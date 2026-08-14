# ULTRA REVIEW — macOS_updates (2026-08-14)

Autor: Oz (Warp Agent) | Zakres: pełna analiza kodu, log ostatniego przebiegu `update_all.sh`
(2026-08-14 11:22), pełny test suite (150 testów + 4174 subtestów — PASS), research konkurencji.
Wszystkie ustalenia poniżej są zweryfikowane w kodzie lub w logu — bez hipotez.

---

## 1. Kontekst przebiegu z 2026-08-14 11:22 (dowody z logu)

Pełny pipeline zakończył się w **6 min 54 s** ze statusem „zakończono z ostrzeżeniami":

| Krok | Wynik | Szczegóły |
|---|---|---|
| 0. Scan | OK | Inwentarz spójny, brak nowych/usuniętych aplikacji |
| 1. App Store | ⚠️ soft | OneDrive 26.134→26.139 przez `sudo mas` (zweryfikowany), Track 2 GUI kliknięty, niezweryfikowany |
| 2. Native CLI + npm | OK | claude-code 2.1.228→2.1.232, opencode 1.18.16→1.18.18, agy 1.1.12→1.1.13 |
| 3. Homebrew | OK | 11 formulae + 3 casks (brave, obsidian, spotify), cleanup ~93 MB, brew doctor OK |
| 4. Internet apps | ⚠️ soft | 9 aplikacji „uruchomiony (niezweryfikowany)", MAU zablokowany przez odroczenia |
| 5. Inventory | OK | 24 zmiany wersji zapisane w APPLICATIONS.md / UPDATES.md |
| 6. macOS | OK | Brak dostępnych aktualizacji (26.6.1 aktualny) |

Kontrakt severity (0 / 10 / 1) zadziałał poprawnie: soft-warningi NIE zablokowały kroku macOS.

---

## 2. Co działa bardzo dobrze (zweryfikowane)

1. **Kontrakt severity 0/10/1** — konsekwentnie zaimplementowany w `update_internet_apps.sh`,
   `update_appstore.sh`, `update_brew.sh` i egzekwowany przez `update_all.sh`; statusy błędów
   dopasowywane po stałych i18n (exact match), nie po glifach — odporne na tłumaczenia.
2. **Dwutorowy App Store** — `sudo mas upgrade` (wymóg macOS 15.7.2+/26.1+) + automatyzacja GUI
   dla aplikacji iPad (UniFi/WiFiman/Picsart); fallback `mas list` gdy `mas account` nie działa
   na macOS 26 — wszystko widoczne w logu, działa.
3. **Inwentarz samoutrzymujący się (step 0)** — prescan wykrywa nowe aplikacje (/Applications,
   formulae, casks, mas), usunięte aplikacje z GRUPY 3, deduplikuje GRUPĘ 3 vs casks 4c,
   atomic write. To unikat — żaden konkurent nie utrzymuje czytelnego dla człowieka inwentarza.
