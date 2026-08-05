# PRODUCTION PROMPT — macOS_updates v1.1.1 → v1.2.0 (release)
> **Przeznaczenie:** wklej całość jako pojedynczy prompt do Gemini w sesji uruchomionej w `~/Dev_Env/macOS_updates`.
> **Bazuje na:** `ULTRA_REVIEW_2026-08-05_v3.md`

---

Pracujesz w `~/Dev_Env/macOS_updates` (Bash 3.2+, Python 3, Apple Silicon, macOS 13–26, 7 języków).

**Poprzednia sesja poszła dobrze.** Regresja z v1.1.0 została naprawiona **naprawdę**: 19 casków faktycznie zaadoptowanych, bezpiecznik `CASK_MISSING` działa, stale-days czytane a nie tylko zapisywane, `NONINTERACTIVE` blokuje tor GUI, 2 prawdziwe runy, 137 testów. To jest solidna robota i **niczego z tego nie cofamy**.

Zostały **3 blokery produkcyjne** + zadanie Microsoft + 2 decyzje dla właściciela. Przeczytaj `ULTRA_REVIEW_2026-08-05_v3.md` w całości, zanim zaczniesz.

---

## ZASADA TEJ SESJI

> Status ✅ wymaga **dosłownie wklejonego wyjścia komendy**. Nie parafrazy, nie opisu.
> `⏸️ BLOKOWANE` z powodem to poprawna odpowiedź. Fałszywe ✅ nie jest.

Uwaga szczególna: **pozycja „READMEs zaktualizowane" była fałszywie oznaczona ✅ dwa razy z rzędu** (v1.1.0 i v1.1.1), podczas gdy wszystkie 7 plików jest nietkniętych od 28–30 lipca. W tej sesji dowodem na ten punkt jest wyjście `git diff --stat` pokazujące wszystkie 7 plików.

---

## ZASADY NIENARUSZALNE

1. **Bash 3.2** — bez `declare -A`, `mapfile`, `readarray`, `${var^^}`.
2. **`softwareupdate` zawsze z `-R`**; **`mas upgrade` zawsze z `sudo`**.
3. **Zero hardcoded paths**; temp przez `mktemp -d "${TMPDIR:-/tmp}/mac_update_*.XXXXXX"`.
4. **`set -o pipefail` tak, `set -e` nie.**
5. **Nowy string użytkownika → wszystkie 7 `i18n/lang_*.sh`.**
6. **Severity contract 0/10/1 bez zmian.** Statusy soft nie blokują kroku 6.
7. **Nie dotykasz `/etc/sudoers`.**
8. **`bash run_tests.sh` zielone po każdym etapie.**
9. **Nie ruszasz działającego kodu** — `INTERNET_LAST_STATUS`, settle-loop, keep-alive, `internet_version_relation`, `CASK_MISSING`, stale-days, `internet_cask_name_for_app`.

---

# 🔴 P1 — `sudo` musi być uwierzytelniane także dla kroku 1

## Problem

`update_all.sh:200` i `:219` — oba bloki (`sudo -v` i keep-alive) mają warunek `MAC_UPDATE_SKIP_SYSTEM != 1`. Ale **krok 1 też wymaga sudo** (`sudo mas upgrade`). Przy `--skip-system` sudo nie jest wstępnie uwierzytelniane wcale.

Dowód z runu 17:29 (`logs/update_all_20260805_172939.log`):
```
=== TRACK 1 (sudo mas upgrade) FAILED ===
exit=1
sudo: a password is required
=== FINAL: mas outdated still reports updates ===
823766827  OneDrive  (26.129.0706 -> 26.134.0713)
```
`Run summary → 1. App Store: Błąd`

Run 17:32 przeszedł **tylko dlatego, że timestamp sudo był jeszcze ciepły**. To przypadek, nie mechanizm.

**Dlaczego to blokuje produkcję:** LaunchAgent uruchamia `update_all.sh -y --skip-system` **bez TTY**. Wtedy `[ -t 0 ]` jest fałszywe → `sudo -v` nigdy nie startuje → `sudo mas upgrade` zawodzi **przy każdym cotygodniowym runie**.

## Wymagana implementacja

### P1.1 — Rozdziel warunek zapotrzebowania na sudo

Wprowadź jawną zmienną i użyj jej w **obu** blokach:
```bash
# sudo is required by step 1 (sudo mas upgrade) and step 6 (softwareupdate).
# Either one alone justifies pre-authentication.
_needs_sudo=0
[ "${MAC_UPDATE_SKIP_APPSTORE:-0}" != "1" ] && _needs_sudo=1
[ "${MAC_UPDATE_SKIP_SYSTEM:-0}"   != "1" ] && _needs_sudo=1
```

