#!/usr/bin/env bash
# ============================================================
# run_tests.sh — One-shot test runner for the toolkit
# ============================================================
# Runs:
#   1. bash -n on every .sh in the project (syntax check)
#   2. python3 -m py_compile on every .py
#   3. tests/test_safety_static.py (path safety + static shell asserts)
#   4. scripts/scan_secrets.sh (optional gitleaks / pattern scan)
#
# Usage:
#   bash run_tests.sh
#
# Exit codes:
#   0 — everything passed
#   1 — one or more checks failed
# ============================================================
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

unit_only=0
pattern='test*.py'
while [ "$#" -gt 0 ]; do
    case "$1" in
        --unit-only) unit_only=1 ;;
        --pattern) shift; [ "$#" -gt 0 ] || { echo "--pattern requires a value" >&2; exit 2; }; pattern="$1" ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
    shift
done

fail=0
say()  { echo -e "${CYAN}── $1${NC}"; }
ok()   { echo -e "  ${GREEN}✅ $1${NC}"; }
err()  { echo -e "  ${RED}❌ $1${NC}"; fail=1; }

if [ "$unit_only" -eq 0 ]; then
say "1/4  bash -n on all .sh"
syntax_fail=0
for f in *.sh lib/*.sh dev_sync/*.sh i18n/*.sh scripts/*.sh; do
    [ -f "$f" ] || continue
    if ! bash -n "$f" 2>&1; then
        err "syntax error in $f"
        syntax_fail=1
    fi
done
[ "$syntax_fail" -eq 0 ] && ok "all bash scripts parse"

say "2/4  python3 -m py_compile on all .py and inline heredocs"
# Only tracked project code belongs to the production test surface. Local
# ignored scratch helpers must never make CI or a release check fail.
PY_FILES="lib/python/*.py dev_sync/*.py scripts/*.py tests/*.py"
if python3 -m py_compile $PY_FILES 2>&1; then
    ok "all python modules compile"
else
    err "py_compile failed"
fi

if python3 -c "
import glob, re, sys, tempfile, os, subprocess

tmpdir = os.environ.get('TMPDIR', '/tmp')
sh_files = glob.glob('*.sh') + glob.glob('lib/*.sh') + glob.glob('dev_sync/*.sh') + glob.glob('scripts/*.sh')
pattern = re.compile(r'<<\s*[\'\"]?(PY[A-Za-z0-9_]*)[\'\"]?\n(.*?)\n\s*\1', re.DOTALL)

count = 0
failed = False
extracted_files = []

for sh_path in sh_files:
    if not os.path.isfile(sh_path):
        continue
    with open(sh_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    matches = pattern.findall(content)
    for idx, (marker, py_code) in enumerate(matches, 1):
        count += 1
        tmp_fd, tmp_path = tempfile.mkstemp(prefix=f'mac_update_heredoc_{os.path.basename(sh_path)}_{marker}_', suffix='.py', dir=tmpdir)
        os.write(tmp_fd, py_code.encode('utf-8'))
        os.close(tmp_fd)
        extracted_files.append(tmp_path)
        comp = subprocess.run([sys.executable, '-m', 'py_compile', tmp_path], capture_output=True, text=True)
        if comp.returncode != 0:
            print(f'  ❌ heredoc python syntax error in {sh_path} ({marker}): {comp.stderr.strip()}')
            failed = True

    c_pattern = re.compile(r\"python3\s+(?:-\S+\s+)*-c\s+'([^']*)'\", re.DOTALL)
    for m in c_pattern.finditer(content):
        code = m.group(1)
        line_num = content[:m.start()].count('\n') + 1
        try:
            compile(code, sh_path, \"exec\")
        except SyntaxError as e:
            print(f\"  ❌ inline python -c syntax error in {sh_path}:{line_num}: {e}\")
            failed = True

if __import__('shutil').which('ruff'):
    if extracted_files:
        subprocess.run(['ruff', 'check'] + extracted_files, capture_output=True)

for p in extracted_files:
    try: os.remove(p)
    except Exception: pass

if failed:
    sys.exit(1)
" 2>&1; then
    ok "all inline heredoc and -c python blocks compile"
else
    err "inline python compile failed"
fi

fi

say "3/4  python3 -m unittest discover tests"
# Host guard (pattern from macOS_cleanup 240f0b8/6b61e8f): a test that forgets to
# mock a host-mutating tool must hit a failing stub, never the real one. Tests
# still prepend their own mock dirs, which win over the guard. stdin is closed
# so no test can block on, or answer, a real prompt.
REAL_PYTHON="$(command -v python3)" || exit 1
GUARD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/mac_update_testguard.XXXXXX")" || exit 1
GUARD_LOG="$GUARD_DIR/blocked.log"
: > "$GUARD_LOG"
# Persistent vendor feed state (lib/python/feed_state.py) must never be read
# from or written to the real ~/.local/state during tests.
export MAC_UPDATE_FEED_STATE_FILE="$GUARD_DIR/feed_state.json"
export MAC_UPDATE_HOMEBREW_PREFIX="$GUARD_DIR/empty-homebrew"
for tool in softwareupdate mas brew msupdate installer sudo launchctl docker killall curl wget open osascript defaults hdiutil ditto codesign spctl; do
    cat > "$GUARD_DIR/$tool" <<GUARD_EOF
#!/bin/sh
echo "[\${MAC_UPDATE_TEST_NAME:-unknown}] $tool \$*" >> "\${MAC_UPDATE_TEST_GUARD_LOG:-$GUARD_LOG}"
echo "run_tests.sh guard: real '$tool' blocked during tests" >&2
exit 97
GUARD_EOF
    chmod +x "$GUARD_DIR/$tool"
done
cat > "$GUARD_DIR/python3" <<SH_WRAPPER
#!/bin/sh
PYTHONPATH="$GUARD_DIR\${PYTHONPATH+:\$PYTHONPATH}"; export PYTHONPATH
exec "$REAL_PYTHON" "\$@"
SH_WRAPPER
chmod +x "$GUARD_DIR/python3"
export MAC_UPDATE_TEST_GUARD_LOG="$GUARD_LOG"
# sitecustomize applies to Python children too, without placing product modules
# on PYTHONPATH. Local server tests may explicitly opt in to loopback sockets.
cat > "$GUARD_DIR/sitecustomize.py" <<'PY_GUARD'
import os
import socket
import subprocess
_guard_dir = os.path.dirname(__file__)
_original_popen = subprocess.Popen
class _GuardedPopen(_original_popen):
    def __init__(self, *args, **kwargs):
        env = dict(os.environ if kwargs.get('env') is None else kwargs['env'])
        env['PYTHONPATH'] = _guard_dir + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
        env.setdefault('MAC_UPDATE_TEST_GUARD_LOG', os.environ.get('MAC_UPDATE_TEST_GUARD_LOG', ''))
        kwargs['env'] = env
        super().__init__(*args, **kwargs)
subprocess.Popen = _GuardedPopen
def _deny():
    path = os.environ.get('MAC_UPDATE_TEST_GUARD_LOG')
    if path:
        with open(path, 'a') as log:
            log.write('python network blocked\n')
    raise OSError('network blocked by test guard')
_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex
_original_getaddrinfo = socket.getaddrinfo
def _allowed(address):
    return (os.environ.get('MAC_UPDATE_TEST_ALLOW_LOOPBACK') == '1'
            and isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1', 'localhost'))
def _connect(self, address):
    if self.family == socket.AF_UNIX or _allowed(address):
        return _original_connect(self, address)
    return _deny()
def _connect_ex(self, address):
    if self.family == socket.AF_UNIX or _allowed(address):
        return _original_connect_ex(self, address)
    return _deny()
def _getaddrinfo(host, *args, **kwargs):
    if os.environ.get('MAC_UPDATE_TEST_ALLOW_LOOPBACK') == '1' and host in ('127.0.0.1', '::1', 'localhost', None):
        return _original_getaddrinfo(host, *args, **kwargs)
    return _deny()
socket.getaddrinfo = _getaddrinfo
socket.socket.connect = _connect
socket.socket.connect_ex = _connect_ex
PY_GUARD
if PATH="$GUARD_DIR:$PATH" PYTHONPATH="$GUARD_DIR" python3 -c 'import sys, unittest
sys.path[:0] = ["dev_sync", "lib/python"]
import os
original_run = unittest.TestCase.run
def named_run(self, result=None):
    os.environ["MAC_UPDATE_TEST_NAME"] = self.id()
    try: return original_run(self, result)
    finally: os.environ.pop("MAC_UPDATE_TEST_NAME", None)
unittest.TestCase.run = named_run
prog = unittest.main(module=None, argv=["unittest", "discover", "-s", "tests", "-p", sys.argv[1]], exit=False)
for test, reason in prog.result.skipped:
    print("SKIPPED: {}: {}".format(test.id(), reason))
sys.exit(0 if prog.result.wasSuccessful() else 1)' "$pattern" </dev/null 2>&1; then
    ok "test suite passed"
else
    err "test suite failed"
fi
if [ -s "$GUARD_LOG" ]; then
    err "tests reached unmocked host tools (blocked by guard):"
    sort "$GUARD_LOG" | uniq -c | sed 's/^/      /'
fi
rm -rf "$GUARD_DIR"

if [ "$unit_only" -eq 0 ]; then
say "4/4  scripts/scan_secrets.sh"
if bash scripts/scan_secrets.sh 2>&1; then
    ok "secret scan passed"
else
    err "secret scan failed"
fi

fi

echo ""
if [ "$fail" -eq 0 ]; then
    echo -e "${GREEN}╔══════════════════════════╗${NC}"
    echo -e "${GREEN}║   ALL CHECKS PASSED ✅   ║${NC}"
    echo -e "${GREEN}╚══════════════════════════╝${NC}"
    exit 0
else
    echo -e "${RED}╔══════════════════════════╗${NC}"
    echo -e "${RED}║   CHECKS FAILED      ❌   ║${NC}"
    echo -e "${RED}╚══════════════════════════╝${NC}"
    exit 1
fi
