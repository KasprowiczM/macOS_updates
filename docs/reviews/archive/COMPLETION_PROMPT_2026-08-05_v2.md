# COMPLETION PROMPT — macOS_updates v1.1.0 → v1.1.1 (production-ready)
> **Przeznaczenie:** wklej całość jako pojedynczy prompt do Gemini w sesji uruchomionej w `~/Dev_Env/macOS_updates`.
> **Bazuje na:** `ULTRA_REVIEW_2026-08-05_v2.md` (weryfikacja Twojego wdrożenia v1.1.0)

---

Pracujesz w repozytorium `~/Dev_Env/macOS_updates` (Bash 3.2+, Python 3, Apple Silicon, macOS 13–26, 7 języków).

Wykonałeś wcześniej wdrożenie v1.1.0. **Faza 1 wyszła bardzo dobrze** — wzorzec `INTERNET_LAST_STATUS`, config-driven settle-loop, `internet_version_relation()`, sudo keep-alive: to solidna inżynieria i nic z tego nie ruszamy.

Ale weryfikacja wykazała **regresję krytyczną** i trzy fazy odhaczone bez pokrycia. Przeczytaj **najpierw** `ULTRA_REVIEW_2026-08-05_v2.md` — cały. Ten prompt zakłada, że go znasz.

---

## NAJWAŻNIEJSZA ZASADA TEJ SESJI

> **Nie wolno oznaczyć zadania jako wykonane na podstawie edycji pliku, jeżeli zadanie wymaga zmiany stanu systemu.**

Poprzednio Faza 2 została zaraportowana jako ✅, ponieważ zmieniono `config/internet_app_methods.txt`. Ale `brew install --cask --adopt` nigdy nie uruchomiono, więc 18 aplikacji przestało być aktualizowane przez cokolwiek.

W tej sesji **każde** stwierdzenie „zrobione" musi mieć dowód w postaci **wklejonego wyjścia komendy**. Nie opisu. Nie parafrazy. Dosłownego outputu.

Jeżeli nie możesz wykonać komendy (brak sieci, brak uprawnień, brak interaktywnej sesji) — **oznacz zadanie jako ⏸️ BLOKOWANE i napisz dlaczego**. To jest w pełni akceptowalna odpowiedź. Fałszywe ✅ nie jest.

---

## ZASADY NIENARUSZALNE (bez zmian względem poprzedniej sesji)

1. **Bash 3.2** — zero `declare -A`, `mapfile`, `readarray`, `${var^^}`.
2. **`softwareupdate` zawsze z `-R`**; **`mas upgrade` zawsze z `sudo`**.
3. **Zero hardcoded paths**; temp przez `mktemp -d "${TMPDIR:-/tmp}/mac_update_*.XXXXXX"`.
4. **`set -o pipefail` tak, `set -e` nie.**
5. **Każdy nowy string użytkownika → wszystkie 7 `i18n/lang_*.sh`.**
6. **Nie zmieniasz severity contract** (0/10/1). Statusy „unverified" nie blokują kroku 6.
7. **Nie dotykasz `/etc/sudoers`.**
8. **Po każdym etapie `bash run_tests.sh` musi być zielone.**
9. **Nie ruszasz kodu Fazy 1** — `INTERNET_LAST_STATUS`, settle-loop, keep-alive, `internet_version_relation()` zostają jak są.

---

# ETAP A — NAPRAWA REGRESJI (blokuje wszystko inne)

## A.0 — Ustal stan faktyczny, zanim cokolwiek zmienisz

Uruchom i **wklej pełne wyjście** do raportu:

```bash
brew list --cask --versions
brew --version
ls -1 /Applications | wc -l
```

Następnie zbuduj tabelę porównawczą — dla każdego wiersza `brew_cask` w `config/internet_app_methods.txt` sprawdź, czy aplikacja faktycznie jest w `brew list --cask`:

```bash
while IFS='|' read -r app method status_var; do
    case "$app" in '#'*|'') continue ;; esac
    [ "$(echo "$method" | tr -d '[:space:]')" = "brew_cask" ] || continue
    printf '%-34s' "$app"
    if brew list --cask --versions 2>/dev/null | grep -qi "$(echo "$app" | tr '[:upper:] ' '[:lower:]-')"; then
        echo "✅ pod Homebrew"
    else
        echo "❌ NIEZARZĄDZANA"
    fi
done < config/internet_app_methods.txt
```

Ta tabela jest **punktem wyjścia**. Wklej ją w całości.

## A.1 — Bezpiecznik: wykrywanie desyncu config ↔ Homebrew

**To robisz PIERWSZE, przed adopcją.** Chodzi o to, żeby problem nigdy więcej nie przeszedł niezauważony.

Dodaj do `update_internet_apps.sh` (przed sekcją PODSUMOWANIE) walidację:
- dla każdego wpisu `brew_cask` w configu sprawdź obecność w `brew list --cask --versions`
- brak → status `L_INTERNET_STATUS_CASK_MISSING` (nowy klucz) + `INTERNET_SOFT_FAIL=1`
- **soft, nigdy hard** — nie wolno zablokować kroku 6

Nowy klucz i18n we **wszystkich 7** językach, np.:
- EN: `L_INTERNET_STATUS_CASK_MISSING="⚠️  Config says brew_cask but the cask is not installed"`
- PL: `L_INTERNET_STATUS_CASK_MISSING="⚠️  Config mówi brew_cask, ale cask nie jest zainstalowany"`

Dodaj status do pętli klasyfikującej SOFT w `update_internet_apps.sh` (~L640).

Dodaj test w `tests/test_safety_static.py`:
`test_brew_cask_entries_are_validated` — asercja, że `update_internet_apps.sh` zawiera walidację `brew list --cask` dla metody `brew_cask`.

**Weryfikacja:** uruchom `bash update_internet_apps.sh` i pokaż, że **18 aplikacji zgłasza `CASK_MISSING`**. To potwierdzi, że bezpiecznik działa i że diagnoza z review jest prawdziwa.

## A.2 — Audyt casków (wcześniej pominięty)

```bash
bash scripts/audit_cask_candidates.sh
```

**Wklej pełne wyjście.** Jeżeli skrypt nie działa albo daje bezużyteczny wynik — napraw go i uruchom ponownie.

Dla każdej z 18 aplikacji potrzebuję jednoznacznej odpowiedzi: `cask istnieje` / `cask nie istnieje` / `cask istnieje, ale to inna aplikacja`.

⚠️ Pamiętaj o swoim własnym znalezisku z poprzedniej sesji: cask `gemini` to Gemini 2 od MacPaw, nie Google Gemini. **Sprawdź każdy cask pod tym kątem** — porównaj `brew info --cask <nazwa>` (homepage, desc) z faktyczną aplikacją. Fałszywe dopasowanie = nadpisanie cudzą aplikacją.

## A.3 — Decyzja per aplikacja

Podziel 18 aplikacji na trzy koszyki i **przedstaw mi tabelę do zatwierdzenia przed wykonaniem**:

| Koszyk | Kryterium | Akcja |
|--------|-----------|-------|
| **ADOPT** | cask istnieje, jednoznacznie ta sama aplikacja | `brew install --cask --adopt` |
| **ROLLBACK** | brak casku / niejednoznaczny / inna aplikacja | powrót do `silent_launch` |
| **PYTAM** | wątpliwość (licencja, ścieżka, dane użytkownika) | pytasz mnie |

**Nie wykonuj adopcji przed moim zatwierdzeniem tabeli.**

## A.4 — Wykonanie ADOPT (partiami po 5)

