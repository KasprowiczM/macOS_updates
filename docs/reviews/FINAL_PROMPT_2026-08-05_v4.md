# FINAL PROMPT — macOS_updates v1.2.0 → v1.3.0 (production release)
> **Przeznaczenie:** wklej całość jako pojedynczy prompt do Gemini w sesji uruchomionej w `~/Dev_Env/macOS_updates`.
> **Bazuje na:** `ULTRA_REVIEW_2026-08-05_v4.md`

---

Pracujesz w `~/Dev_Env/macOS_updates` (Bash 3.2+, Python 3, Apple Silicon, macOS 13–26, 7 języków).

**v1.2.0 naprawiło P1 (sudo) i P4 (kanał MAU) naprawdę — to zostaje.** Ale trzy rzeczy blokują produkcję, a badanie API Homebrew wykazało, że **4 aplikacje właściciela są w tej chwili o krok od cofnięcia do starszych wersji**.

Przeczytaj **najpierw** `ULTRA_REVIEW_2026-08-05_v4.md` w całości.

---

## 🚨 NAJWAŻNIEJSZA ZASADA TEJ SESJI

> **Test statyczny (`grep` po pliku) NIE jest dowodem, że kod działa.**

Dwie funkcje z v1.2.0 przeszły testy, będąc całkowicie niefunkcjonalne:
- bezpiecznik downgrade'u — sprawdza `[ "$rel" = "older" ]`, a funkcja nigdy nie zwraca `"older"`
- dedup inwentarza — porównuje `Brave Browser` ze `brave-browser`, więc przekrój jest pusty zawsze

**Każdy test w tej sesji musi być behawioralny:** wywołaj funkcję na przygotowanych danych i sprawdź wynik. Jeżeli test nie potrafi zawieść przy zepsutej implementacji, jest bezwartościowy.

**Zanim uznasz zadanie za zrobione — uruchom kod i wklej wyjście.** Nie `grep`, tylko wykonanie.

---

## ZASADY NIENARUSZALNE

1. **Bash 3.2** — bez `declare -A`, `mapfile`, `readarray`, `${var^^}`.
2. **`softwareupdate` z `-R`**; **`mas upgrade` z `sudo`**.
3. **Zero hardcoded paths**; temp przez `mktemp -d "${TMPDIR:-/tmp}/mac_update_*.XXXXXX"`.
4. **`set -o pipefail` tak, `set -e` nie.**
5. **Nowy string użytkownika → wszystkie 7 `i18n/lang_*.sh`.**
6. **Severity contract 0/10/1 bez zmian.** Statusy soft nie blokują kroku 6.
7. **Nie ruszasz działającego kodu:** `INTERNET_LAST_STATUS`, settle-loop, `_needs_sudo`, `MAC_UPDATE_NO_SUDO`, keep-alive, `CASK_MISSING`, stale-days, detekcja kanału MAU.
8. **`bash run_tests.sh` zielone po każdym etapie.**

---

# 🔴 F1 — Napraw bezpiecznik przed downgrade'em (3 błędy w jednej funkcji)

`update_brew.sh:235–262`. Ta funkcja **nigdy nie zadziałała**.

## F1.1 — Błąd logiczny: `"older"` nie istnieje

`internet_version_relation()` (`lib/internet_app_updates.sh:8`) zwraca wyłącznie `"newer"`, `"current"`, `"unknown"`. Warunek `[ "$rel" = "older" ]` nie będzie prawdziwy nigdy.

**Wybierz jedno i zrób konsekwentnie:**
- **(a)** odwróć argumenty: downgrade ⟺ `internet_version_relation "$installed_ver" "$cask_ver"` = `"newer"`, albo
- **(b)** rozszerz `internet_version_relation` o czwartą wartość `"older"` i **zaktualizuj wszystkich jej konsumentów** (`grep -rn internet_version_relation`)

Rekomenduję **(a)** — nie zmienia kontraktu funkcji używanej gdzie indziej.

## F1.2 — Błąd parsowania: `awk '{print $3}'` łapie złe pole

```
==> comet (Comet): 145.2.7632.4581 (auto_updates)
     $1      $2         $3               $4          ← $3 = "(Comet):"
==> inkscape: 1.4.4
     $1    $2      $3                                 ← $3 = "1.4.4"
```
Zachowanie zależy od tego, czy cask ma nazwę w nawiasie. **Nie parsuj tekstu `brew info`.**

