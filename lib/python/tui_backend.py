"""Fixed TUI operations, private display settings and an isolated PTY worker.

Importing this module performs no scans, launches or state writes. The existing
scripts retain all consent, authorization, mutation and recovery decisions.
"""

import codecs
import errno
import fcntl
import heapq
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import termios
import time
import uuid

from inventory_store import StoreError, _open_regular, _root


GROUPS = ("appstore", "npm", "brew", "internet", "system")
LANGUAGES = ("en", "pl", "de", "fr", "es", "it", "pt")
DEFAULT_SETTINGS = dict(language="en", groups=list(GROUPS), theme="dark",
                        ascii=False, auto_resize=True, wizard_complete=False)
ACTIONS = {
    "preview": dict(script="update_all.sh", args=("--dry-run",), mutating=False, grouped=True),
    "update": dict(script="update_all.sh", args=("--cli",), mutating=True, grouped=True),
    "inventory": dict(script="build_inventory.sh", args=("--cli",), mutating=True),
    "setup_inspect": dict(script="setup.sh", args=("--cli", "--inspect"), mutating=False),
    "setup_dependencies": dict(script="setup.sh", args=("--cli", "--install-dependencies"), mutating=True),
    "setup_shell": dict(script="setup.sh", args=("--cli", "--configure-shell"), mutating=True),
    "catalog": dict(script="setup.sh", args=("--cli", "--catalog"), mutating=True),
    "preferences": dict(script="update_all.sh", args=("--cli", "--preferences-only"), mutating=True),
    "doctor": dict(script="update_all.sh", args=("--doctor",), mutating=False),
    "coverage": dict(script="scripts/report_update_coverage.sh", args=(), mutating=False),
    "sources": dict(script="scripts/scan_update_feeds.sh", args=(), mutating=False),
    "migration_preview": dict(script="build_inventory.sh", args=("--cli", "--migration", "--preview"), mutating=True),
}
_SETTINGS_FILE = "tui-settings.json"


def _groups(value):
    if not isinstance(value, (list, tuple, set, frozenset)) or any(
        not isinstance(x, str) or x not in GROUPS for x in value
    ) or len(set(value)) != len(value):
        raise ValueError("invalid_tui_groups")
    return [x for x in GROUPS if x in value]


def _settings(value):
    if value is None:
        value = {}
    if not isinstance(value, dict) or set(value) - set(DEFAULT_SETTINGS):
        raise ValueError("invalid_tui_settings")
    result = dict(DEFAULT_SETTINGS, **value)
    if result["language"] not in LANGUAGES or result["theme"] not in ("dark", "light"):
        raise ValueError("invalid_tui_settings")
    if any(type(result[key]) is not bool for key in ("ascii", "auto_resize", "wizard_complete")):
        raise ValueError("invalid_tui_settings")
    result["groups"] = _groups(result["groups"])
    return result


def load_settings(root=None):
    directory = _root(root, False)
    if directory is None:
        return _settings(None)
    path = os.path.join(directory, _SETTINGS_FILE)
    if not os.path.lexists(path):
        return _settings(None)
    fd = _open_regular(path, os.O_RDONLY)
    with os.fdopen(fd, "rb") as handle:
        raw = handle.read(16385)
    if len(raw) > 16384:
        raise ValueError("tui_settings_too_large")
    return _settings(json.loads(raw))


