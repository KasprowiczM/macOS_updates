"""Per-app tuning: ``<config>/overrides.tsv`` (lib/python/mu_paths.py).

While that file does not exist yet, the old ``<state>/user_overrides.tsv`` is
read; the first save writes the new file (the old one is left as it was, the
engine then reads the new one). MAC_UPDATE_OVERRIDES_FILE wins for both.
Line format: group<TAB>id<TAB>mode<TAB>source. Missing apps are automatic.
The file is read leniently (bad lines are kept aside, never fatal) and
written atomically.
"""
import os

from tui_settings import atomic_write, read_private

GROUPS = ('appstore', 'cli', 'brew', 'cask', 'internet', 'system')
MODES = ('auto', 'manual', 'skip')
SOURCES = ('', 'brew', 'appstore', 'vendor', 'native')
FILENAME = 'user_overrides.tsv'          # old location, in the state folder
CONFIG_FILENAME = 'overrides.tsv'        # current location, in the config folder
HEADER = '# group\tid\tmode\tsource — written by the macOS Updates terminal interface\n'


def state_dir(explicit=None):
    if explicit:
        return explicit
    import mu_paths
    try:
        return mu_paths.state_dir()
    except mu_paths.PathError:
        return os.path.join(os.path.expanduser('~/.local/state'), 'mac-update')


def _valid(group, ident, mode, source):
    return (group in GROUPS and ident and '\t' not in ident and '\n' not in ident and len(ident) <= 512
            and mode in MODES and source in SOURCES)


def config_dir(explicit=None):
    if explicit:
        return explicit
    import mu_paths
    try:
        return mu_paths.config_dir()
    except mu_paths.PathError:
        return os.path.join(os.path.expanduser('~/.config'), 'mac-update')


class OverrideStore:
    def __init__(self, directory=None, config=None):
        override = os.environ.get('MAC_UPDATE_OVERRIDES_FILE')
        self.path = override or os.path.join(config_dir(config), CONFIG_FILENAME)
        self.legacy_path = None if override else os.path.join(state_dir(directory), FILENAME)
        self.rows = {}        # (group, id) -> (mode, source)
        self.load()

    @property
    def read_path(self):
        if self.legacy_path and not os.path.lexists(self.path) and os.path.isfile(self.legacy_path):
            return self.legacy_path
        return self.path

    def load(self):
        self.rows = {}
        self.error = None
        try:
            data = read_private(self.read_path, 4 * 1024 * 1024, strict=False)
        except OSError as exc:
            self.error = str(exc)
            return
        if data is None:
            return
        lines = data.decode('utf-8', 'replace').splitlines()
        for line in lines:
            if not line.strip() or line.startswith('#'):
                continue
            parts = line.split('\t')
            parts += [''] * (4 - len(parts))
            group, ident, mode, source = (p.strip() for p in parts[:4])
            if _valid(group, ident, mode, source):
                self.rows[(group, ident)] = (mode, source)

    def get(self, group, ident, default='auto'):
        """(mode, source); ``default`` is the app's mode when no line exists
        (the inventory's default_mode for newly detected apps, else auto)."""
        return self.rows.get((group, ident), (default if default in MODES else 'auto', ''))

    def set_many(self, keys, mode=None, source=None, defaults=None):
        defaults = defaults or {}
        for group, ident in keys:
            default = defaults.get((group, ident), 'auto')
            old_mode, old_source = self.get(group, ident, default)
            new = (mode if mode is not None else old_mode, source if source is not None else old_source)
            if not _valid(group, ident, new[0], new[1]):
                raise ValueError('invalid_override')
            if new == (default if default in MODES else 'auto', '') and default == 'auto':
                self.rows.pop((group, ident), None)
            elif new == (default, ''):
                # A non-auto default is the inventory's suggestion, not a choice;
                # keep no line so a later MAC_UPDATE_NEW_APP_MODE change applies.
                self.rows.pop((group, ident), None)
            else:
                self.rows[(group, ident)] = new
        self.save()

    def save(self):
        body = HEADER + ''.join('%s\t%s\t%s\t%s\n' % (g, i, m, s) for (g, i), (m, s) in sorted(self.rows.items()))
        directory = os.path.dirname(self.path)
        if not os.path.isdir(directory):
            import mu_paths
            mu_paths.make_private_dirs(directory)
        atomic_write(self.path, body.encode('utf-8'), mode=0o600, private_root=True)

    def export_rows(self):
        return [[g, i, m, s] for (g, i), (m, s) in sorted(self.rows.items())]

    def import_rows(self, rows):
        imported = {}
        for row in rows:
            if isinstance(row, list) and len(row) == 4 and all(isinstance(x, str) for x in row) and _valid(*row):
                if (row[2], row[3]) != ('auto', ''):
                    imported[(row[0], row[1])] = (row[2], row[3])
        self.rows = imported
        self.save()
        return len(imported)
