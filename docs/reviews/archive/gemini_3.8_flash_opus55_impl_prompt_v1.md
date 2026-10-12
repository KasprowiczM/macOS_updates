# Prompt wykonawczy dla Gemini 3.8 Flash — macOS Updates v1.4.6 → v1.5.0: „prawda od producenta”, tylko zainstalowane, inwentarz bez dryfu

> **Źródło ustaleń:** `docs/reviews/archive/opus_5.5_ultra_review_v1.md` (2026-09-23).
> **Jak użyć:** wklej całość od linii „---” poniżej jako pierwszą wiadomość do Gemini 3.8 Flash, uruchomionego w
> `~/Dev_Env/macOS_updates`. Prompt jest samowystarczalny. Review czytaj tylko, gdy potrzebujesz dowodu.
> **Po zakończeniu** Gemini zostawia raport `docs/reviews/archive/IMPLEMENTATION_REPORT_opus55_v1.md`, który zweryfikuje Opus.

---

Jesteś starszym inżynierem shell/Python/macOS. Pracujesz w repozytorium `~/Dev_Env/macOS_updates` (toolkit
aktualizacji macOS: Bash **3.2**, Python 3, tylko Apple Silicon, macOS 13–27, 7 języków i18n). Maszyna: macOS 27.0
(26A428), Homebrew 7.0.6, mas 7.0.0, Xcode 27. Punkt wyjścia: `main` = `0a613d0` (v1.4.6), `bash run_tests.sh` = **326 testów OK**.

Twoje zadanie: **wdrożyć dokładnie zadania T0–T15** poniżej, w tej kolejności, każde jako osobny commit, z testami.
Nie improwizuj architektury. Gdy specyfikacja mówi „dokładnie”, zrób dokładnie tak. Gdy coś jest niejasne, wybierz
**bezpieczniejszy** wariant (mniej mutacji, mniej uprawnień) i zapisz decyzję w raporcie w sekcji „Odchylenia”.

Przed pierwszą zmianą przeczytaj: `CLAUDE.md`, `AGENTS.md`, `docs/agents/critical_rules.md`,
`docs/agents/architecture.md`, `docs/agents/exit_codes.md`, a w review: `docs/reviews/archive/opus_5.5_ultra_review_v1.md` §3 i §5.

## 0. Zakres — decyzje już podjęte (nie zmieniaj ich)

| # | Decyzja |
|---|---|
| D1 | **Harmonogram jest POZA zakresem.** Nie dotykaj `scripts/install_launchagent.sh`, `tests/test_launchagent.py`, `~/Library/LaunchAgents`, `launchctl`, `sfltool`. Nie dodawaj trybu `--background`, watcherów ani `StartCalendarInterval`. |
| D2 | **Zasada „tylko zainstalowane”**: `update_all.sh` i skrypty potomne aktualizują wyłącznie to, co jest na Macu. Instalowanie brakujących CLI tylko z nową flagą `--bootstrap-cli` (`MAC_UPDATE_BOOTSTRAP_CLI=1`). |
| D3 | **Bez pliku tombstone'ów.** Odinstalowanie obsługują: D2 + wykrywanie osieroconych casków (T9) + synchronizacja inwentarza we wszystkich grupach (T11). |
| D4 | **Bez `sparkle` CLI** (Sparkle 2.10.0 nie dystrybuuje go jako binarki). Aplikacje Sparkle obsługuje ścieżka „feed producenta → updater aplikacji → zweryfikowane pobranie od producenta” (T4). |
| D5 | **Prawdą o wersji jest feed producenta** (`config/vendor_feeds.txt`, T1/T4) albo odpowiedź Omaha updatera Google/Comet (T5). Cask Homebrew jest tylko drugim głosem: może potwierdzić „w tyle”; „aktualne” wyłącznie przy **równości** i tylko dla aplikacji bez feedu producenta (kod `current_cask_only`). |
| D6 | **Najpierw sprawdź, potem działaj**: nie uruchamiaj aplikacji, VM ani updatera, jeśli feed mówi „aktualna”. |
| D7 | **Nigdy nie zamykaj aplikacji uruchomionej przez użytkownika** i nigdy jej nie podmieniaj. Zamykasz wyłącznie to, co sam uruchomiłeś; zawsze łagodnie (`quit`), nigdy `kill`. |
| D8 | Nazwy metod w `config/internet_app_methods.txt` zostają, poza trzema zmianami: `Gemini → keystone`, `Comet → chromium_updater` (nowa), `Remote Desktop Manager → silent_launch`. `IPMIView` zostaje `manual`, ale runtime rozpoznaje aplikacje App Store (T7). |
| D9 | Stany mają kody (enum, T8). Napisy i18n służą tylko do wyświetlania. Liczniki i severity liczone z kodów. |
| D10 | Poza zakresem: tabela modeli w `CLAUDE.md`, `dev_sync/`, parsowanie Track 1 (`mas upgrade`), `uv tool`/`pipx`, workflowy GitHub Actions. |

## 1. Ograniczenia nienegocjowalne

1. **Bash 3.2**: zakaz `declare -A`, `mapfile`, `readarray`, `${var,,}`, `${var^^}`, `&>>`, `|&`, `local -n`. Tablice indeksowane są dozwolone. `bash -n` po każdym pliku.
2. Każdy `update_*.sh` ma `set -o pipefail` i **nie ma** `set -e` ani `set -u`.
3. `softwareupdate` do instalacji **zawsze z `-R`**, per etykieta, nigdy `-ia`. `mas upgrade` zawsze `sudo` + jawne ID (nie zmieniasz Track 1).
4. Każde zapytanie Homebrew przez `lib/brew.sh`. Nigdy `brew list --cask --versions` bezpośrednio, nigdy `brew outdated … 2>&1`.
5. **Measured, not claimed**: sukces raportujesz tylko po ponownym odczycie żywego systemu (wersja bundla, `--version`, listing).
6. Python w pipeline: tylko **importowalne moduły** w `lib/python/` (czyste funkcje, testowalne) wołane z heredoców Bash. Żadnych nowych samodzielnych entrypointów Python.
7. Pobrania: tylko `https://`, host z allowlisty (T4), weryfikacja sumy (gdy producent ją publikuje), potem istniejące `copy_verified_app` (spctl + bundle id + Team ID + staged swap + rollback). Zakaz `curl | sh`.
8. Handlery raportują przez `INTERNET_LAST_STATUS` (globalna), **nigdy** przez stdout.
9. Nowy tekst UI = klucz w **wszystkich 7** plikach `i18n/lang_*.sh` (parytet kluczy jest testowany). Teksty EN i PL są w Dodatku C. DE/ES/FR/IT/PT przetłumacz poprawnie, nie kopiuj angielskiego.
10. Testy działają na atrapach (`PATH` ze stubami, tymczasowy `HOME`, fikstury w `tests/fixtures/`). **Żadnej sieci w testach.** Testy wymagające narzędzi macOS (`plutil`, `defaults`, `codesign`, `osascript`) oznacz `@unittest.skipUnless(sys.platform == "darwin", "macOS only")`, bo CI uruchamia unittest także na Ubuntu. Czyste moduły Python testuj bez tego warunku.
11. Nie czytaj i nie modyfikuj w testach prawdziwego `APPLICATIONS.md`/`UPDATES.md`. Fikstury inwentarza są syntetyczne.
12. `bash run_tests.sh` zielony po **każdym** zadaniu. Na końcu ShellCheck jak w CI:
    `find . -type f -name '*.sh' ! -path './.git/*' ! -path './graphify-out/*' ! -path './dev_sync_logs/*' -print0 | xargs -0 shellcheck --severity=warning`: zero znalezisk.
13. Nie zmieniaj istniejących testów tylko po to, żeby przeszły. Wyjątek: test, który **koduje starą, błędną regułę** wymienioną w tym prompcie (np. „cask potwierdza aktualność”). Wtedy zmień go, dopisz komentarz `# Changed in v1.5.0: <reguła>` i wymień w raporcie.
14. Po każdym zadaniu commit na gałęzi `feat/vendor-truth-v1.5`. Wiadomość `feat|fix|docs(<obszar>): <opis> (T<n>)` + stopka `Co-Authored-By` z modelu. **Bez push, bez tagu, bez merge.**

**Zakazane komendy** (także „na próbę”): `bash update_all.sh` bez `--dry-run`, `update_internet_apps.sh`,
`update_brew.sh`, `update_appstore.sh`, `update_npm_cli.sh` bez `MAC_UPDATE_DRY_RUN=1`, `brew upgrade|install|uninstall`,
`mas upgrade`, `softwareupdate -i`, `sudo …`, `docker desktop update|start|stop`, `open -a`, `osascript … quit`,
`codex update`, `claude update`, `agent update`, `agy update`, `rm -rf` poza katalogami tymczasowymi testów i `scratch/`.
**Dozwolone odczyty na żywo:** `curl -fsS` feedów producentów, `brew info --json=v2`, `brew list`, `mas list --json`,
`mas outdated --json`, `mas config --json`, `defaults read`, `plutil -extract`, `codesign -dv`, `ls`, `du`,
`bash update_all.sh --dry-run`, `bash build_inventory.sh` (tylko z kopią zapasową, T11), `bash scripts/report_update_coverage.sh`,
`bash scripts/check_vendor_feeds.sh` (T14).

## 2. Metoda pracy (każde zadanie)

1. Napisz test, który **pada na obecnym kodzie** (uruchom i zobacz porażkę).
2. Zaimplementuj minimalną zmianę zgodną ze specyfikacją.
3. `bash run_tests.sh` → zielony. `bash -n` na zmienionych `.sh`. ShellCheck na zmienionych `.sh`.
4. Commit.
5. W raporcie (Dodatek D) wpisz: pliki, nazwy nowych testów, liczbę testów po zadaniu, odchylenia.

---

## T0 — Przygotowanie (bez zmian logiki)

- `git switch -c feat/vendor-truth-v1.5` z `main`. Nie commituj plików `docs/reviews/*` nieśledzonych przez git.
- Kopia zapasowa prywatnych plików: `mkdir -p scratch/backup_T0 && cp -p APPLICATIONS.md UPDATES.md scratch/backup_T0/` (`scratch/` jest w `.gitignore`).
- `bash run_tests.sh` i zapisz liczbę testów (oczekiwane 326) w raporcie.
- Utwórz szkielet raportu `docs/reviews/archive/IMPLEMENTATION_REPORT_opus55_v1.md` według Dodatku D.

## T1 — Fundament: moduł feedów producenta i porównanie trójstronne

**Nowe pliki:** `lib/python/vendor_feeds.py`, `lib/vendor_feeds.sh`, `config/vendor_feeds.txt`, `tests/test_vendor_feeds.py`,
`tests/fixtures/vendor_feeds/*`. **Zmiana:** `lib/version.sh` (nowa funkcja, stare bez zmian).

### 1.1 `lib/python/vendor_feeds.py` (czyste funkcje, tylko stdlib)