Dla każdej partii:
```bash
brew install --cask --adopt <cask1> <cask2> ... 
brew list --cask --versions | grep -E "cask1|cask2|..."
```
Po każdej partii:
- **wklej wyjście obu komend**
- otwórz każdą aplikację i potwierdź, że działa (ustawienia, licencja, zalogowanie)
- jeśli cokolwiek pójdzie źle → **stop**, opisz, nie kontynuuj

## A.5 — Wykonanie ROLLBACK

Dla aplikacji bez casku przywróć poprzedni, działający stan:
1. `config/internet_app_methods.txt`: `brew_cask` → `silent_launch`
2. `config/internet_dispatch_order.txt`: **odkomentuj** wpis `iu_*`
3. `update_internet_apps.sh` (~L407–435): usuń zahardkodowany `"→ managed by Homebrew"`, przywróć `="$L_INTERNET_STATUS_SKIPPED"`
4. Sprawdź, że funkcja `iu_*` w `lib/internet_app_updates.sh` nadal istnieje i jest sprawna

## A.6 — Aktualizacja inwentarza

```bash
bash build_inventory.sh
```
Potwierdź, że `APPLICATIONS.md` sekcja 4c zawiera **wszystkie** zaadoptowane caski, a zmigrowane aplikacje zniknęły z GRUPY 3.

## A.7 — PRAWDZIWY RUN (nie dry-run)

```bash
bash update_all.sh -y --skip-system 2>&1 | tail -120
```

**Wklej ostatnie 120 linii.** Muszę zobaczyć:
- zero statusów `CASK_MISSING`
- każda zaadoptowana aplikacja: `→ managed by Homebrew` **i** obecna w `brew list --cask`
- tabelę podsumowania z **jedną linią na aplikację** (bez wielolinijkowych sklejek)
- `Settle wait: Xs (limit Ys, N stable readings)` — dowód, że settle-loop żyje
- **ani jednego promptu o hasło**

### 🚦 BRAMKA ETAPU A

Nie przechodzisz dalej, dopóki nie masz **wszystkich** poniższych dowodów wklejonych:
- [ ] `brew list --cask --versions` — przed i po
- [ ] wyjście `audit_cask_candidates.sh`
- [ ] zatwierdzona przeze mnie tabela ADOPT/ROLLBACK/PYTAM
- [ ] log prawdziwego runu, bez `[DRY-RUN]`
- [ ] `bash run_tests.sh` zielone

---

# ETAP B — DOKOŃCZENIE FUNKCJI ZADEKLAROWANYCH JAKO GOTOWE

## B.1 — Logika „dni bez zmiany" (Faza 3.4 — dziś połowa)

Stan obecny: `logs/version_history.tsv` jest **zapisywany**, ale **nikt go nie czyta**. Klucze `L_INTERNET_UNCHANGED_DAYS_FMT` i `L_INTERNET_STALE_WARNING_FMT` istnieją we wszystkich 7 językach i **nie są nigdzie użyte**. `MAC_UPDATE_STALE_DAYS=45` jest udokumentowane w `lib/cli.sh:32` i **nieobsłużone**.

Dokończ:
1. Funkcja czytająca TSV i zwracająca liczbę dni od ostatniej **zmiany wersji** danej aplikacji (nie od ostatniego wpisu — od ostatniej różnicy).
2. W podsumowaniu kroku 4, dla aplikacji bez bezpośredniej weryfikacji, dopisz `· <L_INTERNET_UNCHANGED_DAYS_FMT>`.
3. Gdy `dni > MAC_UPDATE_STALE_DAYS` (domyślnie 45) → status `L_INTERNET_STALE_WARNING_FMT` + `INTERNET_SOFT_FAIL=1`. **Nigdy hard.**
4. **Rotacja:** przytnij TSV do ostatnich `MAC_UPDATE_MAX_LOGS` × liczba aplikacji wierszy albo do 365 dni — wybierz jedno i udokumentuj.
5. `.gitignore`: dodaj `logs/version_history.tsv`, `logs/launchd.out`, `logs/launchd.err`.

Test: `test_version_history_is_read_back` — asercja, że TSV jest czytany, nie tylko zapisywany.

