# ULTRA REVIEW v4 — weryfikacja v1.2.0 + badanie wersji cask vs natywny updater
**Data:** 2026-08-05 · **Weryfikowany commit:** `cf50346` · **Źródło danych:** `formulae.brew.sh/api` + `registry.npmjs.org` (pobrane 2026-08-05)

---

## WERDYKT: ⛔ NIE WYPUSZCZAĆ — 3 blokery, w tym „bezpiecznik", który nie działa

v1.2.0 naprawiło P1 (sudo) i P4 (kanał MAU) **naprawdę**. Ale:

1. **Zabezpieczenie przed downgrade'em — sztandarowa funkcja tego wydania — jest martwym kodem.** Ma dwa niezależne błędy i nie zadziała nigdy.
2. **Twoje pytanie o wersje ma odpowiedź: TAK, i to gorzej niż podejrzewałeś.** Cztery aplikacje z Twojej listy „zawsze najnowsze" zostaną cofnięte, w tym Cursor o **7 wersji minor** i Warp o **2 miesiące**.
3. **Deduplikacja inwentarza (P2) to test pozorny** — przechodzi, bo porównuje `Brave Browser` z `brave-browser`. 18 aplikacji nadal figuruje dwa razy.

---

# CZĘŚĆ 1 — Odpowiedź na Twoje pytanie o wersje

## 1.1 Kluczowe odkrycie: istnieją **dwa różne typy casków**

Pobrałem dziś metadane wszystkich Twoich casków z oficjalnego API Homebrew. Różnica, która decyduje o wszystkim:

### Typ A — „zawsze najnowszy" (`sha256: no_check`, URL bez numeru wersji)
```json
"url": "https://www.perplexity.ai/rest/browser/download?channel=stable&platform=mac_arm64",
"sha256": "no_check",
"version": "145.2.7632.4581"
```
URL to **przekierowanie na aktualne wydanie**. Numer wersji w casku jest wyłącznie kosmetyczny.
→ **Nie ma downgrade'u.** Ale `--greedy` ściąga 1,4 GB przy każdym runie i metadane Homebrew na stałe kłamią.

**Twoje aplikacje typu A:** Comet, Google Chrome

### Typ B — „przypięty" (prawdziwy `sha256`, URL zawiera numer wersji)
```json
"url": "https://proton.me/download/mail/macos/1.13.3/ProtonMail-desktop.dmg",
"sha256": "0b4511866c5c6d07cff2e31ef2746e531e5fd092f404cbefad615f5c709547dd",
"version": "1.13.3"
```
`brew upgrade --cask` zainstaluje **dokładnie tę wersję**.
→ **Gdy cask jest w tyle za aplikacją, to jest prawdziwy downgrade.**

**Twoje aplikacje typu B:** wszystkie pozostałe — i tu jest problem.

## 1.2 Tabela: co masz vs. co da Ci Homebrew (dane z 2026-08-05)

| Aplikacja | Masz zainstalowane | Wersja w casku | Cask bumpnięty | Typ | Werdykt |
|-----------|--------------------|----------------|----------------|-----|---------|
| **Cursor** | **3.14.27** | **3.7.21** | **2026-06-09** | B | 🔴 **DOWNGRADE o 7 wersji minor** |
| **Warp** | **0.2026.07.29.09.05.02** | **0.2026.05.27.15.44.stable_01** | **2026-05-31** | B | 🔴 **DOWNGRADE o ~2 miesiące** |
| **Antigravity** | **2.5.0** | **2.0.10** | **2026-05-30** | B | 🔴 **DOWNGRADE o 5 wersji minor** |
| **Proton Mail** | **1.13.4** | **1.13.3** | **2026-07-16** | B | 🔴 **DOWNGRADE o 1 patch** |
| Comet | 150.0.7871.228 | 145.2.7632.4581 | 2026-08-05 | **A** | 🟡 metadane kłamią, ale pobiera najnowsze; 1,4 GB/run |
| Google Chrome | 151.0.7922.76 | 150.0.7871.101 | 2026-07-08 | **A** | 🟡 j.w. — i tak masz Keystone, zostaw |
| Proton Drive | 3.0.0 | 3.0.0 | 2026-07-17 | B | 🟡 równe **dziś**, cask już jest 3 tyg. stary |
| Brave Browser | 151.1.93.129 | 1.93.129.0 | 2026-08-05 | B | ✅ ten sam build (193.129) |
| Antigravity IDE | 2.1.1 | 2.1.1 | 2026-08-05 | B | ✅ aktualny |
| Claude Desktop | 1.25927.0 | 1.25927.0 | 2026-08-05 | B | ✅ aktualny |
| **ChatGPT** | 26.727.51351 | **26.730.61639** | 2026-08-05 | B | ✅ **cask jest NOWSZY** — czeka upgrade |
| Firefox Dev Edition | 154.0 | *(nie jest caskiem — `github_dmg`)* | — | — | ✅ zostaw jak jest |