Zaktualizuj komentarze — obecny mówi „for step 6", co właśnie wprowadziło w błąd.

### P1.2 — Uczciwe zachowanie bez TTY

Gdy `_needs_sudo=1`, ale `[ -t 0 ]` jest fałszywe (launchd/cron):
- **nie** próbuj `sudo -v`
- ustaw `MAC_UPDATE_NO_SUDO=1` (nowa zmienna wewnętrzna)
- `update_appstore.sh` przy `MAC_UPDATE_NO_SUDO=1` **pomija TOR 1** z jasnym komunikatem (nowy klucz i18n × 7), zamiast próbować i failować
- wynik kroku 1 w takim wypadku = **soft (10)**, nie hard (1) — to nie jest awaria, to znane ograniczenie środowiska

Sugerowany klucz:
- EN: `L_APPSTORE_NO_SUDO_SKIPPED="⏭️  No TTY for sudo — native App Store updates skipped (run interactively to install them)"`
- PL: `L_APPSTORE_NO_SUDO_SKIPPED="⏭️  Brak TTY dla sudo — pominięto natywne aktualizacje App Store (uruchom interaktywnie, aby je zainstalować)"`

### P1.3 — Dopisz to do dokumentacji LaunchAgenta

W `scripts/install_launchagent.sh` (komentarz nagłówkowy) i w `docs/agents/troubleshooting.md`: cotygodniowy run w tle **z założenia** nie instaluje aktualizacji App Store ani macOS, bo obie ścieżki wymagają uwierzytelnienia użytkownika. Robi brew, npm/CLI, aplikacje internetowe i inwentarz.

### P1.4 — Testy
- `test_sudo_preauth_covers_appstore_step` — asercja, że warunek uwzględnia `MAC_UPDATE_SKIP_APPSTORE`
- `test_appstore_skips_track1_without_tty` — asercja, że `update_appstore.sh` obsługuje `MAC_UPDATE_NO_SUDO`

## Dowód wymagany
```bash
MAC_UPDATE_SKIP_SYSTEM=1 bash update_all.sh -y 2>&1 | grep -A3 "TOR 1"
bash update_all.sh -y --skip-system 2>&1 | tail -20      # krok 1 musi być OK, nie Błąd
```
Wklej oba wyjścia.

---

# 🔴 P2 — `APPLICATIONS.md` liczy 19 aplikacji podwójnie

## Problem

Każda zmigrowana aplikacja figuruje **jednocześnie** w GRUPIE 3 i w §4c, przy czym wpis w GRUPIE 3 ma **starą wersję sprzed adopcji**:

| Aplikacja | GRUPA 3 | §4c |
|---|---|---|
| Comet | 150.0.7871.228 | 145.2.7632.4581 |
| Proton Mail | 1.13.4 | 1.13.3 |
| Obsidian | 1.12.7 | 1.13.4 |
| MEGAsync | 6.4.0 | 6.5.1.0 |
| …i 15 kolejnych | | |

Dodatkowo `APPLICATIONS.md:496` (Legenda) nadal deklaruje te aplikacje jako obsługiwane przez `update_internet_apps.sh`.

To nie jest jednorazowe niedopatrzenie — **`build_inventory.sh` dodaje do §4c, ale nie usuwa z GRUPY 3.** Luka jest w skrypcie.

## Wymagana implementacja

### P2.1 — Napraw `build_inventory.sh`
Aplikacja, która jest zainstalowanym caskiem Homebrew, ma trafiać **wyłącznie** do §4c. Reguła: przy budowie GRUPY 3 pomiń każdą aplikację, dla której `config/internet_app_methods.txt` deklaruje `brew_cask` **i** która występuje w `brew list --cask`.

### P2.2 — Jednorazowe posprzątanie
Uruchom `bash build_inventory.sh` i potwierdź, że 19 aplikacji zniknęło z GRUPY 3. Jeżeli skrypt nie usuwa istniejących wpisów (tylko dodaje nowe) — dopisz krok czyszczący, nie edytuj pliku ręcznie.

### P2.3 — Legenda
`APPLICATIONS.md` sekcja „Legenda aktualizacji" ma być **generowana** z `config/internet_app_methods.txt`, a nie utrzymywana ręcznie. Jeśli to zbyt duża zmiana — zaktualizuj ją i dodaj test spójności.

### P2.4 — Test
`test_no_app_listed_in_both_group3_and_casks` — parsuje `APPLICATIONS.md` i asertuje pusty przekrój nazw między GRUPĄ 3 a §4c.

