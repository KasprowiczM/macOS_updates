# Implementation Prompt — Gemini 3 Flash (High Effort)
## macOS Updates v1.3.1 → v1.4.0

**Source review:** `docs/reviews/Opus5_Max_Ultra_Review_v6.md` (2026-08-12, HEAD `dd3c7d5`)
**Scope of this prompt:** Blocks 1 and 2 only — tasks **A3, A4, A5, A6, A1a–A1h, B1–B4**.
Blocks 3–5 (tasks C\*, D\*, P\*, L\*) are **out of scope**; they ship in v1.5.0.

Copy everything between the `====` markers into Gemini.

---

```
================================================================================
ROLE

You are implementing v1.4.0 of macOS Updates, a Bash 3.2 + Python 3 update
orchestrator for Apple Silicon Macs. You are working from an independent
read-only audit (Opus5 Max Ultra Review v6). Nine tasks, no more.

Repo root: the directory containing update_all.sh, VERSION (1.3.1) and
config/internet_apps.txt.

--------------------------------------------------------------------------------
PROCESS — read this twice before writing a line of code

  * Implement EXACTLY tasks A3, A4, A5, A6, A1, B. Do NOT invent, renumber,
    merge or add tasks. Anything else you believe needs doing goes under
    `## PROPOSED - <title>` in IMPLEMENTATION_NOTES.md, NOT implemented.
  * NEVER modify an existing test assertion to make code pass. If a test fails,
    the code is wrong, or the test needs a NEW assertion added alongside the old
    one. Weakening an assertion is the single worst outcome of this round.
  * Paste ACTUAL command output verbatim for every ACCEPTANCE CHECK. Do not
    paraphrase, do not summarise, do not write "passed". Paste the bytes.
  * If an acceptance check cannot run in your environment, say so explicitly and
    name the missing dependency. Do not silently skip it and do not claim a pass.
  * Work task by task. Run `bash run_tests.sh` after each task, not once at the
    end. A green suite after task N is what makes task N+1 debuggable.
  * Calibration note from the last round: v5 flagged that a P1 fix was "verified"
    on Bash 3.2.57 — the one shell where the bug could not manifest. When a
    defect is shell-version-dependent or environment-dependent, verify on the
    version or environment where it MANIFESTS, and say which one you used.

--------------------------------------------------------------------------------
NON-NEGOTIABLE RULES (violating any of these fails the round)

 1. `softwareupdate` install paths MUST keep `-R`. All 3 occurrences in
    update_system.sh stay. Without it macOS downloads updates and never applies
    them.
 2. `mas upgrade` MUST run with root. Do not change the invocation in
    update_appstore.sh.
 3. Bash 3.2 only. No `declare -A`, no `mapfile`, no `readarray`, no `${var^^}`,
    no `&>>`. macOS ships /bin/bash 3.2 and it is a supported target.
 4. Keep `set -o pipefail` in every update_*.sh. NEVER add `set -e` — the
    orchestrator must run every step even on partial failure.
 5. No hardcoded paths. Use `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`.
    Temp files: `mktemp -d "${TMPDIR:-/tmp}/mac_update_*.XXXXXX"`, never bare /tmp.
 6. All seven i18n/lang_*.sh files currently have EXACTLY 671 keys. After your
    changes they must still have an identical count in all seven. Verify with:
      for f in i18n/lang_*.sh; do grep -c '^L_[A-Z0-9_]*=' "$f"; done
 7. Status constants used in exact-match `case` comparisons must stay STATIC —
    no `%s` placeholders. `tests/test_safety_static.py::test_exact_match_status_keys_stay_static`
    enforces this.
 8. A method name in a config file is only valid if a handler exists. Adding a
    method string without its handler is a silent no-op and has shipped as a
    regression twice in this project. `test_every_config_method_has_a_handler`
    enforces it.
 9. NEVER read, print, or commit: .env, .dev_sync_config.json, UPDATES.md,
    dev_sync_logs/. You MAY edit the three specific APPLICATIONS.md lines named
    in task B3 — do not read or quote any other part of that file.
10. Never call interactive `sudo` without a controlling TTY. This is the entire
    subject of task A3.
11. Do not touch anything in docs/reviews/ except appending to
    IMPLEMENTATION_NOTES.md. Do not modify any ultra_review_*.md or
    Opus5_Max_*.md file.

================================================================================
TASK A3 — update_system.sh: severity contract + non-TTY sudo gate   [HIGH]
================================================================================

THE DEFECT (verified by grep, two parts)

Part 1 — the sudo gate is missing. `MAC_UPDATE_NO_SUDO` is consumed in exactly
one place in the whole repo:

    $ grep -rn "MAC_UPDATE_NO_SUDO" --include="*.sh" .
    update_appstore.sh:247:  if [ "${MAC_UPDATE_NO_SUDO:-0}" = "1" ] || { [ ! -t 0 ] && ! sudo -n true; }; then
    update_all.sh:222:       export MAC_UPDATE_NO_SUDO=1
    lib/cli.sh:29:           MAC_UPDATE_NO_SUDO_KEEPALIVE=1     <-- a DIFFERENT variable

update_system.sh is absent from that list yet calls sudo unconditionally at
lines 149 and 159:

    update_system.sh:149:  if sudo softwareupdate -ia -R --verbose; then
    update_system.sh:159:  if sudo softwareupdate -ia -R --verbose; then