## B.2 — `MAC_UPDATE_NONINTERACTIVE` ma naprawdę działać

Dziś steruje **wyłącznie** powiadomieniem (`update_all.sh:1825`). Efekt: run z launchd wejdzie w TOR 2 App Store GUI (`update_appstore.sh:286–445`), spróbuje AppleScript bez sesji użytkownika i zawiśnie albo zwróci błąd Accessibility.

Zaimplementuj pełny kontrakt:
- wymusza `MAC_UPDATE_YES=1` (także gdy ustawione jako zmienna środowiskowa, nie tylko przez flagę `--non-interactive`)
- pomija sudo keep-alive (i tak `[ -t 0 ]` jest fałszywe — dodaj jawny warunek dla czytelności)
- **pomija TOR 2 App Store GUI** w `update_appstore.sh` z jasnym komunikatem, że pominięto z powodu braku sesji GUI (nowy klucz i18n × 7)
- pomija wszelkie `read -r -p`

Test: `test_noninteractive_skips_gui_track`.

## B.3 — `printf` z formatem ze zmiennej

`lib/internet_handlers.sh` — zastąp `printf "$L_..._FMT" ...` istniejącym helperem `internet_msg`, tak jak w reszcie projektu. Powód: `%` lub backslash w którymkolwiek z 7 tłumaczeń psuje status.

Przeskanuj **cały projekt** pod kątem tego wzorca (`printf "$L_`) i napraw każde wystąpienie. Wypisz listę.

## B.4 — `install_launchagent.sh` — higiena argumentów

- `*)` ma zgłaszać błąd i kończyć z kodem 2, nie `shift` po cichu
- dodaj `-h/--help`
- waliduj `--day` (1–7) i `--hour` (0–23); poza zakresem → błąd przed zapisem plistu
- `--check` ma dodatkowo pokazać `StartCalendarInterval` z faktycznego plistu

## B.5 — Optymalizacja settle-loopa

`update_internet_apps.sh:497–507` parsuje `internet_app_methods.txt` dla każdej aplikacji w każdej sekundzie pollingu. Zbuduj mapę `STATUS_VAR → app_path` **raz**, przed pętlą (w Bash 3.2: dwie równoległe zmienne łańcuchowe albo plik tymczasowy).

## 🚦 BRAMKA ETAPU B
- [ ] `bash run_tests.sh` zielone
- [ ] `bash update_all.sh -y --skip-system` — wklejony log pokazujący „dni bez zmiany" przy aplikacjach
- [ ] `MAC_UPDATE_NONINTERACTIVE=1 bash update_all.sh -y --skip-system` — wklejony log, **bez** prób automatyki GUI

---

# ETAP C — ROZSZERZENIE WERYFIKACJI (Faza 3 do końca)

## C.1 — Uruchom skaner feedów

```bash
bash scripts/scan_update_feeds.sh
```
**Wklej pełne wyjście.** W poprzedniej sesji skrypt powstał, ale nigdy go nie uruchomiono — dlatego `sparkle_appcast` trafił tylko na 1 aplikację.

## C.2 — Rozjedź `sparkle_appcast`

Na podstawie wyniku C.1 przełącz na `sparkle_appcast` **każdą** pozostałą aplikację `silent_launch`, która ma `SUFeedURL`. Dziś zostało 5: `ChatGPT / Codex`, `Gemini`, `OpenCode`, `Ascendo`, `Remote Desktop Manager` (lista może się zmienić po ETAPIE A).

Dla każdej udowodnij działanie:
```bash
defaults read "/Applications/<App>.app/Contents/Info" SUFeedURL
curl -fsSL --max-time 15 "<feed>" | grep -o 'sparkle:shortVersionString="[^"]*"' | head -3
```

## C.3 — Electron feed (opcjonalnie, jeśli C.1 wykaże)

