"""Fixed TUI operations, run history and an isolated PTY worker.

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
import struct
import subprocess
import sys
import termios
import time

from inventory_store import StoreError, _open_regular, _root


ACTIONS = {
    "native_recovery": dict(script="scripts/reconcile_native.sh", args=(), mutating=True),
    "toolkit_check": dict(script="scripts/update_toolkit.sh", args=("--check",), mutating=False),
    "toolkit_prepare": dict(script="scripts/update_toolkit.sh", args=("--prepare",), mutating=False),
    "run": dict(script="update_all.sh", args=("--cli",), mutating=True),
    "inventory": dict(script="build_inventory.sh", args=("--cli",), mutating=True),
    "setup_inspect": dict(script="setup.sh", args=("--cli", "--inspect"), mutating=False),
    "requirements": dict(script="update_all.sh", args=("--requirements", "--tsv"), mutating=False),
    "prepare": dict(script="update_all.sh", args=("--prepare", "--yes"), mutating=True),
    "catalog": dict(script="setup.sh", args=("--cli", "--catalog"), mutating=True),
    "doctor": dict(script="update_all.sh", args=("--doctor",), mutating=False),
    "coverage": dict(script="scripts/report_update_coverage.sh", args=(), mutating=False),
    "sources": dict(script="scripts/scan_update_feeds.sh", args=(), mutating=False),
    "schedule": dict(script="scripts/install_launchagent.sh", args=(), mutating=True),
}
_FLAG = re.compile(r"--[a-z][a-z0-9-]{0,40}")


def _script(repo, relative):
    root = Path(repo).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("invalid_tui_repository")
    script = root / relative
    # Neither a symlinked script nor a symlinked scripts/ parent may escape.
    if script.is_symlink() or script.resolve(strict=True) != script or not script.is_file():
        raise ValueError("unsafe_tui_script")
    return script


def build_command(repo, action, extra=(), install_plan=None):
    """Fixed script plus validated extra arguments (flags or short numbers)."""
    if not isinstance(action, str) or action not in ACTIONS:
        raise ValueError("invalid_tui_action")
    spec = ACTIONS[action]
    script = _script(repo, spec["script"])
    extra = list(extra)
    for value in extra:
        if not isinstance(value, str) or not (_FLAG.fullmatch(value) or re.fullmatch(r"[0-9]{1,4}", value)
                                              or re.fullmatch(r"([01]?[0-9]|2[0-3]):[0-5][0-9]", value)
                                              or value in ("always", "needs_you", "never")):
            raise ValueError("invalid_tui_argument")
    command = ["/bin/bash", str(script), *spec["args"], *extra]
    if install_plan is not None:
        from install_execution import load_install_plan
        from inventory_store import default_root
        path = Path(install_plan)
        directory = Path(_root(default_root(), False) or default_root()) / 'install-plans'
        if action != 'catalog' or path.parent != directory or path.is_symlink() or path.resolve(strict=True) != path:
            raise ValueError('unsafe_tui_install_plan')
        load_install_plan(str(path))
        command = ['/bin/bash', str(script), '--cli', '--install-plan', str(path)]
    return command


def child_environment(language="en", extra=None):
    # Old invocation flags must not silently answer this job's prompts, select a
    # different mode, inherit another run's plan, or reuse a guard capability.
    reset = {
        "MAC_UPDATE_YES", "MAC_UPDATE_NONINTERACTIVE", "MAC_UPDATE_PARENT_CONFIRMED",
        "MAC_UPDATE_DRY_RUN", "MAC_UPDATE_PLAN_ONLY", "MAC_UPDATE_PREFERENCES",
        "MAC_UPDATE_PREFERENCES_ONLY", "MAC_UPDATE_VERIFY_ONLY", "MAC_UPDATE_JSON_SUMMARY",
        "MAC_UPDATE_INVENTORY_ONLY", "MAC_UPDATE_BOOTSTRAP_CLI", "MAC_UPDATE_PLAN_PATH",
        "MAC_UPDATE_SESSION_DIR", "MAC_UPDATE_RUN_ID", "MAC_UPDATE_ALLOW_MAJOR_UPGRADE",
        "MAC_UPDATE_AUTOMATIC_INTERNET_BATCH", "MAC_UPDATE_EVENT_FILE",
    }
    env = {key: value for key, value in os.environ.items()
           if key not in reset and not key.startswith(("MAC_UPDATE_SKIP_", "MAC_UPDATE_SYSTEM_GUARD_"))}
    env.update(MAC_UPDATE_TUI_CHILD="1", MAC_UPDATE_LANG=language, MAC_LANG=language, PYTHONUNBUFFERED="1")
    for key, value in (extra or {}).items():
        if isinstance(key, str) and key.startswith("MAC_") and isinstance(value, str):
            env[key] = value
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

    def __init__(self, command, env=None):
        if not command or command[0] != "/bin/bash":
            raise ValueError("invalid_tui_command")
        self.command = list(command)
        self.env = dict(child_environment() if env is None else env)
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
                start_new_session=True, env=self.env,
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
    import mu_paths
    logs = Path(mu_paths.logs_dir(repo))
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


def read_summary(repo, filename):
    """Load one run summary (bounded, regular private file, no symlinks)."""
    if not re.fullmatch(r"run_summary_[0-9_]+\.json", str(filename)):
        return None
    import mu_paths
    path = Path(mu_paths.logs_dir(repo)) / filename
    try:
        fd = _open_regular(str(path), os.O_RDONLY)
        with os.fdopen(fd, "rb") as handle:
            raw = handle.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            return None
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError, StoreError):
        return None


def host_facts():
    """Cheap, read-only facts for the Status pane: free disk and power."""
    facts = {}
    try:
        import shutil
        facts["disk_free_gb"] = int(shutil.disk_usage("/").free // (1024 ** 3))
    except OSError:
        pass
    try:
        out = subprocess.run(["/usr/bin/pmset", "-g", "batt"], capture_output=True, text=True, timeout=1,
                             stdin=subprocess.DEVNULL).stdout
    except (OSError, subprocess.SubprocessError):
        out = ""
    if out:
        source = "ac" if "AC Power" in out else ("battery" if "Battery Power" in out else None)
        match = re.search(r"(\d{1,3})%", out)
        if source:
            facts["power"] = dict(source=source, percent=int(match.group(1)) if match else None)
    return facts
