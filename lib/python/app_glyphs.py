"""Per-app / per-group emoji from config/app_glyphs.tsv (the only place they are defined).

``glyph_for(name)`` returns the emoji or '' (missing name, missing file). The
glyph is only ever a display prefix: it is never part of a name or a matching key.
"""

import os

_CACHE = {}


def _path():
    override = os.environ.get('MAC_UPDATE_APP_GLYPHS')
    if override:
        return override
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'config', 'app_glyphs.tsv')


def load_glyphs(path=None):
    path = path or _path()
    if path not in _CACHE:
        table = {}
        try:
            with open(path, encoding='utf-8') as stream:
                for line in stream:
                    if not line.strip() or line.startswith('#'):
                        continue
                    name, _, glyph = line.rstrip('\n').partition('\t')
                    if name and glyph.strip():
                        table[name.strip()] = glyph.strip().split()[0]
        except OSError:
            pass
        _CACHE[path] = table
    return _CACHE[path]


def glyph_for(name):
    return load_glyphs().get(str(name), '')
