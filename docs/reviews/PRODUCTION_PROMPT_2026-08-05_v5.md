# PRODUCTION PROMPT — macOS_updates v1.3.0 → v1.3.1 (release do produkcji)
> **Przeznaczenie:** wklej całość jako pojedynczy prompt do Gemini w sesji uruchomionej w `~/Dev_Env/macOS_updates`.
> **Bazuje na:** `ULTRA_REVIEW_2026-08-05_v5.md`

---

Pracujesz w `~/Dev_Env/macOS_updates` (Bash 3.2+, Python 3, Apple Silicon, macOS 13–26, 7 języków).

**v1.3.0 to najlepszy stan tego projektu do tej pory.** Cel biznesowy osiągnięty: 9 aplikacji zdjętych z Homebrew, **wszystkie zachowały najnowsze wersje** (Comet 150.0.7871.228, Cursor 3.14.27, Warp 0.2026.07.29, Antigravity 2.5.0, Proton Mail 1.13.4). Bezpiecznik downgrade'u działa, deduplikacja inwentarza jest prawdziwa, 146 testów przechodzi.

**Do produkcji brakuje jednej rzeczy z prawdziwą treścią.** Przeczytaj `ULTRA_REVIEW_2026-08-05_v5.md` w całości.

⚠️ **Prompty sudo/Touch ID zostały już naprawione poza Twoją sesją** — `update_all.sh` blok „SUDO ACQUISITION", 3 nowe klucze i18n, 4 testy behawioralne. **Nie ruszaj tego kodu.** Jeśli musisz go dotknąć, najpierw wyjaśnij dlaczego.

---

## 🚨 ZASADA TEJ SESJI

> **Zmiana etykiety w configu to nie jest wdrożenie metody.**

Zdarzyło się to dwa razy:
- v1.1.0: `brew_cask` w configu, adopcja nigdy nie wykonana → 18 aplikacji bez aktualizacji
- v1.3.0: `vendor_latest` w configu, **handler nigdy nie napisany** → 9 aplikacji nadal „⏳ uruchomiony (niezweryfikowany)"

**Dowodem wdrożenia metody weryfikującej wersję jest linia z logu prawdziwego runu pokazująca porównanie wersji lokalnej ze zdalną.** Nie wpis w pliku. Nie fragment kodu. Linia z logu.

---

## ZASADY NIENARUSZALNE

1. **Bash 3.2** — bez `declare -A`, `mapfile`, `readarray`, `${var^^}`.
2. **`softwareupdate` z `-R`**; **`mas upgrade` z `sudo`**.
3. **Zero hardcoded paths**; temp przez `mktemp -d "${TMPDIR:-/tmp}/mac_update_*.XXXXXX"`.
4. **`set -o pipefail` tak, `set -e` nie.**
5. **Nowy string użytkownika → wszystkie 7 `i18n/lang_*.sh`.**
6. **Severity contract 0/10/1 bez zmian.** Statusy soft nie blokują kroku 6.
7. **Nie ruszasz działającego kodu:** blok „SUDO ACQUISITION" w `update_all.sh`, `INTERNET_LAST_STATUS`, settle-loop, `CASK_MISSING`, stale-days, bezpiecznik downgrade'u (`update_brew.sh:240–283`), detekcja kanału MAU, `scripts/fix_inventory_dedup.py`.
8. **Każdy nowy test musi potrafić zawieść** przy zepsutej implementacji — pokaż to.
9. **`bash run_tests.sh` zielone po każdym etapie.**

---

# 🔴 G1 — Zaimplementuj `vendor_latest` (jedyny prawdziwy bloker)

## Stan faktyczny
```bash
grep -rn "vendor_latest" --include="*.sh" --include="*.py" .
→ scripts/report_update_coverage.sh:227
→ scripts/fix_inventory_dedup.py:7
```
**Zero handlerów.** Dziewięć aplikacji spada do starych funkcji `iu_*` i zachowuje się jak `silent_launch`. Log ostatniego runu:
```
Cursor:        ⏳ Uruchomiony (niezweryfikowany)
Warp:          ⏳ Uruchomiony (niezweryfikowany)
Comet:         ⏳ Uruchomiony (niezweryfikowany)
Proton Mail:   ⏳ Uruchomiony (niezweryfikowany)
```

