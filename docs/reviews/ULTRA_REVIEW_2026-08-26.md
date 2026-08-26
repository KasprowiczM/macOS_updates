# Ultra review — 2026-08-26 (v1.4.1 → v1.4.2)

**Zakres:** weryfikacja ostatniego logu uruchomienia (`logs/update_all_20260826_101524.log`),
eliminacja *wszystkich* zgłoszonych problemów, testy regresyjne, bump wersji.

**Punkt wyjścia:** przebieg zakończył się `exit_code: 0`, ale `degraded: true` —
cztery z siedmiu kroków raportowały ostrzeżenia:

```
appstore  : Ostrzeżenie (niezweryfikowane)
npmcli    : Ostrzeżenie (niezweryfikowane)
brew      : Ostrzeżenie (niezweryfikowane)
internet  : Ostrzeżenie (niezweryfikowane)
```

**Wniosek z audytu:** żadne z tych ostrzeżeń nie było przejściowe. Każde z nich
odtwarzało się przy każdym uruchomieniu i **blokowało realną aktualizację** —
log od tygodni raportował te same pozycje jako „miękkie ostrzeżenia", podczas gdy
cztery aplikacje po prostu nie mogły się zaktualizować.

---

## P0-1 — `codex-cli` kończył się błędem przy każdym przebiegu (`exit=124`)

**Objaw w logu**

```
ℹ️  Aktualizuję codex-cli przez własny updater (native installer update)...
⚠️  Aktualizacja codex-cli nie powiodła się
=== codex native installer (exit=124) ===
```

**Przyczyna źródłowa.** `exit=124` to zabicie przez `run_with_timeout`, nie błąd
sieci. Pobrany skrypt instalatora dostawcy (`https://chatgpt.com/codex/install.sh`)
ma:

```sh
NON_INTERACTIVE="${CODEX_NON_INTERACTIVE:-false}"
...
prompt_yes_no() {
  case "$NON_INTERACTIVE" in 1|true|yes) return 1 ;; esac
  if ( : </dev/tty ) 2>/dev/null; then
    printf '%s [y/N] ' "$prompt" >/dev/tty
    if ! IFS= read -r answer </dev/tty; then return 1; fi
```

Instalator pyta `Start Codex now?` (i przy konflikcie menedżerów
`Uninstall the existing npm-managed Codex now?`) **czytając bezpośrednio z `/dev/tty`**.
Przekierowanie stdin tego nie omija — jedynym wyjściem jest udokumentowany
przełącznik `CODEX_NON_INTERACTIVE`. Instalator blokował się na promptcie, aż
`run_with_timeout 120` go zabił. Pozostałe trzy instalatory (`claude`, `agy`,
`cursor`) nie mają promptów — dlatego wyłącznie codex zawodził.

Druga, ukryta połowa problemu: sam skrypt dostawcy ma `RELEASES_ASSET_TIMEOUT=300`.
Nasz limit 120 s był **niższy niż limit pobierania dostawcy**, więc nawet zdrowa,
wolna instalacja padłaby jako „błąd".

**Poprawka** (`update_npm_cli.sh`)

- nowe `native_installer_env()` — mapa przełączników non-interactive per instalator
  (`codex → CODEX_NON_INTERACTIVE=1`),
- nowe `native_installer_timeout()` — domyślnie 360 s (twardo powyżej 300 s dostawcy),
  konfigurowalne przez `MAC_UPDATE_NATIVE_INSTALLER_TIMEOUT`,
- stdin instalatora odpięty (`</dev/null`) jako obrona w głąb.

**Weryfikacja na żywo**

```
==> Updating Codex CLI from 0.149.1 to 0.150.0
Codex CLI 0.150.0 installed successfully.      (< 45 s, bez promptu)
```

W przebiegu kontrolnym: `✅ codex-cli: 0.150.0`.

---

## P0-2 — Ledger Live nigdy nie mógł przejść weryfikacji sumy kontrolnej

**Objaw w logu**

```
⚠️  Dostępna nowa wersja: 4.17.1 (masz: 4.15.0)
▶  Pobieranie Ledger Wallet 4.17.1...
⚠️  Checksum SHA512 Ledger Live nie zgadza się
```

