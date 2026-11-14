# Terminal workspace 1.8.0

## Intent

The owner requested implementation and publication of a mature terminal application, including a first-run wizard, persistent settings, help, keyboard shortcuts and a three-column interface. The visual direction is Warp-inspired command blocks, with a left navigation rail and right contextual details. These are product requirements; implementation choices below are the builder's decisions.

## Approach

Use Python 3.9+ standard-library curses, backed by the existing Bash/Python engine through a supervised controlling PTY. Textual offers ready-made widgets but introduces a new dependency/bootstrap lifecycle on new Macs. A web dashboard would add a service and browser workflow contrary to the terminal request. Curses keeps the existing Python dependency floor and allows full-screen panels, keyboard interaction, resize and deterministic model tests.

The interface observes and controls the existing engine. It never interprets an initial launch confirmation as per-app consent, invents updater completion, installs catalog apps automatically, or clears unresolved execution leases. Public mutations remain serialized until existing parallel-safety evidence allows overlap. Read-only UI rendering and log updates remain responsive during work.

## Screens

- Left rail: overview, updates, inventory, catalog/sources, diagnostics, history, settings, setup wizard, help.
- Center: task cards, selected group toggles, action menu, current task progress, scrollable bounded live output. Percentages come from engine observations; unknown durations stay unknown.
- Right rail: focused action explanation, selected scope, running process state, safety/consent information and context shortcuts.
- Footer: keyboard legend, current state and explicit input affordance. Command palette provides action search without arbitrary shell execution.
- Narrow terminals hide the right rail while keeping the focused action and help accessible; very small terminals show a resize message with safe exit. ASCII and light/dark display settings are available.

## Wizard and persistence

First interactive launch shows a guided sequence: welcome/language, prerequisites inspection, local inventory, source/conflict review, preferences/groups, preview, finish. Finishing persists wizard_complete; subsequent starts open the dashboard. Menu can rerun the wizard without erasing policies. UI preferences are private, schema-validated and atomically written; storing them grants no update permission. Missing prerequisites are explained and installation remains an explicit action with the existing setup confirmations.

## Execution boundaries

A fixed whitelist maps UI actions to repository scripts and validated skip flags. One active child owns its PTY. Explicit terminal answers are forwarded only when the user submits the input dialog. Secret-input mode follows terminal ECHO state and never logs or persists submitted input. No guessed yes/no, no arbitrary command strings, no shell eval. Commands launched from the UI disable recursive UI entry. Existing noninteractive and explicit CLI flags keep script compatibility.

Update, setup and inventory scripts enter the UI only for a bare interactive invocation or explicit --tui. --cli forces legacy text mode. The policy editor receives a dedicated preferences-only path that cannot run updates. Group selection constrains command flags; individual scope approval remains the existing engine's authoritative review. Cancellation never grants permissions or clears recovery state, and active mutation interruption requires a warning and explicit choice.

## Help and internationalization

Every label, tooltip, wizard step, input instruction, error state and help section supports all seven existing languages. Brands and literal command flags are invariant. Help covers first use, groups, consent, preview, live logs, progress, saved settings, troubleshooting, source conflicts, blocked recipes, interruption and shortcuts. Context descriptions explain effects before launch.

## Verification and limits

Use isolated fixture commands and host/network guards for backend, PTY input, terminal restoration, settings permissions, malformed data, resize, navigation and operation scope. Exercise the actual full-screen interface in a PTY and visually inspect a representative render. Do not equate terminal tests with live acceptance of application recipes. Final gates: full guarded suite, shell/Python checks, secret scan, landing lint/build, CI and deployed-site parity. No claim of perfection or accepted live recipes follows from these gates.

## Window and input behavior

The default auto-resize setting requests at least 140 by 38 through supported xterm window operations, then requests the original dimensions on exit. Multiplexers and unsupported terminals are not resized. Rendering remains responsive without that facility; below 80 by 24 operation shortcuts are disabled.

Tab into output expands the center log. Wrapped output and the answer editor preserve question context and displayed scopes, with page scrolling. Bracketed paste is treated as data, never a sequence of action shortcuts. Clipboard operations require explicit keys. If rendering fails during a job, curses restores the terminal before handing the same worker to text interaction, without restarting it or inventing consent.
