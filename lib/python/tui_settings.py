"""One schema table drives the Settings screen, the saved file and the
environment handed to the update engine.

Only settings that the toolkit actually honours appear here: each row maps
to a verified MAC_UPDATE_* variable, an update_all.sh flag, a config file, a
script flag of scripts/install_launchagent.sh, or interface-only behaviour.
"""
import json
import os
import plistlib
import stat
import tempfile

GROUPS = ('prescan', 'appstore', 'cli', 'brew', 'internet', 'inventory', 'system')
UPDATE_GROUPS = GROUPS
# Verified flags of lib/cli.sh (update_all.sh). The engine's "cli" group is
# still spelled --skip-npm and "inventory" is the post-update step.
SKIP_FLAGS = dict(prescan='--skip-prescan', appstore='--skip-appstore', cli='--skip-npm', brew='--skip-brew',
                  internet='--skip-internet', inventory='--skip-postupdate', system='--skip-system')
LANGUAGES = ('en', 'pl', 'de', 'es', 'fr', 'it', 'pt')
NATIVE_NAMES = dict(en='English', pl='Polski', de='Deutsch', es='Español', fr='Français', it='Italiano', pt='Português')
SETTINGS_FILE = 'tui-settings.json'
SECTIONS = ('groups', 'apps', 'schedule', 'safety', 'network', 'notify', 'look', 'system')
SECTION_LABELS = dict(groups='ui_sec_groups', apps='ui_sec_apps', schedule='ui_sec_schedule', safety='ui_sec_safety',
                      network='ui_sec_network', notify='ui_sec_notify', look='ui_sec_look', system='ui_sec_system')
PROFILES = ('full', 'careful', 'check')


class Setting:
    """kind: bool | choice | int | action | info. ``env`` names the variable
    exported to the child; ``to_env`` converts the value."""
    __slots__ = ('key', 'kind', 'default', 'env', 'section', 'label', 'help', 'choices', 'low', 'high', 'step',
                 'to_env', 'from_env', 'local')

    def __init__(self, key, kind, default, section, label, help, env=None, choices=(), low=0, high=0, step=1,
                 to_env=None, from_env=None, local=False):
        self.key, self.kind, self.default, self.section = key, kind, default, section
        self.label, self.help, self.env, self.choices = label, help, env, tuple(choices)
        self.low, self.high, self.step = low, high, step
        self.to_env, self.from_env, self.local = to_env, from_env, local


def _b(value):
    return '1' if value else '0'


def _from_b(text):
    return text.strip() in ('1', 'true', 'yes', 'on')