Aplikacje objęte: **ChatGPT / Codex, Claude, Comet, Antigravity, Antigravity IDE, Cursor, Proton Mail, Proton Drive, Warp**.

## G1.1 — Handler

Dodaj `internet_handler_vendor_latest()` do `lib/internet_handlers.sh`. Semantyka: **weryfikuj wersję zdalną, nie instaluj.**

Kolejność prób pozyskania wersji zdalnej — pierwsza, która zadziała:
1. `SUFeedURL` z `Info.plist` → appcast Sparkle (użyj **istniejącego** `internet_handler_sparkle_check`, nie pisz drugiej implementacji)
2. `Contents/Resources/app-update.yml` → feed electron-updater
3. Endpoint producenta z nowej kolumny `feed_url` w configu (patrz G1.2)

Następnie:
- porównaj przez **istniejące** `internet_version_relation "$remote" "$local"`
- ustaw `INTERNET_LAST_STATUS`:
  - `"newer"` → `L_INTERNET_STATUS_UPDATE_AVAILABLE_FMT` (lokalna → zdalna)
  - `"current"` → `L_INTERNET_STATUS_CURRENT_FMT`
  - `"unknown"` / brak feedu → `L_INTERNET_STATUS_UNKNOWN_VERSION`
  - brak sieci → `L_INTERNET_STATUS_OFFLINE`
- uruchom natywny updater w tle (jak `silent_launch`)
- **nigdy nie podmieniaj bundla**

## G1.2 — Źródła feedów

Rozszerz `config/internet_app_methods.txt` o opcjonalną **czwartą kolumnę** `feed_url`, zachowując wsteczną zgodność z wierszami 3-kolumnowymi (`lib/internet_registry.sh` — rozszerz walidację, nie łam).

Najpierw **uruchom skaner** i wklej wyjście:
```bash
bash scripts/scan_update_feeds.sh
```
Dla każdej z 9 aplikacji podaj: `Sparkle` / `electron-updater` / `brak`. Dla tych bez feedu — sprawdź publiczny endpoint producenta (np. Cursor API, Warp releases). **Jeśli aplikacja nie ma żadnego weryfikowalnego źródła, zostaw ją jako `silent_launch` i napisz to wprost.** Nie udawaj weryfikacji.

## G1.3 — Rejestracja metody
- dispatcher w `lib/internet_registry.sh` / `update_internet_apps.sh`
- `METHOD_LABELS` w `scripts/report_update_coverage.sh` — **wszystkie 7 sekcji językowych**
- opis metody w komentarzu nagłówkowym `config/internet_app_methods.txt`

## G1.4 — Testy behawioralne
1. `test_vendor_latest_handler_exists_and_sets_status` — wywołuje handler ze zmockowanym feedem i sprawdza `INTERNET_LAST_STATUS`
2. `test_vendor_latest_detects_newer_remote` — feed z wersją wyższą → status „update available"
3. `test_vendor_latest_reports_current_when_equal`
4. `test_every_config_method_has_a_handler` — **strażnik systemowy**: dla każdej unikalnej metody w `config/internet_app_methods.txt` musi istnieć odpowiadający handler. Ten test uniemożliwia powtórkę „etykieta bez kodu".

Test #4 musi **zawieść na obecnym kodzie**. Pokaż to, zanim napiszesz handler.

## G1.5 — Dowód wymagany
```bash
bash update_all.sh -y --skip-system 2>&1 | grep -A2 -E "Cursor|Warp|Comet|Proton Mail"
```
W logu muszą być **konkretne wersje**, np.:
```
Cursor:  ✅ Aktualny (3.14.27)
Warp:    ⚠️  Dostępna aktualizacja: 0.2026.07.29 → 0.2026.08.03
```
**Status „⏳ Uruchomiony (niezweryfikowany)" dla którejkolwiek z 9 aplikacji = zadanie niewykonane.**

---

# 🔴 G2 — Napraw zawyżoną metrykę pokrycia

`scripts/report_update_coverage.sh:227`:
```python
DIRECT_METHODS = {"keystone", "github_dmg", "msupdate", "docker_cli", "sparkle_appcast", "vendor_latest"}
```