def save_settings(root, settings):
    value = _settings(settings)
    directory = _root(root, True)
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = ".tui-settings-" + uuid.uuid4().hex
    try:
        info = os.fstat(directory_fd)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise StoreError("unsafe tui settings directory")
        try:
            fd = _open_regular(_SETTINGS_FILE, os.O_RDONLY, dir_fd=directory_fd)
        except (StoreError, OSError):
            # Only absence permits creating a new file; links, modes and other
            # unsafe existing objects must not be repaired behind the user.
            try:
                os.stat(_SETTINGS_FILE, dir_fd=directory_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise
        else:
            os.close(fd)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=directory_fd)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(value, handle, ensure_ascii=True, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, _SETTINGS_FILE, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        os.fsync(directory_fd)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
        os.close(directory_fd)
    return value


def build_command(repo, action, groups=None, settings=None):
    settings = _settings(settings)
    groups = _groups(settings["groups"] if groups is None else groups)
    if not isinstance(action, str) or action not in ACTIONS:
        raise ValueError("invalid_tui_action")
    root = Path(repo).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("invalid_tui_repository")
    spec = ACTIONS[action]
    script = root / spec["script"]
    # Neither a symlinked script nor a symlinked scripts/ parent may escape.
    if script.is_symlink() or script.resolve(strict=True) != script or not script.is_file():
        raise ValueError("unsafe_tui_script")
    if action == "update" and not groups:
        raise ValueError("no_update_groups_selected")
    command = ["/bin/bash", str(script), *spec["args"]]
    if spec.get("grouped"):
        command.extend("--skip-" + group for group in GROUPS if group not in groups)
    return command


def _child_environment(settings):
    # Old invocation flags must not silently answer this job's prompts, select a
    # different mode, inherit another run's plan, or reuse a guard capability.
    reset = {
        "MAC_UPDATE_YES", "MAC_UPDATE_NONINTERACTIVE", "MAC_UPDATE_PARENT_CONFIRMED",
        "MAC_UPDATE_DRY_RUN", "MAC_UPDATE_PLAN_ONLY", "MAC_UPDATE_PREFERENCES",
        "MAC_UPDATE_PREFERENCES_ONLY", "MAC_UPDATE_VERIFY_ONLY", "MAC_UPDATE_JSON_SUMMARY",
        "MAC_UPDATE_INVENTORY_ONLY", "MAC_UPDATE_BOOTSTRAP_CLI", "MAC_UPDATE_PLAN_PATH",
        "MAC_UPDATE_SESSION_DIR", "MAC_UPDATE_RUN_ID", "MAC_UPDATE_ALLOW_MAJOR_UPGRADE",
    }
    env = {key: value for key, value in os.environ.items()
           if key not in reset and not key.startswith(("MAC_UPDATE_SKIP_", "MAC_UPDATE_SYSTEM_GUARD_"))}
    env.update(MAC_UPDATE_TUI_CHILD="1", MAC_UPDATE_LANG=settings["language"],
               MAC_LANG=settings["language"], PYTHONUNBUFFERED="1")
    # MAC_LANG selects application strings. Do not set the operating-system
    # LANG/LC_ALL here: shell locale reassignment is unsafe on some macOS builds.
    return env


class _OutputFilter:
    """Discard OSC commands across arbitrary chunks without retaining payloads."""

    def __init__(self):
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.state = "text"

    def feed(self, raw, final=False):
        output = []
        for char in self.decoder.decode(raw, final):
            if self.state == "text":
                if char == "\033":
                    self.state = "escape"
                elif char == "\x9d":
                    self.state = "osc"
                else:
                    output.append(char)
            elif self.state == "escape":
                if char == "]":
                    self.state = "osc"
                elif char == "\033":
                    output.append("\033")
                else:
                    output.extend(("\033", char))
                    self.state = "text"
            elif self.state == "osc":
                if char in ("\a", "\x9c"):
                    self.state = "text"
                elif char == "\033":
                    self.state = "osc_escape"
            elif char in ("\\", "\x9c"):
                self.state = "text"
            elif char != "\033":
                self.state = "osc"
        return "".join(output)


def worker_main(terminal_fd, command):
    """Called only by the isolated Python child before it execs a fixed script."""
    if terminal_fd < 3 or not command or command[0] != "/bin/bash":
        return 2
    fcntl.ioctl(terminal_fd, termios.TIOCSCTTY, 0)
    os.tcsetpgrp(terminal_fd, os.getpgrp())
    for target in (0, 1, 2):
        os.dup2(terminal_fd, target)
    os.close(terminal_fd)
    os.execvpe(command[0], command, os.environ)
    return 2


class TerminalJob:
    """One explicitly started job; no auto answers, logging or forced shutdown."""

    def __init__(self, repo, action, groups=None, settings=None):
        self.settings = _settings(settings)
        self.command = build_command(repo, action, groups, self.settings)
        self._process = None
        self._master = None
        self._size = (24, 80)
        self._filter = _OutputFilter()
        self.started_at = None
        self.stop_requested = False

    @property
    def running(self):
        return self._process is not None and self._process.poll() is None

    @property
    def returncode(self):
        return None if self._process is None else self._process.poll()

    @property
    def pid(self):
        return None if self._process is None else self._process.pid

    @property
    def secret_input(self):
        if self._master is None or not self.running:
            return False
        try:
            return not bool(termios.tcgetattr(self._master)[3] & termios.ECHO)
        except OSError:
            return False

    def start(self):
        if self._process is not None:
            raise ValueError("tui_job_already_started")
        master, slave = os.openpty()
        self._master = master
        self.resize(*self._size)
        os.set_blocking(master, False)
        helper = ('import sys; sys.path.insert(0, sys.argv[1]); '
                  'from tui_backend import worker_main; '
                  'sys.exit(worker_main(int(sys.argv[2]), sys.argv[3:]))')
        try:
            self._process = subprocess.Popen(
                [sys.executable, "-c", helper, str(Path(__file__).resolve().parent),
                 str(slave), *self.command],
                stdin=slave, stdout=slave, stderr=slave, pass_fds=(slave,),
                start_new_session=True, env=_child_environment(self.settings),
            )
            self.started_at = time.monotonic()
        except BaseException:
            os.close(master)
            self._master = None
            raise
        finally:
            os.close(slave)
        return self

    def poll(self):
        chunks = []
        # A noisy child cannot allocate an unbounded buffer or starve UI input.
        for _ in range(16):
            if self._master is None:
                break
            try:
                raw = os.read(self._master, 4096)
            except BlockingIOError:
                break
            except OSError as exc:
                if exc.errno != errno.EIO:
                    raise
                raw = b""
            if not raw:
                final = self._filter.feed(b"", final=True)
                if final:
                    chunks.append(final)
                os.close(self._master)
                self._master = None
                break
            text = self._filter.feed(raw)
            if text:
                chunks.append(text)
        if self._process is not None:
            self._process.poll()
        return chunks

    def send(self, text):
        if not isinstance(text, str) or len(text) > 4096:
            raise ValueError("invalid_tui_input")
        if self._master is None or not self.running:
            return 0
        # Forward exactly what the user submitted. Do not retain, echo or log it.
        data = text.encode("utf-8")
        sent = 0
        while sent < len(data):
            written = os.write(self._master, data[sent:])
            if written <= 0:
                break
            sent += written
        return sent

    def resize(self, rows, cols):
        if type(rows) is not int or type(cols) is not int or not (1 <= rows <= 1000 and 1 <= cols <= 1000):
            raise ValueError("invalid_terminal_size")
        self._size = (rows, cols)
        if self._master is not None:
            fcntl.ioctl(self._master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    def interrupt(self):
        """Only the UI's explicitly confirmed cancellation may call this."""
        if self._master is None or not self.running:
            return False
        self.stop_requested = True
        # The PTY delivers this to its foreground job, not the UI process group.
        self.send("\x03")
        return True


def _plain(value, maximum=128):
    return "".join(c for c in str(value) if c.isprintable())[:maximum]


def recent_runs(repo, limit=10):
    if type(limit) is not int or not 0 <= limit <= 50:
        raise ValueError("invalid_history_limit")
    logs = Path(repo) / "logs"
    if not limit or logs.is_symlink() or not logs.is_dir():
        return []
    rows = []
    names = heapq.nlargest(1000, (p.name for p in logs.iterdir() if re.fullmatch(r"run_summary_[0-9_]+\.json", p.name)))
    for name in names:
        try:
            fd = _open_regular(str(logs / name), os.O_RDONLY)
            with os.fdopen(fd, "rb") as handle:
                raw = handle.read(16 * 1024 * 1024 + 1)
            if len(raw) > 16 * 1024 * 1024:
                continue
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get("format_version") != 4:
                continue
            status = data.get("run_status")
            if status not in ("started", "completed", "interrupted", "failed"):
                status = "unknown"
            row = dict(filename=name, timestamp=_plain(data.get("timestamp", "")),
                       run_status=status, exit_class=_plain(data.get("exit_class", "unknown"), 32))
            for key in ("duration_seconds", "exit_code"):
                value = data.get(key)
                row[key] = value if type(value) is int and value >= 0 else None
            rows.append(row)
        except (OSError, ValueError, TypeError, StoreError):
            continue
        if len(rows) >= limit:
            break
    return rows
