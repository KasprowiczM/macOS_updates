# Opus5 Max — Ultra Review v6 · macOS Updates v1.3.1

**Data:** 2026-08-12 · **HEAD:** `dd3c7d5` · **Gałąź:** `main` · **Working tree:** czysty
**Poprzednik:** `ultra_review_opus5_v5.md` (2026-07-30) i seria `ULTRA_REVIEW_2026-08-05_v1..v5` + `ULTRA_REVIEW_FINAL_v1.3.1.md`
**Numeracja:** kontynuacja linii `ultra_review_opus5_v1..v5` → **v6**

**Metoda:** audyt read-only całego drzewa (bez uruchamiania niczego na Macu). `bash -n` na 40 skryptach — 0 błędów. Weryfikacja przez lekturę źródeł + odpytanie oficjalnej dokumentacji Anthropic dla zadania A i dokumentacji Homebrew dla H-2.

**Czego NIE czytałem (zgodnie z `docs/agents/security.md`):** `.env`, `.dev_sync_config.json`, `dev_sync_logs/`, `UPDATES.md`. **Wyjątek:** `APPLICATIONS.md` — otworzyłem wyłącznie fragment dotyczący Ascendo (wyraźne polecenie) oraz policzyłem strukturę tabel (bez odczytu nazw aplikacji). Żadna zawartość inwentarza nie trafiła do tego dokumentu poza wierszami Ascendo.

**Czego NIE mogłem wykonać:** sandbox to Linux/Bash 5.1/Python 3.10 — nie ma `brew`, `mas`, `defaults`, `softwareupdate`, `shellcheck` ani Bash 3.2. Każde twierdzenie oparte na zachowaniu runtime jest niżej oznaczone jako **[do potwierdzenia jedną komendą]** wraz z tą komendą.

---

## 1. Werdykt i punktacja

### **7.9 / 10 — produkcyjnie zdatny, jeszcze nie produkcyjnie autonomiczny**

To nie jest cofnięcie oceny 8.6 z `ULTRA_REVIEW_FINAL_v1.3.1.md`. Tamta ocena była trafna dla pytania *„czy to działa, gdy człowiek siedzi przy terminalu?"*. Ten przegląd mierzy inne pytanie — to, które postawiłeś: *„czy po jednym uruchomieniu wszystko jest najświeższe, bez nadzoru?"*. Przy tej poprzeczce trzy klasy defektów, których poprzednie rundy nie testowały, obniżają wynik.

| Obszar | v1.3.1 (self) | **v6 (Opus5 Max)** | Uzasadnienie zmiany |
|---|---|---|---|
| Architektura pipeline'u | 9 | **9** | Kontrakt severity 0/10/1 z macierzą blokowania nadal najlepszy element projektu |
| Bezpieczeństwo | 9 | **9** | Weryfikacja podpisu i Team ID, atomowe zapisy, brak passwordless sudo — bez zastrzeżeń |
| Pokrycie / świeżość aktualizacji | 8 | **7** ↓ | 21 zweryfikowanych, ale **zero pomiaru opóźnienia źródeł**; wybór metody per aplikacja jest deklaracją, nie pomiarem |
| Bezobsługowość | 9 | **6** ↓↓ | `update_system.sh` ignoruje `MAC_UPDATE_NO_SUDO`; LaunchAgent **nigdy** nie instaluje aktualizacji macOS (H-1, H-3) |
| Integralność inwentarza | 9 | **6** ↓↓ | 14 z 22 tabel w `APPLICATIONS.md` bez wiersza nagłówka; brak jakiejkolwiek listy wykluczeń (H-4, M-3) |
| Jakość testów | 9 | **8** ↓ | 150 testów, świetne strażniki klas — ale `update_system.sh` jest poza kontraktem severity **i poza testami** |
| Uczciwość raportowania | 9 | **9** | Bez zmian; `silent_launch` z realną weryfikacją jest wręcz **niedoszacowany** w metryce |
| Dokumentacja | 9 | **9** | 7 języków, 671 kluczy w parytecie, `docs/agents/` zgodne z kodem |
| Wydajność | — | **6** | 34 startów `python3` na przebieg, pętla settle O(sekundy×apps×odczyt-configu), zero równoległości I/O (P-1..P-7) |
| Dług techniczny | 6 | **7** ↑ | **H4 z v5 jest praktycznie zamknięty:** heredoc Pythona w `update_all.sh` skurczył się z 1121 do **86 linii**. `lib/internet_app_updates.sh` = 1710 linii — nadal duży, ale nie krytyczny |

**Średnia: 7.9**

### Co to znaczy w jednym zdaniu

Kod jest napisany lepiej niż większość komercyjnych narzędzi tej klasy — kontrakt severity, weryfikacja podpisów przed podmianą bundla i strażniki testowe „metoda bez handlera" to poziom, którego zwykle się nie widuje. Ale **ścieżka bezobsługowa jest zamknięta na ostatnim metrze**: zaplanowany przebieg z premedytacją pomija aktualizacje systemu, a przebieg bez TTY trafia na `sudo` w kroku 6, który nie zna kontraktu ustalonego dla wszystkich pozostałych kroków.

---

## 2. Co jest już zrobione — **nie powtarzaj tego**

Zweryfikowałem, że wszystkie poniższe pozycje z poprzednich rund są **realnie w kodzie**, nie tylko zadeklarowane:

| Pozycja | Runda | Dowód w kodzie (v6) |
|---|---|---|
| `softwareupdate -ia -R` | v1 | `update_system.sh:86,149,159` — 3 wystąpienia, `-R` obecne |
| `sudo mas upgrade` | v1 | `update_appstore.sh:253` — `sudo -n env MAS_NO_AUTO_INDEX=1 mas upgrade` |
| Jeden punkt akwizycji sudo, brak `sudo` bez TTY | 08-05 | `update_all.sh:211-248` — **poprawne w orkiestratorze** (patrz jednak H-1) |
| Keep-alive startowany raz, PID przed startem | 08-05 | `update_all.sh:245-246` + `cleanup_session_dir:257-264` |
| `print_header` w `lib/ui.sh` | v5/X1 | `test_orchestrators_all_print_functions_defined` (`tests:1237`) — klasa zamknięta |
| Strażnik „metoda w configu bez handlera" | v1.1.0 | `test_every_config_method_has_a_handler` (`tests:668`) |
| Zabezpieczenie przed downgrade'em casków | v1.2.0→1.3.1 | `update_brew.sh:236-289`, `--json=v2`, `artifacts[].app`, właściwa kolejność argumentów |
| `keystone` zawężony do produktów Google | 08-05 | `config/internet_app_methods.txt` — tylko Chrome i Google Drive |
| Weryfikacja oportunistyczna w `silent_launch` | 08-05 | `lib/internet_handlers.sh:158-199` (+ `internet_feed_source:55`) → `internet_handler_vendor_latest` |
| `INTERNET_LAST_STATUS` jako globalna, nie stdout | 08-05 | `lib/internet_handlers.sh:11` + testy 1645/1657 |
| Kwarantanna regresji MAU | 1.3.0 | `mau_regressed_entries` / `mau_reconcile_deferrals` + 8 testów |
| Lista settle budowana z configu | 08-05 | `update_internet_apps.sh:475-489` + `test_settle_list_generated_from_config` |
| **H4 — Python w heredocach** | v5 (otwarty) | **Faktycznie zamknięty:** 2 bloki, 86 linii razem (`update_all.sh:1007`, `:1781`). Rule 4 nadal wskazuje `lib/python/`, ale ten katalog **nie istnieje** — patrz L-1 |

**Wniosek:** nie ma sensu ponownie audytować sudo w `update_all.sh`, downgrade'u casków, kontraktu severity dla `update_brew/appstore/npm_cli`, ani MAU. To działa.

---

## 3. Nowe ustalenia

Numeracja: **H** = high, **M** = medium, **L** = low, **P** = performance.

---

### H-1 · `update_system.sh` nie zna kontraktu sudo ani kontraktu severity — **HIGH**

**Fakt.** `MAC_UPDATE_NO_SUDO` jest konsumowane **dokładnie w jednym miejscu**:

```
$ grep -rn "MAC_UPDATE_NO_SUDO" --include="*.sh" .
update_appstore.sh:247:  if [ "${MAC_UPDATE_NO_SUDO:-0}" = "1" ] || { [ ! -t 0 ] && ! sudo -n true; }; then
update_all.sh:222:       export MAC_UPDATE_NO_SUDO=1
lib/cli.sh:29:           MAC_UPDATE_NO_SUDO_KEEPALIVE=1     ← inna zmienna
```

`update_system.sh` **nie występuje na tej liście**, a wywołuje `sudo` bezwarunkowo:

```
update_system.sh:149:  if sudo softwareupdate -ia -R --verbose; then
update_system.sh:159:  if sudo softwareupdate -ia -R --verbose; then
```

**Dlaczego to boli.** `update_all.sh:220-224` w gałęzi bez TTY świadomie **nie robi** `sudo -v`, eksportuje `MAC_UPDATE_NO_SUDO=1` i ustawia `_needs_sudo=0`. Krok 6 mimo to się wykonuje (jest bramkowany wyłącznie przez `SKIP_SYSTEM` i `BLOCKING_EXIT`, `update_all.sh:1761-1774`). Efekt zależy od konfiguracji PAM:

- **Bez Touch ID:** `sudo: no tty present and no askpass program specified` → exit 1 → `RESULT_SYSTEM=❌`, `OVERALL_EXIT=1`. Zdrowy przebieg raportowany jako awaria.
- **Z Touch ID** (a `scripts/setup_touchid_sudo.sh` sam go instaluje!): `pam_tid.so` uwierzytelnia **bez TTY** → wyskakuje okno Touch ID. To dosłownie objaw opisany w `docs/agents/critical_rules.md` §6c jako naprawiony.

Naprawiono go w `update_all.sh` i `update_appstore.sh`. **Krok 6 został pominięty.**

**Drugi defekt tego samego pliku.** `update_system.sh` jako jedyny skrypt `update_*.sh` **nie ładuje `lib/severity.sh`**:

```
$ grep -ln "lib/severity.sh" *.sh
update_appstore.sh
update_brew.sh
update_npm_cli.sh          ← update_system.sh i update_internet_apps.sh nieobecne
```

`update_internet_apps.sh` ma własny mechanizm (`INTERNET_SOFT_EXIT`), więc kontrakt spełnia. `update_system.sh` **nie ma żadnego** — każda porażka to exit 1. Chwilowy brak sieci przy `softwareupdate -l` (linia 71-77) → twardy błąd → cały przebieg oznaczony „COMPLETED WITH ERRORS".

**Dlaczego testy tego nie złapały.** `test_leaf_scripts_source_severity_and_have_soft_exit_path` (`tests:1053`) iteruje po liście `["update_brew.sh", "update_appstore.sh", "update_npm_cli.sh"]`. `update_system.sh` nie jest na liście. `test_appstore_skips_track1_without_tty` (`tests:1830`) nie ma odpowiednika dla systemu. Luka jest w **doborze zakresu testu**, nie w asercji.

**Poprawka:** zadanie **A3**.

---

### H-2 · Jedna przypięta formuła Homebrew blokuje aktualizacje bezpieczeństwa macOS na zawsze — **HIGH**

**Fakt (kod).** `update_brew.sh:305-313`:

```bash
if ! REMAINING_FORMULAE=$(brew outdated --formula 2>&1 | strip_ansi); then
    ...SOFT_FAIL=1
elif [ -n "$REMAINING_FORMULAE" ]; then
    print_error "Formulae still outdated after upgrade:"
    HARD_FAIL=1          # ← exit 1
fi
```

`HARD_FAIL=1` (linia 312) → `mac_update_severity_exit_code` → `1` → `update_all.sh:1195-1197` ustawia `OVERALL_EXIT=1` **i `BLOCKING_EXIT=1`** → `update_all.sh:1766-1769` pomija krok 6.

**Fakt (Homebrew).** `brew outdated` **wypisuje** formuły przypięte, a `brew upgrade` je **pomija** — to zamierzone zachowanie `brew pin`. Potwierdzone w dokumentacji Homebrew (patrz Źródła).

**Konsekwencja.** Wystarczy jedna komenda `brew pin <cokolwiek>` kiedykolwiek w przeszłości i od tej chwili **każdy** przebieg kończy się twardą awarią Homebrew, a `softwareupdate -ia -R` nie uruchamia się **nigdy**. Narzędzie, którego celem jest aktualność, cicho przestaje instalować łatki bezpieczeństwa systemu — i wygląda przy tym na uszkodzone, więc użytkownik przestaje ufać czerwonemu statusowi.

To ta sama rodzina co regresja z 2026-07-26 opisana w `critical_rules.md` §10: *stan, którego nie da się naprawić, blokuje aktualizacje systemu*.

**[Do potwierdzenia jedną komendą]** `brew list --pinned`. Pusty wynik = defekt utajony, nie aktywny. Niepusty = aktywny **dziś**.

**Ta sama klasa, drugi przypadek.** Formuła, której `brew upgrade` nie może podnieść z powodu braku bottle dla bieżącego macOS (buduje ze źródeł i pada), również zostaje w `brew outdated` na stałe. Filtr musi obsłużyć oba.

**Poprawka:** zadanie **A4**.

---

### H-3 · Zaplanowany przebieg z definicji nie aktualizuje macOS — **HIGH (projektowy)**

`scripts/install_launchagent.sh:93-99` generuje plist z:

```xml
<string>${SCRIPT_DIR}/update_all.sh</string>
<string>-y</string>
<string>--skip-system</string>
```

Cotygodniowy, bezobsługowy przebieg **zawsze** pomija krok 6. To jest sensowna decyzja obronna (launchd nie ma TTY — patrz H-1) i nawet racjonalna (nie chcesz restartu o 9:00 w poniedziałek), ale nigdzie nie jest to powiedziane użytkownikowi wprost: ani w `docs/agents/exit_codes.md`, ani w `README*`, ani w komunikacie samego skryptu instalującego. Użytkownik, który włączył harmonogram, ma pełne prawo sądzić, że system też jest pilnowany.

W połączeniu z H-1 to jest **pełna dziura**: harmonogram nie robi systemu z premedytacją, a ręczne uruchomienie bez TTY albo pada, albo prosi o Touch ID.

**Poprawka:** zadanie **A5** — rozdzielenie harmonogramu na dwa i jawna deklaracja w UI.

---

### H-4 · Brak mechanizmu wykluczeń — usunięta aplikacja wraca przy następnym przebiegu — **HIGH**

**Fakt.** W całym repozytorium nie istnieje żadna lista ignorowanych aplikacji. Prescan (`update_all.sh:542-552`, snapshot do `installed_apps_after.txt` w `:580`) robi:

```python
for applications_dir in ('/Applications', os.path.expanduser('~/Applications')):
    for item in os.listdir(applications_dir):
        if item.endswith('.app'):
            installed_app_paths.setdefault(item[:-4], ...)
```

…po czym dopisuje wszystko, czego nie ma w GRUPACH 1–3, do `APPLICATIONS.md`. `build_inventory.sh` to ten sam kod (`exec bash update_all.sh` z `MAC_UPDATE_INVENTORY_ONLY=1`).

**Konsekwencja dla Twojego polecenia.** Skreślenie Ascendo z pięciu plików konfiguracyjnych zatrzyma jego *aktualizowanie i uruchamianie* — ale przy pierwszym `build_inventory.sh` albo pierwszym pełnym przebiegu prescan zobaczy `/Applications/Ascendo.app` i **wpisze go z powrotem** do inwentarza jako nową aplikację. Za tydzień pojawi się w raporcie pokrycia jako `unknown` i ktoś (albo agent) „naprawi" to, dodając handler.

Dlatego zadanie B nie może być usunięciem pięciu linii. Musi wprowadzić `config/ignored_apps.txt` jako pierwszorzędny artefakt honorowany przez prescan, postupdate, rejestr internetowy i raport pokrycia. To jest jednocześnie funkcja, której projekt i tak potrzebuje — każdy użytkownik ma aplikacje pisane samodzielnie albo zarządzane przez pracodawcę.

