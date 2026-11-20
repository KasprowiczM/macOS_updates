"""Scoped App Store iPad action. GUI and installed observations are injected.

The environment must attest the product ID on the *displayed* page and expose
stable control IDs. Opening a URL alone is not such an attestation. This module
never invokes AppleScript itself; unsupported environments must defer.
"""

_KEYS = ('expected_target', 'target_path', 'identity_fingerprint', 'store_id')
_UPDATE_LABELS = frozenset(('Update', 'Uaktualnij', 'Aktualizuj', 'Aktualisieren',
                            'Actualizar', 'Aggiorna', 'Atualizar', 'Mettre à jour',
                            'Actualiser'))


def _result(status, reason, started=False, verified=False):
    return dict(status=status, reason_code=reason, verified=verified,
                mutation_started=started, recovery_required=started and not verified)


def _same_identity(action, observed):
    return isinstance(observed, dict) and all(observed.get(k) == action[k] for k in _KEYS)


def _control(page, store_id):
    if not isinstance(page, dict) or page.get('store_id') != store_id:
        return None, 'unproven_product'
    controls = page.get('controls')
    if not isinstance(controls, list):
        return None, 'inaccessible_ui'
    matches = []
    for control in controls:
        if not isinstance(control, dict):
            return None, 'inaccessible_ui'
        labels = (control.get('name'), control.get('description'), control.get('title'))
        if any(isinstance(label, str) and label.casefold() in
               {item.casefold() for item in _UPDATE_LABELS} for label in labels):
            matches.append(control.get('id'))
    if len(matches) > 1 or (matches and not matches[0]):
        return None, 'ambiguous_control'
    return (matches[0], None) if matches else (None, 'not_offered')


def execute_ipad_update(action, authorize, environment):
    """Execute one target action; uncertain post-click state retains its lease.

    `authorize(action)` must check current scope, not merely cached consent.
    `observe_completion` must attest helper completion for this exact identity;
    changed versions, a click, or an opened page are insufficient evidence.
    """
    if (not isinstance(action, dict) or any(not isinstance(action.get(k), str)
            or not action[k] for k in _KEYS) or not action['store_id'].isascii()
            or not action['store_id'].isdigit()):
        return _result('deferred', 'invalid_identity')
    import time
    started = False
    try:
        if not _same_identity(action, environment.observe_identity(action)):
            return _result('deferred', 'identity_changed')
        if not authorize(action):
            return _result('deferred', 'not_authorized')
        environment.open_product(action['store_id'])
        # Ten three-second intervals; one refresh halfway through the budget.
        control = None
        deadline = time.monotonic() + 30
        for attempt in range(11):
            control, reason = _control(environment.observe_page(), action['store_id'])
            if reason == 'ambiguous_control':
                return _result('deferred', reason)
            if control:
                break
            remaining = deadline - time.monotonic()
            if attempt == 10 or remaining <= 0:
                return _result('deferred', reason or 'not_offered')
            if attempt == 5 and reason == 'not_offered':
                environment.refresh()
            environment.wait(min(3, remaining))
        if not _same_identity(action, environment.observe_identity(action)):
            return _result('deferred', 'identity_changed')
        if not authorize(action):
            return _result('deferred', 'not_authorized')
        current, reason = _control(environment.observe_page(), action['store_id'])
        if reason or current != control:
            return _result('deferred', reason or 'control_changed')
        # A failing click may still have started an asynchronous installation.
        started = True
        environment.click(control)
        evidence = environment.observe_completion(action)
        if (isinstance(evidence, dict) and evidence.get('completed') is True
                and evidence.get('store_id') == action['store_id']
                and evidence.get('identity_fingerprint') == action['identity_fingerprint']):
            return _result('completed', 'helper_completed', started=True, verified=True)
        return _result('unconfirmed', 'completion_unknown', started=True)
    except Exception:
        return _result('unconfirmed' if started else 'deferred',
                       'completion_unknown' if started else 'environment_unavailable', started)

