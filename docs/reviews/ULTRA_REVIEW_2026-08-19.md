# ULTRA REVIEW — macOS Updates v1.4.1

**Data:** 2026-08-19 · **Maszyna:** nowy MacBook, macOS 26.6.2 Tahoe (25G83), Apple Silicon arm64
**Punkt wyjścia:** `logs/update_all_20260819_173541.log` — exit 1, krok macOS pominięty
**Punkt końcowy:** `logs/update_all_20260819_184212.log` — exit 0, `blocking_exit: 0`, 170/170 testów zielonych

---

## 0. Streszczenie w jednym akapicie

Nieudany przebieg po migracji **nie był spowodowany migracją**. Za exit 1 odpowiadał błąd w samym
`update_brew.sh` (przechwytywanie stderr `brew outdated` jako wartości), a za wszystkie ostrzeżenia
„cask nie jest zainstalowany" — regresja w Homebrew wypuszczona w trakcie Twojego przebiegu.
Migracja ujawniła natomiast trzy inne rzeczy, których nikt wcześniej nie widział: **rozdwojony
toolchain Node** (aktualizowałeś kopie, których nie używasz), **martwy token GitHub w dwóch
plikach profilu + 36 kopiach zapasowych** i **zakleszczoną kwarantannę Microsoft AutoUpdate**,
która blokowała Teams na zawsze.

---

## 1. Analiza ostatniego logu — co się naprawdę stało

### 1.1 🔴 Przyczyna exit 1: przechwycone stderr, nie prawdziwe pakiety

W logu (linia 275):

```
❌ Formulae still outdated after upgrade:
==> Downloading Homebrew API data
✔︎ JSON API packages.arm64_tahoe.jws.json
```

To **nie są nazwy pakietów**. Kod brzmiał:

```bash
if ! REMAINING_FORMULAE=$(brew outdated --formula 2>&1 | strip_ansi); then
```

`2>&1` wciągnęło komunikaty postępu z stderr do zmiennej. Niepusta zmienna = „są nieaktualne
pakiety" → `HARD_FAIL=1` → `BLOCKING_EXIT=1` → **krok 6 (aktualizacje bezpieczeństwa macOS)
pominięty na maszynie, na której wszystko było aktualne**.

To najgroźniejszy z błędów: cichy, powtarzalny i odkłada łatki bezpieczeństwa systemu.

Ten sam wzorzec był w czterech miejscach `update_brew.sh` — w tym w **przed**-sprawdzeniu, gdzie
śmieci z stderr trafiłyby dalej do `brew upgrade --cask $UPGRADEABLE_CASKS` jako nazwy casków.

**Naprawione:** wszystkie cztery miejsca idą teraz przez `brew_outdated_formulae` /
`brew_outdated_casks` w nowym `lib/brew.sh`, które trzymają stderr poza wartością i odfiltrowują
linie postępu. Test `test_brew_outdated_never_merges_stderr_into_value` pilnuje, żeby `2>&1` nie
wróciło.

### 1.2 🔴 `Error: uninitialized constant Cask::CaskLoader` — regresja Homebrew w trakcie przebiegu

Log pokazuje sekwencję krok po kroku:

| Moment | Wersja brew | Efekt |
|---|---|---|
| start kroku 3 | `6.0.18-29-ga2005e5` | snapshot casków **przed** — OK |
| `brew update` w trakcie | → `ad5738cd77` | podciągnął commit „reduce-install-command-load" |
| snapshot casków **po** | `6.0.18-48-gad5738c` | 💥 `uninitialized constant Cask::CaskLoader` |

Zweryfikowane na żywo na Twojej maszynie:

```
$ brew list --cask --versions     → Error: uninitialized constant Cask::CaskLoader
$ brew list --cask                → działa, 12 casków
```

To błąd upstream w Homebrew, nie u Ciebie. Ale przez niego:

