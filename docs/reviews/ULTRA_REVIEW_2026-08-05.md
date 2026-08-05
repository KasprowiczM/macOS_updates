# ULTRA REVIEW — macOS_updates v1.0.21
**Data:** 2026-08-05 · **Log bazowy:** `logs/update_all_20260805_113635.log` · **Autor:** Claude (Opus)

---

## TL;DR — 5 rzeczy do zrobienia w tej kolejności

| # | Problem | Wpływ | Czas naprawy |
|---|---------|-------|--------------|
| 1 | **Touch ID nie działa na drugim Macu** — `/etc/pam.d/` nie jest w repo | Hasło przy każdym runie | 2 min (skrypt gotowy) |
| 2 | **Brak sudo keep-alive** — cache wygasa po 5 min, a runy trwają do 52 min | Hasło **w środku** runu | 30 min |
| 3 | **BUG: stdout pollution w `internet_handler_silent_launch`** — psuje status 19 aplikacji | Fałszywe raporty + martwy kod | 1 h |
| 4 | **24/45 aplikacji = „uruchomiony, niezweryfikowany"** | Nie wiesz czy się zaktualizowały | 1–2 dni |
| 5 | Brak harmonogramu (launchd) | Musisz pamiętać żeby uruchomić | 2 h |

---

## 1. Weryfikacja ostatniego runu

**Wynik:** `AKTUALIZACJA ZAKOŃCZONA Z OSTRZEŻENIAMI`, 2 min 58 s, exit ≠ hard fail.

```
0. Scan new apps:    OK        — APPLICATIONS.md aktualny, 0 zmian
1. App Store:        OK        — 14 apps, 0 outdated
2. Native CLI + npm: OK        — 7 pakietów sprawdzonych, wszystkie aktualne
3. Homebrew:         OK        — 1 upgrade (cffi 2.1.0→2.1.1), cache -90 MB
4. Internet apps:    WARNING   — Microsoft AutoUpdate zablokowany
5. Inventory:        OK        — 6 zmian wersji zapisanych
6. macOS System:     OK        — 26.6 (25G72), brak aktualizacji
```

### Co faktycznie zadziałało dobrze
- Pipeline nie wywalił się ani razu, severity contract (0/10/1) zadziałał zgodnie z projektem
- Soft-fail w kroku 4 **nie zablokował** kroku 6 — to była poprawna decyzja architektoniczna z 2026-07-26
- Rotacja logów, session dir, snapshoty przed/po — działają
- Wykrywanie `mas account` broken na macOS 26.x z fallbackiem na `mas list` — dobra robota

### Co wymaga uwagi

**a) Dwa interaktywne prompty w logu**
```
Czy chcesz uruchomić obie aktualizacje? [T/n]:
Czy chcesz zaktualizować wszystkie pakiety? [T/n]:
```
Uruchamiasz bez `-y`. Flaga **istnieje** (`lib/cli.sh:33`) i eksportuje się do dzieci. Od teraz zawsze:
```bash
bash update_all.sh -y
```

**b) Microsoft AutoUpdate — zablokowany po stronie Microsoftu, nie Twojej**
```
PPT32019: Microsoft oferuje 16.111.2, ale zainstalowano 16.111.5
```
MAU serwuje **starszą** wersję niż zainstalowana. To błąd kanału dystrybucji Microsoftu. Twój skrypt wykrył to poprawnie i nie próbował downgrade'u — to jest właściwe zachowanie. Nie ma tu nic do naprawy poza monitoringiem: warto dodać licznik dni („zablokowane od X dni") i eskalację do WARN po np. 30 dniach.

**c) 24 z 45 aplikacji kończy jako „⏳ Uruchomiony (niezweryfikowany)"** — to sedno problemu z pkt. 4 poniżej.

---

## 2. Dlaczego na drugim Macu wciąż wpisujesz hasło (a nie palec)

### Przyczyna #1 — konfiguracja Touch ID nigdy nie była w repo

Przeszukałem cały projekt:
```bash
grep -rn "pam_tid\|sudo_local\|TouchID" --include="*.sh" --include="*.md" .
# → 0 wyników
```

