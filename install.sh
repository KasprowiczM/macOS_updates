#!/usr/bin/env bash
# ============================================================
# install.sh - install or upgrade mac-update from a release archive
# ============================================================
# No git, no sudo, no prompts. Works as a pipe and as a local file:
#
#   curl -fsSL https://github.com/KasprowiczM/macOS_updates/releases/latest/download/install.sh | bash
#   curl -fsSL <that URL> | bash -s -- --version 1.8.3 --configure-shell
#   bash install.sh --dry-run
#
# It checks the Mac, downloads mac-update-<version>.tar.gz and SHA256SUMS,
# verifies the checksum, unpacks next to the target folder, swaps the program
# files in (the old version stays as <dir>.previous) and links the launcher at
# ~/.local/bin/mac-update and its long name ~/.local/bin/macos-update.
# Re-running upgrades in place. The program folder itself never moves: its
# entries (bin, lib, ...) are swapped one by one, each in one atomic
# renamex_np(RENAME_SWAP) call on APFS (plain renames elsewhere), around the
# Node.js and npm tools mac-update keeps there (node/, npm-global/), which are
# never moved, replaced or deleted. An error or Ctrl-C puts the old version back
# at once; a run that was killed is rolled back by the next run.
#
# It never touches your settings folder (~/.config/mac-update), never edits a
# shell profile unless you pass --configure-shell, never uses sudo and never
# starts the Command Line Tools installer for you.
# ============================================================

usage() {
    cat <<'USAGE_TEXT'
Usage: install.sh [options]

  --version X        install release X (default: the latest release)
  --dir DIR          program folder (default: $MAC_UPDATE_HOME or ~/.local/share/mac-update)
  --dry-run          print what would happen; writes nothing and uses no network
  --configure-shell  add ~/.local/bin to PATH in your zsh or bash profile
  --quiet            print only warnings and errors
  -h, --help         show this help

Environment:
  MAC_UPDATE_RELEASE_BASE     release download base laid out as <base>/v<version>/<file>;
                              without --version it also needs <base>/LATEST (mirrors, tests)
  MAC_UPDATE_INSTALL_VERSION  same as --version
  MAC_UPDATE_HOME             program folder
  NO_COLOR                    plain output

Exit codes: 0 done, 1 failed, 2 bad usage, 3 this Mac is missing a prerequisite.
USAGE_TEXT
}

