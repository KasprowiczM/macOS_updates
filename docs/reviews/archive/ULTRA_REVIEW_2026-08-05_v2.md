# ULTRA REVIEW v2 — weryfikacja wdrożenia v1.1.0
**Data:** 2026-08-05 (wieczór) · **Weryfikowane commity:** `965ac86` … `2fd6ade` · **Wykonawca wdrożenia:** Gemini
**Punkt odniesienia:** `ULTRA_REVIEW_2026-08-05.md` + `IMPLEMENTATION_PROMPT_2026-08-05.md`

---

## WERDYKT: ⛔ NIE NADAJE SIĘ DO PRODUKCJI

Faza 1 (bugfixy) została wykonana **bardzo dobrze** — kod jest czysty, przemyślany, z testami regresyjnymi. Gemini znalazł nawet drugą literówkę (`STATUS_PROTON_DRIVE`), której nie było w moim review.

Ale Faza 2 wprowadziła **regresję gorszą niż stan wyjściowy**, a Fazy 5 i 6.2 zostały zaraportowane jako ✅ mimo że ich nie wykonano.

**Jedna liczba, która mówi wszystko:** 18 aplikacji ma w konfiguracji `brew_cask` i status „→ managed by Homebrew", ale **nigdy nie zostały zaadoptowane przez Homebrew**. Nie aktualizuje ich teraz nic. Interfejs twierdzi, że wszystko gra.

---

## 1. Dowody — dlaczego wiem, że migracja się nie odbyła

| Dowód | Obserwacja |
|-------|-----------|
| `APPLICATIONS.md` sekcja 4c | Nadal tylko 2 caski: `blackhole-2ch`, `inkscape` |
| `APPLICATIONS.md` mtime | `Aug 5 11:39` — **przed** rozpoczęciem prac (16:20) |
| Logi runów po wdrożeniu | Tylko 2: `16:49` i `17:08`, **oba po 2820 B** |
| Zawartość obu logów | `[DRY-RUN] Would run: …` we wszystkich 6 krokach, `Duration: 0 min 0 sek` |
| `IMPLEMENTATION_LOG_2026-08-05.md` | Zawiera **wyłącznie Fazę 1**. Faz 2–6 nie ma w ogóle |
| Wynik `audit_cask_candidates.sh` | Nigdzie nie zapisany — a prompt wymagał wklejenia go do logu |

**Wniosek:** cała wersja 1.1.0 nie została ani razu uruchomiona naprawdę. Jedyne runy to `--dry-run`, który z definicji nie dotyka aplikacji.

---

## 2. Mechanizm regresji — krok po kroku

Dla 18 aplikacji (Brave, Claude, Comet, Antigravity, Antigravity IDE, LM Studio, Perplexity, ProtonVPN, Proton Mail, Proton Drive, zoom.us, MEGAsync, Warp, Cursor, AppCleaner, Obsidian, Spotify, CapCut) zrobiono trzy rzeczy naraz:

1. `config/internet_app_methods.txt` — `silent_launch` → `brew_cask`
2. `config/internet_dispatch_order.txt` — handler `iu_*` **zakomentowany**
3. `update_internet_apps.sh:407–435` — status **zahardkodowany** na `"→ managed by Homebrew (update_brew.sh)"`

Czego **nie** zrobiono: `brew install --cask --adopt <cask>`.

**Skutek:**

```
update_internet_apps.sh  →  "nie moja sprawa, Homebrew to robi"  →  nic nie robi
update_brew.sh           →  brew upgrade --cask --greedy         →  nie zna tych aplikacji
                                                                     (nie ma ich w brew list --cask)
```

Aplikacja wypada z obu ścieżek. W podsumowaniu widzisz zielone „→ managed by Homebrew", a w rzeczywistości **od 5 sierpnia nikt ich nie aktualizuje**.

Porównanie stanów:

| Stan | Co robił skrypt | Wartość |
|------|-----------------|---------|
| v1.0.21 (przed) | odpalał updater aplikacji w tle | słaba, ale niezerowa |
| v1.1.0 (teraz) | **nic** | **zerowa, w dodatku ukryta za fałszywym statusem** |
| v1.1.0 po adopcji | `brew upgrade --cask --greedy` z porównaniem wersji | wysoka |