### Narzędzia CLI przez npm — tu problemu nie ma

| CLI | Masz | npm `latest` | Werdykt |
|-----|------|--------------|---------|
| `claude` (claude-code) | 2.1.222 | **2.1.222** | ✅ |
| `codex` (@openai/codex) | 0.146.0 | **0.146.0** | ✅ |
| `opencode` (opencode-ai) | 1.18.13 | **1.18.13** | ✅ |
| `agy` | 1.1.10 | *(własny updater `agy update`)* | ✅ |

**npm zawsze serwuje najnowsze wydanie — nie ma opóźnienia jak w casku.** Ścieżka npm/CLI w tym projekcie jest zdrowa i nie wymaga zmian.

## 1.3 Dlaczego cask się opóźnia

Wszystkie Twoje caski mają `auto_updates: true` i `autobump: true`. Autobump to bot, który podnosi wersję, gdy wykryje nowe wydanie — ale:
- działa z opóźnieniem i bywa, że utknie (Warp: 2026-05-31, Antigravity: 2026-05-30, Cursor: 2026-06-09 — **wszystkie ponad 2 miesiące bez bumpa**)
- aplikacja z `auto_updates` **sama się aktualizuje w międzyczasie**, więc rozjazd rośnie z każdym dniem
- Homebrew sam to dokumentuje: przy `auto_updates` porównanie wersji „nie jest dostępne dla każdego schematu wersjonowania" i wtedy cask jest pomijany — chyba że wymusisz `--greedy`

**A Ty masz w `update_brew.sh` właśnie `--greedy`.**

## 1.4 Rekomendacja — trzy kategorie zamiast jednej