update_all.sh:220-224 deliberately does NOT call `sudo -v` when there is no TTY;
it exports MAC_UPDATE_NO_SUDO=1 instead. Step 6 still runs — it is gated only by
SKIP_SYSTEM and BLOCKING_EXIT (update_all.sh:1761-1774). So in a non-TTY run:
  - without Touch ID: `sudo: no tty present` -> exit 1 -> whole run reported as
    failed;
  - with Touch ID (which scripts/setup_touchid_sudo.sh installs!): pam_tid.so
    authenticates WITHOUT a tty -> a Touch ID dialog pops in the background.
That second case is the exact symptom docs/agents/critical_rules.md section 6c
describes as fixed. It was fixed in update_all.sh and update_appstore.sh only.

Part 2 — no severity contract. update_system.sh is the only update_*.sh that
does not source lib/severity.sh:

    $ grep -ln "lib/severity.sh" *.sh
    update_appstore.sh
    update_brew.sh
    update_npm_cli.sh

(update_internet_apps.sh has its own INTERNET_SOFT_EXIT mechanism, so it
complies. update_system.sh has nothing.) Every failure is exit 1. A transient
network failure on `softwareupdate -l` (lines 71-77) becomes a hard failure and
the whole run is banner-reported as "COMPLETED WITH ERRORS".

WHY THE TESTS MISSED IT
tests/test_safety_static.py:1053 `test_leaf_scripts_source_severity_and_have_soft_exit_path`
iterates over ["update_brew.sh", "update_appstore.sh", "update_npm_cli.sh"].
update_system.sh is not in the list. The gap is in test SCOPE, not in the
assertion. Fixing the scope is part of this task.

WHAT TO DO

A3a. Source lib/severity.sh in update_system.sh and call mac_update_severity_init,
     matching the pattern in update_brew.sh:34-36. Exit through
     `mac_update_severity_exit_code` on every path that currently exits 1,
     EXCEPT the two named in A3c.

A3b. `softwareupdate -l` failure (lines 71-77): set SOFT_FAIL=1 and exit 10, not
     1. A transient network failure must never defer macOS security updates.

A3c. Keep HARD (exit 1) exactly two cases:
       - `sudo softwareupdate -ia -R --verbose` itself returns non-zero
         (something broke mid-install);
       - the user explicitly declines a restart-required update (line ~145) —
         current behaviour, keep it, it is a deliberate refusal not a fault.

A3d. Add a sudo gate immediately before BOTH sudo call sites. Copy the shape
     from update_appstore.sh:247 verbatim so the two scripts stay diffable:

         if [ "${MAC_UPDATE_NO_SUDO:-0}" = "1" ] || { [ ! -t 0 ] && ! sudo -n true 2>/dev/null; }; then
             print_warn "$L_SYSTEM_SUDO_SKIPPED_NO_TTY"
             print_info  "sudo softwareupdate -ia -R --verbose"
             SOFT_FAIL=1
         else
             ... existing sudo call, UNCHANGED, -R intact ...
         fi

     The printed command must be the literal command a human can paste. Do not
     print a paraphrase.

A3e. Two new i18n keys in ALL SEVEN i18n/lang_*.sh, same key names, same order,
     each language's own wording:
       L_SYSTEM_SUDO_SKIPPED_NO_TTY  — "No terminal available: macOS system
                                        updates were not installed. Run this
                                        manually:"
       L_SYSTEM_SOFT_CHECK_FAILED    — "Could not query softwareupdate; system
                                        update state is unknown (non-blocking)."
     671 -> 673 in every file.

A3f. Add three tests to tests/test_safety_static.py:
     1. update_system.sh sources lib/severity.sh and calls
        mac_update_severity_exit_code.
     2. Static: every `sudo ` invocation in update_system.sh is inside a block
        whose nearest preceding `if` mentions MAC_UPDATE_NO_SUDO. (Regex over
        the file is acceptable; assert 0 ungated `sudo ` calls.)
     3. Behavioural: with mocked uname/sw_vers/softwareupdate on PATH and
        MAC_UPDATE_NO_SUDO=1 MAC_UPDATE_YES=1, update_system.sh exits 10 and
        invokes `sudo` zero times (use a `sudo` stub that appends to a marker
        file; assert the file is empty).

A3g. ADD "update_system.sh" to the list in
     test_leaf_scripts_source_severity_and_have_soft_exit_path (line ~1054).
     Do not remove the existing three.