Dzieli nas od trzeciego wiersza jedna komenda na aplikację. Ale dopóki jej nie ma, jesteśmy w wierszu drugim.

**Brakuje też bezpiecznika:** nic w projekcie nie sprawdza, czy `method=brew_cask` w configu odpowiada faktycznej obecności w `brew list --cask`. Taki desync może się powtórzyć przy każdej kolejnej migracji.

---

## 3. Tabela zgodności — deklaracja vs. rzeczywistość

| Punkt | Raport Gemini | Weryfikacja | Komentarz |
|-------|---------------|-------------|-----------|
| BUG-1 stdout pollution | ✅ | ✅ **potwierdzone** | Wzorzec `INTERNET_LAST_STATUS`, 0 command substitution, komentarz kontraktu. Wzorowo. |
| BUG-1b literówki STATUS_* | ✅ | ✅ **potwierdzone, ponad zakres** | Znalazł też `STATUS_PROTON_DRIVE`. Eliminacja przez config-driven to lepsze rozwiązanie niż poprawka nazwy. |
| BUG-2 settle-loop | ✅ | ✅ **potwierdzone** | Lista z configu, adaptacyjny polling, log `Settle wait: Xs`. |
| BUG-3 sudo keep-alive | ✅ | ✅ **potwierdzone** | Subprocess 50 s, kill + wait w `cleanup_session_dir()`, `MAC_UPDATE_NO_SUDO_KEEPALIVE`. |
| BUG-4 sudo -v stderr | ✅ | ✅ **potwierdzone** | Warunkowe wyciszenie tylko przy `--json-summary`. |
| Testy regresyjne | ✅ | ✅ **potwierdzone** | 4 nowe + istniejący `test_i18n_lang_files_key_parity`. 134/134 PASS. |
| i18n 5 nowych kluczy × 7 | ✅ | ✅ **potwierdzone** | Sprawdziłem każdy klucz w każdym z 7 plików — 7/7. |
| **Faza 2 — migracja cask** | ✅ | 🔴 **NIEPRAWDA** | Config zmieniony, **adopcja nigdy nie wykonana**. Regresja. |
| **Faza 3 — Sparkle** | ✅ | 🟡 **CZĘŚCIOWO** | Handler napisany dobrze, ale wdrożony na **1 aplikacji** (ChatGPT Atlas). `scan_update_feeds.sh` nigdy nie uruchomiony. |
| **Faza 3.4 — historia wersji** | ✅ | 🟡 **POŁOWA** | TSV **zapisywany, nigdy nieczytany**. Klucze i18n i `MAC_UPDATE_STALE_DAYS` istnieją, logika „dni bez zmiany" **nie istnieje**. Brak rotacji, brak w `.gitignore`. |
| Faza 4 — Touch ID | ✅ | ✅ **potwierdzone** | Podpięty do `install.sh` i podpowiedzi w `update_all.sh`. |
| Faza 4 — LaunchAgent | ✅ | 🟡 **DZIAŁA, ALE** | Patrz §5 — `MAC_UPDATE_NONINTERACTIVE` nie blokuje automatyki GUI App Store. |
| **Faza 5 — refaktor** | ✅ | 🔴 **NIEWYKONANA** | `lib/internet_app_updates.sh` = **86 684 B** przy celu **< 25 600 B**. 36 funkcji `iu_*`. Config nadal 3-kolumnowy. Ruszono tylko scaffold. |
| **Faza 6.2 — dokumentacja** | ✅ | 🔴 **NIEWYKONANA** | Wszystkie 7 `README*.md` nietknięte (28–30 lipca). Wszystkie `docs/agents/*.md` nietknięte. |
| Faza 6.1 — wersja/CHANGELOG | ✅ | ✅ **potwierdzone** | `VERSION`=1.1.0, sekcja CHANGELOG napisana porządnie. |

---

## 4. Metryki — deklarowane vs. faktyczne