Użyj JSON:
```bash
brew info --json=v2 --cask "$cask" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["casks"][0]["version"])'
```

## F1.3 — Błąd mapowania: slug casku ≠ nazwa aplikacji

`cask_app_path="/Applications/$cask.app"` nie zadziała dla `brave-browser`, `proton-mail`, `lm-studio`, `antigravity-ide`…

Weź prawdziwą nazwę z artefaktu w tym samym JSON-ie:
```bash
d["casks"][0]["artifacts"] → pierwszy wpis z kluczem "app" → np. ["Comet.app"]
```
Albo dodaj mapowanie odwrotne do istniejącego `internet_cask_name_for_app`.

## F1.4 — Testy **behawioralne** (obowiązkowe)

Napisz testy, które **wywołują** logikę i **zawiodą przy zepsutej implementacji**:

1. `test_version_relation_detects_downgrade` — wywołaj `internet_version_relation` dla par: `("3.7.21","3.14.27")`, `("1.13.3","1.13.4")`, `("0.2026.05.27","0.2026.07.29")`, `("2.0.10","2.5.0")` i sprawdź, że wybrana logika z F1.1 klasyfikuje **każdą** jako downgrade.
2. `test_cask_version_parsing_handles_parenthesised_name` — na sztucznym JSON-ie casku z nazwą w nawiasie i bez niej.
3. `test_cask_app_path_resolves_from_artifacts` — `brave-browser` → `Brave Browser.app`.
4. Zmodyfikuj `test_brew_upgrade_guards_against_downgrade`, aby weryfikował **zachowanie**, nie obecność tekstu.

## F1.5 — Dowód wymagany
```bash
# każda z tych par MUSI zostać sklasyfikowana jako downgrade
for p in "3.7.21 3.14.27" "1.13.3 1.13.4" "0.2026.05.27.15.44 0.2026.07.29.09.05" "2.0.10 2.5.0"; do
    set -- $p; echo -n "cask=$1 installed=$2 → "
    # wywołaj tu swoją finalną logikę i wypisz decyzję
done
```
Wklej wyjście.

---

# 🔴 F2 — Wprowadź kategorię „always-latest" i wypnij 9 aplikacji z Homebrew

## Kontekst — dane pobrane 2026-08-05 z `formulae.brew.sh/api`

| Aplikacja | Zainstalowana | Cask | Cask bumpnięty | Ryzyko |
|-----------|---------------|------|----------------|--------|
| **Cursor** | 3.14.27 | **3.7.21** | 2026-06-09 | 🔴 −7 minor |
| **Warp** | 0.2026.07.29.09.05.02 | **0.2026.05.27.15.44.stable_01** | 2026-05-31 | 🔴 −2 mies. |
| **Antigravity** | 2.5.0 | **2.0.10** | 2026-05-30 | 🔴 −5 minor |
| **Proton Mail** | 1.13.4 | **1.13.3** | 2026-07-16 | 🔴 −1 patch |
| Comet | 150.0.7871.228 | 145.2.7632.4581 | 2026-08-05 | 🟡 typ A |
| Proton Drive | 3.0.0 | 3.0.0 | 2026-07-17 | 🟡 zaraz się rozjedzie |
| Claude Desktop | 1.25927.0 | 1.25927.0 | 2026-08-05 | 🟡 aktualny przypadkiem |
| ChatGPT | 26.727.51351 | 26.730.61639 | 2026-08-05 | 🟡 cask nowszy |
| Antigravity IDE | 2.1.1 | 2.1.1 | 2026-08-05 | 🟡 aktualny przypadkiem |

**Wymóg właściciela:** te aplikacje mają być **zawsze najnowsze**; woli ręcznie i aktualnie niż automatycznie i wstecz.

## F2.1 — Nowa metoda `vendor_latest`

Semantyka: **weryfikuj wersję zdalną, nie instaluj — instalację zostaw natywnemu updaterowi.**

- czyta feed producenta (`SUFeedURL` → Sparkle, `app-update.yml` → Electron, API producenta)
- porównuje z zainstalowaną przez `internet_version_relation`
- statusy: `L_INTERNET_STATUS_CURRENT_FMT` (aktualna) / `L_INTERNET_STATUS_UPDATE_AVAILABLE_FMT` (jest nowsza) / `L_INTERNET_STATUS_OFFLINE` / `L_INTERNET_STATUS_UNKNOWN_VERSION`
- uruchamia natywny updater w tle (jak `silent_launch`), ale **status pochodzi z feedu**
- **nigdy nie podmienia bundla**