main() {
    # Never let a child process read the rest of a piped script.
    exec </dev/null

    local GITHUB_REPO="KasprowiczM/macOS_updates"
    local DEFAULT_BASE="https://github.com/${GITHUB_REPO}/releases/download"
    local LATEST_PAGE="https://github.com/${GITHUB_REPO}/releases/latest"
    local ISSUES_URL="https://github.com/${GITHUB_REPO}/issues"

    local OPT_VERSION="${MAC_UPDATE_INSTALL_VERSION:-}" OPT_DIR="" DRY_RUN=0 CONFIGURE_SHELL=0 QUIET=0
    local CUSTOM_BASE=0 BASE
    if [ -n "${MAC_UPDATE_RELEASE_BASE:-}" ]; then
        CUSTOM_BASE=1
        BASE="${MAC_UPDATE_RELEASE_BASE%/}"
    else
        BASE="$DEFAULT_BASE"
    fi

    local GREEN="" YELLOW="" RED="" BOLD="" NC=""
    if [ -t 1 ] && [ -z "${NO_COLOR:-}" ] && [ "${TERM:-dumb}" != dumb ]; then
        GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'; RED=$'\033[0;31m'; BOLD=$'\033[1m'; NC=$'\033[0m'
    fi

    # ---- output: one row per fact, plain sentences ----
    row_ok()   { [ "$QUIET" = 1 ] || printf '  %s\xe2\x9c\x93%s %s\n' "$GREEN" "$NC" "$1"; }
    row_warn() { printf '  %s!%s %s\n' "$YELLOW" "$NC" "$1"; }
    row_note() { [ "$QUIET" = 1 ] || printf '    %s\n' "$1"; }
    row_plan() { printf '  %s\xe2\x86\x92%s %s\n' "$BOLD" "$NC" "$1"; }
    # die "what happened." "what to do." [exit code]
    die() {
        printf '  %s\xe2\x9c\x97%s %s\n' "$RED" "$NC" "$1" >&2
        printf '    %s\n' "$2" >&2
        exit "${3:-1}"
    }

    # ---- arguments ----
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --version)
                [ -n "${2:-}" ] || die "--version needs a version number." "For example: --version 1.8.3" 2
                OPT_VERSION="$2"; shift 2 ;;
            --version=*) OPT_VERSION="${1#--version=}"; shift ;;
            --dir)
                [ -n "${2:-}" ] || die "--dir needs a folder." "For example: --dir \$HOME/.local/share/mac-update" 2
                OPT_DIR="$2"; shift 2 ;;
            --dir=*) OPT_DIR="${1#--dir=}"; shift ;;
            --dry-run) DRY_RUN=1; shift ;;
            --configure-shell) CONFIGURE_SHELL=1; shift ;;
            --quiet|-q) QUIET=1; shift ;;
            -h|--help) usage; return 0 ;;
            *) die "Unknown option: $1" "Run it with --help to see the options." 2 ;;
        esac
    done

    local HOME_DIR="${HOME:-}"
    case "$HOME_DIR" in
        /*) ;;
        *) die "HOME is not set to an absolute folder." "Run the installer from a normal terminal session." 1 ;;
    esac
    HOME_DIR="${HOME_DIR%/}"

    [ "$QUIET" = 1 ] || printf '\n%smac-update installer%s\n\n' "$BOLD" "$NC"

    # ---- 1. platform ----
    local os arch macos major
    os="$(uname -s 2>/dev/null || echo unknown)"
    [ "$os" = Darwin ] || die "This installer only runs on macOS." "Run it on a Mac with Apple Silicon." 3
    arch="$(uname -m 2>/dev/null || echo unknown)"
    [ "$arch" = arm64 ] || die "This Mac has an Intel processor (${arch}), which mac-update does not support." \
        "Use it on an Apple Silicon Mac." 3
    macos="$(sw_vers -productVersion 2>/dev/null || echo 0)"
    major="${macos%%.*}"
    case "$major" in ''|*[!0-9]*) major=0 ;; esac
    [ "$major" -ge 13 ] || die "macOS ${macos} is older than the supported macOS 13." \
        "Update macOS first, then run the installer again." 3
    row_ok "macOS ${macos} on Apple Silicon"

    # ---- 2. python3 (Apple's /usr/bin/python3 is only a shim until the Command Line Tools exist) ----
    local py dev pyver
    py="$(command -v python3 2>/dev/null || true)"
    if [ "$py" = /usr/bin/python3 ]; then
        dev="$(xcode-select -p 2>/dev/null || true)"
        if [ -z "$dev" ] || [ ! -x "$dev/usr/bin/python3" ]; then
            py=""
        fi
    fi
    if [ -z "$py" ]; then
        die "Python 3 is not installed yet: macOS only ships a placeholder until the Command Line Tools are installed." \
            "Run \"xcode-select --install\", wait for it to finish, then run this installer again." 3
    fi
    if ! "$py" -I -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
        pyver="$("$py" -I -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo unknown)"
        die "Python ${pyver} is older than the required 3.9." \
            "Install a newer Python (the Command Line Tools provide one: \"xcode-select --install\")." 3
    fi
    pyver="$("$py" -I -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null || echo 3)"
    row_ok "Python ${pyver}"

    local tool
    for tool in curl tar shasum; do
        command -v "$tool" >/dev/null 2>&1 \
            || die "${tool} was not found." "Restore /usr/bin/${tool} (it is part of macOS) and try again." 3
    done

    # ---- 3. program folder ----
    local DIR
    if [ -n "$OPT_DIR" ]; then
        DIR="$OPT_DIR"
    elif [ -n "${MAC_UPDATE_HOME:-}" ]; then
        DIR="$MAC_UPDATE_HOME"
    else
        DIR="$HOME_DIR/.local/share/mac-update"
    fi
    case "$DIR" in
        /*) ;;
        *) die "The program folder must be an absolute path (got: ${DIR})." \
               "Pass something like --dir \"\$HOME/.local/share/mac-update\"." 2 ;;
    esac
    while [ "${DIR%/}" != "$DIR" ] && [ -n "${DIR%/}" ]; do DIR="${DIR%/}"; done
    local depth
    depth="$(printf '%s' "$DIR" | tr -cd '/' | wc -c | tr -d ' ')"
    if [ "$DIR" = "/" ] || [ "$DIR" = "$HOME_DIR" ] || [ "$depth" -lt 2 ]; then
        die "${DIR} is too broad to use as the program folder." \
            "Choose a folder of its own, for example --dir \"\$HOME/.local/share/mac-update\"." 2
    fi
    case "$DIR" in
        */.|*/..|*/./*|*/../*) die "The program folder path may not contain . or .. parts." "Spell out the full path." 2 ;;
    esac

    local PREV="${DIR}.previous" OLD="${DIR}.swap-old"
    local LAUNCH_DIR="$HOME_DIR/.local/bin"
    local LAUNCHER="$LAUNCH_DIR/mac-update"
    local ALIAS="$LAUNCH_DIR/macos-update"

    # Toolkit-managed data inside the program folder. update_npm_cli.sh keeps the managed
    # Node.js (node/) and the global npm packages (npm-global/) in ~/.local/share/mac-update,
    # which is also the default program folder, and briefly node.staging.* / node.backup.*
    # while it replaces Node. *.older.* are older copies this installer set aside (see
    # rescue_managed_data). People's PATH points into them, so install, update and rollback
    # swap the program files around these names and never move, replace or delete them.
    # One name per word, shell patterns allowed, matched without regard to case (APFS is
    # case-insensitive); a new name is one more word here.
    # Keep in step with MANAGED_DATA_NAMES in uninstall.sh (a test compares them).
    local MANAGED_DATA_NAMES='node npm-global node.staging.* node.backup.* node.older.* npm-global.older.*'
    # Finder metadata that may sit next to them: left in place, never counted as foreign.
    local IGNORED_NAMES='.DS_Store'
    # MU_TEST_* knobs below act only when MAC_UPDATE_INSTALLER_TEST_HOOKS=1 (set by the tests).
    local TEST_HOOKS=0
    [ "${MAC_UPDATE_INSTALLER_TEST_HOOKS:-}" != 1 ] || TEST_HOOKS=1

    name_in() { # name_in NAME "PATTERNS" : NAME matches one of the patterns, ignoring case
        local name="$1" pat hit=1 had=0
        shopt -q nocasematch && had=1
        shopt -s nocasematch
        set -f
        for pat in $2; do
            case "$name" in $pat) hit=0; break ;; esac
        done
        set +f
        [ "$had" = 1 ] || shopt -u nocasematch
        return "$hit"
    }
    is_managed_data() { name_in "$1" "$MANAGED_DATA_NAMES"; }
    is_kept_name() { name_in "$1" "$MANAGED_DATA_NAMES $IGNORED_NAMES"; }
    # Every entry of a folder, dotfiles included: for e in "$d"/* "$d"/.[!.]* "$d"/..?*
    managed_in() { # managed_in DIR : the managed data names in DIR, comma separated
        local e n out=""
        for e in "$1"/* "$1"/.[!.]* "$1"/..?*; do
            [ -e "$e" ] || [ -L "$e" ] || continue
            n="${e##*/}"
            if is_managed_data "$n"; then out="${out:+$out, }$n"; fi
        done
        printf '%s' "$out"
    }
    foreign_in() { # foreign_in DIR : the first entry that is neither managed data nor Finder metadata
        local e
        for e in "$1"/* "$1"/.[!.]* "$1"/..?*; do
            [ -e "$e" ] || [ -L "$e" ] || continue
            if ! is_kept_name "${e##*/}"; then printf '%s' "${e##*/}"; return 0; fi
        done
        return 0
    }
    # managed_deep PATH : where managed data sits in PATH, in its subfolders and in theirs
    # (a staging folder holds a toolkit copy one or two levels down); it does not look
    # inside managed folders themselves.
    managed_deep() {
        local a b m out=""
        m="$(managed_in "$1")"
        [ -z "$m" ] || out="${1}: ${m}"
        for a in "$1"/* "$1"/.[!.]* "$1"/..?*; do
            [ -d "$a" ] && [ ! -L "$a" ] || continue
            ! name_in "${a##*/}" "$MANAGED_DATA_NAMES" || continue
            m="$(managed_in "$a")"
            [ -z "$m" ] || out="${out:+$out; }${a}: ${m}"
            for b in "$a"/* "$a"/.[!.]* "$a"/..?*; do
                [ -d "$b" ] && [ ! -L "$b" ] || continue
                ! name_in "${b##*/}" "$MANAGED_DATA_NAMES" || continue
                m="$(managed_in "$b")"
                [ -z "$m" ] || out="${out:+$out; }${b}: ${m}"
            done
        done
        printf '%s' "$out"
    }
    # remove_tree PATH : rm -rf PATH, unless managed data is anywhere in it (then it stays, with a warning)
    remove_tree() {
        local found
        [ -e "$1" ] || [ -L "$1" ] || return 0
        if [ -d "$1" ] && [ ! -L "$1" ]; then
            found="$(managed_deep "$1")"
            if [ -n "$found" ]; then
                row_warn "Kept ${1}: it holds Node.js or npm tools mac-update manages (${found})."
                row_note "Nothing was deleted there. Move what you need back, then delete ${1} by hand."
                return 1
            fi
        fi
        rm -rf "$1"
    }
    interrupted_swap() { # a staging folder with a swap journal: an earlier run was killed mid-swap
        local d
        for d in "${DIR}".tmp.*; do
            if [ -f "$d/journal" ]; then return 0; fi
        done
        return 1
    }

    # A folder that exists must be ours, empty, or hold only managed data; never move foreign data aside.
    is_toolkit_dir() { [ -f "$1/update_all.sh" ] && [ -f "$1/VERSION" ]; }
    check_dir() {
        if [ -e "$DIR" ] || [ -L "$DIR" ]; then
            if [ -e "$DIR/.git" ]; then
                die "${DIR} is a git checkout, and the installer will not replace a working copy." \
                    "Pick another place with --dir, or keep using the checkout."
            fi
            if [ ! -d "$DIR" ]; then
                die "${DIR} exists and is not a folder." "Remove it or pick another place with --dir."
            fi
            if ! is_toolkit_dir "$DIR" && [ -n "$(foreign_in "$DIR")" ] && ! interrupted_swap; then
                die "${DIR} already holds files that are not mac-update." "Pick an empty folder with --dir."
            fi
        fi
    }
    check_dir
    local KEPT_DATA=""
    [ ! -d "$DIR" ] || KEPT_DATA="$(managed_in "$DIR")"
    local installed=""
    if is_toolkit_dir "$DIR"; then
        installed="$(tr -d '[:space:]' < "$DIR/VERSION" 2>/dev/null || true)"
    fi

    # ---- 4. which version ----
    local VERSION="" TAG TARNAME
    version_ok() { printf '%s' "$1" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+([-+.][0-9A-Za-z.-]+)?$'; }
    if [ -n "$OPT_VERSION" ]; then
        VERSION="${OPT_VERSION#v}"
        version_ok "$VERSION" || die "\"${OPT_VERSION}\" is not a release version." "Use a number like 1.8.3." 2
    fi

    fetch() { # fetch URL DEST
        local url="$1" dest="$2" proto="=https"
        if [ "$CUSTOM_BASE" = 1 ]; then proto="=https,file"; fi
        curl --fail --silent --show-error --location --proto "$proto" --proto-redir "=https" \
            --connect-timeout 15 --max-time 900 --retry 2 -o "$dest" "$url" </dev/null
    }

    if [ -z "$VERSION" ]; then
        if [ "$DRY_RUN" = 1 ]; then
            VERSION="latest"
        elif [ "$CUSTOM_BASE" = 1 ]; then
            local latest_file latest_raw
            latest_file="$(mktemp "${TMPDIR:-/tmp}/mac-update-latest.XXXXXX")" \
                || die "Could not create a temporary file." "Check that ${TMPDIR:-/tmp} is writable."
            if ! fetch "$BASE/LATEST" "$latest_file" 2>/dev/null; then
                rm -f "$latest_file"
                die "Could not find the latest release at ${BASE}." \
                    "Check your internet connection, or choose a release with --version."
            fi
            latest_raw="$(head -n 1 "$latest_file" | tr -d '[:space:]')"
            rm -f "$latest_file"
            VERSION="${latest_raw#v}"
            version_ok "$VERSION" || die "The latest-release answer was not a version number." "Choose a release with --version."
        else
            local landed
            landed="$(curl --fail --silent --show-error --location --proto "=https" --proto-redir "=https" \
                --connect-timeout 15 --max-time 60 -o /dev/null -w '%{url_effective}' "$LATEST_PAGE" </dev/null 2>/dev/null)" \
                || die "Could not look up the latest release." \
                       "Check your internet connection, or choose a release with --version."
            VERSION="${landed##*/}"
            VERSION="${VERSION#v}"
            version_ok "$VERSION" || die "Could not read the latest release number." "Choose a release with --version."
        fi
    fi
    TAG="v${VERSION}"
    TARNAME="mac-update-${VERSION}.tar.gz"

    # ---- which program each name really starts (read-only) ----
    first_on_path() { # first_on_path NAME : the first executable NAME on PATH
        local dir IFS=:
        set -f
        for dir in ${PATH:-}; do
            [ -n "$dir" ] || continue
            if [ -x "$dir/$1" ] && [ ! -d "$dir/$1" ]; then set +f; printf '%s\n' "$dir/$1"; return 0; fi
        done
        set +f
        return 1
    }
    real_path() { "$py" -I -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$1" 2>/dev/null; }
    # check_names : warn when typing mac-update or macos-update would start some other file.
    check_names() {
        local name hit want
        want="$(real_path "$DIR/bin/mac-update")"
        for name in mac-update macos-update; do
            hit="$(first_on_path "$name")" || continue    # not on PATH at all: the PATH advice covers it
            [ "$hit" != "$LAUNCH_DIR/$name" ] || continue  # ours, or a foreign file already reported
            [ "$(real_path "$hit")" != "$want" ] || continue
            row_warn "Typing ${name} runs ${hit}, not this mac-update: that file comes earlier on your PATH."
            row_note "Remove or rename it, or put ${LAUNCH_DIR} before $(dirname "$hit") in your PATH."
        done
    }

    # ---- dry run: say everything, write nothing ----
    if [ "$DRY_RUN" = 1 ]; then
        printf '  %sDry run: nothing will be written, downloaded or changed.%s\n\n' "$BOLD" "$NC"
        if [ -n "$installed" ]; then
            row_plan "Found version ${installed} in ${DIR}."
        else
            row_plan "Nothing is installed in ${DIR} yet."
        fi
        if [ "$VERSION" = latest ]; then
            row_plan "Look up the latest release, then download mac-update-<version>.tar.gz and SHA256SUMS from ${BASE}/v<version>/."
        else
            row_plan "Download ${TARNAME} and SHA256SUMS from ${BASE}/${TAG}/."
        fi
        row_plan "Check the archive against its SHA-256 checksum and stop if it does not match."
        row_plan "Unpack it into a temporary folder next to ${DIR}."
        if [ -n "$installed" ]; then
            row_plan "Swap the program files in one by one (atomically where the disk allows) and keep version ${installed} as ${PREV}."
        elif [ -d "$DIR" ]; then
            row_plan "Move the program files into ${DIR}."
        else
            row_plan "Move it into place as ${DIR}."
        fi
        if [ -n "$KEPT_DATA" ]; then
            row_plan "Leave ${KEPT_DATA} in ${DIR} exactly where they are (the Node.js and npm tools mac-update manages)."
        fi
        row_plan "Link ${LAUNCHER} to ${DIR}/bin/mac-update."
        row_plan "Link ${ALIAS} to the same file (the same command under a longer name)."
        row_plan "Check which program the names mac-update and macos-update start on your PATH."
        check_names
        case ":${PATH:-}:" in
            *":${LAUNCH_DIR}:"*) row_plan "${LAUNCH_DIR} is already on your PATH; nothing to add." ;;
            *) if [ "$CONFIGURE_SHELL" = 1 ]; then
                   row_plan "Add ${LAUNCH_DIR} to your PATH in your shell profile (--configure-shell)."
               else
                   row_plan "Print the one PATH line to add yourself, because ${LAUNCH_DIR} is not on your PATH."
               fi ;;
        esac
        if interrupted_swap; then
            row_plan "First roll back an earlier update that was interrupted."
        fi
        row_plan "Leave your settings folder, shell profiles and every other file untouched."
        return 0
    fi

    # ---- the swap: program files go in and out around the managed data ----
    # python3 -I -c "$SWAP_PY" swap DIR STAGE NEWROOT "MANAGED PATTERNS" "IGNORED PATTERNS"
    #   Moves every entry of NEWROOT into DIR (VERSION and .install-info last). An entry
    #   DIR already has trades places with the new one (renamex_np RENAME_SWAP: the path
    #   is never missing) or, without that, is moved out and the new one moved in; the old
    #   one lands in STAGE/old. DIR entries the new version lacks also go to STAGE/old,
    #   except managed data and ignored names, which are never touched (names compare
    #   without regard to case, as APFS does). Ignored names in NEWROOT are skipped.
    #   Before each step it appends what it is about to do to STAGE/journal.
    #   Exit 0 done (all atomic), 5 done (plain renames used), 1 failed and rolled back,
    #   2 failed and could not roll back completely, 3 NEWROOT holds a managed name
    #   (checked before anything moves).
    # python3 -I -c "$SWAP_PY" recover DIR STAGE
    #   For a run that was killed: exit 0 when that swap had finished (the live
    #   .install-info carries swap_id=<STAGE name>; STAGE/old is the old version),
    #   6 when it was rolled back now, 2 when it could not be, 7 when STAGE has no journal.
    # -I: nothing from the current folder or PYTHON* variables is imported or honoured.
    # Test knobs, honoured only with MAC_UPDATE_INSTALLER_TEST_HOOKS=1: MU_TEST_NO_EXCHANGE=1
    # (plain renames), MU_TEST_SWAP_STOP=fail:N|kill:N|pause:N before operation N+1: fail
    # raises (in-process rollback), kill exits at once with 99 (the installer then kills
    # itself), pause writes STAGE/paused and sleeps so a test can send a signal.
    local SWAP_PY='