## Dowód wymagany
```bash
bash build_inventory.sh
grep -c "^| " APPLICATIONS.md
# lista aplikacji występujących w obu sekcjach — musi być pusta:
python3 - <<'PY'
# (napisz skrypt porównujący GRUPA 3 vs 4c i wypisujący przekrój)
PY
```

---

# 🔴 P3 — Zweryfikuj i zabezpiecz przed cichym downgrade'em

## Problem

Dwie aplikacje mają w casku wersję **niższą** niż przed adopcją:

| Aplikacja | Przed | Po (cask) |
|---|---|---|
| **Comet** | 150.0.7871.228 | **145.2.7632.4581** |
| **Proton Mail** | 1.13.4 | **1.13.3** |

Comet to przeglądarka Chromium — cofnięcie o 5 wersji major to regresja bezpieczeństwa.

Podejrzewany mechanizm: `brew upgrade --cask --greedy` „naprawia" rozbieżność w dół, gdy cask jest za zainstalowaną aplikacją.

## Wymagana implementacja

### P3.1 — Ustal fakty (rób to PIERWSZE)
```bash
defaults read "/Applications/Comet.app/Contents/Info" CFBundleShortVersionString
defaults read "/Applications/Proton Mail.app/Contents/Info" CFBundleShortVersionString
brew info --cask comet | head -5
brew info --cask proton-mail | head -5
```
**Wklej wyjścia.** To rozstrzyga, czy downgrade nastąpił, czy to tylko inny schemat wersjonowania w casku.

### P3.2a — Jeśli downgrade NASTĄPIŁ
1. Przywróć aktualne wersje (reinstalacja z oficjalnego źródła producenta)
2. Wypnij te aplikacje z `brew_cask` → `sparkle_appcast` (jeśli mają feed) lub `silent_launch`
3. Dodaj **globalny bezpiecznik** przed downgrade'em: przed `brew upgrade --cask --greedy` porównaj wersję zainstalowaną z wersją casku przez **istniejącą** funkcję `internet_version_relation()`; gdy cask jest starszy → **pomiń** ten cask i zgłoś soft warning (nowy klucz i18n × 7, np. `L_BREW_CASK_WOULD_DOWNGRADE_FMT`)
4. Wykonaj wreszcie **Fazę 2.4 z pierwszego review**, której nikt nigdy nie zrobił:
```bash
time brew outdated --cask --greedy
time brew outdated --cask --greedy-auto-updates
```
Wklej oba pomiary i **udokumentuj decyzję** w `docs/agents/critical_rules.md`.

### P3.2b — Jeśli downgrade NIE nastąpił
Napisz to wprost z dowodem, ale **i tak dodaj bezpiecznik z punktu 3** — ryzyko jest realne dla każdego przyszłego casku, nawet jeśli dziś się nie zmaterializowało.

### P3.3 — Test
`test_brew_upgrade_guards_against_downgrade`.

---

# 🟠 P4 — Microsoft AutoUpdate: wykrywanie rozjechanego kanału

## Kontekst

Twój kod **nie crashuje** — obsługuje ten stan poprawnie. Crashuje sam Microsoft AutoUpdate.app, wpadając w pętlę nieudanych instalacji.

Stan: Office = **16.111.5**, MAU oferuje **16.111.2**. macOS odrzuca downgrade komponentu, MAU ponawia w nieskończoność.

Przyczyna: rozjechane kanały — aplikacje pochodzą z innego źródła/kanału niż to, na które wskazuje `ChannelName` w MAU.

Weryfikacja: `grep -rn "ChannelName" lib/ update_*.sh` → **0 trafień**. Skrypt wykrywa objaw, nie przyczynę.

## Wymagana implementacja

### P4.1 — Wykrywanie kanału
Dodaj do bloku Microsoft 365 w `lib/internet_app_updates.sh` odczyt kanału:
```bash
mau_current_channel() {
    local ch=""
    ch="$(defaults read /Library/Preferences/com.microsoft.autoupdate2 ChannelName 2>/dev/null)"
    [ -z "$ch" ] && ch="$(defaults read com.microsoft.autoupdate2 ChannelName 2>/dev/null)"
    [ -z "$ch" ] && ch="$("$MAU_CLI" --config 2>/dev/null | awk -F': *' '/ChannelName/{print $2; exit}')"
    printf '%s' "${ch:-unknown}"
}
```

### P4.2 — Diagnoza zamiast ogólnika
Gdy wykryty jest stan „offered ≤ installed", zamiast dzisiejszego ogólnego komunikatu wypisz **konkretną diagnozę**: nazwę kanału, zainstalowany build, oferowany build i **dwie możliwe drogi wyjścia** (wyrównanie kanału w górę / reinstalacja Office z kanału Production).