SCHEMA = [Setting('group_' + g, 'bool', True, 'groups', 'ui_set_group', 'ui_set_group_help') for g in GROUPS] + [
    Setting('check_only', 'bool', False, 'groups', 'ui_set_check_only', 'ui_set_check_only_help'),
    Setting('allow_major', 'bool', False, 'groups', 'ui_set_allow_major', 'ui_set_allow_major_help',
            env='MAC_UPDATE_ALLOW_MAJOR_UPGRADE', to_env=_b, from_env=_from_b),
    # macOS updates: install (auto), only report them (notify), or do not check (skip).
    Setting('system_mode', 'choice', 'auto', 'groups', 'ui_set_system_mode', 'ui_set_system_mode_help',
            env='MAC_UPDATE_SYSTEM_MODE', choices=('auto', 'notify', 'skip')),
    # Newly detected apps that are not on the tested list: by detection
    # confidence (default), always automatic, or always manual.
    Setting('new_app_mode', 'choice', 'default', 'apps', 'ui_set_new_app_mode', 'ui_set_new_app_mode_help',
            env='MAC_UPDATE_NEW_APP_MODE', choices=('default', 'auto', 'manual'),
            to_env=lambda v: '' if v == 'default' else v,
            from_env=lambda t: t.strip().lower() if t.strip().lower() in ('auto', 'manual') else 'default'),
    Setting('open_apps', 'action', None, 'apps', 'ui_set_open_apps', 'ui_set_open_apps_help'),
    Setting('exclusions', 'info', None, 'apps', 'ui_set_exclusions', 'ui_set_exclusions_help'),
    Setting('npm_clis', 'info', None, 'apps', 'ui_set_npm_clis', 'ui_set_npm_clis_help'),
    # Daily automation (scripts/install_launchagent.sh). Off by default and no
    # time or trigger is preselected: turning it on asks for each and confirms.
    Setting('schedule', 'action', None, 'schedule', 'ui_set_schedule', 'ui_set_schedule_help'),
    Setting('schedule_test', 'action', None, 'schedule', 'ui_set_schedule_test', 'ui_set_schedule_test_help'),
    # Off by default: scheduled runs skip macOS updates unless this is on when the
    # automation is turned on (install_launchagent.sh --system-updates).
    Setting('schedule_system', 'bool', False, 'schedule', 'ui_set_schedule_system', 'ui_set_schedule_system_help',
            local=True),
    Setting('quit_wait', 'int', 60, 'safety', 'ui_set_quit_wait', 'ui_set_quit_wait_help', env='MAC_UPDATE_QUIT_WAIT',
            low=0, high=300, step=10),
    Setting('vendor_direct', 'bool', True, 'safety', 'ui_set_vendor_direct', 'ui_set_vendor_direct_help',
            env='MAC_UPDATE_VENDOR_DIRECT', to_env=_b, from_env=_from_b),
    Setting('min_free_gb', 'int', 15, 'safety', 'ui_set_min_free_gb', 'ui_set_min_free_gb_help',
            env='MAC_UPDATE_MIN_FREE_GB', low=1, high=500),
    Setting('min_battery', 'int', 30, 'safety', 'ui_set_min_battery', 'ui_set_min_battery_help',
            env='MAC_UPDATE_MIN_BATTERY', low=0, high=100, step=5),
    Setting('feed_ttl', 'int', 24, 'network', 'ui_set_feed_ttl', 'ui_set_feed_ttl_help',
            env='MAC_UPDATE_FEED_CACHE_TTL_H', low=0, high=168),
    Setting('prompt_timeout', 'int', 120, 'network', 'ui_set_prompt_timeout', 'ui_set_prompt_timeout_help',
            env='MAC_UPDATE_PROMPT_TIMEOUT', low=10, high=900, step=10),
    Setting('mas_timeout', 'int', 1800, 'network', 'ui_set_mas_timeout', 'ui_set_mas_timeout_help',
            env='MAC_UPDATE_MAS_UPGRADE_TIMEOUT', low=60, high=7200, step=60),
    Setting('github_token', 'info', None, 'network', 'ui_set_github_token', 'ui_set_github_token_help'),
    Setting('notify', 'choice', 'never', 'notify', 'ui_set_notify', 'ui_set_notify_help', env='MAC_UPDATE_NOTIFY',
            choices=('always', 'never'), to_env=lambda v: _b(v == 'always'),
            from_env=lambda t: 'always' if _from_b(t) else 'never'),
    Setting('open_last_log', 'action', None, 'notify', 'ui_set_open_last_log', 'ui_set_open_last_log_help'),
    Setting('max_logs', 'int', 30, 'notify', 'ui_set_max_logs', 'ui_set_max_logs_help', env='MAC_UPDATE_MAX_LOGS',
            low=1, high=500, step=5),
    Setting('language', 'choice', 'en', 'look', 'ui_set_language', 'ui_set_language_help', choices=LANGUAGES,
            env='MAC_UPDATE_LANG'),
    Setting('theme', 'choice', 'auto', 'look', 'ui_set_theme', 'ui_set_theme_help', choices=('auto', 'dark', 'light'), local=True),
    Setting('accent', 'choice', 'blue', 'look', 'ui_set_accent', 'ui_set_accent_help',
            choices=('blue', 'violet', 'amber', 'green', 'rose', 'graphite'), local=True),
    Setting('density', 'choice', 'comfortable', 'look', 'ui_set_density', 'ui_set_density_help',
            choices=('comfortable', 'compact'), local=True),
    Setting('ascii', 'bool', False, 'look', 'ui_set_ascii', 'ui_set_ascii_help', local=True),
    Setting('auto_resize', 'bool', True, 'look', 'ui_set_auto_resize', 'ui_set_auto_resize_help', local=True),
    Setting('mouse', 'bool', True, 'look', 'ui_set_mouse', 'ui_set_mouse_help', local=True),
    Setting('help_open', 'bool', True, 'look', 'ui_set_help_open', 'ui_set_help_open_help', local=True),
    Setting('mau_deferral', 'int', 7, 'system', 'ui_set_mau_deferral', 'ui_set_mau_deferral_help',
            env='MAC_UPDATE_MAU_DEFERRAL_DAYS', low=0, high=60),
    Setting('keep_awake', 'bool', True, 'system', 'ui_set_keep_awake', 'ui_set_keep_awake_help',
            env='MAC_UPDATE_NO_CAFFEINATE', to_env=lambda v: _b(not v), from_env=lambda t: not _from_b(t)),
    Setting('scan_now', 'action', None, 'system', 'ui_diag_inventory', 'ui_diag_inventory_help'),
    Setting('open_diagnostics', 'action', None, 'system', 'ui_set_open_diag', 'ui_set_open_diag_help'),
    Setting('toolkit_update', 'action', None, 'system', 'ui_set_toolkit', 'ui_set_toolkit_help'),
    Setting('export', 'action', None, 'system', 'ui_set_export', 'ui_set_export_help'),
    Setting('import', 'action', None, 'system', 'ui_set_import', 'ui_set_import_help'),
    Setting('reset', 'action', None, 'system', 'ui_set_reset', 'ui_set_reset_help'),
]
BY_KEY = {s.key: s for s in SCHEMA}
VALUE_KEYS = tuple(s.key for s in SCHEMA if s.kind in ('bool', 'choice', 'int'))
PROFILE_VALUES = dict(
    full=dict(check_only=False, allow_major=False, system_mode='auto', **{'group_' + g: True for g in GROUPS}),
    careful=dict(check_only=False, allow_major=False, system_mode='notify',
                 **{'group_' + g: True for g in GROUPS}),
    check=dict(check_only=True),
)