import ctypes, fnmatch, os, signal, sys, time

mode, d, stage = sys.argv[1], sys.argv[2], sys.argv[3]
J = os.path.join
journal, old, trash = J(stage, "journal"), J(stage, "old"), J(stage, "trash")
hooks = os.environ.get("MAC_UPDATE_INSTALLER_TEST_HOOKS") == "1"
ops = [0]
lib = []

def ino(p):
    try:
        return os.lstat(p).st_ino
    except OSError:
        return None

def have(p):
    return os.path.lexists(p)

def matches(name, patterns):
    return any(fnmatch.fnmatchcase(name.lower(), p.lower()) for p in patterns)

def exchange(a, b):
    if hooks and os.environ.get("MU_TEST_NO_EXCHANGE") == "1":
        return False
    try:
        if not lib:
            fn = ctypes.CDLL(None, use_errno=True).renamex_np
            fn.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
            fn.restype = ctypes.c_int
            lib.append(fn)
        return lib[0](os.fsencode(a), os.fsencode(b), 2) == 0
    except (AttributeError, OSError):
        return False

def step():
    spec = os.environ.get("MU_TEST_SWAP_STOP", "") if hooks else ""
    how, _, num = spec.partition(":")
    if mode == "swap" and num.isdigit() and ops[0] == int(num):
        if how == "kill":
            os._exit(99)
        if how == "pause":
            open(J(stage, "paused"), "w").close()
            for _ in range(600):
                time.sleep(0.1)
        raise OSError("test stop")
    ops[0] += 1