Gdy aplikacja nie ma feedu — zostaw `silent_launch` i **napisz to wprost w raporcie**, zamiast udawać weryfikację.

## F2.2 — Wypnij 9 aplikacji z Homebrew

Dla: **Cursor, Warp, Antigravity, Antigravity IDE, Comet, Proton Mail, Proton Drive, Claude Desktop, ChatGPT**

1. `brew uninstall --cask --force <cask>` — **UWAGA: tylko `uninstall`, nigdy `--zap`.** `--zap` kasuje dane użytkownika, ustawienia i licencje. Aplikacja w `/Applications` ma **zostać nietknięta**.
2. Po każdej aplikacji sprawdź, że `.app` istnieje i ma **niezmienioną** wersję:
```bash
defaults read "/Applications/Cursor.app/Contents/Info" CFBundleShortVersionString
```
3. `config/internet_app_methods.txt`: `brew_cask` → `vendor_latest`
4. `config/internet_dispatch_order.txt`: odkomentuj / dodaj wpis `iu_*`
5. `update_internet_apps.sh`: usuń zahardkodowane `"→ managed by Homebrew"` dla tych 9

**Rób partiami po 3. Po każdej partii wklej wyjście `defaults read` dla każdej aplikacji.**

⚠️ **Przed pierwszym `uninstall` przedstaw właścicielowi listę do zatwierdzenia i zaczekaj.**

## F2.3 — ChatGPT: cask jest nowszy niż zainstalowana wersja

Cask `chatgpt` = `26.730.61639`, zainstalowana = `26.727.51351`. **Zanim wypniesz** — uruchom natywny updater ChatGPT i potwierdź, że dogoni. Jeśli nie dogoni w rozsądnym czasie, zostaw ChatGPT w `brew_cask` i odnotuj wyjątek z uzasadnieniem.

## F2.4 — Zostaw w Homebrew (bez zmian)
Brave, Obsidian, Spotify, AppCleaner, CapCut, MEGAsync, ProtonVPN, zoom, LM Studio, Perplexity, Inkscape.

## F2.5 — Przełącz na `--greedy-auto-updates`
Pomiary z v1.2.0 (1,20 s vs 0,30 s) uzasadniają zmianę w `update_brew.sh` (linie 130, 240, 260).

⚠️ W `docs/agents/critical_rules.md` zapisz **prawdziwe** uzasadnienie: unikamy re-pobrań casków `version :latest`. **Nie pisz, że to eliminuje ryzyko downgrade'u** — nie eliminuje. Przed nim chroni dopiero bezpiecznik z F1.

## F2.6 — Dowód wymagany
```bash
brew list --cask --versions            # 9 aplikacji ma zniknąć
ls -d /Applications/Cursor.app /Applications/Warp.app /Applications/Comet.app   # muszą istnieć
for a in Cursor Warp Comet "Proton Mail" Antigravity; do
  echo -n "$a: "; defaults read "/Applications/$a.app/Contents/Info" CFBundleShortVersionString
done
bash scripts/report_update_coverage.sh
```

---

# 🔴 F3 — Napraw deduplikację inwentarza (P2 było pozorne)

## Problem

Raport v1.2.0 podał „Intersection: 0". Przy normalizacji nazw przekrój wynosi **18**:
```
GRUPA3: 47   4c: 20   overlap: 18
['capcut','brave browser','warp','inkscape','proton mail','proton drive',
 'antigravity ide','obsidian','spotify','protonvpn', ...]
```
Dowód z pliku:
```
GRUPA 3:  | Cursor      | 3.14.27 | https://cursor.com |
4c:       | cursor      | 3.14.27,047548b00c1a... |
GRUPA 3:  | Proton Mail | 1.13.4  | https://proton.me/mail/download |
4c:       | proton-mail | 1.13.3  |
```
Test `test_no_app_listed_in_both_group3_and_casks` porównuje nazwy wyświetlane ze slugami — **przekrój jest pusty z definicji**.

## F3.1 — Napraw test
Normalizuj obie strony przed porównaniem: lower-case, `[-_ .]` → nic. Wykorzystaj **istniejące** `internet_cask_name_for_app` do mapowania nazwa→slug, zamiast heurystyki.

