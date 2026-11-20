"""Semantic theme: glyph sets and colour styles for the terminal interface.

Styles are names ("ok", "focus_border", ...). Rendering code never picks raw
colours; this module maps names to curses attributes for 256-colour,
16-colour and NO_COLOR terminals, in a dark and a light variant.
"""
import os
import re

GLYPHS_UNICODE = dict(
    tl='╭', tr='╮', bl='╰', br='╯', h='─', v='│', tee_l='├', tee_r='┤',
    marker='▶', ok='✓', current='•', needs='!', fail='✗', running='⟳', pending='○', off='–',
    check_on='[✓]', check_off='[ ]', radio_on='●', radio_off='○', arrow='→', ellipsis='…',
    bar_full='█', bar_empty='█', bar_parts=('', '▏', '▎', '▍', '▌', '▋', '▊', '▉'),
    # Progress bars are one slim heavy line: the fill and the track are the same glyph and differ by colour;
    # a half-cell cap smooths the leading edge, and the travelling highlight reuses the fill glyph.
    bar_fill='━', bar_track='━', bar_cap='╸', bar_cap_r='╺', bar_pulse='━',
    spinner=('⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'), expand='▾', collapse='▸',
    spark=('▁', '▂', '▃', '▄', '▅', '▆', '▇', '█'), sep='·', up='↑', down='↓',
)
GLYPHS_ASCII = dict(
    tl='+', tr='+', bl='+', br='+', h='-', v='|', tee_l='+', tee_r='+',
    marker='>', ok='+', current='=', needs='!', fail='x', running='*', pending='o', off='-',
    check_on='[x]', check_off='[ ]', radio_on='(*)', radio_off='( )', arrow='->', ellipsis='...',
    bar_full='#', bar_empty='.', bar_parts=('',) * 8,
    bar_fill='#', bar_track='-', bar_cap='', bar_cap_r='', bar_pulse='=',
    spinner=('|', '/', '-', '\\'), expand='v', collapse='>',
    spark=('_', '_', '.', '.', '-', '-', '^', '^'), sep='|', up='^', down='v',
)

ACCENTS = ('blue', 'violet', 'amber', 'green', 'rose', 'graphite')
STYLES = ('base', 'muted', 'accent', 'ok', 'warn', 'fail', 'sel', 'sel_focus', 'border', 'focus_border',
          'title', 'focus_title', 'header', 'header_accent', 'keybar', 'keybar_key', 'btn', 'btn_focus',
          'btn_primary', 'bar_track', 'bar_run', 'bar_ok', 'bar_warn', 'bar_fail', 'bar_pulse', 'dialog', 'dialog_border', 'input',
          'status', 'status_ok', 'status_warn', 'tab', 'tab_active', 'strong', 'disabled')

# Styles that paint their own background. Any other style drawn over one of
# these surfaces inherits it (the light scheme does this so a coloured word on a selected row keeps the row).
SURFACE_OF = dict(sel='sel', sel_focus='sel', input='sel', header='header', header_accent='header',
                  keybar='header', keybar_key='header', dialog='dialog', dialog_border='dialog')

# 256-colour palette: (dark, light)
# Accents are deliberately desaturated so none reads as a status colour:
# blue #5f87af, violet #8787d7, amber #d7af87, green (sage) #87af87, rose #d7879f, graphite #bcbcbc.
_ACCENT_256 = dict(blue=(67, 25), violet=(104, 61), amber=(180, 94), green=(108, 65), rose=(175, 132),
                   graphite=(250, 240))
# Light scheme: the same design as the macOS Cleanup light scheme. The page keeps the terminal's own
# background and body text uses the terminal's own foreground (colour -1), so nothing can wash out; only
# the header/key bar, the selected row and dialogs paint a pale surface (254 / 253 / 255). Colours are
# Cleanup's, with the few that fail WCAG 4.5:1 on those surfaces moved to the nearest passing colour:
# violet 61->55, amber accent 94->58, green 65->23, rose 132->125, ok 28->22, warn 130->94, fail 160->124
# (blue 25, graphite 240 and every surface are Cleanup's own).
_LIGHT_ACCENT_256 = dict(blue=25, violet=55, amber=58, green=23, rose=125, graphite=240)
_LIGHT_ACCENT_16 = dict(blue=4, violet=5, amber=1, green=2, rose=5, graphite=0)
_ACCENT_16 = dict(blue=4, violet=5, amber=3, green=2, rose=5, graphite=7)
# Semantic colours stay independent of the accent: bright ok green, amber warn, red fail.
_SEM_256 = dict(ok=(77, 28), warn=(214, 130), fail=(203, 160), muted=(248, 242), base=(253, 236),
                strong=(255, 232), sel_bg=(237, 253), header_bg=(236, 254), dialog_bg=(235, 255))