**Przyczyna źródłowa.** `latest-mac.yml` (electron-builder) wygląda tak:

```yaml
files:
  - url: ledger-live-desktop-4.17.1-mac.zip
    sha512: 7v118UqK/...          ← pierwszy sha512 w dokumencie
  - url: ledger-live-desktop-4.17.1-mac.dmg
    sha512: k/+rW0KRndW7...       ← ten, który jest nam potrzebny
path: ledger-live-desktop-4.17.1-mac.zip
sha512: 7v118UqK/...              ← powtórzenie digestu ZIP-a
```

Handler pobierał **pierwszy** `sha512:` w dokumencie:

```python
match = re.search(r'sha512:\s*([A-Za-z0-9+/=]+)', yml)
```

…czyli sumę **ZIP-a**, a następnie porównywał ją z pobranym **DMG**. Niezgodność
była strukturalna, nie przypadkowa — Ledger nie mógł się zaktualizować *nigdy*.
Aplikacja tkwiła na 4.15.0, gdy dostępne było 4.17.1.

**Poprawka** (`lib/internet_app_updates.sh`): URL DMG-a i jego digest są czytane
z **tego samego wpisu manifestu**; gdy manifest nie da się sparsować, nazwa pliku
jest zgadywana, a digest **czyszczony** (nie ma czego weryfikować — lepiej pominąć
krok niż porównywać z cudzą sumą).

**Weryfikacja na żywo** — pobrany DMG 4.17.1 (299 979 713 B):

```
DMG digest (nowy kod)  matches: True
ZIP digest (stary kod) matches: False
```

---

## P0-3 — `brave-browser` był pomijany przez strażnika downgrade'u, bezterminowo

**Objaw w logu**

```
⚠️  Cask brave-browser (1.93.138.0) jest starszy niż zainstalowana wersja
    aplikacji (151.1.93.138) — pominięto aktualizację, aby zapobiec cofnięciu wersji
```

**Przyczyna źródłowa.** Brave publikuje w bundlu `CFBundleShortVersionString`
w postaci `<Chromium major>.<wersja Brave>` — `151.1.93.138`. Cask używa własnego
schematu `1.93.138.0`. Strażnik porównywał je segment po segmencie: `151 > 1`,
werdykt „zainstalowana nowsza" → pomiń. To nie jest stan przejściowy: dopóki
Brave prefiksuje wersję Chromium, strażnik **zawsze** będzie blokował aktualizację.

Pomiar na żywo przed poprawką:

```
cask_ver=1.93.138.0   recorded=1.93.136.0   app_ver=151.1.93.138
app vs cask (STARY) -> newer      ← pomiń (błędnie)
```

Uwaga: Homebrew *sam* miał poprawną odpowiedź w swojej ewidencji
(`installed: 1.93.136.0` < `1.93.138.0`) — nie była ona w ogóle czytana.

**Poprawka**

- `update_brew.sh` czyta teraz `installed` z `brew info --json=v2` i **to** jest
  główny operand porównania (jedyny like-for-like),
- wersja z bundla jest fallbackiem i idzie przez nowe
  `app_vs_package_version_relation()` (`lib/version.sh`), które przed porównaniem
  wyrównuje prefiks producenta, a gdy schematy są nieporównywalne, zwraca
  `unknown` zamiast zmyślać downgrade,
- przypadek `unknown` jest raportowany jako informacja, nie ostrzeżenie.

**Weryfikacja na żywo** (przebieg kontrolny):

```
brave-browser  1.93.136.0 -> 1.93.138.0
🍺  brave-browser was successfully upgraded!
```

Realny downgrade nadal jest wyłapywany — `151.1.93.140` vs `1.93.138.0` → `newer`.

---

## P0-4 — zwolnienia odroczeń Microsoft AutoUpdate raportowane bez weryfikacji

**Objaw w logu**

```
⚠️  Znaleziono odroczenia: ... DeferralVersions.TEAMS21=26213.1006.5011.1671
✅ Zwolniono odroczenia Microsoft AutoUpdate: DeferralVersions.TEAMS21
```