Touch ID dla `sudo` mieszka w **`/etc/pam.d/sudo_local`** — pliku należącym do `root:wheel`, poza katalogiem projektu. `git pull` **nigdy** go nie przeniesie. Na pierwszym Macu skonfigurowałeś to ręcznie kiedyś w przeszłości; drugi Mac o tym nie wie.

**To nie jest bug w projekcie — to brakujący krok bootstrapu per-maszyna.**

Naprawiłem to. Gotowy skrypt: **`scripts/setup_touchid_sudo.sh`**

```bash
# Na drugim Macu:
bash scripts/setup_touchid_sudo.sh --check     # diagnoza
bash scripts/setup_touchid_sudo.sh             # naprawa (1× hasło)

# Test:
sudo -k && sudo true      # powinien pokazać prompt Touch ID
```

Skrypt:
- pisze do `/etc/pam.d/sudo_local` na macOS 14+ → **przeżywa aktualizacje systemu** (Apple dodało ten plik w Sonomie właśnie po to)
- na macOS 13 patchuje `/etc/pam.d/sudo` z backupem i ostrzeżeniem, że OS to nadpisze
- automatycznie wykrywa i podpina `pam_reattach`, jeśli masz go z Homebrew → Touch ID działa też w tmux
- **nie dotyka `/etc/sudoers`** i nie nadaje sudo bez hasła
- jest idempotentny, ma `--check` i `--uninstall`

### Przyczyna #2 — brak sudo keep-alive (to gryzie też pierwszego Maca)

`update_all.sh:194` robi jednorazowe `sudo -v`. Domyślny `timestamp_timeout` w sudo to **5 minut**. Twoje runy:

| Log | Czas trwania |
|-----|--------------|
| 2026-07-28 14:42 | **52 min 39 s** |
| 2026-07-22 22:45 | 19 min 2 s |
| 2026-07-18 08:23 | 14 min 9 s |
| 2026-07-30 14:14 | 12 min 18 s |

Krok 6 (`sudo softwareupdate -ia -R`) startuje **na końcu**. Cache dawno wygasł → sudo pyta ponownie, w środku runu, często gdy już odszedłeś od komputera.

**Fix — dodaj do `update_all.sh` tuż po `sudo -v` (linia ~196):**

```bash
# Keep the sudo timestamp warm for the whole run. Without this, a 15+ minute
# run outlives the default 5-minute timestamp_timeout and step 6 re-prompts.
SUDO_KEEPALIVE_PID=""
if [ "${MAC_UPDATE_SKIP_SYSTEM:-0}" != "1" ] && [ -t 0 ]; then
    if sudo -n true 2>/dev/null; then
        ( while true; do sudo -n true 2>/dev/null || exit; sleep 50; done ) &
        SUDO_KEEPALIVE_PID=$!
    fi
fi
```

i w `cleanup_session_dir()`:
```bash
[ -n "${SUDO_KEEPALIVE_PID:-}" ] && kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true
```

Alternatywa (mniej inwazyjna, per-maszyna): `/etc/sudoers.d/timestamp` z `Defaults timestamp_timeout=60`. Ale keep-alive jest czystszy — nie rozluźnia polityki bezpieczeństwa na stałe.

### Przyczyna #3 — ograniczenie Apple Silicon, którego nie obejdziesz

Ważne, żebyś wiedział: **na Apple Silicon `softwareupdate` dla aktualizacji systemu wymaga poświadczeń właściciela woluminu (volume owner) — nawet jako root.** `sudo` samo w sobie nie wystarcza; Apple celowo wymaga tu interakcji użytkownika. Jedyna droga do w pełni bezobsługowej aktualizacji macOS to komenda MDM.

**Wniosek praktyczny:** dla macOS zawsze zostanie moment uwierzytelnienia. Ale z Touch ID to jest **dotknięcie palca zamiast wpisywania hasła** — i to jest maksimum, co da się osiągnąć bez MDM. Twoje aplikacje (brew, npm, mas, internet apps) można natomiast doprowadzić do 100% bezobsługowości.