def coerce(setting, value):
    """Return a valid value for ``setting`` or raise ValueError."""
    if setting.kind == 'bool':
        if type(value) is bool:
            return value
        raise ValueError('bool')
    if setting.kind == 'choice':
        value = str(value)
        if value in setting.choices:
            return value
        raise ValueError('choice')
    if setting.kind == 'int':
        if type(value) is bool:
            raise ValueError('int')
        value = int(value)
        if setting.low <= value <= setting.high:
            return value
        raise ValueError('range')
    raise ValueError('kind')


def defaults():
    return {key: BY_KEY[key].default for key in VALUE_KEYS}


_OLD_ACCENTS = dict(cyan='blue', magenta='violet', orange='amber')
LOOK_VERSION = 2     # files written before the Auto colours choice carry no look_version


def system_language(environ, home=None):
    """The Mac's language when the user has not chosen one: MAC_LANG (CLI
    preference), then AppleLanguages/AppleLocale, then LANG/LC_*; else English."""
    hint = environ.get('MAC_LANG')
    if hint in LANGUAGES:
        return hint
    path = os.path.join(home or os.path.expanduser('~'), 'Library', 'Preferences', '.GlobalPreferences.plist')
    try:
        if os.path.isfile(path) and os.path.getsize(path) < 4 * 1024 * 1024:
            with open(path, 'rb') as handle:
                prefs = plistlib.load(handle)
            languages = prefs.get('AppleLanguages') or []
            for value in list(languages[:1]) + [prefs.get('AppleLocale') or '']:
                code = str(value)[:2].lower()
                if code in LANGUAGES:
                    return code
    except Exception:   # unreadable preferences: fall through to the environment
        pass
    for name in ('LC_ALL', 'LC_MESSAGES', 'LANG'):
        code = str(environ.get(name) or '')[:2].lower()
        if code in LANGUAGES and code != 'c':
            return code
    return 'en'