`vendor_latest` jest liczony jako weryfikacja bezpośrednia, choć dziś nic nie weryfikuje. **Raport zawyża pokrycie o 9 aplikacji.**

## G2.1
- **Do czasu ukończenia G1** usuń `vendor_latest` z `DIRECT_METHODS`.
- **Po ukończeniu G1** wróć go tam, ale zaklasyfikuj **per aplikacja, nie per metoda**: aplikacja z działającym feedem → direct; bez feedu → `triggered_unverified`.

## G2.2 — Test
`test_coverage_does_not_count_unverified_as_direct` — metoda bez działającego handlera weryfikującego nie może trafić do `DIRECT_METHODS`.

## G2.3 — Dowód
```bash
bash scripts/report_update_coverage.sh
```
Wklej wyjście **przed i po** G1. Liczba „zweryfikowanych" ma wzrosnąć **dopiero wtedy, gdy weryfikacja faktycznie działa**.

---

# 🟡 G3 — Dwie aplikacje raportują błędnie

## G3.1 — Claude Desktop: `⏭️ Pominięty`
Podsumowanie mówi „Pominięty", a inwentarz ma `Claude 1.25927.0`. Handler szuka innej nazwy/ścieżki niż faktyczna (`/Applications/Claude.app`). Znajdź rozbieżność i napraw.

## G3.2 — ChatGPT Atlas: `⏭️ Nieznana wersja`
`sparkle_appcast` nie parsuje feedu tej aplikacji. To jedna z **dwóch** aplikacji na tej metodzie — 50 % awaryjności.
```bash
defaults read "/Applications/ChatGPT Atlas.app/Contents/Info" SUFeedURL
curl -fsSL --max-time 15 "<feed>" | head -40
```
Wklej wyjścia i napraw parser (możliwe: `<title>` zamiast `sparkle:shortVersionString`, namespace, przekierowanie).

## G3.3 — Dowód
Obie aplikacje w logu z konkretną wersją, nie ze statusem zastępczym.

---

# 🟡 G4 — Higiena repozytorium przed wydaniem

## G4.1 — Nic nie jest zacommitowane
`git status` pokazuje 20+ zmodyfikowanych plików, `VERSION`=1.3.0, a w `.git` leży `index.lock` po przerwanej operacji.

1. Usuń `index.lock`, jeśli żaden proces git nie działa
2. Przejrzyj `git diff` **w całości** — potwierdź, że nie ma przypadkowych zmian
3. Zacommituj jako `[RELEASE] v1.3.1`

## G4.2 — Wersja i changelog
`VERSION` → `1.3.1`; `CHANGELOG.md` → sekcja `## [1.3.1]` opisująca **uczciwie**:
- naprawę promptów sudo/Touch ID bez TTY (wraz z osieroconym keep-alive)
- implementację `vendor_latest` (G1)
- korektę metryki pokrycia (G2)