### Checklist Touch ID — gdyby dalej nie działało

| Objaw | Przyczyna | Fix |
|-------|-----------|-----|
| Brak promptu Touch ID w ogóle | brak `sudo_local` | `bash scripts/setup_touchid_sudo.sh` |
| Działa w Terminal, nie w tmux | Touch ID przypięty do sesji GUI | `brew install pam-reattach`, potem re-run skryptu |
| Zniknęło po aktualizacji macOS | patch w `/etc/pam.d/sudo` zamiast `sudo_local` | skrypt użyje `sudo_local` (macOS 14+) |
| Prompt przy **każdym** kroku | brak keep-alive | patch z Przyczyny #2 |
| Nie działa po SSH | oczekiwane — brak sensora | `ignore_ssh` już jest w konfiguracji |
| Nie działa po zamknięciu klapy / restarcie | Apple wymaga hasła po reboot | oczekiwane, raz na sesję |

---

## 3. Bugi znalezione w kodzie

### 🔴 BUG-1 — stdout pollution psuje status 19 aplikacji

**Plik:** `lib/internet_handlers.sh:10–27` (`internet_handler_silent_launch`) + `:92–124` (`internet_dispatch_silent_launch`)

`internet_handler_silent_launch()` zwraca status przez `echo`, ale **równocześnie drukuje na stdout** przez `print_info` / `print_step` / `print_warn`:

```bash
internet_handler_silent_launch() {
    ...
    print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$ver")"   # → stdout
    print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "$app")"    # → stdout
    ...
    echo "$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"                          # → miał być statusem
}
```

Wywoływana jest przez podstawienie komendy (`internet_handlers.sh:106`):
```bash
st="$(internet_handler_silent_launch "$app_display" "$launch_target" "$verify_hint" "$APP_PATH")"
```

**Efekt: cały output leci do `$st` zamiast na ekran.** Dowód wprost z Twojego logu:

Sekcja Brave — pusta:
```
╔════════════════════════════════════════════════╗
║  🦁 Brave Browser                               ║
╚════════════════════════════════════════════════╝
                                    ← nic
```

A w podsumowaniu — 4 linie wciśnięte w jedną komórkę tabeli:
```
  Brave Browser:                     ℹ️  Zainstalowana wersja: 151.1.93.129
  ▶  Uruchamiam Brave Browser w tle (ukryty) — ...
  ℹ️  Ręczna weryfikacja: Brave → Pomoc → O Brave Browser
⏳ Uruchomiony (niezweryfikowany)
```

**Dotknięte aplikacje (19 wywołań `internet_dispatch_silent_launch`):**
Brave, Claude, Comet, Antigravity, Antigravity IDE, Gemini, LM Studio, ProtonVPN, Proton Mail, MEGAsync, Proton Drive, Warp, Cursor, Ascendo, AppCleaner, Obsidian, Spotify, CapCut, Remote Desktop Manager.

Pozostałe 5 `silent_launch` (Atlas, ChatGPT/Codex, Perplexity, OpenCode, zoom.us) mają własne handlery i drukują poprawnie.

**Fix — przekieruj UI na stderr, zostaw stdout jako kanał zwrotny:**

```bash
internet_handler_silent_launch() {
    ...
    print_info "..." >&2
    print_step "..." >&2
    ...
    echo "$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"   # jedyne na stdout
}
```

**Lepszy fix (zalecany)** — pozbądź się podstawienia komendy w ogóle. Zamiast zwracać przez stdout, ustaw zmienną globalną:

```bash
internet_handler_silent_launch() {
    ...
    INTERNET_LAST_STATUS="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
}

# w internet_dispatch_silent_launch:
internet_handler_silent_launch "$app_display" "$launch_target" "$verify_hint" "$APP_PATH"
internet_handler_set_status "$status_var" "$INTERNET_LAST_STATUS"
```

To eliminuje klasę błędu na stałe — nie da się już zanieczyścić statusu przypadkowym `echo`.