Test musi **zawieść na obecnym `APPLICATIONS.md`** — to jest kryterium poprawności testu. Pokaż to.

## F3.2 — Napraw `build_inventory.sh`
Aplikacja zarządzana caskiem trafia **wyłącznie** do §4c. Skrypt ma **usuwać** wpisy z GRUPY 3, nie tylko dodawać do 4c.

Uwaga: po F2 dziewięć aplikacji wraca do GRUPY 3 (jako `vendor_latest`) i **nie może** już być w 4c — logika ma wynikać z `config/internet_app_methods.txt` + `brew list --cask`, a nie z listy na sztywno.

## F3.3 — Uzupełnij opisy casków
20 wierszy w §4c ma `🆕 NOWY — opis do uzupełnienia`. Wypełnij z pola `desc` z API Homebrew (`brew info --json=v2 --cask <slug>`).

## F3.4 — Legenda
`APPLICATIONS.md` sekcja „Legenda aktualizacji" nadal przypisuje aplikacje do `update_internet_apps.sh` niezgodnie ze stanem. **Generuj ją z configu.**

## F3.5 — Dowód
```bash
bash build_inventory.sh
python3 - <<'PY'
# wklej tu skrypt normalizujący i wypisz overlap — musi być 0
PY
```

---

# 🟡 F4 — Microsoft AutoUpdate: kanał `External`

Detekcja z v1.2.0 działa i wykryła `ChannelName: External`. **To jest przyczyna pętli:** kanał External serwuje 16.111.2, a masz zainstalowane 16.111.5.

## F4.1 — Rozszerz diagnostykę
Gdy `offered < installed`, wypisz **konkretnie**: nazwę kanału, build zainstalowany, build oferowany oraz dwie drogi wyjścia (wyrównanie kanału w górę / reinstalacja Office z kanału zgodnego). Klucze i18n × 7.

## F4.2 — Eskalacja czasowa
Wykorzystaj `logs/version_history.tsv`: jeśli wersje Office nie zmieniły się od > `MAC_UPDATE_STALE_DAYS`, a MAU stale oferuje starszy pakiet — podnieś z INFO do WARN.

## F4.3 — Czego NIE robić
❌ **Nie zmieniaj `ChannelName` automatycznie.** To decyzja administracyjna dla całego pakietu Office. Skrypt ma wykryć i nazwać, nie naprawiać.

## F4.4 — Przygotuj notatkę dla właściciela
Krótko, w raporcie: co oznacza kanał `External`, dlaczego powoduje pętlę, jakie są dwie opcje i którą rekomendujesz. Bez wykonywania.

---

# 🟡 F5 — Domknięcie

## F5.1 — READMEs merytorycznie
`git diff --stat` z v1.2.0 pokazał 7/7 plików, ale **5 z nich dostało 1 linię** (sam numer wersji). Merytorycznie zaktualizowane są tylko `README.md` i `README.pl.md`.

Uzupełnij `README.de.md`, `README.es.md`, `README.fr.md`, `README.it.md`, `README.pt.md` o **treść**: Touch ID, LaunchAgent, nowe flagi i zmienne, nowe metody (`brew_cask`, `sparkle_appcast`, `vendor_latest`), tabelę pokrycia.

**Dowód:** `git diff --stat` z liczbą zmienionych linii **> 10 dla każdego** z 5 plików.

## F5.2 — Audyt testów pozornych
Przejrzyj **wszystkie** testy w `tests/test_safety_static.py` i dla każdego odpowiedz: *czy ten test zawiedzie, jeśli zepsuję implementację?* Wypisz listę testów, które **nie** spełniają tego kryterium, i napraw co najmniej te dotyczące: bezpiecznika downgrade'u, dedupu inwentarza, walidacji `CASK_MISSING`, `NONINTERACTIVE`.

## F5.3 — Wersja
`VERSION` → `1.3.0`; `CHANGELOG.md` → sekcja `## [1.3.0]` opisująca **uczciwie**, że naprawia niedziałający bezpiecznik z 1.2.0 i wprowadza kategorię `vendor_latest`; `CLAUDE.md` → numer wersji.

## F5.4 — Etap E (refaktor `lib/internet_app_updates.sh` 86 KB → < 25 KB)
**Nadal odłożony.** Nie zaczynaj. Zapisz jako znany dług.