```python
SPARKLE_NS = "http://www.andymatuschak.org/xml-namespaces/sparkle"

def normalize_vendor_version(value: str) -> str:
    """Strip whitespace; drop leading 'v'/'V'; drop cask build suffix after the first ','
    ('2.7032.0,6c46…' -> '2.7032.0'); drop a trailing parenthesised build ('7.2.1 (88329)' -> '7.2.1');
    replace a trailing '.(stable|beta|dev|canary|preview)_<digits>' by '.<digits>'
    ('v0.2026.09.16.08.27.stable_02' -> '0.2026.09.16.08.27.02'). Empty/None -> ''."""

def version_key(value: str) -> tuple | None:
    """Same algorithm as internet_version_relation() in lib/version.sh (12 numeric segments, prerelease rank
    dev<alpha<beta<rc<final, 4 suffix numbers), applied AFTER normalize_vendor_version. None if no digits."""

def version_compare(a: str, b: str) -> int | None:
    """-1 if a<b, 0 if equal keys, 1 if a>b, None if either is unparseable."""

def parse_sparkle_appcast(xml_text: str, os_version: str | None = None,
                          channels: set[str] | None = None) -> dict | None:
    """Parse with xml.etree.ElementTree. For every <item>:
       channel = text of <sparkle:channel> (None if absent). Allowed channels: {None} ∪ (channels or {'stable'}).
       min_os  = <sparkle:minimumSystemVersion> text or enclosure attribute sparkle:minimumSystemVersion;
                 skip the item if os_version is given and version_compare(min_os, os_version) == 1.
       short   = <sparkle:shortVersionString> text or enclosure attr sparkle:shortVersionString.
       build   = <sparkle:version> text or enclosure attr sparkle:version.
       url     = enclosure attr url.
       version = short or build.
     Return the item with the MAXIMUM version_key (never the first one) as
       {'version': version, 'build': build, 'url': url, 'checksum_kind': None, 'checksum': None}.
     Return None on ParseError or when no item qualifies."""

# Named JSON/text selectors. Each returns {'version','url','checksum_kind','checksum'} or None.
def select_claude_releases(obj: dict) -> dict | None      # version=obj['currentRelease']; url=releases[i]['updateTo']['url'] where releases[i]['version']==currentRelease
def select_cursor_update(obj: dict) -> dict | None        # version=obj['name']; url=obj['url']
def select_warp_channels(obj: dict) -> dict | None        # version=normalize(obj['stable']['version']); url=None
def select_antigravity_ide(obj: dict) -> dict | None      # url=obj['url']; version=re.search(r'/stable/(\d+(?:\.\d+)+)-', url)[1]; checksum_kind='sha256hex', checksum=obj.get('sha256hash')
def select_tauri_latest(obj: dict, platform: str = "darwin-aarch64") -> dict | None  # version=obj['version']; url=obj['platforms'][platform]['url']
def select_proton_releases(obj: dict) -> dict | None      # among obj['Releases'] with CategoryName=='Stable' take max Version; url = File with Identifier=='Apple Disk Image' -> 'Url'; checksum_kind='sha512hex', checksum='Sha512CheckSum'
def parse_electron_yml(text: str) -> dict | None          # no PyYAML: top-level 'version: X'; under 'files:' pairs '- url: U' + 'sha512: S'; pick first url ending '.zip' (else first); checksum_kind='sha512b64'
def parse_devolutions_productinfo(text: str, prefix: str) -> dict | None  # lines '<prefix>.Version=', '<prefix>.Url=', '<prefix>.hash=' ; checksum_kind='sha256hex'

JSON_SELECTORS = {"claude_releases": ..., "cursor_update": ..., "warp_channels": ...,
                  "antigravity_ide": ..., "tauri_latest": ..., "proton_releases": ...}

def evaluate_feed(kind: str, body: str, arg: str, os_version: str | None = None) -> dict | None:
    """kind: 'sparkle' (arg = comma channels or '-'), 'json' (arg = selector name), 'yml' (arg '-'),
    'kv' (arg = productinfo prefix). Never raises: any exception -> None.
    Post-process: result['version'] = normalize_vendor_version(result['version']);
    result['url'] spaces -> '%20'."""

def omaha_last_status(log_text: str, appid: str) -> str | None:
    """Return the LAST updatecheck status for appid in Omaha RESPONSES found in a Chromium-updater log.
    Regex per line (no DOTALL): r'"appid":"' + re.escape(appid) + r'".{0,600}?"updatecheck":\{"status":"([a-z]+)"'
    Request lines contain "updatecheck":{} and must never match. Values: 'noupdate', 'ok', 'error-…' or None."""

def version_history_public(obj: dict) -> str | None:
    """Google VersionHistory response: max 'version' among releases whose float(fraction) >= 1.0;
    if none, max overall; None if empty."""

def parse_config_line(line: str) -> dict | None:
    """config/vendor_feeds.txt row -> {'app','kind','url','arg','artifact','host'}; comments/blank -> None;
    requires exactly 6 '|' fields and url starting 'https://'."""
```

### 1.2 `config/vendor_feeds.txt` (dokładna treść, Dodatek A)

Format: `App Name|kind|feed_url|arg|artifact|allowed_host`. `artifact` ∈ `zip|dmg|tar.gz|-`
(`-` = tylko weryfikacja, bez instalacji od producenta). `allowed_host` = dokładny host pobrania albo `-`.
`App Name` = nazwa rejestru z `config/internet_app_methods.txt`.

### 1.3 `lib/vendor_feeds.sh` (Bash 3.2, sourcowany)

```bash
_VENDOR_FEEDS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # = lib/
vendor_feed_config_path()   # echo "$_VENDOR_FEEDS_DIR/../config/vendor_feeds.txt"
vendor_feed_row "<App>"     # prints the raw row or returns 1
vendor_feed_lookup "<App>"  # prints ONE line: version|url|checksum_kind|checksum|artifact|host ; returns 1 on any failure
```

`vendor_feed_lookup`: pobierz body przez **`curl -fsSL --max-time 15 --retry 2 "$url"` na stdout** (nie przez
`fetch_to_file`, bo istniejące testy stubują `curl` jako funkcję) i przekaż je na stdin do heredocu Python:
`PYTHONPATH="$_VENDOR_FEEDS_DIR/python" python3 - "$kind" "$arg" "$(sw_vers -productVersion 2>/dev/null)" <<'PYEOF_VFL'`,
który woła `evaluate_feed`. Puste pola jako `-`. Limit body: 5 MB (`head -c 5242880`).

### 1.4 `lib/version.sh` — nowa funkcja (istniejących nie zmieniaj)

```bash
_VERSION_SH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# version_cmp A B -> prints: newer (A>B) | equal | older (A<B) | unknown
version_cmp() { PYTHONPATH="$_VERSION_SH_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 - "$1" "$2" <<'PYEOF_VCMP'
import sys
from vendor_feeds import version_compare
print({None: "unknown", -1: "older", 0: "equal", 1: "newer"}[version_compare(sys.argv[1], sys.argv[2])])
PYEOF_VCMP
}
```

### 1.5 Testy `tests/test_vendor_feeds.py` (czysty Python, bez skipów)

Fikstury z Dodatku B. Wymagane przypadki (nazwy testów dokładnie takie):
- `test_normalize_warp_stable_suffix`, `test_normalize_cask_build_suffix`, `test_normalize_parenthesised_build`
- `test_version_compare_three_way` (1.2 < 1.10, equal, older, None dla „abc”)
- `test_sparkle_picks_max_not_first` (fikstura RDM rosnąca → `2023.1.12.0`)
- `test_sparkle_attribute_form` (Docker: `4.91.0` i `4.92.0` jako atrybuty enclosure → `4.92.0`)
- `test_sparkle_element_form_and_url` (ChatGPT → `26.917.62051` + url `.zip`)
- `test_sparkle_filters_beta_channel` (ProtonVPN: `6.5.2` tylko w kanale `beta`, stable `6.5.1` → `6.5.1`)
- `test_sparkle_respects_minimum_system_version` (item z min OS 99.0 pominięty)
- `test_sparkle_parse_error_returns_none`
- `test_select_claude_releases`, `test_select_cursor_update`, `test_select_warp_channels`, `test_select_antigravity_ide_version_from_url`,
  `test_select_tauri_latest`, `test_select_proton_releases_ignores_alpha`, `test_parse_electron_yml_zip_and_sha512`,
  `test_parse_devolutions_productinfo`
- `test_omaha_ignores_request_lines`, `test_omaha_last_response_wins`, `test_omaha_unknown_appid_none`
- `test_version_history_public_prefers_full_rollout`
- `test_config_file_rows_are_valid`: każdy wiersz `config/vendor_feeds.txt` parsuje się, każde `App Name` istnieje w `config/internet_app_methods.txt`, `json`→`arg` ∈ `JSON_SELECTORS`, `artifact != '-'` ⇒ `host != '-'`.
- `test_version_cmp_bash_wrapper` (skipUnless bash): `version_cmp 2.16.0 2.15.1` → `newer`; `version_cmp 2023.1.12.0 2026.3.0.5` → `older`.

**Akceptacja:** `PYTHONPATH=dev_sync:lib/python python3 -m unittest tests.test_vendor_feeds -v` zielone; `bash run_tests.sh` zielone.

## T2 — Uczciwa weryfikacja Sparkle w istniejących handlerach

**Plik:** `lib/internet_handlers.sh`.

1. `internet_handler_sparkle_check`: pobieraj XML dotychczasowym `curl … "$feed_url"`, ale wersję zdalną licz przez
   `evaluate_feed sparkle` (heredoc z `vendor_feeds`, maksimum z kanałów domyślnych i z filtrem minimum OS).
   Relacja przez `version_cmp "$remote" "$local"`:
   - `newer` → `L_INTERNET_STATUS_UPDATE_AVAILABLE_FMT` (bez zmian), `INTERNET_LAST_VERIFIED=1`;
   - `equal` → `L_INTERNET_STATUS_CURRENT_FMT`, `INTERNET_LAST_VERIFIED=1`;
   - `older` → **nowy** `L_INTERNET_STATUS_FEED_STALE_FMT` (`remote`, `local`), `INTERNET_LAST_VERIFIED=0`;
   - `unknown`/brak → `L_INTERNET_STATUS_UNKNOWN_VERSION`.
2. `internet_handler_vendor_latest` (gałąź electron-updater i override): identycznie `version_cmp` zamiast
   `internet_version_relation`, `older` → `FEED_STALE`. Gałąź Sparkle deleguje (bez zmian).
3. Zachowaj wywołania `silent_launch_app` na końcu jak dziś (T4 to zmieni tylko dla aplikacji z feedem producenta).
4. Istniejące testy `test_vendor_latest_*` stubują `internet_version_relation`. Nowy kod woła `version_cmp`, więc te
   testy muszą przejść **bez** zmiany asercji (prawdziwe `version_cmp` da `newer` dla 2.0.0 vs 1.0.0). Jeśli któryś
   stub blokuje nowy kod, dopisz w teście stub `version_cmp` o tej samej semantyce i opisz to w raporcie.