**Test regresyjny do dodania w `run_tests.sh`:**
```bash
# Status musi być jednolinijkowy — pilnuje BUG-1
for v in $(grep -o 'STATUS_[A-Z0-9_]*' config/internet_app_methods.txt | sort -u); do
    : # w runtime: [ "$(printf '%s' "$st" | wc -l)" -eq 0 ] || fail
done
```

---

### 🔴 BUG-2 — adaptacyjny settle-loop to martwy kod (konsekwencja BUG-1)

**Plik:** `update_internet_apps.sh:467–472`

```bash
for status_var in STATUS_BRAVE STATUS_CLAUDE_APP ... ; do
    eval "st=\$$status_var"
    if [ "$st" = "$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED" ]; then   # ← nigdy prawda
        unverified_apps="$unverified_apps $status_var"
    fi
done
```

Lista zawiera **dokładnie te 19 aplikacji dotkniętych BUG-1**, więc `$st` nigdy nie równa się czystemu statusowi. `unverified_apps` zostaje puste → warunek `[ -n "$unverified_apps" ]` fałszywy → kod leci do `else`:

```bash
elif [ "$INTERNET_SETTLE" -gt 0 ]; then
    sleep "$INTERNET_SETTLE"     # ← zawsze ta gałąź, sztywne 15 s
fi
```

**Cała inteligentna logika polling-until-stable (do 3 stabilnych odczytów) nigdy się nie wykonała.** Po naprawie BUG-1 zacznie działać i skróci krok 4 — w Twoim logu krok 4 trwał 1 min 19 s, z czego 15 s to ten sleep (~19%).

---

### 🟡 BUG-3 — statusy `LAUNCHED_UNVERIFIED` nie wpływają na exit code

**Plik:** `update_internet_apps.sh:610–657`

To jest **udokumentowana decyzja projektowa** (severity contract w `update_all.sh:280–320`) i zgadzam się z nią — 24 self-updatery „uruchomione" to normalny zdrowy stan, nie awaria. Ale skutek uboczny: `OVERALL_EXIT=0` mimo że nie masz pojęcia, czy cokolwiek się zaktualizowało.

**Rekomendacja:** nie zmieniaj exit code. Zamiast tego wprowadź **trzeci wymiar raportowania** — świeżość:

```
  Spotify:      ⏳ uruchomiony · wersja bez zmian od 12 dni  ⚠️
  Obsidian:     ✅ 1.12.6 → 1.12.7 (potwierdzone porównaniem snapshotów)
```

Masz już `internet_before.txt` / `internet_after.txt` w session dir. Wystarczy je persystować między runami (np. `logs/version_history.tsv`) i liczyć „dni bez zmiany". To zamienia bezużyteczne „⏳" w sygnał, na który da się zareagować.

---

### 🟡 BUG-4 — `sudo -v` z wyciszonym stderr

**Plik:** `update_all.sh:194`
```bash
if ! sudo -v 2>/dev/null; then
```

`2>/dev/null` zjada komunikat PAM. Przy Touch ID prompt i tak idzie na `/dev/tty`, więc działa — ale przy błędzie (np. konto bez sudo, zła konfiguracja PAM) nie zobaczysz **dlaczego**. Zostaw stderr, a wycisz tylko przy `--json-summary`.

---

## 4. Pokrycie aktualizacji — jak dojść do „bez ręcznej interwencji"

### Stan faktyczny (z `config/internet_app_methods.txt`, 45 wpisów)

| Metoda | Ile | Weryfikacja wersji? | Ocena |
|--------|-----|---------------------|-------|
| `silent_launch` | **24** | ❌ nie | 🔴 „odpalone i nadzieja" |
| `github_dmg` | 6 | ✅ tak, z weryfikacją podpisu | 🟢 wzorzec do naśladowania |
| `msupdate` | 5 | ✅ tak | 🟢 (obecnie blokada Microsoftu) |
| `appstore_gui` | 3 | ⚠️ przez GUI AppleScript | 🟡 kruche |
| `keystone` | 2 | ⚠️ trigger, bez potwierdzenia | 🟡 |
| `manual` | 2 | ❌ | 🔴 IPMIView, DJI |
| `docker_cli` | 1 | ✅ | 🟢 |
| `brew_cask` | 1 | ✅ | 🟢 |
| `mau_fallback` | 1 | ⚠️ | 🟡 |