# The light scheme's own text colours (see light_palette); -1 is the terminal's default colour.
_LIGHT_256 = dict(ok=22, warn=94, fail=124, muted=241, faint=244, head=236, strong_on_surface=232, on_accent=255)
# Progress bars are not text: a solid pale track (253) with a fill in a calmer tone than the text colours
# (done green 28, needs-you amber 130, failed red 160, running = the accent). One state, one colour; never a
# colour by position.
_LIGHT_BAR_256 = dict(track=253, ok=28, warn=130, fail=160)
_DARK_BAR_256 = dict(track=238, ok=77, warn=214, fail=203)
_BAR_16 = dict(track=7, ok=2, warn=3, fail=1)
# The travelling highlight of a running bar: a lighter blue than the run colour on the light scheme (it still
# reads on white, 3:1), a brighter one on the dark scheme. Per accent, never teal.
_LIGHT_PULSE_256 = dict(blue=33, violet=98, amber=100, green=28, rose=168, graphite=244)
_DARK_PULSE_256 = dict(blue=75, violet=147, amber=222, green=151, rose=211, graphite=255)

THEME_CHOICES = ('auto', 'dark', 'light')
OSC11_TIMEOUT = 0.25
DEFAULT = -1


def light_palette(accent='blue', colors=256):
    """The light scheme as data: ``(surfaces, specs)``.

    ``surfaces`` maps a surface name (page, header, sel, dialog) to a colour number; the page is -1, the
    terminal's own background. ``specs`` maps every style to ``(foreground, background, flags)`` where the
    foreground may be -1 (the terminal's own text colour), the background is a surface name or a colour
    number, and flags is a string of b(old), u(nderline), r(everse). Like the macOS Cleanup light scheme it
    assumes a light terminal (Auto picks it only then); every pair is checked against WCAG contrast in
    tests/test_tui_theme.py, with the terminal assumed black on white.
    """
    accent = accent if accent in ACCENTS else 'blue'
    if colors >= 256:
        surfaces = dict(page=DEFAULT, header=254, sel=253, dialog=255)
        acc = _LIGHT_ACCENT_256[accent]
        pulse = _LIGHT_PULSE_256[accent]
        c = _LIGHT_256
        ok, warn, fail, muted, faint, head, on_acc = c['ok'], c['warn'], c['fail'], c['muted'], c['faint'], c['head'], c['on_accent']
        bars = _LIGHT_BAR_256
        strong_sel = c['strong_on_surface']
        sel = (strong_sel, 'sel', ''), (acc, 'sel', 'b'), (strong_sel, 'sel', 'u')
        keybar = head
    else:
        # 8/16 colours: only the darker standard colours, because the pale ones vanish on white. Bold on a
        # colour 1-7 turns it bright in many terminals, so those styles are not bold.
        surfaces = dict(page=DEFAULT, header=7, sel=0, dialog=DEFAULT)
        acc = pulse = _LIGHT_ACCENT_16[accent]
        ok, warn, fail = 2, 5, 1
        muted = faint = 8 if colors >= 16 else 0
        bars = dict(track=7, ok=2, warn=1, fail=1)
        head = keybar = 0
        on_acc = 15 if colors >= 16 else 7
        sel = (7, 'sel', ''), (7, 'sel', ''), (7, 'sel', 'u')
    bd = 'b' if colors >= 256 else ''
    sel_plain, sel_focus, sel_input = sel
    specs = dict(
        base=(DEFAULT, 'page', ''), muted=(muted, 'page', ''), accent=(acc, 'page', ''), ok=(ok, 'page', ''),
        warn=(warn, 'page', ''), fail=(fail, 'page', bd), sel=sel_plain, sel_focus=sel_focus,
        border=(faint, 'page', ''), focus_border=(acc, 'page', bd), title=(DEFAULT, 'page', 'b'),
        focus_title=(acc, 'page', bd), header=(head, 'header', ''), header_accent=(acc, 'header', bd),
        keybar=(keybar, 'header', ''), keybar_key=(acc, 'header', bd), btn=(DEFAULT, 'page', ''),
        btn_focus=(on_acc, acc, 'b'), btn_primary=(acc, 'page', bd), bar_track=(bars['track'], 'page', ''),
        bar_run=(acc, 'page', ''), bar_ok=(bars['ok'], 'page', ''), bar_warn=(bars['warn'], 'page', ''),
        bar_fail=(bars['fail'], 'page', ''), bar_pulse=(pulse, 'page', ''),
        dialog=(head, 'dialog', ''), dialog_border=(acc, 'dialog', bd), input=sel_input,
        status=(DEFAULT, 'page', ''), status_ok=(ok, 'page', bd), status_warn=(warn, 'page', bd),
        tab=(head, 'page', ''), tab_active=(on_acc, acc, 'b'), strong=(DEFAULT, 'page', 'b'),
        disabled=(faint, 'page', ''))
    return surfaces, specs