**Testy** (nowe w `tests/test_vendor_truth_handlers.py`, skipUnless bash):
`test_sparkle_check_stale_feed_is_not_current` (atrapa `curl` zwraca fiksturę RDM, `app_version`=2026.3.0.5 →
status zawiera „stale” z EN, `INTERNET_LAST_VERIFIED=0`), `test_sparkle_check_max_item_detects_update` (Docker
fikstura, local 4.91.0 → update available 4.92.0).

## T3 — Cask Homebrew tylko jako drugi głos

**Pliki:** `config/cask_oracles.txt`, `update_internet_apps.sh` (blok „Cask Oracle”, dziś ok. linie 631–724), `tests/test_cask_oracle.py`.

1. Usuń z `config/cask_oracles.txt` wiersze `Gemini|gemini`, `Gemini Desktop|gemini` (cask `gemini` to MacPaw Gemini,
   `com.macpaw.site.Gemini2`) oraz `Comet|comet`, `Comet (Perplexity Browser)|comet` (cask stale: 145.x przy 152.x).
   Dodaj komentarz z datą i powodem.
2. Blok oracle: pomijaj aplikacje, które mają wiersz w `config/vendor_feeds.txt` (`vendor_feed_row`). Relacja przez
   `version_cmp "$_cask_ver" "$_bundle_ver"`:
   - `newer` → `L_INTERNET_STATUS_CASK_BEHIND_FMT` + wpis do `internet_behind_apps.txt` (bez zmian);
   - `equal` → `L_INTERNET_STATUS_CASK_CURRENT` (kod `current_cask_only`, T8) + wpis do `internet_verified_apps.txt`;
   - `older`/`unknown` → **bez zmiany statusu** (zostaje ⏳).
3. Popraw `tests/test_cask_oracle.py` do nowych reguł (komentarz `# Changed in v1.5.0`): cask starszy od bundla ≠ aktualny.

## T4 — Ścieżka „prawda od producenta” dla aplikacji `silent_launch`

**Nowe:** `lib/vendor_direct.sh`. **Zmiany:** `lib/internet_handlers.sh`, `lib/internet_app_updates.sh`
(`iu_chatgpt`, `iu_remote_desktop_manager`), `config/internet_app_methods.txt` (RDM → `silent_launch`),
`update_internet_apps.sh` (source nowych libów po definicji `copy_verified_app`).

### 4.1 Pomocnicze (w `lib/vendor_direct.sh`)

```bash
_vd_valid_bundle_id() { case "$1" in ''|*[!A-Za-z0-9._-]*) return 1 ;; esac; return 0; }
internet_app_bundle_id "<app_path>"     # defaults read "<app>/Contents/Info" CFBundleIdentifier
internet_app_is_running "<bundle_id>"   # validate id; [ "$(run_with_timeout 10 osascript -e "application id \"$id\" is running" 2>/dev/null)" = "true" ]
internet_app_quit_gracefully "<bundle_id>"  # only called when running; run_with_timeout 20 osascript -e "tell application id \"$id\" to quit"; then poll is_running up to 60 s (every 2 s); return 0 if exited
vendor_direct_host_allowed "<url>" "<host>" # url must start https:// ; host part (between '://' and next '/') must equal host exactly
vendor_direct_verify_checksum "<file>" "<kind>" "<value>"  # sha256hex|sha512hex (case-insensitive, shasum -a 256|512) | sha512b64 (python3 hashlib+base64) ; empty kind -> 0
vendor_direct_install "<installed_app_path>" "<url>" "<artifact>" "<checksum_kind>" "<checksum>" "<host>"
```

`vendor_direct_install`, kroki dokładnie w tej kolejności (każda porażka = return 1 i wpis `internet_diag_log`):
1. `MAC_UPDATE_DRY_RUN=1` albo `MAC_UPDATE_VERIFY_ONLY=1` → print info, return 2 (nic nie robi).
2. Zainstalowana ścieżka musi zaczynać się od `/Applications/`, inaczej return 1 (copy_verified_app obsługuje tylko `/Applications`).
3. `vendor_direct_host_allowed` (odmowa → `L_INTERNET_VENDOR_HOST_REJECTED_FMT`).
4. Aplikacja **nie może** działać (`internet_app_is_running`), inaczej return 1.
5. Pobranie: `fetch_to_file "$url" "$INTERNET_TEMP_ROOT/vd.XXXXXX.<ext>" 1800 4294967296` (plik przez `mktemp`).
6. Suma kontrolna (gdy podana), niezgodność → `L_INTERNET_CHECKSUM_MISMATCH_FMT`.
7. Rozpakowanie do `mktemp -d "$INTERNET_TEMP_ROOT/vd_x.XXXXXX"`: `zip` → `ditto -x -k`; `tar.gz` → `tar -xzf … -C`;
   `dmg` → `mount_verified_dmg` (istniejący helper; odmontuj `detach_verified_dmg` na końcu w każdej ścieżce).
8. Wybierz **dokładnie jeden** `*.app` (`find … -maxdepth 3 -type d -name '*.app' -prune`), którego `CFBundleIdentifier`
   jest równy zainstalowanemu. Zero albo więcej niż jeden → return 1.
9. `copy_verified_app "$found" "$(basename "$installed_app_path")"` (spctl + bundle + Team ID + staged swap + rollback).

### 4.2 `internet_handler_vendor_truth "<Registry App>" "<app_path>" "<launch_target>"` (w `lib/internet_handlers.sh`)

Algorytm (ustawia `INTERNET_LAST_STATUS`, `INTERNET_LAST_VERIFIED`, `INTERNET_LAST_LAUNCH_OK`):

```
I := app_version(path)
row := vendor_feed_lookup(App)
if lookup fails:
    print_warn L_INTERNET_VENDOR_FEED_UNREACHABLE_FMT; fall back to internet_handler_silent_launch (legacy) ; return
R, URL, CK, CS, ART, HOST := row
rel := version_cmp R I
equal  -> status VENDOR_CURRENT_FMT(I), VERIFIED=1, NO launch            ; return
older  -> status FEED_STALE_FMT(R, I), VERIFIED=0, NO launch              ; return
unknown-> status UNKNOWN_VERSION, NO launch                               ; return
newer:
  if DRY_RUN or VERIFY_ONLY -> UPDATE_AVAILABLE_FMT(I, R), VERIFIED=1     ; return
  BID := bundle id ; if internet_app_is_running BID -> NEEDS_RESTART_FMT(I, R), VERIFIED=1 ; return   # D7
  WAIT := MAC_UPDATE_STAGE_WAIT (default 90, integer, clamp 0..600)
  if WAIT > 0:                                   # launch cycle = original updater
      print L_INTERNET_LAUNCH_CYCLE_FMT ; silent_launch_app "$launch_target" ; sleep WAIT
      if internet_app_is_running BID: internet_app_quit_gracefully BID (never kill)
      poll app_version every 5 s up to 60 s until it changes
      I2 := app_version ; if version_cmp R I2 in {equal, older} -> UPDATED_FMT(I2), VERIFIED=1 ; return
  if ART != "-" and MAC_UPDATE_VENDOR_DIRECT != 0 and not running:
      print L_INTERNET_VENDOR_DIRECT_FMT(App, R, HOST)
      vendor_direct_install ... ; rc
      rc==0 -> I3 := app_version ; version_cmp R I3 in {equal,older} -> UPDATED_FMT(I3), VERIFIED=1 else BEHIND_FMT(I3,R)
      rc!=0 and failure happened at/after copy_verified_app -> INSTALL_ERROR (hard, existing semantics)
      rc!=0 before copy (host/download/checksum/extract/identity) -> DOWNLOAD_ERROR (soft)
      return
  BEHIND_FMT(I, R), VERIFIED=1
```

`vendor_direct_install` musi odróżniać porażkę przed kopiowaniem (return 1) od porażki `copy_verified_app`
(return 3), żeby handler wybrał DOWNLOAD_ERROR albo INSTALL_ERROR.

### 4.3 Podpięcie

- `update_internet_apps.sh`: `. "$SCRIPT_DIR/lib/vendor_feeds.sh"` i `. "$SCRIPT_DIR/lib/vendor_direct.sh"` (a w T7
  `lib/appstore_ios.sh`, w T8 `lib/internet_status.sh`) sourcuj **po** linii `. "$SCRIPT_DIR/lib/proc.sh"`
  (`run_with_timeout`) i przed `. "$SCRIPT_DIR/lib/internet_app_updates.sh"`. Dopisz te pliki do
  `test_lib_internet_apps_sourced_by_orchestrators`, jeśli test sprawdza listę.
- `internet_dispatch_silent_launch`: jeśli `vendor_feed_row "$app_display"` istnieje → `internet_handler_vendor_truth`,
  w przeciwnym razie dotychczasowa logika (bez zmian).
- `iu_chatgpt`: ścieżka z `internet_app_path "ChatGPT / Codex"` (bundle-ID-only, nie zmieniaj rozwiązywania), potem
  `internet_handler_vendor_truth "ChatGPT / Codex" "$OPENAI_APP" "$OPENAI_APP"` i `internet_handler_set_status STATUS_CHATGPT`.
- `iu_remote_desktop_manager` → `internet_dispatch_silent_launch` (zamiast `internet_dispatch_sparkle_appcast`);
  w `config/internet_app_methods.txt` RDM → `silent_launch`.
- Blok „Stale Days Warning” (`update_internet_apps.sh`, `STALE_LIMIT`): pomiń aplikacje, których kod (T8) to
  `current_verified`, `current_vendor` albo `updated`.

**Testy** (`tests/test_vendor_truth_handlers.py`, skipUnless darwin i bash). Fałszywy bundle w tmp
(`Contents/Info.plist` z plistlib: `CFBundleIdentifier`, `CFBundleShortVersionString`), stuby w PATH:
`curl` (zwraca fiksturę po wzorcu URL), `osascript` (odpowiada `true`/`false` z pliku stanu, loguje wywołania),
`open` (loguje), `sleep` (no-op). Ustaw `MAC_UPDATE_STAGE_WAIT=0` i `MAC_UPDATE_VENDOR_DIRECT=0`, o ile test nie mówi inaczej.
- `test_vendor_truth_equal_does_not_launch` (log `open` pusty, status „Up to date … vendor”)
- `test_vendor_truth_running_app_is_never_touched` (osascript `is running` → true ⇒ NEEDS_RESTART, brak `quit` i `open` w logu)
- `test_vendor_truth_behind_without_actions_reports_behind`
- `test_vendor_truth_stale_feed`
- `test_vendor_truth_feed_unreachable_falls_back` (curl rc 22 ⇒ legacy launch, status „Launched (unverified)”)
- `test_vendor_truth_dry_run_reports_update_available_without_launch`
- `test_vendor_direct_host_allowlist` (inny host ⇒ 1; `http://` ⇒ 1; dokładny host ⇒ 0)
- `test_vendor_direct_checksum_kinds` (sha256hex wielkimi literami OK, sha512b64 OK, niezgodność ⇒ 1)
- `test_vendor_direct_refuses_non_applications_path`
- `test_vendor_direct_dry_run_returns_2`

## T5 — Updatery Chromium: Google (Chrome, Drive, **Gemini**) i Comet z dowodem Omaha