- nie zapisał się posnapshot casków → `SOFT_FAIL=1`
- `update_internet_apps.sh` zgłosił **11 aplikacji** jako „Config mówi brew_cask, ale cask nie jest
  zainstalowany" — Brave, Perplexity, LM Studio, ProtonVPN, Zoom, MEGAsync, AppCleaner, Obsidian,
  Spotify, CapCut, Inkscape. **Wszystkie 11 było zainstalowanych.** Lista casków to dokładnie te 11
  plus `blackhole-2ch`.

**Naprawione:** `brew_cask_versions()` w `lib/brew.sh` — próbuje `brew list --cask --versions`, a gdy
to zawiedzie, składa wynik z `brew list --cask` + układu `$(brew --prefix)/Caskroom/<token>/<wersja>`,
który nie zmienił się od lat. Podpięte we wszystkich 5 miejscach wywołań (`update_brew.sh` ×3,
`update_internet_apps.sh`, `update_all.sh` bash + Python prescan, `migration_setup.sh`).
Test `test_no_raw_brew_cask_versions_call` blokuje powrót surowego wywołania.

### 1.3 🟡 Fałszywy baner sukcesu

Log linia 470–473:

```
║  ✅ SKRYPT 4 ZAKOŃCZONY POMYŚLNIE               ║
  ❌ Homebrew finished with errors or soft warnings.
```

Nagłówek drukował się bezwarunkowo, tuż nad komunikatem o błędzie — czyli dokładnie tam, gdzie
czytelnik szuka przyczyny. Dodatkowo miękkie ostrzeżenia (exit 10) dostawały ten sam czerwony
tekst co twarde awarie. **Naprawione** — baner tylko przy exit 0, osobny komunikat dla soft/hard.

### 1.4 Pozostałe wpisy z logu — werdykt

| Wpis | Werdykt |
|---|---|
| `bun upgrade zakończony ostrzeżeniem` | Przejściowe. Fallback zadziałał, downgrade zablokowany. Po naprawie PATH już nie występuje. |
| `Trezor Suite: Brak połączenia z GitHub` | **Nie awaria sieci.** Limit GitHub API 60 req/h dla zapytań bez autoryzacji — `GITHUB_TOKEN` wskazywał na martwy token (§3.2). Po ponownym przebiegu: ✅ Aktualny (26.7.4). |
| `mas account` nie działa | Znany problem macOS 26.x, obsłużony fallbackiem przez `mas list`. Bez akcji. |
| `Microsoft AutoUpdate: Wstrzymany` | Realny problem — §4. |
| `GarageBand` jako nowa aplikacja | Poprawne wykrycie, dodane do APPLICATIONS.md. |

---

## 2. ChatGPT Atlas — usunięty

Potwierdzone, że `.app` nie ma na dysku. Wyczyszczone **każde** żywe wystąpienie:

| Plik | Co usunięto |
|---|---|
| `config/internet_apps.txt` | wpis `ChatGPT Atlas` |
| `config/internet_app_methods.txt` | `ChatGPT Atlas\|sparkle_appcast\|STATUS_ATLAS` |
| `config/internet_dispatch_order.txt` | `iu_chatgpt_atlas` → komentarz-nagrobek z datą |
| `lib/internet_app_updates.sh` | cała funkcja `iu_chatgpt_atlas()` (sekcja 4b) |
| `lib/internet_apps.sh` | gałąź `case` w `internet_app_path` |
| `update_internet_apps.sh` | `STATUS_ATLAS` — inicjalizacja, wiersz podsumowania, wpis w pętli klasyfikacji |
| `scripts/report_update_coverage.sh` | alias + `com.openai.atlas` |
| `scripts/audit_cask_candidates.sh` | gałąź `case` |
| `APPLICATIONS.md`, `UPDATES.md` | notatki i sekcja instrukcji ręcznej |
| `README.pl.md`, `docs/agents/*` | wzmianki w tabelach metod |

Historyczne wpisy w tabelach sesji `UPDATES.md` zostawione — to zapis historii, nie konfiguracja.

