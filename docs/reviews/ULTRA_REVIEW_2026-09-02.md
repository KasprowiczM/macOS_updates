# Ultra Review — macOS Updates v1.4.3

**Data:** 2026-09-02
**Zakres:** log przebiegu `logs/update_all_20260901_110312.log` + 22 wcześniejsze przebiegi, cała ścieżka Microsoft AutoUpdate, TOR 1 App Store, raport maszynowy
**Maszyna referencyjna:** mac-r12-home, macOS 26.6.2 (25G83), Apple Silicon — najnowszy stabilny macOS w dniu review
**Metoda:** pomiar systemu docelowego, nie stanu repozytorium

---

## 1. Wniosek w jednym zdaniu

Ostatni przebieg zakończył się `exit_code: 0`, ale `degraded: true` — i tak samo **20 z ostatnich 26 przebiegów**. Żadne z tych ostrzeżeń nie było przejściowe: jedno ukrywało realną aktualizację Office przez siedem tygodni, drugie dziesięć razy z rzędu raportowało zapis, którego nie potrafiło utrzymać, trzecie zostawiło zainstalowaną starą wersję WhatsAppa, nazywając krok „niezweryfikowanym".

Po tej sesji krok internetowy przechodzi z **8 ostrzeżeń + soft-fail (exit 10)** na **0 ostrzeżeń, exit 0**, a Office jest na 16.112.3 zamiast 16.112.2.

---

## 2. Scoring aplikacji

Skala 1–10. Kolumna „przed" to stan zastany 2026-09-01, „po" to stan po tej sesji.

| Obszar | Przed | Po | Uzasadnienie |
|---|:--:|:--:|---|
| **Prawdomówność raportowania** | 4 | 8 | Był to najsłabszy punkt projektu i drugi raz z rzędu główne źródło defektów. Kwarantanna raportowała „wstrzymane przez odroczenie" jako stan, gdy była to usterka; pin TEAMS21 raportował zwolnienie, którego nie było; TOR 1 raportował „completed" przy pominiętej aplikacji. Naprawione pomiarem, nie opisem. |
| **Architektura i ograniczenia** | 8 | 8 | Bash 3.2 respektowany konsekwentnie (brak `declare -A`, `mapfile`), `SCRIPT_DIR` bez hardcode'ów, Python wyłącznie w heredocach i `lib/python/`. `shellcheck -S error`: 0 błędów na 18 537 linii shella. Podział `lib/` czytelny. |
| **Bezpieczeństwo** | 8 | 8 | Atomowe zapisy z `os.replace`, `chmod 600` na kopiach profilu, backup domeny MAU przed każdą mutacją, `plutil -lint` przed importem, gitleaks w pakiecie testów (97 commitów, 0 wycieków). Sekrety poza repo. Bez zastrzeżeń. |
| **Odporność strażników** | 3 | 7 | Klasa defektu, którą znalazłem: **strażnik tłumiący własny dowód**. Kwarantanna ukrywała produkt przed `msupdate --list`, a regułą zwolnienia była oferta z tej listy. Zamknięta pętla, siedem tygodni blokady. Naprawione wygasaniem, ale wzorzec może istnieć w innych strażnikach — patrz rekomendacja R1. |
| **Testowalność** | 8 | 9 | 213 testów, zielone. Testy są behawioralne tam, gdzie to ma znaczenie (uruchamiają funkcje bashowe przez `subprocess`), a nie tylko regexowe na treści plików. Dopisałem 24 regresje, w tym własność „ponowne uzbrojenie nie resetuje zegara", bez której poprawka odtworzyłaby oryginalny błąd. |
| **Obserwowalność** | 5 | 8 | `run_summary_*.json` — 26 kolejnych plików z `"counts": {}`, bo wywołujący nigdy nie przekazał mapy, którą `build_run_summary()` od zawsze przyjmował. Każdy konsument JSON-a musiał parsować log dla człowieka. Naprawione. Brakuje jeszcze wykrywania **chronicznych** ostrzeżeń — patrz R2. |
| **Pokrycie aktualizacji** | 9 | 9 | 62/65 aplikacji (95,4%), znane pokrycie 64/65 (98,5%). Dwie pozycje wyłącznie ręczne z winy dostawcy (IPMIView, DJI Assistant 2), jedna nieznana (Ascendo — projekt własny). Trudno o więcej na tej maszynie. |
| **Dokumentacja i proces** | 9 | 9 | 13 handoffów, CHANGELOG z rzeczywistymi przyczynami źródłowymi, `AGENTS.md` z regułami nienegocjowalnymi, 7 języków i18n, pamięć projektu spójna z kodem. To najmocniejsza strona projektu i powód, dla którego dało się dziś pracować szybko. |
| **UX terminala** | 7 | 8 | Czytelny, ale inflacja ostrzeżeń realnie szkodziła: żółta linia na każdym przebiegu uczy operatora ignorować żółte linie. Zdemowałem do informacji to, czego operator nie może wyczyścić (brak auto-updatera u dostawcy, księgowość MAU). |
| **Łącznie** | **6,8** | **8,2** | |

