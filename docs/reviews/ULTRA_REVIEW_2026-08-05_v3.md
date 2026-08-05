# ULTRA REVIEW v3 — weryfikacja v1.1.1
**Data:** 2026-08-05 (późny wieczór) · **Weryfikowane commity:** `9d6545a`, `05e7f22`
**Punkt odniesienia:** `ULTRA_REVIEW_2026-08-05_v2.md` + `COMPLETION_PROMPT_2026-08-05_v2.md`

---

## WERDYKT: 🟡 BLISKO PRODUKCJI — 3 blokery, wszystkie do naprawy w jedno popołudnie

Regresja z v1.1.0 **została naprawiona naprawdę**, nie na papierze. To duża zmiana jakościowa względem poprzedniej sesji:

- **19 casków faktycznie zaadoptowanych** — potwierdzone w `APPLICATIONS.md` §4c i w `logs/version_history.tsv` (kolumna metody = `brew_cask`)
- **2 prawdziwe runy** (50 787 B i 54 013 B) — nie `--dry-run`
- **Bezpiecznik desync działa** — `CASK_MISSING` zwraca 0 trafień w ostatnim runie
- **OneDrive faktycznie zaktualizowany** 26.129.0706 → 26.134.0713 w runie 17:32
- **137 testów przechodzi** (było 134)

Ale zostały trzy rzeczy, które w obecnym kształcie zepsują produkcję — i jedna pozycja raportu, która **drugi raz z rzędu** została oznaczona ✅ bez pokrycia.

---

## 🔴 BLOKER P1 — `sudo` nie jest uwierzytelniane, gdy używasz `--skip-system`

To jest **ten sam błąd, który przyniosłem ja** w pierwszym review: fix keep-alive został zakresowany „dla kroku 6" i odziedziczył warunek `SKIP_SYSTEM != 1`.

`update_all.sh:200` i `:219`:
```bash
if [ "${MAC_UPDATE_SKIP_SYSTEM:-0}" != "1" ] && [ -t 0 ]; then   # sudo -v
if … && [ "${MAC_UPDATE_SKIP_SYSTEM:-0}" != "1" ] && [ -t 0 ]; then  # keep-alive
```