def note(line):
    with open(journal, "a") as f:
        f.write(line + "\n")

def good_name(name):
    return bool(name) and name not in (".", "..") and "/" not in name and "\0" not in name

def read_journal():
    newroot, out = None, []
    try:
        with open(journal) as f:
            rows = f.read().split("\n")
    except OSError:
        return None, []
    inside = os.path.realpath(stage) + os.sep
    for row in rows:
        kind, _, rest = row.partition(" ")
        if kind == "N" and rest:
            if os.path.realpath(rest).startswith(inside):
                newroot = rest
        elif kind == "S":
            num, _, name = rest.partition(" ")
            if num.isdigit() and good_name(name):
                out.append(("S", int(num), name))
        elif kind == "R" and good_name(rest):
            out.append(("R", None, rest))
    return newroot, out

def put_back():
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    newroot, entries = read_journal()
    ok = True
    for kind, new_ino, name in reversed(entries):
        dst, was = J(d, name), J(old, name)
        try:
            if kind == "S" and have(dst) and ino(dst) == new_ino:
                os.makedirs(trash, exist_ok=True)
                spot, n = J(trash, name), 0
                while have(spot):
                    n += 1
                    spot = J(trash, "%s.%d" % (name, n))
                os.rename(dst, spot)
            if not have(dst):
                src = J(newroot, name) if newroot else None
                if have(was):
                    os.rename(was, dst)
                elif kind == "S" and src and have(src) and ino(src) != new_ino:
                    os.rename(src, dst)
        except OSError:
            ok = False
    if have(old) and os.listdir(old):
        ok = False
    return ok