**Ocena ogólna: 8,2/10.** To dojrzały, dobrze udokumentowany i dobrze przetestowany projekt, którego jedyną powtarzalną słabością jest ta sama klasa błędu w kolejnych wydaniach: *system twierdzi coś, czego nie zmierzył*.

---

## 3. Defekty znalezione i naprawione

### P0-1 — Kwarantanna Office nie mogła się zwolnić i ukrywała realną aktualizację przez 7 tygodni

**Objaw:** `⚠️ Brak dostępnych aktualizacji — te produkty Microsoft są wstrzymane przez odroczenie: MSWD2019 XCEL2019 PPT32019 OPIM2019 ONMC2019` — w **20 kolejnych przebiegach**, od 2026-08-15 do 2026-09-01.

**Przyczyna źródłowa:** pięć wpisów `DeferralDays=7` uzbrojonych regresją pakietu Office Preview z 2026-07-14 nadal żyło. Reguła zwolnienia wymaga oferty, której wersja krótka jest nowsza od zainstalowanej — ale **aktywny `DeferralDays` całkowicie ukrywa produkt przed `msupdate --list`**. Dowód potrzebny do zwolnienia kwarantanny był tłumiony przez samą kwarantannę. Komentarz w kodzie zakładał, że wpis „wygasa sam po `MAC_UPDATE_MAU_DEFERRAL_DAYS`" — nie wygasa. `DeferralDays` to opóźnienie liczone per aktualizacja, a sam wpis zostaje w domenie bezterminowo.

**Pomiar (2026-09-02, po zdjęciu odroczeń):**
```
PPT32019  Microsoft PowerPoint Update 16.112.3 (26083020)
ONMC2019  Microsoft OneNote    Update 16.112.3 (26083020)
XCEL2019  Microsoft Excel      Update 16.112.3 (26083020)
OPIM2019  Microsoft Outlook    Update 16.112.3 (26083020)
MSWD2019  Microsoft Word       Update 16.112.3 (26083020)
```
Zainstalowane było 16.112.2. To **upgrade, nie regresja** — trzymany w kwarantannie siedem tygodni. Tymczasem demon MAU dowoził w tle 16.112 → 16.112.1 → 16.112.2, a toolkit był na to ślepy i przy każdym przebiegu ogłaszał, że nic nie jest dostępne.

**Naprawa:** kwarantanna dostała wygasanie, którym steruje sam strażnik — `MAC_UPDATE_MAU_QUARANTINE_MAX_DAYS` (domyślnie 14, przycinane do 1–90), zapisywane w `~/.local/state/mac-update/mau_quarantine.tsv`. Po upływie okna wpis jest zwalniany, żeby następny przebieg zobaczył prawdziwy feed; jeśli oferta nadal jest cofnięciem wersji, `mau_regressed_entries` uzbraja ją ponownie w tym samym przebiegu. Najgorszy przypadek to jedno zbędne pobranie na produkt na dwa tygodnie zamiast bezterminowej ciemności.