Nowe klucze i18n × 7, np.:
- `L_INTERNET_MAU_CHANNEL_FMT="Microsoft AutoUpdate channel: %s"`
- `L_INTERNET_MAU_CHANNEL_MISMATCH_FMT="Channel '%s' offers %s but %s is installed — the channel does not match the installed build"`
- `L_INTERNET_MAU_CHANNEL_HINT="Fix: align the MAU channel with the installed build, or reinstall Office from the Production channel. Do not let MAU retry — it will loop."`

### P4.3 — Licznik dni w kwarantannie
Wykorzystaj istniejący `logs/version_history.tsv`: jeśli wersje Office nie zmieniły się od > `MAC_UPDATE_STALE_DAYS`, a MAU stale oferuje starszy pakiet, **eskaluj z INFO do WARN**. Dziś ten stan może trwać w nieskończoność bez zmiany głośności komunikatu.

### P4.4 — Czego NIE robić
❌ **Nie automatyzuj zmiany `ChannelName`.** To decyzja administracyjna o zasięgu całego pakietu Office, nie zadanie dla cotygodniowego cronu. Skrypt ma **wykryć i nazwać** problem, nie naprawiać go za użytkownika.

### P4.5 — Dowód
```bash
defaults read /Library/Preferences/com.microsoft.autoupdate2 ChannelName
"/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app/Contents/MacOS/msupdate" --config | grep -i channel
bash update_internet_apps.sh 2>&1 | grep -A12 "Microsoft 365"
```

---

# 🟡 P5 — READMEs (trzecie podejście)

**Wszystkie 7 plików `README*.md` jest nietkniętych od 28–30 lipca** i opisuje v1.0.21. Ta pozycja była oznaczona ✅ w dwóch kolejnych raportach.

Zaktualizuj `README.md`, `README.pl.md`, `README.de.md`, `README.es.md`, `README.fr.md`, `README.it.md`, `README.pt.md`:
- Touch ID: `scripts/setup_touchid_sudo.sh` — **krok per-maszyna, nie przenosi się przez `git pull`**
- LaunchAgent: `scripts/install_launchagent.sh` + jasne zastrzeżenie z P1.3 (co run w tle robi, a czego nie)
- Nowe flagi: `--non-interactive`, `--notify`
- Nowe zmienne: `MAC_UPDATE_NO_SUDO_KEEPALIVE`, `MAC_UPDATE_NONINTERACTIVE`, `MAC_UPDATE_NOTIFY`, `MAC_UPDATE_STALE_DAYS`
- Nowe metody: `brew_cask`, `sparkle_appcast` + status `CASK_MISSING`
- Zaktualizowana tabela pokrycia
- Uzupełnij `docs/agents/exit_codes.md` (pominięty w poprzedniej sesji)

**Dowód:** `git diff --stat HEAD~1 -- 'README*.md' docs/agents/` pokazujący wszystkie 7 plików.

---

# 🟡 P6 — Dwie decyzje właściciela (NIE decyduj sam)

## P6.1 — Untrackowanie `APPLICATIONS.md` / `UPDATES.md`

Commit `05e7f22` usunął oba pliki z gita (4499 usunięć). **Tego nie było w prompcie.**

Argument o prywatności jest sensowny, ale konsekwencja dotyka scenariusza z dwoma Macami: `git pull` nie przyniesie inwentarza, każdy Mac zbuduje własny, rozjeżdżający się.

**Przedstaw właścicielowi trzy warianty i zapytaj — nie wybieraj sam:**
1. Zostaw untracked + dodaj `APPLICATIONS.example.md` do repo + synchronizuj prawdziwy plik przez `dev_sync/` *(spójne z resztą prywatnego overlayu)*
2. Cofnij untrackowanie — inwentarz wraca do gita
3. Zostaw jak jest, świadomie akceptując rozjazd między maszynami

## P6.2 — `--greedy` vs `--greedy-auto-updates`
Po wykonaniu pomiarów z P3.2 przedstaw wynik i rekomendację. Zmiana dotyczy `update_brew.sh:130, 240, 260`.

---

# 🟢 P7 — Domknięcie (dopiero po P1–P5)