Stary test `test_chatgpt_atlas_ignores_codex_bundle` zastąpiony testem
`test_chatgpt_atlas_fully_removed`, który sprawdza, że **żadna** żywa powierzchnia nie odwołuje
się do Atlasa. Połowiczne usunięcie byłoby gorsze niż zostawienie: config deklarowałby zmienną
statusu, której nikt nie ustawia, a pętla klasyfikacji porównywałaby pusty string ze stałymi błędów.

Raport pokrycia potwierdza: **„Obsługiwane przez projekt, ale NIE zainstalowane: 0"**.

---

## 3. Migracja na nowy MacBook — co znalazłem

### 3.1 🔴 Rozdwojony toolchain Node — aktualizowałeś kopie, których nie używasz

To jest największe znalezisko całego przeglądu i **bez migracji nigdy by nie wyszło**.

`ensure_toolchain_paths()` oddawał władzę nad Node/npm do nvm, gdy tylko `~/.nvm/nvm.sh` **istniał**
— ale nadal instalował globalne CLI do `~/.local/share/mac-update/`. Na ten katalog nie wskazywało
nic w Twoim interaktywnym `PATH`. Efekt zmierzony przed naprawą:

| Narzędzie | Co uruchamiałeś (nvm) | Co skrypt „zaktualizował" |
|---|---|---|
| node | v24.13.0 | **v26.7.0** |
| npm | 11.13.0 | **12.0.2** |
| pnpm | 11.2.2 | **11.22.0** |
| codex | 0.147.0 | **0.148.0** |
| opencode | 1.17.18 | **1.18.18** |
| claude | 2.1.235 | 2.1.235 (zbieżność) |

`update_all.sh` codziennie raportował te CLI na zielono. Twój terminal codziennie startował starsze.

**Naprawione** (Twoja decyzja: toolkit przejmuje PATH). Zarządzany prefiks jest teraz domyślnie
pierwszy; stare zachowanie jest za jawną furtką `MAC_UPDATE_NVM_OWNS_NODE=1`. `nvm.sh` nadal się
ładuje, więc `nvm use` działa świadomie. Zweryfikowane w świeżej powłoce logowania — wszystkie
osiem narzędzi rozwiązuje się teraz do zarządzanego prefiksu.

### 3.2 🔴 Token GitHub w otwartym tekście — w dwóch plikach i 36 kopiach

Znalezione i **usunięte**:

- `~/.zshrc` — `export GITHUB_TOKEN="ghp_…"`
- `~/.zshenv` — ten sam token (to ten „działający", bo `.zshenv` ładuje się też dla procesów
  nieinteraktywnych, stąd MCP GitHub w Claude Code go widział)
- **36 plików** `~/.zshrc.macupd-backup-*` — każdy z zamrożoną kopią tokenu

Token zwraca z GitHub API **401 Bad credentials** — jest martwy (odwołany, wygasły albo unieważniony
przez GitHub Secret Scanning). Dlatego nie da się z niego odczytać konta właściciela.

Zastąpione ładowaniem z `~/.config/secrets/github.env` (chmod 600, katalog 700) w obu plikach.
Plik utworzony z pustym placeholderem — **wygeneruj nowy token i wklej go tam**, nic więcej nie
trzeba zmieniać.

Dlaczego `run_tests.sh` tego nie złapał: `scripts/scan_secrets.sh` uruchamia gitleaks, a gitleaks
skanuje **wyłącznie treść śledzoną przez git**. Pliki profilu są poza repo, więc cały pakiet testów
był na nie ślepy. **Dodane:** doradczy (nigdy nie blokujący) skan plików profilu, wyłączalny przez
`MAC_UPDATE_SKIP_PROFILE_SCAN=1` — nie może wywrócić CI, gdzie żadnych profili nie ma.