**Pomiar systemu docelowego po przebiegu** (`defaults read com.microsoft.autoupdate2`):

```
DeferralVersions = { TEAMS21 = "26213.1006.5011.1671"; };   ← wciąż tam
```

**Przyczyna źródłowa.** `mau_reconcile_deferrals()` weryfikowało **tylko** zapisy
`armed` (`DeferralDays`) względem żywej domeny. Usunięcia (`removed`) przyjmowano
na słowo — na podstawie kodu wyjścia `plutil -remove` wykonanego na **wyeksportowanej
kopii**. To nie mówi nic o żywej domenie: MAU odtwarza pin, który wciąż uważa za swój.
Trzy przebiegi z rzędu (28.07, 19.08, 26.08) zaraportowały zwolnienie, którego nie było.

To dokładnie ten sam wzorzec, który zapisaliśmy w pamięci projektu po poprzednim
review: *raport agenta sprawdzaj pomiarem systemu docelowego, nie repozytorium*.

**Poprawka** (`lib/internet_app_updates.sh`): każdy wpis z `removed` jest sprawdzany
w żywej domenie po imporcie. Wpisy, które przetrwały, trafiają do
`L_INTERNET_MS_DEFERRALS_NOT_RELEASED_FMT` (ostrzeżenie + `SOFT_FAIL=1`), a `print_ok`
wypisuje wyłącznie to, co faktycznie zniknęło.

**Uwaga otwarta (decyzja użytkownika, bez zmian):** źródłem kwarantanny Office
pozostaje `ChannelName = Preview` przy Office zbudowanym dla `Current`. Zmiana
kanału to trwałe rozwiązanie i nadal czeka na Twoją decyzję.

---

## P1-1 — prescan raportował własną księgowość jako „nowe aplikacje"

**Objaw w logu**

```
⚠️  Nowe aplikacje nieobecne w APPLICATIONS.md (1 szt.):
     → GarageBand
```

…podczas gdy `APPLICATIONS.md` linia 88 zawiera: `| GarageBand 🆕 | 682658836 |`.

**Przyczyna źródłowa.** Toolkit sam dopisuje nowe aplikacje do sekcji „🆕"
z markerem w nazwie. `norm_name()` usuwało tylko `-_ .`, więc:

```
norm_name("GarageBand 🆕") == "garageband🆕"  ≠  "garageband"
```

Każda aplikacja dopisana automatycznie była więc zgłaszana jako nowa **przy każdym
kolejnym przebiegu** — pętla samopodtrzymująca się.

Dodatkowo `update_all.sh` miał **dwie inline'owe kopie** `norm_name()`, które
przesłaniały wersję kanoniczną i cofały każdą jej poprawkę.

**Poprawka**

- `lib/python/inventory.py` — `norm_name()` usuwa znaki kategorii Unicode
  `So`/`Sk`/`Cf` (emoji, modyfikatory, selektory wariantów) obok dotychczasowych
  separatorów,
- obie przesłaniające definicje w `update_all.sh` usunięte, z komentarzem
  wyjaśniającym, dlaczego nie wolno ich przywracać.

---

## P1-2 — Antigravity ostrzegał `⏭️ Nieznana wersja` przy każdym przebiegu

**Przyczyna źródłowa.** `Contents/Resources/app-update.yml` wskazuje na
`https://antigravity-hub-auto-updater-…run.app/manifest/`, który **nie jest
statycznym manifestem** — oczekuje parametrów platformy i architektury. Sprawdzone
na żywo: `latest-mac.yml`, `latest.yml` i sam katalog zwracają 404.

To fakt o kanale dostawcy, nie usterka przebiegu. Aplikacja aktualizuje się sama.

**Poprawka** (`lib/internet_handlers.sh`): nieosiągalny manifest przy istniejącym
feedzie jest raportowany jako informacja
(`L_INTERNET_FEED_NOT_MACHINE_READABLE_FMT`). Feed, który **odpowiada**, ale nie
zawiera wersji, nadal ostrzega — ta ścieżka diagnostyczna zostaje nienaruszona.

---

## Pozostawione świadomie