ACCEPTANCE CHECK (paste all output verbatim)

    bash -n update_system.sh && echo SYNTAX_OK
    grep -c "MAC_UPDATE_NO_SUDO" update_system.sh          # expect >= 2
    grep -c "softwareupdate -ia -R" update_system.sh       # expect 3, unchanged
    grep -n "lib/severity.sh" update_system.sh

    M=$(mktemp -d)
    printf '#!/bin/sh\necho arm64\n' > "$M/uname"
    printf '#!/bin/sh\ncase "$1" in -productVersion) echo 26.5.2;; -buildVersion) echo T;; *) echo "ProductVersion: 26.5.2";; esac\n' > "$M/sw_vers"
    printf '#!/bin/sh\ncase "$1" in -l) echo "Software Update found the following new or updated software:"; echo "* Label: Safari-26.1"; exit 0;; *) exit 0;; esac\n' > "$M/softwareupdate"
    printf '#!/bin/sh\necho CALLED >> %s/sudo_calls\nexit 0\n' "$M" > "$M/sudo"
    chmod +x "$M"/*
    PATH="$M:/usr/bin:/bin" MAC_UPDATE_NO_SUDO=1 MAC_UPDATE_YES=1 MAC_LANG=en \
        bash ./update_system.sh >/dev/null 2>&1; echo "EXIT=$?"
    echo "SUDO_CALLS=$(wc -l < "$M/sudo_calls" 2>/dev/null || echo 0)"

    for f in i18n/lang_*.sh; do printf '%s %s\n' "$f" "$(grep -c '^L_[A-Z0-9_]*=' "$f")"; done

REQUIRED: SYNTAX_OK; `softwareupdate -ia -R` count still 3; EXIT=10;
SUDO_CALLS=0; all seven i18n files report 673.

================================================================================
TASK A4 — one pinned Homebrew formula must not block macOS updates   [HIGH]
================================================================================

THE DEFECT

update_brew.sh:305-313 (post-upgrade verification):

    if ! REMAINING_FORMULAE=$(brew outdated --formula 2>&1 | strip_ansi); then
        ... SOFT_FAIL=1
    elif [ -n "$REMAINING_FORMULAE" ]; then
        print_error "Formulae still outdated after upgrade:"
        HARD_FAIL=1                       # <-- line 312, exit 1
    fi

HARD_FAIL=1 -> mac_update_severity_exit_code -> 1 -> update_all.sh:1195-1197
sets OVERALL_EXIT=1 AND BLOCKING_EXIT=1 -> update_all.sh:1766-1769 SKIPS step 6.

`brew outdated` LISTS pinned formulae; `brew upgrade` SKIPS them. That is the
documented, intended behaviour of `brew pin`
(https://docs.brew.sh/FAQ, https://github.com/Homebrew/brew/pull/3043).

Consequence: one `brew pin <anything>` at any point in the past means every
subsequent run hard-fails Homebrew and `softwareupdate -ia -R` NEVER runs. The
tool whose purpose is currency silently stops installing OS security patches.
Same family as the 2026-07-26 regression in critical_rules.md section 10.

The defect may be LATENT on this machine — check `brew list --pinned`. Fix it
either way, and report which it was.

WHAT TO DO

A4a. Capture the pinned set once, near the other brew snapshots:
         BREW_PINNED="$(brew list --pinned 2>/dev/null || true)"
     Guard the whole feature on brew supporting it (older brew: empty output,
     which degrades correctly to today's behaviour).

A4b. In BOTH places where `brew outdated --formula` feeds a severity decision
     (the first check at lines 117-126 and the post-upgrade check at 305-313),
     filter pinned formulae out of the list
     BEFORE the emptiness test. Bash 3.2, no associative arrays — a
     `grep -Fxv -f <(printf ...)` is not available portably, so use a plain
     `while read` loop building a filtered string, or write the pinned list to
     a session-dir temp file and use `grep -Fxv -f "$file"`. Match on the
     formula NAME only: `brew outdated --formula` may print
     `name (1.2.3) < 1.2.4`, so split on whitespace first.

A4c. Report pinned-and-outdated formulae as INFORMATION, never silently:
         print_info "$L_BREW_PINNED_SKIPPED"   (followed by the names)
     Silence here would be worse than the bug.

A4d. Downgrade the remaining case. Non-pinned formulae that are STILL outdated
     after a SUCCESSFUL `brew upgrade` become SOFT_FAIL=1, not HARD_FAIL=1.
     Rationale, and put this rationale in a code comment: HARD_FAIL exists for
     "the machine is mid-transaction, a reboot would make it worse"
     (critical_rules.md section 10). A formula that refused to upgrade leaves
     the machine in its previous good state — that is the definition of soft.
     `brew upgrade --formula` RETURNING NON-ZERO (the `if brew upgrade --formula`
     branch at lines 180-186, HARD_FAIL at 184) stays HARD — there something
     genuinely broke mid-operation. Do not touch that branch.

A4e. One new i18n key in all seven files:
         L_BREW_PINNED_SKIPPED — "Pinned formulae, intentionally not upgraded:"
     673 -> 674.

A4f. New behavioural test `test_pinned_formula_does_not_block_macos_step`:
     brew stub where `brew list --pinned` prints `somepkg` and
     `brew outdated --formula` always prints `somepkg (1.0) < 2.0`.
     Assert update_brew.sh exits 0 or 10, NEVER 1.
     Then extend the existing update_all layer harness: the same stub must
     leave BLOCKING_EXIT at 0 and step 6 must execute.

A4g. Do NOT change the cask path. `brew outdated --cask --greedy-auto-updates`
     is already informational-only after upgrade (lines 314-322) and
     `--greedy-auto-updates` is the correct flag — `--greedy` would include
     `version :latest` casks whose version Homebrew cannot know, reinstalling
     them every run.

ACCEPTANCE CHECK (paste all output verbatim)

    bash -n update_brew.sh && echo SYNTAX_OK
    brew list --pinned; echo "PINNED_TODAY_EXIT=$?"          # record: latent or active
    grep -n "brew list --pinned" update_brew.sh
    grep -n "HARD_FAIL=1" update_brew.sh                     # confirm which branches remain hard
    PYTHONPATH=dev_sync python3 -m unittest tests.test_safety_static -k pinned -v 2>&1 | tail -20
    for f in i18n/lang_*.sh; do printf '%s %s\n' "$f" "$(grep -c '^L_[A-Z0-9_]*=' "$f")"; done

REQUIRED: SYNTAX_OK; the new test passes; all seven i18n files report 674;
state explicitly in your notes whether `brew list --pinned` was empty (latent)
or non-empty (active today).

================================================================================
TASK A5 — the scheduled run never installs macOS updates; say so   [HIGH]
================================================================================

THE DEFECT

scripts/install_launchagent.sh:93-99 generates a plist that always passes
`--skip-system` (the literal argument is at line 98). The weekly unattended run therefore NEVER applies macOS
updates. That is a defensible design decision (launchd has no TTY — see A3 —
and nobody wants a reboot at 09:00 Monday), but it is stated NOWHERE: not in
the installer's own output, not in `--check`, not in docs/agents/exit_codes.md,
not in any README. A user who enabled the schedule reasonably believes the
system is covered. Combined with A3 this is a complete hole.

WHAT TO DO

A5a. `--check` and the post-install message must both print, verbatim and
     unmissably:
         "This schedule does NOT install macOS system updates (--skip-system)."
     Use a warning colour/prefix consistent with the rest of the script.

A5b. New flag `--with-system`. It writes a SECOND plist,
     `com.<user>.macos-updates-system`, on a MONTHLY schedule
     (StartCalendarInterval with a Day key, default day 1, same --hour), whose
     ProgramArguments run update_all.sh with:
         -y --skip-prescan --skip-appstore --skip-npm --skip-brew
            --skip-internet --skip-postupdate
     i.e. step 6 only. After A3 this exits 10 with a printable command instead
     of silently prompting for Touch ID, which is the honest outcome for an
     unattended context.
     `--uninstall` must remove BOTH plists. `--check` must report both.

A5c. Document it in:
       - docs/agents/exit_codes.md, section "Sudo Pre-authentication and
         Unattended / Cron Runs"
       - docs/user/<lang>/OPERATIONS.md for all seven languages
     One sentence each, no essay.

A5d. Test `test_launchagent_declares_system_skip`: the generated plist for the
     default schedule contains `--skip-system`, and install_launchagent.sh
     contains the literal warning string from A5a.

ACCEPTANCE CHECK (paste all output verbatim)

    bash -n scripts/install_launchagent.sh && echo SYNTAX_OK
    bash scripts/install_launchagent.sh --help
    bash scripts/install_launchagent.sh --check
    grep -c "skip-system" scripts/install_launchagent.sh
    ls docs/user/*/OPERATIONS.md | wc -l                     # expect 7
    grep -l "skip-system" docs/user/*/OPERATIONS.md | wc -l  # expect 7

REQUIRED: SYNTAX_OK; --check prints the warning; all 7 OPERATIONS.md updated.
Do NOT actually `launchctl load` anything during the check.

================================================================================
TASK A6 — TEE_PID is assigned from a $! that Bash 3.2 does not set  [MEDIUM]
================================================================================

THE DEFECT

update_all.sh:243-255:

    ( while true; do sudo -n true || exit 0; sleep 50; done ) &
    SUDO_KEEPALIVE_PID=$!               # :246
    ...
    exec 3>&1 4>&2                      # :253
    exec > >(tee -a "$LOG_FILE") 2>&1   # :254
    TEE_PID=$!                          # :255   <-- Bash 3.2 does not set $! here

ultra_review_opus5_v5.md section 1 states it explicitly: "Bash 3.2 does not set
$! for a process substitution" — that is why it disqualified the Bash-3.2
verification of the original P1 fix. The same property means that on
/bin/bash (macOS system shell) TEE_PID inherits the PREVIOUS $!, i.e. the sudo
keep-alive PID, or empty when no keep-alive ran (--dry-run).

The effect is not a hang: cleanup_session_dir kills and reaps the keep-alive
before reaching `wait "$TEE_PID"` at :315, so the wait fails instantly and is
swallowed by `|| true`. The effect is worse than a hang because it is invisible:
`tee` is never awaited, so the guarantee "trap diagnostics reach disk" — the
entire point of the M19/P1 fix — does not hold on the shell macOS actually
ships. Behaviour differs between Bash 3.2 and 5.x, and the tests run on 5.x.

test_update_all_does_not_hang_on_tee_wait (tests:1231) only asserts "returns,
exit 0". It passes either way, because the absence of a hang is a SIDE EFFECT
of the bug, not proof of correctness.

WHAT TO DO

A6a. Replace the process substitution with a FIFO, which sets $! deterministically
     on every bash version:

         exec 3>&1 4>&2
         LOG_FIFO="$SESSION_DIR/log.fifo"
         if mkfifo -m 600 "$LOG_FIFO" 2>/dev/null; then
             tee -a "$LOG_FILE" < "$LOG_FIFO" &
             TEE_PID=$!
             exec > "$LOG_FIFO" 2>&1
         else
             print_warn "..."      # degrade to today's behaviour, do not abort
             exec > >(tee -a "$LOG_FILE") 2>&1
             TEE_PID=""
         fi

A6b. The FIFO lives in $SESSION_DIR (already mode 700). Never in bare /tmp.
     cleanup_session_dir removes it after the wait.

A6c. cleanup_session_dir ordering is UNCHANGED and must stay:
       1. kill + wait SUDO_KEEPALIVE_PID, then clear it
       2. exec 1>&3 2>&4
       3. [ -n "$TEE_PID" ] && wait "$TEE_PID"
       4. rm -f "$LOG_FIFO"
     Reordering 1 and 3 reintroduces the orphaned-keepalive regression from
     v1.2.0.

A6d. New test `test_tee_pid_comes_from_a_real_background_job`: in update_all.sh,
     the line assigning TEE_PID is immediately preceded (ignoring blank lines
     and comments) by a line ending in `&` that is NOT a process substitution,
     i.e. the preceding line must not contain `>(`.

A6e. Keep test_update_all_does_not_hang_on_tee_wait exactly as it is. Add, do
     not replace.

ACCEPTANCE CHECK (paste all output verbatim)

    bash -n update_all.sh && echo SYNTAX_OK
    grep -n "TEE_PID\|mkfifo\|LOG_FIFO\|exec 1>&3\|exec 3>&1" update_all.sh
    PYTHONPATH=dev_sync python3 -m unittest tests.test_safety_static -k tee -v 2>&1 | tail -20
    bash --version | head -1
    timeout 60 bash update_all.sh --yes --dry-run >/dev/null 2>&1; echo "exit=$?"

REQUIRED: SYNTAX_OK; both tee tests pass; dry-run exit is 0 and NOT 124.
State which bash version you ran the dry-run on. If it is not 3.2, say so.

================================================================================
TASK A1 — Claude Code CLI moves to the native updater (`claude update`)
================================================================================

CURRENT STATE

config/npm_global_clis.txt:5
    claude-code|@anthropic-ai/claude-code|npm||claude

Method `npm` -> update_npm_cli.sh:754-764 ->
    npm install -g --prefix "$NPM_GLOBAL_PREFIX" @anthropic-ai/claude-code@latest

A `self-update` method already exists (:765-780) and runs
`run_with_timeout 300 "$command_path" update`. Only agy-cli uses it.

FACTS FROM ANTHROPIC'S OFFICIAL DOCS (https://code.claude.com/docs/en/setup,
retrieved 2026-08-12). Treat these as the contract; do not improvise around them.

  * Native install is the recommended method. Launcher: ~/.local/bin/claude.
    Versions: ~/.local/share/claude/versions/.
  * Native installs auto-update in the background. `claude update` forces it now.
  * `claude update` output strings — THIS IS THE PARSING CONTRACT:
      "Successfully updated from <old> to version <new>"  -> updated
      "Claude Code is up to date (<version>)"             -> current, verified
      "Claude is up to date!"                             -> the install is owned
          by Homebrew / WinGet / apk and `claude update` IS A NO-OP. This string
          means "you do not own this install", NOT success.
  * `claude doctor` — read-only diagnostics: install type, health, and the result
    of the most recent update attempt. Does not start a session.
  * `claude install` — migrates an npm install to the native install.
  * `claude --version` prints e.g. `2.1.211 (Claude Code)`.
  * Channels: setting `autoUpdatesChannel` = "latest" (default) or "stable"
    (~one week behind). `minimumVersion` sets a floor.
  * DISABLE_AUTOUPDATER=1 stops only the background check; `claude update` and
    `claude install` still work. DISABLE_UPDATES=1 blocks everything.
  * The npm package installs THE SAME native binary via the optional dependency
    @anthropic-ai/claude-code-darwin-arm64. Upgrade with
    `npm install -g ...@latest`; `npm update -g` is explicitly discouraged.
  * Homebrew: cask `claude-code` tracks STABLE (~1 week behind) and does NOT
    auto-update; `claude-code@latest` tracks latest and also does not auto-update.

SOURCE-PRIORITY DOCTRINE (review section 5.3). For Claude Code the fastest path
to current is the NATIVE installer on the `latest` channel. The `claude-code`
Homebrew cask is a week behind BY DESIGN. Anyone who later "tidies this up" by
moving the CLI to Homebrew is introducing a freshness regression documented by
the vendor. Record this where it will be found again.

--------------------------------------------------------------------------------
A1c — FIX PATH RESOLUTION FIRST. Nothing else in A1 works without this.

Two independent places prefer the npm prefix over the native launcher:

  update_npm_cli.sh:327-331
      npm|pnpm|claude|codex|opencode)
          if [ -x "$NPM_GLOBAL_BIN/$command_name" ]; then      # npm wins

  update_all.sh:1022-1027   (CLI snapshot heredoc)
      roots = [ npm-global/bin, node/bin, ~/.local/bin, ~/.bun/bin ]   # npm wins

The native installer owns ~/.local/bin/claude. While ANY npm remnant exists,
both functions return the npm binary, `claude update` acts on the wrong install,
and the version snapshot reports the wrong number. Do this before A1e or the
task will look done and do nothing.

  * update_npm_cli.sh: move `claude` out of the `npm|pnpm|claude|codex|opencode)`
    branch into its own branch that checks "$LOCAL_BIN/claude" FIRST, then
    "$NPM_GLOBAL_BIN/claude", then falls through to `command -v`.
  * update_all.sh heredoc: make the root order data-driven per command (a dict
    of command -> ordered roots, defaulting to today's order) rather than adding
    another `if`. For `claude`, ~/.local/bin comes first.

--------------------------------------------------------------------------------
A1a — new method name

config/npm_global_clis.txt line 5 becomes:

    claude-code|@anthropic-ai/claude-code|native_self_update|claude-code|claude

Do NOT overload the existing `self-update`. agy has no output contract and a
shared parser would misclassify one of them. A distinct name also satisfies
rule 8 (a method name is valid only when its handler exists).

--------------------------------------------------------------------------------
A1b — detect the install owner BEFORE mutating anything

In order:
  1. `run_with_timeout 60 claude doctor` — if it reports a package-manager-managed
     install, do NOT attempt `claude update`.
  2. If `command -v claude` resolves inside `$(brew --prefix)` -> owner is
     Homebrew -> status MANAGED_BY_BREW, defer to step 3 (update_brew.sh), AND
     warn if the installed cask is `claude-code` (stable), recommending
     `claude-code@latest`. Detect with: brew list --cask | grep -x 'claude-code'
  3. If BOTH "$NPM_GLOBAL_BIN/claude" and "$HOME/.local/bin/claude" exist ->
     dual install -> migrate (A1d).
  4. If ONLY "$NPM_GLOBAL_BIN/claude" exists -> migrate (A1d).
  5. Otherwise -> native -> `claude update` (A1e).

--------------------------------------------------------------------------------
A1d — npm -> native migration: idempotent, reversible, never strands the user

  1. Record the current version: `claude --version`.
  2. `run_with_timeout 300 claude install`.
  3. Verify ~/.local/bin/claude exists and is executable, and that
     `~/.local/bin/claude --version` is >= the recorded version, compared with
     `internet_version_relation`. NEVER accept a lower version.
  4. ONLY THEN `npm uninstall -g @anthropic-ai/claude-code`. No sudo — the docs
     explicitly forbid `sudo npm install -g`.
  5. If ANY step fails: do NOT uninstall the npm copy. SOFT_FAIL=1, honest
     status, move on. A migration that leaves the user without `claude` is worse
     than no migration.

--------------------------------------------------------------------------------
A1e — the native_self_update handler

`run_quiet_with_error_log` cannot be used: it discards stdout, and stdout IS the
contract here. Add a capturing variant (do not modify the existing function,
other callers depend on its behaviour):

    OUT="$(run_with_timeout 300 "$command_path" update 2>&1)"; rc=$?

Classify ONLY on the documented strings, and independently confirm with
`claude --version` before and after. rc=0 alone is not evidence of an update.

  | Observation                                              | Status                     | Severity |
  |----------------------------------------------------------|----------------------------|----------|
  | "Successfully updated from ... to version ..." AND        | UPDATED (verified)         | 0        |
  |   the version actually changed                            |                            |          |
  | "Claude Code is up to date (...)"                         | CURRENT (verified)         | 0        |
  | "Claude is up to date!"                                   | MANAGED_EXTERNALLY         | 10       |
  | DISABLE_UPDATES is set                                    | UPDATES_DISABLED_BY_POLICY | 0        |
  | timeout 124 / rc != 0 / no string matched                 | UPDATE_FAILED              | 10       |
  | post-version < pre-version                                | DOWNGRADE_BLOCKED          | 1        |

DISABLE_UPDATES is severity 0 on purpose: it is a deliberate user policy, not a
warning. Route UPDATE_FAILED diagnostics through the existing
`sanitize_npm_stderr` and append at most 20 lines to
$MAC_UPDATE_SESSION_DIR/npm_cli_errors.log, matching current behaviour.

--------------------------------------------------------------------------------
A1f — channel policy

New variable MAC_UPDATE_CLAUDE_CHANNEL: `latest` (default) | `stable` | `keep`.
For `latest`/`stable`, set `autoUpdatesChannel` in ~/.claude/settings.json
ATOMICALLY: temp file in the SAME directory, mode 0600, os.replace() — reuse the
`atomic_write_text` shape from update_all.sh's postupdate heredoc. Preserve every
other key in that file. NEVER write or overwrite `minimumVersion`. `keep` means
do not touch the file at all. If ~/.claude/settings.json does not exist and the
channel is `latest` (the vendor default), do nothing — do not create a file to
assert a default.

--------------------------------------------------------------------------------
A1g — inventory and i18n

  * APPLICATIONS.md section 4d: the claude-code row's method becomes
    `native (claude update)` instead of `npm`. Change ONLY that row. Do not read
    or quote any other part of the file.
  * New i18n keys in all seven lang files (same names, same order):
      L_NPM_CLAUDE_UPDATED_FMT        (2 placeholders: old, new)
      L_NPM_CLAUDE_CURRENT_FMT        (1 placeholder: version)
      L_NPM_CLAUDE_MANAGED_EXTERNALLY (static, no %s)
      L_NPM_CLAUDE_UPDATES_DISABLED   (static, no %s)
      L_NPM_CLAUDE_MIGRATING          (static)
      L_NPM_CLAUDE_MIGRATION_FAILED   (static)
      L_NPM_CLAUDE_DOWNGRADE_BLOCKED  (2 placeholders)
      L_NPM_CLAUDE_BREW_STABLE_WARN   (static — "Homebrew cask claude-code
                                       tracks the stable channel, roughly a week
                                       behind. Use claude-code@latest.")
    Count: 674 -> 682 in every file.
    test_placeholder_counts_match_english enforces placeholder parity — count
    them per language.

--------------------------------------------------------------------------------
A1h — documentation

docs/agents/critical_rules.md section 5, the "Native/npm/self-updating CLI" row:
split Claude Code onto its own row and add the doctrine from section 5.3 of the
review — native installer on `latest` is rank 1; the `claude-code` cask is
stable and ~a week behind; never move the CLI to Homebrew for freshness. Two or
three sentences. This is knowledge that otherwise evaporates.

--------------------------------------------------------------------------------
A1 TESTS (add to tests/test_safety_static.py)

  1. test_claude_code_uses_native_self_update — config/npm_global_clis.txt row
     for claude-code has method `native_self_update`, and a handler for that
     method name exists in update_npm_cli.sh. (The generic
     test_every_config_method_has_a_handler covers internet apps only; this is
     the CLI manifest's equivalent — write it.)
  2. test_claude_path_resolution_prefers_local_bin — static: in
     update_npm_cli.sh, within the branch that resolves `claude`, the
     "$LOCAL_BIN/" check appears before the "$NPM_GLOBAL_BIN/" check. Same
     assertion for the update_all.sh heredoc roots.
  3. test_claude_update_output_is_classified — feed each of the four documented
     output strings to the classifier and assert the mapped status and severity.
     Stub `claude` as a shell script that echoes the string and exits 0.
     "Claude is up to date!" must NOT map to a success status.
  4. test_claude_migration_never_uninstalls_before_verification — static: in
     update_npm_cli.sh the `npm uninstall -g @anthropic-ai/claude-code` call
     appears AFTER the version-verification block, and is not reachable when
     verification fails.
  5. test_claude_settings_write_is_atomic — the settings.json writer uses
     mkstemp in the same directory plus os.replace, and mode 0600.

ACCEPTANCE CHECK (paste all output verbatim)

    bash -n update_npm_cli.sh update_all.sh && echo SYNTAX_OK
    grep -n "claude" config/npm_global_clis.txt
    grep -n "native_self_update" update_npm_cli.sh | head
    command -v claude; claude --version; claude doctor 2>&1 | head -30
    ls -la ~/.local/bin/claude ~/.local/share/mac-update/npm-global/bin/claude 2>&1
    brew list --cask 2>/dev/null | grep -i claude || echo "no claude cask"

    # Real run of just the CLI step:
    MAC_UPDATE_SESSION_DIR=$(mktemp -d "${TMPDIR:-/tmp}/mac_update_test.XXXXXX") \
      bash update_npm_cli.sh 2>&1 | tail -40; echo "EXIT=$?"

    claude --version
    PYTHONPATH=dev_sync python3 -m unittest tests.test_safety_static -k claude -v 2>&1 | tail -25
    for f in i18n/lang_*.sh; do printf '%s %s\n' "$f" "$(grep -c '^L_[A-Z0-9_]*=' "$f")"; done

REQUIRED: SYNTAX_OK; the run reports one of the six documented statuses (say
which, and paste the raw `claude update` output that produced it); `claude
--version` afterwards is >= before; all five new tests pass; all seven i18n
files report 682.

If `claude` is not installed on the machine you are working on, say so plainly,
run the static and stubbed tests only, and mark the live check as NOT RUN. Do
not fabricate it.

================================================================================
TASK B — remove Ascendo from the inventory, permanently
================================================================================

GOAL (user's words): update_all.sh must not update and must not LAUNCH Ascendo.
It is a user-owned application, updated by hand.

WHY THIS IS NOT A FIVE-LINE DELETION

There is NO ignore mechanism anywhere in the repo. The prescan
(update_all.sh:542-552) does:

    for applications_dir in ('/Applications', os.path.expanduser('~/Applications')):
        for item in os.listdir(applications_dir):
            if item.endswith('.app'): ...

and appends anything missing from GROUPS 1-3 to APPLICATIONS.md.
build_inventory.sh is the same code path. So deleting Ascendo from the config
files stops the updating — and the very next `build_inventory.sh` or full run
puts it straight back into the inventory as a newly discovered app, where it
will show up as `unknown` in the coverage report and invite someone (or some
agent) to "fix" it by adding a handler.

--------------------------------------------------------------------------------
B1 — new artefact config/ignored_apps.txt

    # Applications excluded from macOS Updates management.
    # One bundle name per line (no .app). '#' starts a comment.
    # Excluded from: inventory prescan, internet registry, dispatch,
    # coverage report and version history. Never launched, never updated.
    Ascendo

Loader in lib/internet_apps.sh: `internet_apps_is_ignored <name>` returning 0/1.
Bash 3.2 — read the file into a delimited string once
(IGNORED_CACHE="|Ascendo|Foo|") and test with a `case` glob. Do not re-read the
file per call: the settle loop already demonstrates what that costs
(review section P-3).

--------------------------------------------------------------------------------
B2 — honour it in all five places. Miss one and the app comes back.

  | Location                                          | Change                                            |
  |---------------------------------------------------|---------------------------------------------------|
  | lib/internet_apps.sh internet_apps_load_config    | skip ignored when building INTERNET_APPS_LIST[]   |
  | lib/internet_registry.sh internet_registry_load   | skip rows for ignored apps                         |
  | update_all.sh prescan (:542-552)                  | filter from installed_apps AND from the write of   |
  |                                                   | installed_apps_after.txt at :580 — postupdate      |
  |                                                   | reads that file (:1377) and would re-add them      |
  | update_all.sh postupdate (heredoc from :1262)     | same filter when inserting GROUP 3 rows            |
  | scripts/report_update_coverage.sh                 | skip — otherwise they appear as `unknown` and      |
  |                                                   | drag the coverage metric down                      |

--------------------------------------------------------------------------------
B3 — the Ascendo-specific cleanup (exact locations, verified)

  config/internet_apps.txt:17          delete the line `Ascendo`
  config/internet_app_methods.txt:22   delete `Ascendo|silent_launch|STATUS_ASCENDO`
  config/internet_dispatch_order.txt:28  replace `iu_ascendo` with
        `# Ascendo — user-managed (config/ignored_apps.txt)`
  lib/internet_app_updates.sh:1453-1455  delete function iu_ascendo
  update_internet_apps.sh:431          delete STATUS_ASCENDO=...
  update_internet_apps.sh:639          delete the printf row "Ascendo:"
  update_internet_apps.sh:680          delete "$STATUS_ASCENDO" from the exit loop
  update_internet_apps.sh:20           remove "Ascendo" from the DEV TOOLS header comment
  scripts/audit_cask_candidates.sh:36  delete the "Ascendo") echo "ascendo" mapping
  docs/agents/critical_rules.md:105    remove "Ascendo" from the silent-launch list
  APPLICATIONS.md:138                  delete the row `| Ascendo | 0.2.0 | https://ascendo.dev |`
  APPLICATIONS.md:141                  "Ascendo i Cursor aktualizują się..." ->
                                       "Cursor aktualizuje się..."
  APPLICATIONS.md:463                  remove "Ascendo" from the auto-updated list

  Touch NO other line of APPLICATIONS.md.

CONSISTENCY WARNING: test_internet_config_status_var_parity (tests:812) checks
five invariants at once — identical app lists across the two config files, every
STATUS_* initialised, present in the summary table AND in the exit loop, and no
orphans. Removing Ascendo from four of the five places WILL fail that test. That
is the test working correctly. Do all five in one commit.

--------------------------------------------------------------------------------
B4 — regression test (without this the task is not finished)

test_ignored_apps_are_never_dispatched_or_inventoried:
  1. For every name in config/ignored_apps.txt: absent from internet_apps.txt,
     absent from internet_app_methods.txt, no uncommented iu_* entry in
     internet_dispatch_order.txt.
  2. Simulate the prescan against a fixture directory containing `Ascendo.app`
     and assert the name does NOT appear in the output list.
  3. grep -c "Ascendo" update_internet_apps.sh lib/internet_app_updates.sh -> 0.

ACCEPTANCE CHECK (paste all output verbatim)

    bash -n update_internet_apps.sh lib/internet_apps.sh lib/internet_registry.sh \
            lib/internet_app_updates.sh update_all.sh && echo SYNTAX_OK
    cat config/ignored_apps.txt
    grep -rn -i "ascendo" config/ lib/ update_internet_apps.sh update_all.sh scripts/ \
        | grep -v "ignored_apps.txt" | grep -v "^config/internet_dispatch_order.txt.*#"
    wc -l < config/internet_apps.txt
    grep -c "|" config/internet_app_methods.txt
    PYTHONPATH=dev_sync python3 -m unittest tests.test_safety_static -k ignored -v 2>&1 | tail -20
    PYTHONPATH=dev_sync python3 -m unittest tests.test_safety_static -k parity -v 2>&1 | tail -20
    bash scripts/report_update_coverage.sh 2>&1 | tail -25

REQUIRED: SYNTAX_OK; the grep returns nothing except the commented dispatch line;
the parity test passes; the coverage report no longer lists Ascendo and its total
app count dropped by exactly one.

================================================================================
FINAL DELIVERABLE — append to IMPLEMENTATION_NOTES.md
================================================================================

A section headed `## v1.4.0 — Opus5 Max Ultra Review v6 implementation`
containing:

  1. A table: Task (A3, A4, A5, A6, A1, B) | Status | Commit SHA | Notes
  2. VERBATIM acceptance-check output for every task. Not summarised.
  3. Full `bash run_tests.sh` output (all four sections).
  4. `bash --version | head -1` — and state whether that is the shell your users
     run. If you verified anything shell-version-dependent (A6) on a different
     version than the one where it manifests, say so explicitly.
  5. `for f in i18n/lang_*.sh; do grep -c '^L_[A-Z0-9_]*=' "$f"; done`
     — expect seven identical counts of 682.
  6. `timeout 120 bash update_all.sh --yes --dry-run; echo "exit=$?"`
     — expect a prompt return, exit 0, never 124.
  7. `bash scripts/report_update_coverage.sh | tail -25` before and after.
  8. Explicit answers to these three questions:
       - Was `brew list --pinned` empty (A4 latent) or non-empty (A4 active)?
       - What did `claude doctor` report as the install type before A1?
       - Which of the six documented statuses did the real `claude update` return?
  9. Any `## PROPOSED - <title>` items you chose not to implement.

Then bump VERSION to 1.4.0 and add a CHANGELOG.md entry.

Do NOT modify any file in docs/reviews/ other than appending to
IMPLEMENTATION_NOTES.md.

================================================================================
```

---

## Notes for the human reviewer (not part of the Gemini prompt)

- Run the three verification commands in §11 of the review **before** handing this to Gemini. If `brew list --pinned` is non-empty, A4 is your most urgent item and you can move it ahead of A3.
- The i18n key count walks 671 → 673 (A3) → 674 (A4) → 682 (A1). If Gemini reports a different number at any checkpoint, a key was added to fewer than seven files.
- `test_internet_config_status_var_parity` failing mid-task-B is expected and correct. It should be green again at the end of B3.
- Blocks 3–5 of the review (source-lag ledger, parallel feed probing, `lib/python/` + inventory fixture) are deliberately excluded. They need the fixture that nobody has built yet, and mixing them into this round would make the acceptance output unreadable.