def swap(new, managed, ignored):
    incoming = sorted(n for n in os.listdir(new) if not matches(n, ignored))
    if any(matches(n, managed) for n in incoming):
        sys.exit(3)
    lower = set(n.lower() for n in incoming)
    last = [n for n in ("VERSION", ".install-info") if n in incoming]
    first = [n for n in incoming if n not in last]
    retire = sorted(n for n in os.listdir(d)
                    if n.lower() not in lower and not matches(n, managed) and not matches(n, ignored))
    os.mkdir(old)
    note("N " + new)
    plain = False
    def swap_in(n):
        src, dst = J(new, n), J(d, n)
        note("S %d %s" % (ino(src), n))
        if have(dst):
            step()
            if exchange(src, dst):
                step()
                os.rename(src, J(old, n))
                return False
            os.rename(dst, J(old, n))
            step()
            os.rename(src, dst)
            return True
        step()
        os.rename(src, dst)
        return False
    for n in first:
        plain = swap_in(n) or plain
    for n in retire:
        note("R " + n)
        step()
        os.rename(J(d, n), J(old, n))
    for n in last:
        plain = swap_in(n) or plain
    step()
    return 5 if plain else 0

def finished():
    try:
        with open(J(d, ".install-info")) as f:
            return ("swap_id=" + os.path.basename(stage)) in f.read().split("\n")
    except OSError:
        return False

def interrupted(signum, frame):
    raise KeyboardInterrupt

if mode == "swap":
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    try:
        rc = swap(sys.argv[4], sys.argv[5].split(), sys.argv[6].split())
    except SystemExit:
        raise
    except BaseException:
        sys.exit(1 if put_back() else 2)
    sys.exit(rc)
if not os.path.isfile(journal):
    sys.exit(7)
if finished():
    newroot, entries = read_journal()
    for kind, new_ino, name in entries:
        src = J(newroot, name) if newroot else None
        if kind == "S" and src and have(src) and ino(src) != new_ino and not have(J(old, name)):
            os.rename(src, J(old, name))
    sys.exit(0)