Trzy własności, bez których poprawka odtworzyłaby oryginalny błąd:
- **Ponowne uzbrojenie nie restartuje zegara.** `mau_arm_deferrals` jest no-opem, gdy wartość już wynosi tyle, ile trzeba, więc długo żyjąca kwarantanna jest raportowana jako „uzbrojona" przy każdym przebiegu. Odświeżanie znacznika czasu oznaczałoby kwarantannę odnawiającą się w nieskończoność.
- **Wpis bez zapisu liczy się jako wygasły** — poprzedza tę księgowość, więc z definicji jest starszy niż okno. To dokładnie stan zastany 2026-09-01.
- **Zbiór wygasły idzie jako argument oferty tego samego wywołania `mau_reconcile_deferrals`**, nigdy jako drugie wywołanie. Dwa cykle export/import w jednym przebiegu ścigają się przez `cfprefsd` — to znany błąd z 2026-08-26, który wskrzeszał wpis właśnie usunięty.

### P0-2 — `DeferralVersions.TEAMS21` zwalniany dziesięć razy, odtwarzany dziesięć razy

**Objaw:** `✅ Zwolniono odroczenia Microsoft AutoUpdate: DeferralVersions.TEAMS21` w 10 przebiegach + `⚠️ … is not the documented Major.Minor form` w każdym.

**Przyczyna źródłowa:** pin **na** zainstalowanym buildzie to nie jest przeterminowany pin — to własna księgowość Microsoft AutoUpdate dla produktu, który sam zarządza swoim cyklem aktualizacji. Wartość `26213.1006.5011.1671` jest co do znaku równa `CFBundleShortVersionString` Teams i wpisowi w rejestrze `AppVersions` samego MAU. Poprawka z 1.4.2 zaczęła prawidłowo *mierzyć* usunięcie na żywej domenie, ale nie zakwestionowała założenia, że ten pin w ogóle należy usuwać. Efekt: każdy przebieg przepisywał domenę preferencji użytkownika, raportował zwolnienie, które MAU cofał w ciągu godzin, i podnosił ostrzeżenie o zdrowiu, na które operator nie mógł zareagować.

**Naprawa:** pin `DeferralVersions` jest zwalniany wyłącznie wtedy, gdy jest **ściśle starszy** od zainstalowanego builda — taki faktycznie blokuje produkt bezterminowo. Ostrzeżenie o formacie Major.Minor jest tłumione, gdy wartość zgadza się z zainstalowanym buildem. Zainstalowany build czytany jest z rejestru `AppVersions` samego MAU — jedynego operandu like-for-like dla wartości, którą MAU zapisał — z `CFBundleShortVersionString` jako fallbackiem. To ta sama zasada, co „ewidencja Homebrew przed wersją z bundla" z poprzedniego review.

### P0-3 — `sudo mas upgrade` po cichu pominął oczekującą aktualizację

**Objaw:** przebieg 2026-09-01 wylistował jako oczekujące **Copilot i WhatsApp**, zaktualizował Copilot, nie wspomniał o WhatsAppie ani słowem, i zamknął krok jako „niezweryfikowany". WhatsApp został na 26.33.73 przy dostępnym 26.34.72.

**Przyczyna źródłowa:** TOR 1 uruchamiał gołe `mas upgrade`, co każe `mas` samodzielnie wyliczyć zbiór nieaktualnych aplikacji — a pod `sudo` to wyliczenie dzieje się w kontekście roota, nie w tym, który przebieg zmierzył. W kodzie stał nawet `TODO(M17)` dokładnie o tym.

**Pomiar:** `mas upgrade 310633997` uruchomione jako użytkownik zakończyło się sukcesem w trzy sekundy — ta sama aktualizacja, którą ścieżka sudo pominęła.