**Poprawka:** zadanie **B**.

---

### M-1 · `TEE_PID` jest przypisywany z `$!`, którego Bash 3.2 nie ustawia dla podstawienia procesu — **MEDIUM**

`update_all.sh:243-255`:

```bash
( while true; do sudo -n true || exit 0; sleep 50; done ) &
SUDO_KEEPALIVE_PID=$!          # :246
...
exec 3>&1 4>&2                 # :253
exec > >(tee -a "$LOG_FILE") 2>&1   # :254
TEE_PID=$!                     # :255  ← Bash 3.2 nie ustawia tu $!
```

`ultra_review_opus5_v5.md` §1 stwierdza wprost: *„Bash 3.2 does not set `$!` for a process substitution"* — i na tej podstawie zdyskwalifikował weryfikację P1 wykonaną przez Gemini na Bash 3.2.57. Ta sama własność sprawia, że **na `/bin/bash` z macOS** `TEE_PID` dziedziczy poprzednią wartość `$!`, czyli **PID procesu keep-alive** (gdy sudo było pozyskane) albo pusty łańcuch (gdy nie było — np. `--dry-run`).

Skutek nie jest zawieszeniem: `cleanup_session_dir` zabija i „żni" keep-alive **zanim** dojdzie do `wait "$TEE_PID"` (`:315`), więc `wait` pada natychmiast i jest połknięte przez `|| true`. Skutek jest subtelniejszy i gorszy dla diagnostyki: **`tee` nie jest nigdy oczekiwane, więc gwarancja „diagnostyka trapu dociera na dysk" — cały cel poprawki M19/P1 — nie obowiązuje na powłoce, którą macOS faktycznie dostarcza.** Zachowanie różni się między Bash 3.2 a 5.x, a testy chodzą na tej drugiej.

`test_update_all_does_not_hang_on_tee_wait` (`tests:1231`) sprawdza wyłącznie „nie zawiesza się i kod wyjścia = 0". Przechodzi w obu wariantach, bo brak zawieszenia to *skutek uboczny* błędu, nie dowód poprawności.

**Poprawka deterministyczna, niezależna od wersji powłoki** — FIFO zamiast podstawienia procesu:

```bash
exec 3>&1 4>&2
LOG_FIFO="$SESSION_DIR/log.fifo"
mkfifo -m 600 "$LOG_FIFO" || { ...; }
tee -a "$LOG_FILE" < "$LOG_FIFO" &
TEE_PID=$!                       # zwykłe zadanie w tle — $! ustawione w KAŻDYM bashu
exec > "$LOG_FIFO" 2>&1
```

**Poprawka:** zadanie **A6**.

**[Do potwierdzenia jedną komendą]** `/bin/bash -c 'true & : > >(cat); echo $!'` na Macu — porównaj z PID-em zadania w tle.

---

### M-2 · Kolejność rozwiązywania ścieżek stawia npm przed instalatorem natywnym — **MEDIUM** (blokuje zadanie A)

Dwa niezależne miejsca szukają `claude` najpierw w prefiksie npm:

`update_npm_cli.sh:327-331`
```bash
npm|pnpm|claude|codex|opencode)
    if [ -x "$NPM_GLOBAL_BIN/$command_name" ]; then   # ← npm wygrywa
```

`update_all.sh:1022-1027` (heredoc snapshotu CLI)
```python
roots = [ npm-global/bin, node/bin, ~/.local/bin, ~/.bun/bin ]   # ← npm wygrywa
```

Instalator natywny Claude Code trzyma launcher w `~/.local/bin/claude`, a wersje w `~/.local/share/claude/versions/`. Dopóki pozostaje choćby resztka po instalacji npm, obie funkcje zwrócą binarkę npm i `claude update` zadziała na niewłaściwej instalacji, a snapshot wersji pokaże niewłaściwą liczbę. To trzeba naprawić **przed** przełączeniem metody, inaczej zadanie A wygląda na wykonane i nic nie robi.

**Poprawka:** zadanie **A1c**.

---

### M-3 · 14 z 22 tabel w `APPLICATIONS.md` nie ma wiersza nagłówka — **MEDIUM**

Kontrola strukturalna (bez odczytu nazw aplikacji):

```
separator rows WITH header:                     8
separator rows WITHOUT header (broken table):  14
```

Wzorzec: sekcja `### …` → pusta linia → **od razu** `|-------|--------|---------------------|` bez poprzedzającego `| Nazwa | Wersja | Strona |`. Markdown wymaga wiersza nagłówka przed separatorem; bez niego tabela renderuje się jako zwykły tekst. Dwie trzecie inwentarza nie renderuje się poprawnie ani na GitHubie, ani w Obsidianie.

Prawdopodobne źródło: `scripts/fix_inventory_dedup.py` albo logika wstawiania wierszy w prescan/postupdate potraktowała wiersz nagłówka jako duplikat. Nie da się tego udowodnić bez fixture'a — i to jest dokładnie ten sam fixture, którego brak blokował H4 w rundach v3–v5. **Ta pozycja i „reszta H4" to jedno zadanie.**

**Poprawka:** zadanie **C1** (fixture + naprawa generatora + test strukturalny).

---

### M-4 · Parser appcastu Sparkle bierze pierwszy `<item>` bez uwzględnienia kanału — **MEDIUM**

`lib/internet_handlers.sh:224-236` — cztery kolejne próby, każda z `head -1`. Appcast Sparkle **nie gwarantuje** porządku od najnowszego, a Sparkle 2 dopuszcza `<sparkle:channel>beta</sparkle:channel>` oraz `sparkle:minimumSystemVersion` w tym samym pliku. Pierwsze `<item>` może być betą albo buildem dla nowszego macOS niż zainstalowany.

Skutek jest ograniczony (handler **nigdy nie podmienia bundla** — tylko raportuje i uruchamia aplikację), więc to nie jest ryzyko instalacyjne. To ryzyko **fałszywego „update available"**, które podnosi `DEGRADED` i uczy użytkownika ignorować ostrzeżenia.

Poprawnie: sparsować wszystkie `<item>`, odrzucić te z `<sparkle:channel>` innym niż pusty/`release`, odrzucić te z `minimumSystemVersion` > bieżącego `sw_vers -productVersion`, wybrać maksimum po `internet_version_relation`.

**Poprawka:** zadanie **C2**.

---

### M-5 · Ścieżka electron-updater obsługuje tylko dostawcę generycznego — **MEDIUM**

`lib/internet_handlers.sh:302-314` (grep `^url:` w `:306`) czyta wyłącznie klucz `url:` z `Contents/Resources/app-update.yml`. Aplikacje electron-updater z `provider: github` **nie mają** klucza `url:` — mają `owner:` i `repo:`, a manifest leży pod `https://github.com/<owner>/<repo>/releases/latest/download/latest-mac.yml`. Dla nich `remote_ver` zostaje puste i handler schodzi do „⏳ uruchomiony (niezweryfikowany)" mimo że feed jest w pełni odpytywalny.

To bezpośrednio zaniża metrykę pokrycia — jedyną liczbę, po której ocenia się ten projekt.

**Poprawka:** zadanie **C3**.

---

### M-6 · Metoda `silent_launch` nigdy nie liczy się jako zweryfikowana, nawet gdy realnie weryfikuje — **MEDIUM (metryka)**

`scripts/report_update_coverage.sh:231`:

```python
DIRECT_METHODS = {"keystone", "github_dmg", "msupdate", "docker_cli", "sparkle_appcast"}
```

`silent_launch` jest poza zbiorem — słusznie w momencie wprowadzenia tej reguły (`critical_rules.md` §6b: metoda liczy się jako zweryfikowana tylko wtedy, gdy naprawdę porównała wersję zdalną). Ale od poprawki z 2026-08-05 `internet_dispatch_silent_launch` **wykonuje** to porównanie, kiedy bundle publikuje feed, i sygnalizuje to przez `INTERNET_LAST_VERIFIED=1`.