`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, README × 7 — numer wersji.

## G4.3 — Decyzja właściciela, która wciąż wisi
**P6.1 z poprzednich sesji: untrackowanie `APPLICATIONS.md` i `UPDATES.md`.** Właściciel nie podjął decyzji. Przypomnij trzy warianty i **zapytaj**:
1. untracked + `APPLICATIONS.example.md` w repo + sync przez `dev_sync/` *(rekomendowany)*
2. cofnięcie untrackowania
3. zostawienie bez synchronizacji, świadoma rozbieżność między Macami

## G4.4 — Dług świadomie odłożony
`lib/internet_app_updates.sh` ~86 KB, 36 funkcji `iu_*`. **Nie zaczynaj refaktoru.** Zapisz w `CHANGELOG.md` jako znany dług.

---

# RAPORT KOŃCOWY — `IMPLEMENTATION_REPORT_v5.md`

## 1. Tabela wykonania

| ID | Zadanie | Status | Dowód (**linia z logu runu** dla G1/G3, wyjście komendy dla reszty) |
|----|---------|--------|---------------------------------------------------------------------|
| G1.1 | Handler `vendor_latest` | | |
| G1.2 | Skaner feedów + kolumna `feed_url` | | |
| G1.3 | Rejestracja metody + `METHOD_LABELS` × 7 | | |
| G1.4 | Testy behawioralne (w tym strażnik metod) | | |
| G2.1 | Korekta `DIRECT_METHODS` | | |
| G2.3 | Pokrycie przed/po | | |
| G3.1 | Claude Desktop | | |
| G3.2 | ChatGPT Atlas | | |
| G4.1 | Commit | | |
| G4.2 | Wersja 1.3.1 | | |
| G4.3 | Pytanie do właściciela | | |

Statusy: **✅** (z dowodem) · **⏸️ blokowane** (z powodem) · **❌** (z powodem) · **❓ czeka na właściciela**

## 2. Tabela 9 aplikacji `vendor_latest` — stan końcowy

| Aplikacja | Wersja lokalna | Źródło feedu | Wersja zdalna | Status w logu |
|---|---|---|---|---|
| ChatGPT / Codex | | | | |
| Claude | | | | |
| Comet | | | | |
| Antigravity | | | | |
| Antigravity IDE | | | | |
| Cursor | | | | |
| Proton Mail | | | | |
| Proton Drive | | | | |
| Warp | | | | |

Kolumna „Status w logu" musi zawierać **dosłowny** tekst z runu. Żadne pole nie może brzmieć „⏳ Uruchomiony (niezweryfikowany)" — a jeśli brzmi, w kolumnie „Źródło feedu" ma być `brak` z wyjaśnieniem.

## 3. Metryki

| Metryka | v1.3.0 | v1.3.1 |
|---|---|---|
| Aplikacje `vendor_latest` z **działającą** weryfikacją | **0** | **musi być ≥ 6/9** |
| Aplikacje ze statusem „uruchomiony, niezweryfikowany" | 9 | ? |
| Pokrycie wg `report_update_coverage.sh` | zawyżone o 9 | **musi być prawdziwe** |
| Metody w configu bez handlera | **1** (`vendor_latest`) | **musi być 0** |
| Testy | 146 | ? |
| Niezacommitowane pliki | 20+ | **musi być 0** |

## 4. Weryfikacja końcowa — wklej wszystkie wyjścia
```bash
bash run_tests.sh
bash update_all.sh -y --skip-system
MAC_UPDATE_NONINTERACTIVE=1 bash update_all.sh -y --skip-system   # ZERO promptów sudo
bash update_all.sh --dry-run -y                                    # ZERO promptów sudo
bash scripts/report_update_coverage.sh
git status --short
git log --oneline -3
```

## 5. Znane ograniczenia
- Refaktor `lib/internet_app_updates.sh` (86 KB) — odłożony
- macOS na Apple Silicon wymaga volume owner — run w tle nie instaluje aktualizacji systemu
- App Store bez TTY — świadomie pomijane

---

# CZEGO NIE ROBIĆ

- ❌ **Nie zmieniaj etykiety metody w configu bez napisania handlera.** To trzeci raz.
- ❌ **Nie pisz testów, które nie potrafią zawieść.** Pokaż, że test #G1.4.4 zawodzi na obecnym kodzie.
- ❌ Nie ruszaj bloku „SUDO ACQUISITION" w `update_all.sh` ani 4 testów sudo.
- ❌ Nie licz metody jako „direct", dopóki nie weryfikuje wersji.
- ❌ Nie ruszaj działającego kodu z listy w zasadzie #7.
- ❌ Nie zaczynaj refaktoru `lib/internet_app_updates.sh`.
- ❌ Nie dodawaj kluczy i18n tylko do `en`/`pl`.
- ❌ Nie używaj `--zap` przy jakichkolwiek operacjach na caskach.
- ❌ Nie decyduj sam w G4.3 — to decyzja właściciela.

---

**Zacznij od G1.4.4** — napisz strażnika „każda metoda w configu ma handler" i **pokaż, że zawodzi na obecnym kodzie**, wskazując `vendor_latest`. To potwierdzi diagnozę i będzie bramką dla reszty pracy. Potem uruchom `scripts/scan_update_feeds.sh`, wklej wyjście i przedstaw plan dla 9 aplikacji do zatwierdzenia.