def _migrate(raw):
    """Accept the previous tui-settings.json layout (groups list, npm id)."""
    out = dict(raw)
    if raw.get('theme') == 'dark' and 'look_version' not in raw:
        # "dark" was the only default before Auto existed and every save wrote it, so it never was a choice.
        out['theme'] = 'auto'
    if raw.get('accent') in _OLD_ACCENTS:
        out['accent'] = _OLD_ACCENTS[raw['accent']]
    groups = raw.get('groups')
    if isinstance(groups, list):
        names = {'npm': 'cli'}
        chosen = {names.get(g, g) for g in groups if isinstance(g, str)}
        for g in ('appstore', 'cli', 'brew', 'internet', 'system'):
            out.setdefault('group_' + g, g in chosen)
    return out


class SettingsStore:
    """Values, where each came from (default/file/env), and atomic saving."""

    def __init__(self, state_dir=None, environ=None, home=None):
        self.state_dir = state_dir
        self.home = home
        self.language_explicit = False
        self.session_language = False
        self.file_language = None
        self.environ = dict(os.environ if environ is None else environ)
        self.values = defaults()
        self.origin = {key: 'default' for key in VALUE_KEYS}
        self.error = None
        self.load()

    @property
    def path(self):
        root = self.state_dir
        if not root:
            import mu_paths
            try:
                root = mu_paths.state_dir()
            except mu_paths.PathError:
                root = os.path.join(os.path.expanduser('~/.local/state'), 'mac-update')
        return os.path.join(root, SETTINGS_FILE)

    def load(self):
        raw = {}
        try:
            data = read_private(self.path, 65536)
            if data is not None:
                loaded = json.loads(data.decode('utf-8'))
                raw = loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError) as exc:     # unsafe or malformed: defaults, never a crash
            self.error = str(exc)
        self.apply_raw(_migrate(raw), origin='file')
        # Language: an explicit choice saved in Settings wins over the Mac's
        # language; files from the old interface never held a real choice.
        legacy = isinstance(raw.get('groups'), list) or 'wizard_complete' in raw
        self.language_explicit = raw.get('language') in LANGUAGES and not legacy
        self.file_language = raw.get('language') if self.language_explicit else None
        if not self.language_explicit:
            self.values['language'] = system_language(self.environ, self.home)
            self.origin['language'] = 'default'
        session = self.environ.get('MAC_UPDATE_LANG')
        if session in LANGUAGES:          # one-session override, never saved
            self.values['language'] = session
            self.session_language = True
        for setting in SCHEMA:
            if setting.env and setting.kind != 'action' and setting.key != 'language':
                text = self.environ.get(setting.env)
                if text is None or text == '':
                    continue
                try:
                    value = setting.from_env(text) if setting.from_env else text
                    self.values[setting.key] = coerce(setting, value)
                    self.origin[setting.key] = 'env'
                except (ValueError, TypeError):
                    continue

    def apply_raw(self, raw, origin):
        for key in VALUE_KEYS:
            if key in raw:
                try:
                    self.values[key] = coerce(BY_KEY[key], raw[key])
                    self.origin[key] = origin if raw[key] != BY_KEY[key].default else 'default'
                except (ValueError, TypeError):
                    continue

    def get(self, key):
        return self.values[key]

    def set(self, key, value, save=True):
        setting = BY_KEY[key]
        if self.origin.get(key) == 'env':
            raise PermissionError(setting.env)
        self.values[key] = coerce(setting, value)
        self.origin[key] = 'default' if self.values[key] == setting.default else 'file'
        if key == 'language':
            self.language_explicit, self.session_language = True, False
            self.origin[key] = 'file'
        if save:
            self.save()

    def save(self):
        data = {key: self.values[key] for key in VALUE_KEYS if self.origin.get(key) != 'env'
                and (key != 'language' or self.language_explicit)}
        data['look_version'] = LOOK_VERSION
        if self.session_language and self.language_explicit:
            data['language'] = self.file_language
        elif self.language_explicit:
            self.file_language = self.values['language']
        atomic_write(self.path, (json.dumps(data, ensure_ascii=True, sort_keys=True, indent=1) + '\n').encode(), private_root=True)

    def reset(self):
        for key in VALUE_KEYS:
            if self.origin.get(key) != 'env':
                self.values[key] = BY_KEY[key].default
                self.origin[key] = 'default'
        self.language_explicit = self.session_language = False
        self.values['language'] = system_language(self.environ, self.home)
        self.save()

    # -- profiles -------------------------------------------------------
    def profile(self):
        v = self.values
        if v['check_only']:
            return 'check'
        groups = [v['group_' + g] for g in GROUPS]
        if all(groups) and not v['allow_major'] and v.get('system_mode', 'auto') == 'auto':
            return 'full'
        if all(groups) and not v['allow_major'] and v.get('system_mode') == 'notify':
            return 'careful'
        return 'custom'

    def apply_profile(self, name):
        for key, value in PROFILE_VALUES[name].items():
            if self.origin.get(key) != 'env':
                self.values[key] = value
                self.origin[key] = 'default' if value == BY_KEY[key].default else 'file'
        self.save()

    # -- settings passed to the engine ------------------------------------
    def groups(self):
        return [g for g in GROUPS if self.values['group_' + g]]

    def child_env(self):
        env = {}
        for setting in SCHEMA:
            if not setting.env or setting.kind not in ('bool', 'choice', 'int'):
                continue
            value = self.values[setting.key]
            env[setting.env] = setting.to_env(value) if setting.to_env else str(value)
        env['MAC_LANG'] = self.values['language']
        return env

    def flags(self, dry_run=False, groups=None):
        """Engine flags; ``groups`` is the list of groups to run (default: those turned on in Settings)."""
        flags = []
        if dry_run or self.values['check_only']:
            flags.append('--dry-run')
        chosen = self.groups() if groups is None else list(groups)
        flags.extend(SKIP_FLAGS[g] for g in GROUPS if g not in chosen)
        return flags

    # -- export / import --------------------------------------------------
    def export_data(self, overrides):
        return dict(format='mac-update-settings', version=1,
                    settings={key: self.values[key] for key in VALUE_KEYS},
                    overrides=[list(row) for row in overrides])

    def import_data(self, data):
        if not isinstance(data, dict) or data.get('format') != 'mac-update-settings':
            raise ValueError('not_a_settings_file')
        settings = data.get('settings')
        if not isinstance(settings, dict):
            raise ValueError('not_a_settings_file')
        for key, value in settings.items():
            if key in BY_KEY and key in VALUE_KEYS and self.origin.get(key) != 'env':
                try:
                    self.values[key] = coerce(BY_KEY[key], value)
                    self.origin[key] = 'default' if self.values[key] == BY_KEY[key].default else 'file'
                except (ValueError, TypeError):
                    continue
        self.save()
        rows = data.get('overrides', [])
        return rows if isinstance(rows, list) else []