---

# RAPORT KOŃCOWY — `IMPLEMENTATION_REPORT_v4.md`

## 1. Tabela wykonania

| ID | Zadanie | Status | Dowód (wyjście **wykonanego kodu**, nie grep) |
|----|---------|--------|-----------------------------------------------|
| F1.1 | Logika `older` | | |
| F1.2 | Parsowanie JSON | | |
| F1.3 | Mapowanie slug→app | | |
| F1.4 | Testy behawioralne | | |
| F2.1 | Metoda `vendor_latest` | | |
| F2.2 | Wypięcie 9 aplikacji | | |
| F2.3 | ChatGPT — decyzja | | |
| F2.5 | `--greedy-auto-updates` | | |
| F3.1 | Test dedupu (musi najpierw zawieść) | | |
| F3.2 | Fix `build_inventory.sh` | | |
| F3.3 | Opisy casków | | |
| F3.4 | Legenda z configu | | |
| F4.1–4.4 | MAU | | |
| F5.1 | READMEs × 5 merytorycznie | | |
| F5.2 | Audyt testów pozornych | | |
| F5.3 | Wersja 1.3.0 | | |

Statusy: **✅** (z dowodem wykonania) · **⏸️ blokowane** · **❌ niewykonane** · **❓ czeka na decyzję właściciela**

## 2. Metryki

| Metryka | v1.2.0 (zweryfikowane) | v1.3.0 (Twoje) |
|---|---|---|
| Aplikacje zagrożone downgrade'em | **4** | **musi być 0** |
| Bezpiecznik downgrade | **martwy kod** | **musi działać (dowód z F1.5)** |
| Aplikacje zdublowane w inwentarzu | **18** | **musi być 0** |
| Testy pozorne | **≥ 2** | ? |
| Aplikacje `vendor_latest` | 0 | ? |
| Caski zainstalowane | 20 | ? (spodziewane ~11) |
| READMEs merytorycznie | **2/7** | **musi być 7/7** |
| Testy | 141 | ? |

## 3. Tabela wersji — przed/po dla 9 wypiętych aplikacji
`Aplikacja | wersja przed wypięciem | wersja po | czy nietknięta? | dowód (defaults read)`

## 4. Decyzje dla właściciela
- Lista do wypięcia (F2.2) — do zatwierdzenia **przed** wykonaniem
- ChatGPT (F2.3)
- Microsoft AutoUpdate — kanał `External` (F4.4)
- P6.1 z poprzedniej sesji (untrackowanie `APPLICATIONS.md`) — **czy właściciel podjął decyzję?**

## 5. Weryfikacja końcowa — wklej wszystkie wyjścia
```bash
bash run_tests.sh
bash update_all.sh -y --skip-system
MAC_UPDATE_NONINTERACTIVE=1 bash update_all.sh -y --skip-system
bash scripts/report_update_coverage.sh
brew list --cask --versions
git diff --stat HEAD~1 -- 'README*.md'
```

---

# CZEGO NIE ROBIĆ

- ❌ **Nie pisz testów, które nie potrafią zawieść.** Każdy nowy test musi zawieść przy zepsutej implementacji — pokaż to.
- ❌ **Nie używaj `--zap` przy odpinaniu casków.** Kasuje dane użytkownika. Tylko `uninstall --force`.
- ❌ Nie wypinaj aplikacji przed zatwierdzeniem listy przez właściciela.
- ❌ Nie zmieniaj `ChannelName` Microsoft AutoUpdate.
- ❌ Nie ruszaj działającego kodu z listy w zasadzie #7.
- ❌ Nie zaczynaj Etapu E (refaktor).
- ❌ Nie dodawaj kluczy i18n tylko do `en`/`pl`.
- ❌ Nie twierdź, że `--greedy-auto-updates` eliminuje ryzyko downgrade'u.
- ❌ Nie edytuj `APPLICATIONS.md` ręcznie — napraw `build_inventory.sh` i wygeneruj.

---

**Zacznij od F1.5** — uruchom pętlę porównującą cztery pary wersji przez obecną logikę i **pokaż, że wszystkie cztery przechodzą przez bezpiecznik bez zatrzymania**. To potwierdzi diagnozę i będzie punktem odniesienia dla naprawy. Dopiero potem pisz kod.