| Pozycja z logu | Decyzja |
|---|---|
| `mas account` — nie można odczytać Apple ID | Znany regres macOS 26.x po stronie Apple; obsłużone, opisane w logu |
| Office `DeferralDays=7` (MSWD2019 …) | Świadoma kwarantanna po regresie pakietu Preview 2026-07-14 — działa zgodnie z projektem |
| `ChannelName = Preview` | Trwała naprawa = zmiana kanału MAU; **decyzja użytkownika**, otwarta od 2026-08-19 |
| IPMIView, DJI Assistant 2 — brak auto-updatera | Prawidłowo raportowane jako aktualizacja ręczna |

---

## Testy

Nowy plik `tests/test_run_log_regressions_20260826.py` — 19 testów, jedna grupa na
każdą przyczynę źródłową, w tym asercja, że **wszystkie 7 plików językowych**
definiuje trzy nowe klucze i18n.

```
── 1/4  bash -n on all .sh                    ✅
── 2/4  py_compile + inline heredocs          ✅
── 3/4  unittest discover tests    189 tests  OK
── 4/4  scan_secrets.sh (gitleaks) no leaks   ✅
        ALL CHECKS PASSED ✅
```

## Zmienione pliki

```
VERSION                                       1.4.1 → 1.4.2
CHANGELOG.md                                  wpis [1.4.2]
update_npm_cli.sh                             native_installer_env/_timeout
update_brew.sh                                ewidencja Homebrew + porównanie schematów
update_all.sh                                 usunięte przesłaniające norm_name()
lib/version.sh                                app_vs_package_version_relation()
lib/internet_app_updates.sh                   Ledger sha512 + weryfikacja usunięć MAU
lib/internet_handlers.sh                      feed bez czytelnego manifestu
lib/python/inventory.py                       norm_name() bez markerów
i18n/lang_{pl,en,de,fr,es,it,pt}.sh           3 nowe klucze × 7 języków
tests/test_run_log_regressions_20260826.py    19 testów regresyjnych
docs/reviews/ULTRA_REVIEW_2026-08-26.md       ten dokument
```

---

## Przebieg kontrolny po poprawkach (2026-08-26 23:02, `--skip-appstore --skip-system`)

| Krok | Przed (10:15) | Po (23:02) |
|---|---|---|
| `prescan` | OK (ale zgłaszał GarageBand) | **OK** — `✅ Wszystkie aplikacje z /Applications są w APPLICATIONS.md` |
| `npmcli` | ⚠️ Ostrzeżenie (codex `exit=124`) | **OK completed** — `✅ codex-cli: 0.150.0` |
| `brew` | ⚠️ Ostrzeżenie (brave pominięty) | **OK completed** — `brave-browser 1.93.136.0 → 1.93.138.0` |
| `internet` | ⚠️ Ostrzeżenie (Ledger, Antigravity, MAU) | ⚠️ Ostrzeżenie — **wyłącznie z powodów projektowych** |

Realne aktualizacje odblokowane w tym przebiegu:

```
✅ codex-cli:      0.149.1  → 0.150.0     (blokowane od wielu przebiegów)
✅ brave-browser:  1.93.136.0 → 1.93.138.0 (blokowane strażnikiem downgrade'u)
✅ Ledger Wallet:  4.15.0   → 4.17.1      (blokowane niezgodnością sumy kontrolnej)
✅ Antigravity:    informacja zamiast ostrzeżenia
✅ GarageBand:     brak fałszywego „nowa aplikacja"
```

Pozostałe ostrzeżenia kroku `internet` po poprawkach — wszystkie zamierzone:
kwarantanna Office (`DeferralDays=7`), IPMIView i DJI Assistant 2 (brak
auto-updatera), VS Code 1.135.0 (aktualizuje się sam).

**Uwaga operacyjna:** przebieg zatrzymał się na ~4 min na oknie uwierzytelniania
`sudo` przy `brew upgrade --cask spotify` (`launchctl print gui/501/...`).
Zachowanie sprzed tych zmian i niezwiązane z nimi, ale w trybie
`MAC_UPDATE_NONINTERACTIVE=1` i tak potrafi zablokować przebieg bez terminala —
warto rozważyć osobno.