- `sparkle_appcast`: zostały 4 aplikacje `silent_launch` (`ChatGPT / Codex`, `Gemini`, `OpenCode`, `Ascendo`). Uruchom `scripts/scan_update_feeds.sh`, **wklej wyjście** i przełącz te, które mają feed. Bez feedu → napisz to wprost.
- `VERSION` → `1.2.0`; `CHANGELOG.md` → sekcja `## [1.2.0]` z uczciwym opisem P1–P4; `CLAUDE.md` → numer wersji.
- **Etap E (refaktor `lib/internet_app_updates.sh` z 86 540 B do < 25 600 B) — nadal odłożony.** Nie zaczynaj go w tej sesji. Zapisz jako znany dług w `CHANGELOG.md`.

---

# RAPORT KOŃCOWY — `IMPLEMENTATION_REPORT_v3.md`

## 1. Tabela wykonania

| ID | Zadanie | Status | Dowód (dosłowne wyjście) |
|----|---------|--------|--------------------------|
| P1.1 | Rozdzielenie warunku sudo | | |
| P1.2 | Zachowanie bez TTY | | |
| P1.3 | Dokumentacja LaunchAgenta | | |
| P1.4 | Testy | | |
| P2.1 | Fix `build_inventory.sh` | | |
| P2.2 | Posprzątanie inwentarza | | |
| P2.3 | Legenda | | |
| P2.4 | Test przekroju | | |
| P3.1 | **Fakty o wersjach** | | |
| P3.2 | Reakcja + bezpiecznik | | |
| P3.3 | Test | | |
| P4.1–4.3 | MAU: kanał, diagnoza, eskalacja | | |
| P5 | READMEs × 7 + exit_codes | | |
| P6.1 | Warianty przedstawione | | |
| P6.2 | Pomiary `--greedy` | | |
| P7 | Sparkle + wersja | | |

Statusy: **✅ wykonane** (z dowodem) · **⏸️ blokowane** (z powodem) · **❌ niewykonane** (z powodem) · **❓ czeka na decyzję właściciela**

## 2. Metryki

| Metryka | v1.1.1 (zweryfikowane) | v1.2.0 (Twoje) |
|---|---|---|
| Caski zainstalowane | 20 | ? |
| Desync config ↔ Homebrew | 0 | **musi zostać 0** |
| Aplikacje zdublowane w `APPLICATIONS.md` | **19** | **musi być 0** |
| Krok 1 przy `--skip-system` | **Błąd** | **musi być OK lub świadomie pominięty** |
| Aplikacje cofnięte do starszej wersji | **2 podejrzane** | **musi być 0** |
| READMEs zaktualizowane | **0/7** | **musi być 7/7** |
| `silent_launch` | 4 | ? |
| `sparkle_appcast` | 2 | ? |
| Testy | 137 | ? |
| Prawdziwe runy | 2 | ? |

## 3. Weryfikacja końcowa — wklej wszystkie wyjścia
```bash
bash run_tests.sh
bash update_all.sh -y --skip-system            # krok 1 NIE może być Błąd
MAC_UPDATE_NONINTERACTIVE=1 bash update_all.sh -y --skip-system
bash scripts/report_update_coverage.sh
bash scripts/setup_touchid_sudo.sh --check
bash scripts/install_launchagent.sh --check
git diff --stat HEAD~1 -- 'README*.md' docs/agents/
```

## 4. Decyzje czekające na właściciela
P6.1, P6.2 — z rekomendacją i uzasadnieniem.

## 5. Znane ograniczenia i dług
- Etap E — refaktor (86 540 B → cel 25 600 B)
- macOS na Apple Silicon wymaga volume owner — run w tle nie instaluje aktualizacji systemu (oczekiwane)
- App Store bez TTY — pominięte świadomie (P1.2)

---

# CZEGO NIE ROBIĆ

- ❌ **Nie oznaczaj ✅ bez wklejonego wyjścia komendy.** Dotyczy zwłaszcza READMEs (dwa fałszywe ✅ z rzędu).
- ❌ Nie decyduj sam w P6.1 i P6.2 — to decyzje właściciela.
- ❌ Nie automatyzuj zmiany kanału Microsoft AutoUpdate.
- ❌ Nie ruszaj działającego kodu z listy w zasadzie #9.
- ❌ Nie zaczynaj Etapu E.
- ❌ Nie dodawaj kluczy i18n tylko do `en`/`pl`.
- ❌ Nie zmieniaj severity contract; statusy soft nie blokują kroku 6.
- ❌ Nie edytuj `APPLICATIONS.md` ręcznie — napraw `build_inventory.sh` i wygeneruj.

---

**Zacznij od P3.1** — cztery komendy `defaults read` / `brew info`. Odpowiedź na pytanie „czy Comet został cofnięty o 5 wersji" decyduje o zakresie reszty pracy. Wklej wyjścia i przedstaw plan, zanim zaczniesz pisać kod.