**Naprawa:** TOR 1 przekazuje jawne ID zmierzone przez pre-skan, a to, co po nim nadal jest nieaktualne, dostaje **jeden** retry per ID w sesji wywołującego użytkownika. Paragony App Store i zalogowane Apple ID należą do użytkownika, nie do roota. Retry jest celowo jednorazowy — to fallback na niezgodność kontekstu, nie pętla; ostatnie słowo ma i tak końcowa kontrola kolejki.

### P1-4 — 26 kolejnych raportów maszynowych z pustym `counts`

`build_run_summary()` od zawsze przyjmował mapę `counts`, a wywołujący nigdy jej nie przekazał. Każdy `run_summary_*.json` na tej maszynie zawierał `"counts": {}`, choć krok 5 wypisywał te liczby dla człowieka tuż obok. Każda automatyzacja czytająca JSON musiała parsować log tekstowy. Krok 5 zapisuje teraz `run_counts.json` w katalogu sesji, a generator podsumowania go czyta.

### P1-5 — Inflacja ostrzeżeń

`IPMIView` i `DJI Assistant 2` nie mają auto-updatera. To trwały fakt o dostawcy, nie usterka przebiegu, a mimo to obniżał krok internetowy przy każdym uruchomieniu. Zdemowane do informacji — dokładnie tak, jak feed 404 Antigravity 2026-08-26. Ostrzeżenie, którego nikt nie może wyczyścić, to ostrzeżenie, które wszyscy nauczą się pomijać.

Analogicznie baner preflightu MAU: rozdzielony na to, co wymaga działania (kwarantanna `DeferralDays`, pin starszy od zainstalowanego), i na własną księgowość MAU.

### Zmiana konfiguracji — kanał MAU `Preview` → `Current`

Otwarta decyzja od 2026-08-19, zamknięta w tej sesji za zgodą właściciela. `ChannelName = Preview` przy Office zbudowanym dla `Current` było źródłem regresji z 2026-07-14, a więc i całej kwarantanny. Uwaga techniczna: `msupdate --config` w tym buildzie MAU (4.85.26080216) tylko **wyświetla** konfigurację — nie ustawia jej. Zmiana idzie przez `defaults write com.microsoft.autoupdate2 ChannelName -string Current`.

---

## 4. Weryfikacja na żywo

Trzy kolejne pełne przebiegi `update_internet_apps.sh` na maszynie referencyjnej:

| | przed (2026-09-01) | po |
|---|---|---|
| Ostrzeżenia w kroku internetowym | 8 | **0** |
| Exit code kroku | 10 (soft-fail) | **0** |
| Office | 16.112.2, wstrzymany | **16.112.3, „Microsoft 365 jest aktualny"** |
| Status Microsoft AutoUpdate | ⚠️ Wstrzymany — błąd pakietu dostawcy | ✅ Aktualny |
| WhatsApp | 26.33.73 (26.34.72 dostępne) | **26.34.72** |
| Pakiet testów | 189 | **213, zielone** |
| `shellcheck -S error` | 0 | 0 |
| gitleaks | czysto | czysto |

Pin `DeferralVersions.TEAMS21` został odtworzony przez MAU między przebiegami — dokładnie jak przewidywała diagnoza — i jest teraz raportowany jako informacja, bez zapisu do domeny i bez wpływu na status kroku.

---

## 5. Rekomendacje

### R1 — Zasada dla strażników: „tłumisz wejście, deklarujesz wygaszanie i sondę" *(wysoki priorytet)*

To drugi z rzędu review, w którym główny defekt to ta sama klasa: **system twierdzi coś, czego nie zmierzył**. W 1.4.2 były to zapisy raportowane bez odczytu żywej domeny. Tu — strażnik, którego dowód zwolnienia tłumi on sam.

