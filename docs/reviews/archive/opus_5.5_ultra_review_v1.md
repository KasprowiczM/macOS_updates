# Ultra Review — macOS Updates v1.4.6 na macOS 27 Golden Gate (Opus 5.5, v1)

> **Data:** 2026-09-23 · **Commit:** `0a613d0` (`main`, tag `v1.4.6`) · **System:** macOS 27.0 (26A428), Apple Silicon
> **Narzędzia:** Homebrew 7.0.6-21 · mas 7.0.0 · Bash 3.2 · Python 3 · 326 testów zielonych
> **Zakres (zgodnie z poleceniem):** główna funkcja — *wszystko aktualizuje się, najlepiej w tle, zawsze z najlepszego
> (oryginalnego) źródła*; inwentarz odporny na ręczne zmiany; odinstalowane aplikacje nigdy nie wracają do pipeline'u.
> **Tryb:** wyłącznie odczyt. Nie zmieniono kodu, konfiguracji ani systemu (jedyny skutek uboczny opisany w §10).
> **Metoda:** skille `ultra-review` (6 faz), `systematic-debugging` (przyczyna źródłowa każdej anomalii z logu),
> `agentic-memory` (kontekst projektu i handoff). Dokumentacja: Context7 (Sparkle), WebSearch/WebFetch (Homebrew,
> Docker, mas, Apple, Codex, Cursor, Installomator, App Auto-Patch). `deep-research` pominięty — wymaga płatnego klucza Gemini.

---

## 0. Wniosek w jednym akapicie

Toolkit jest bezpieczny i uczciwy w tym, **jak** instaluje (weryfikacja podpisów, Team ID, `spctl`, rollback, MAU
guard, 326 testów). Ma jednak trzy luki strukturalne w tym, **co i kiedy** aktualizuje, i one uderzają dokładnie w
Twoje wymagania. **(1) Nic nie działa w tle.** LaunchAgent zainstalowany 2026-09-16 nie wykonał ani jednego
przebiegu: macOS Background Task Management ma go jako `disallowed`, a instalator mimo to pisze „✅ Installed and
loaded”. **(2) Odinstalowanie nie jest stanem, który toolkit rozumie.** CLI (codex, cursor-agent, claude, agy, pnpm,
bun) są doinstalowywane z powrotem, bo kod ma semantykę „ensure”, a nie „update”. Aplikacja z caska przeciągnięta do
Kosza sprawi, że przy następnej wersji `brew upgrade` rzuci `CaskError` i **zablokuje aktualizację macOS**. Inwentarz
wykrywa usunięcia tylko w GRUPIE 3. **(3) „Zweryfikowane” nie zawsze znaczy zweryfikowane.** Wyrocznią jest wersja
caska w repozytorium Homebrew, a nie feed producenta, więc wynik opóźnia się względem producenta. Mapowanie `Gemini → gemini`
wskazuje na **MacPaw Gemini** (wyszukiwarkę duplikatów). Parser Sparkle bierze pierwszy wpis appcastu, więc Remote
Desktop Manager „przechodzi weryfikację” na martwym feedzie zakończonym na wersji 2023.1.12. Rozwiązaniem nie jest
kolejna łatka, tylko **rejestr źródeł per aplikacja** (feed producenta jako prawda + oryginalny updater jako
wykonawca + Homebrew tylko tam, gdzie nie odstaje), **inwentarz z tombstone'ami** i **trójwarstwowy tryb w tle**
(watcher inwentarza, bezpieczny dzienny przebieg bez sudo i GUI, interaktywny „finisher”). Szczegóły: §5, plan: §7.

### 0.1 Dziesięć najważniejszych ustaleń