**Dodane:** rotacja kopii profilu. `declare_profile_backup` zostawiał jedną kopię na każdy przebieg
i nigdy nie kasował — stąd 36. Teraz `chmod 600` + zachowanie najnowszych
`MAC_UPDATE_MAX_PROFILE_BACKUPS` (domyślnie 5).

### 3.3 ✅ Co po migracji jest w porządku

| Element | Stan |
|---|---|
| Homebrew, mas 7.0.0, python3, git, gh, gitleaks, shellcheck, ruff, jq | zainstalowane |
| Touch ID dla sudo (`/etc/pam.d/sudo_local`) | aktywne |
| Konfiguracje MCP (6 plików) | `fix_mcp_all.sh` — „No changes needed" dla wszystkich |
| `dev_sync` → Proton Drive | ścieżka istnieje, `rclone` niepotrzebny (`MAC_CLOUD_RCLONE_REMOTE` puste) |
| Repo git | czyste przed zmianami, gałąź `main`, gitleaks bez znalezisk (92 commity) |
| Pokrycie aktualizacji | 62/65 = **95.4%**, znane pokrycie 98.5% |

### 3.4 Czego brakuje / do decyzji

| Element | Uwaga |
|---|---|
| **LaunchAgent** | Nie zainstalowany. Jeśli na starym Macu miałeś harmonogram: `bash scripts/install_launchagent.sh --day 1 --hour 9`. |
| **Puste pakiety npm** | `@google` i `@qwen-code` — puste katalogi po migracji, usunięte. |
| **Duplikaty chmur** | `ProtonDrive-mk@itcs.pl-folder (19-08-2026 14:05)` i `GoogleDrive-m.kasprowicz@gmail.com (19-08-2026 14:02)` — drugie montowania z dzisiejszej migracji. `dev_sync` wskazuje na właściwe (bez sufiksu). Warto sprawdzić w Finderze, czy nie dublują danych. |
| **`FIREFOX_DEV_CHANNEL_VERSION=150.0b10`** w `.mac_update_prefs` | Martwy klucz — nic w kodzie go nie czyta, a zainstalowany Firefox to 155.0. Zostawiony, bo to Twój plik konfiguracyjny. |
| **`Ascendo.app`** | Nadal w `/Applications`, celowo w `config/inventory_exclusions.txt`. Jedyna aplikacja bez pokrycia. |

---

## 4. 🔴 Microsoft AutoUpdate — zakleszczona kwarantanna (Teams zablokowany na zawsze)