Klasyfikacja jest dziś statyczna (z configu), a powinna być **za przebieg** (z faktycznego wyniku). 11 aplikacji `silent_launch` — część z nich weryfikuje się realnie i jest raportowana jako niezweryfikowana. Błąd jest w bezpiecznym kierunku, ale mierzysz się nieprawdziwą liczbą.

Poprawnie: zapisywać `INTERNET_LAST_VERIFIED` per aplikacja do `$MAC_UPDATE_SESSION_DIR/internet_verified.txt` i pozwolić raportowi podnieść klasyfikację z `triggered_unverified` do `verified_direct` **wyłącznie na podstawie dowodu z tego przebiegu**. Nigdy z configu.

**Poprawka:** zadanie **D2** (część arbitra źródeł).

---

### L-1 · `lib/python/` nie istnieje mimo że reguła 4 się na niego powołuje

`CLAUDE.md`/`AGENTS.md` reguła 4 dopuszcza „importowalne moduły czystych funkcji pod `lib/python/`, które `run_tests.sh` kompiluje i testuje". Katalogu nie ma, a `run_tests.sh` kompiluje `dev_sync/*.py scripts/*.py tests/*.py` — bez `lib/python/*.py`. Reguła opisuje strukturę, która nie powstała. Powstanie przy zadaniu C1.

### L-2 · `datetime.utcnow()` — przestarzałe od Pythona 3.12

`lib/internet_apps.sh:91` i `:104`. Zamiennik: `datetime.datetime.now(datetime.timezone.utc)`. Dziś tylko `DeprecationWarning`, ale te dwa bloki liczą „dni bez zmiany wersji" — czyli sygnał, na którym opiera się ostrzeżenie o zastoju.

### L-3 · Twardy `/opt/homebrew` w `update_brew.sh:272`

```bash
cask_app_path=$(find "/opt/homebrew/Caskroom/$cask" -maxdepth 3 -name "*.app" | head -1)
```