Jeśli skaner znajdzie `app-update.yml`, dodaj metodę `electron_feed` analogiczną do `sparkle_appcast`. Jeśli nie znajdzie — **napisz to wprost i pomiń**. Nie dodawaj martwego kodu.

## 🚦 BRAMKA ETAPU C
- [ ] Liczba aplikacji z **potwierdzoną wersją zdalną** ≥ 12 (start: 6)
- [ ] `bash scripts/report_update_coverage.sh` — wklejone wyjście

---

# ETAP D — DOKUMENTACJA (Faza 6.2, wcześniej pominięta)

Wszystkie 7 `README*.md` i wszystkie `docs/agents/*.md` są **nietknięte od 28–30 lipca** i opisują v1.0.21. Uzupełnij:

## D.1 — README × 7
`README.md`, `README.pl.md`, `README.de.md`, `README.es.md`, `README.fr.md`, `README.it.md`, `README.pt.md`:
- Touch ID: `scripts/setup_touchid_sudo.sh` (krok per-maszyna, **nie** przenosi się przez `git pull`)
- LaunchAgent: `scripts/install_launchagent.sh`
- nowe flagi: `--non-interactive`, `--notify`
- nowe zmienne: `MAC_UPDATE_NO_SUDO_KEEPALIVE`, `MAC_UPDATE_NONINTERACTIVE`, `MAC_UPDATE_NOTIFY`, `MAC_UPDATE_STALE_DAYS`
- nowe metody: `brew_cask`, `sparkle_appcast`
- zaktualizowana tabela pokrycia

## D.2 — docs/agents
- `architecture.md` — kontrakt `INTERNET_LAST_STATUS` (handlery **nigdy** nie zwracają statusu przez stdout); format configu
- `critical_rules.md` — nowa reguła: „metoda `brew_cask` w configu wymaga faktycznej adopcji; walidacja obowiązkowa"; decyzja o `--greedy` vs `--greedy-auto-updates`
- `troubleshooting.md` — Touch ID (tabela objaw/przyczyna/fix z `ULTRA_REVIEW_2026-08-05.md` §2), keep-alive, launchd, `CASK_MISSING`
- `scripts.md` — `setup_touchid_sudo.sh`, `install_launchagent.sh`, `audit_cask_candidates.sh`, `scan_update_feeds.sh`
- `exit_codes.md` — nowe statusy soft

## D.3 — Wersja
`VERSION` → `1.1.1`; `CHANGELOG.md` → sekcja `## [1.1.1]` opisująca **uczciwie**, że naprawia regresję z 1.1.0; `CLAUDE.md` → numer wersji.

---

# ETAP E — DŁUG TECHNICZNY (dopiero po A–D)

Faza 5 z poprzedniego promptu **nie została wykonana**: `lib/internet_app_updates.sh` ma **86 684 B** przy celu **< 25 600 B**, 36 funkcji `iu_*`, config nadal 3-kolumnowy.

**Nie zaczynaj tego etapu, dopóki A–D nie są zamknięte.** Jeżeli zabraknie kontekstu lub czasu — **zostaw i wyraźnie zaznacz w raporcie**. To jedyny etap, który wolno świadomie odłożyć.

Gdy ruszasz:
1. Rozszerz config o kolumny `app_path | feed_url | version_regex | team_id | verify_hint | download_url`, zachowując wsteczną zgodność z 3-kolumnowymi wierszami (`lib/internet_registry.sh:20–40` — rozszerz walidację, nie łam)
2. Zredukuj `iu_*` do handlerów generycznych sterowanych configiem
3. Zostaw wyłącznie funkcje z nieredukowalną logiką (Microsoft 365 z deferralami, Teams z fallbackiem MAU, Firefox Dev z kanałem beta) — **uzasadnij każdą**
4. Zaktualizuj `scripts/scaffold_internet_app.sh` tak, by generował **wpis w configu**, nie boilerplate shellowy; dodaj znajomość metod `brew_cask` i `sparkle_appcast`
5. Test regresji: pełny run musi dać **identyczny zestaw statusów** jak log z ETAPU A.7

