"""Single source of truth for the three toolkit directories (standard library only).

Three roots, one owner each:

    program  replaced by an upgrade (program files only); nothing writes inside it at
             runtime except the Node.js and npm tools update_npm_cli.sh keeps in the
             default folder (node/, npm-global/), which upgrades and uninstall leave alone
    config   user-owned settings, never touched by installers or upgrades
    state    disposable: logs, caches, scan results, backups

The shell twin is lib/paths.sh. Both print identical results for identical
input (tests/test_paths.py runs them side by side), so a change here needs the
same change there.

Resolution order, first match wins:

    program  $MAC_UPDATE_HOME
             this toolkit's own root when it is a git checkout (developer mode)
             or an installed tree (it carries .install-info)
             ~/.local/share/mac-update
    config   $MAC_UPDATE_CONFIG_DIR, $XDG_CONFIG_HOME/mac-update, ~/.config/mac-update
    state    $MAC_UPDATE_STATE_DIR, $XDG_STATE_HOME/mac-update, ~/.local/state/mac-update

MAC_UPDATE_* overrides must be absolute paths (a relative one is an error).
XDG_* values must be absolute too; per the XDG spec a relative value is ignored.
Trailing slashes are dropped. Symlinks are never resolved in the returned
paths, except for the toolkit root, which is always the physical directory.
"""
import os
import sys

NAME = "mac-update"
INSTALL_MARKER = ".install-info"
KINDS = ("program", "config", "state")


class PathError(ValueError):
    """A path setting is unusable. The message is one sentence."""


def _clean(path):
    cleaned = path.rstrip("/")
    return cleaned or "/"


def _home(env):
    home = env.get("HOME", "")
    if not home:
        raise PathError("HOME is not set, so the toolkit folders cannot be located.")
    if not home.startswith("/"):
        raise PathError("HOME must be an absolute path.")
    return _clean(home)


def _override(env, name):
    value = env.get(name, "")
    if not value:
        return None
    if not value.startswith("/"):
        raise PathError("%s must be an absolute path." % name)
    return _clean(value)


def _xdg(env, name):
    value = env.get(name, "")
    if value.startswith("/"):
        return _clean(value)
    return None


def toolkit_root():
    """The physical directory that contains lib/python/mu_paths.py's lib/."""
    here = os.path.dirname(os.path.realpath(__file__))
    return os.path.dirname(os.path.dirname(here))


def resolve(env=None, root=None):
    """Return {'program','config','state','mode'} for this environment.

    mode says where the program directory came from: env, checkout, installed
    or default.
    """
    env = os.environ if env is None else env
    home = _home(env)
    root = os.path.realpath(root) if root else toolkit_root()

    program = _override(env, "MAC_UPDATE_HOME")
    if program:
        mode = "env"
    elif os.path.exists(os.path.join(root, ".git")):
        program, mode = root, "checkout"
    elif os.path.isfile(os.path.join(root, INSTALL_MARKER)):
        program, mode = root, "installed"
    else:
        program, mode = home + "/.local/share/" + NAME, "default"

    config = _override(env, "MAC_UPDATE_CONFIG_DIR")
    if not config:
        base = _xdg(env, "XDG_CONFIG_HOME")
        config = (base or home + "/.config") + "/" + NAME
    state = _override(env, "MAC_UPDATE_STATE_DIR")
    if not state:
        base = _xdg(env, "XDG_STATE_HOME")
        state = (base or home + "/.local/state") + "/" + NAME
    return {"program": program, "config": config, "state": state, "mode": mode}


def program_dir(env=None, root=None):
    return resolve(env, root)["program"]


def config_dir(env=None, root=None):
    return resolve(env, root)["config"]


def state_dir(env=None, root=None):
    return resolve(env, root)["state"]


def data_paths(env=None, root=None):
    """Where each kind of data lives; twin of mu_data_resolve in lib/paths.sh.

    logs <state>/logs (MAC_UPDATE_LOGS_DIR wins), lock <state>/lock, reports
    <config>/reports/{APPLICATIONS,UPDATES}.md (outside the state folder, which
    the inventory journal requires), overrides <config>/overrides.tsv
    (MAC_UPDATE_OVERRIDES_FILE wins; reads fall back to <state>/user_overrides.tsv
    while the new file is missing), language <config>/lang. A developer checkout
    that still keeps data in the old places keeps using them while the new
    location does not exist; nothing is moved automatically. ``legacy`` lists the
    old locations in use.
    """
    env = os.environ if env is None else env
    paths = resolve(env, root)
    program, state, config = paths["program"], paths["state"], paths["config"]
    checkout = paths["mode"] == "checkout"
    legacy = []
    if env.get("MAC_UPDATE_LOGS_DIR"):
        logs = _clean(env["MAC_UPDATE_LOGS_DIR"])
    else:
        logs = state + "/logs"
        old = program + "/logs"
        if checkout and os.path.isdir(old) and not os.path.islink(old) and not os.path.lexists(logs):
            logs = old
            legacy.append(old)
    reports = {}
    for name in ("APPLICATIONS.md", "UPDATES.md"):
        new, old = config + "/reports/" + name, program + "/" + name
        if checkout and os.path.isfile(old) and not os.path.lexists(new):
            reports[name] = old
            legacy.append(old)
        else:
            reports[name] = new
    if env.get("MAC_UPDATE_OVERRIDES_FILE"):
        overrides = overrides_read = env["MAC_UPDATE_OVERRIDES_FILE"]
    else:
        overrides = overrides_read = config + "/overrides.tsv"
        old = state + "/user_overrides.tsv"
        if not os.path.lexists(overrides) and os.path.isfile(old):
            overrides_read = old
            legacy.append(old)
    lang = config + "/lang"
    old = program + "/.mac_update_prefs"
    legacy_prefs = old if checkout and os.path.isfile(old) and not os.path.lexists(lang) else None
    return dict(paths, logs=logs, lock=state + "/lock", applications_md=reports["APPLICATIONS.md"],
                updates_md=reports["UPDATES.md"], overrides=overrides, overrides_read=overrides_read,
                lang=lang, legacy_prefs=legacy_prefs, legacy=legacy)