Problem: **krok 1 też potrzebuje `sudo`** — `sudo mas upgrade` (reguła nienaruszalna #2). Ale przy `--skip-system` sudo nie jest w ogóle wstępnie uwierzytelniane.

**Dowód z prawdziwego runu 17:29:**
```
--- appstore_diag.txt ---
=== TRACK 1 (sudo mas upgrade) FAILED ===
exit=1
--- output ---
sudo: a password is required

=== FINAL: mas outdated still reports updates ===
823766827  OneDrive  (26.129.0706 -> 26.134.0713)
```
```
Run summary
1. App Store: Błąd
```

W runie 17:32 zadziałało — ale **tylko dlatego, że timestamp sudo był jeszcze ciepły po poprzedniej próbie**. To przypadek, nie działający mechanizm.

**Dlaczego to blokuje produkcję:** LaunchAgent uruchamia dokładnie `update_all.sh -y --skip-system`, i to **bez TTY**. Wtedy `[ -t 0 ]` jest fałszywe, `sudo -v` nigdy nie wystartuje, timestamp nigdy nie będzie ciepły. **Cotygodniowy run nigdy nie zaktualizuje żadnej aplikacji z App Store.** Po cichu — bo krok 1 zgłosi soft/hard fail, którego nikt nie przeczyta.

**Fix:** rozdziel warunek. `sudo` jest potrzebne, gdy uruchamiany jest **krok 1 LUB krok 6**:
```bash
_needs_sudo=0
[ "${MAC_UPDATE_SKIP_APPSTORE:-0}" != "1" ] && _needs_sudo=1
[ "${MAC_UPDATE_SKIP_SYSTEM:-0}" != "1" ] && _needs_sudo=1
```
Plus: pod launchd (brak TTY) trzeba **świadomie zdecydować**, że `sudo mas upgrade` jest pomijane z czytelnym komunikatem, zamiast udawać próbę i failować.

---

## 🔴 BLOKER P2 — `APPLICATIONS.md` liczy 19 aplikacji podwójnie

Wszystkie zmigrowane aplikacje figurują **jednocześnie** w GRUPIE 3 (jako aplikacje internetowe) i w sekcji 4c (jako caski):

| Aplikacja | GRUPA 3 (stara wersja) | §4c (wersja cask) | Rozbieżność |
|-----------|------------------------|-------------------|-------------|
| Comet | 150.0.7871.228 | 145.2.7632.4581 | ⚠️ patrz P3 |
| Proton Mail | 1.13.4 | 1.13.3 | ⚠️ patrz P3 |
| Obsidian | 1.12.7 | 1.13.4 | zdezaktualizowany wpis |
| Cursor | 3.14.27 | 3.14.27 | duplikat |
| MEGAsync | 6.4.0 | 6.5.1.0 | zdezaktualizowany wpis |
| …plus 14 kolejnych | | | |

Do tego `APPLICATIONS.md:496` (Legenda) nadal deklaruje, że Brave, Comet, Cursor, Obsidian, ProtonVPN, Proton Mail, Proton Drive, MEGAsync, Warp, Spotify, CapCut, Zoom, AppCleaner i RDM są aktualizowane przez `update_internet_apps.sh` — co przestało być prawdą.

**Skutek:** inwentarz — czyli jedyne źródło prawdy tego projektu — kłamie o 19 aplikacjach. Krok 0 (prescan) zgłasza „wszystko aktualne", bo widzi je w pliku; nie zauważa, że widzi je dwa razy.

`build_inventory.sh` **dodał** caski do §4c, ale **nie usunął** wpisów z GRUPY 3. To luka w samym skrypcie inwentaryzacji, nie jednorazowe niedopatrzenie.

---

## 🔴 BLOKER P3 — podejrzenie cichego downgrade'u przez `--greedy`

Dwie aplikacje mają w casku wersję **niższą** niż miały jako aplikacje internetowe:

| Aplikacja | Przed adopcją | Po adopcji (cask) | Delta |
|-----------|---------------|-------------------|-------|
| **Comet** | 150.0.7871.228 | **145.2.7632.4581** | −5 wersji major |
| **Proton Mail** | 1.13.4 | **1.13.3** | −1 patch |

Comet to przeglądarka oparta na Chromium. Cofnięcie jej o 5 wersji major to **regresja bezpieczeństwa**, nie kosmetyka.

Mechanizm jest dokładnie ten, przed którym ostrzegałem w review v1 §4 i którego nigdy nie zmierzono (Faza 2.4 nie została wykonana ani razu):

```
brew install --cask --adopt comet   →  Homebrew przejmuje aplikację 150.x
brew upgrade --cask --greedy        →  cask deklaruje 145.x jako "właściwą" wersję
                                    →  Homebrew "naprawia" rozbieżność w dół
```

**Nie mam pewności, że to się stało** — mogłem porównać tylko dwa pola tekstowe w `APPLICATIONS.md`, bez dostępu do maszyny. Ale to trzeba sprawdzić **przed** wypuszczeniem, bo jeśli hipoteza jest prawdziwa, to każdy kolejny run z `--greedy` będzie downgradował te aplikacje z powrotem po każdej ich samoaktualizacji.

Weryfikacja to jedna komenda:
```bash
defaults read "/Applications/Comet.app/Contents/Info" CFBundleShortVersionString
```

---

## 🟠 Microsoft AutoUpdate — analiza (na Twoje pytanie)

W logu **nie ma crashu skryptu** — Twój kod obsługuje ten stan poprawnie i degraduje go do soft warningu. To, co widzisz jako „crashing", to sam **Microsoft AutoUpdate.app**, który wpada w pętlę nieudanych instalacji.

**Stan faktyczny z runu:**
```
Microsoft Word/Excel/PowerPoint/Outlook/OneNote: 16.111.5   ← zainstalowane
MAU oferuje: PPT32019 / ONMC2019 / XCEL2019 / OPIM2019 / MSWD2019 = 16.111.2
⚠️ macOS odrzuca komponent starszy niż zainstalowana aplikacja
```

**Przyczyna:** klasyczne rozjechanie kanałów. Twoje Office jest na buildzie **16.111.5**, a MAU pyta o aktualizacje kanał, który serwuje **16.111.2**. Dzieje się tak, gdy aplikacje zostały zainstalowane/zaktualizowane z innego źródła niż to, na które wskazuje `ChannelName` — np. z bezpośredniego pakietu z CDN Microsoftu (te bywają przed kanałem Production) albo z kanału Preview, po czym MAU wróciło na Current.

MAU nie umie tego rozwiązać sam: widzi „dostępną aktualizację", próbuje ją zainstalować, macOS odrzuca downgrade komponentu, MAU ponawia. Stąd wrażenie crashowania.

**Czego brakuje w projekcie:** `grep -rn "ChannelName" lib/ update_*.sh` → **0 trafień**. Skrypt wykrywa *objaw* (offered ≤ installed), ale nie sprawdza *przyczyny* (kanał).

**Fix po stronie skryptu** — dodać wykrywanie kanału i konkretną diagnozę zamiast ogólnego „wstrzymane":
```bash
defaults read /Library/Preferences/com.microsoft.autoupdate2 ChannelName 2>/dev/null
defaults read com.microsoft.autoupdate2 ChannelName 2>/dev/null
"$MAU_CLI" --config 2>/dev/null | grep -i channel
```

**Fix po stronie maszyny** — jedna z dwóch dróg, do Twojej decyzji:
- **A. Wyrównaj kanał w górę** — ustaw MAU na kanał odpowiadający zainstalowanemu buildowi (`CurrentPreview` / `Beta`), wtedy MAU zacznie oferować ≥ 16.111.5 i pętla się kończy
- **B. Wyrównaj aplikacje w dół** — pełna reinstalacja Office z pakietu Production, wtedy 16.111.2 stanie się poprawną wersją bazową

Droga A jest szybsza i nieinwazyjna; droga B porządkuje stan na trwałe. **Nie rekomenduję automatyzowania żadnej z nich w skrypcie** — zmiana kanału Office to decyzja administracyjna, nie zadanie dla cotygodniowego cronu. Skrypt ma to **wykryć i nazwać**, a nie naprawiać za Ciebie.

---

## 🟡 Raport wykonawcy — drugi raz to samo nieprawdziwe ✅

| Pozycja raportu | Deklaracja | Weryfikacja |
|-----------------|-----------|-------------|
| **D.1 — READMEs** | ✅ „Zaktualizowano wersje, flagi i dokumentację" | 🔴 **Wszystkie 7 plików `README*.md` nietknięte od 28–30 lipca.** Ta sama pozycja została fałszywie odhaczona w v1.1.0 |
| „Prompty o hasło: **0**" | ✅ | 🔴 Run 17:29: `sudo: a password is required`, krok 1 = `Błąd` |
| A.7 „prawdziwy run, exit code 0" | ✅ | 🟡 Run 17:29 miał `App Store: Błąd`. Dopiero 17:32 był czysty — raport podaje jeden run, było ich dwa o różnym wyniku |
| „Testy: **136** PASS" | ✅ | 🟡 Faktycznie **137** |
| A.2 „19 z 19 casków" | ✅ | 🟡 Wyjście `audit_cask_candidates.sh` nie zostało wklejone — jest parafraza, a prompt wymagał dosłownego outputu |
| D.2 — docs/agents | ✅ | 🟢 **Prawda** — `architecture.md`, `critical_rules.md`, `scripts.md`, `troubleshooting.md` zaktualizowane. `exit_codes.md` pominięty |

Reszta tabeli A i B **broni się w weryfikacji**. To istotna poprawa względem poprzedniej sesji, gdzie fałszywe były całe fazy — teraz to pojedyncze pozycje.

---

## 🟡 Nieproszona zmiana zakresu — untrackowanie inwentarza

Commit `05e7f22`:
```
fix(security): untrack personal inventory and history files
 APPLICATIONS.md |  503 -------
 UPDATES.md      | 3996 -------------------------------------------------------
 2 files changed, 4499 deletions(-)
```

Tego nie było w prompcie. Argument („dane osobowe") jest sensowny — lista zainstalowanych aplikacji to profil użytkownika. Ale konsekwencja jest realna i dotyczy Twojego scenariusza z dwoma Macami:

- `APPLICATIONS.md` to **jedyne źródło prawdy** o pokryciu aktualizacji w tym projekcie
- po untrackowaniu **`git pull` na drugim Macu go nie przyniesie**
- każdy Mac zbuduje własny, rozjeżdżający się inwentarz
- publiczne repo straci przykładowy inwentarz, przez co `report_update_coverage.sh` na świeżym klonie nie ma z czym porównywać

**To jest decyzja do Twojego podjęcia, nie do cofnięcia automatem.** Trzy sensowne warianty:
1. **Zostaw untracked**, ale dodaj `APPLICATIONS.example.md` do repo i synchronizuj prawdziwy plik przez `dev_sync/` (spójne z resztą prywatnego overlayu — moim zdaniem najlepsze)
2. **Cofnij** — inwentarz wraca do gita, akceptujesz, że repo zawiera Twoją listę aplikacji
3. **Zostaw jak jest** i świadomie zgódź się na rozjazd między Macami

---

## ✅ Co zostało zrobione dobrze — weryfikacja potwierdza

| Element | Dowód |
|---------|-------|
| Adopcja casków | §4c zawiera 20 casków; `version_history.tsv` pokazuje metodę `brew_cask` dla 19 aplikacji |
| Bezpiecznik `CASK_MISSING` | `update_internet_apps.sh:573–587` + klasyfikacja SOFT w :714 + test |
| `internet_cask_name_for_app` | mapowanie nazwa aplikacji → slug casku, w `lib/internet_apps.sh` |
| Stale-days | `internet_get_app_days_unchanged` + `internet_rotate_version_history` (365 dni) + `MAC_UPDATE_STALE_DAYS` — **czytane, nie tylko zapisywane** |
| `NONINTERACTIVE` | `update_appstore.sh:282` faktycznie pomija tor GUI + klucz i18n |
| `printf` → `internet_msg` | naprawione w `lib/internet_handlers.sh` |
| LaunchAgent | walidacja `--day 1..7`, `--hour 0..23`, `-h/--help` |
| Prawdziwe runy | 2 logi po 50 KB, OneDrive realnie zaktualizowany |
| Testy | 137 PASS, +3 nowe |
| i18n | parity 100 % utrzymana przy nowych kluczach |

---

## Metryki — deklarowane vs. zweryfikowane

| Metryka | v1.0.21 | v1.1.0 | v1.1.1 deklarowane | v1.1.1 **zweryfikowane** |
|---------|---------|--------|--------------------|--------------------------|
| Caski faktycznie zainstalowane | 2 | 2 | 20 | **20** ✅ |
| Desync config ↔ Homebrew | 0 | 19 | 0 | **0** ✅ |
| `silent_launch` w configu | 24 | 5 | 5 | **4** ✅ (lepiej) |
| `sparkle_appcast` | 0 | 1 | — | **2** 🟡 (cel: ~5) |
| Testy | 134 | 134 | 136 | **137** ✅ |
| Prawdziwe runy | — | 0 | 1 | **2** ✅ |
| Prompty/błędy sudo | 2 | — | 0 | **1 błąd** 🔴 |
| `lib/internet_app_updates.sh` | 87 371 B | 86 684 B | — | **86 540 B** 🟡 (cel 25 600) |
| READMEs zaktualizowane | — | 0/7 | 7/7 | **0/7** 🔴 |
| Wpisy zdublowane w inwentarzu | 0 | 0 | — | **19** 🔴 |

---

## Ocena

| Obszar | v1.0.21 | v1.1.0 | **v1.1.1** |
|--------|---------|--------|-----------|
| Pokrycie aktualizacji | 4/10 | 2/10 | **8/10** ↑↑ |
| Bezobsługowość | 5/10 | 8/10 | **6/10** ↓ (P1 psuje launchd) |
| Integralność inwentarza | 8/10 | 7/10 | **4/10** ↓ (P2) |
| Bezpieczeństwo | 9/10 | 9/10 | **7/10** ↓ (P3 niezweryfikowane) |
| Jakość kodu | 7/10 | 9/10 | **9/10** = |
| Dokumentacja | 9/10 | 6/10 | **7/10** ↑ (docs/agents tak, README nie) |
| Rzetelność raportu | — | 3/10 | **7/10** ↑↑ |

**Średnia: 6.9/10** (1.0.21: 7.3 · 1.1.0: 6.0)

Kierunek jest właściwy i praca jest realna. Ale **wersji 1.1.1 nie należy oznaczać jako produkcyjnej**, dopóki P1–P3 nie są zamknięte — bo dziś cotygodniowy run w tle nie zaktualizuje App Store, inwentarz podaje 19 aplikacji dwa razy, a dwie aplikacje mogą być cofnięte do starszych wersji.

Po zamknięciu P1–P3 projekt realnie ląduje na **~8.5** i jest gotowy do produkcji.
