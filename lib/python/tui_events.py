"""Bounded, observational UI messages. They never authorize engine actions."""
import json
import os
import sys
import threading
from user_policy import identity_fingerprint, source_fingerprint

from collections import Counter, defaultdict
from tui_i18n import tr

GROUP_KEYS = {'app_store': 'group_appstore', 'npm': 'group_npm',
              'homebrew': 'group_brew', 'vendor': 'group_internet'}
REASONS = {
    'consent_required': 'inventory_reason_consent',
    'scan_partial': 'inventory_reason_evidence',
    'source_unavailable': 'inventory_reason_evidence',
    'source_conflict': 'inventory_reason_conflict',
    'manual_by_policy': 'inventory_reason_manual',
    'ignored_by_policy': 'inventory_reason_excluded',
    'deferred_by_user': 'inventory_reason_deferred',
    'running_app': 'inventory_reason_running',
    'app_running': 'inventory_reason_running',
    'target_running': 'inventory_reason_running',
    'deepseek_manual_only': 'inventory_reason_owner_manual',
    'unsupported_automatic_method': 'inventory_reason_unsupported',
    'resources_pending': 'inventory_reason_deferred',
    'pending_updater_session': 'inventory_reason_deferred',
}
UNCONFIRMED = {'triggered_unconfirmed', 'observed_version_changed',
               'legacy_handler_completed_unconfirmed', 'update_unverified',
               'recovery_required'}
NONFINAL = {'running', 'vendor_updater_observing'}
MAX_DETAILS = 25

UNCONFIRMED_LABELS = {
    'en': 'Vendor completion unconfirmed', 'pl': 'Zakończenie aktualizatora niepotwierdzone',
    'de': 'Abschluss des Anbieterprogramms unbestätigt', 'es': 'Finalización del actualizador sin confirmar',
    'fr': 'Fin du programme fournisseur non confirmée', 'it': 'Completamento del programma del fornitore non confermato',
    'pt': 'Conclusão do atualizador do fornecedor não confirmada',
}


def _safe(value):
    return ''.join(c for c in str(value or '') if c.isprintable())[:160]


def _group(action):
    adapter = action.get('adapter_id')
    if adapter in ('app_store', 'npm', 'homebrew'):
        return adapter
    source = action.get('expected_resolution', {}).get('source')
    return source if source in ('app_store', 'npm', 'homebrew') else 'vendor'


class Reporter:
    def __init__(self, lang='en', output=None):
        self.lang = lang
        self.output = output if output is not None else sys.stdout
        self.lock = threading.RLock()
        self.active = set()
        self.started = set()
        self.shown = set()
        self.finished = set()
        self.pending = {}
        self.counts = defaultdict(Counter)
        self.details = 0
        self._heartbeat_started = False

    def _write(self, line):
        try:
            self.output.write(line + '\n')
            self.output.flush()
        except (OSError, BrokenPipeError, ValueError):
            pass

    def _label(self, key):
        if key == 'cli_unconfirmed':
            return UNCONFIRMED_LABELS.get(self.lang, UNCONFIRMED_LABELS['en'])
        return tr(key, self.lang)

    def phase(self, adapter, status):
        if adapter not in GROUP_KEYS or status not in ('running', 'ok', 'warn', 'error', 'skipped'):
            return
        with self.lock:
            group = self._label(GROUP_KEYS[adapter])
            if status == 'running':
                self.active.add(adapter)
                self._write(group + ': ' + self._label('running'))
                return
            self.active.discard(adapter)
            for identity, action in list(self.pending.items()):
                if _group(action) == adapter:
                    self.target(action, {'status': 'triggered_unconfirmed'})
            for key, count in self.counts.pop(adapter, Counter()).most_common(5):
                self._write('  ' + str(count) + ' × ' + self._label(key))
            self._write(group + ': ' + self._label({'ok': 'completed', 'warn': 'warnings',
                                                    'error': 'failed', 'skipped': 'skipped'}[status]))

    def target(self, action, outcome=None):
        if not isinstance(action, dict):
            return
        identity = _safe(action.get('action_id'))
        if not identity:
            return
        group = _group(action)
        with self.lock:
            if outcome is None:
                if identity in self.started:
                    return
                self.started.add(identity)
                self.pending[identity] = action
                if self.details >= MAX_DETAILS:
                    return
                self.details += 1
                self.shown.add(identity)
                target = action.get('expected_target') or {}
                name = _safe(target.get('name') or target.get('source_identity') or target.get('bundle_id'))
                self._write('  ' + (name or self._label('unknown')) + ': ' + self._label('running'))
                return
            status = outcome.get('status', '')
            if status in NONFINAL or identity in self.finished:
                return
            self.finished.add(identity)
            self.pending.pop(identity, None)
            reason = outcome.get('reason_code', '')
            if identity not in self.started:
                self.counts[group][REASONS.get(reason, 'not_available')] += 1
                return
            if identity not in self.shown:
                key = ('cli_unconfirmed' if status in UNCONFIRMED else
                       'failed' if status in ('update_failed', 'failed') else
                       REASONS.get(reason, 'completed'))
                self.counts[group][key] += 1
                return
            target = action.get('expected_target') or {}
            name = _safe(target.get('name') or target.get('source_identity') or target.get('bundle_id'))
            label = ('cli_unconfirmed' if status in UNCONFIRMED else
                     'failed' if status in ('update_failed', 'failed', 'source_unavailable') else
                     'toolkit_status_updated' if status == 'current_verified' and
                     reason == 'updated_verified' and outcome.get('verified') is True else
                     'toolkit_status_current' if status == 'current_verified' else
                     REASONS.get(reason) if reason in REASONS else 'completed')
            details = self._label(label)
            if outcome.get('verified') is True and outcome.get('after'):
                details += ' (' + _safe(outcome['after']) + ')'
            self._write('  ' + (name or self._label('unknown')) + ': ' + details)

    def tick(self):
        with self.lock:
            if self.active:
                names = ', '.join(self._label(GROUP_KEYS[a]) for a in sorted(self.active))
                self._write(names + ': ' + self._label('activity_unknown'))

    def start_heartbeat(self):
        with self.lock:
            if self._heartbeat_started:
                return
            self._heartbeat_started = True
        def loop():
            while True:
                threading.Event().wait(15)
                self.tick()
        threading.Thread(target=loop, daemon=True, name='cli-progress').start()