**53% aplikacji z internetu nie ma żadnej weryfikacji.** To jest liczba, którą trzeba zbić.

### Strategia — trzy poziomy, w kolejności opłacalności

#### Poziom 1 (największy zysk, najmniejszy koszt): migracja do Homebrew Cask

Homebrew cask daje: znaną wersję zdalną, weryfikację podpisu, atomową podmianę, rollback i **zero AppleScriptu**. Prawie wszystkie Twoje `silent_launch` aplikacje mają casks:

| Aplikacja | Prawdopodobny cask | Aplikacja | Prawdopodobny cask |
|-----------|--------------------|-----------|--------------------|
| Brave Browser | `brave-browser` | Warp | `warp` |
| Cursor | `cursor` | AppCleaner | `appcleaner` |
| Obsidian | `obsidian` | Spotify | `spotify` |
| LM Studio | `lm-studio` | CapCut | `capcut` |
| ProtonVPN | `protonvpn` | Claude | `claude` |
| Proton Mail | `proton-mail` | ChatGPT | `chatgpt` |
| Proton Drive | `proton-drive` | zoom.us | `zoom` |
| MEGAsync | `megasync` | RDM | `devolutions-remote-desktop-manager` |

Weryfikacja przed migracją:
```bash
for c in brave-browser cursor obsidian lm-studio protonvpn proton-mail \
         proton-drive megasync warp appcleaner spotify capcut claude chatgpt zoom; do
    printf '%-32s' "$c"
    brew info --cask "$c" >/dev/null 2>&1 && echo "✅ istnieje" || echo "❌ brak"
done
```

Migracja istniejącej instalacji bez reinstalacji od zera:
```bash
brew install --cask --adopt brave-browser    # --adopt przejmuje już zainstalowaną aplikację
```

**Dobra wiadomość: `update_brew.sh` już to obsługuje.** Linia 240 to `brew upgrade --cask --greedy`, a 130/260 to `brew outdated --cask --greedy`. Migracja aplikacji do casków **nie wymaga żadnych zmian w kodzie** — wystarczy `--adopt` i edycja `config/internet_app_methods.txt`.

⚠️ **Ale uwaga na skalowanie `--greedy`:** dziś masz tylko 2 caski (`blackhole-2ch`, `inkscape`), więc koszt jest zerowy. Po migracji ~15 aplikacji gołe `--greedy` zacznie łapać też caski z `version :latest` — te nie mają wersji do porównania, więc będą **pobierane i reinstalowane przy każdym runie**. To wydłuży krok 3 o minuty i zje transfer.

Decyzja do podjęcia po migracji: porównaj czasy `brew outdated --cask --greedy` vs `--greedy-auto-updates`. Jeśli różnica jest duża, przełącz się na `--greedy-auto-updates` (łapie `auto_updates true`, pomija `version :latest`) i obsłuż `version :latest` osobno, rzadziej — np. raz w tygodniu.

**Realistyczny efekt: 24 niezweryfikowanych → ok. 6–8.**

#### Poziom 2: prawdziwa weryfikacja Sparkle przez appcast

Dla aplikacji spoza Homebrew (Ascendo, Antigravity, Gemini, Comet, Atlas) — jeśli używają Sparkle, mają `SUFeedURL` w `Info.plist`. To jest **odpytywalny endpoint**, nie zgadywanka:

```bash
# lib/internet_handlers.sh — nowa metoda: sparkle_appcast
internet_handler_sparkle_check() {
    local app_path="$1" feed remote local_ver
    feed="$(defaults read "$app_path/Contents/Info" SUFeedURL 2>/dev/null)"
    [ -n "$feed" ] || return 1

    remote="$(curl -fsSL --max-time 15 "$feed" 2>/dev/null \
        | grep -o 'sparkle:shortVersionString="[^"]*"' \
        | head -1 | cut -d'"' -f2)"
    [ -n "$remote" ] || return 1

    local_ver="$(app_version "$app_path")"
    if [ "$local_ver" = "$remote" ]; then
        echo "$L_INTERNET_STATUS_UP_TO_DATE"      # ✅ realna weryfikacja
    else
        echo "outdated:$local_ver→$remote"        # ⚠️ konkretny sygnał
    fi
}
```