def read_private(path, limit, strict=True):
    """Read a state file. Strict: regular, owned, mode 0600, one link.
    Lenient (hand-edited files): regular, owned, not a symlink.
    Returns None when it does not exist; raises OSError when it is unsafe."""
    from inventory_store import StoreError, _open_regular
    if not os.path.lexists(path):
        return None
    if strict:
        try:
            fd = _open_regular(path, os.O_RDONLY)
        except StoreError as exc:
            raise OSError('unsafe state file: ' + os.path.basename(path)) from exc
    else:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            os.close(fd)
            raise OSError('unsafe state file: ' + os.path.basename(path))
    with os.fdopen(fd, 'rb') as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise OSError('state file too large: ' + os.path.basename(path))
    return data


def atomic_write(path, data, mode=0o600, private_root=False):
    directory = os.path.dirname(path)
    if private_root:
        # The state directory must be private (0700, owned, no symlinked ancestor).
        from inventory_store import StoreError, _root
        try:
            _root(directory, True)
        except StoreError as exc:
            raise OSError(str(exc)) from exc
    else:
        os.makedirs(directory, mode=0o700, exist_ok=True)
    if os.path.islink(path) or (os.path.exists(path) and os.stat(path).st_nlink != 1):
        raise OSError('refusing to replace a link: ' + path)
    fd, temporary = tempfile.mkstemp(prefix='.tmp-', dir=directory)
    try:
        with os.fdopen(fd, 'wb') as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