**Pliki:** `lib/internet_app_updates.sh` (`google_keystone_check`, `iu_google_chrome`, `iu_google_drive`, `iu_gemini`,
`iu_comet`), `lib/internet_handlers.sh` (`internet_handler_chromium_updater`), `config/internet_app_methods.txt`,
`scripts/report_update_coverage.sh`, testy.

1. **Logi:** user `"$HOME/Library/Application Support/Google/GoogleUpdater/updater.log"`, system
   `"/Library/Application Support/Google/GoogleUpdater/updater.log"`, Comet
   `"$HOME/Library/Application Support/Perplexity/CometUpdater/updater.log"`. Przed triggerem zapisz rozmiar
   (`wc -c`). Po triggerze odpytuj co 3 s do `MAC_UPDATE_OMAHA_WAIT` (domyślnie 45, clamp 0..180) i czytaj tylko
   przyrost (`tail -c +$((size+1))`). Jeśli plik się skurczył (rotacja), czytaj cały. Przyrost dopisz do
   `$MAC_UPDATE_SESSION_DIR/chromium_updater_log.txt`.
2. **`google_keystone_check`:** zachowaj trigger (`GoogleSoftwareUpdateAgent --runMode ondemand`, jeden raz na przebieg,
   cache `GOOGLE_KEYSTONE_RAN`). Jeśli agenta brak, uruchom
   `"$HOME/Library/Application Support/Google/GoogleUpdater/Current/GoogleUpdater.app/Contents/MacOS/GoogleUpdater" --wake-all`
   (`run_with_timeout 120`). Po triggerze zbierz przyrost obu logów Google do zmiennej/pliku sesji raz na przebieg.
3. **Status z Omaha** (`omaha_last_status` na przyroście), appid: Chrome `com.google.chrome`, Gemini
   `com.google.geminimacos`, Drive `com.google.drivefs`, Comet `ai.perplexity.comet`:
   - `noupdate` → `L_INTERNET_STATUS_VENDOR_NOUPDATE` (zweryfikowane, kod `current_vendor`). **Tylko Chrome:** dodatkowo
     GET `https://versionhistory.googleapis.com/v1/chrome/platforms/mac_arm64/channels/stable/versions/all/releases?filter=endtime=none`
     → `version_history_public`. Jeśli `version_cmp public installed = newer`, status
     `L_INTERNET_STATUS_ROLLOUT_HOLD_FMT(installed, public)` (kod `rollout_hold`, informacyjny, bez soft);
   - `ok` → odczytuj wersję bundla co 5 s do 60 s; zmiana → `UPDATED_FMT`; brak zmiany → `L_INTERNET_STATUS_UPDATE_IN_PROGRESS` (⏳);
   - brak odpowiedzi → `L_INTERNET_STATUS_UPDATER_TRIGGERED` (⏳, kod `unverified`);
   - porażka triggera → `L_INTERNET_STATUS_LAUNCH_FAILED` (bez zmian).
4. **Gemini:** w configu metoda `keystone` (produkt Google; reguła §6b spełniona). `iu_gemini` używa tego samego
   (zbuforowanego) triggera i mapowania.
5. **Comet:** metoda `chromium_updater`. Dodaj `internet_handler_chromium_updater "<App>" "<app_path>" "<binary>" "<log>" "<appid>"`
   (wymagane przez `test_every_config_method_has_a_handler`). `iu_comet`: binarka
   `"$HOME/Library/Application Support/Perplexity/CometUpdater/Current/CometUpdater.app/Contents/MacOS/CometUpdater"`;
   brak → legacy `internet_dispatch_silent_launch`. Trigger: `run_with_timeout 120 "$bin" --wake-all`
   (**bez** `launchctl`), potem mapowanie jak w pkt 3.
6. **Pokrycie:** w `scripts/report_update_coverage.sh` dodaj `chromium_updater` do `DIRECT_METHODS`. Aplikacja z
   wierszem w `config/vendor_feeds.txt` jest klasyfikowana jako `verified_direct`/`vendor_feed` przed sprawdzeniem
   metody. Dodaj brakujący test `test_direct_methods_are_used_and_verify` (komentarz w skrypcie się na niego powołuje):
   każda metoda z `DIRECT_METHODS` występuje w configu i ma handler.
7. **Testy** (`tests/test_chromium_updaters.py`): fikstura logu (Dodatek B.9). `test_google_status_noupdate_is_current_vendor`,
   `test_chrome_rollout_hold_when_public_newer` (stub curl zwraca fiksturę VersionHistory),
   `test_google_no_response_is_unverified`, `test_comet_uses_its_own_updater_log`, `test_gemini_configured_as_keystone`.

## T6 — Docker Desktop: feed najpierw, CLI tylko przy aktualizacji

**Plik:** `lib/internet_app_updates.sh` `iu_docker_desktop`.

1. `R` z `vendor_feed_lookup "Docker Desktop"` (appcast arm64, `artifact -`).
2. `equal` → `VENDOR_CURRENT_FMT`, **bez uruchamiania Dockera**. `older` → `FEED_STALE_FMT`. Lookup nieudany →
   `UNKNOWN_VERSION` (soft), **bez `open -a Docker`**.
3. `newer`: dry-run/verify-only → `UPDATE_AVAILABLE_FMT`. Brak `docker` w PATH → `BEHIND_FMT` + podpowiedź.
   Działa (`run_with_timeout 15 docker desktop status` rc 0) → `run_with_timeout 900 docker desktop update -q`.
   Nie działa → `run_with_timeout 180 docker desktop start`, czekaj na `status` (co 5 s do 120 s),
   `update -q`, potem `run_with_timeout 120 docker desktop stop` (**tylko** gdy to Ty go uruchomiłeś).
   Na koniec odczytuj wersję co 10 s do 300 s → `UPDATED_FMT` albo `BEHIND_FMT`.
4. **Usuń** kombinację `--check-only --quiet`, bo dokumentacja opisuje `-q` jako „check **and apply**”.
5. Testy (stub `docker`, `curl`): `test_docker_current_does_not_start_engine`, `test_docker_behind_running_runs_update_quiet`,
   `test_docker_behind_not_running_starts_then_stops`, `test_docker_feed_unreachable_never_opens_app`.

## T7 — App Store: aplikacje iPad bez ślepego GUI, rozpoznawanie aplikacji App Store

**Nowe:** `lib/appstore_ios.sh`, `lib/python/appstore_lookup.py`, `tests/test_appstore_ios.py`.
**Zmiany:** `update_appstore.sh` (sekcja TRACK 2), `lib/internet_handlers.sh` / `lib/internet_app_updates.sh`
(strażnik), `scripts/report_update_coverage.sh`, prescan w `update_all.sh`.

1. `lib/python/appstore_lookup.py` (czyste): `read_itunes_metadata(plist_bytes) -> dict|None`
   (`itemId`→str, `bundleShortVersionString`, `itemName`/`bundleDisplayName`), `parse_lookup(json_obj) -> {trackId(str): version}`,
   `pending_ios(installed: list[dict], store: dict) -> list[dict]` (tylko `version_compare(store, installed) == 1`).
2. `lib/appstore_ios.sh`:
   - `ios_apps_scan` → linie `name|itemId|version|path` dla `/Applications/*.app` i `~/Applications/*.app` z
     `Wrapper/iTunesMetadata.plist` (plistlib w heredocu, bez sieci);
   - `ios_store_country` → pole `store` z `mas config --json` małymi literami, albo puste;
   - `ios_apps_pending` → jedno żądanie `https://itunes.apple.com/lookup?id=<id1,id2,…>[&country=<cc>]`
     (`curl -fsS --max-time 20`), wynik `name|itemId|installed|store`; rc 0 = sukces (także pusty), rc 2 = lookup nieudany.
   - `app_store_managed "<app_path>"` → 0, gdy istnieje `Wrapper/iTunesMetadata.plist` albo `Contents/_MASReceipt`.
3. `update_appstore.sh`, TRACK 2. Bramkę umieść **przed** istniejącym wczesnym wyjściem dla trybu nieinteraktywnego
   (`if [ "${MAC_UPDATE_NONINTERACTIVE:-0}" = "1" ] || [ ! -t 0 ]`, dziś ok. linii 358) i przed sprawdzeniem
   Accessibility, żeby zaległe aplikacje iPad były zapisywane także bez TTY:
   - zapisz `appstore_ios_before.txt` (wynik `ios_apps_scan`, format `name|version`);
   - brak aplikacji iOS → info i pominięcie TRACK 2;
   - lookup nieudany → `L_APPSTORE_IOS_LOOKUP_FAILED` i dotychczasowe zachowanie;
   - **nic nie czeka → `L_APPSTORE_IOS_ALL_CURRENT`, pominięcie GUI, bez `SOFT_FAIL`, bez `APPSTORE_TOR2_BACKGROUND`**;
   - coś czeka → wypisz każdą pozycję `L_APPSTORE_IOS_PENDING_FMT`. Bez TTY lub `NONINTERACTIVE` →
     `L_APPSTORE_IOS_NEEDS_INTERACTIVE`, `SOFT_FAIL=1`, zapisz `appstore_ios_pending.txt`. Z TTY → dotychczasowy TRACK 2,
     a po kliknięciu odpytuj wersje (`ios_apps_scan`) co 15 s do `MAC_UPDATE_APPSTORE_VERIFY_TIMEOUT` (domyślnie 300,
     clamp 0..1800). Wszystkie dogonione → `L_APPSTORE_IOS_VERIFIED` i **wyzeruj** `APPSTORE_TOR2_BACKGROUND`;
     w przeciwnym razie `L_APPSTORE_IOS_STILL_PENDING_FMT` + `SOFT_FAIL=1` + `appstore_ios_pending.txt`;
   - na końcu zawsze `appstore_ios_after.txt`.
4. Strażnik w kroku internet: na początku `internet_handler_manual`, `internet_dispatch_silent_launch`,
   `internet_dispatch_sparkle_appcast` i `iu_ipmiview`: `app_store_managed "$APP_PATH"` →
   `INTERNET_LAST_STATUS="$L_INTERNET_STATUS_MANAGED_APPSTORE"`, ustaw status i return (bez uruchamiania).
   Skutek: IPMIView na tym Macu (aplikacja iPad, itemId 952163566) przestaje być „ręczny”.
5. Pokrycie: aplikacja z `iTunesMetadata.plist` → `externally_managed` / `app_store_ios` **przed** `manual`/`unknown`.
6. Testy: `test_itunes_metadata_parse`, `test_pending_ios_only_when_store_newer`, `test_lookup_parse_ignores_missing_ids`
   (czysty Python), `test_app_store_managed_detects_wrapper` (darwin), `test_track2_skipped_when_all_current` (stuby
   `curl`/`mas`/`osascript`, osascript nie może być wywołany z „Update All”).

## T8 — Kody stanów, liczniki, severity, podsumowanie bez odinstalowanych

**Nowe:** `lib/internet_status.sh`. **Zmiany:** `update_internet_apps.sh`, `lib/python/run_summary.py`, testy.