Szybki audyt, które aplikacje to obsługują:
```bash
for app in /Applications/*.app; do
    feed="$(defaults read "$app/Contents/Info" SUFeedURL 2>/dev/null)"
    [ -n "$feed" ] && printf '%-40s %s\n' "$(basename "$app")" "$feed"
done
```

**To jest największy pojedynczy skok jakości w całym projekcie.** Zamienia „⏳ uruchomiony" na „✅ 1.12.7 = 1.12.7, potwierdzone".

#### Poziom 3: Electron / Squirrel.Mac

Apps typu Cursor, Warp, Antigravity używają `electron-updater`. Feed URL siedzi zwykle w `Contents/Resources/app-update.yml`. Ten sam wzorzec co wyżej. Warto zrobić dopiero po Poziomie 1 i 2 — to długi ogon.

### Aplikacje, które zostaną ręczne (i to jest OK)

| App | Dlaczego | Co zrobić |
|-----|----------|-----------|
| IPMIView | Supermicro, brak API, brak cask | Zostaw jako `manual`, dodaj przypomnienie co 90 dni |
| DJI Assistant 2 | brak auto-updatera, wersja nieznana | jw. |
| UniFi, WiFiman, Picsart | apps iPadOS na Apple Silicon — `mas` ich nie widzi | Tor 2 GUI to jedyna droga; zaakceptuj |

---

## 5. Research — kto robi to najlepiej i czego się od nich nauczyć

### 🥇 Installomator — złoty standard w świecie zarządzania flotą Mac

Open-source, ~1000 obsługiwanych aplikacji, używany przez Jamf/Intune/Mosyle. **Kluczowa różnica względem Twojego projektu:** Installomator zawsze *najpierw pobiera wersję zdalną z API producenta, porównuje z lokalną, i dopiero potem instaluje.* Nigdy nie „odpala aplikacji i ma nadzieję".

Do podprowadzenia:
- **Deklaratywne labele zamiast kodu per aplikacja.** Jeden wpis = nazwa, typ, URL, sposób pobrania wersji. Ty masz 87 KB `internet_app_updates.sh` z ręcznym kodem na aplikację — Installomator ma jedną tabelę. Twój `config/internet_app_methods.txt` już idzie w dobrą stronę; dociągnij tam URL-e i regexy wersji, a `lib/` zredukujesz o rzędy wielkości.
- **`BLOCKING_PROCESS_ACTION`** — kontrolowane zachowanie gdy aplikacja jest uruchomiona (prompt / kill / odłóż). U Ciebie tego brakuje: podmiana bundla działającej aplikacji to proszenie się o kłopoty.
- **Wymuszona weryfikacja Team ID** przed instalacją. Ty to masz w `verify_replacement_identity()` — dobra robota, to jest na poziomie Installomatora.

### 🥈 Topgrade — najbliższy odpowiednik Twojego `update_all.sh`

Rust, wykrywa wszystkie zainstalowane menedżery pakietów i uruchamia je po kolei: brew, mas, npm, pip, cargo, rustup, VS Code extensions, App Store, macOS. Dokładnie Twój use case.

Do podprowadzenia:
- **Plik konfiguracyjny TOML** z `[misc] assume_yes = true`, `disable = [...]`, `skip_notify`. Ty masz `.mac_update_prefs` — rozbuduj go do pełnej konfiguracji zamiast 20 zmiennych `MAC_UPDATE_*`.
- **`--only` / `--disable`** per krok. Masz `--skip-*`, ale brakuje odwrotności (`--only brew`).
- **Podsumowanie z kolorowym statusem per menedżer na końcu** — masz to, i lepiej niż topgrade.