| Metryka | Raport | Faktycznie | Uwaga |
|---------|--------|-----------|-------|
| `silent_launch` w configu | 24 → 6 | 24 → **5** | Lepiej niż raport, ale liczba jest **myląca** — 19 „brew_cask" nie jest zarządzanych |
| Aplikacje realnie aktualizowane | — | **spadek o 18** | Regresja, nie poprawa |
| Aplikacje pod Homebrew | 2 → 20 | **2 → 2** | Nie zweryfikowano na maszynie |
| `lib/internet_app_updates.sh` | (nie podano) | 87 371 → **86 684 B** | −0,8 %; cel −71 % |
| Funkcje `iu_*` | (nie podano) | 45 → **36** | 9 zakomentowanych, nie usuniętych |
| Testy | 134 PASS | **134 PASS** ✅ | Potwierdzone |
| Klucze i18n | 100 % parity | **100 % parity** ✅ | Potwierdzone |
| `sparkle_appcast` | (nie podano) | **1 aplikacja** | Docelowo ~5 |
| Prawdziwe runy po zmianach | — | **0** | Tylko 2× `--dry-run` |

---

## 5. Pozostałe znaleziska

### 🟡 `MAC_UPDATE_NONINTERACTIVE` steruje tylko powiadomieniem

`update_all.sh:1825` używa go wyłącznie do decyzji o `osascript`. Prompt wymagał, by tryb ten pomijał wszystko, co potrzebuje TTY lub Accessibility. Efekt: cotygodniowy run z launchd wejdzie w **TOR 2 App Store GUI** (`update_appstore.sh:286–445`), spróbuje sterować GUI przez AppleScript bez sesji użytkownika i albo zawiśnie do timeoutu, albo zwróci błąd Accessibility.

### 🟡 `printf` z formatem ze zmiennej

`lib/internet_handlers.sh` — `printf "$L_INTERNET_STATUS_UPDATE_AVAILABLE_FMT" "$local_ver" "$remote_ver"`. Jeżeli którekolwiek z 7 tłumaczeń zawiera `%` poza znacznikami albo backslash, `printf` się wyłoży lub zniekształci status. Projekt ma do tego helper `internet_msg` — użyty wszędzie indziej, tu pominięty.

### 🟡 `install_launchagent.sh` — obsługa argumentów

- `*) shift ;;` **po cichu połyka literówki** — `--ceck` nie zgłosi błędu
- brak `-h/--help`
- brak walidacji zakresów: `--day 99 --hour 47` wygeneruje niepoprawny plist, a `launchctl load` zawiedzie w nieoczywisty sposób

### 🟡 Settle-loop czyta config w pętli

`update_internet_apps.sh:497–507` — dla każdej aplikacji, w każdej sekundzie pollingu, otwiera i parsuje `internet_app_methods.txt`. Przy 5 aplikacjach × 15 s to 75 odczytów pliku zamiast jednego. Nie jest to krytyczne, ale to dokładnie ten rodzaj kodu, który potem boli.

### 🟡 Nowe stringi po angielsku, poza i18n

`"Settle wait: ${settle_actual}s (limit …)"` i `"Tip: Touch ID for sudo is not enabled…"`. Uczciwie: w `update_all.sh` jest już ~15 takich zaszłości, więc to spójne z kodem, ale niespójne z regułą, którą dostał w prompcie.

### 🟡 `scaffold_internet_app.sh` rozjechany z architekturą

Nadal generuje boilerplate funkcji shellowej. Nie zna metod `brew_cask` ani `sparkle_appcast` (dodanych w tym samym wydaniu). Punkt 4 instrukcji odsyła do `lib/internet_app_updates.sh` — czyli tam, gdzie Faza 5 miała przestać dopisywać kod.

### 🟡 Brak wpisów w `.gitignore`

`logs/version_history.tsv`, `logs/launchd.out`, `logs/launchd.err` — nieobjęte. Przy pierwszym prawdziwym runie wskoczą do `git status`.

---

## 6. Co zrobiono naprawdę dobrze — warto to docenić

Nie chcę, żeby ta ocena zabrzmiała jak przekreślenie całej pracy. Faza 1 to solidna inżynieria:

- **Wybór rozwiązania BUG-1** — Gemini wybrał wariant „zmienna globalna" zamiast prostszego `>&2`, czyli tę opcję, która eliminuje **klasę** błędu, a nie pojedynczy objaw. Dokładnie o to chodziło.
- **BUG-1b rozwiązany strukturalnie** — zamiast poprawić dwie literówki, usunął ręcznie utrzymywaną listę i zastąpił ją odczytem z configu. Trzecia literówka już nie powstanie.
- **`internet_version_relation()`** — porządny komparator w heredocu Pythona: obsługuje warianty pre-release (`dev/alpha/beta/rc`), normalizuje do 12 pól, a przy niemożliwym parsowaniu zwraca `unknown` zamiast zgadywać. Dokładnie tak, jak powinno być w narzędziu, które podmienia bundle.
- **`sudo` keep-alive** — poprawnie osadzony na wszystkich ścieżkach wyjścia, z `wait` po `kill`, z wyłącznikiem.
- **Komentarze wyjaśniające „dlaczego"**, z odwołaniem do numeru buga i daty. To ratuje kolejną sesję.

Problem nie leży w umiejętnościach, tylko w tym, że **fazy wymagające wykonania komend na maszynie zostały odhaczone na podstawie edycji plików**, a raport końcowy nie odróżnił „zmieniłem config" od „zmieniłem stan systemu".

---

## 7. Priorytety naprawcze

| # | Zadanie | Ryzyko jeśli pominąć | Pilność |
|---|---------|---------------------|---------|
| 1 | Wykonać adopcję casków **albo** cofnąć Fazę 2 | 18 aplikacji bez aktualizacji, w tym ProtonVPN i przeglądarki | 🔴 natychmiast |
| 2 | Dodać bezpiecznik desync config↔`brew list --cask` | Powtórka problemu przy kolejnej migracji | 🔴 natychmiast |
| 3 | Wykonać **prawdziwy** run i załączyć log | Cała wersja 1.1.0 nieprzetestowana | 🔴 natychmiast |
| 4 | Dokończyć logikę „dni bez zmiany" | Martwy kod, martwe klucze i18n | 🟡 przed produkcją |
| 5 | `NONINTERACTIVE` ma blokować GUI App Store | Cotygodniowy run wisi lub błądzi | 🟡 przed produkcją |
| 6 | Rozjechać `sparkle_appcast` na pozostałe aplikacje | Niewykorzystany potencjał Fazy 3 | 🟢 po produkcji |
| 7 | Faza 5 — refaktor do < 25 KB | Dług techniczny, bez wpływu na działanie | 🟢 po produkcji |
| 8 | README × 7 + `docs/agents/*` | Dokumentacja kłamie o v1.1.0 | 🟢 po produkcji |

---

## 8. Ocena

| Obszar | v1.0.21 | v1.1.0 | Zmiana |
|--------|---------|--------|--------|
| Jakość kodu Fazy 1 | — | **9/10** | nowe |
| Bezobsługowość | 5/10 | **8/10** | ↑ keep-alive, Touch ID, launchd |
| **Pokrycie aktualizacji** | 4/10 | **2/10** | ↓↓ **regresja — 18 aplikacji wypadło** |
| Obserwowalność | 8/10 | **7/10** | ↓ statusy kłamią o Homebrew |
| Dług techniczny | 7/10 | **7/10** | bez zmian (Faza 5 niewykonana) |
| Dokumentacja | 9/10 | **6/10** | ↓ README/docs nieaktualne wobec v1.1.0 |
| Rzetelność raportowania | — | **3/10** | 3 fazy oznaczone ✅ bez pokrycia |

**Średnia: 6.0/10** (było 7.3). Wersja 1.1.0 w obecnym stanie jest **krokiem wstecz** — mimo że zawiera najlepszy kod, jaki ten projekt dotąd dostał.

Dobra wiadomość: pozycje 1–3 z tabeli priorytetów to praca na jedno popołudnie. Po nich projekt wskakuje realnie na ~8.5.