| # | Prio | Ustalenie | Dowód (skrót) | Co to znaczy dla Ciebie |
|---|:--:|---|---|---|
| 1 | **P0** | LaunchAgent nie działa, instalator raportuje sukces | `launchctl print gui/501/com.<user>.macos-updates` → *Could not find service*; `sfltool dumpbtm` → `Name: bash`, `Disposition: [enabled, disallowed, notified]`; brak `logs/launchd.out` | Od instalacji (16.09) zero przebiegów w tle, pominięty zaplanowany przebieg pon. 21.09 |
| 2 | **P0** | Cask z aplikacją w Koszu blokuje krok brew i odracza macOS | Homebrew 7.0.6 `cask/artifact/moved.rb:212-215` rzuca `CaskError "…source is not there"`; `update_brew.sh:322-352` mimo braku `.app` dodaje cask do `UPGRADEABLE_CASKS` | Jedno ręczne odinstalowanie = czerwony przebieg i brak aktualizacji systemu |
| 3 | **P0** | Odinstalowane CLI wracają | `update_npm_cli.sh:789-840` (instalator zawsze dla codex/cursor-agent, dla claude/agy gdy brak binarki), `:871` (`npm install -g pnpm@latest`), `:775` (bun) | Usuwasz `codex`, jutro znów jest |
| 4 | **P0** | Fałszywie zielone „zweryfikowane” | RDM: feed 338 wpisów od najstarszego, max `2023.1.12.0`; Gemini → cask `com.macpaw.site.Gemini2`; Comet: cask `145.2…` < zainstalowany `152.0…` → zawsze „aktualna” | Metryka pokrycia zawyżona, zaległości niewidoczne |
| 5 | **P1** | `silent_launch` zostawia ~12 aplikacji uruchomionych, a aktualizacja ląduje dopiero przy ich zamknięciu | `update_internet_apps.sh:334-353` (`open -gjF`, nigdy quit); `internet_behind ≥ 1` w 6 z 7 przebiegów od 16.09 (Antigravity, Claude, ChatGPT, Cursor, Warp — każda dogania dopiero w kolejnym przebiegu) | Docker odpala VM, RAM zajęty, update dzień później |
| 6 | **P1** | ChatGPT: producent ma nowszą wersję niż Homebrew | appcast producenta `26.917.62051` > cask `26.917.61114` > zainstalowany `26.917.51856` | Dokładnie Twój przypadek „brew później niż oryginał” |
| 7 | **P1** | Inwentarz dryfuje | w `APPLICATIONS.md`: `gemini-cli`, `qwen-code`, `Notion Web Clipper` (odinstalowane), brak `cursor-agent`, `WiFiman`, `Picsart`; `GarageBand 🆕` poza tabelą | Inwentarz nie odzwierciedla Maca |
| 8 | **P1** | Aplikacje iPad: Track 2 ślepy, klasyfikacja błędna | iTunes Lookup API zwraca wersje UniFi/WiFiman/Picsart/S2M/TrackMan/**IPMIView** (to aplikacja iPad z App Store, id 952163566, nie Java z supermicro.com) | Chroniczne „⚠️ niezweryfikowane”, GUI otwierane bez potrzeby |
| 9 | **P1** | Tryb w tle niekompletny nawet po naprawie #1 | `update_brew.sh` ignoruje `MAC_UPDATE_NO_SUDO` (Zoom = `pkg` + sudo); mas wymaga sudo; macOS na Apple Silicon wymaga poświadczeń właściciela woluminu | Przebieg z launchd skończyłby się błędem Zoom |
| 10 | **P1** | `--greedy-auto-updates` jest dziś kontrproduktywne | Homebrew (PR #21882, 2026-04-08) sam porównuje wersję bundla dla `auto_updates` i robi „metadata-only upgrade” | Zbędne pobrania, własny strażnik downgrade'u dubluje Homebrew |

---

## 1. Faza 1 — pomiar stanu zastanego (ground truth)

| Obszar | Pomiar | Wynik |
|---|---|---|
| Testy | `bash run_tests.sh` | `bash -n` OK, `py_compile` OK, **326/326 OK** (41,6 s), gitleaks: 124 commity, brak wycieków |
| Git | `git status`, `git log` | `main` = `0a613d0` = tag `v1.4.6`; 4 nieśledzone review w `docs/reviews/` |
| Harmonogram | `launchctl print gui/$(id -u)/com.<user>.macos-updates` | **Could not find service** |
| Background Task Management | `sfltool dumpbtm` | `Type: legacy agent`, `Executable Path: /bin/bash`, `Parent: Unknown Developer`, **`Disposition: [enabled, disallowed, notified]`** |
| Ślady przebiegów launchd | `ls logs/launchd.*` | brak plików → **0 przebiegów zaplanowanych** |
| Automatyczne aktualizacje Apple | `defaults read /Library/Preferences/com.apple.SoftwareUpdate` | `AutomaticDownload=1`, `AutomaticallyInstallMacOSUpdates=1`, `CriticalUpdateInstall=1`, `ConfigDataInstall=1`; App Store `AutoUpdate=1` |
| Chrome | bundle vs VersionHistory API vs log GoogleUpdater | zainstalowany `153.0.8010.53`; stable mac_arm64 `154.0.8037.58` (`fraction 1`, od 2026-09-22 18:08 UTC); Omaha dla tej kohorty: `updatecheck: noupdate` |
| ChatGPT / Codex | bundle vs cask vs appcast producenta | `26.917.51856` < cask `26.917.61114` < **producent `26.917.62051`** |
| Comet | bundle vs cask | `152.0.7977.197` vs cask `145.2.7632.4581` → cask **za** producentem |
| Gemini | `brew info --cask gemini` | `url …/com.macpaw.site.Gemini2/…` → **inna aplikacja** |
| Remote Desktop Manager | `SUFeedURL` vs `productinfo.htm` | feed: 338 pozycji, rosnąco, max `2023.1.12.0`; producent: `RDMMacbin.Version=2026.3.0.5` + URL + SHA-256 |
| Docker Desktop | appcast arm64 | max `4.92.0` = zainstalowany (dało się sprawdzić bez uruchamiania VM) |
| Updatery Google | `ksadmin --print`, log GoogleUpdater | user-scope: `com.google.chrome`, `com.google.geminimacos`; system-scope: `com.google.drivefs 131.0.2.0`; Keystone shim uruchamia `GoogleUpdater --wake-all [--system]` → poprawnie |
| Updater Comet | `~/Library/LaunchAgents/ai.perplexity.CometUpdater.wake.plist` | `CometUpdater --wake-all` (updater Chromium) — toolkit go nie używa |
| Aplikacje iPad | `Wrapper/iTunesMetadata.plist` + `itunes.apple.com/lookup` | UniFi 1057750338, WiFiman 1385561119, Picsart 587366035, S2M 1359042934, TrackMan 1192720039, **IPMIView 952163566** — wersje z API = zainstalowane |
| CLI na dysku | `command -v` | `gemini`, `qwen` **nie istnieją**; `cursor-agent`/`agent` istnieją |
| Śmieci po updaterach CLI | `du -sh` | `~/.codex/packages/standalone/releases`: **13 wersji, ~3,6 GB**; `~/.local/share/cursor-agent/versions`: **7 wersji, ~3,2 GB**; `~/.local/bin/agy.*.old`: 184 MB |
| Nie objęte | `uv tool list` | `flow-agent`, `graphifyy` (poza zakresem toolkitu) |

### 1.1 Ostatni przebieg — 2026-09-23 09:41:54 (8 min 39 s, uruchomiony ręcznie)

| Krok | Status w logu | Co faktycznie się stało | Komentarz |
|---|---|---|---|
| 0 Prescan | OK „nie wykryto zmian” | nie wykrył `Notion Web Clipper`, `gemini-cli`, `qwen-code` jako usuniętych | wykrywanie usunięć tylko w GRUPIE 3 (`update_all.sh:876`) |
| 1 App Store | ⚠️ ostrzeżenie | `mas outdated` puste, a Track 2 i tak kliknął „Update All”; **Picsart 30.7.2 → 30.8.2 zaktualizował się**, ale nigdzie tego nie przypisano | sukces Track 2 jest niewidoczny, ostrzeżenie chroniczne |
| 2 CLI | OK | npm 12.0.2→12.1.0, claude 2.1.278→2.1.280, codex 0.155.1→0.156.1, agy 1.2.8→1.2.9, cursor-agent → 2026.09.18 | codex i cursor-agent przez ponowne uruchomienie skryptu instalacyjnego, choć mają `codex update` / `agent update` |
| 3 Homebrew | OK | 4 formulae, casks `appcleaner` 3.6.8→3.7, `zoom` 7.1.5→7.2.1 (pkg, `sudo`) | Zoom w tle by nie przeszedł (sudo) |
| 4 Internet | OK | MS365 16.113.1→.2 (XCEL2019: *„Updater failed to validate applied update. Repairing”* → pełne pobranie → OK), Ledger 4.21.0→4.21.1 (zweryfikowany), Cursor 3.21.16→3.21.18; **ChatGPT „w tyle”**; Chrome „✅ Sprawdzony przez CLI”; Docker Desktop uruchomiony (VM) tylko po to, by wyrocznia casku powiedziała „aktualna” | „w tyle” nie zmienia statusu kroku (`internet=ok`) |
| 5 Inwentarz | OK (20 pól) | Claude 2.2553.13→2.7032.0 i ChatGPT 26.915→26.917 zmieniły się **między prescanem a snapshotem kroku 4** | nie ma ich w sekcji „📌 Zaktualizowano” |
| 6 macOS | OK | „No new software available” | — |
| Log | 1909 linii | ~1000 linii to zrzut list `brew` z katalogu sesji, bo krok 1 miał *miękkie* ostrzeżenie | `update_all.sh:431` zrzuca snapshoty także przy `DEGRADED` |

**Trend z 12 ostatnich `run_summary_*.json`:** App Store `warn` w 3 z 12 przebiegów, `internet_behind ≥ 1` w 6 z 7 przebiegów
od 16.09 (rekord: 4 aplikacje 18.09), a status kroku `internet` zawsze `ok`. Z `version_history.tsv` wynika wzorzec:
aplikacje `silent_launch` (ChatGPT, Claude, Cursor, Warp, Antigravity) są „w tyle” w jednym przebiegu i doganiają
w następnym. Updater producenta pobiera wersję, gdy toolkit uruchomi aplikację, ale instaluje ją dopiero przy zamknięciu.

---

## 2. Faza 2 — co działa (zweryfikowane, do zachowania)

1. **Microsoft AutoUpdate** — najlepszy moduł projektu: guard regresji, reconciliacja deferrali, sanitizacja, wybór ID.
   W tym przebiegu sam obsłużył nieudaną walidację XCEL2019 i zakończył z `msupdate --list` = 0.
2. **Instalacje bezpośrednio od producenta z pełną weryfikacją** (Firefox Dev, KeePassXC, Trezor, Ledger, VS Code,
   CodeEdit): unikalny mountpoint, `hdiutil verify`, Team ID, `spctl`, staged swap z rollbackiem. To jest wzorzec,
   który warto rozszerzyć na kolejne aplikacje (§5.6 `vendor_direct`).
3. **CLI przez oryginalne updatery**: `claude update`, `agy update`, `opencode upgrade --method npm`, `bun upgrade`,
   zarządzany prefiks z pierwszeństwem w `PATH`, `report_cli_version_or_fail`. Ta część jest zgodna z Twoją filozofią:
   Claude Code CLI przez natywny updater, a nie przez npm.
4. **Homebrew przez `lib/brew.sh`**: odporne zapytania, bramka licencji Xcode, diagnoza CLT, strażnik downgrade'u,
   końcowa weryfikacja `outdated`.
5. **System**: `softwareupdate -i <label> -R`, klasyfikacja major/minor, `MAC_UPDATE_ALLOW_MAJOR_UPGRADE`.
6. **Trigger Google jest poprawny**, choć nie wiadomo o tym w kodzie. Shim Keystone uruchamia
   `GoogleUpdater --wake-all` (user) oraz `--wake-all --system`, a te wykonują `UpdateAll` dla Chrome, **Gemini** i
   **Google Drive** (log 09:46:42–09:46:46).
7. **Obserwowalność**: schema v4, `items`, stabilne kody kroków, `version_history.tsv`, raport chronicznych ostrzeżeń.
8. **Higiena**: 326 testów, gitleaks, ShellCheck, strażnicy statyczni (`test_safety_static.py`), zakaz `set -e`.

---

## 3. Faza 3 — zweryfikowane luki

Każda pozycja: **dowód → scenariusz awarii → przyczyna źródłowa → poprawka**.

### P0-1 — Harmonogram w tle nie działa, a instalator twierdzi, że działa

- **Dowód:** plik `~/Library/LaunchAgents/com.<user>.macos-updates.plist` istnieje (2026-09-16, `plutil -lint` OK, bez
  kwarantanny, `print-disabled` = `enabled`). Mimo to `launchctl print` nie znajduje usługi, a `sfltool dumpbtm`
  pokazuje `Disposition: [enabled, disallowed, notified]`. Nie ma żadnego `logs/launchd.out` ani `logs/launchd.err`.
- **Przyczyna:** Background Task Management (macOS 13+) wyświetlił powiadomienie o elemencie „**bash**” od
  „**Unknown Developer**”, a przełącznik „Zezwalaj w tle” jest wyłączony. Taka nazwa nic nie mówi, więc łatwo ją
  wyłączyć. `scripts/install_launchagent.sh:138-144` wykonuje `bootstrap … 2>/dev/null || load -w … || true` i
  **bezwarunkowo** drukuje „✅ Installed and loaded”. To łamie zasadę projektu „mutacja jest zrobiona dopiero, gdy
  potwierdzi to żywy system”.
- **Poprawka:**
  1. Program w plistcie: wrapper `bin/macos-updates-scheduled` (shebang `#!/bin/bash`, `exec update_all.sh --background`).
     BTM pokaże wtedy nazwę „macos-updates-scheduled”, a nie „bash”.
  2. Po `bootstrap` weryfikacja `launchctl print gui/$UID/<label>` oraz parsowanie `sfltool dumpbtm` pod kątem
     `disallowed`. W razie problemu: komunikat z dokładną ścieżką *Ustawienia → Ogólne → Rzeczy otwierane przy
     logowaniu i rozszerzenia → Zezwalaj w tle*, otwarcie `x-apple.systempreferences:com.apple.LoginItems-Settings.extension`
     i kod wyjścia ≠ 0.
  3. `install_launchagent.sh --status`: loaded / BTM disposition / ostatni przebieg / ostatni exit code.
  4. Test: atrapa `launchctl` zwracająca błąd → skrypt **nie może** wypisać ✅.

### P0-2 — Aplikacja z caska przeciągnięta do Kosza blokuje krok Homebrew i odracza aktualizację macOS

- **Dowód (kod Homebrew 7.0.6):** `Cask::Installer#start_upgrade` → `uninstall_artifacts(skip: false)` →
  `Artifact::Moved#move_back`, który przy braku `target` wykonuje
  `raise CaskError, "It seems the App source '…' is not there."` (`/opt/homebrew/Library/Homebrew/cask/artifact/moved.rb:212-215`).
  **Dowód (toolkit):** `update_brew.sh:322-333` szuka `.app` w `/Applications`, potem w `Caskroom`. Gdy nic nie
  znajdzie, pomija porównanie wersji i **dodaje cask do `UPGRADEABLE_CASKS`** (`:352`). Potem `brew upgrade --cask`
  (`:357`) kończy się błędem → `HARD_FAIL=1` → `BLOCKING_EXIT` → krok 6 (macOS) zostaje odroczony.
  W inwentarzu wiersz z sekcji 4c też zostaje na zawsze (prescan szuka tylko *nowych* casków).
- **Scenariusz:** usuwasz np. CapCut przez Finder albo AppCleaner, a nie `brew uninstall`. Przy następnej wersji
  CapCut każdy przebieg jest czerwony, a macOS się nie aktualizuje.
- **Poprawka:** detektor **osieroconych casków** w prescanie: cask ma artefakt `app`, a żaden z celów nie istnieje w
  `/Applications` ani `~/Applications`. Taki cask jest (a) pomijany w `brew upgrade`, (b) zapisywany jako tombstone
  (§5.4), (c) w trybie interaktywnym toolkit proponuje `brew uninstall --cask --force <token>` (tylko po potwierdzeniu),
  w tle wyłącznie raportuje. Test: atrapa `brew info --json=v2` z artefaktem `app` bez bundla → cask nie trafia do upgrade.

### P0-3 — Odinstalowane CLI wracają (semantyka „ensure” zamiast „update”)

- **Dowód:**
  - `update_npm_cli.sh:789-840` `install_native_cli`: dla `codex` i `agent` (`native_installer_existing_update_cmd`
    zwraca pusty ciąg, `lib/native_installers.sh:52`) **zawsze** pobiera i uruchamia `install.sh`. Dla `claude`/`agy`
    robi to samo, gdy binarki brak w `~/.local/bin`.
  - `:871` metoda `npm`: `npm install -g <pkg>@latest` bez sprawdzenia obecności (pnpm).
  - `:775` `ensure_latest_bun`: brak binarki → `install_bun_tarball`.
  - Wyjątek jest jeden: `self-update` (opencode) poprawnie wypisuje „nie zainstalowane” i przechodzi dalej.
- **Scenariusz:** `rm ~/.local/bin/codex` albo odinstalowanie przez producenta → następny `update_all.sh` instaluje ponownie.
- **Przyczyna:** logika bootstrapu (właściwa dla `setup.sh`/`migration_setup.sh`) została przeniesiona do ścieżki aktualizacji.
- **Poprawka:** w `update_all.sh` zasada „**tylko to, co zainstalowane**”. Doinstalowanie zostaje tylko w `setup.sh` /
  `migration_setup.sh` / fladze `--bootstrap`. Wyjątek: `node`/`npm` jako zależność runtime **zainstalowanych** CLI
  npm. Tombstone (§5.4) blokuje ponowną instalację nawet w trybie `--bootstrap`, dopóki użytkownik go nie usunie.

### P0-4 — Fałszywie zielone „zweryfikowane”

| Przypadek | Dowód | Mechanizm błędu |
|---|---|---|
| Remote Desktop Manager „✅ Aktualny (2026.3.0.5)” | `SUFeedURL` = feed rosnący, 338 wpisów, max `2023.1.12.0` | `lib/internet_handlers.sh:229-237` bierze `head -1` (= `0.9.0.3`), relacja „remote nie nowszy” = „current”. **Feed jest martwy**, ale nikt tego nie wie |
| Gemini (Google) | `config/cask_oracles.txt:13` `Gemini\|gemini`; cask `gemini` = `com.macpaw.site.Gemini2` 2.10.1 | wyrocznia porównuje aplikację Google z produktem MacPaw. Dziś wychodzi `unknown` (⏳), jutro może wyjść „w tyle” albo „aktualna” — oba wyniki fałszywe |
| Comet „✅ aktualna (cask)” | cask `145.2.7632.4581`, zainstalowany `152.0.7977.197` | cask nie nadąża za producentem, więc relacja zawsze daje „current” i nie da się wykryć zaległości |
| Wszystkie „✅ aktualna (cask)” | `update_internet_apps.sh:632-724` | wyrocznia = **wersja w repozytorium Homebrew**, nie feed producenta. ChatGPT pokazuje, że cask potrafi być 1–2 buildy za producentem |
| Chrome / Drive „✅ Sprawdzony przez CLI” | log GoogleUpdater: `updatecheck: noupdate`; publiczny stable = 154.0.8037.58 | status mówi „sprawdzono”, ale nie „co odpowiedział producent”. Użytkownik nie wie, że czeka na rollout |

- **Reguła, którą trzeba dodać do `critical_rules.md` §6b:** *„zweryfikowane” = porównano z **najwyższą** wersją z
  **feedu producenta** dla właściwego kanału. `remote < local` to `feed_stale`, a nie `current`. Wyrocznia caska może
  tylko **potwierdzić zaległość**, nigdy aktualności.*
- **Poprawka parsera Sparkle** (lepiej w `lib/python/feeds.py` jako czysta funkcja niż w `grep`): maksimum po
  `sort -V` ze wszystkich `<item>`; filtr `sparkle:channel` (domyślnie bez kanału lub `stable`);
  `sparkle:minimumSystemVersion ≤ sw_vers`; porównanie `shortVersionString ↔ CFBundleShortVersionString` oraz
  `sparkle:version ↔ CFBundleVersion` (nigdy krzyżowo); wynik `feed_stale`, gdy max < zainstalowana.

### P1-5 — `silent_launch`: aplikacje zostają uruchomione, aktualizacja ląduje dopiero po zamknięciu

- **Dowód:** `update_internet_apps.sh:334-353` używa `open -gjF` i nie ma ścieżki zamknięcia (grep `quit app` = 0
  trafień poza MAU). Po przebiegu w tle działają m.in. ChatGPT, Claude, Comet, Antigravity, Antigravity IDE,
  OpenCode, Proton Mail, Teams, Warp, Cursor, Proton Drive, RDM i **Docker Desktop z maszyną wirtualną**.
  Squirrel.Mac i Sparkle instalują pobraną wersję przy zamknięciu aplikacji, stąd stały wzorzec „w tyle → dogania
  w następnym przebiegu”.
- **Poprawka („launch cycle”):** najpierw sprawdzić feed producenta (read-only, §5.2). **Nie uruchamiać niczego, co
  jest aktualne.** Gdy producent ma nowszą wersję:
  - aplikacja Sparkle → `sparkle` CLI (§5.6), który sam zamyka, instaluje i uruchamia ponownie, a przy uruchomionej
    aplikacji użyć `--defer-install`;
  - aplikacja Squirrel/Electron, której toolkit **sam** nie uruchomił wcześniej → `open -gj`, poczekać do
    `MAC_UPDATE_STAGE_TIMEOUT` (sprawdzając feed/katalog `ShipIt`), potem łagodnie `osascript -e 'quit app id "<bundle_id>"'`
    i odczytać wersję ponownie;
  - aplikacja uruchomiona przez użytkownika → nie zamykać, status `staged` („zainstaluje się przy zamknięciu”);
  - brak zbieżności przez N przebiegów (domyślnie 2) → eskalacja do `vendor_direct` (zweryfikowane pobranie od
    producenta z pinem Team ID) albo do caska, jeśli cask ≥ producent.
- **Status kroku:** `behind` utrzymujące się ≥ 2 przebiegi → `warn` (dziś `internet=ok` przy 4 zaległych).

### P1-6 — Google Updater: dobry trigger, ale raport ukrywa odpowiedź producenta; Gemini źle sklasyfikowany

- **Dowód:** `ksadmin --print` i żądanie Omaha w logu GoogleUpdater zawierają `com.google.geminimacos`. Gemini jest
  więc aktualizowany przez **ten sam** trigger co Chrome, a mimo to ma metodę `silent_launch` i błędną wyrocznię (P0-4).
  Google Drive jest zarejestrowany w **system-scope** updaterze jako `131.0.2.0`, podczas gdy bundle podaje `131.0`.
- **Poprawka:** metoda `google_updater` (nazwa `keystone` zostaje jako alias dla zgodności testów):
  1. jeden trigger na przebieg (dziś są dwa: Chrome i Drive);
  2. wersja z rejestracji updatera (`ksadmin --print` / `KSVersion`), nie z `CFBundleShortVersionString`;
  3. wynik z logu Omaha dla `appid`: `noupdate` → status `rollout_hold`, jeśli VersionHistory ma nowszy stable z
     `fraction=1`, w innym przypadku `current_verified`; `ok` + nowa wersja na dysku → `updated`;
     Chrome z nową wersją na dysku i starym procesem → `staged` („zrestartuj Chrome”);
  4. Gemini przenieść do tej metody i usunąć `Gemini|gemini` z `cask_oracles.txt`.
- **Comet** ma własny updater Chromium (`CometUpdater --wake-all`, LaunchAgent `ai.perplexity.CometUpdater.wake`).
  Metoda `chromium_updater`: `launchctl kickstart gui/$UID/ai.perplexity.CometUpdater.wake`, a weryfikacja przez
  JSON producenta (`perplexity.ai/rest/browser/update?…platform=mac_arm64`, adres z livechecku caska).

### P1-7 — Inwentarz dryfuje i nie rozumie usunięć

- **Dowód (stan `APPLICATIONS.md` z 2026-09-23 09:50):**
  - usunięte, a nadal wpisane: `gemini-cli 0.46.0`, `qwen-code 0.17.1` (4d), `Notion Web Clipper` (GRUPA 2, brak w `mas list`);
  - brakujące: `cursor-agent` (aktualizowany w każdym przebiegu), `WiFiman`, `Picsart` (świadomie pominięte w
    `update_all.sh:718`, choć `UniFi` jest wpisany);
  - nieaktualne wersje: `Ascendo 0.2.0` (zainstalowane 1.0.4), `Google Docs/Sheets/Slides 129.0` (131.0).
    Dodatkowo są to skróty Google Drive (`com.google.drivefs.shortcuts.*`), a nie PWA Chrome, jak twierdzi notka;
  - `| GarageBand 🆕 | 682658836 |` stoi **poza tabelą** (pusta linia przed markerem, `update_all.sh:996-999`);
  - „Podsumowanie” (Casks: 2, faktycznie 12) i „Legenda” (Brave/Perplexity/Zoom jako `update_internet_apps.sh`)
    są przestarzałe;
  - ChatGPT i Codex to dwa wiersze tej samej aplikacji (`com.openai.codex`).
- **Przyczyna:** usuwanie działa tylko dla GRUPY 3 (`update_all.sh:876-911`). Postupdate umie tylko **aktualizować**
  i **dodawać** wiersze. Tożsamość opiera się na nazwie i regexach, a nie na `CFBundleIdentifier` / tokenie caska /
  ID App Store / nazwie CLI. Skanowane jest tylko najwyższe piętro `/Applications`.
- **Poprawka:** Inwentarz v2 (§5.4): stan w `state/inventory.json`, `APPLICATIONS.md` renderowany w całości z tego
  stanu (bez chirurgii regexami), usunięcia i tombstone'y we **wszystkich** grupach, watcher uruchamiany po każdej
  ręcznej zmianie.

### P1-8 — Aplikacje iPad (Track 2) i App Store

- **Dowód:** Track 2 klika „Update All” w każdym przebiegu interaktywnym, także gdy nic nie czeka
  (`appstore_diag.txt`: `UPDATE_ALL_DEEP`, a `mas outdated` pusty), i zawsze kończy się „⚠️ niezweryfikowane”.
  Tymczasem:
  - każda aplikacja iPad ma `Wrapper/iTunesMetadata.plist` z `itemId` i `bundleShortVersionString`;
  - `https://itunes.apple.com/lookup?id=…` zwraca aktualną wersję w sklepie (sprawdzone dla 6 aplikacji);
  - **IPMIView** to aplikacja iPad (id 952163566), a nie Java z supermicro.com, więc metoda `manual` i link są błędne;
  - **S2M** i **TrackMan.Go.Ios** mają status „❓ unknown”, choć to aplikacje App Store.
  mas 7 ma wyjście `--json` dla `list`/`outdated`/`lookup`, a toolkit parsuje tekst regexami.
- **Poprawka:** metoda `appstore_lookup`: przed Track 2 porównanie wersji z API. Nic nie czeka → Track 2 pominięty
  (App Store `AutoUpdate=1` i tak aktualizuje w tle). Coś czeka → Track 2, potem weryfikacja tym samym API
  (`updated`/`behind`), zamiast `unverified`. Automatyczna klasyfikacja w prescanie: `iTunesMetadata.plist` → iPad
  App Store, `_MASReceipt` → Mac App Store. `mas … --json` wszędzie tam, gdzie się da.

### P1-9 — Tryb w tle jest niekompletny nawet po naprawie P0-1

| Element | Problem w trybie bez TTY | Dowód |
|---|---|---|
| Casks z `pkg`/`installer`/`uninstall launchctl` (Zoom; znany przypadek: `brew upgrade --cask spotify` woła `sudo launchctl`) | `brew` woła `sudo` → brak TTY → błąd → `HARD_FAIL` | `update_brew.sh` nie czyta `MAC_UPDATE_NO_SUDO` (grep); log: *„Uninstalling packages with sudo”* |
| mas Track 1 | wymaga `sudo` → pominięty jako soft | `update_appstore.sh:273` |
| Track 2 GUI | pominięty | `update_appstore.sh:358` |
| macOS | na Apple Silicon `softwareupdate` wymaga poświadczeń właściciela woluminu (`--user`/`--stdinpass`); Apple wspiera automatyzację tylko przez MDM/DDM | man `softwareupdate(8)`, munki-dev, Jamf |
| Apki uruchomione przez użytkownika | cask upgrade podmienia bundle pod działającą aplikacją | brak sprawdzenia `pgrep` |

- **Poprawka:** profil `--background` (§5.5) wykonuje tylko to, co jest bezpieczne bez sudo i GUI. Resztę odkłada do
  kolejki `needs_interactive` i wysyła powiadomienie („3 pozycje czekają na przebieg interaktywny”). macOS zostaje przy
  natywnych automatycznych aktualizacjach Apple (na tym Macu wszystkie włączone); toolkit tylko je **audytuje** i
  pobiera wstępnie.

### P1-10 — `--greedy-auto-updates` jest dziś zbędne, a nawet szkodliwe

- **Dowód:** Homebrew FAQ i PR #21882 (scalony 2026-04-08): dla casków `auto_updates true` zwykłe `brew upgrade`
  porównuje wersję **zainstalowanego bundla** z caskiem, aktualizuje tylko starszy bundle i wykonuje *metadata-only
  upgrade*, gdy aplikacja zaktualizowała się sama. `--greedy-auto-updates` (`lib/brew.sh:94`) wymusza ścieżkę opartą
  na zapisie w Caskroom, dlatego toolkit musi utrzymywać własny strażnik downgrade'u (`update_brew.sh:281-353`).
- **Poprawka:** `brew outdated --cask` bez greedy (natywne porównanie bundla). `HOMEBREW_UPGRADE_GREEDY_CASKS` tylko
  dla casków z listy „brew jest kanałem głównym” (np. `megasync`), wyliczanej z rejestru źródeł (§5.2). Strażnik
  downgrade'u zostaje jako druga linia obrony.

### P2-11 — CLI: własne updatery nieużywane, 7 GB starych wersji

- `codex update` istnieje od v0.128.0 (2026-04-30), a Cursor CLI ma `agent update`. Toolkit za każdym razem pobiera
  i uruchamia `install.sh` (`lib/native_installers.sh:49-54`). Zmienić mapę `existing_update_cmd` na
  `claude|agy|codex|agent → update` (instalator tylko w `--bootstrap`).
- Retencja: po udanej aktualizacji zostawić `current` + 1 poprzednią wersję (`~/.codex/packages/standalone/releases`,
  `~/.local/share/cursor-agent/versions`, `~/.local/bin/agy.*.old`). Usuwać tylko katalogi, na które **nie** wskazuje
  żaden symlink. Oszczędność na tym Macu to ok. 7 GB.

### P2-12 — Stany jako zlokalizowane napisy w kroku internet

`update_internet_apps.sh:742-747` liczy `verified`/`behind` przez dopasowanie podciągów (`"w tyle"`, `"behind"`,
`"cask)"` w 7 językach). Konfiguracja jest łączona pętlami zagnieżdżonymi po nazwie (O(n²), ~40 × 50 × 3 przebiegi).
Poprawka: `STATUS_CODE_<APP>` (enum z §5.3) obok napisu i jeden odczyt rejestru do tablicy równoległej (Bash 3.2)
albo do Pythona.

### P2-13 — Krok systemowy

- `update_system.sh:222-229` instaluje etykiety w pętli, każdą z `-R`. Jeśli pierwsza wymaga restartu, pozostałe
  nigdy się nie zainstalują. Poprawka: najpierw etykiety bez restartu, potem **jedno** wywołanie
  `softwareupdate -i <l1> <l2> … -R`.
- Tryb w tle: tylko audyt ustawień Automatic Updates i Background Security Improvements (odczyt `defaults`), plus
  raport „macOS X.Y pobrany, czeka na instalację”.

### P2-14 — Log puchnie przy miękkich ostrzeżeniach

`update_all.sh:431` zrzuca wszystkie snapshoty także przy `DEGRADED`. W ostatnim przebiegu to ~1000 z 1909 linii
(pełne listy formulae przed i po). Poprawka: zrzut tylko przy `BLOCKING_EXIT` albo `--debug`; przy `DEGRADED` tylko
pliki `*diag*.txt`.

### P2-15 — Dokumentacja agentów rozjechana z regułami

- `.claude/commands/mac-update-system.md` każe używać `sudo softwareupdate -ia -R`, co jest **sprzeczne z regułą
  krytyczną #1** (per label, bez `-ia`).
- `.claude/commands/mac-update.md` ma starą kolejność kroków (macOS jako krok 1).
- `.claude/commands/mac-update-appstore.md`: „macOS 26.x / CVE”, lista aplikacji nieaktualna.
- `CLAUDE.md`: tabela modeli (`claude-sonnet-4-6` / `claude-opus-4-7`) jest przestarzała.
- `update_all.sh:1653`: szablon awaryjny w postupdate nie zna `27: 'Golden Gate'` (prescan już zna, to duplikat, który się rozjechał).

### P2-16 — Docker Desktop uruchamiany bez potrzeby

`lib/internet_app_updates.sh` `iu_docker_desktop`: gdy Docker nie działa, toolkit go uruchamia (start VM) i zwraca
`unverified`. Appcast `desktop.docker.com/mac/main/arm64/appcast.xml` daje wersję bez uruchamiania. Poprawka: feed
najpierw. Gdy jest nowsza wersja → `docker desktop start`, potem `docker desktop update -q` i przywrócenie stanu
(`stop`, jeśli wcześniej nie działał). Kombinację `--check-only --quiet` trzeba zweryfikować na żywo, bo dokumentacja
opisuje `-q` jako „quietly check **and apply**”.

---

## 4. Faza 4 — research i benchmark (wrzesień 2026)

### 4.1 Fakty z ekosystemu istotne dla projektu

| Źródło | Fakt | Implikacja |
|---|---|---|
| Sparkle 2 — `sparkle-cli` (Context7: sparkle-project.org/documentation/sparkle-cli) | Oficjalne CLI aktualizuje **dowolną** aplikację Sparkle jej własnym feedem i podpisem EdDSA: `--probe`, `--check-immediately`, `--defer-install`, `--feed-url`, `--channels`, `--user-agent-name`; bez `--interactive` nie prosi o uprawnienia (exit 3); exit 8 = Gatekeeper | **Oryginalny updater, bez GUI, w tle**, dla: ChatGPT, Proton Drive, ProtonVPN, Perplexity, CodeEdit, CapCut, AppCleaner, Brave |
| Homebrew FAQ + PR #21882 | `brew upgrade` porównuje wersję bundla dla `auto_updates`, robi metadata-only upgrade; `HOMEBREW_UPGRADE_GREEDY_CASKS` pozwala wybrać caski | wycofać globalne greedy, brew jako kanał główny tylko z wyboru |
| Homebrew livecheck (źródła casków) | każdy cask ma zapisany **feed producenta**: ChatGPT `…/codex-app-prod/appcast.xml`, Claude `downloads.claude.ai/…/RELEASES.json`, Cursor `api2.cursor.sh/updates/…`, Warp `releases.warp.dev/channel_versions.json`, Comet `perplexity.ai/rest/browser/update`, Docker appcast, Proton Mail `version.json`, OpenCode `latest.json`, Antigravity hub, Chrome VersionHistory | gotowy katalog wyroczni producentów. `brew livecheck` w trybie API wymaga tapa, więc lepiej jednorazowo przenieść URL-e do `config/update_sources.txt` |
| Chromium updater (GoogleUpdater, CometUpdater) | `--wake-all` uruchamia `UpdateAll`; log zawiera żądanie i odpowiedź Omaha (`updatecheck.status`) | trigger jest oryginalny, a status da się odczytać z logu bez zgadywania |
| Google VersionHistory API | `…/platforms/mac_arm64/channels/stable/versions/all/releases?filter=endtime=none` → wersja + `fraction` | odróżnia „brak aktualizacji” od „rollout w toku” |
| iTunes Lookup API | `itunes.apple.com/lookup?id=…` → `version`, `currentVersionReleaseDate` (także dla aplikacji iPad) | weryfikacja Track 2 i jego pomijanie |
| mas 5 → 7 | usunięte `account`/`signin`; `--check-min-os`; mas 7: `--json` dla `list`/`outdated`/`lookup`; mas nadal nie obsługuje aplikacji iOS na Mac | zamienić parsowanie tekstu na JSON |
| `softwareupdate(8)` na Apple Silicon | instalacja wymaga właściciela woluminu (`--user`/`--stdinpass`); automatyzacja wspierana tylko przez MDM/DDM | macOS w tle zostawić Apple (Automatic Updates), toolkit tylko audytuje |
| Apple — Background Security Improvements (macOS 26+) | osobny przełącznik „Instaluj automatycznie” w Prywatność i ochrona | dołączyć do audytu postawy aktualizacji |
| Codex CLI ≥ 0.128 | `codex update` wykrywa metodę instalacji | koniec z ponownym uruchamianiem instalatora |
| Cursor CLI | `agent update`; domyślnie auto-update | j.w. |
| Docker Desktop CLI | `docker desktop update [-k/--check-only] [-q/--quiet]` | feed najpierw, CLI tylko gdy trzeba |
| Installomator | etykieta = `downloadURL` od producenta + `expectedTeamID` + `appNewVersion` + `blockingProcesses` | wzorzec dla metody `vendor_direct` (toolkit ma już 80% tego w `copy_verified_app`) |
| App Auto-Patch (2026) | wykrywanie zainstalowanych aplikacji → etykiety Installomatora, lista *ignored labels*; niedawno naprawiony błąd, przez który zignorowane etykiety mimo to trafiały do kolejki | tombstone'y muszą być sprawdzane przy **dokładnym** dopasowaniu i testowane regresyjnie |

### 4.2 Mapa „najlepsze źródło” dla aplikacji z tego Maca

Legenda kanałów: **native** = oryginalny updater producenta; **brew** = Homebrew cask; **direct** = zweryfikowane
pobranie od producenta (Team ID + `spctl`); **mas/lookup** = App Store. „Wyrocznia” = skąd brać prawdę o wersji.

| Aplikacja | Dziś | Oryginalny updater | Wyrocznia (producent) | Rekomendacja |
|---|---|---|---|---|
| Google Chrome | keystone (✅ „sprawdzony”) | GoogleUpdater | VersionHistory + odpowiedź Omaha | `google_updater`, statusy `rollout_hold`/`staged` |
| Gemini (Google) | silent_launch + **zła** wyrocznia | GoogleUpdater | Omaha | przenieść do `google_updater` |
| Google Drive | keystone | GoogleUpdater (system) | Omaha (`131.0.2.0`) | `google_updater`, wersja z rejestracji |
| Comet | silent_launch + wyrocznia za producentem | CometUpdater (Chromium) | JSON `perplexity.ai/rest/browser/update` | `chromium_updater` (kickstart wake) |
| Brave | brew (greedy) | Sparkle (feed w runtime) | appcast `updates.bravesoftware.com/…/stable-arm64` | brew bez greedy (lub `sparkle` CLI z `--feed-url`) |
| Firefox Dev | direct (product-details) | Balrog | product-details | bez zmian ✅ |
| **ChatGPT / Codex** | silent_launch, „w tyle” 18.09 i 23.09 | **Sparkle** (EdDSA) | appcast producenta (dziś `26.917.62051`) | `sparkle` CLI z `--feed-url`; eskalacja `direct` |
| Claude (desktop) | silent_launch | Squirrel | `RELEASES.json` (`currentRelease`) | wyrocznia producenta + launch cycle; eskalacja: brew albo `direct` (Team ID `Q6L2SF6YDW`) |
| Cursor | silent_launch | Squirrel (ToDesktop) | `api2.cursor.sh/updates/…` | j.w. |
| Warp | silent_launch | własny | `channel_versions.json` (`stable`) | j.w. |
| Antigravity / IDE | silent_launch | electron-updater / Squirrel | huby Antigravity (livecheck) | j.w. |
| OpenCode Desktop | silent_launch | electron-updater | GitHub `latest.json` | wyrocznia + `direct` przez GitHub release (Team ID `5NZ4Q7NXJ4`) |
| Proton Mail | silent_launch | Squirrel | `proton.me/download/mail/macos/version.json` | wyrocznia + launch cycle |
| Proton Drive | sparkle_appcast | Sparkle | appcast | `sparkle` CLI (instalacja, nie tylko weryfikacja) |
| Perplexity, ProtonVPN, AppCleaner, CapCut | brew | Sparkle | appcasty | brew bez greedy (cask = feed dziś); opcjonalnie `sparkle` CLI |
| MEGAsync | brew | własny | tagi GitHub `v…_OSX` | **brew jako główny** (Twoja decyzja, cask nadąża) — `HOMEBREW_UPGRADE_GREEDY_CASKS` |
| Zoom | brew (pkg + sudo) | `us.zoom.updater` (LaunchDaemon) | nagłówek `zoom.us/client/latest` | interaktywnie brew; w tle updater Zooma (bez naszego sudo) |
| Spotify, Obsidian, LM Studio, Inkscape | brew | własne | — | brew bez greedy; Spotify w tle tylko jeśli bez sudo |
| Microsoft 365 / Teams | msupdate / hybryda | MAU | `msupdate --list` | bez zmian ✅ |
| Docker Desktop | docker_cli (uruchamia VM) | własny | appcast arm64 | feed najpierw, CLI tylko przy nowszej wersji |
| VS Code, CodeEdit, KeePassXC, Trezor, Ledger | direct | własne / brak | API / GitHub / manifest | bez zmian ✅ |
| Remote Desktop Manager | sparkle_appcast (**martwy feed**) | własny | `devolutions.net/productinfo.htm` (`RDMMacbin.Version/Url/hash`) | `direct` z SHA-256 od producenta |
| UniFi, WiFiman, Picsart, **IPMIView**, S2M, TrackMan | appstore_gui / manual / unknown | App Store | iTunes Lookup | `appstore_lookup` (Track 2 tylko gdy trzeba) |
| Mac App Store (14 aplikacji) | `sudo mas upgrade` | App Store | `mas outdated --json` | bez zmian, JSON |
| Claude Code CLI, agy, opencode, bun | native | własne | — | bez zmian ✅ |
| Codex CLI, cursor-agent | ponowny instalator | `codex update`, `agent update` | — | przełączyć na własny updater |
| npm, pnpm, node | npm / n | — | — | tylko gdy zainstalowane |

---

## 5. Proponowana architektura — „najlepsze źródło per aplikacja” (nowe funkcje)

### 5.1 Siedem zasad (do `critical_rules.md`)

1. **Aktualizuj tylko to, co jest zainstalowane.** Instalacja brakującego elementu istnieje wyłącznie w
   `setup`/`migration_setup`/`--bootstrap`.
2. **Tombstone jest silniejszy niż konfiguracja.** Coś, co zniknęło z Maca, nie wraca bez jawnej decyzji użytkownika.
3. **Prawdą o wersji jest feed producenta.** Cask to drugi głos, który może potwierdzić zaległość, ale nigdy aktualności.
4. **Wykonawcą jest oryginalny updater.** Homebrew tylko tam, gdzie cask nie odstaje od producenta (mierzone, §5.3)
   albo gdzie brak natywnej ścieżki bez GUI. `direct` to eskalacja.
5. **Najpierw sprawdź, potem działaj.** Nie uruchamiaj aplikacji ani VM, jeśli feed mówi „aktualna”.
6. **„Zweryfikowane” = porównano z maksimum feedu producenta dla właściwego kanału.** `remote < local` = `feed_stale`.
7. **Tło nie prosi o nic.** Bez sudo, bez GUI, bez zamykania aplikacji użytkownika. Wszystko inne trafia do kolejki
   `needs_interactive` i jest zgłaszane powiadomieniem.

### 5.2 Rejestr źródeł `config/update_sources.txt` (zastępuje `cask_oracles.txt`, uzupełnia `internet_app_methods.txt`)

Format pipe-delimited, czytelny dla Bash 3.2, parsowany w `lib/python/sources.py` (czyste funkcje, testowalne):

```text
# name|bundle_id|primary|fallback|oracle|team_id
ChatGPT / Codex|com.openai.codex|sparkle_cli|direct|sparkle:https://persistent.oaistatic.com/codex-app-prod/appcast.xml|2DC432GLL2
Claude|com.anthropic.claudefordesktop|launch_cycle|brew:claude|json:https://downloads.claude.ai/releases/darwin/universal/RELEASES.json#currentRelease|Q6L2SF6YDW
Google Chrome|com.google.Chrome|google_updater|-|versionhistory:mac_arm64/stable+omaha:com.google.chrome|EQHXZ8M8AV
Gemini|com.google.GeminiMacOS|google_updater|-|omaha:com.google.geminimacos|EQHXZ8M8AV
Comet|ai.perplexity.comet|chromium_updater:ai.perplexity.CometUpdater.wake|-|json:https://www.perplexity.ai/rest/browser/update?browser=1.1.1.1&channel=stable&platform=mac_arm64&machine=0#version|7S8W4W365S
Remote Desktop Manager|com.devolutions.remotedesktopmanager|direct|-|kv:https://devolutions.net/productinfo.htm#RDMMacbin.Version|N592S9ASDB
MEGAsync|mega.mac|brew:megasync|-|github_tag:meganz/MEGAsync:_OSX|T9RH74Y7L9
Picsart|com.picsart.studio|appstore_lookup:587366035|-|itunes:587366035|-
```

Oracle kinds: `sparkle`, `json#path`, `yaml#key`, `kv#key`, `github_tag`, `github_release`, `omaha:appid`,
`versionhistory`, `itunes`, `cask` (tylko jako drugi głos). Test statyczny (analogiczny do
`test_every_config_method_has_a_handler`): każdy `primary`/`fallback`/oracle kind ma implementację.

### 5.3 Statusy jako enum i automatyczny pomiar opóźnienia kanałów

**Enum** (zapisywany jako `STATUS_CODE_*`, JSON `items[].status`), a napis to tylko renderowanie:

`updated · current_verified · current_cask_only · behind · staged · rollout_hold · feed_stale · unverified ·
launch_failed · needs_interactive · manual · not_installed · tombstoned`

**Telemetria źródeł** (`logs/source_lag.tsv`): w każdym przebiegu `ts, app, installed, vendor, cask, channel_used, result`.
Raport `scripts/report_source_lag.sh`:

- *cask lag* = ile dni lub przebiegów cask był za producentem w ostatnich 30 dniach;
- *native convergence* = po ilu przebiegach oryginalny updater doprowadził do wersji producenta;
- **rekomendacja kanału** (przykłady formatu): „MEGAsync: cask lag 0 d / 30 d → brew OK”, „ChatGPT: cask za
  producentem o 1 build, natywny updater zbiega dopiero w kolejnym przebiegu → `sparkle_cli`”. Domyślnie tylko rekomendacja. Automatyczna zmiana kanału wyłącznie z
  `MAC_UPDATE_AUTO_CHANNEL=1`, zapis w `state/channel_overrides.txt` i powiadomienie.

To jest „mądre” rozwiązanie Twojego przykładu (MEGAsync przez brew, Claude Code przez natywny updater). Decyzja
opiera się na pomiarze, a nie na jednorazowej obserwacji, i sama podpowiada zmianę, gdy któryś kanał zacznie odstawać.

### 5.4 Inwentarz v2 — stan, tombstone'y, watcher

- **`state/inventory.json`** (gitignored, `0600`, zapis atomowy). Klucz to `kind:id`:
  `app:<CFBundleIdentifier>`, `cask:<token>`, `formula:<name>`, `mas:<adamId>`, `ios:<itemId>`, `cli:<name>`.
  Pola: `name, path, version, team_id, arch, source, channel, first_seen, last_seen, removed_at`.
  Źródła odkrycia:
  `/Applications/**` (głębokość 2, np. foldery producentów), `~/Applications`, `brew info --json=v2 --installed`,
  `mas list --json`, `iTunesMetadata.plist`, `_MASReceipt`, CLI z manifestu (tylko obecne).
- **`APPLICATIONS.md` = czysty render** z `inventory.json` (sekcje, podsumowanie, legenda liczone automatycznie).
  Koniec z wstawianiem wierszy regexami i wierszami poza tabelą. Ręczne notatki w osobnym pliku
  `config/local/inventory_notes.md`, dołączanym do renderu.
- **Tombstone'y `state/tombstones.txt`** (`kind|id|removed_at|how`): wpis powstaje automatycznie, gdy element obecny w
  poprzednim stanie znika, a także dla osieroconego caska (P0-2). Honorują go wszystkie kroki: brew (pominięcie +
  propozycja `brew uninstall --cask`), CLI (bez reinstalacji), internet (brak w podsumowaniu, bez spamu typu
  „DJI Assistant 2: ⏭️ Pominięty” przy każdym przebiegu), App Store. **Ponowna instalacja przez użytkownika
  automatycznie usuwa tombstone** (element wraca w skanie). Dopasowanie po dokładnym `kind:id`, z testem regresyjnym
  (lekcja z App Auto-Patch).
- **Watcher `com.<user>.macos-updates.inventory`** (LaunchAgent, `WatchPaths`: `/Applications`, `~/Applications`,
  `/opt/homebrew/Caskroom`, `~/.local/bin`, managed `npm-global/lib/node_modules`; `ThrottleInterval` 600) uruchamia
  `build_inventory.sh --quiet`: tylko odczyt systemu, zapis wyłącznie `state/` i `APPLICATIONS.md`. **Inwentarz
  aktualizuje się sam po każdej ręcznej instalacji lub deinstalacji**, bez czekania na `update_all.sh`.

### 5.5 Tryb w tle v2 — trzy warstwy

| Warstwa | Wyzwalacz | Co robi | Czego **nie** robi |
|---|---|---|---|
| A. Watcher inwentarza | `WatchPaths` (+ przy logowaniu) | skan → `inventory.json` → render `APPLICATIONS.md` → tombstone'y | żadnych aktualizacji |
| B. Dzienny przebieg bezpieczny (`--background`) | `StartCalendarInterval` codziennie + `RunAtLoad` z throttlingiem 20 h | wyrocznie producentów; formulae; caski **bez** artefaktów wymagających sudo i bez uruchomionej aplikacji; CLI przez natywne updatery (tylko zainstalowane); `google_updater`/`chromium_updater`; `msupdate --install`; `sparkle` CLI z `--defer-install`; `appstore_lookup` (raport); audyt postawy Apple; powiadomienie z podsumowaniem | sudo, GUI, `mas upgrade`, `softwareupdate -i`, zamykanie aplikacji użytkownika, bootstrap |
| C. Finisher interaktywny (`update_all.sh`) | ręcznie, z powiadomienia („N pozycji czeka”) | kolejka `needs_interactive` (pkg casks, mas, Track 2, macOS z `-R`, eskalacje `direct`) | — |

Wymagania: wrapper z czytelną nazwą dla BTM (P0-1), `run_lock` (już jest), exit 10 zamiast 1 przy
`needs_interactive`, wpis w `run_summary` (`mode: background`), rotacja logów `launchd.*`.

### 5.6 Nowe metody (handlery)

| Metoda | Implementacja | Dla |
|---|---|---|
| `google_updater` | kickstart `com.google.GoogleUpdater.wake` (+ system przez istniejący shim), parsowanie odpowiedzi Omaha per `appid`, VersionHistory | Chrome, Gemini, Drive |
| `chromium_updater` | `launchctl kickstart gui/$UID/<label>` + wyrocznia JSON | Comet |
| `sparkle_cli` | przypięta wersja narzędzia `sparkle` z oficjalnego wydania Sparkle 2 (SHA-256 w `config/`, weryfikacja `codesign`) albo build ze źródeł; `--probe`, potem `--check-immediately` lub `--defer-install`, `--user-agent-name macos-updates`, `--feed-url` gdy feed jest ustawiany w runtime; mapowanie exit codes (0/2/3/5/6/8) na enum | ChatGPT, Proton Drive, ProtonVPN, Perplexity, CodeEdit, CapCut, AppCleaner, Brave |
| `launch_cycle` | wyrocznia → `open -gj` tylko przy zaległości → oczekiwanie na staging → łagodne `quit app id` (tylko gdy toolkit uruchomił aplikację) → odczyt wersji | Claude, Cursor, Warp, Antigravity(+IDE), Proton Mail, OpenCode Desktop, Teams |
| `vendor_direct` | uogólnione `copy_verified_app` + `expectedTeamID` + `blockingProcesses` (wzorzec Installomatora) | RDM, eskalacje |
| `appstore_lookup` | `iTunesMetadata.plist` + iTunes Lookup → pominięcie lub uruchomienie Track 2 → weryfikacja | iPad: UniFi, WiFiman, Picsart, IPMIView, S2M, TrackMan |
| `docker_cli` v2 | appcast → (start) → `docker desktop update -q` → przywrócenie stanu | Docker Desktop |

### 5.7 Świadomie poza zakresem (żeby nie rozmywać głównej funkcji)

`uv tool upgrade --all`, rozszerzenia `gh`, `pipx`, `cargo install-update` to przydatne, ale osobne moduły (P3).
Na tym Macu dotyczy to `flow-agent` i `graphifyy`. Czyszczenie pamięci podręcznych innych niż Homebrew też jest poza zakresem.

---

## 6. Faza 5 — macierz punktowa (0–10)

| Wymiar | Ocena | Uzasadnienie |
|---|:--:|---|
| Wierność źródłom (oryginalny updater / najlepszy kanał) | **6** | MAU, CLI, direct: wzorowo; ChatGPT/Comet/Gemini/RDM: źle dobrana wyrocznia lub metoda |
| Prawdomówność weryfikacji | **5** | cztery klasy fałszywej zieleni (P0-4), `behind` nie zmienia statusu kroku |
| Cykl życia: odinstalowanie i inwentarz | **3** | reinstalacja CLI, blokada przez osierocony cask, usunięcia tylko w GRUPIE 3 |
| Praca w tle | **2** | agent nie działa, instalator kłamie, brak profilu bez sudo i GUI |
| Bezpieczeństwo instalacji | **8** | podpisy, Team ID, `spctl`, rollback, brak `curl \| sh`; −1 za brak pinów SHA dla części feedów, −1 za sudo w tle bez polityki |
| Architektura i utrzymanie | **6** | `update_all.sh` 2201 linii z heredocami Python, stany jako napisy, łączenie konfiguracji po nazwie O(n²) |
| Testy | **8** | 326 testów, strażnicy statyczni; brak scenariuszy deinstalacji, porządku appcastów i BTM |
| Obserwowalność | **7** | schema v4, historia wersji; log zaszumiony przy soft warn, brak przypisania zmian między krokami |
| Higiena zasobów | **5** | ~7 GB starych wersji CLI, kilkanaście aplikacji zostawionych w tle, niepotrzebny start VM Dockera |
| Dokumentacja i komendy agentów | **6** | reguły krytyczne świetne; komendy `.claude` sprzeczne z regułą #1, przestarzała tabela modeli |
| **Łącznie** | **5,6** | Solidny, bezpieczny rdzeń; brakuje modelu „stanu Maca” (inwentarz + tombstone) i modelu „źródła prawdy” (feed producenta) |

---

## 7. Faza 6 — plan wdrożenia w kolejności wykonania

Każde R to osobny commit na gałęzi `feat/source-of-truth-v1.5` z testami. **Bez tagowania bez Twojej zgody.**

| # | Prio | Zadanie | Zamyka | Kryterium akceptacji (komenda) |
|---|:--:|---|---|---|
| R0 | — | Gałąź, przeniesienie tego review i 4 nieśledzonych do decyzji (commit albo `.git/info/exclude`) | higiena | `git status` czysty poza celowymi plikami |
| R1 | P0 | LaunchAgent: wrapper z nazwą, weryfikacja `launchctl print` + BTM, `--status`, kod wyjścia ≠ 0 przy `disallowed` | P0-1 | `bash scripts/install_launchagent.sh --status` pokazuje `loaded` albo instrukcję; test z atrapą `launchctl` |
| R2 | P0 | Zasada „tylko zainstalowane” w `update_npm_cli.sh` (native-installer, npm, bun); instalator tylko w `--bootstrap` | P0-3 | test: brak `~/.local/bin/codex` → brak wywołania instalatora; `grep -c install.sh` w logu = 0 |
| R3 | P0 | Detektor osieroconych casków + pomijanie w upgrade + propozycja `brew uninstall --cask --force` (tylko TTY i potwierdzenie) | P0-2 | test: artefakt `app` bez bundla → brak w `UPGRADEABLE_CASKS`, krok brew ≠ hard |
| R4 | P0 | Tombstone'y `state/tombstones.txt` honorowane przez prescan, brew, CLI, internet, App Store; automatyczne czyszczenie przy reinstalacji | P0-2/3, P1-7 | test: `cli\|gemini-cli` → wiersz znika z `APPLICATIONS.md`, a CLI nie jest instalowane |
| R5 | P0 | Uczciwa weryfikacja: parser Sparkle (max, kanał, minOS, `feed_stale`), usunięcie `Gemini\|gemini`, wyrocznia caska tylko jako drugi głos, statusy enum | P0-4, P2-12 | testy z fiksturami: appcast RDM (rosnący), Docker (dwie wersje), ProtonVPN (kanał beta) |
| R6 | P1 | `config/update_sources.txt` + `lib/python/sources.py` (wyrocznie producentów) + test statyczny kompletności | P0-4, §5.2 | `python3 -m unittest tests.test_sources` |
| R7 | P1 | `google_updater` (Omaha + VersionHistory, `rollout_hold`/`staged`), Gemini przeniesiony; `chromium_updater` dla Comet | P1-6 | fikstura logu GoogleUpdater z `noupdate` → `rollout_hold` |
| R8 | P1 | `sparkle_cli` (przypięte narzędzie, SHA-256, exit codes → enum, `--defer-install`) dla ChatGPT i Proton Drive, potem reszty Sparkle | P1-5, §5.6 | ChatGPT: `behind` → `updated` w jednym przebiegu |
| R9 | P1 | `launch_cycle` dla Squirrel/Electron + „najpierw feed, potem launch”; Docker v2 | P1-5, P2-16 | po przebiegu `pgrep` nie pokazuje aplikacji, których nie było przed startem |
| R10 | P1 | `appstore_lookup`: gating Track 2 + weryfikacja; autoklasyfikacja iPad (`iTunesMetadata.plist`); IPMIView, S2M, TrackMan; `mas --json` | P1-8 | przy braku zaległości Track 2 się nie uruchamia; brak `unverified` przy zgodnych wersjach |
| R11 | P1 | Homebrew: brak globalnego greedy, `HOMEBREW_UPGRADE_GREEDY_CASKS` z rejestru; partycja casków sudo/bez sudo; honorowanie `MAC_UPDATE_NO_SUDO` | P1-9, P1-10 | test: cask z `pkg` w trybie bez TTY → `needs_interactive`, nie hard fail |
| R12 | P1 | Tryb w tle v2: `--background`, watcher inwentarza (`WatchPaths`), kolejka `needs_interactive` + powiadomienie | §5.5 | `update_all.sh --background` bez TTY kończy się 0 lub 10, nigdy nie pyta |
| R13 | P1 | Inwentarz v2: `state/inventory.json` + render `APPLICATIONS.md` (bundle id), przypisanie zmian między krokami | P1-7 | `build_inventory.sh` dwukrotnie → identyczny plik (idempotencja); brak wierszy poza tabelami |
| R14 | P2 | CLI: `codex update`, `agent update`; retencja wersji (current + 1) | P2-11 | `ls …/releases \| wc -l` ≤ 2 po przebiegu |
| R15 | P2 | System: grupowanie etykiet z `-R`, audyt postawy (Automatic Updates, BSI) | P2-13 | test: 2 etykiety (restart + bez restartu) → jedno wywołanie z `-R` na końcu |
| R16 | P2 | Log: zrzut snapshotów tylko przy blokadzie; `.claude/commands/*`, `CLAUDE.md`, szablon codename 27 | P2-14, P2-15 | log soft-warn < 400 linii; `grep -- '-ia' .claude/commands` = 0 |
| R17 | P2 | Telemetria `source_lag.tsv` + `report_source_lag.sh` z rekomendacją kanału | §5.3 | raport pokazuje lag per aplikacja za 30 dni |

**Po każdym R:** `bash run_tests.sh` (wszystko zielone), `shellcheck --severity=warning` jak w CI,
7 plików `i18n/lang_*.sh` uzupełnionych, `bash update_all.sh --dry-run` bez błędów, wpis w `CHANGELOG.md`.

---

## 8. Prompt implementacyjny (samowystarczalny, dla kolejnej sesji dowolnego agenta)

```text
Pracujesz w repozytorium ~/Dev_Env/macOS_updates (v1.4.6, Bash 3.2 + Python 3, macOS 13–27, Apple Silicon).
Przeczytaj CLAUDE.md, docs/agents/critical_rules.md, docs/agents/architecture.md oraz
docs/reviews/archive/opus_5.5_ultra_review_v1.md (§3, §5, §7). Wdrażasz R1→R17 w podanej kolejności, każde jako
osobny commit na gałęzi feat/source-of-truth-v1.5.

Ograniczenia nienegocjowalne:
- Bash 3.2 (bez declare -A, mapfile, readarray); każde update_*.sh ma set -o pipefail, nigdy set -e.
- softwareupdate zawsze per etykieta z -R; mas upgrade zawsze z sudo i jawnymi ID; nigdy sudo bez TTY
  (MAC_UPDATE_NO_SUDO=1 → kroki root-only raportują needs_interactive/exit 10).
- Każde zapytanie do Homebrew przez lib/brew.sh; nigdy `brew list --cask --versions` bezpośrednio.
- Python pipeline tylko jako czyste moduły w lib/python/ (testowane) lub heredoc; brak nowych entrypointów.
- Pobrania: HTTPS, lib/fetch.sh, weryfikacja Team ID + spctl (+ SHA-256, gdy producent go publikuje);
  zero `curl | sh`.
- Status handlera przez INTERNET_LAST_STATUS + nowy STATUS_CODE (enum z §5.3); nigdy stdout.
- „Zweryfikowane” = porównanie z MAKSIMUM feedu producenta dla właściwego kanału; remote<local = feed_stale.
- update_all.sh aktualizuje wyłącznie zainstalowane elementy; instalacja tylko w setup/migration_setup/--bootstrap.
- Tombstone (state/tombstones.txt) blokuje reinstalację i upgrade; reinstalacja przez użytkownika go usuwa.
- Tryb --background: bez sudo, bez GUI, bez zamykania aplikacji użytkownika, bez bootstrapu.
- Każdy nowy tekst UI: 7 plików i18n (en najpierw). Każdy nowy method/oracle kind: test kompletności.
- Nic prywatnego w plikach śledzonych (APPLICATIONS.md, UPDATES.md, state/, logs/ są gitignored).
- Nie tagować i nie publikować bez zgody właściciela.

Kolejność i kryteria akceptacji: tabela §7 review. Po każdym kroku: bash run_tests.sh, ShellCheck jak w CI,
bash update_all.sh --dry-run. Na końcu: handoff w docs/agents/handoffs/ + CHANGELOG + bump do 1.5.0 (bez tagu).
```

---

## 9. Co możesz zrobić od razu na tym Macu (ręcznie, bez zmian w kodzie)

1. **Harmonogram:** *Ustawienia systemowe → Ogólne → Rzeczy otwierane przy logowaniu i rozszerzenia → Zezwalaj w tle*,
   element „bash” (Unknown Developer). **Uwaga:** dzisiejszy profil (`-y --skip-system`, bez TTY) prawdopodobnie
   zakończy się błędem kroku brew przy najbliższej aktualizacji Zooma (pkg + sudo, P1-9). Rozsądniej włączyć go po
   R1 + R11, albo zaakceptować czerwony wynik do tego czasu.
   Weryfikacja: `launchctl print gui/$(id -u)/com.<user>.macos-updates | head`.
2. **ChatGPT/Codex desktop:** zamknij i uruchom ponownie aplikację (Sparkle zainstaluje pobraną wersję) albo użyj
   *Check for Updates…*. Producent ma już `26.917.62051`.
3. **Chrome:** nic nie rób, bo Google trzyma tę kohortę na 153 (`noupdate`). Opcjonalnie `chrome://settings/help`.
4. **Inwentarz:** do czasu R13 możesz ręcznie usunąć wiersze `gemini-cli`, `qwen-code`, `Notion Web Clipper`
   i przenieść `GarageBand` do tabeli GRUPY 2. Toolkit ich nie przywróci, bo postupdate tylko aktualizuje wersje.
5. **Miejsce na dysku (ok. 7 GB):** najpierw zobacz, co jest aktualne, i nie usuwaj katalogu, na który wskazuje symlink:
   ```bash
   readlink ~/.codex/packages/standalone/current; ls ~/.codex/packages/standalone/releases
   readlink ~/.local/bin/cursor-agent; ls ~/.local/share/cursor-agent/versions
   ls -la ~/.local/bin/agy.*.old
   ```
   Pliki `agy.*.old` to pozostałości po samoaktualizacji `agy`. Stare katalogi wersji można usunąć ręcznie albo
   poczekać na retencję z R14.
6. **Nie przeciągaj do Kosza aplikacji zainstalowanych przez Homebrew** (lista w sekcji 4c), dopóki nie będzie R3.
   Używaj `brew uninstall --cask <token>`, bo inaczej zablokujesz aktualizację macOS (P0-2).

---

## 10. Czego celowo nie zrobiłem i skutki uboczne

- **Nie uruchamiałem** `update_all.sh`, `brew upgrade`, `mas upgrade`, `softwareupdate -i`, `launchctl bootstrap/kickstart`,
  `sparkle` ani niczego, co instaluje lub zmienia konfigurację. Nie edytowałem kodu, i18n, konfiguracji ani `APPLICATIONS.md`.
- **Skutek uboczny (jedyny):** próba `brew livecheck` (sprawdzenie, czy livecheck działa jako wyrocznia w trybie API)
  zainstalowała 10 gemów deweloperskich Homebrew (`sorbet-runtime`, `rexml`, `plist`, …) w
  `/opt/homebrew/Library/Homebrew/vendor/bundle`. Zarządza nimi sam Homebrew, są nieszkodliwe i nie wymagają działania.
  Sam livecheck odmówił działania (`Cask 'chatgpt' is unavailable`, brak tapa `homebrew/cask`), stąd rekomendacja
  przeniesienia URL-i feedów do konfiguracji (§5.2).
- `bash run_tests.sh` utworzył pliki tymczasowe i `__pycache__` (gitignored); drzewo git bez zmian.
- Zapytania sieciowe wyłącznie GET: feedy producentów (OpenAI, Anthropic, Warp, Docker, Proton, Devolutions,
  CodeEdit, Perplexity), Google VersionHistory, iTunes Lookup, `formulae.brew.sh`, `raw.githubusercontent.com`.
- **Uwaga o prywatności:** ten plik zawiera szczegóły tego konkretnego Maca (lista aplikacji, wersje, ścieżki). Jak
  pozostałe 4 nieśledzone review, **nie powinien trafić do publicznego repo bez redakcji**.

---

## 11. Ślad dowodowy

```bash
# Stan i testy
git log --oneline -40; git status --short; bash run_tests.sh              # 326 OK, gitleaks clean
sed 's/\x1b\[[0-9;]*m//g' logs/update_all_20260923_094154.log             # pełny przebieg + snapshoty sesji
for f in logs/run_summary_2026*.json; do …; done                          # trend statusów i behind
grep -E 'ChatGPT / Codex|Google Chrome|Gemini|Comet|Claude' logs/version_history.tsv

# Harmonogram
launchctl print gui/$(id -u)/com.<user>.macos-updates                        # Could not find service
launchctl print-disabled gui/$(id -u) | grep macos-updates                # enabled
sfltool dumpbtm | grep -A12 macos-updates                                 # disallowed
plutil -lint ~/Library/LaunchAgents/com.<user>.macos-updates.plist; xattr -l …

# Źródła i feedy
for a in /Applications/*.app; do defaults read "$a/Contents/Info" SUFeedURL; codesign -dv "$a"; done
brew info --json=v2 --cask chatgpt claude cursor warp gemini comet docker-desktop …
curl https://formulae.brew.sh/api/cask/<token>.json; curl raw.githubusercontent.com/Homebrew/homebrew-cask/HEAD/<path>  # livecheck
curl https://persistent.oaistatic.com/codex-app-prod/appcast.xml                             # 26.917.62051
curl https://downloads.claude.ai/releases/darwin/universal/RELEASES.json                     # 2.7032.0
curl https://desktop.docker.com/mac/main/arm64/appcast.xml                                   # max 4.92.0
curl https://cdn.devolutions.net/download/Mac/RemoteDesktopManager.xml | … | sort -V | tail  # 2023.1.12.0
curl https://devolutions.net/productinfo.htm | grep '^RDMMac'                                # 2026.3.0.5 + hash
curl 'https://versionhistory.googleapis.com/v1/chrome/platforms/mac_arm64/channels/stable/versions/all/releases?filter=endtime=none'
ksadmin --print; grep 'Omaha' ~/Library/Application\ Support/Google/GoogleUpdater/updater.log  # noupdate
curl 'https://itunes.apple.com/lookup?id=1057750338,1385561119,587366035,1359042934,1192720039,952163566'

# Kod Homebrew (dowód P0-2)
sed -n '195,225p' /opt/homebrew/Library/Homebrew/cask/artifact/moved.rb
sed -n '655,660p;708,760p' /opt/homebrew/Library/Homebrew/cask/installer.rb

# Inwentarz i dysk
command -v gemini qwen cursor-agent; mas list; grep -n '^#' APPLICATIONS.md
du -sh ~/.codex/packages ~/.local/share/cursor-agent/versions; ls -la ~/.local/bin/*.old
defaults read /Library/Preferences/com.apple.SoftwareUpdate
```

**Źródła zewnętrzne (odczyt 2026-09-23):**
[Sparkle CLI](https://sparkle-project.org/documentation/sparkle-cli) ·
[Homebrew FAQ — auto_updates](https://docs.brew.sh/FAQ) ·
[Homebrew PR #21882](https://github.com/Homebrew/brew/pull/21882) ·
[mas releases](https://github.com/mas-cli/mas/releases) ·
[Docker `desktop update`](https://docs.docker.com/reference/cli/docker/desktop/update/) ·
[Codex `codex update`](https://codex.danielvaughan.com/2026/05/08/codex-cli-codex-update-self-update-command/) ·
[Cursor CLI install/update](https://cursor.com/docs/cli/installation) ·
[softwareupdate(8)](https://keith.github.io/xcode-man-pages/softwareupdate.8.html) ·
[munki-dev: OS upgrades on Apple silicon](https://groups.google.com/g/munki-dev/c/zRRHiCbqTIk) ·
[Apple — Background Security Improvements](https://support.apple.com/en-us/102657) ·
[Installomator — Label Variables](https://github.com/Installomator/Installomator/wiki/Label-Variables-Reference) ·
[App Auto-Patch — releases](https://github.com/App-Auto-Patch/App-Auto-Patch/releases)