**Szczerze:** dla developerskiego Maca kombinacja `brew upgrade --cask` + `mas upgrade` + topgrade jest uznawana za mocniejszą niż komercyjny MacUpdater. Twój projekt robi to samo, ale z lepszym raportowaniem i i18n — pod warunkiem, że przejdziesz na cask tam, gdzie się da.

### 🥉 Pozostałe warte podejrzenia

| Narzędzie | Co robi lepiej | Co ukraść |
|-----------|----------------|-----------|
| **Patchomator** | wykrywa zainstalowane aplikacje i mapuje na labele Installomatora | auto-generowanie configu ze skanu `/Applications` — masz krok 0, dociągnij mapowanie na metody |
| **`super` (Macjutsu)** | najlepszy w klasie wrapper na `softwareupdate` z obsługą deferral | logika „ile razy odłożono, kiedy wymusić" |
| **Nudge** | nie aktualizuje — *przekonuje użytkownika* | nic dla Ciebie (single-user), ale wzorzec eskalacji WARN po N dniach jest dobry |
| **MacUpdater (komercyjny)** | baza ~10 000 aplikacji z wersjami | pokazuje, że baza wersji to główna wartość — Twój `config/` powinien nią zostać |

### Czego **nikt** nie rozwiązał (i Ty też nie rozwiążesz)

Bezobsługowa aktualizacja macOS na Apple Silicon bez MDM. Wymaganie volume owner jest twarde. Wszyscy powyżej albo używają MDM, albo proszą użytkownika. **Touch ID to najlepsza możliwa odpowiedź w Twoim scenariuszu.**

---

## 6. Roadmap — konkretna kolejność prac

### Faza 0 — dziś, 15 minut
```bash
# 1. Touch ID na obu Macach
bash scripts/setup_touchid_sudo.sh
bash scripts/setup_touchid_sudo.sh --check

# 2. Od teraz zawsze z -y
echo "alias upd='cd ~/Dev_Env/macOS_updates && bash update_all.sh -y'" >> ~/.zshrc
```

### Faza 1 — ten tydzień
- [ ] sudo keep-alive (patch z §2) — koniec z promptem w środku runu
- [ ] Fix BUG-1: `>&2` w `internet_handler_silent_launch` — odblokowuje BUG-2 za darmo
- [ ] Test regresyjny „status musi być jednolinijkowy" w `run_tests.sh`
- [ ] Usuń `2>/dev/null` z `sudo -v` (BUG-4)

**Efekt: run bez promptów, poprawne raporty, krok 4 szybszy o ~15 s.**

### Faza 2 — ten miesiąc
- [ ] Audyt cask: uruchom pętlę `brew info --cask` z §4
- [ ] Migracja partiami po 5 aplikacji przez `brew install --cask --adopt`
- [ ] Zaktualizuj `config/internet_app_methods.txt`: `silent_launch` → `brew_cask` (kod `update_brew.sh` już gotowy — nic nie zmieniasz)
- [ ] Zmierz czas kroku 3 po migracji; jeśli urósł — rozważ `--greedy-auto-updates`

**Efekt: z 24 niezweryfikowanych do ~8.**

### Faza 3 — kwartał
- [ ] Metoda `sparkle_appcast` (kod w §4, Poziom 2)
- [ ] Historia wersji `logs/version_history.tsv` + „dni bez zmiany" (§3, BUG-3)
- [ ] LaunchAgent — cotygodniowy run w tle:

```xml
<!-- ~/Library/LaunchAgents/com.mk.macos-updates.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.mk.macos-updates</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/Users/mk/Dev_Env/macOS_updates/update_all.sh</string>
    <string>-y</string>
    <string>--skip-system</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>1</integer>
        <key>Hour</key><integer>9</integer>
        <key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key>
  <string>/Users/mk/Dev_Env/macOS_updates/logs/launchd.out</string>
  <key>StandardErrorPath</key>
  <string>/Users/mk/Dev_Env/macOS_updates/logs/launchd.err</string>
</dict></plist>
```

```bash
launchctl load -w ~/Library/LaunchAgents/com.mk.macos-updates.plist
```