def parse_osc11(reply):
    """'dark' or 'light' from a terminal's answer to the OSC 11 background query
    (``ESC ] 11 ; rgb:RRRR/GGGG/BBBB BEL``, 1 to 4 hex digits per channel, or ``#RRGGBB``); None when
    the text holds no colour."""
    if not isinstance(reply, str):
        return None
    match = re.search(r'rgb:([0-9a-fA-F]{1,4})/([0-9a-fA-F]{1,4})/([0-9a-fA-F]{1,4})', reply)
    if match:
        channels = [int(p, 16) / float((16 ** len(p)) - 1) for p in match.groups()]
    else:
        match = re.search(r'#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})', reply)
        if not match:
            return None
        channels = [int(p, 16) / 255.0 for p in match.groups()]
    luminance = 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
    return 'light' if luminance > 0.5 else 'dark'


def parse_colorfgbg(value):
    """'dark' or 'light' from COLORFGBG ('15;0', '0;default;15'): the last field is the background
    colour number; 0-6 and 8 are dark, 7 and 9-15 are light."""
    if not isinstance(value, str) or not value.strip():
        return None
    last = value.strip().split(';')[-1]
    if not last.isdigit():
        return None
    number = int(last)
    if number > 15:
        return None
    return 'dark' if number in (0, 1, 2, 3, 4, 5, 6, 8) else 'light'


def query_terminal_background(timeout=OSC11_TIMEOUT, fd=None):
    """Ask the terminal for its background colour (OSC 11) and return 'dark', 'light' or None. Must run
    before curses takes the terminal. Needs a real terminal on stdin and gives up after ``timeout``."""
    import select
    import sys
    import termios
    import tty
    try:
        fd = sys.stdin.fileno() if fd is None else fd
        if not os.isatty(fd) or not os.isatty(sys.stdout.fileno()):
            return None
        saved = termios.tcgetattr(fd)
    except (OSError, ValueError, termios.error, AttributeError):
        return None
    reply = ''
    try:
        tty.setcbreak(fd)
        os.write(sys.stdout.fileno(), b'\x1b]11;?\x07')
        deadline = timeout
        while deadline > 0:
            ready, _, _ = select.select([fd], [], [], deadline)
            if not ready:
                break
            reply += os.read(fd, 64).decode('latin-1')
            if '\x07' in reply or '\x1b\\' in reply:
                break
            deadline = timeout / 2.0
    except (OSError, ValueError):
        return None
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSAFLUSH, saved)
        except (termios.error, OSError):
            pass
    return parse_osc11(reply)


def detect_background(env=None, query=None):
    """Light or dark terminal: the OSC 11 answer first, then COLORFGBG, then 'dark'."""
    env = os.environ if env is None else env
    asked = (query or query_terminal_background)() if env.get('TERM', '') not in ('dumb', '') else None
    return asked or parse_colorfgbg(env.get('COLORFGBG')) or 'dark'