1. `internet_status_code "<text>"` → wypisuje kod. Porównanie z **aktualnie załadowanymi** stałymi:
   **najpierw** dokładne dopasowanie wszystkich stałych bez `%s` (np. `VENDOR_NOUPDATE` zaczyna się tak samo jak
   `CURRENT_FMT`), **potem** prefiksy `*_FMT` (tekst przed pierwszym `%s`) od najdłuższego do najkrótszego.
   Kody i mapowanie:

| Kod | Źródło |
|---|---|
| `updated` | `UPDATED_FMT` |
| `current_verified` | `CURRENT`, `CURRENT_FMT`, `VENDOR_CURRENT_FMT` |
| `current_vendor` | `VENDOR_NOUPDATE`, `CHECKED_CLI` (legacy MAU/Docker) |
| `current_cask_only` | `CASK_CURRENT` |
| `rollout_hold` | `ROLLOUT_HOLD_FMT` |
| `update_available` | `UPDATE_AVAILABLE_FMT` |
| `behind` | `BEHIND_FMT`, `CASK_BEHIND_FMT` |
| `needs_restart` | `NEEDS_RESTART_FMT` |
| `feed_stale` | `FEED_STALE_FMT` |
| `unverified` | `LAUNCHED_UNVERIFIED`, `UPDATER_TRIGGERED`, `UPDATE_IN_PROGRESS` |
| `managed_brew` / `managed_appstore` | `MANAGED_BREW`, `MANAGED_APPSTORE` |
| `manual` | `MANUAL_UPDATE` |
| `skipped` | `SKIPPED` |
| `error_hard` | `INSTALL_ERROR`, `MOUNT_ERROR`, `EXTRACT_ERROR` |
| `error_soft` | pozostałe z dotychczasowej listy soft (`OFFLINE`, `NO_URL`, `DOWNLOAD_ERROR`, `CHECK_MAU`, `MAU_MISSING`, `MAU_QUARANTINED`, `MAU_OPENED`, `UNKNOWN_VERSION`, `CASK_MISSING`, `LAUNCH_FAILED`) |
| `unknown` | wszystko inne (w tym statusy Rosetty) |

2. Zastąp literały `"→ managed by Homebrew (update_brew.sh)"` i `"→ managed by App Store (update_appstore.sh)"`
   w inicjalizacji `STATUS_*` kluczami `L_INTERNET_STATUS_MANAGED_BREW` / `L_INTERNET_STATUS_MANAGED_APPSTORE`.
3. Po wszystkich handlerach, oracle i Rosetcie: jedna pętla po `config/internet_app_methods.txt` → kod każdego
   `STATUS_*` → `$MAC_UPDATE_SESSION_DIR/internet_status_codes.txt` (`App|code|text`). Liczniki (`internet_verified`,
   `internet_behind`, `internet_unverified`) licz **z kodów** (`current_verified|current_vendor|updated` = verified;
   `behind|needs_restart` = behind; `unverified` = unverified). Usuń dopasowywanie podciągów z 7 języków.
4. Severity: kody `behind`, `needs_restart`, `feed_stale` ⇒ `INTERNET_SOFT_FAIL=1` (dodatkowo do istniejącej pętli).
   `rollout_hold` i `current_cask_only` nie są soft.
5. Podsumowanie: helper `internet_summary_row "<Label:>" "$STATUS_X" "<Registry App>"` pomija wiersz, gdy aplikacja
   nie jest zainstalowana (`internet_app_path` puste lub nie-katalog). Zamień wszystkie `printf` wierszy na helper.
   Nagłówek sekcji drukuj tylko, gdy ma ≥ 1 wiersz. „DJI Assistant 2: ⏭️ Pominięty” znika na tym Macu.
6. `run_summary.collect_run_items`: czytaj `internet_status_codes.txt`. Kody `behind`, `needs_restart`, `feed_stale`,
   `update_available` → item `status: "pending"`, `category: "internet"`, `details` po angielsku, np.
   `"vendor 26.917.62051 > installed 26.917.51856 — quit the app so its updater can install it"`.
   `rollout_hold` → `pending` z `details` „vendor staged rollout (public X)”. Nie duplikuj pozycji już dodanych z
   `internet_behind_apps.txt` (klucz `normalize_app_key` + aliasy `inventory.APP_ALIASES`).
7. Testy: `test_status_code_mapping_en` i `test_status_code_mapping_pl` (bash, ładowanie `lang_en.sh`/`lang_pl.sh`),
   `test_counts_use_codes_not_substrings`, `test_behind_sets_soft_failure`, `test_summary_hides_uninstalled_rows`,
   `test_run_summary_reads_status_codes`.

## T9 — Homebrew: osierocone caski, wymagające sudo, zawężone greedy

**Nowe:** `lib/python/brew_casks.py`, `tests/test_brew_casks.py`. **Zmiany:** `lib/brew.sh`, `update_brew.sh`, `lib/python/run_summary.py`.

1. `brew_casks.py` (czyste):
   - `app_targets(cask: dict) -> list[str]`: z artefaktów `{"app": [...]}`; string → basename; dict → `target` basename;
   - `find_orphan_casks(info_json: dict, app_dirs: list[str], exists=os.path.exists) -> list[str]`: cask ma ≥ 1 cel
     `app` i **żaden** nie istnieje w żadnym `app_dirs`;
   - `cask_requires_sudo(cask: dict) -> bool`: artefakty zawierają klucz `pkg` lub `installer`, albo stanza
     `uninstall` zawiera `pkgutil`, `launchctl` lub `kext`.
2. `lib/brew.sh`:
   - `brew_orphan_casks` → tokeny sierot (`brew info --json=v2 --cask $(brew list --cask)`; app_dirs = `/Applications`,
     `$HOME/Applications`). Błąd zapytania → brak wyjścia, rc 1 (**nigdy** nie uznawaj wszystkiego za sieroty);
   - `brew_casks_requiring_sudo <tokens…>`;
   - `brew_outdated_casks [greedy_tokens…]`: zwykłe `brew outdated --cask` **plus**, gdy podano tokeny,
     `brew outdated --cask --greedy-auto-updates <tokeny>`; unia unikalna po pierwszym polu; zachowaj separację stderr.
3. `update_brew.sh`:
   - tokeny greedy = caski z metodą `brew_cask` w `config/internet_app_methods.txt` (`internet_cask_name_for_app`),
     przefiltrowane do zainstalowanych; przekaż je do `brew_outdated_casks` (także w dry-run i w weryfikacji końcowej);
   - po `outdated`: `brew_orphan_casks`. Dla każdej sieroty `print_info` z `L_BREW_ORPHAN_CASK_FMT` (token, oczekiwany
     `.app`, token), usuń ją z listy do aktualizacji, dopisz do `$MAC_UPDATE_SESSION_DIR/brew_orphan_casks.txt`.
     Tylko gdy `[ -t 0 ]`, `MAC_UPDATE_YES≠1` i `MAC_UPDATE_NONINTERACTIVE≠1`: zapytaj `L_BREW_ORPHAN_CASK_PROMPT_FMT`
     (domyślnie **N**) i przy `^[TtYy]$` wykonaj `brew uninstall --cask --force <token>`. Sieroty **nie** zmieniają exit code;
   - obrona w głębi w pętli strażnika downgrade'u: jeśli cask ma cel `app`, a żaden bundle nie istnieje, pomiń cask.
     Fallback `find Caskroom` używaj wyłącznie dla casków **bez** celu `app`;
   - `MAC_UPDATE_NO_SUDO=1`: caski z `brew_casks_requiring_sudo` wyjmij z upgrade, `print_warn L_BREW_CASK_NEEDS_INTERACTIVE_FMT`,
     dopisz do `brew_needs_interactive.txt`, `SOFT_FAIL=1`.
4. `run_summary`: `brew_orphan_casks.txt` → items `pending`, details
   `"app removed manually; remove the Homebrew record: brew uninstall --cask --force <t>"`;
   `brew_needs_interactive.txt` → `pending`, `"needs an interactive run (administrator rights)"`.
5. Testy: `test_app_targets_string_and_dict`, `test_orphan_when_all_targets_missing`, `test_not_orphan_without_app_artifact`,
   `test_requires_sudo_pkg_and_launchctl` (czysty Python). `test_update_brew_skips_orphan_cask` (stub `brew` logujący
   argv: `brew upgrade --cask` nie zawiera sieroty, exit ≠ 1). `test_greedy_limited_to_designated_casks`,
   `test_no_sudo_defers_pkg_casks`.

## T10 — CLI: tylko zainstalowane, własne updatery, retencja wersji

**Zmiany:** `lib/cli.sh`, `lib/native_installers.sh`, `update_npm_cli.sh`, `tests/test_cli_installers.py` (nowe testy).

1. `lib/cli.sh`: flaga `--bootstrap-cli` → `export MAC_UPDATE_BOOTSTRAP_CLI=1` + linia w `usage`.
2. `native_installer_existing_update_cmd`: `claude|agy|codex|agent` → `update`.
3. `install_native_cli`:
   - binarka `$LOCAL_BIN/<cmd>` niewykonywalna i `MAC_UPDATE_BOOTSTRAP_CLI≠1` → `print_info L_NPM_CLI_NOT_INSTALLED`,
     **return 0**, **bez pobierania instalatora**;
   - istnieje → `env <native_installer_env> "$LOCAL_BIN/<cmd>" update </dev/null` z `run_with_timeout native_installer_timeout`,
     potem `report_cli_version_or_fail`. Gdy `update` zawiedzie, a binarka istnieje, jeden raz wykonaj naprawę
     dotychczasowym instalatorem (download-then-exec), potem ponowna weryfikacja;
   - `MAC_UPDATE_BOOTSTRAP_CLI=1` i brak binarki → dotychczasowa ścieżka instalatora.
4. Metoda `npm`: pakiet jest zainstalowany, gdy istnieje `$NPM_GLOBAL_PREFIX/lib/node_modules/<package>` lub wykonywalny
   `$NPM_GLOBAL_BIN/<command>`. W innym razie (i bez bootstrapu) `L_NPM_CLI_NOT_INSTALLED` i dalej. Wiersz `npm` jest
   częścią toolchainu i aktualizuje się, gdy istnieje `$N_PREFIX/bin/node`.
5. Node: `ensure_latest_node` tylko, gdy istnieje `$N_PREFIX/bin/node` lub bootstrap. W przeciwnym razie
   `L_NPM_TOOLCHAIN_NOT_INSTALLED` i pominięcie całej sekcji npm (bez błędu).
6. Bun: `ensure_latest_bun` tylko, gdy istnieje `$BUN_BIN/bun` lub bootstrap.
7. `prune_vendor_cli_versions` (po aktualizacjach; pomiń przy dry-run lub `MAC_UPDATE_KEEP_CLI_VERSIONS=1`):
   - Codex: root `$HOME/.codex/packages/standalone/releases`; `current` = realpath `$HOME/.codex/packages/standalone/current`;
     kandydaci: katalogi pasujące do `^[0-9]+\.[0-9]+\.[0-9]+-[a-z0-9_]+-apple-darwin$`;
   - cursor-agent: root `$HOME/.local/share/cursor-agent/versions`; chronione = katalogi docelowe symlinków
     `$HOME/.local/bin/cursor-agent` i `$HOME/.local/bin/agent`; wzorzec `^[0-9]{4}\.[0-9]{2}\.[0-9]{2}-[0-9a-f]+$`;
   - zostaw chronione + **jeden** najnowszy (mtime) poprzedni, resztę `rm -rf -- "<root>/<name>"` **dopiero po**
     sprawdzeniu, że realpath zaczyna się od `<root>/` i nie jest chroniony;
   - agy: pliki `$HOME/.local/bin/agy.<cyfry>.old` usuń tylko, jeśli `"$HOME/.local/bin/agy" --version` ma rc 0;
   - raport `L_NPM_PRUNED_FMT` (liczba, nazwa, MB z `du -sk` przed/po).