sys.exit(6 if put_back() else 2)
'

    # being_replaced NAME : update_npm_cli.sh is replacing NAME right now (NAME.staging.* or
    # NAME.backup.* sits next to it), so NAME may be missing for a moment: leave it alone.
    being_replaced() {
        local e
        for e in "$DIR/$1".staging.* "$DIR/$1".backup.*; do
            if [ -e "$e" ] || [ -L "$e" ]; then return 0; fi
        done
        return 1
    }
    # rescue_managed_data FROM : managed data that an older installer (which swapped the whole
    # folder) moved into FROM goes back into DIR. When DIR already has that name, the copy
    # from FROM goes next to it as NAME.older.<time> (a managed name too, so nothing ever
    # deletes it) and the user is told once where it is. Returns 1 when some stays in FROM.
    rescue_managed_data() {
        local from="$1" e n spot k left=0
        [ -d "$from" ] && [ ! -L "$from" ] || return 0
        for e in "$from"/* "$from"/.[!.]* "$from"/..?*; do
            [ -e "$e" ] || [ -L "$e" ] || continue
            n="${e##*/}"
            is_managed_data "$n" || continue
            if [ ! -d "$DIR" ] || being_replaced "$n"; then
                left=1
                continue
            fi
            spot="$DIR/$n"
            if [ -e "$spot" ] || [ -L "$spot" ]; then
                spot="$DIR/${n}.older.$(date +%Y%m%d-%H%M%S)"
                k=0
                while [ -e "$spot" ] || [ -L "$spot" ]; do
                    k=$((k + 1))
                    spot="$DIR/${n}.older.$(date +%Y%m%d-%H%M%S)-${k}"
                done
            fi
            if mv "$e" "$spot" 2>/dev/null; then
                if [ "$spot" = "$DIR/$n" ]; then
                    row_warn "Put ${spot} back: an older installer had moved it into ${from}."
                else
                    row_warn "An older copy of ${n} was in ${from}; it is now ${spot}."
                    row_note "Nothing uses it. Delete it by hand once you no longer need it."
                fi
            else
                left=1
            fi
        done
        return "$left"
    }
    # replace_previous SRC : SRC, the version just replaced, becomes <dir>.previous.
    # Managed data is never deleted on the way (rescue_managed_data, remove_tree), and an
    # existing <dir>.previous is only replaced when there is something to replace it with.
    replace_previous() {
        local src="$1"
        if [ ! -d "$src" ] || [ -z "$(ls -A "$src" 2>/dev/null)" ]; then
            return 0
        fi
        rescue_managed_data "$src" || true
        if [ -e "$PREV" ] || [ -L "$PREV" ]; then
            rescue_managed_data "$PREV" || true
            remove_tree "$PREV" || return 0
        fi
        mv "$src" "$PREV" 2>/dev/null || true
        return 0
    }

    # ---- one installer at a time: a lock folder next to the program folder ----
    local LOCK="${DIR}.lock" LOCKED=0
    take_lock() {
        local pid tries=0
        while ! mkdir "$LOCK" 2>/dev/null; do
            pid="$(head -n 1 "$LOCK/pid" 2>/dev/null)"
            case "$pid" in ''|*[!0-9]*) pid="" ;; esac
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                die "Another mac-update installer is running (process ${pid})." \
                    "Wait for it to finish, then run the installer again."
            fi
            tries=$((tries + 1))
            [ "$tries" -le 5 ] || die "Could not take the installer lock ${LOCK}." \
                "If no installer is running, delete that folder and run the installer again."
            if [ -z "$pid" ] && [ "$tries" = 1 ]; then
                sleep 1   # it may have been created a moment ago; let its pid arrive
                continue
            fi
            rm -f "$LOCK/pid" 2>/dev/null
            rmdir "$LOCK" 2>/dev/null   # stale: the installer that held it is gone
        done
        LOCKED=1
        printf '%s\n' "$$" > "$LOCK/pid"
    }
    release_lock() {
        if [ "$LOCKED" = 1 ]; then
            rm -f "$LOCK/pid" 2>/dev/null
            rmdir "$LOCK" 2>/dev/null
            LOCKED=0
        fi
    }

    # ---- recovery from an interrupted earlier run, and cleanup on exit ----
    local SWAP_ACTIVE=0 STAGE="" d t c rc
    recover_interrupted() {
        for d in "${DIR}".tmp.*; do
            [ -e "$d" ] || continue
            if [ -f "$d/journal" ]; then
                rc=0
                "$py" -I -c "$SWAP_PY" recover "$DIR" "$d" || rc=$?
                case "$rc" in
                    0) replace_previous "$d/old" ;;
                    6) row_warn "An earlier update was interrupted; the version installed before it was put back." ;;
                    *) die "An earlier update was interrupted and could not be undone automatically." \
                           "Its files are kept in ${d}. Report it at ${ISSUES_URL}." ;;
                esac
                remove_tree "$d" || true
                continue
            fi
            # Left by an older installer that swapped the whole folder: a swap that finished
            # leaves the OLD version inside the staging folder, and the live .install-info
            # names that folder (swap_id). Keep the old version as <dir>.previous.
            if [ -f "$DIR/.install-info" ] && grep -qx "swap_id=${d##*/}" "$DIR/.install-info" 2>/dev/null; then
                t=""
                for c in "$d/x" "$d/x"/*; do
                    if [ -d "$c" ] && is_toolkit_dir "$c"; then t="$c"; break; fi
                done
                if [ -n "$t" ]; then
                    replace_previous "$t"
                fi
            fi
            remove_tree "$d" || true
        done
        if [ -d "$OLD" ]; then
            if [ ! -e "$DIR" ]; then
                if mv "$OLD" "$DIR" 2>/dev/null; then
                    row_warn "An earlier update was interrupted; the previous version was put back."
                fi
            else
                replace_previous "$OLD"
                [ ! -e "$OLD" ] || remove_tree "$OLD" || true
            fi
        fi
        return 0
    }
    cleanup() {
        if [ "$SWAP_ACTIVE" = 1 ]; then
            SWAP_ACTIVE=0
            recover_interrupted
        fi
        [ -z "$STAGE" ] || remove_tree "$STAGE" || true
        release_lock
    }
    trap cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM HUP

    mkdir -p "$(dirname "$DIR")" 2>/dev/null \
        || die "Cannot create the folder for ${DIR}." "Check that you can write there, or pick another place with --dir."
    [ -w "$(dirname "$DIR")" ] \
        || die "Cannot write to $(dirname "$DIR")." "Check its permissions, or pick another place with --dir."
    take_lock
    recover_interrupted
    check_dir
    KEPT_DATA=""
    [ ! -d "$DIR" ] || KEPT_DATA="$(managed_in "$DIR")"
    installed=""
    if is_toolkit_dir "$DIR"; then
        installed="$(tr -d '[:space:]' < "$DIR/VERSION" 2>/dev/null || true)"
    fi

    # ---- already current: only make sure the launcher is right ----
    local skip_download=0
    if [ -n "$installed" ] && [ "$installed" = "$VERSION" ] && [ -x "$DIR/bin/mac-update" ] && [ -f "$DIR/.install-info" ]; then
        skip_download=1
        row_ok "Version ${VERSION} is already installed in ${DIR}"
    fi

    if [ "$skip_download" = 0 ]; then
        # ---- 5. download ----
        STAGE="$(mktemp -d "${DIR}.tmp.XXXXXX" 2>/dev/null)" \
            || die "Cannot create a temporary folder next to ${DIR}." \
                   "Free some disk space or check the folder's permissions, then run again."
        mkdir "$STAGE/dl" "$STAGE/x" \
            || die "Cannot create a temporary folder next to ${DIR}." \
                   "Free some disk space or check the folder's permissions, then run again."
        local fname rc
        for fname in "$TARNAME" SHA256SUMS; do
            fetch "${BASE}/${TAG}/${fname}" "$STAGE/dl/${fname}" 2>"$STAGE/curl.err"
            rc=$?
            if [ "$rc" -ne 0 ]; then
                if [ "$rc" = 22 ]; then
                    die "Release ${VERSION} has no file named ${fname}." \
                        "Check the version number, or leave out --version to get the latest release."
                fi
                die "Could not download ${fname}." "Check your internet connection and run the installer again."
            fi
        done
        row_ok "Downloaded ${TARNAME}"

        # ---- 6. checksum ----
        local want got matches
        matches="$(awk -v f="$TARNAME" '{ n = $2; sub(/^\*/, "", n); if (n == f) print $1 }' "$STAGE/dl/SHA256SUMS" | wc -l | tr -d ' ')"
        want="$(awk -v f="$TARNAME" '{ n = $2; sub(/^\*/, "", n); if (n == f) { print $1; exit } }' "$STAGE/dl/SHA256SUMS" | tr 'A-F' 'a-f')"
        if [ "$matches" != 1 ] || ! printf '%s' "$want" | grep -Eq '^[0-9a-f]{64}$'; then
            die "SHA256SUMS does not list ${TARNAME} exactly once, so the download cannot be checked." \
                "Nothing was installed. Run the installer again; if it keeps failing, report it at ${ISSUES_URL}."
        fi
        got="$(shasum -a 256 "$STAGE/dl/$TARNAME" | awk '{ print $1 }' | tr 'A-F' 'a-f')"
        if [ "$got" != "$want" ]; then
            die "The downloaded archive does not match its published checksum, so it was thrown away." \
                "Nothing was installed. Run the installer again; if it keeps failing, report it at ${ISSUES_URL}."
        fi
        row_ok "Checksum verified (SHA-256)"

        # ---- 7. unpack: refuse absolute paths, .. parts and links that leave the folder ----
        local listing
        listing="$(tar -tzf "$STAGE/dl/$TARNAME" 2>/dev/null)" \
            || die "The archive is damaged and cannot be read." "Nothing was installed. Run the installer again."
        if printf '%s\n' "$listing" | grep -Eq '(^/)|((^|/)\.\.(/|$))'; then
            die "The archive contains paths outside its own folder, so it was not unpacked." \
                "Nothing was installed. Report it at ${ISSUES_URL}."
        fi
        if tar -tvzf "$STAGE/dl/$TARNAME" 2>/dev/null | grep -E ' -> ' | sed 's/.* -> //' | grep -Eq '(^/)|((^|/)\.\.(/|$))'; then
            die "The archive contains links that point outside its own folder, so it was not unpacked." \
                "Nothing was installed. Report it at ${ISSUES_URL}."
        fi
        tar -xzf "$STAGE/dl/$TARNAME" -C "$STAGE/x" 2>"$STAGE/tar.err" \
            || die "The archive could not be unpacked (the disk may be full)." \
                   "Free some disk space and run the installer again; nothing was changed."

        local NEWROOT="$STAGE/x" entries sub
        if [ ! -f "$NEWROOT/VERSION" ]; then
            entries="$(ls -A "$NEWROOT" | wc -l | tr -d ' ')"
            sub="$(ls -A "$NEWROOT" | head -n 1)"
            if [ "$entries" = 1 ] && [ -d "$NEWROOT/$sub" ] && [ -f "$NEWROOT/$sub/VERSION" ]; then
                NEWROOT="$NEWROOT/$sub"
            fi
        fi
        if [ ! -f "$NEWROOT/VERSION" ] || [ ! -f "$NEWROOT/update_all.sh" ] || [ ! -f "$NEWROOT/bin/mac-update" ]; then
            die "The archive is not a complete mac-update release." \
                "Nothing was installed. Report it at ${ISSUES_URL}."
        fi
        if [ "$(tr -d '[:space:]' < "$NEWROOT/VERSION")" != "$VERSION" ]; then
            die "The archive holds version $(tr -d '[:space:]' < "$NEWROOT/VERSION"), not the requested ${VERSION}." \
                "Nothing was installed. Report it at ${ISSUES_URL}."
        fi
        local shipped=""
        shipped="$(managed_in "$NEWROOT")"
        if [ -n "$shipped" ]; then
            # what was just unpacked came from the download, not from this Mac: throw it away
            rm -rf "$STAGE/x"
            die "The archive contains ${shipped}, a name reserved for the Node.js and npm tools mac-update manages." \
                "Nothing was installed. Report it at ${ISSUES_URL}."
        fi
        chmod 755 "$NEWROOT/bin/mac-update" "$NEWROOT/update_all.sh" 2>/dev/null || true
        {
            printf 'version=%s\n' "$VERSION"
            printf 'installed_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
            printf 'source=%s/%s/%s\n' "$BASE" "$TAG" "$TARNAME"
            printf 'installer=1\n'
            printf 'swap_id=%s\n' "${STAGE##*/}"
        } > "$NEWROOT/.install-info" \
            || die "Cannot write inside the temporary folder." "Free some disk space and run the installer again."
        row_ok "Unpacked ${TARNAME}"

        # ---- 8. swap: the program files go in around the managed data; the old version is kept as <dir>.previous ----
        if [ -d "$DIR" ] && [ -z "$(ls -A "$DIR" 2>/dev/null)" ]; then
            rmdir "$DIR" 2>/dev/null || true
        fi
        if [ -e "$DIR" ]; then
            local swap_rc=0
            SWAP_ACTIVE=1
            "$py" -I -c "$SWAP_PY" swap "$DIR" "$STAGE" "$NEWROOT" "$MANAGED_DATA_NAMES" "$IGNORED_NAMES" || swap_rc=$?
            if [ "$swap_rc" = 99 ] && [ "$TEST_HOOKS" = 1 ]; then
                kill -KILL $$   # tests only: behave like a power cut in the middle of the swap
            fi
            case "$swap_rc" in
                0|5)
                    replace_previous "$STAGE/old"
                    SWAP_ACTIVE=0
                    if [ -n "$installed" ]; then
                        row_ok "Updated ${installed} to ${VERSION} (previous version kept in ${PREV})"
                    else
                        row_ok "Installed ${VERSION} in ${DIR}"
                    fi
                    if [ -n "$KEPT_DATA" ]; then
                        row_ok "Left ${KEPT_DATA} in ${DIR} where they were (the Node.js and npm tools mac-update manages)"
                    fi
                    if [ "$swap_rc" = 0 ] && [ -n "$installed" ]; then
                        row_note "Swapped in atomically, one entry at a time: ${DIR} was never missing."
                    fi ;;
                1)
                    SWAP_ACTIVE=0
                    if [ -n "$installed" ]; then
                        die "Could not put the new version in place, so it was taken out again; ${installed} is still installed." \
                            "Free some disk space, close anything using ${DIR} and run the installer again."
                    fi
                    die "Could not put the new version in place, so it was taken out again." \
                        "Free some disk space, close anything using ${DIR} and run the installer again." ;;
                3)
                    SWAP_ACTIVE=0
                    rm -rf "$STAGE/x"   # the unpacked download, nothing from this Mac
                    die "The archive contains a name reserved for the Node.js and npm tools mac-update manages." \
                        "Nothing was changed. Report it at ${ISSUES_URL}." ;;
                *)
                    SWAP_ACTIVE=0
                    local kept_stage="$STAGE"
                    STAGE=""
                    die "Could not put the new version in place, and the old one could not be restored completely." \
                        "Its files are kept in ${kept_stage}; run the installer again, which retries the restore." ;;
            esac
        else
            mv "$NEWROOT" "$DIR" 2>/dev/null \
                || die "Could not move the new version into place." \
                       "Check the folder's permissions and free disk space, then run again."
            row_ok "Installed ${VERSION} in ${DIR}"
        fi
    fi

    # ---- 9. launchers: mac-update and its long name macos-update, both links to bin/mac-update ----
    local target="$DIR/bin/mac-update" LINK_STATE launcher_state
    # link_launcher LINK : point LINK at target unless it belongs to something else.
    # Sets LINK_STATE to same | replace | foreign | nodir | failed. Never fails the install.
    link_launcher() {
        local link="$1" cur link_dir tmp_link
        LINK_STATE=ok
        mkdir -p "$LAUNCH_DIR" 2>/dev/null || LINK_STATE=nodir
        if [ "$LINK_STATE" = ok ]; then
            if [ -L "$link" ]; then
                cur="$(readlink "$link")"
                if [ "$cur" = "$target" ]; then
                    LINK_STATE=same
                else
                    link_dir="${cur%/bin/mac-update}"
                    if [ "$link_dir" != "$cur" ] && { [ -f "$link_dir/.install-info" ] || [ ! -e "$cur" ]; }; then
                        LINK_STATE=replace
                    else
                        LINK_STATE=foreign
                    fi
                fi
            elif [ -e "$link" ]; then
                LINK_STATE=foreign
            else
                LINK_STATE=replace
            fi
        fi
        case "$LINK_STATE" in
            same) row_ok "Launcher is in place: ${link}" ;;
            replace)
                tmp_link="$LAUNCH_DIR/.${link##*/}.$$"
                if ln -s "$target" "$tmp_link" 2>/dev/null && mv -f "$tmp_link" "$link" 2>/dev/null; then
                    row_ok "Launcher linked: ${link}"
                else
                    rm -f "$tmp_link" 2>/dev/null
                    row_warn "Could not create ${link}. Run mac-update directly with ${target}."
                    LINK_STATE=failed
                fi ;;
            foreign)
                row_warn "${link} already exists and is not from mac-update, so it was left alone."
                row_note "Run mac-update directly with ${target}, or remove that file and run the installer again." ;;
            nodir)
                row_warn "Could not create ${LAUNCH_DIR}. Run mac-update directly with ${target}." ;;
        esac
    }
    link_launcher "$LAUNCHER"
    launcher_state="$LINK_STATE"
    if [ "$launcher_state" != nodir ]; then
        link_launcher "$ALIAS"
    fi

    # ---- 10. PATH: never edits a profile without --configure-shell ----
    local path_line='export PATH="$HOME/.local/bin:$PATH"' rc="" shell_name
    case "$launcher_state" in
        same|replace)
            case ":${PATH:-}:" in
                *":${LAUNCH_DIR}:"*) row_ok "${LAUNCH_DIR} is on your PATH" ;;
                *)
                    shell_name="${SHELL##*/}"
                    case "$shell_name" in
                        zsh) rc="$HOME_DIR/.zshrc" ;;
                        bash) rc="$HOME_DIR/.bash_profile" ;;
                    esac
                    if [ "$CONFIGURE_SHELL" = 1 ] && [ -n "$rc" ]; then
                        if [ -f "$rc" ] && grep -q '^# >>> mac-update >>>' "$rc" 2>/dev/null; then
                            row_ok "${rc} already has the mac-update PATH block"
                        elif { printf '\n# >>> mac-update >>>\n%s\n# <<< mac-update <<<\n' "$path_line" >> "$rc"; } 2>/dev/null; then
                            row_ok "Added ${LAUNCH_DIR} to your PATH in ${rc}"
                            row_note "Open a new terminal window for it to take effect."
                        else
                            row_warn "Could not write ${rc}."
                            row_note "Add this line to your shell profile yourself: ${path_line}"
                        fi
                    else
                        row_warn "${LAUNCH_DIR} is not on your PATH yet."
                        row_note "Add this line to your shell profile (or re-run with --configure-shell), then open a new terminal:"
                        row_note "  ${path_line}"
                        if [ "$CONFIGURE_SHELL" = 1 ]; then
                            row_note "Your shell (${shell_name:-unknown}) is not zsh or bash, so no profile was edited."
                        fi
                    fi ;;
            esac ;;
    esac

    check_names

    cleanup
    trap - EXIT
    if [ "$QUIET" != 1 ]; then
        printf '\n  %sDone.%s Run %smac-update%s to open it. Your settings folder was not touched.\n\n' \
            "$BOLD" "$NC" "$BOLD" "$NC"
    fi
    return 0
}

main "$@"; exit $?
