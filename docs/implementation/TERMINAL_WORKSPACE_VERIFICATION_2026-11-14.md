# Terminal workspace source 1.8.0 verification

Date: 2026-11-14. This receipt describes local verification, not live application acceptance.

- Final `bash run_tests.sh`: 1441 cases passed, zero skips, 280.859 seconds. Bash syntax, Python compilation including inline blocks, secret checks and host/network guards passed.
- Python 3.9.6 compatibility: 34 TUI backend/entry/i18n/recovery tests and 36 terminal model/window/integration/PTY tests passed under the guarded runner.
- Real curses PTY fixtures exercised the wizard, help, resize, preview output, explicitly submitted answers and restoration of terminal modes. They ran synthetic scripts only.
- Deterministic layouts covered seven languages and multiple terminal sizes. A representative synthetic render was visually inspected. Native terminal window resizing is best effort and still depends on each terminal's support; the emitted request and restoration were tested, not universal emulator behavior.
- Recovery tests retained the existing child after a UI failure, restored foreground interaction and preserved secret input. Phase completion and exit code are not proof of an application update.

Integration found and fixed hidden question context, clipped long scopes, missing-helper argument loss, EOF consent behavior and partial Homebrew formula evidence. The initial full gate failed while new modules were absent from tracked-only fixture copies; the final gate included those modules. A power-dependent legacy fixture was isolated with explicit power, disk, network and sleep-prevention mocks rather than weakening its assertions.

No real application installation, update, launch, quit or system restart was performed for this verification. Public mutation remains serial; live T6 and recipe activation remain deferred. The interface cannot grant acceptance to catalog recipes or clear unresolved recovery leases.