8. Testy (tymczasowy `HOME`, stub `curl` logujący wywołania):
   `test_missing_native_cli_is_not_reinstalled` (brak `codex` ⇒ zero wywołań curl, rc 0),
   `test_existing_codex_uses_update_subcommand`, `test_existing_agent_uses_update_subcommand`,
   `test_bootstrap_flag_installs_missing_cli`, `test_npm_package_skipped_when_absent`,
   `test_bun_not_installed_when_absent`, `test_prune_keeps_current_and_one_previous`,
   `test_prune_never_deletes_symlink_target`, `test_prune_ignores_unexpected_names`, `test_prune_agy_old_files`.

## T11 — Inwentarz: synchronizacja wszystkich grup (inwentarz aktualny po każdej ręcznej zmianie)

**Nowe:** `lib/python/inventory_sync.py`, `tests/test_inventory_sync.py`, `tests/fixtures/inventory/APPLICATIONS_sample.md`.
**Zmiany:** prescan i postupdate w `update_all.sh` (heredoki), `lib/python/inventory.py` (tylko import/eksport).

1. `inventory_sync.py`:

```python
def minimal_template(user, os_label, build, home, script_dir, today) -> str
    # One template for BOTH prescan and postupdate (replace the two inline copies; codename map includes 27: 'Golden Gate').
    # Must contain the iPad subsection header (see sync_ipad_section).
def section_span(md: str, heading_re: str) -> tuple[int, int] | None
    # from the heading line start to the next heading of the same or higher level (or EOF)
def sync_mas_group(md, mas_apps: dict[str, tuple[str, str]] | None) -> tuple[str, list[str], list[str]]
    # GRUPA 2 (heading r'^## GRUPA 2\b'): collect ALL two-column rows '| name | <6+ digits> |' anywhere in the
    # section (also detached ones like '| GarageBand 🆕 | 682658836 |'), drop them, write ONE table right after the
    # section's leading '>' quote lines: header '| Nazwa | App ID |' + '|-------|--------|' + rows sorted
    # case-insensitively. Keep an existing row's name (strip ' 🆕') if its ID is installed; add rows for new IDs
    # with the mas name; remove rows whose ID is not installed. None -> unchanged.
def sync_ipad_section(md, ipad_apps: list[tuple[str, str, str]] | None) -> tuple[str, int]
    # Managed subsection inside GRUPA 2: '### 📱 Aplikacje iPad na Apple Silicon (App Store)' +
    # '| Nazwa | App ID | Wersja |' table + one note line. Replaces the legacy quote block that starts with
    # '> ⚠️ **Aplikacje iPad na Apple Silicon**' (and its following '>' lines). None -> unchanged.
def remove_names_from_group3(md, names: set[str]) -> tuple[str, list[str]]
    # remove rows whose first cell (norm_name, aliases) is in names from GRUPA 3 tables incl. the 🆕 section
def sync_formulae(md, installed: set[str] | None) -> tuple[str, list[str]]        # remove rows in 4a/4b not installed
def sync_casks(md, installed_nonorphan: set[str] | None) -> tuple[str, list[str]] # remove rows in 4c not in set
def rebuild_cli_section(md, clis: list[tuple[str, str]] | None) -> tuple[str, list[str], list[str]]
    # 4d = exactly the detected manifest CLIs; keep an existing description when the name matches, else '—'
def recompute_summary(md) -> str       # rewrite the whole '## Podsumowanie' table (format in Dodatek E)
def rebuild_legend(md, rows: list[tuple[str, str]]) -> str   # rewrite the '## Legenda aktualizacji' table
def legend_rows(methods_rows, installed_names, casks, mas_names, ipad_names, cli_names) -> list[tuple[str, str]]
def detect_cli_versions(manifest_path, home, which=shutil.which, run=subprocess.run) -> list[tuple[str, str]]
    # moved verbatim from the inline Python in update_all.sh (inventory-only branch); update that branch to import it
def gather_facts(script_dir, home, run=subprocess.run) -> dict
    # keys: mas (adamID->(name,version) from `mas list --json` NDJSON; fallback text; empty -> None),
    # formulae (`brew list --formula`), casks_nonorphan (`brew list --cask` minus brew_casks.find_orphan_casks),
    # orphans, clis (detect_cli_versions), ipad (Wrapper/iTunesMetadata.plist via plistlib),
    # installed_app_names. Any failed source -> None for that key.
def sync_all(md, facts, methods_rows) -> tuple[str, dict]
    # Applies all of the above in a fixed order; returns (new_md, report).
    # SAFETY GUARD: if a sync would remove EVERY row of a group that currently has rows, skip that group and put a
    # warning in report['skipped_groups'] (never wipe a group on a flaky query).
```

2. **Prescan:** oblicz `facts = gather_facts(...)` na początku. Aplikacje iPad i te z `_MASReceipt` dodaj do
   `SKIP_DISCOVERY_APPS` (nie trafiają do 🆕). Na końcu, **niezależnie od `any_new_found`**, wykonaj `sync_all`.
   Zapisz plik atomowo, gdy treść się zmieniła. Zmień warunek wczesnego `sys.exit(0)` tak, żeby exit następował
   dopiero, gdy nie ma ani nowych pozycji, ani zmian z synchronizacji. Wypisz `L_PRESCAN_REMOVED_FROM_GROUP_FMT`
   dla każdej grupy z usunięciami i `L_PRESCAN_IPAD_SECTION_SYNCED_FMT`.
3. **Postupdate:** po aktualizacji wersji jeszcze raz `sync_all` ze świeżymi `facts` (zmiany w trakcie przebiegu).
   Szablon awaryjny zastąp `minimal_template` (usuwa duplikat mapy kodów bez 27).
4. `build_inventory.sh` nie wymaga zmian (używa prescan + postupdate w trybie inventory-only). Sprawdź.
5. **Testy** (czysty Python, syntetyczna fikstura z Dodatku B.10):
   `test_mas_group_removes_uninstalled_and_merges_detached_row`, `test_mas_group_none_is_noop`,
   `test_ipad_section_created_and_group3_rows_removed`, `test_formulae_and_casks_removed_when_uninstalled`,
   `test_cli_section_rebuilt_from_detected`, `test_guard_never_wipes_whole_group`,
   `test_summary_counts_match_tables`, `test_legend_rebuilt_from_config`, `test_sync_all_is_idempotent`
   (dwa przebiegi ⇒ identyczny tekst), `test_minimal_template_has_golden_gate_and_ipad_section`.
6. **Weryfikacja na żywo (obowiązkowa):**
   ```bash
   mkdir -p scratch/backup_T11 && cp -p APPLICATIONS.md scratch/backup_T11/
   bash build_inventory.sh
   diff -u scratch/backup_T11/APPLICATIONS.md APPLICATIONS.md | head -250 > scratch/T11_inventory.diff
   ```
   Oczekiwane (jeśli Mac się nie zmienił): znikają `Notion Web Clipper`, `gemini-cli`, `qwen-code`; pojawia się
   `cursor-agent`; `GarageBand` jest w tabeli GRUPY 2; powstaje sekcja iPad z UniFi, WiFiman, Picsart, IPMIView, S2M,
   TrackMan.Go.Ios; te nazwy znikają z GRUPY 3 i z 🆕; podsumowanie ma poprawne liczby. **Jeśli diff zawiera cokolwiek
   innego niż oczekiwane (np. znika cała grupa), przywróć kopię** (`cp -p scratch/backup_T11/APPLICATIONS.md .`),
   napraw kod i powtórz. Diff (bez danych osobowych poza nazwami aplikacji) dołącz do raportu.

## T12 — Przypisanie zmian wykonanych „między krokami”

**Plik:** `lib/python/run_summary.py` (`collect_run_items`), test.

Dodaj sekcję po wszystkich kategoriach: porównaj `installed_apps_scan.txt` z `installed_apps_after.txt` (format
`name|version`) oraz `appstore_ios_before.txt` z `appstore_ios_after.txt`. Dla każdej aplikacji, której wersja się
zmieniła, a klucz (`normalize_app_key` + wszystkie aliasy z `inventory.APP_ALIASES`) nie jest w `seen_updated_apps`,
dodaj item `category: "background"`, `status: "updated"`,
`details: "updated outside toolkit steps (vendor updater / App Store)"`. Test:
`test_between_step_changes_are_attributed` (Claude 2.2553.13 → 2.7032.0, Picsart 30.7.2 → 30.8.2, brak duplikatu,
gdy aplikacja jest już jako `internet`).

## T13 — Krok systemowy i log