Twój wymóg („zawsze najnowsze, wolę ręcznie ale aktualne") jest **niezgodny z `brew_cask`** dla aplikacji szybko wydawanych. Proponuję:

### 🥇 Kategoria „bleeding edge" — wypnij z Homebrew
**Cursor, Warp, Antigravity, Comet, Proton Mail, Proton Drive, ChatGPT, Claude Desktop, Antigravity IDE**

Metoda: `sparkle_appcast` / feed producenta → **weryfikuj wersję zdalną, ale instalację zostaw natywnemu updaterowi**. Dostajesz to, czego chcesz: pewność, że masz najnowsze, bez ryzyka cofnięcia.

Dlaczego również Claude/ChatGPT/Antigravity IDE, skoro dziś są aktualne? Bo są aktualne **przypadkiem** — nic nie gwarantuje, że autobump nie utknie na 2 miesiące jak przy Warpie. Kryterium ma być tempo wydawania, nie stan na dziś.

### 🥈 Kategoria „cask jest OK" — zostaw w Homebrew
**Brave, Obsidian, Spotify, AppCleaner, CapCut, MEGAsync, ProtonVPN, zoom, LM Studio, Perplexity, Inkscape**

Wolniejsze cykle wydawnicze, cask nadąża, prawdziwa weryfikacja wersji za darmo.

### 🥉 Kategoria „natywny kanał jest lepszy" — nie ruszaj
**Google Chrome** (Keystone), **Firefox Dev** (`github_dmg`), **npm CLI** (claude-code, codex, opencode, agy)

---

# CZĘŚĆ 2 — Weryfikacja wdrożenia v1.2.0

## 🔴 BLOKER 1 — bezpiecznik przed downgrade'em to martwy kod

`update_brew.sh:249–252`:
```bash
rel=$(internet_version_relation "$cask_ver" "$installed_ver" 2>/dev/null || echo "same")
if [ "$rel" = "older" ]; then
```

### Błąd 1a — funkcja nigdy nie zwraca `"older"`
`lib/internet_app_updates.sh:8–41` zwraca dokładnie trzy wartości:
```python
print("unknown")   # gdy nie da się sparsować
print("newer")     # gdy remote > local
print("current")   # w każdym innym przypadku
```
Nie ma gałęzi `"older"`. **Warunek `[ "$rel" = "older" ]` nie będzie prawdziwy nigdy.**

Poprawna logika wymaga odwrócenia argumentów: downgrade to sytuacja, w której *zainstalowana* jest nowsza od *casku*, czyli `internet_version_relation "$installed_ver" "$cask_ver" = "newer"`.

### Błąd 1b — parsowanie wersji łapie złe pole
```bash
cask_ver=$(echo "$cask_info" | awk '{print $3}')
```
Format `brew info --cask` (z Twojego własnego wklejonego wyjścia):
```
==> comet (Comet): 145.2.7632.4581 (auto_updates)
     $1      $2       $3               $4
```
`$3` = `(Comet):` — nie wersja. Dla casków bez nazwy w nawiasie (`==> inkscape: 1.4.4`) `$3` = `1.4.4`, czyli **działa niekonsekwentnie zależnie od casku**.

Skutek złożony: `cask_ver="(Comet):"` → `version_key()` nie znajduje cyfr → zwraca `None` → `"unknown"` → `≠ "older"` → cask ląduje w `UPGRADEABLE_CASKS` → **downgrade się wykonuje**.

### Błąd 1c — mapowanie casku na ścieżkę aplikacji
```bash
cask_app_path="/Applications/$cask.app"
```
Slug casku ≠ nazwa aplikacji: `brave-browser` → `/Applications/brave-browser.app` (nie istnieje), `proton-mail` → `/Applications/proton-mail.app` (nie istnieje). Projekt ma już `internet_cask_name_for_app` — brakuje mapowania odwrotnego. Artefakt `artifacts[].app` z API Homebrew podaje prawdziwą nazwę.

### Dlaczego test tego nie złapał
`test_brew_upgrade_guards_against_downgrade` jest **statyczny** — sprawdza obecność bloku w pliku, nie jego poprawność. Trzy błędy logiczne przechodzą.

---

## 🔴 BLOKER 2 — deduplikacja inwentarza (P2) jest pozorna

Raport podaje: *„Intersection count between GRUPA 3 and Section 4c Casks: 0"*.

Sprawdziłem — przy normalizacji nazw (wielkość liter + separatory) przekrój wynosi **18**:

```
GRUPA3: 47   4c: 20   overlap: 18
['capcut', 'brave browser', 'warp', 'inkscape', 'proton mail',
 'proton drive', 'antigravity ide', 'obsidian', 'spotify', 'protonvpn', ...]
```

Dowód wprost z pliku:
```
GRUPA 3:  | Cursor | 3.14.27 | https://cursor.com |
4c:       | cursor | 3.14.27,047548b00c1a... | 🆕 NOWY |

GRUPA 3:  | Proton Mail | 1.13.4 | https://proton.me/mail/download |
4c:       | proton-mail | 1.13.3 | 🆕 NOWY |
```

Test `test_no_app_listed_in_both_group3_and_casks` porównuje **nazwy wyświetlane** (`Brave Browser`) ze **slugami casków** (`brave-browser`). Te zbiory nie mają wspólnych elementów **z definicji** — test przechodzi zawsze, niezależnie od stanu pliku.

To ten sam wzorzec co w Blokerze 1: test potwierdza istnienie kodu, nie jego działanie.

Dodatkowo widać tu wprost rozjazd wersji z Części 1: GRUPA 3 mówi `Proton Mail 1.13.4`, sekcja 4c mówi `1.13.3`. Inwentarz sam sobie zaprzecza.

---

## 🔴 BLOKER 3 — cztery aplikacje czekają na cofnięcie

Bloker 1 + dane z Części 1 dają konkretne ryzyko przy następnym `bash update_all.sh`:

| Aplikacja | Zostanie cofnięta z | do | Skala |
|-----------|---------------------|-----|-------|
| Cursor | 3.14.27 | 3.7.21 | 7 wersji minor |
| Warp | 0.2026.07.29 | 0.2026.05.27 | ~2 miesiące |
| Antigravity | 2.5.0 | 2.0.10 | 5 wersji minor |
| Proton Mail | 1.13.4 | 1.13.3 | 1 patch |

To nie jest teoretyczne — `brew upgrade --cask --greedy` zobaczy różnicę wersji, bezpiecznik nie zadziała, DMG jest przypięty do starej wersji z prawidłową sumą kontrolną.

---

## ✅ Co w v1.2.0 działa naprawdę

| Element | Weryfikacja |
|---------|-------------|
| **P1 — `_needs_sudo`** | `update_all.sh:201–205` — warunek poprawnie obejmuje `SKIP_APPSTORE` **i** `SKIP_SYSTEM` ✅ |
| **P1 — brak TTY** | `update_appstore.sh:247` — `MAC_UPDATE_NO_SUDO` obsłużone, soft zamiast hard ✅ |
| **P4 — kanał MAU** | Wykryty: `ChannelName: External`. To jest przyczyna pętli — kanał External serwuje 16.111.2, a masz 16.111.5 ✅ |
| **P5 — READMEs** | `git diff --stat` potwierdza 7/7 plików. Ale 5 z nich dostało **1 linię zmiany** — realnie zaktualizowane są `README.md` (+15/−3) i `README.pl.md` (+39/−15) 🟡 |
| **Testy** | 140–141 PASS ✅ |
| **Prawdziwe runy** | 3 runy, App Store OK, OneDrive 26.129 → 26.134 ✅ |
| **P6.2 — pomiary** | `--greedy` 1,20 s vs `--greedy-auto-updates` 0,30 s ✅ |

Rekomendacja Gemini z P6.2 („przejść na `--greedy-auto-updates`") jest **słuszna, ale z innego powodu niż podano**. Uzasadnienie „oba są w 100% bezpieczne dzięki naszemu bezpiecznikowi" jest nieprawdziwe — bezpiecznik nie działa. Prawdziwy powód: `--greedy-auto-updates` pomija caski `version :latest`, więc unika bezsensownych re-pobrań. Ryzyko downgrade'u zostaje w obu wariantach.

---

## Metryki — deklarowane vs. zweryfikowane

| Metryka | Raport v1.2.0 | Weryfikacja |
|---------|---------------|-------------|
| Testy | 140/140, potem 141/141 | **PASS** ✅ |
| Krok 1 przy `--skip-system` | OK | **OK** ✅ |
| Aplikacje zdublowane w inwentarzu | **0** | **18** 🔴 |
| Bezpiecznik downgrade | działa | **martwy kod** 🔴 |
| Aplikacje zagrożone cofnięciem | 0 | **4** 🔴 |
| READMEs | 7/7 | 7/7 plików, **2/7 merytorycznie** 🟡 |
| Kanał MAU | wykryty | **wykryty (`External`)** ✅ |

---

## Ocena

| Obszar | v1.1.1 | **v1.2.0** |
|--------|--------|-----------|
| Bezobsługowość | 6/10 | **9/10** ↑ (P1 naprawione) |
| Integralność inwentarza | 4/10 | **4/10** = (dedup pozorny) |
| Bezpieczeństwo | 7/10 | **5/10** ↓ (4 aplikacje czekają na cofnięcie, bezpiecznik martwy) |
| Diagnostyka MAU | 5/10 | **9/10** ↑↑ |
| Jakość kodu | 9/10 | **7/10** ↓ (3 błędy logiczne w jednej funkcji) |
| Jakość testów | 8/10 | **5/10** ↓ (2 testy pozorne) |
| Rzetelność raportu | 7/10 | **6/10** ↓ (P2 zweryfikowane błędną metodą) |

**Średnia: 6.4/10**

Wzorzec, który się powtarza i który trzeba przerwać: **testy statyczne sprawdzają, czy kod istnieje, a nie czy działa.** Bezpiecznik downgrade'u i dedup inwentarza przeszły testy, będąc niefunkcjonalne. Następna sesja musi dodać testy **behawioralne** — wywołujące funkcję na sztucznych danych i sprawdzające wynik.

Po naprawie tych trzech blokerów i przeniesieniu 9 aplikacji do kategorii „bleeding edge" projekt jest gotowy do produkcji i realnie ląduje na **~8.5/10**.

---

## Źródła

- [Homebrew API — cask/comet.json](https://formulae.brew.sh/api/cask/comet.json)
- [Homebrew API — cask/proton-mail.json](https://formulae.brew.sh/api/cask/proton-mail.json)
- [Homebrew API — cask/cursor.json](https://formulae.brew.sh/api/cask/cursor.json)
- [Homebrew API — cask/warp.json](https://formulae.brew.sh/api/cask/warp.json)
- [Homebrew API — cask/antigravity.json](https://formulae.brew.sh/api/cask/antigravity.json)
- [Homebrew API — cask/claude.json](https://formulae.brew.sh/api/cask/claude.json)
- [Homebrew API — cask/chatgpt.json](https://formulae.brew.sh/api/cask/chatgpt.json)
- [Homebrew API — cask/google-chrome.json](https://formulae.brew.sh/api/cask/google-chrome.json)
- [Homebrew API — cask/brave-browser.json](https://formulae.brew.sh/api/cask/brave-browser.json)
- [npm — @anthropic-ai/claude-code](https://registry.npmjs.org/@anthropic-ai/claude-code/latest)
- [npm — @openai/codex](https://registry.npmjs.org/@openai/codex/latest)
- [npm — opencode-ai](https://registry.npmjs.org/opencode-ai/latest)
- [Homebrew — cask version tracking with auto_updates (#15932)](https://github.com/Homebrew/brew/issues/15932)
- [Homebrew Discussion #6951 — upgrading auto_updates casks](https://github.com/orgs/Homebrew/discussions/6951)
- [Homebrew FAQ](https://docs.brew.sh/FAQ)
