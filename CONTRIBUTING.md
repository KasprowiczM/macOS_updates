# Contributing

Thank you for contributing to **macOS Updates** (v1.5.5, MIT license). Project site: <https://macosupdates.dev>. Security issues: see [SECURITY.md](SECURITY.md) (do not open a public issue).

## Requirements

- **Apple Silicon (arm64) Mac running macOS 13 to 27** — Intel and older macOS releases are not supported
- **Bash 3.2+** — macOS default shell; no `declare -A`, `mapfile`, or `readarray` in project scripts
- **Python 3.11+** for `dev_sync/`, the importable modules under `lib/python/` and inline heredocs in `update_all.sh`

## Before you submit

```bash
bash scripts/pre-commit.sh # staged bash -n + py_compile
bash run_tests.sh          # bash -n, py_compile, unit/static tests, doc guards, gitleaks
shellcheck --severity=warning $(find . -name '*.sh' ! -path './.git/*' -print)  # uses .shellcheckrc
```

`bash run_tests.sh` takes about two minutes and prints the final test count; include that line in your PR. The suite contains documentation guards (for example every `lib/*.sh` and `lib/python/*.py` file must be listed in `docs/agents/scripts.md`, and the living docs must mention the current `VERSION`).

## Adding an internet app

The authoritative step list is in [docs/agents/scripts.md](docs/agents/scripts.md#adding-a-new-internet-app). In short:

1. Add the app name to `config/internet_apps.txt` and a method row to `config/internet_app_methods.txt` (`AppName|method|STATUS_VAR`).
2. `bash scripts/scaffold_internet_app.sh "App Name" silent_launch` generates boilerplate.
3. Implement `iu_<slug>()` in `lib/internet_app_updates.sh`; append it to `config/internet_dispatch_order.txt`.
4. Add `L_INTERNET_*` keys to all 7 `i18n/lang_*.sh` files (English first).
5. `bash run_tests.sh` — the config to handler parity tests must pass.

## Non-negotiable rules

The full list is in [AGENTS.md](AGENTS.md). Highlights:

1. `softwareupdate` install paths **must** include `-R`.
2. `mas upgrade` **must** use `sudo` and explicit app IDs (macOS 15.7.2+/14.8.2+/26.1+ entitlement change, see <https://github.com/orgs/Homebrew/discussions/6550>).
3. All `update_*.sh` orchestrators **must** use `set -o pipefail` and **must not** use `set -e`.
4. **No new standalone pipeline entrypoints** — update-pipeline Python stays in heredocs or importable pure-function modules under `lib/python/` (which `run_tests.sh` compiles and tests).
5. Use `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"` — no hardcoded user paths.
6. Temp files: `mktemp` with a `${TMPDIR:-/tmp}/mac_update_*` prefix.
7. **Do not install apps for users** — handlers run only when the app is already installed.

## i18n

- **English (`i18n/lang_en.sh`)** is the source of truth for new keys.
- Translate to PL, ES, FR, DE, IT and PT with identical key names. User-facing claims and numbers in `README.md` must match in all seven `README.*.md` files.

## Documentation

When behavior changes, update in the same pull request:

- `README.md` and the six translations (`README.pl/es/fr/de/it/pt.md`), including flag and environment-variable tables (`lib/cli.sh` is the authoritative flag list)
- `docs/agents/*` (script reference, exit codes, critical rules), `docs/user/*` and `docs/INSTALL.md` where relevant
- `CHANGELOG.md`, and `VERSION` when releasing

Documentation hygiene:

- Counts (tests, apps, update methods) must come from commands, not memory: `bash run_tests.sh`, `grep -vcE '^\s*(#|$)' config/internet_apps.txt`.
- `docs/reviews/` is an index plus an archive of development records; add new records to its [README](docs/reviews/README.md) and move superseded ones to `docs/reviews/archive/` with `git mv`.
- No absolute home-directory paths, account names, e-mail addresses, hostnames or machine inventory in tracked files.

## Pull requests

- One logical change per PR when possible.
- Describe test evidence (`run_tests.sh` output).
- Do not include private files (`APPLICATIONS.md`, `UPDATES.md`, `.env`, `.dev_sync_config.json`, `logs/`, etc.); they are gitignored by design.
- CI cost: this repository has a hard monthly GitHub Actions allowance. Do not add scheduled workflows or macOS runners to push/PR triggers without maintainer approval.