1. `update_system.sh`: podziel `INSTALL_LABELS` na `NORESTART_LABELS` i `RESTART_LABELS` (tablice indeksowane).
   Najpierw każda etykieta bez restartu: `sudo softwareupdate -i "$lbl" -R --verbose` (reguła #1: zawsze `-R`).
   Potem **jedno** wywołanie `sudo softwareupdate -i "${RESTART_LABELS[@]}" -R --verbose`. Przy sukcesie dopisz
   każdą etykietę do `system_installed_labels.txt`. Dry-run wypisuje dokładnie te wywołania.
   Test w `tests/test_system_step.py`: listing z jedną etykietą restart i jedną bez ⇒ dwa wywołania, restart ostatni i
   zawiera obie etykiety restart. Użyj istniejącego stylu stubów.
2. `update_all.sh` (zrzut snapshotów przy wyjściu, ok. linii 431): pełny zrzut tylko, gdy `BLOCKING_EXIT≠0` lub
   `MAC_UPDATE_DEBUG=1`. Przy samym `DEGRADED` dołącz tylko pliki `*diag*.txt`, `*pending*.txt`,
   `internet_status_codes.txt`, `brew_orphan_casks.txt`. `test_appstore_diag_captured_on_failure` ma przejść.
   Nowy test `test_degraded_run_does_not_dump_brew_lists`.

## T14 — Dokumentacja, narzędzie kontrolne, wersja 1.5.0

1. **`scripts/check_vendor_feeds.sh`** (tylko odczyt, bez mutacji): dla każdego wiersza `config/vendor_feeds.txt`,
   którego aplikacja jest zainstalowana, wypisz tabelę `App | installed | vendor | relation | artifact host`, a dla
   Chrome/Gemini/Drive/Comet ostatni status Omaha z logów. Kod wyjścia 0. Flaga `--json` (lista obiektów).
2. `docs/agents/critical_rules.md`: nowe §15 „Vendor truth” (D5–D7, `remote<local = feed_stale`, cask tylko drugi
   głos, allowlista hostów, `copy_verified_app` obowiązkowe), §16 „Only installed” (D2, `--bootstrap-cli`), §17
   „Orphan casks”. Zaktualizuj tabelę metod (§5) i §6b (`chromium_updater`, Gemini w `keystone`).
3. `docs/agents/scripts.md`: nowe pliki, flaga `--bootstrap-cli`, zmienne `MAC_UPDATE_STAGE_WAIT`,
   `MAC_UPDATE_VENDOR_DIRECT`, `MAC_UPDATE_OMAHA_WAIT`, `MAC_UPDATE_APPSTORE_VERIFY_TIMEOUT`,
   `MAC_UPDATE_KEEP_CLI_VERSIONS`, `MAC_UPDATE_DEBUG`.
4. `docs/agents/troubleshooting.md`: wiersze „Cask app removed manually (orphan)”, „Status: quit the app so its
   updater can install”, „Vendor feed stale”, „Chrome: vendor staged rollout”, „CLI not installed — skipping”.
5. `.claude/commands/`: `mac-update-system.md` (usuń `softwareupdate -ia -R`; opisz per-label + batch restart),
   `mac-update.md` (kolejność 0 prescan → 1 App Store → 2 CLI → 3 Homebrew → 4 internet → 5 inwentarz → 6 macOS),
   `mac-update-appstore.md` (bez „macOS 26.x / CVE”, dodaj bramkę iTunes Lookup), `mac-update-internet.md` (feed producenta).
6. `CHANGELOG.md`: wpis `1.5.0` z listą T1–T13. `VERSION` = `1.5.0` i wszystkie pliki z `tests/test_version_consistency.py` (`LIVING`).
7. 7 × README: jedna zwięzła sekcja/punkt o: feedzie producenta, zasadzie „tylko zainstalowane” + `--bootstrap-cli`,
   osieroconych caskach, `scripts/check_vendor_feeds.sh`. Tekst EN i PL z Dodatku C.4, pozostałe przetłumacz.

## T15 — Weryfikacja końcowa i raport

Uruchom i wklej wyniki (skrócone) do raportu:

```bash
bash run_tests.sh                                   # ALL CHECKS PASSED, liczba testów
find . -type f -name '*.sh' ! -path './.git/*' ! -path './graphify-out/*' ! -path './dev_sync_logs/*' -print0 | xargs -0 shellcheck --severity=warning
bash update_all.sh --dry-run 2>&1 | tail -60        # brak open/quit/download, każdy krok [DRY-RUN]
bash scripts/check_vendor_feeds.sh                  # tabela prawdy producentów
bash scripts/report_update_coverage.sh | head -40
git log --oneline main..HEAD
git diff --stat main..HEAD | tail -5
```

W raporcie wypełnij Dodatek D w całości. **Nie deklaruj sukcesu bez tych wyników.** Jeśli któreś zadanie jest
niepełne, oznacz je `PARTIAL` i opisz, czego brakuje.

---

## Dodatek A — `config/vendor_feeds.txt` (dokładna treść)

```text
# ============================================================
# config/vendor_feeds.txt — vendor truth for internet apps (v1.5.0)
# Format: App Name|kind|feed_url|arg|artifact|allowed_host
#   kind: sparkle | json | yml | kv
#   arg:  sparkle -> comma channels or '-' ; json -> selector name ; yml -> '-' ; kv -> productinfo prefix
#   artifact: zip | dmg | tar.gz | -   ('-' = verify only, never install from vendor)
#   allowed_host: exact download host, '-' when artifact is '-'
# The feed is the source of truth; a Homebrew cask may only confirm "behind".
# URLs mirror each cask's livecheck block (verified 2026-09-23).
# ============================================================
ChatGPT / Codex|sparkle|https://persistent.oaistatic.com/codex-app-prod/appcast.xml|-|zip|persistent.oaistatic.com
Claude|json|https://downloads.claude.ai/releases/darwin/universal/RELEASES.json|claude_releases|zip|downloads.claude.ai
Cursor|json|https://api2.cursor.sh/updates/api/update/darwin-arm64/cursor/0.0.0/stable|cursor_update|zip|downloads.cursor.com
Warp|json|https://releases.warp.dev/channel_versions.json|warp_channels|-|-
Antigravity|yml|https://antigravity-hub-auto-updater-974169037036.us-central1.run.app/manifest/latest-arm64-mac.yml|-|zip|storage.googleapis.com
Antigravity IDE|json|https://antigravity-ide-auto-updater-974169037036.us-central1.run.app/api/update/darwin-arm64/stable/latest|antigravity_ide|zip|edgedl.me.gvt1.com
OpenCode|json|https://github.com/anomalyco/opencode/releases/latest/download/latest.json|tauri_latest|tar.gz|github.com
Proton Mail|json|https://proton.me/download/mail/macos/version.json|proton_releases|dmg|proton.me
Docker Desktop|sparkle|https://desktop.docker.com/mac/main/arm64/appcast.xml|-|-|-
Remote Desktop Manager|kv|https://devolutions.net/productinfo.htm|RDMMacbin|dmg|cdn.devolutions.net
```

Stan producentów z 2026-09-23 (do porównania w T15, może się zmienić): ChatGPT `26.917.62051`, Claude `2.7032.0`,
Cursor `3.21.18`, Warp stable `v0.2026.09.16.08.27.stable_02`, Antigravity `2.16.0`, Antigravity IDE `2.5.5`,
OpenCode `1.18.32`, Proton Mail Stable `1.14.0`, Docker `4.92.0`, RDM `2026.3.0.5`.

## Dodatek B — fikstury (utwórz w `tests/fixtures/vendor_feeds/`)

**B.1 `rdm_ascending.xml`** (atrybuty, rosnąco, bez nowszych niż 2023):
```xml
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle"><channel>
<item><title>0.9.0.3</title><enclosure url="https://cdn.devolutions.net/a.dmg" sparkle:shortVersionString="0.9.0.3" sparkle:version="0.9.0.3" type="application/octet-stream"/></item>
<item><title>2023.1.11.1</title><enclosure url="https://cdn.devolutions.net/b.dmg" sparkle:shortVersionString="2023.1.11.1" sparkle:version="2023.1.11.1" type="application/octet-stream"/></item>
<item><title>2023.1.12.0</title><enclosure url="https://cdn.devolutions.net/c.dmg" sparkle:shortVersionString="2023.1.12.0" sparkle:version="2023.1.12.0" type="application/octet-stream"/></item>
</channel></rss>
```
**B.2 `docker_attr.xml`**: dwa `<item>`, enclosure z `sparkle:shortVersionString="4.91.0"` i `"4.92.0"` (w tej kolejności).
**B.3 `chatgpt_elements.xml`**: trzy `<item>` z elementami `<sparkle:version>10789</sparkle:version>`,
`<sparkle:shortVersionString>26.917.62051</sparkle:shortVersionString>`, `<sparkle:minimumSystemVersion>13.0</sparkle:minimumSystemVersion>`
i `<enclosure url="https://persistent.oaistatic.com/codex-app-prod/ChatGPT-darwin-arm64-26.917.62051.zip" length="1" type="application/octet-stream"/>`;
pozostałe dwa: `10640/26.917.61114`, `10492/26.917.51856`.
**B.4 `protonvpn_channels.xml`**: `6.5.2` z `<sparkle:channel>beta</sparkle:channel>`, `6.5.1` bez kanału, `6.5.0` bez kanału.
**B.5 `claude_releases.json`**:
```json
{"currentRelease":"2.7032.0","releases":[{"version":"2.7032.0","updateTo":{"name":"Claude 2.7032.0","version":"2.7032.0","pub_date":"2026-09-22T06:11:48.656Z","url":"https://downloads.claude.ai/releases/darwin/universal/2.7032.0/Claude-6c468ab6ed862a68c9555cce34f11186c35f526d.zip","notes":""}}]}
```
**B.6 `cursor_update.json`**: `{"url":"https://downloads.cursor.com/production/c4730f7d93d787d9ab120af715999f0345ee5bc5/darwin/arm64/Cursor-darwin-arm64.zip","name":"3.21.18"}`
**B.7 `warp_channels.json`**: `{"beta":{"version":"v0.2024.12.18.08.02.beta_00"},"stable":{"cli_version":"v0.2026.09.09.08.26.stable_03","version":"v0.2026.09.16.08.27.stable_02"}}`
**B.8 `antigravity.yml`**:
```yaml
version: 2.16.0
files:
  - url: https://storage.googleapis.com/antigravity-public/antigravity-hub/2.16.0-4917332007583744/darwin-arm/Antigravity.zip
    sha512: Wx5mDtyLZocfalRgfKZ5xAzeJicsGHZ5BI/8CfuDKpt0OVWPBn/0k6KUV+MJ4Dfzk/FIgmL6hxpYIgVzXPb6fQ==
    size: 181548704
path: Antigravity.zip
sha512: Wx5mDtyLZocfalRgfKZ5xAzeJicsGHZ5BI/8CfuDKpt0OVWPBn/0k6KUV+MJ4Dfzk/FIgmL6hxpYIgVzXPb6fQ==
```
**B.8b `antigravity_ide.json`**: `{"url":"https://edgedl.me.gvt1.com/edgedl/release2/j0qc3/antigravity/stable/2.5.5-4923483625488384/darwin-arm/Antigravity IDE.zip","name":"1.107.0","productVersion":"1.107.0","sha256hash":"33338ced"}`
(uwaga: wersja pochodzi z URL = `2.5.5`, nie z `name`; spacja w URL → `%20`).
**B.8c `tauri_latest.json`**: `{"version":"1.18.32","platforms":{"darwin-aarch64":{"url":"https://github.com/anomalyco/opencode/releases/download/v1.18.32/opencode-desktop-mac-arm64.app.tar.gz","signature":"x"}}}`
**B.8d `proton_version.json`**: `Releases` z `Alpha 1.15.0`, `Stable 1.14.0`, `Stable 1.13.4`, `EarlyAccess 1.13.2`; każdy z
`File: [{"Identifier":"Apple Disk Image","Url":"https://proton.me/download/mail/macos/ProtonMail-desktop.dmg","Sha512CheckSum":"<hex>"}]` → oczekiwane `1.14.0`.
**B.8e `productinfo.htm`**: `RDMMacbin.Version=2026.3.0.5`, `RDMMacbin.Url=https://cdn.devolutions.net/download/Mac/Devolutions.RemoteDesktopManager.Mac.2026.3.0.5.dmg`, `RDMMacbin.hash=945B1D1F…`, plus linie innych produktów.
**B.9 `googleupdater.log`** (dwie linie żądania i odpowiedzi; odpowiedź ostatnia wygrywa):
```text
[1:2:0923/094646.062632:VERBOSE2:components/update_client/request_sender.cc:119] Sending Omaha request: {"request":{"apps":[{"appid":"com.google.chrome","cohort":"1:1y5:","updatecheck":{},"version":"153.0.8010.53"},{"appid":"com.google.geminimacos","updatecheck":{},"version":"1.116.5.889"}]}}
[1:2:0923/094646.163000:VERBOSE2:components/update_client/request_sender.cc:200] {"response":{"apps":[{"appid":"com.google.chrome","cohort":"1:1y5:","status":"ok","cohortname":"Stable","ping":{"status":"ok"},"updatecheck":{"status":"noupdate"}},{"appid":"com.google.geminimacos","status":"ok","ping":{"status":"ok"},"updatecheck":{"status":"noupdate"}}]}}
```
**B.9b `versionhistory.json`**: `{"releases":[{"version":"154.0.8037.58","fraction":1},{"version":"154.0.8037.57","fraction":0.1},{"version":"153.0.8010.53","fraction":0.8}]}` → public `154.0.8037.58`.
**B.10 `tests/fixtures/inventory/APPLICATIONS_sample.md`**: syntetyczny inwentarz z sekcjami GRUPA 1–4, Podsumowanie,
Legenda. GRUPA 2 ma tabelę z 3 aplikacjami (jedna niezainstalowana, np. `Notion Web Clipper | 1559269364`) oraz
**odłączony** wiersz `| GarageBand 🆕 | 682658836 |` po pustej linii, a potem blok `> ⚠️ **Aplikacje iPad na Apple Silicon** …`.
GRUPA 3 ma `UniFi` w tabeli sieciowej i sekcję 🆕 z `S2M`. 4d ma `gemini-cli` i `qwen-code`. Bez prawdziwych danych osobowych.

## Dodatek C — klucze i18n (dodaj do wszystkich 7 plików; EN / PL dokładnie)

**C.1 internet**

| Klucz | EN | PL |
|---|---|---|
| `L_INTERNET_STATUS_FEED_STALE_FMT` | `⚠️  Vendor feed stale (feed %s < installed %s)` | `⚠️  Nieaktualny feed producenta (feed %s < zainstalowana %s)` |
| `L_INTERNET_STATUS_BEHIND_FMT` | `⚠️  Behind: %s < %s (vendor)` | `⚠️  W tyle: %s < %s (producent)` |
| `L_INTERNET_STATUS_NEEDS_RESTART_FMT` | `⚠️  Update %s → %s pending — quit the app so its updater can install it` | `⚠️  Czeka aktualizacja %s → %s — zamknij aplikację, aby jej updater ją zainstalował` |
| `L_INTERNET_STATUS_VENDOR_CURRENT_FMT` | `✅ Up to date (%s, vendor feed)` | `✅ Aktualna (%s, feed producenta)` |
| `L_INTERNET_STATUS_VENDOR_NOUPDATE` | `✅ Up to date (vendor updater: no update)` | `✅ Aktualna (updater producenta: brak aktualizacji)` |
| `L_INTERNET_STATUS_ROLLOUT_HOLD_FMT` | `ℹ️  Vendor rollout: %s installed, %s public — not offered to this Mac yet` | `ℹ️  Rollout producenta: zainstalowana %s, publiczna %s — ten Mac jeszcze nie dostał oferty` |
| `L_INTERNET_STATUS_UPDATER_TRIGGERED` | `⏳ Vendor updater triggered (no response recorded)` | `⏳ Uruchomiono updater producenta (brak zapisanej odpowiedzi)` |
| `L_INTERNET_STATUS_UPDATE_IN_PROGRESS` | `⏳ Vendor is installing an update` | `⏳ Producent instaluje aktualizację` |
| `L_INTERNET_STATUS_MANAGED_BREW` | `→ managed by Homebrew (update_brew.sh)` | `→ zarządzane przez Homebrew (update_brew.sh)` |
| `L_INTERNET_STATUS_MANAGED_APPSTORE` | `→ managed by App Store (update_appstore.sh)` | `→ zarządzane przez App Store (update_appstore.sh)` |
| `L_INTERNET_VENDOR_FEED_UNREACHABLE_FMT` | `Vendor feed for %s unreachable — falling back to the app's own updater` | `Feed producenta dla %s niedostępny — przełączam na wbudowany updater aplikacji` |
| `L_INTERNET_LAUNCH_CYCLE_FMT` | `Starting %s so its own updater can install %s (it will be quit afterwards)` | `Uruchamiam %s, aby jej własny updater zainstalował %s (potem zostanie zamknięta)` |
| `L_INTERNET_VENDOR_DIRECT_FMT` | `Installing %s %s from the vendor (%s) with signature and Team ID verification` | `Instaluję %s %s od producenta (%s) z weryfikacją podpisu i Team ID` |
| `L_INTERNET_VENDOR_HOST_REJECTED_FMT` | `Refusing download from unexpected host %s for %s` | `Odrzucam pobieranie z nieoczekiwanego hosta %s dla %s` |
| `L_INTERNET_CHECKSUM_MISMATCH_FMT` | `Checksum mismatch for %s — download discarded` | `Niezgodna suma kontrolna dla %s — pobranie odrzucone` |

**C.2 App Store**

| Klucz | EN | PL |
|---|---|---|
| `L_APPSTORE_IOS_ALL_CURRENT` | `iPad apps are up to date (App Store lookup) — Track 2 not needed` | `Aplikacje iPad są aktualne (App Store lookup) — Track 2 niepotrzebny` |
| `L_APPSTORE_IOS_PENDING_FMT` | `iPad app update available: %s %s → %s` | `Dostępna aktualizacja aplikacji iPad: %s %s → %s` |
| `L_APPSTORE_IOS_LOOKUP_FAILED` | `App Store lookup unavailable — running Track 2 without a pre-check` | `App Store lookup niedostępny — uruchamiam Track 2 bez wstępnej weryfikacji` |
| `L_APPSTORE_IOS_VERIFIED` | `iPad apps verified after Track 2` | `Aplikacje iPad zweryfikowane po Track 2` |
| `L_APPSTORE_IOS_STILL_PENDING_FMT` | `Still installing or pending: %s` | `Nadal instalowane lub oczekujące: %s` |
| `L_APPSTORE_IOS_NEEDS_INTERACTIVE` | `iPad app updates need an interactive run (Track 2 uses the App Store window)` | `Aktualizacje aplikacji iPad wymagają przebiegu interaktywnego (Track 2 używa okna App Store)` |

**C.3 Homebrew / CLI / inwentarz**

| Klucz | EN | PL |
|---|---|---|
| `L_BREW_ORPHAN_CASK_FMT` | `Cask %s: the app was removed manually (%s missing) — skipping. Remove the Homebrew record: brew uninstall --cask --force %s` | `Cask %s: aplikacja została usunięta ręcznie (brak %s) — pomijam. Usuń rekord Homebrew: brew uninstall --cask --force %s` |
| `L_BREW_ORPHAN_CASK_PROMPT_FMT` | `Remove the Homebrew record for %s now? [y/N]: ` | `Usunąć teraz rekord Homebrew dla %s? [t/N]: ` |
| `L_BREW_CASK_NEEDS_INTERACTIVE_FMT` | `Cask %s needs administrator rights — deferred to an interactive run` | `Cask %s wymaga uprawnień administratora — odłożony do przebiegu interaktywnego` |
| `L_NPM_TOOLCHAIN_NOT_INSTALLED` | `Managed Node toolchain not installed — skipping (use --bootstrap-cli to install)` | `Zarządzany toolchain Node nie jest zainstalowany — pomijam (użyj --bootstrap-cli, aby zainstalować)` |
| `L_NPM_PRUNED_FMT` | `Removed %s old %s versions (freed %s MB)` | `Usunięto %s starych wersji %s (zwolniono %s MB)` |
| `L_PRESCAN_REMOVED_FROM_GROUP_FMT` | `Removed %s entries that are no longer installed from %s` | `Usunięto %s wpisów, których już nie ma na Macu, z %s` |
| `L_PRESCAN_IPAD_SECTION_SYNCED_FMT` | `iPad apps section synced (%s apps)` | `Sekcja aplikacji iPad zsynchronizowana (%s)` |

**C.4 README (EN / PL, jeden akapit):**
- EN: „**Vendor truth (v1.5.0):** each app's version is checked against its vendor's own feed before anything runs.
  Up-to-date apps are left alone; outdated ones are updated by the app's own updater, or installed from the vendor
  with signature and Team ID verification. Only software that is installed gets updated (`--bootstrap-cli` installs
  missing CLIs on purpose). Apps removed manually are detected and never reinstalled. Check the vendor state
  read-only with `bash scripts/check_vendor_feeds.sh`.”
- PL: „**Prawda od producenta (v1.5.0):** wersja każdej aplikacji jest porównywana z feedem jej producenta, zanim
  cokolwiek zostanie uruchomione. Aktualne aplikacje zostają nietknięte; nieaktualne aktualizuje ich własny updater
  albo instalacja od producenta z weryfikacją podpisu i Team ID. Aktualizowane jest wyłącznie to, co jest
  zainstalowane (`--bootstrap-cli` celowo instaluje brakujące CLI). Aplikacje usunięte ręcznie są rozpoznawane i
  nigdy nie wracają. Stan producentów sprawdzisz bez zmian w systemie: `bash scripts/check_vendor_feeds.sh`.”

## Dodatek D — szablon raportu `docs/reviews/archive/IMPLEMENTATION_REPORT_opus55_v1.md`

```markdown
# Implementation report — vendor truth v1.5.0 (Gemini 3.8 Flash)
Branch: feat/vendor-truth-v1.5 · base: 0a613d0 · date: <YYYY-MM-DD>

## Summary
| Task | Status (DONE/PARTIAL/SKIPPED) | Commit | Tests added (names) | Tests total after |
|---|---|---|---|---|
| T0 … T15 | | | | |

## Evidence
- run_tests.sh: <paste the last 15 lines>
- shellcheck: <output or "no findings">
- update_all.sh --dry-run: <tail -60>
- check_vendor_feeds.sh: <table>
- report_update_coverage.sh: <head -40>
- T11 inventory diff: <scratch/T11_inventory.diff content>

## Deviations from the prompt (with reason)
## Tests changed because they encoded an old rule (file::test, old rule → new rule)
## Open questions / things I could not verify live
## Files changed (git diff --stat main..HEAD)
```

## Dodatek E — format tabeli „Podsumowanie” (dokładnie)

```markdown
## Podsumowanie

| Grupa | Liczba |
|-------|--------|
| 🍎 Systemowe Apple | <n> |
| 🛍️ App Store | <n> |
| 📱 App Store — iPad | <n> |
| 🌐 Pobrane z Internetu | <n> |
| 🆕 Do skategoryzowania | <n> |          ← tylko gdy n > 0
| 🍺 Homebrew Formulae (kluczowe) | <n> |
| 🍺 Homebrew Formulae (biblioteki) | <n> |
| 🍺 Homebrew Casks | <n> |
| 🧰 Native CLI + npm | <n> |
| **RAZEM** | **<suma>** |
```

Liczby = liczba wierszy danych w odpowiednich tabelach (bez nagłówka i separatora). „Pobrane z Internetu” = wszystkie
tabele GRUPY 3 poza sekcją 🆕.

---

**Na koniec** napisz w czacie trzy linie: gałąź, liczba commitów, liczba testów przed i po. Dopisz: „Raport:
docs/reviews/archive/IMPLEMENTATION_REPORT_opus55_v1.md”. Nie pushuj i nie merguj.