Projekt jest arm64-only, więc ścieżka jest w praktyce trafna — ale łamie regułę 5 („żadnych zakodowanych ścieżek") i psuje się przy niestandardowym `HOMEBREW_PREFIX`. `update_npm_cli.sh:809` robi to poprawnie: `brew --prefix 2>/dev/null || echo "/opt/homebrew"`. Wyrównać.

### L-4 · `DOCTOR_EXIT` przypisywane dwukrotnie i nigdy nieczytane

`update_brew.sh:335` i `:364`. Martwa zmienna — sugeruje, że kod wyjścia `brew doctor` miał kiedyś znaczenie i przestał mieć. Albo użyć, albo usunąć.

### L-5 · `internet_get_app_days_unchanged` może zwrócić pusty łańcuch przy braku `python3`

`update_internet_apps.sh:566-567` → `[ "$_s_days" -gt "$STALE_LIMIT" ]` z pustym `$_s_days` to błąd składni testu wypisywany na stderr. Nieszkodliwy (brak `set -e`), ale zaśmieca log. Domknąć `${_s_days:-0}`.

### L-6 · Potrójny `defaults read … SUFeedURL` na aplikację

`internet_feed_source` → `internet_handler_vendor_latest` → `internet_handler_sparkle_check` czytają ten sam klucz trzy razy. Przy 11 aplikacjach `silent_launch` to 33 wywołania `defaults` zamiast 11. Ujęte w P-2.

---

## 4. Wydajność — dlaczego przebieg trwa dłużej niż musi

Żadna z tych pozycji nie jest błędem poprawnościowym. Wszystkie są bezpośrednio sprzeczne z celem *„po jednym uruchomieniu wszystko najświeższe"*, bo płacisz czasem tam, gdzie nie musisz.

| # | Problem | Dowód | Kierunek |
|---|---|---|---|
| **P-1** | **Zero równoległości I/O.** 10 wywołań `curl` w `lib/internet_app_updates.sh` + feedy Sparkle/electron dla 14 aplikacji, wszystko szeregowo, każde z `--max-time 15 --retry 2` → pesymistycznie ~40 s **na aplikację** przy padającym feedzie | `grep -c "curl " lib/internet_app_updates.sh` → 10; brak `&`/`wait`/`xargs -P` w ścieżce sond | Rozbić krok 4 na **fazę sondowania** (równolegle, `xargs -P 8` albo jeden worker Pythona z `concurrent.futures`, wyniki do `$SESSION_DIR/feeds/`), **fazę decyzji** (czysta, offline), **fazę działania** (szeregowo — mutacje muszą być) |
| **P-2** | **34 starty `python3` na przebieg**, z czego 18 to samo `internet_version_relation` | `grep -rn python3 --include=*.sh` → 34; `grep -rn internet_version_relation` → 18 | Komparator w `awk` (start ~2 ms vs ~40 ms dla CPythona z importem `re`) w `lib/version_compare.sh`, z zachowaniem obecnej semantyki pre-release. Alternatywnie: jedno wywołanie na wszystkie pary z pliku |
| **P-3** | **Pętla settle jest O(sekundy × aplikacje × odczyt-pliku).** Dla każdej sekundy i każdej niezweryfikowanej aplikacji **ponownie parsuje cały `internet_app_methods.txt`**, żeby odwzorować `STATUS_VAR` → nazwa → ścieżka, po czym woła `capture_app_path` (a to `defaults read`/`mdls` dla przypadków specjalnych) | `update_internet_apps.sh:491-524` — `while elapsed` (`:491`) → `for var` (`:493`) → zagnieżdżony `while read` po całym configu (`:496`) | Rozwiązać mapowanie **raz**, przed pętlą, do dwóch równoległych list. W pętli tylko `defaults read` na gotowej ścieżce |
| **P-4** | **`brew info --json=v2 --cask` raz na każdy przestarzały cask** + `python3 -c` raz na każdy | `update_brew.sh:239-262` — pętla `for cask in …` (`:239`) | `brew info --json=v2 --cask $ALL` przyjmuje wiele nazw. Jedno wywołanie + jeden parser |
| **P-5** | **`brew update` i `softwareupdate -l` blokują szeregowo.** `brew update` to `git fetch` — zwykle najdłuższy pojedynczy blok przebiegu. `softwareupdate -l` to 10–60 s, wołane dopiero w kroku 6 | `update_brew.sh:107`, `update_system.sh:68` | Prefetch obu w tle na `t=0` w `update_all.sh`, konsumpcja w swoim kroku. Oszczędność realna, ryzyko zerowe (obie operacje są read-only) |
| **P-6** | **`brew cleanup --prune=all` przy każdym przebiegu** kasuje **cały** cache pobrań, w tym bottle wersji właśnie zainstalowanych. Każda naprawa/reinstalacja to ponowne pobranie setek MB — czyli dokładne przeciwieństwo „najszybciej do aktualnego" | `update_brew.sh:436` | Domyślnie `brew cleanup` (retencja 30 dni). `--prune=all` tylko przy `--deep` lub raz w miesiącu, sterowane `MAC_UPDATE_BREW_PRUNE_DAYS` |
| **P-7** | **`mas outdated --accurate` dwa razy w przebiegu.** Tryb `--accurate` odpytuje App Store per aplikacja i jest wielokrotnie wolniejszy niż zwykły | `update_appstore.sh:190` i `:482` | Pierwszy przebieg `--accurate` (potrzebna dokładność). Weryfikacja końcowa: `--accurate` **tylko** jeśli pierwszy coś znalazł; inaczej szybki `mas outdated` |

**Realistyczna prognoza:** P-1 + P-3 + P-5 to gros zysku. Szacuję skrócenie kroków 3–4 o **40–60 %** na łączu o normalnej latencji, bez zmiany semantyki ani jednego statusu. Nie mierzyłem tego na Macu — zadanie **D4** wymaga wpisania liczb przed/po do `IMPLEMENTATION_NOTES.md`.

---

## 5. Doktryna priorytetu źródeł — odpowiedź na Twoje główne pytanie

Poprosiłeś: *„jeśli jest możliwość instalacji danej aplikacji z wielu źródeł, zawsze ustawiaj priorytet na taką ścieżkę, aby aplikacja była najszybciej aktualna."*

Dziś projekt **ma dobrą intuicję i zero pomiaru**. Wersja 1.1.0 przeniosła 18 aplikacji na Homebrew, 1.3.0 zdjęła 9 z powrotem, bo cask zostawał w tyle (Cursor 3.7.21 przy 3.14.27 zainstalowanym — udokumentowane w `ULTRA_REVIEW_FINAL_v1.3.1.md` §4). Obie decyzje były słuszne, obie podjęto na podstawie **jednorazowego ręcznego badania API Homebrew**, którego nikt nie powtórzy za pół roku. To jest polityka, która się cicho zestarzeje.

### 5.1 Drabina świeżości (uporządkowana, z uzasadnieniem)

| Ranga | Kanał | Typowe opóźnienie do GA | Weryfikowalny? | Kiedy używać |
|---|---|---|---|---|
| **1** | Updater producenta z odczytywalnym feedem — Sparkle `SUFeedURL`, electron `latest-mac.yml`, Omaha/Keystone | **0** — producent publikuje tu **jako pierwsze** | tak (porównanie feed↔bundle) | Domyślnie, gdy feed istnieje i handler go rozumie |
| **2** | Bezpośrednie pobranie od producenta — GitHub Releases, oficjalne metadane (`github_dmg`) | 0 – godziny | tak (tag ↔ wersja) | Gdy brak feedu, ale jest stabilny endpoint wydań. Wymaga podpisanej podmiany bundla |
| **3** | Kanał menedżera pakietów **jawnie oznaczony „latest"** — npm `@latest`, cask `…@latest` | minuty – godziny | tak | Dla CLI i aplikacji, które producent sam publikuje do menedżera |
| **4** | Homebrew cask z `--greedy-auto-updates` | godziny – dni (najgorszy zaobserwowany w tym repo: **~7 wersji minor**) | tak | Gdy 1–3 niedostępne. Atomowo i bezpiecznie, ale z opóźnieniem |
| **5** | Homebrew cask na kanale „stable" producenta (np. `claude-code`) | **~7 dni z założenia** | tak | **Nigdy dla świeżości.** Tylko gdy świadomie chcesz opóźnienia |
| **6** | Mac App Store (`mas`) | opóźnienie producenta + recenzja Apple | częściowo | Gdy producent nie daje innej drogi |
| **7** | Ręcznie | ∞ | nie | Ostateczność, jawnie zadeklarowana |

Dwie uwagi techniczne, które w tym projekcie mają znaczenie:

- **`--greedy-auto-updates` jest właściwym wyborem** i nie należy go zmieniać na `--greedy`. `--greedy` obejmuje kaski `version :latest`, których wersji Homebrew **nie zna** — reinstalowałby je przy każdym przebiegu. Konsekwencja: aplikacja w kasku `:latest` jest strukturalnie **nieśledzona** i musi trafić na rangę 1 lub 2, bo w Homebrew nigdy nie da się o niej powiedzieć nic prawdziwego.
- **Ranga 1 bije rangę 4 nawet gdy ranga 4 „działa"**, bo cask jest z definicji pochodną feedu producenta. Cask nie może być świeższy niż źródło, z którego powstaje.

### 5.2 Reguła arbitrażu — mierz, nie zgaduj

> Dla każdej aplikacji wybierz **najwyżej sklasyfikowany kanał**, który jednocześnie: (a) ma zaimplementowany handler, (b) zweryfikował wersję zdalną w co najmniej jednym z trzech ostatnich przebiegów, (c) nie zgłosił regresji. Kiedy dostępne są dwa kanały — **notuj oba i porównuj**. Zmieniaj metodę wyłącznie na podstawie pomiaru.

To wymaga jednego nowego artefaktu i jednego raportu:

**`logs/source_lag.tsv`** — dopisywany w każdym przebiegu, rotowany jak `version_history.tsv`:

```
ts <TAB> app <TAB> channel <TAB> remote_version <TAB> installed_version <TAB> verified(0|1)
```

gdzie `channel` ∈ `vendor_feed | vendor_download | pkg_latest | brew_cask | mas | manual`. Kluczowe: dla aplikacji, która **ma** cask i **ma** feed, zapisuj **dwa wiersze na przebieg**, nawet jeśli aktualizujesz tylko jednym kanałem. Koszt: jedno dodatkowe `brew info --json=v2 --cask` (już zbatchowane w P-4). Zysk: po kilku tygodniach masz twardą odpowiedź „o ile dni cask zostaje w tyle za feedem dla tej konkretnej aplikacji" i nie musisz jej nigdy więcej zgadywać.

**`scripts/report_source_lag.sh`** — czyta TSV, wypisuje per aplikacja: bieżący kanał, kanał rekomendowany, medianę opóźnienia, liczbę próbek. Rekomendacja **nigdy nie zmienia configu sama** — to raport. Reguła „metoda w configu bez handlera" (`critical_rules.md` §6a) zaliczyła już dwie regresje; automatyczne przepisywanie configu byłoby trzecią.

### 5.3 Natychmiastowe zastosowanie doktryny — Claude Code CLI

Twoje polecenie („aktualizuj przez natywny updater `claude update`") **jest** tą doktryną w praktyce, i akurat tutaj różnica jest udokumentowana przez samego producenta:

| Kanał dla Claude Code | Ranga | Opóźnienie wg dokumentacji Anthropic |
|---|---|---|
| Instalator natywny, kanał `latest` | **1** | 0 — auto-update w tle + `claude update` na żądanie |
| Instalator natywny, kanał `stable` | 5 | **„typically about a week behind"** |
| npm `@anthropic-ai/claude-code@latest` | 3 | ~0, ale to opakowanie tej samej binarki natywnej; Anthropic klasyfikuje npm jako „advanced", nie zalecane |
| Homebrew cask `claude-code` | **5** | **stable — ~tydzień w tyle, i „do not auto-update"** |
| Homebrew cask `claude-code@latest` | 3 | latest, ale nadal bez auto-update |

Wniosek jest jednoznaczny i wart zapisania w `critical_rules.md`: **dla Claude Code najszybszą drogą do aktualności jest instalator natywny na kanale `latest`. Cask `claude-code` jest z projektu tydzień w tyle** — gdyby ktoś kiedyś „uporządkował" to, przenosząc CLI na Homebrew, byłaby to regresja świeżości udokumentowana przez producenta.

---

## 6. Zadanie A — Claude Code CLI na natywny `claude update`

### A0 · Stan faktyczny

`config/npm_global_clis.txt:5`
```
claude-code|@anthropic-ai/claude-code|npm||claude
```

Metoda `npm` → `update_npm_cli.sh:754-764` → `npm install -g --prefix "$NPM_GLOBAL_PREFIX" @anthropic-ai/claude-code@latest`.

Metoda `self-update` już istnieje (`:765-780`) i robi `run_with_timeout 300 "$command_path" update` — czyli **dokładnie `claude update`**. Używa jej dziś tylko `agy-cli`.

### A1 · Fakty potwierdzone w dokumentacji Anthropic (2026-08-12)

- Instalacja natywna zalecana: `curl -fsSL https://claude.ai/install.sh | bash`. Launcher: `~/.local/bin/claude`, wersje: `~/.local/share/claude/versions/`.
- **Instalacje natywne aktualizują się same w tle**; `claude update` wymusza natychmiast.
- Komunikaty `claude update` — to jest kontrakt parsowania:
  - `Successfully updated from <stara> to version <nowa>` → **zaktualizowano**
  - `Claude Code is up to date (<wersja>)` → **aktualne, zweryfikowane**
  - `Claude is up to date!` → **instalacja należy do Homebrew/WinGet/apk — `claude update` jest no-opem**. Ten string to sygnał „nie jesteś właścicielem tej instalacji", nie sukces.
- `claude doctor` — diagnostyka read-only: typ instalacji, zdrowie, **wynik ostatniej próby aktualizacji**. Nie startuje sesji.
- `claude install` — przechodzi z instalacji npm na natywną.
- `claude --version` → `2.1.211 (Claude Code)`.
- Kanały: `autoUpdatesChannel` = `"latest"` (domyślnie) | `"stable"` (~tydzień w tyle). `minimumVersion` = podłoga wersji.
- `DISABLE_AUTOUPDATER=1` wyłącza tylko sprawdzanie w tle — `claude update` i `claude install` nadal działają. `DISABLE_UPDATES=1` blokuje **wszystko**.
- Pakiet npm od v2.1.198 wymaga Node ≥ 22 i instaluje **tę samą binarkę natywną** przez zależność opcjonalną `@anthropic-ai/claude-code-darwin-arm64`. Aktualizacja: `npm install -g …@latest`; **`npm update -g` jest jawnie odradzane** (respektuje zakres semver z pierwotnej instalacji).

### A2 · Specyfikacja

**A1a — nowa metoda `native_self_update`** w `config/npm_global_clis.txt`. Nie przeciążać istniejącego `self-update`: `agy` nie ma kontraktu wyjścia Claude'a, a wspólny parser rozjechałby oba. Nowa nazwa jest też zgodna z regułą „nazwa metody istnieje tylko wtedy, gdy istnieje handler".

```
claude-code|@anthropic-ai/claude-code|native_self_update|claude-code|claude
```

**A1b — wykrycie właściciela instalacji przed jakąkolwiek mutacją.** Kolejność:
1. `claude doctor` (timeout 60 s) — jeśli raportuje instalację zarządzaną przez menedżer pakietów, **nie próbuj `claude update`**.
2. Jeśli `command -v claude` wskazuje wewnątrz `$(brew --prefix)` → właścicielem jest Homebrew → status `MANAGED_BY_BREW`, delegacja do kroku 3, **i ostrzeżenie**, jeśli cask to `claude-code` (stable), z rekomendacją `claude-code@latest` (§5.3).
3. Jeśli istnieje `$NPM_GLOBAL_BIN/claude` **i** `$HOME/.local/bin/claude` → dwie instalacje jednocześnie → migracja (A1d).
4. Jeśli istnieje tylko `$NPM_GLOBAL_BIN/claude` → migracja (A1d).
5. W przeciwnym razie → natywna → `claude update`.

**A1c — naprawa kolejności ścieżek (M-2), obowiązkowo przed A1e.**
- `update_npm_cli.sh:327` — wyprowadzić `claude` z gałęzi `npm|pnpm|claude|codex|opencode` do własnej, sprawdzającej `$LOCAL_BIN/claude` **jako pierwsze**, dopiero potem `$NPM_GLOBAL_BIN/claude`.
- `update_all.sh:1022-1027` — dla `claude` przestawić `roots` tak, by `~/.local/bin` szedł pierwszy. Zrobić to danymi (kolejność per komenda), nie kolejnym `if`-em.

**A1d — migracja npm → natywna, idempotentna i odwracalna.**
1. Zanotować wersję: `claude --version`.
2. `run_with_timeout 300 claude install` (dokumentowana ścieżka migracji).
3. Sprawdzić, że `~/.local/bin/claude` istnieje i jest wykonywalny; `claude --version` z **tej** ścieżki ≥ zanotowanej (`internet_version_relation`, nigdy nie akceptować niższej).
4. Dopiero wtedy `npm uninstall -g @anthropic-ai/claude-code` (bez `sudo` — dokumentacja tego zabrania).
5. Jeśli którykolwiek krok padnie: **nie odinstalowywać npm**, `SOFT_FAIL=1`, honestny status. Migracja, która zostawia użytkownika bez `claude`, jest gorsza niż brak migracji.

**A1e — handler `native_self_update`.** Nie da się użyć `run_quiet_with_error_log`, bo ono zjada stdout, a stdout jest tu kontraktem. Potrzebny wariant przechwytujący:

```
OUT="$(run_with_timeout 300 "$command_path" update 2>&1)"; rc=$?
```

Klasyfikacja **wyłącznie po stringach z A1**, plus niezależne potwierdzenie `claude --version` przed i po. Sam `rc=0` nie jest dowodem aktualizacji.

| Wynik | Status | Severity |
|---|---|---|
| `Successfully updated from … to version …` **i** wersja się zmieniła | `UPDATED` (zweryfikowane) | 0 |
| `Claude Code is up to date (…)` | `CURRENT` (zweryfikowane) | 0 |
| `Claude is up to date!` | `MANAGED_EXTERNALLY` — delegacja do brew | 10 |
| `DISABLE_UPDATES` aktywne | `UPDATES_DISABLED_BY_POLICY` | 0 (świadoma decyzja użytkownika, **nie** ostrzeżenie) |
| timeout 124 / rc≠0 / brak dopasowania | `UPDATE_FAILED` + zsanityzowane 20 linii do `npm_cli_errors.log` | 10 |
| Wersja po < wersja przed | `DOWNGRADE_BLOCKED` | **1** (twardy — to nigdy nie powinno się zdarzyć) |

**A1f — polityka kanału (doktryna z §5.3).** Nowa zmienna `MAC_UPDATE_CLAUDE_CHANNEL` (`latest` domyślnie | `stable` | `keep`). Przy `latest`/`stable` ustawić `autoUpdatesChannel` w `~/.claude/settings.json` **atomowo** (tempfile w tym samym katalogu + `os.replace`, tryb 0600 — jak `atomic_write_text`), zachowując wszystkie pozostałe klucze. `keep` = nie dotykaj. Nigdy nie nadpisywać `minimumVersion`.

**A1g — inwentarz i i18n.** `APPLICATIONS.md` sekcja 4d: metoda `native (claude update)` zamiast `npm`. Nowe klucze statusów do **wszystkich siedmiu** `i18n/lang_*.sh` — dziś 671 na plik, po zmianie 671 + N, **identycznie w każdym** (`test_i18n_lang_files_key_parity`). Statusy używane w dopasowaniu dokładnym muszą pozostać **statyczne, bez `%s`** (`test_exact_match_status_keys_stay_static`).

**A1h — dokumentacja.** `docs/agents/critical_rules.md` §5, wiersz „Native/npm/self-updating CLI": rozdzielić Claude Code na własny wiersz z notatką z §5.3 (cask `claude-code` = stable = tydzień w tyle; kanał `latest` = najszybszy). To jest wiedza, która inaczej zniknie.

### A3 · Naprawa `update_system.sh` (H-1)

1. Załadować `lib/severity.sh` + `mac_update_severity_init`; wychodzić przez `mac_update_severity_exit_code`.
2. Porażka `softwareupdate -l` (`:71-77`): `SOFT_FAIL=1`, exit 10 — **nie** 1. Chwilowy brak sieci nie może blokować.
3. **Przed każdym `sudo`:** jeśli `MAC_UPDATE_NO_SUDO=1` **lub** (`! [ -t 0 ]` **i** `! sudo -n true`) → nie wołać `sudo`. Wypisać dokładną komendę do ręcznego uruchomienia, `SOFT_FAIL=1`, exit 10. Wzorzec skopiować z `update_appstore.sh:247`.
4. Zachować `-R` na **każdej** ścieżce instalacji (reguła nienaruszalna 1).
5. Trzy nowe testy: (a) `update_system.sh` ładuje `lib/severity.sh`; (b) każde wywołanie `sudo` jest poprzedzone bramką `MAC_UPDATE_NO_SUDO`/TTY; (c) test behawioralny — `MAC_UPDATE_NO_SUDO=1` + zaślepki → exit **10**, zero wywołań `sudo`.
6. **Rozszerzyć listę** w `test_leaf_scripts_source_severity_and_have_soft_exit_path` o `update_system.sh`. To jest poprawka, która zamyka klasę.

### A4 · Filtr formuł przypiętych (H-2)

W obu miejscach, gdzie `brew outdated --formula` decyduje o severity (`update_brew.sh:117-126` i `:305-313`):

1. `PINNED="$(brew list --pinned 2>/dev/null)"`.
2. Odfiltrować przypięte z `REMAINING_FORMULAE` **przed** testem `HARD_FAIL`.
3. Wypisać je osobno jako informację: „przypięte, pominięte celowo: …". Cisza byłaby gorsza od błędu.
4. Formuły nieprzypięte, które **pozostały** przestarzałe po `brew upgrade`, degradować z `HARD_FAIL=1` do `SOFT_FAIL=1`. Uzasadnienie z `critical_rules.md` §10: `HARD_FAIL` istnieje dla „maszyna jest w połowie transakcji, restart pogorszy sprawę". Formuła, która nie chciała się podnieść, nie zostawia maszyny w połowie transakcji — zostawia ją w stanie sprzed. To definicja soft. `brew upgrade` **zwracające błąd** (`:186-192`) pozostaje twarde — tam faktycznie coś pękło w trakcie.
5. Test: zaślepka `brew` zwracająca stale przestarzałą formułę na liście przypiętych → `update_brew.sh` kończy **0** lub **10**, nigdy 1; krok 6 się wykonuje.

### A5 · LaunchAgent (H-3)

1. `--check` i komunikat po instalacji muszą powiedzieć wprost: **„Ten harmonogram nie instaluje aktualizacji systemu macOS (`--skip-system`)."**
2. Nowa flaga `--with-system`, generująca **drugi** plist (miesięczny), który uruchamia wyłącznie krok 6 — i który po naprawie A3 uczciwie kończy się kodem 10 z instrukcją zamiast prosić o Touch ID w tle.
3. Powtórzyć to zdanie w `docs/agents/exit_codes.md` §„Sudo Pre-authentication and Unattended" i w `docs/user/*/OPERATIONS.md` (7 języków).

### A6 · Deterministyczny `TEE_PID` (M-1)

Zamienić podstawienie procesu na FIFO (kod w §M-1). Warunki:
- FIFO w `$SESSION_DIR` (tryb 700), nigdy w gołym `/tmp`.
- Awaria `mkfifo` → degradacja do obecnego zachowania z ostrzeżeniem, nie przerwanie przebiegu.
- `cleanup_session_dir` kolejność bez zmian: zabij keep-alive → `exec 1>&3 2>&4` → `wait "$TEE_PID"` → usuń FIFO.
- Nowy test: `TEE_PID` jest przypisywane **bezpośrednio po zwykłym zadaniu w tle**, nigdy po `>(`.

---

## 7. Zadanie B — Ascendo poza inwentarzem, na stałe

**Cel:** `update_all.sh` nie aktualizuje i **nie uruchamia** Ascendo, a inwentarz nie wpisuje go z powrotem.

### B1 · Nowy artefakt `config/ignored_apps.txt`

```
# Aplikacje wyłączone spod zarządzania macOS Updates.
# Jedna nazwa bundla (bez .app) w wierszu; # rozpoczyna komentarz.
# Wykluczone z: prescan inwentarza, rejestru internetowego, dispatchu,
# raportu pokrycia i historii wersji. Nigdy nie są uruchamiane ani aktualizowane.
Ascendo
```

Loader w `lib/internet_apps.sh`: `internet_apps_is_ignored <nazwa>` → 0/1. Bash 3.2 — pętla po pliku, bez tablic asocjacyjnych. Wynik cache'owany w zmiennej łańcuchowej z separatorami (`|Ascendo|`), żeby nie czytać pliku N razy (lekcja z P-3).

### B2 · Punkty honorowania (wszystkie pięć, inaczej wraca)

| Miejsce | Zmiana |
|---|---|
| `lib/internet_apps.sh` → `internet_apps_load_config` | pomijaj ignorowane przy budowie `INTERNET_APPS_LIST[]` |
| `lib/internet_registry.sh` → `internet_registry_load` | pomijaj wiersze ignorowanych aplikacji |
| `update_all.sh` prescan (`:542-552`) | odfiltruj z `installed_apps` **oraz** z zapisu `installed_apps_after.txt` (`:580`) — inaczej postupdate wpisze je z powrotem |
| `update_all.sh` postupdate (heredoc od `:1262`, odczyt w `:1377`) | ten sam filtr przy wstawianiu wierszy do GRUPY 3 |
| `scripts/report_update_coverage.sh` | pomijaj — inaczej pojawią się jako `unknown` i zaniżą pokrycie |

### B3 · Czyszczenie punktowe dla Ascendo

| Plik | Akcja |
|---|---|
| `config/internet_apps.txt:17` | usuń wiersz `Ascendo` |
| `config/internet_app_methods.txt:22` | usuń `Ascendo\|silent_launch\|STATUS_ASCENDO` |
| `config/internet_dispatch_order.txt:28` | zamień `iu_ascendo` na komentarz `# Ascendo — user-managed (config/ignored_apps.txt)` |
| `lib/internet_app_updates.sh:1453-1455` | usuń funkcję `iu_ascendo` |
| `update_internet_apps.sh:431` | usuń `STATUS_ASCENDO=…` |
| `update_internet_apps.sh:639` | usuń wiersz `printf … "Ascendo:"` |
| `update_internet_apps.sh:680` | usuń `"$STATUS_ASCENDO"` z pętli kodu wyjścia |
| `update_internet_apps.sh:20` | usuń „Ascendo" z komentarza nagłówkowego DEV TOOLS |
| `scripts/audit_cask_candidates.sh:36` | usuń mapowanie `"Ascendo") echo "ascendo"` |
| `docs/agents/critical_rules.md:105` | usuń „Ascendo" z listy silent-launch |
| `APPLICATIONS.md:138` | usuń wiersz `\| Ascendo \| 0.2.0 \| https://ascendo.dev \|` |
| `APPLICATIONS.md:141` | zmień „Ascendo i Cursor aktualizują się…" na „Cursor aktualizuje się…" |
| `APPLICATIONS.md:463` | usuń „Ascendo" z listy auto-aktualizowanych |

**Uwaga o spójności testowej:** `test_internet_config_status_var_parity` (`tests:812`) sprawdza pięć niezmienników naraz — listy aplikacji identyczne, każdy `STATUS_*` zainicjalizowany, obecny w tabeli podsumowania **i** w pętli wyjścia, brak sierot. Usunięcie Ascendo z czterech z pięciu miejsc wywali ten test. To dobrze — tak ma działać. Wszystkie pięć naraz.

`test_no_app_listed_in_both_group3_and_casks` czyta `APPLICATIONS.md` i pomija się, gdy pliku brak — po usunięciu wiersza nadal przechodzi.

### B4 · Test na regresję (bez tego zadanie jest niedokończone)

`test_ignored_apps_are_never_dispatched_or_inventoried`:
1. Dla każdej nazwy w `config/ignored_apps.txt`: brak w `internet_apps.txt`, brak w `internet_app_methods.txt`, brak nieskomentowanego `iu_*` w `internet_dispatch_order.txt`.
2. Symulacja prescanu na fixture katalogu z `Ascendo.app` → nazwa **nie** pojawia się na wyjściu.
3. `grep -c "Ascendo" update_internet_apps.sh lib/internet_app_updates.sh` → **0**.

---

## 8. Nowa funkcjonalność — ranking

| # | Funkcja | Dlaczego | Rozmiar |
|---|---|---|---|
| **D1** | `logs/source_lag.tsv` + `scripts/report_source_lag.sh` (§5.2) | Zamienia doktrynę priorytetu źródeł z opinii w pomiar. To jest odpowiedź na Twoje główne pytanie | M |
| **D2** | Klasyfikacja pokrycia z dowodu przebiegu, nie z configu (M-6) | 11 aplikacji `silent_launch` — część weryfikuje się realnie i jest liczona jako niezweryfikowana | S |
| **D3** | Równoległa faza sondowania feedów (P-1) | Największy pojedynczy zysk czasu; zero ryzyka (read-only) | M |
| **D4** | Profile `--fast` / `--deep` | `--fast`: bez `brew doctor`, bez `--prune=all`, bez `mas --accurate` w weryfikacji końcowej. `--deep`: wszystko + `report_source_lag` | S |
| **D5** | `lib/version_compare.sh` w awk (P-2) | Zdejmuje 18 z 34 startów `python3` | S |
| **D6** | `lib/python/` + fixture `APPLICATIONS.md` (L-1, M-3, reszta H4) | Odblokowuje jednocześnie test strukturalny inwentarza i wyciągnięcie czystych funkcji | M |
| **D7** | `--verify-only` | Sprawdź co jest nieaktualne, nie mutując nic. Dziś `--dry-run` wychodzi z leaf-skryptów **przed** sondowaniem, więc nie odpowiada na to pytanie | S |

**D7 warto uzasadnić:** `update_internet_apps.sh:395-401` przy `MAC_UPDATE_DRY_RUN=1` wychodzi natychmiast, przed jakąkolwiek sondą. To poprawne dla „nic nie mutuj", ale oznacza, że nie da się zapytać „co jest nieaktualne?" bez uruchomienia pełnej aktualizacji. Po D3 faza sondowania jest już oddzielona i `--verify-only` to praktycznie darmowy tryb.

---

## 9. Kolejność wykonania

**Blok 1 — bezpieczeństwo i uczciwość (przed czymkolwiek innym)**
`A3` (severity + sudo w update_system) → `A4` (formuły przypięte) → `A5` (LaunchAgent) → `A6` (TEE_PID)
*Uzasadnienie: A3 i A4 to jedyne dwa defekty, które mogą trwale wstrzymać łatki bezpieczeństwa macOS.*

**Blok 2 — Twoje dwa polecenia**
`A1c` (kolejność ścieżek — **musi poprzedzać A1e**) → `A1a/b/d/e/f/g/h` (Claude Code) → `B1..B4` (Ascendo)

**Blok 3 — świeżość**
`D1` → `D2` → `C2` (kanały Sparkle) → `C3` (electron/GitHub)

**Blok 4 — wydajność**
`D3`/`P-1` → `P-3` → `P-5` → `D5`/`P-2` → `P-4` → `P-6` → `P-7` → `D4`

**Blok 5 — dług**
`D6` (`lib/python/` + fixture + `C1`) → `L-2` → `L-3` → `L-4` → `L-5` → `L-6` → `D7`

Wersjonowanie: Blok 1+2 → **v1.4.0**. Blok 3+4 → **v1.5.0**. Blok 5 → **v1.5.1**.

---

## 10. Otwarte pytania i ryzyko resztkowe

1. **Nic nie zostało uruchomione na macOS.** Trzy twierdzenia wymagają po jednej komendzie na Twoim Macu — wszystkie w §11.
2. **H-2 może być utajone.** Jeśli `brew list --pinned` jest puste, defekt istnieje w kodzie, ale nie zadziałał jeszcze ani razu. Naprawić i tak — koszt jest trzy linie, a jedna komenda `brew pin` w przyszłości uzbraja go bez ostrzeżenia.
3. **`shellcheck` nie był uruchomiony** — nie ma go w sandboxie. `bash -n` przechodzi na 40 plikach. `.shellcheckrc` w repo istnieje, więc gdzieś w CI to chodzi; warto potwierdzić, że obejmuje `lib/`.
4. **M-3 zdiagnozowałem strukturalnie, nie przyczynowo.** Wiem, że 14 tabel jest zepsutych; nie wiem, czy zrobił to `fix_inventory_dedup.py`, czy logika wstawiania. Bez fixture'a to zgadywanie — dlatego D6 jest warunkiem C1, a nie odwrotnie.
5. **Nie czytałem `UPDATES.md`** (132 KB, prywatny). Zachowanie postupdate przy realnych danych pozostaje niezweryfikowane — to samo ryzyko resztkowe, które v3–v5 nazywały „H4".
6. **`codex-cli` i `opencode-cli` mogą mieć własne updatery natywne.** Nie sprawdzałem i **nie twierdzę, że mają**. Po zamknięciu A warto zadać to samo pytanie tym dwóm — ale odpowiedź musi przyjść z dokumentacji producenta, nie z analogii do Claude Code. Analogia jest dokładnie tym, co wyprodukowało regresje `brew_cask` i `vendor_latest`.

---

## 11. Weryfikacja — komendy do uruchomienia na Macu

```bash
# ── Trzy twierdzenia tego przeglądu, po jednej komendzie ──

# H-2: czy defekt formuł przypiętych jest aktywny dziś?
brew list --pinned; echo "pinned-exit=$?"
#   niepusty wynik  → H-2 blokuje krok 6 przy KAŻDYM przebiegu
#   pusty           → utajony; napraw i tak

# M-1: czy /bin/bash ustawia $! dla podstawienia procesu?
/bin/bash --version | head -1
/bin/bash -c 'sleep 0.1 & A=$!; : > >(cat); B=$!; echo "bg=$A subst=$B same=$([ "$A" = "$B" ] && echo YES || echo no)"'
#   same=YES → TEE_PID wskazuje keep-alive, nie tee (M-1 potwierdzone)

# H-1: czy krok 6 woła sudo bez TTY?
grep -n "MAC_UPDATE_NO_SUDO" update_system.sh || echo "BRAK BRAMKI — H-1 potwierdzone"
echo | MAC_UPDATE_NO_SUDO=1 MAC_UPDATE_YES=1 bash update_system.sh; echo "exit=$?"
#   prompt Touch ID albo "no tty present" → H-1 potwierdzone
#   exit=1 przy zwykłym braku sieci → druga połowa H-1

# ── Stan bazowy przed pracą Gemini ──
bash run_tests.sh 2>&1 | tail -20
for f in i18n/lang_*.sh; do printf '%s %s\n' "$f" "$(grep -c '^L_[A-Z0-9_]*=' "$f")"; done   # 7 × 671
bash scripts/report_update_coverage.sh | tail -25
git status --short

# ── Punkt wyjścia dla zadania A ──
command -v claude; claude --version; claude doctor 2>&1 | head -30
ls -la ~/.local/bin/claude ~/.local/share/mac-update/npm-global/bin/claude 2>&1
brew list --cask 2>/dev/null | grep -i claude

# ── Punkt wyjścia dla zadania B ──
ls -d /Applications/Ascendo.app 2>/dev/null && echo "Ascendo zainstalowane — prescan wpisze je z powrotem bez B1"
grep -rn -i "ascendo" config/ lib/ update_internet_apps.sh scripts/ | wc -l
```

---

## 12. Podsumowanie w trzech zdaniach

Ten projekt jest o klasę lepszy niż typowe „skrypty do aktualizacji" — kontrakt severity z macierzą blokowania, weryfikacja podpisu i Team ID przed podmianą bundla oraz strażniki testowe, które uniemożliwiają zadeklarowanie metody bez implementacji, to rozwiązania, których nie ma większość komercyjnych narzędzi tej kategorii. Trzy defekty wysokiego priorytetu leżą jednak dokładnie na ścieżce, dla której to wszystko powstało: przebieg bez nadzoru albo pomija aktualizacje macOS z premedytacji (`--skip-system` w LaunchAgencie), albo trafia na `sudo` w kroku 6, który jako jedyny nie zna kontraktu ustalonego dla pozostałych kroków — a pojedyncza przypięta formuła Homebrew potrafi wstrzymać łatki bezpieczeństwa systemu na stałe i wyglądać przy tym jak zwykły czerwony status.

Największą brakującą funkcją nie jest kolejny handler, tylko **pomiar**: dziś wybór źródła aktualizacji per aplikacja jest deklaracją w pliku konfiguracyjnym, opartą na jednorazowym ręcznym badaniu z 2026-08-05, które nikt nie powtórzy — `logs/source_lag.tsv` plus raport arbitra zamieniłby to w politykę, która sama się aktualizuje i sama się broni.

---

## Źródła

- [Claude Code — Advanced setup (instalacja, `claude update`, kanały, integralność binariów)](https://code.claude.com/docs/en/setup)
- [Homebrew Documentation — FAQ (`brew pin`, zachowanie `brew upgrade`)](https://docs.brew.sh/FAQ)
- [Homebrew/brew — Note cases when pinned formulae get upgraded (PR #3043)](https://github.com/Homebrew/brew/pull/3043)
- [Homebrew Discussions #6550 — zmiana entitlementów `mas` (cytowane w `critical_rules.md` §2)](https://github.com/orgs/Homebrew/discussions/6550)

*Ten przegląd nie zmodyfikował żadnego pliku projektu. Utworzone zostały wyłącznie: ten dokument oraz `docs/reviews/Opus5_Max_Implementation_Prompt_v6.md`.*
