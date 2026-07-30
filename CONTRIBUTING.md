# Contributing

Thank you for contributing to **macOS Updates** (v1.0.20).

## Requirements

- **Apple Silicon (arm64) Mac running macOS 13+** — Intel and older macOS releases are not supported
- **Bash 3.2+** — macOS default shell; no `declare -A`, `mapfile`, or `readarray` in project scripts
- **Python 3.11+** for `dev_sync/` and inline heredocs in `update_all.sh`

## Before you submit

```bash
bash run_tests.sh          # bash -n, py_compile, unit/static tests, gitleaks
shellcheck --severity=warning $(find . -name '*.sh' ! -path './.git/*' -print)  # uses .shellcheckrc
```

## Adding an internet app

1. Add the app name to `config/internet_apps.txt`
2. Add method row to `config/internet_app_methods.txt`
3. `bash scripts/scaffold_internet_app.sh "App Name" silent_launch`
4. Implement handler in `lib/internet_app_updates.sh`; add to `config/internet_dispatch_order.txt`
5. Mirror `L_INTERNET_*` keys in all 7 `i18n/lang_*.sh` files
6. `bash run_tests.sh` — config↔handler tests must pass

## Non-negotiable rules

1. `softwareupdate` install paths **must** include `-R`
2. `mas upgrade` **must** use `sudo` (macOS 15.7.2+/14.8.2+/26.1+ entitlement change, see https://github.com/orgs/Homebrew/discussions/6550)
3. All `update_*.sh` orchestrators **must** use `set -o pipefail`
4. **No new standalone pipeline entrypoints** — update pipeline Python stays in heredocs or importable pure-function modules under `lib/python/` (which `run_tests.sh` compiles and tests)
5. Use `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"` — no hardcoded user paths
6. Temp files: `mktemp` with `${TMPDIR:-/tmp}/mac_update_*` prefix
7. **Do not install apps for users** — handlers run only when the app is already installed

## i18n

- **English (`lang_en.sh`)** is the source of truth for new keys
- Translate to PL, DE, FR, ES, IT, PT with identical key names

## Pull requests

- One logical change per PR when possible
- Describe test evidence (`run_tests.sh` output)
- Do not include private files (`APPLICATIONS.md`, `.env`, `.dev_sync_config.json`, etc.)

## Documentation

When changing behavior, update `README.md`, relevant `docs/` files, and `VERSION` if releasing.