def make_private_dirs(path):
    """mkdir -p where every directory created is 0700 (os.makedirs gives
    intermediate directories the umask default, which the state checks refuse)."""
    missing = []
    current = os.path.abspath(path)
    while current and not os.path.isdir(current):
        missing.append(current)
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    for directory in reversed(missing):
        try:
            os.mkdir(directory, 0o700)
        except FileExistsError:
            continue
        os.chmod(directory, 0o700)
    return path


def logs_dir(root=None, env=None):
    """Logs folder for readers (history, status, last log): data_paths()["logs"];
    while that does not exist, an existing <root>/logs is read instead."""
    old = os.path.join(root or toolkit_root(), "logs")
    try:
        new = data_paths(env, root)["logs"]
    except PathError:
        return old
    if not os.path.lexists(new) and os.path.isdir(old) and not os.path.islink(old):
        return old
    return new


def report_path(name, env=None, root=None, read=False):
    """APPLICATIONS.md or UPDATES.md: MAC_UPDATE_REPORT_PATH (APPLICATIONS.md) /
    MAC_UPDATE_UPDATES_MD win, then data_paths(); falls back to <root>/<name>.
    ``read``: while the resolved file does not exist, an existing <root>/<name>
    is returned instead (display only)."""
    env = os.environ if env is None else env
    if read:
        path = report_path(name, env, root)
        old = os.path.join(root or toolkit_root(), name)
        if not os.path.lexists(path) and os.path.isfile(old):
            return old
        return path
    key = "MAC_UPDATE_REPORT_PATH" if name == "APPLICATIONS.md" else "MAC_UPDATE_UPDATES_MD"
    if env.get(key):
        return env[key]
    try:
        paths = data_paths(env, root)
    except PathError:
        return os.path.join(root or toolkit_root(), name)
    return paths["applications_md" if name == "APPLICATIONS.md" else "updates_md"]


def legacy_notice(env=None, root=None):
    """The one-line hint shown when old-location data is in use, else ''."""
    try:
        legacy = data_paths(env, root)["legacy"]
    except PathError:
        return ""
    if not legacy:
        return ""
    return ("Note: data from an older layout is still used in place (%s); run `mac-update migrate` "
            "to copy it to the new folders." % " ".join(legacy))


def _physical(path):
    """realpath that tolerates a path that does not exist yet."""
    return os.path.realpath(path)


def _inside(path, parent):
    return path == parent or path.startswith(parent.rstrip("/") + "/")


def ensure_dir(kind, env=None, root=None):
    """Create the config or state directory (0700) and return its path.

    Refuses a directory that lives inside, or is a symlink into, the program
    directory: the program tree is replaced wholesale and must stay read-only
    at runtime.
    """
    if kind not in ("config", "state"):
        raise PathError("Only the config and state folders are created on demand.")
    paths = resolve(env, root)
    target = paths[kind]
    if _inside(_physical(target), _physical(paths["program"])):
        raise PathError(
            "The %s folder is inside the program folder, which is replaced on every update." % kind
        )
    try:
        os.makedirs(target, mode=0o700, exist_ok=True)
    except OSError:
        raise PathError("The %s folder %s cannot be created." % (kind, target))
    if _inside(_physical(target), _physical(paths["program"])):
        raise PathError(
            "The %s folder is a link into the program folder, which is replaced on every update." % kind
        )
    return target


def _main(argv):
    root = None
    args = list(argv)
    if "--root" in args:
        i = args.index("--root")
        try:
            root = args[i + 1]
        except IndexError:
            print("--root needs a directory.", file=sys.stderr)
            return 2
        del args[i : i + 2]
    command = args[0] if args else "print"
    try:
        if command == "print":
            paths = resolve(root=root)
            for key in ("program", "config", "state", "mode"):
                print("%s=%s" % (key, paths[key]))
        elif command in KINDS or command == "mode":
            print(resolve(root=root)[command])
        elif command in ("logs", "lock"):
            print(data_paths(root=root)[command])
        elif command == "ensure" and len(args) == 2:
            print(ensure_dir(args[1], root=root))
        else:
            print("Usage: mu_paths.py [print|program|config|state|mode|ensure config|ensure state] [--root DIR]",
                  file=sys.stderr)
            return 2
    except PathError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
