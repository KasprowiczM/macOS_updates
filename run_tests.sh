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

fail=0
say()  { echo -e "${CYAN}── $1${NC}"; }
ok()   { echo -e "  ${GREEN}✅ $1${NC}"; }
err()  { echo -e "  ${RED}❌ $1${NC}"; fail=1; }

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

say "3/4  python3 -m unittest discover tests"
if python3 -c 'import sys, unittest
sys.path[:0] = ["dev_sync", "lib/python"]
prog = unittest.main(module=None, argv=["unittest", "discover", "-s", "tests"], exit=False)
sys.exit(0 if prog.result.wasSuccessful() else 1)' 2>&1; then
    ok "test suite passed"
else
    err "test suite failed"
fi

say "4/4  scripts/scan_secrets.sh"
if bash scripts/scan_secrets.sh 2>&1; then
    ok "secret scan passed"
else
    err "secret scan failed"
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