_OUTPUT_LOCK = threading.Lock()


_CLI_REPORTER = None
_CLI_REPORTER_LOCK = threading.Lock()


def _cli_reporter():
    global _CLI_REPORTER
    if os.environ.get('MAC_UPDATE_CLI_PROGRESS') != '1':
        return None
    with _CLI_REPORTER_LOCK:
        if _CLI_REPORTER is None:
            _CLI_REPORTER = Reporter(os.environ.get('MAC_LANG', 'en'))
        return _CLI_REPORTER


def _text(value):
    return ''.join(c for c in str(value or '') if c.isprintable())[:500]


def emit(kind, payload=None, output=None):
    if os.environ.get('MAC_UPDATE_TUI_CHILD') != '1':
        return
    output = sys.stdout if output is None else output
    line = '@@MAC_UPDATE_' + kind
    if payload is not None:
        line += ' ' + json.dumps(payload, ensure_ascii=True, separators=(',', ':'))
    if len(line) > 8192:
        return
    try:
        with _OUTPUT_LOCK:
            output.write(line + "\n")
            output.flush()
    except (BrokenPipeError, OSError):
        pass


def candidate(action):
    target, resolution = action['expected_target'], action['expected_resolution']
    reasons = action.get('reason_codes', [])
    name = target.get('name') or target.get('source_identity') or target.get('bundle_id') or action['target_path']
    if isinstance(name, str) and name.startswith(('formula:', 'cask:')):
        name = name.partition(':')[2]
    excluded = 'ignored_by_policy' in reasons
    return dict(id=action['action_id'], target=dict(action['target']),
                identity_fingerprint=identity_fingerprint(target), source_fingerprint=source_fingerprint(target, resolution),
                name=_text(name), version=_text(action.get('from_version')), source=resolution['source'],
                status='excluded' if excluded else 'manual' if action['kind'] == 'manual' else 'blocked' if any(r != 'consent_required' for r in reasons) else 'enabled',
                reasons=[_text(r) for r in reasons[:20]], path=_text(action['target_path']),
                enabled=not excluded, kind=action['target']['kind'])


def emit_plan(plan, output=None):
    if os.environ.get('MAC_UPDATE_TUI_CHILD') != '1':
        return
    emit('CANDIDATES_BEGIN', output=output)
    for action in plan['actions']:
        try:
            emit('CANDIDATE', candidate(action), output)
        except (KeyError, TypeError, ValueError):
            continue
    emit('CANDIDATES_END', output=output)


def emit_target(action, outcome=None):
    if os.environ.get('MAC_UPDATE_TUI_CHILD') != '1':
        try:
            reporter = _cli_reporter()
            if reporter:
                reporter.target(action, outcome)
        except Exception:
            pass  # Observation must never change update execution.
        return
    try:
        row = candidate(action)
    except (KeyError, TypeError, ValueError):
        return
    result = dict(target=row['target'], identity_fingerprint=row['identity_fingerprint'],
                  source_fingerprint=row['source_fingerprint'], status='running', verified=False)
    if outcome is not None:
        result.update(status=_text(outcome.get('status')), verified=outcome.get('verified') is True,
                      reason_code=_text(outcome.get('reason_code')), after=_text(outcome.get('after')))
    emit('TARGET', result)


def emit_phase(adapter, status):
    """Closed phase protocol shared by the serial and mixed supervisors."""
    if os.environ.get('MAC_UPDATE_TUI_CHILD') != '1':
        try:
            reporter = _cli_reporter()
            if reporter:
                reporter.phase(adapter, status)
                if status == 'running':
                    reporter.start_heartbeat()
        except Exception:
            pass  # Observation must never change update execution.
        return
    phases = {'app_store': 'appstore', 'npm': 'npmcli', 'homebrew': 'brew', 'vendor': 'internet'}
    if adapter not in phases or status not in ('running', 'ok', 'warn', 'error', 'skipped'):
        return
    try:
        with _OUTPUT_LOCK:
            sys.stdout.write('@@MAC_UPDATE_PHASE ' + phases[adapter] + ' ' + status + '\n')
            sys.stdout.flush()
    except (BrokenPipeError, OSError):
        pass