To znalezisko wymagało wejścia w kod, bo objaw („⚠️ Wstrzymany — błąd pakietu dostawcy") wygląda
jak normalne działanie zabezpieczenia.

Stan zastany w `com.microsoft.autoupdate2`:

```
DeferralDays     = { MSWD2019=7, XCEL2019=7, PPT32019=7, OPIM2019=7, ONMC2019=7 }
DeferralVersions = { TEAMS21 = "26213.1006.5011.1671" }
Zainstalowany Teams                     26213.1006.5011.1671   ← identyczny
```

`DeferralVersions` przypina **maksymalną** wersję, jaką MAU kiedykolwiek zaoferuje. Przypięta do
zainstalowanego builda = **Teams nie zaktualizuje się nigdy**.

Kod ma na to `MAU_STALE_DEFERRAL_VERSION_IDS="TEAMS21"` i `mau_clean_stale_deferrals()`, które to
usuwają. Ale zakleszczenie było takie:

```
aktywne DeferralDays  →  produkty ukryte przed msupdate --list
                      →  MAU_COUNT = 0
                      →  gałąź "$MAU_COUNT -gt 0" nieosiągnięta
                      →  mau_reconcile_deferrals() nigdy nie wywołane
                      →  mau_clean_stale_deferrals() nigdy nie wywołane
                      →  pin TEAMS21 zostaje  →  i tak w kółko, każdy przebieg
```

**Naprawione:** w gałęzi „nic nie zaoferowano" wywoływane jest teraz
`mau_reconcile_deferrals "" ""`. Przy pustym zbiorze ofert lista zwolnień Office pozostaje pusta
(kwarantanna Office trwa nietknięta, zgodnie z projektem), ale przestarzałe piny wersji — które są
bezwarunkowo błędne — zostają zdjęte. Potwierdzone w przebiegu:

```
✅ Zwolniono odroczenia Microsoft AutoUpdate: DeferralVersions.TEAMS21
```

### Co zostaje do Twojej decyzji

Kwarantanna 5 aplikacji Office (`DeferralDays=7`) **stoi celowo** — to zabezpieczenie po regresji
pakietu Office Preview z 2026-07-14. Będzie zgłaszać miękkie ostrzeżenie przy każdym przebiegu,
dopóki nie zostanie zwolniona na podstawie pozytywnego dowodu z feedu.

Źródłem problemu jest kanał: **`ChannelName = Preview`**, a Office jest zbudowany dla `Current`.
Masz dwie drogi:

1. **Przełączyć MAU na Production/Current** — usuwa przyczynę na stałe. To ustawienie Twojego
   Office, więc nie ruszałem go bez pytania.
2. **Jednorazowo zwolnić kwarantannę** i zobaczyć, czy feed się naprawił:
   `MAC_UPDATE_MAU_CLEAR_DEFERRALS=1 bash update_all.sh`. Jeśli MAU znów zaoferuje downgrade,
   toolkit sam uzbroi kwarantannę z powrotem przy następnym przebiegu.

---

## 5. Natywne aktualizatory CLI — zrobione, z jedną pułapką

Zgodnie z prośbą `claude-code` i `codex-cli` przeszły z `npm install -g …@latest` na własne
aktualizatory, dołączając do `agy-cli`:

```
claude-code|@anthropic-ai/claude-code|self-update||claude     → claude update
codex-cli|@openai/codex|self-update||codex                    → codex update
agy-cli|agy|self-update||agy                                  → agy update       (już było)
```

Reszta bez zmian (`node` przez `n`, `npm`/`pnpm`/`opencode` przez npm, `bun` przez `bun upgrade`).

**Pułapka, którą wykryłem testując na żywo:** `codex update` wywołuje wewnętrznie gołe
`npm install -g @openai/codex`. Skonfigurowany prefiks npm na tej maszynie to prefiks **node**
(`~/.local/share/mac-update/node`), a nie zarządzany `npm-global` — a `npm-global/bin` wygrywa w
PATH. Bez zabezpieczenia `codex update` instalował **przesłoniętą kopię**, meldował sukces i
zostawiał starą binarkę nadal wygrywającą `command -v`. Zweryfikowałem to eksperymentalnie
(powstał duplikat w `node/lib/node_modules/@openai/codex`, który następnie usunąłem).

**Naprawione:** gałąź `self-update` uruchamia aktualizator w podpowłoce z przypiętym
`npm_config_prefix` / `NPM_CONFIG_PREFIX` na zarządzany prefiks. Test
`test_self_update_pins_npm_prefix` tego pilnuje.

Zweryfikowany przebieg na żywo:

```
ℹ️  Aktualizuję claude-code przez własny updater (claude update)...   ✅ 2.1.235
ℹ️  Aktualizuję codex-cli przez własny updater (codex update)...      ✅ 0.148.0
ℹ️  Aktualizuję agy-cli przez własny updater (agy update)...          ✅ 1.1.15
```

---

## 6. Higiena projektu — pozostałe poprawki

| Znalezisko | Akcja |
|---|---|
| `APPLICATIONS.md` — 14 tabel w GRUPIE 3 miało wiersz separatora bez wiersza nagłówka → nie renderowały się jako tabele | Nagłówki przywrócone; potwierdzone, że przebieg ich nie kasuje |
| `~/.zshrc` — 8× ta sama linia PATH Antigravity, 3× Python 3.9, 2× brew shellenv, 2× `source agentic.zsh` | Zdeduplikowane (zachowane **ostatnie** wystąpienia, żeby końcowa kolejność PATH była identyczna co do bajtu — zweryfikowane); 92 → 64 linii |
| Wersja rozjechana: `VERSION`=1.4.0, `CLAUDE.md`=1.3.1, `CODEX.md`=1.3.1, dokumentacja użytkownika ×15 = 1.0.21 | Wszystko ujednolicone na **1.4.1** |
| Brak dokumentacji nowych trybów awarii | `docs/agents/troubleshooting.md` — 4 nowe wiersze; zaktualizowane `architecture.md`, `critical_rules.md`, `scripts.md` |
| CHANGELOG | Wpis 1.4.1 z pełnym opisem przyczyn źródłowych |

---

## 7. Stan końcowy — weryfikacja

```
bash run_tests.sh
  ✅ all bash scripts parse
  ✅ all python modules compile
  ✅ all inline heredoc python blocks compile
  Ran 170 tests — OK          (było 160; +10 nowych testów regresji)
  ✅ secret scan passed
  ║   ALL CHECKS PASSED ✅   ║

shellcheck (zmienione pliki)  → tylko info/style, zero błędów
bash update_all.sh --dry-run  → OK
bash update_all.sh --yes      → exit_code 0, blocking_exit 0
```

Porównanie przebiegów:

| | 17:35 (przed) | 18:42 (po) |
|---|---|---|
| exit_code | **1** | **0** |
| blocking_exit | **1** | **0** |
| Homebrew | ❌ Błąd | ✅ OK completed |
| Krok macOS | ⏭️ **pominięty** | wykonywalny (pominięty tylko flagą `--skip-system`) |
| Ostrzeżenia „cask nie zainstalowany" | **11** | **0** |
| Trezor Suite | ⚠️ Brak połączenia | ✅ Aktualny |
| Czas trwania | 13m 45s | 2m 01s |

Jedyne pozostałe ostrzeżenie to celowa kwarantanna Office (§4) — miękkie, nieblokujące z definicji.

### Nowe testy regresji (10)

`test_no_raw_brew_cask_versions_call` · `test_brew_lib_is_sourced_by_cask_consumers` ·
`test_brew_outdated_never_merges_stderr_into_value` · `test_brew_lib_helpers_exist_and_filter_progress_lines` ·
`test_self_update_pins_npm_prefix` · `test_native_self_update_clis_configured` ·
`test_managed_toolchain_wins_path_by_default` · `test_profile_backups_are_rotated_and_locked_down` ·
`test_secret_scan_profile_advisory_is_never_fatal` · `test_mau_empty_list_still_clears_stale_version_pins` ·
`test_chatgpt_atlas_fully_removed`

---

## 8. Co robisz teraz

**Pilne**
1. Wygeneruj nowy token GitHub → wklej do `~/.config/secrets/github.env`. Bez niego zapytania do
   GitHub API lecą na limicie 60/h i `Trezor Suite` / `KeePassXC` / `Ledger` będą losowo zgłaszać
   brak połączenia.

**Decyzje**
2. Kanał Microsoft AutoUpdate: `Preview` → `Current`? (§4)
3. LaunchAgent (harmonogram automatyczny) — instalować? (§3.4)
4. Commit — 42 zmienione pliki + `lib/brew.sh` czekają niezacommitowane. Powiedz słowo, zrobię commit.

**Weryfikacja po Twojej stronie**
5. Otwórz **nowy** terminal i sprawdź: `command -v node npm claude codex` — wszystko powinno
   wskazywać na `~/.local/share/mac-update/…`.
6. Odpal pełny `bash update_all.sh` (bez `--skip-system`) — krok 6 jest jedynym, którego nie
   uruchamiałem, żeby nie zrestartować Ci Maca w trakcie pracy. Jego kod nie był zmieniany.

---

*Wygenerowane przez Claude Opus 5 · macOS Updates v1.4.1 · 2026-08-19*