def resolve_theme(setting, detected=None, env=None):
    """'dark' or 'light' for a setting value (auto, dark, light) given a detection result."""
    if setting in ('dark', 'light'):
        return setting
    env = os.environ if env is None else env
    return detected or parse_colorfgbg(env.get('COLORFGBG')) or 'dark'


GLYPHS_UNICODE_MONO = dict(GLYPHS_UNICODE, bar_empty='░', bar_track='─')   # no colours: the track must differ by shape


def glyphs(ascii_only=False, mono=False):
    if ascii_only:
        return GLYPHS_ASCII
    return GLYPHS_UNICODE_MONO if mono else GLYPHS_UNICODE


def color_disabled(env=None):
    env = os.environ if env is None else env
    return 'NO_COLOR' in env or env.get('TERM', '') in ('dumb', '')


def wants_ascii(env=None, setting=False):
    env = os.environ if env is None else env
    if setting:
        return True
    encoding = (env.get('LC_ALL') or env.get('LC_CTYPE') or env.get('LANG') or '').upper()
    return env.get('TERM', '') in ('linux', 'vt100', 'vt220') or (bool(encoding) and 'UTF' not in encoding and encoding not in ('C', 'POSIX'))


class Theme:
    """Resolves style names to curses attributes. Pure data when curses is absent."""

    def __init__(self, name='dark', accent='blue', no_color=False):
        self.name = name if name in ('dark', 'light') else resolve_theme(name)
        self.accent = accent if accent in ACCENTS else 'blue'
        self.no_color = no_color
        self.attrs = {}
        self._build = None
        self._built = {}

    def setup(self, curses):
        """Initialise colour pairs. Safe to call again after a theme change."""
        A = curses
        self.attrs = {}
        self._build = None
        colors = 0
        self.default_colors = False
        if not self.no_color:
            try:
                if curses.has_colors():
                    curses.start_color()
                    try:
                        curses.use_default_colors()
                        bg = -1
                        self.default_colors = True
                    except curses.error:
                        bg = curses.COLOR_BLACK
                    colors = curses.COLORS
            except curses.error:
                colors = 0
        bold, dim, rev, und = A.A_BOLD, A.A_DIM, A.A_REVERSE, A.A_UNDERLINE
        if colors < 8:
            mono = dict(base=0, muted=dim, accent=bold, ok=0, warn=bold, fail=bold | und, sel=rev,
                        sel_focus=rev | bold, border=dim, focus_border=bold, title=0, focus_title=bold | rev,
                        header=rev, header_accent=rev | bold, keybar=rev, keybar_key=rev | bold, btn=0,
                        btn_focus=rev | bold, btn_primary=bold, bar_track=dim, bar_run=bold, bar_ok=bold, bar_warn=bold,
                        bar_fail=bold, bar_pulse=bold | rev, dialog=0, dialog_border=bold, input=und, status=0, status_ok=bold,
                        status_warn=bold, tab=dim, tab_active=rev | bold, strong=bold, disabled=dim)
            self.attrs = mono
            return self
        light = 1 if self.name == 'light' else 0
        if light:
            return self._setup_light(curses, colors)
        pairs = {}
        nxt = [1]

        def pair(fg, bgc=None):
            key = (fg, bg if bgc is None else bgc)
            if key not in pairs:
                try:
                    curses.init_pair(nxt[0], key[0], key[1])
                except curses.error:
                    return 0
                pairs[key] = curses.color_pair(nxt[0])
                nxt[0] += 1
            return pairs[key]

        if colors >= 256:
            acc = _ACCENT_256[self.accent][light]
            s = {k: v[light] for k, v in _SEM_256.items()}
            c = dict(acc=acc, ok=s['ok'], warn=s['warn'], fail=s['fail'], muted=s['muted'], base=s['base'],
                     strong=s['strong'], sel_bg=s['sel_bg'], header_bg=s['header_bg'], dialog_bg=s['dialog_bg'],
                     on_acc=(234 if not light else 255))
            dbg = c['dialog_bg']
            bar = _DARK_BAR_256
        else:
            acc = _ACCENT_16[self.accent]
            c = dict(acc=acc, ok=2, warn=3, fail=1, muted=(7 if not light else 0), base=-1, strong=-1,
                     sel_bg=bg, header_bg=bg, dialog_bg=bg, on_acc=0)
            dbg = bg
            bar = dict(track=8 if colors >= 16 else 7, ok=2, warn=3, fail=1)
        self.attrs = dict(
            base=pair(c['base']), muted=pair(c['muted']) | (dim if colors < 256 else 0),
            accent=pair(c['acc']), ok=pair(c['ok']), warn=pair(c['warn']), fail=pair(c['fail']) | bold,
            sel=(pair(c['strong'], c['sel_bg']) if colors >= 256 else rev),
            sel_focus=(pair(c['acc'], c['sel_bg']) | bold if colors >= 256 else rev | bold),
            border=pair(c['muted']) | (dim if colors < 256 else 0), focus_border=pair(c['acc']) | bold,
            title=pair(c['base']), focus_title=pair(c['acc']) | bold,
            header=pair(c['base'], c['header_bg']), header_accent=pair(c['acc'], c['header_bg']) | bold,
            keybar=pair(c['muted'], c['header_bg']), keybar_key=pair(c['acc'], c['header_bg']) | bold,
            btn=pair(c['base']), btn_focus=pair(c['on_acc'], c['acc']) | bold, btn_primary=pair(c['acc']) | bold,
            bar_track=pair(bar['track']) | (dim if colors < 16 else 0), bar_run=pair(c['acc']), bar_ok=pair(bar['ok']),
            bar_warn=pair(bar['warn']), bar_fail=pair(bar['fail']),
            bar_pulse=(pair(_DARK_PULSE_256[self.accent]) if colors >= 256 and not light else pair(c['acc']) | bold),
            dialog=pair(c['base'], dbg), dialog_border=pair(c['acc'], dbg) | bold, input=pair(c['strong'], c['sel_bg']) | und,
            status=pair(c['muted']), status_ok=pair(c['ok']) | bold, status_warn=pair(c['warn']) | bold,
            tab=pair(c['muted']), tab_active=pair(c['on_acc'], c['acc']) | bold, strong=pair(c['strong']) | bold,
            disabled=pair(c['muted']),
        )
        # Swatches for the accent preview in Settings.
        for name in ACCENTS:
            fg = _ACCENT_256[name][light] if colors >= 256 else _ACCENT_16[name]
            self.attrs['swatch_' + name] = pair(fg) | bold
        return self

    def _setup_light(self, curses, colors):
        surfaces, specs = light_palette(self.accent, colors)
        pairs = {}
        # Without default-colour support (-1) fall back to black text on a white page, as the scheme assumes.
        plain_fg, plain_bg = (DEFAULT, DEFAULT) if self.default_colors else (curses.COLOR_BLACK, 15 if colors >= 16 else curses.COLOR_WHITE)

        def make(fg, bgc):
            fg = plain_fg if fg == DEFAULT else fg
            bgc = plain_bg if bgc == DEFAULT else bgc
            key = (fg, bgc)
            if key not in pairs:
                try:
                    curses.init_pair(len(pairs) + 1, fg, bgc)
                except curses.error:
                    return 0
                pairs[key] = curses.color_pair(len(pairs) + 1)
            return pairs[key]

        flag_bits = dict(b=curses.A_BOLD, u=curses.A_UNDERLINE, r=curses.A_REVERSE)

        def build(style, surface=None):
            fg, bgs, flags = specs[style]
            bgc = bgs if isinstance(bgs, int) else surfaces[surface if surface and style not in SURFACE_OF else bgs]
            attr = make(fg, bgc)
            for f in flags:
                attr |= flag_bits[f]
            return attr

        self._build, self._built = build, {}
        self.attrs = {style: build(style) for style in specs}
        for name in ACCENTS:
            self.attrs['swatch_' + name] = make(_LIGHT_ACCENT_256[name] if colors >= 256 else _LIGHT_ACCENT_16[name],
                                                DEFAULT) | curses.A_BOLD
        return self

    def attr(self, style, surface=None):
        if surface and surface != 'page' and self._build is not None and style in STYLES and style not in SURFACE_OF:
            key = (style, surface)
            if key not in self._built:
                self._built[key] = self._build(style, surface)
            return self._built[key]
        return self.attrs.get(style, 0)