# AXURL on the front window is the only accepted page identity proof. Some
# App Store releases do not expose it; those versions are intentionally manual.
_PAGE_SCRIPT = r'''
-- PAGE_RESULT: only a front window with an exact product URL is actionable.
on run argv
    set pid to item 1 of argv
    set mode to item 2 of argv
    set wantedIndex to 0
    if mode is "click" then set wantedIndex to (item 3 of argv) as integer
    tell application "System Events" to tell process "App Store"
        set w to window 1
        try
            set pageURL to value of attribute "AXURL" of w as text
        on error
            return ""
        end try
        if pageURL is not ("https://apps.apple.com/app/id" & pid) and pageURL is not ("macappstores://apps.apple.com/app/id" & pid) then return ""
        set elems to entire contents of w
        set matches to {}
        set matchLabels to {}
        repeat with i from 1 to count of elems
            set elem to item i of elems
            try
                if class of elem is button then
                    set labels to {}
                    try
                        set end of labels to name of elem as text
                    end try
                    try
                        set end of labels to description of elem as text
                    end try
                    try
                        set end of labels to title of elem as text
                    end try
                    repeat with lbl in labels
                        if lbl is in {"Update", "Uaktualnij", "Aktualizuj", "Aktualisieren", "Actualizar", "Aggiorna", "Atualizar", "Mettre à jour", "Actualiser"} then
                            set end of matches to i
                            set end of matchLabels to contents of lbl
                            exit repeat
                        end if
                    end repeat
                end if
            end try
        end repeat
        if mode is "click" then
            if (count of matches) is not 1 or (item 1 of matches) is not wantedIndex then error "target control changed"
            click item wantedIndex of elems
            return "CLICKED"
        end if
        set resultText to pid
        repeat with i from 1 to count of matches
            set resultText to resultText & tab & (item i of matches) & tab & (item i of matchLabels)
        end repeat
        return resultText
    end tell
end run
'''

_OPEN_SCRIPT = r'''
on run argv
    tell application "App Store" to activate
    open location "macappstores://apps.apple.com/app/id" & (item 1 of argv)
end run
'''
_REFRESH_SCRIPT = r'''
tell application "System Events" to tell process "App Store" to keystroke "r" using command down
'''


def _native_runner(script, args):
    import subprocess
    result = subprocess.run(['osascript', '-e', script, '--'] + list(args),
                            capture_output=True, text=True, timeout=15, check=True)
    return result.stdout.strip()


class NativeAppStoreEnvironment:
    """Native backend; caller supplies fresh installed-identity observation.

    There is no native helper-completion proof yet, so a click is unconfirmed.
    `runner` and `sleep` are injectable to test without controlling the host.
    """
    def __init__(self, observe_identity, runner=None, sleep=None):
        import time
        self.observe_identity = observe_identity
        self._runner = runner or _native_runner
        self._sleep = sleep or time.sleep
        self._store_id = None

    def open_product(self, store_id):
        if not store_id.isascii() or not store_id.isdigit():
            raise ValueError('invalid store id')
        self._store_id = store_id
        self._runner(_OPEN_SCRIPT, [store_id])

    def observe_page(self):
        output = self._runner(_PAGE_SCRIPT, [self._store_id, 'observe'])
        fields = output.split('\t') if output else []
        if not fields or fields[0] != self._store_id or len(fields) % 2 != 1:
            return dict(store_id=None, controls=[])
        controls = []
        for index in range(1, len(fields), 2):
            if not fields[index].isascii() or not fields[index].isdigit():
                return dict(store_id=None, controls=[])
            controls.append(dict(id=fields[index], name=fields[index + 1]))
        return dict(store_id=fields[0], controls=controls)

    def refresh(self):
        self._runner(_REFRESH_SCRIPT, [])

    def wait(self, seconds):
        self._sleep(seconds)

    def click(self, control_id):
        if not control_id.isascii() or not control_id.isdigit():
            raise ValueError('invalid control id')
        if self._runner(_PAGE_SCRIPT, [self._store_id, 'click', control_id]) != 'CLICKED':
            raise RuntimeError('click unconfirmed')

    def observe_completion(self, action):
        return None