# -- read-only facts shown in Settings --------------------------------------
def count_config_lines(repo, name):
    try:
        with open(os.path.join(repo, 'config', name), encoding='utf-8', errors='replace') as handle:
            return sum(1 for line in handle if line.strip() and not line.lstrip().startswith('#'))
    except OSError:
        return None


def github_token_present(environ=None):
    environ = os.environ if environ is None else environ
    return bool(environ.get('GITHUB_TOKEN'))


DAILY_LABEL = 'site.64bit.mac-update.daily'


def launchagent_path(home=None):
    return os.path.join(home or os.path.expanduser('~'), 'Library', 'LaunchAgents', DAILY_LABEL + '.plist')


def legacy_launchagent_path(home=None):
    import pwd
    user = pwd.getpwuid(os.getuid()).pw_name
    return os.path.join(home or os.path.expanduser('~'), 'Library', 'LaunchAgents', 'com.%s.macos-updates.plist' % user)


def _read_plist(path):
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_size > 262144:
        raise ValueError('not a plain plist')
    with open(path, 'rb') as handle:
        return plistlib.load(handle)


def schedule_status(home=None):
    """Read the LaunchAgent written by install_launchagent.sh (files only, no
    launchctl), with the fields of its ``--status --json``.

    Returns dict(state='on'|'off'|'unknown', triggers=[...], notify, delay_min,
    legacy=bool, plist). A trigger is {'type': 'login'} or {'type': 'calendar',
    'weekday': None|0-7, 'hour', 'minute'}."""
    for path, legacy in ((launchagent_path(home), False), (legacy_launchagent_path(home), True)):
        try:
            data = _read_plist(path)
        except FileNotFoundError:
            continue
        except Exception:  # malformed plist: show unknown rather than crash
            return dict(state='unknown', plist=path, legacy=legacy)
        triggers = [dict(type='login')] if data.get('RunAtLoad') else []
        cal = data.get('StartCalendarInterval')
        for c in ([cal] if isinstance(cal, dict) else cal or []):
            if isinstance(c, dict) and not ('Month' in c and 'Day' in c):
                triggers.append(dict(type='calendar', weekday=c.get('Weekday'), hour=c.get('Hour', 0),
                                     minute=c.get('Minute', 0)))
        env = data.get('EnvironmentVariables') or {}
        try:
            delay = int(env.get('MAC_UPDATE_DELAY_MIN') or 0)
        except (TypeError, ValueError):
            delay = 0
        return dict(state='on', triggers=triggers, notify=env.get('MAC_UPDATE_NOTIFY'), delay_min=delay,
                    legacy=legacy, plist=path,
                    system_updates=env.get('MAC_UPDATE_AUTOMATION_SYSTEM_UPDATES') == '1')
    return dict(state='off')


SCHEDULE_TRIGGERS = ('daily', 'login', 'both')
SCHEDULE_NOTIFY = ('needs_you', 'always', 'never')
TEST_RUN_MINUTES = 2


def parse_hhmm(text):
    """'9:05' / '09:05' -> (9, 5); anything else raises ValueError."""
    import re
    match = re.fullmatch(r'\s*([01]?\d|2[0-3]):([0-5]\d)\s*', str(text))
    if not match:
        raise ValueError('time')
    return int(match.group(1)), int(match.group(2))


def schedule_args(trigger, time_text=None, notify='needs_you', system_updates=False):
    """Exact install_launchagent.sh arguments for an explicit choice. There is
    no default trigger or time; an incomplete choice raises ValueError."""
    if trigger not in SCHEDULE_TRIGGERS or notify not in SCHEDULE_NOTIFY:
        raise ValueError('schedule')
    args = []
    if trigger in ('daily', 'both'):
        hour, minute = parse_hhmm(time_text or '')
        args += ['--daily', '%02d:%02d' % (hour, minute)]
    if trigger in ('login', 'both'):
        args += ['--at-login']
    args += ['--notify', notify]
    if system_updates:
        args += ['--system-updates']
    return args


def schedule_command(repo, args):
    return ['/bin/bash', os.path.join(repo, 'scripts', 'install_launchagent.sh')] + list(args)
