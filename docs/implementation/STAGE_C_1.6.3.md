# Stage C implementation, 1.6.3

Local source checkpoint dated 2026-11-13. Tasks T06-T09 activate the common model.

The master builds one local plan, obtains explicit scoped decisions, and sends the immutable plan to every app leaf. Read-only previews precede logs, locks, inventory and sudo. Standalone leaves cannot fall back to broad legacy updates. Normal unknown apps remain manual; conflict and partial evidence cannot grant mutation. Existing Markdown requires explicit migration preview and acceptance; original bytes and notes survive rollback and restart.

Direct-download transport and same-volume transactions validate identity, source, signatures and destination, preserve backups and recover incomplete journals before a new scan. Public reviewed-direct recipes remain empty. Homebrew opaque/dependency effects and npm scripts, dependencies or global command changes require further review; normal updates never bootstrap them. Common coverage and capability proposal code was prepared in parallel with D.

An independent C/D review found three scope gaps and a transport deadline gap. Related cask identities and source fingerprints are now checked, cask dependencies are deferred, npm metadata effects are bounded with scripts/bin links disabled for the narrow eligible path, and downloads use single-read streaming plus a connection deadline. Additional parent checks preserve the exact cask app directory and reject truncated responses. Targeted regressions cover each finding and positive fixture execution.

Verification: the sealed stage-C full runner passed 1101 cases (1100 passed, one explicitly skipped), with zero unexpected host-command or network guard hits. Shell syntax, Python compilation and tracked secret scanning passed. Warning-level ShellCheck passed for all tracked shell files. Python 3.9.6 passed 188 selected inventory, policy, plan, download and transaction cases; the full suite used Python 3.15.2. No real updates, installs, host migrations, network probes, publication or landing edits were used as tests.