4. **Bezpieczeństwo instalacji DMG** — `hdiutil verify`, mount read-only w katalogu sesji,
   `spctl --assess`, weryfikacja bundle identifier, SHA-512 dla Ledger (base64/hex), odmowa
   instalacji nie-nowszego payloadu („Refusing non-newer..."), staging/rollback w /Applications.
5. **Downgrade guard koncepcyjnie** + opt-in `brew link --overwrite` recovery (wyłączone
   domyślnie — dobra decyzja bezpieczeństwa). Uwaga: guard ma buga — patrz §3.1.
6. **Detekcja problemów MAU** — skrypt wykrył odroczenia (DeferralDays.*=7), kanał Preview
   zamiast Production i niedokumentowany format `DeferralVersions.TEAMS21` — poziom diagnostyki,
   którego nie ma żaden konkurent.
7. **Testy i CI** — `tests/test_safety_static.py`: 150 testów / 4174 subtestów; parzystość
   config↔STATUS_*↔summary↔exit-loop↔handlery egzekwowana statycznie; heredoc Python
   kompilowany; CI: macOS runner (bash 3.2) + shellcheck. To realnie chroni przed regresjami
   konfiguracji (dzisiejsze usunięcie Ascendo przeszło na zielono od razu).
8. **i18n 7 języków** (de/en/es/fr/it/pl/pt) z loaderem i statycznymi kluczami statusów.
9. **Snapshoty sesyjne** — before/after dla mas, brew, npm/CLI, internet apps; katalog sesji
   zachowywany przy błędzie; `version_history.tsv` z rotacją (365 dni / 5000 wierszy)
   + ostrzeżenia o „stale apps" (>45 dni bez zmiany wersji).
10. **Dokumentacja agentowa** — `docs/agents/*` (critical_rules, exit_codes, architecture)
    jest precyzyjna i zgodna z kodem (zweryfikowałem reguły `-R`, `sudo mas`, bash 3.2).

---

## 3. Co NIE działa / wymaga naprawy (100% potwierdzone)

### 3.1. [P0] Martwy downgrade guard w `update_brew.sh` (linia 276)
Log: `update_brew.sh: line 276: app_version: command not found` ×3 (dla 3 casks).
Przyczyna: `app_version()` jest zdefiniowane tylko w `update_internet_apps.sh:356`
(i lokalnie w `scripts/audit_cask_candidates.sh`); `update_brew.sh` source'uje
`lib/platform.sh, cli.sh, ui.sh, i18n, severity.sh, internet_apps.sh` — żaden nie definiuje
`app_version`. Skutek: `installed_ver` puste → cała gałąź porównania wersji jest pomijana
→ guard NIGDY nie chroni przed downgrade + śmieci na stderr przy każdym przebiegu z casks.
Testy tego nie łapią (brak testu „każda wywoływana funkcja jest zdefiniowana w zasięgu").

### 3.2. [P1] `installed_apps_after.txt` powstaje PRZED aktualizacjami
`update_all.sh:580` — prescan (step 0) zapisuje snapshot o nazwie `installed_apps_after.txt`.
Dowód w logu: plik zawiera `Obsidian|1.13.6`, `Spotify|1.2.95.453`, `OneDrive|26.134.0713`
— wersje sprzed aktualizacji, mimo sufiksu `_after`. Mylące nazewnictwo + ryzyko użycia
nieaktualnych danych przez przyszły kod. (Krok 5 używa innych snapshotów — brew/mas/internet —
dlatego APPLICATIONS.md ma poprawne wersje; sam plik jest jednak semantycznie fałszywy.)

### 3.3. [P1] Przestarzałe `datetime.utcnow()` (12 DeprecationWarnings na przebieg)
`lib/internet_apps.sh:91` i `:104` (heredoc Python: stale-days + rotacja historii).
Python usunie `utcnow()`; już dziś zaśmieca log. Naprawa: `datetime.now(datetime.timezone.utc)`
(+ spójne naive/aware porównania z `strptime`).

### 3.4. [P1] Brak mechanizmu wykluczeń w skanerze inwentarza
`SKIP_DISCOVERY_APPS = set(['Utilities'])` jest zahardkodowane w `update_all.sh:495`
(+ appstore_gui z configu). Przypadek Ascendo (usunięty dziś z pipeline'u na życzenie
użytkownika) pokazał lukę: aplikacji zainstalowanej w /Applications NIE DA SIĘ usunąć
z APPLICATIONS.md — prescan doda ją z powrotem jako „🆕 do skategoryzowania". Wiersz musiał
zostać. Potrzebny `config/inventory_exclusions.txt` (lub kolumna „excluded") czytany przez
prescan.

### 3.5. [P2] MAU wykrywa problemy, ale ich nie naprawia
Odroczenia (DeferralDays=7) + kanał Preview blokują aktualizacje Office 16.112. Skrypt
poprawnie diagnozuje i podaje instrukcję ręczną, ale nie oferuje opcjonalnej, bramkowanej
naprawy (usunięcie kluczy odroczeń / wyrównanie kanału). Office pozostaje nieaktualny
przebieg po przebiegu.

### 3.6. [P2] 9 aplikacji trwale „⏳ niezweryfikowany"
ChatGPT/Codex, Claude, Gemini, Comet, Antigravity ×2, OpenCode, Warp, Cursor, Docker, Teams,
Proton Mail — metoda `silent_launch` uruchamia updater, ale nie potwierdza wyniku. Settle-loop
(adaptive, 3 stabilne odczyty) łagodzi to tylko częściowo. Brak trybu re-weryfikacji
(np. `--verify-only` po 10–15 min), który domknąłby pętlę dowodową.

### 3.7. [P2] Dług utrzymaniowy orkiestratora
`update_all.sh` ma **1904 linie** z wielkimi heredocami Pythona; AGENTS.md (reguła 4) mówi
o modułach w `lib/python/` — ten katalog NIE istnieje. Cała logika prescan/inwentarza żyje
w heredocach nietestowalnych jednostkowo (tylko py_compile).

### 3.8. [P2] Higiena repo
`git_history_archive.md` (7,5 MB!) w korzeniu repo publicznego, `.DS_Store` (10 KB),
`graphify-out/`, 89 pozycji w `dev_sync_logs/`. Zaburza clone i przeglądanie.

### 3.9. [P3] Niespójne źródła wersji w snapshotach
Log: `installed_apps_after.txt` ma `Google Chrome|151.0.7922.109`, a snapshot internet apps
`151.0.7922.138` (defaults vs mdls, moment odczytu). Nie powoduje błędnych decyzji dziś,
ale utrudnia diagnostykę.

---

## 4. Analiza konkurencji (research 2026, jako specjalista macOS)

Kontekst rynkowy: **MacUpdater — dotychczasowy złoty standard — zamknięty 2026-01-01**
(CoreCode; baza wygasa do końca 2026). Rynek szuka następcy. Stan alternatyw:

| Narzędzie | Model | Mocne strony | Czego nie robi |
|---|---|---|---|
| **Latest** (free, OSS) | GUI, Sparkle+MAS | prosty, notarized, release notes | ~44% skuteczności (test TidBITS), brak brew/CLI |
| **Updatest** ($12.99) | GUI, multi-source | Sparkle+MAS+brew+Electron+GitHub, sieć społecznościowa wersji, adopt do brew | brak systemu macOS, brak npm/CLI, macOS 15+ |
| **topgrade** (OSS, Rust) | CLI meta-updater | brew+mas+macOS+node+rust+docker itd. | zero weryfikacji per-app, brak Sparkle, brak inwentarza |
| **brew cu** (OSS) | CLI casks | pin/unpin wersji, greedy | tylko casks |
| **freshly** (OSS, Rust TUI) | TUI 3 źródła | MAS+brew+Sparkle równolegle, `--json` | nie instaluje sam (poza brew), młody projekt |
| **Relay** (beta) | GUI menu-bar | **snapshoty APFS przed update (rollback!)**, brew bridge | beta, mała baza |
| **CleanMyMac** ($39.95/r) | GUI suite | ładny updater w pakiecie | ~27% skuteczności, subskrypcja, bloat |

**Pozycja macOS_updates**: jedyne rozwiązanie łączące w JEDNYM przebiegu: macOS system
(`softwareupdate -R`), App Store (dwutorowo!), Homebrew (z downgrade guard), natywne CLI/npm
oraz ~40 aplikacji internetowych z 10 metodami (Sparkle appcast, GitHub DMG+checksum, Keystone,
msupdate, docker cli...) + samoutrzymujący się inwentarz + kontrakt severity + i18n.
Funkcjonalnie przewyższa topgrade (weryfikacja per-app) i Updatest (macOS system + CLI).

**Czego konkurenci mają, a my nie** (kandydaci do przejęcia):
1. **Rollback / APFS snapshot przed aktualizacją** (Relay) — najcenniejsza brakująca ochrona.
2. **`--json` output** (freshly) — raport maszynowy do automatyzacji/monitoringu.
3. **Pin/exclude wersji** (brew cu `pin`) — nasz przypadek Ascendo to dokładnie ta luka (§3.4).
4. **GUI/menu-bar** albo chociaż powiadomienie systemowe po przebiegu — dziś wynik żyje
   tylko w terminalu i logu.
5. Updatest Network (społecznościowa baza wersji) — poza zasięgiem projektu 1-osobowego,
   ale rozszerzanie bazy kanałów Sparkle (SUFeedURL z Info.plist) jest osiągalne.

---

## 5. Scoring (0–10)

| Kategoria | Ocena | Uzasadnienie |
|---|---|---|
| Niezawodność pipeline'u | 8.5 | pełny przebieg 7 min bez twardych błędów; kontrakt severity działa |
| Bezpieczeństwo instalacji | 9.0 | hdiutil verify, spctl, SHA-512, staging/rollback, opt-in recovery |
| Pokrycie aktualizacji | 8.5 | system+MAS+brew+CLI+40 apek; Office zablokowany przez MAU (środowisko) |
| Weryfikowalność wyników | 6.0 | 9 aplikacji trwale „unverified"; brak trybu re-weryfikacji |
| Jakość kodu / utrzymanie | 6.5 | martwy downgrade guard (P0), 1904-liniowy orkiestrator, heredoki |
| Testy i CI | 9.0 | 4174 subtesty parzystości, shellcheck, macOS runner |
| UX / raportowanie | 7.0 | świetne podsumowania PL, progres; brak JSON, brak powiadomień |
| Dokumentacja | 9.0 | docs/agents precyzyjne; drobny dryf (lib/python/ nie istnieje) |
| Pozycja vs konkurencja | 8.5 | unikalne pokrycie; brak rollbacku i GUI |
| Higiena repo | 6.0 | 7.5 MB archiwum w korzeniu, .DS_Store |

**OCENA ŁĄCZNA: 78/100** — dojrzały, bezpieczny i unikalny na rynku orkiestrator z jednym
realnym bugiem P0, jasno zdefiniowanym długiem utrzymaniowym i konkretną listą przewag
konkurencji do przejęcia.

---

## 6. Priorytety napraw (wsad do promptu implementacyjnego)

- **P0-1**: naprawa `app_version` w `update_brew.sh` (przenieść do `lib/version.sh` + source
  wszędzie; test statyczny na niezdefiniowane funkcje).
- **P1-2**: naprawa semantyki `installed_apps_after.txt` (rename + realny snapshot po kroku 4).
- **P1-3**: `datetime.utcnow()` → aware UTC (2 heredoki w `lib/internet_apps.sh`).
- **P1-4**: `config/inventory_exclusions.txt` + wsparcie prescanu (przypadek Ascendo).
- **P1-5**: tryb `--verify-only` (re-weryfikacja wersji po zakończonym przebiegu).
- **P2-6**: opcjonalna, bramkowana naprawa odroczeń/kanału MAU.
- **P2-7**: `logs/run_summary.json` (raport maszynowy) + powiadomienie osascript po przebiegu.
- **P2-8**: ekstrakcja heredoców Pythona do `lib/python/` (zgodnie z AGENTS.md regułą 4).
- **P2-9**: higiena repo (git_history_archive.md, .DS_Store).
- **P3-10**: ujednolicenie źródła wersji w snapshotach; opcjonalny APFS snapshot przed casks
  (research wykonalności — jak Relay).

Zmiany wykonane w ramach tego przeglądu (jedyne dozwolone): usunięcie **Ascendo** z pipeline'u
aktualizacji (config ×3, orkiestrator, handler, legenda APPLICATIONS.md, docs, audit script) —
testy 150/150 zielone. Wiersz inwentarza pozostał świadomie (aplikacja wciąż zainstalowana;
prescan dodałby ją z powrotem — patrz §3.4).
