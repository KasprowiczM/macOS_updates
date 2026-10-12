# Security Policy

## Supported versions

Only the latest release line receives security fixes.

| Version | Supported |
|---------|-----------|
| 1.5.x   | Yes |
| < 1.5   | No — update to the latest 1.5.x |

The toolkit supports Apple Silicon Macs running macOS 13 to 27 only; issues that exist solely on unsupported platforms are out of scope.

## Reporting a vulnerability

Please report security issues **privately**; do not open a public issue or pull request with exploit details.

1. Open the repository's **Security** tab on GitHub: <https://github.com/KasprowiczM/macOS_updates/security>.
2. Choose **Report a vulnerability** to create a private security advisory.
3. If that option is not available, open a public issue that only asks for a private contact channel and contains no technical details.

Include the affected version (`VERSION`), macOS version, a minimal reproduction and the impact you expect. You will get an acknowledgement as soon as the maintainer can review it; this is a single-maintainer project, so response times are best effort.

## Scope

In scope (code and configuration in this repository):

- Privilege handling: `sudo` use, `softwareupdate`/`mas` invocation, the Touch ID PAM helper (`scripts/setup_touchid_sudo.sh`) and the LaunchAgent installer
- Download and install verification for vendor artifacts (HTTPS-only fetch, signature, Team ID and Gatekeeper checks, staged swap with rollback)
- Unsafe temporary files, predictable paths, symlink or path-traversal handling (including the `dev_sync` private-overlay import)
- Leakage of secrets or private inventory into tracked files, logs or run summaries

Out of scope:

- Vulnerabilities in third-party software the toolkit updates (macOS, Homebrew, vendor applications and their own updaters) — report those upstream
- Findings that require an already-compromised account or physical access to an unlocked Mac
- Denial of service through deliberately malformed vendor feeds that only produce a warning

## Handling secrets

Never commit tokens, `.env`, `.dev_sync_config.json`, `APPLICATIONS.md` or `UPDATES.md`; they are gitignored and travel only through the optional private overlay. `bash run_tests.sh` and CI run a gitleaks scan (see [docs/agents/security.md](docs/agents/security.md)). If you find a secret in the repository history, report it as described above so it can be rotated.