Proponuję podnieść to do reguły nienegocjowalnej w `AGENTS.md`: *każdy mechanizm, który ukrywa własne wejście diagnostyczne, musi mieć zadeklarowane okno życia i drogę do ponownej oceny.* Kandydaci do przeglądu pod tym kątem: strażnik cofania wersji casków w `update_brew.sh`, logika `vendor_latest` oraz filtry pomijania w `update_npm_cli.sh`.

### R2 — Detektor chronicznych ostrzeżeń *(wysoki priorytet)*

20 kolejnych przebiegów `degraded` i nic nie eskalowało. Ostrzeżenie, które powtarza się N razy, przestaje być stanem, a staje się defektem — i powinno być inaczej raportowane niż ostrzeżenie nowe. Konkret: `run_summary_*.json` ma już wszystko, czego trzeba. Skrypt czytający ostatnie N podsumowań i zgłaszający „ten sam krok jest degraded od X przebiegów" złapałby kwarantannę Office po trzech dniach zamiast po siedmiu tygodniach. Naturalne miejsce: `scripts/report_chronic_warnings.sh`, wywoływane na końcu `update_all.sh`.

### R3 — Rozszerzyć `counts` o niepowodzenia, nie tylko sukcesy *(średni)*

Teraz `counts` mówi, ile pakietów się ruszyło. Nie mówi, ile *powinno* było się ruszyć. Dodanie `pending_after_run` na krok zamieniłoby raport maszynowy w coś, na czym da się oprzeć R2 bez parsowania logu.

### R4 — `mas` jako pojedynczy punkt awarii App Store *(średni)*

`mas account` nie działa na macOS 26.x (znany problem), a `mas outdated` i App Store GUI dają rozbieżne odpowiedzi — 2026-09-01 GUI mówiło „wszystko aktualne", gdy `mas` widział WhatsAppa. Obecna dwutorowość jest sensowna, ale rozbieżność między torami nie jest nigdzie zapisywana jako fakt. Warto ją logować do diagnostyki: to najlepszy dostępny sygnał, że jeden z torów kłamie.

### R5 — Martwy klucz konfiguracyjny *(niski)*

`.mac_update_prefs` zawiera `FIREFOX_DEV_CHANNEL_VERSION=150.0b10`, do którego żaden skrypt się nie odwołuje (zainstalowane jest 156.0). Do usunięcia albo do podłączenia jako cache kanału.

### R6 — Etykieta wersji Firefox Developer Edition *(niski)*

Przebieg pobrał `156.0b1` i zaraportował „zaktualizowany do wersji 156.0". Bundle rzeczywiście deklaruje `156.0`, więc porównanie jest poprawne, ale komunikat gubi informację o kanale. Warto pokazywać obie: `156.0 (kanał 156.0b1)`.

### R7 — Znany, nierozwiązany problem operacyjny *(średni, bez zmian)*

`brew upgrade --cask spotify` woła `sudo launchctl print gui/501/…`, co podnosi okno SecurityAgent. Pod `MAC_UPDATE_NONINTERACTIVE=1` bez terminala potrafi zablokować cały przebieg. Otwarte od 2026-08-26.

---

## 6. Czego celowo nie zrobiłem

- **Nie instalowałem Office ręcznie z pominięciem toolkitu.** Aktualizacja do 16.112.3 zeszła przez demona MAU po zdjęciu odroczeń, czyli tą drogą, którą naprawiony kod będzie chodził produkcyjnie.
- **Nie odwracałem reguły sudo dla `mas`.** Pomiar sugeruje, że sesja użytkownika działa lepiej, ale zmiana domyślnej ścieżki wymagałaby dowodu z wielu maszyn i wersji macOS. Fallback daje korzyść bez tego ryzyka.
- **Nie ruszałem `update_brew.sh` ani `update_npm_cli.sh`.** W logu 2026-09-01 oba kroki są `OK completed`; audyt pod kątem R1 to osobne zadanie z własną weryfikacją.

---

*Review wykonany na maszynie referencyjnej mac-r12-home, macOS 26.6.2 (25G83). Wszystkie liczby pochodzą z pomiaru systemu docelowego.*