---

# RAPORT KOŃCOWY — `IMPLEMENTATION_REPORT_v2.md`

Format obowiązkowy. Kolumna „Dowód" zawiera **dosłowne wyjście komendy**, nie opis.

## 1. Tabela wykonania

| Etap | Zadanie | Status | Dowód (wklejone wyjście) |
|------|---------|--------|--------------------------|
| A.0 | Stan faktyczny | | |
| A.1 | Bezpiecznik desync | | |
| A.2 | Audyt casków | | |
| A.3 | Tabela decyzji | | |
| A.4 | Adopcja | | |
| A.5 | Rollback | | |
| A.6 | Inwentarz | | |
| A.7 | Prawdziwy run | | |
| B.1–B.5 | … | | |
| C.1–C.3 | … | | |
| D.1–D.3 | … | | |
| E | Refaktor | | |

Dozwolone statusy: **✅ wykonane** (z dowodem) · **⏸️ blokowane** (z powodem) · **❌ niewykonane** (z powodem) · **🔄 rollback**.
**Status ✅ bez wklejonego dowodu jest nieważny.**

## 2. Metryki — zmierzone, nie szacowane

| Metryka | v1.0.21 | v1.1.0 (zweryfikowane) | v1.1.1 (Twoje) |
|---------|---------|------------------------|----------------|
| Aplikacje faktycznie pod Homebrew (`brew list --cask \| wc -l`) | 2 | **2** | ? |
| Wpisy `brew_cask` w configu | 0 | 19 | ? |
| **Desync config ↔ Homebrew** | 0 | **19** | **musi być 0** |
| `silent_launch` w configu | 24 | 5 | ? |
| Aplikacje z potwierdzoną wersją zdalną | 6 | 6 | ? |
| `lib/internet_app_updates.sh` (bajty) | 87 371 | 86 684 | ? |
| Testy | 134 | 134 | ? |
| Prompty o hasło w pełnym runie | 2 + sudo | nietestowane | ? |
| **Prawdziwe (nie dry-run) runy po zmianach** | — | **0** | **musi być ≥ 1** |

## 3. Aplikacje — stan końcowy
Tabela: `Aplikacja | metoda przed | metoda po | pod Homebrew? | wersja zweryfikowana? | dowód`

## 4. Odłożone
Co, dlaczego, co odblokuje. „Nie zdążyłem" bez dalszego ciągu jest niedopuszczalne.

## 5. Ryzyka rezydualne
Co może się zepsuć po tym wydaniu i jak to wykryć.

---

# CZEGO NIE ROBIĆ

- ❌ **Nie oznaczaj zadania ✅ bez wklejonego wyjścia komendy.**
- ❌ Nie zmieniaj configu na `brew_cask` bez wykonanej i potwierdzonej adopcji.
- ❌ Nie ruszaj kodu Fazy 1 (`INTERNET_LAST_STATUS`, settle-loop, keep-alive, `internet_version_relation`).
- ❌ Nie dodawaj `set -e`; nie zmieniaj severity contract; nie blokuj kroku 6 statusami soft.
- ❌ Nie usuwaj weryfikacji podpisu / Team ID.
- ❌ Nie dodawaj kluczy i18n tylko do `en`/`pl`.
- ❌ Nie commituj `logs/`, `dev_sync_logs/`, `.mac_update_prefs`.
- ❌ Nie zaczynaj ETAPU E przed zamknięciem A–D.
- ❌ Nie adoptuj casku, którego tożsamości nie potwierdziłeś (pamiętaj o pułapce `gemini` = MacPaw).

---

**Zacznij od ETAPU A.0.** Wykonaj komendy, wklej wyjścia, przedstaw tabelę decyzji z A.3 i **zaczekaj na moje zatwierdzenie** przed pierwszą adopcją. Nie pisz kodu przed A.0.