⚠️ `--skip-system` jest tu celowe: krok 6 potrzebuje interakcji (volume owner), więc w tle by tylko wisiał. macOS zostaw na ręczny run z Touch ID.

### Faza 4 — refaktor długoterminowy
- [ ] Przenieś dane per aplikacja z `lib/internet_app_updates.sh` (87 KB!) do `config/` w stylu Installomatora — nazwa | metoda | feed URL | regex wersji | Team ID
- [ ] `lib/` zostaje z ~6 generycznymi handlerami zamiast 45 funkcji
- [ ] Auto-generowanie wpisów configu ze skanu `/Applications` (à la Patchomator)

---

## 7. Ocena projektu

| Obszar | Ocena | Komentarz |
|--------|-------|-----------|
| Architektura pipeline'u | **9/10** | Severity contract 0/10/1 z macierzą blokowania to bardzo dojrzały design. Komentarz przy nim jest lepszy niż w niejednym komercyjnym narzędziu. |
| Bezpieczeństwo | **9/10** | Weryfikacja podpisu + Team ID przed podmianą bundla, brak hardcoded paths, `mktemp` z prefiksem, 600 na logach. |
| Obserwowalność | **8/10** | Rotacja logów, session dir, dump snapshotów przy porażce, `--json-summary`. Brakuje tylko historii między runami. |
| **Pokrycie aktualizacji** | **4/10** | 53% aplikacji bez weryfikacji. To jest wąskie gardło całego projektu. |
| **Bezobsługowość** | **5/10** | Brak Touch ID bootstrapu, brak keep-alive, brak harmonogramu. Naprawialne w tydzień. |
| Jakość kodu | **7/10** | Bash 3.2 dyscyplina utrzymana, ale BUG-1 pokazuje, że wzorzec „echo jako return" jest kruchy. 87 KB w jednym libie to dług. |
| Dokumentacja | **9/10** | 7 języków, docs/agents/, CLAUDE.md z regułami — wzorowo. |

**Średnia ważona: 7.3/10.** Fundamenty są mocne — problem nie leży w inżynierii, tylko w tym, że połowa aplikacji jest obsługiwana strategią „odpal i licz na to". Faza 1+2 podnosi to do ~8.5 w miesiąc.

---

## Źródła

- [Six Colors — In macOS Sonoma, Touch ID for sudo can survive updates](https://sixcolors.com/post/2023/08/in-macos-sonoma-touch-id-for-sudo-can-survive-updates/)
- [fabianishere/pam_reattach — Touch ID support in tmux](https://github.com/fabianishere/pam_reattach)
- [Enable Touch ID for sudo on macOS That Survives Updates](https://andrewbaker.ninja/2023/10/26/macbook-osx-using-touch-id-fingerprints-to-enable-sudo/)
- [Homebrew Discussion #2923 — cask auto-update vs `upgrade --greedy`](https://github.com/orgs/Homebrew/discussions/2923)
- [Homebrew Discussion #73 — `auto_updates` vs `version :latest`](https://github.com/orgs/Homebrew/discussions/73)
- [Homebrew FAQ](https://docs.brew.sh/FAQ)
- [Installomator — official site](https://installomator.com/)
- [Secure Bash for macOS — Ch. 20: Installomator + Patchomator](https://bash.itsecurity.network/part3_real_world_projects/20_application_deployment_update_automation/)
- [AppAddict — Using Topgrade silently and automatically](https://appaddict.app/post/how-to-use-topgrade-silently-and-automatically-for-multiple-update-protocols-free)
- [Babo D's Corner — No more sudo with softwareupdate on Apple Silicon](https://babodee.wordpress.com/2020/11/11/no-more-sudo-with-softwareupdate-or-unattended-updates-on-macos-running-on-apple-silicon-2/)
- [Der Flounder — Granting Volume Owner status on Apple Silicon Macs](https://derflounder.wordpress.com/2023/03/10/granting-volume-owner-status-on-apple-silicon-macs/)
- [Sparkle — Documentation (appcast / SUFeedURL)](https://sparkle-project.org/documentation/)
