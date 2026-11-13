# Audyt nowych instalacji i wyboru źródła aktualizacji

Data: 2026-11-13. Status: diagnoza i projekt do akceptacji, bez wdrożenia.

Audytowana baza: `main`, `2378c9b17fbd15060420718e1d8b0308b4a66d66`, `VERSION=1.6.0`.
Odczyt zdalnego `main` wskazał ten sam commit. Zapytanie o zdalne tagi `v1.6*` nie zwróciło tagu. Numer w VERSION nie stanowi dowodu opublikowanego, tagowanego wydania ani identyczności paczki pobranej przez użytkownika.

Plan wykonawczy: [source-aware-inventory](../superpowers/plans/2026-11-13-source-aware-inventory.md).

## 1. Wniosek

Projekt ma wiele dobrych zabezpieczeń dla znanych aplikacji, ale jego model danych i raportowanie nadal zakładają zestaw aplikacji z konfiguracji autora. Obsługa obcego Maca wymaga rozdzielenia:

1. **Katalogu możliwości:** jakie aplikacje i mechanizmy projekt umie obsłużyć.
2. **Obserwacji lokalnych:** jakie konkretne instalacje istnieją na tym Macu i skąd to wiadomo.
3. **Polityki użytkownika:** na jakie działania wobec tych instalacji użytkownik się zgodził.
4. **Wyniku działania:** co rzeczywiście sprawdzono, zmieniono, odroczono lub pominięto.

Wpis w katalogu nie dowodzi instalacji. Obecność instalacji nie upoważnia do zmiany kanału. Wykryty framework aktualizacyjny nie dowodzi, że można bezpiecznie uruchomić jego aktualizator.

Najbardziej prawdopodobnym wyjaśnieniem aplikacji pojawiających się podczas `update_all.sh` jest przechodzenie przez stały katalog handlerów i drukowanie nagłówków także dla nieobecnych aplikacji. Istnieje też rzeczywisty błąd generujący ostrzeżenia o brakującym casku dla nieobecnych aplikacji i instalacji App Store. Bez logu z drugiego Maca nie przypisujemy temu zdarzeniu wszystkich usterek znalezionych w audycie.

Zgłoszenie doprecyzowano: komunikaty wystąpiły podczas `update_all.sh` po zbudowaniu inventory; pojawił się również błąd dotyczący niezainstalowanego caska. To jest zgodne z F02, ale bez logu nie ustalamy konkretnego tokena ani dokładnego tekstu błędu.

Nie znaleziono dowodu, że zwykły czysty klon pobiera prywatny inventory autora. `APPLICATIONS.md` i `UPDATES.md` nie są śledzone przez Git. Istnieją jednak warunkowe ścieżki mogące przywrócić usuniętą aplikację; absolutnej obietnicy „nigdy niczego nie doinstaluje” obecny kod nie uzasadnia.

## 2. Zakres i metody

- Przegląd instalatora, setup, inventory, aktualizacji App Store/Homebrew/internet/CLI, wspólnych zabezpieczeń, raportów, testów i CI.
- Pełny `bash run_tests.sh`, osobny warning-level ShellCheck wszystkich śledzonych skryptów, kontrola Git i zdalnego main/tagów.
- Reprodukcje wyłącznie na syntetycznych danych i funkcjach bez skutków systemowych.
- Porównanie z dokumentacją Homebrew, mas, Apple i Sparkle.
- Orkiestra: Astra jako koordynator; dwa zadania audytowe dla GPT-6.1 Sol/high, z krótkimi zadaniami uzupełniającymi. Koordynator sam przeczytał kluczowe warunki i odtworzył najważniejsze przypadki.
- Zastosowane procedury: ultra-review, systematic-debugging, brainstorming, writing-plans; wyszukanie procedur w hubie i w publicznym źródle Superpowers. Nie instalowano ani nie aktywowano nowych skills.
- Nie uruchamiano rzeczywistego setup, update_all, instalacji, odinstalowania, zamykania aplikacji, zmiany PAM ani rebootu. Testy nie zastępują próby na czystym koncie/macOS.

Przegląd nie jest kompletnym pentestem każdego handlera i `dev_sync`. Istniejące testy tego ostatniego uruchomiono w pełnym zestawie. Audyt prywatnego systemu pamięci nie jest miarą jakości tego produktu; jego diagnostyka pozostaje poza tym publicznym raportem.

## 3. Pomiary

| Pomiar | Wynik i ograniczenie |
|---|---|
| Git | lokalny HEAD i zdalny main zgodne; przed pracą brak zmian w plikach śledzonych, istniejący nieśledzony materiał pozostawiono bez zmian |
| Bash | 3.2.57; składnia wszystkich skryptów przeszła |
| Python | 3.15.2 w tym uruchomieniu; moduły i heredoki skompilowane |
| Pełne unittest | 846 wykonanych w 265.432 s, 843 bez zgłoszonego failure, 3 failures; brak raportowanych skips/errors |
| Wynik run_tests | exit 1, zestaw nie jest zielony |
| Błędy | `test_deepseek_grokbot.DispatchTests`: `test_current_is_verified_without_launching`, `test_behind_is_reported_without_installing_in_dry_run`, `test_running_app_is_never_launched_or_replaced` |
| Charakter błędów | oczekiwane wersje fixture różnią się od wersji otrzymanych przez handler; szczegóły izolacji poniżej |
| ShellCheck | wszystkie śledzone `.sh`, `--severity=warning`, bez diagnostyki |
| Gitleaks | 209 commitów, brak wykrytych sekretów; kontrola zabronionych plików śledzonych przeszła |
| Harmonogram na hoście audytu | zapytanie launchctl nie znalazło etykiety `macos-updates`; nie mówi to nic o komputerze nowego użytkownika |
| CI | pliki workflow przeczytane; zdalnych wyników Actions nie odświeżano, nie twierdzimy, że aktualny CI jest zielony |

Powyższa liczba testów jest wynikiem wykonania, a nie tylko kolekcji. Komunikaty testowych fixture o błędach zapisu nie stanowią dowodu problemu z dyskiem hosta.

## 4. Ustalenia z dowodami

Skala: P0 to potwierdzone, pilne ryzyko integralności lub bezpieczeństwa; P1 blokuje szerokie wdrożenie dla nowych użytkowników; P2 oznacza istotną poprawę odporności lub czytelności. W audytowanym zakresie nie potwierdzono P0. „Kod” oznacza analizę osiągalnej ścieżki, nie realną instalację.

### F01. P1: katalog obsługi przecieka do przebiegu aktualizacji

`update_internet_apps.sh:542` uruchamia dispatch katalogu. Przykładowo `lib/internet_handlers.sh:256` drukuje nagłówek przed ustaleniem obecności, a `:285` komunikuje brak aplikacji. Dedykowane handlery robią podobnie, np. `lib/internet_app_updates.sh:426,450`.

Istotne rozróżnienie: końcowa tabela **już filtruje nieobecne aplikacje**, `lib/internet_status.sh:96-105`. Nie należy usuwać tego zabezpieczenia ani błędnie opisywać całego podsumowania jako bezwarunkowej listy wszystkich aplikacji. Problem obejmuje wcześniejszy przebieg i niezależne agregacje statusów.

Naprawa: wybrać lokalne instalacje przed dispatch i przed drukowaniem sekcji. Nieobecne pozycje tylko w jawnym trybie diagnostycznym/katalogu. Brak aplikacji nie jest ostrzeżeniem.

### F02. P1: fałszywy konflikt App Store/Homebrew i ostrzeżenia dla nieobecnych aplikacji

`config/internet_app_methods.txt:54` przypisuje CapCut do `brew_cask`, a `config/internet_dispatch_order.txt:37` wyłącza jego handler komentarzem o migracji do Homebrew. Normalny run zaczyna więc z `STATUS_CAPCUT=managed_brew` (`update_internet_apps.sh:518`), bez rozpoznania źródła tego bundle. Następnie `:679-692` ustawia status brakującego caska bez sprawdzenia faktycznego kanału ani obecności aplikacji. `:1005` zalicza go do soft failure. Plik statusów także powstaje dla całego katalogu (`:811-819`).

Ogólny handler posiada ochronę receipt (`lib/internet_handlers.sh:262-267`), a wywołany bezpośrednio `iu_capcut` z niej korzysta. Nie wolno jednak utożsamiać takiego testu funkcji z normalnym przebiegiem: CapCut nie jest w nim dispatchowany. Ponadto późniejsza walidacja casków nadpisałaby także poprawny status MAS. Statyczna kolejność dispatch utrwala kanał wybrany na komputerze autora.

To daje dwa przypadki: MAS CapCut staje się „cask missing”; całkowicie nieobecna aplikacja może również pogorszyć wynik kroku. Nie jest to dowód jej instalacji. Raport coverage ma podobną niespójność: `scripts/report_update_coverage.sh:553-555` uznaje skonfigurowany `brew_cask` za zarządzany przez Homebrew nawet bez znalezionego tokena.

Naprawa: wspólny resolver źródła i wynik `not_installed`/`source_unknown`/`source_conflict`. Konfiguracja możliwości nie może nadpisywać lokalnego źródła.

### F03. P1: ochrona przed utratą inventory utrwala stare wpisy

`lib/python/inventory_sync.py:976,1040,1065,1091` blokuje przejście wcześniej niepustych grup MAS/formula/cask/CLI do pustych. Kod nie odróżnia poprawnego pustego skanu od awarii źródła w tej decyzji. Analogiczna blokada występuje dla grupy 3 w `:1012`.

Reprodukcja syntetyczna: poprawne `mas={}` pozostawia stary wiersz i zwraca `skipped_groups=['GRUPA 2']`. Subagent odtworzył to również dla pozostałych grup. Testy starego zachowania trzeba świadomie zastąpić testami kompletności, a nie tylko usunąć guard.

`update_all.sh:870-879` używa istniejącego pliku; pusty szablon powstaje wyłącznie przy jego braku. Stary/kopiowany plik nie staje się automatycznie nowym inventory innego Maca.

Naprawa: jawny wynik skanu i pochodzenie snapshotu. Sukces z kompletnym pokryciem pozwala usunąć nieobecne wpisy; błąd zachowuje ostatnią obserwację jako nieaktualną. Obcy plik jest materiałem migracyjnym, nie dowodem instalacji.

### F04. P1: nazwa jest używana jako tożsamość aplikacji

`lib/python/inventory.py:22-24` traktuje ChatGPT i Codex jako aliasy. Reprodukcja `row_exists('| ChatGPT | 1 | fixture |', 'Codex')` zwraca `True`. `:484-500` przechowuje jedną ścieżkę na nazwę; dwa syntetyczne bundle o tej samej nazwie w dwóch katalogach dały jeden rekord.

Naprawa: rekord konkretnej instalacji z canonical path, bundle ID, Team ID i zakresem użytkownika. Bundle ID też nie jest samodzielnie unikalny, bo mogą istnieć dwie kopie. Alias nazwy ma służyć prezentacji/wyszukiwaniu, nie przyznaniu prawa do aktualizacji.

### F05. P1: Homebrew może wybrać bundle zastąpiony wersją App Store

`update_brew.sh:424-487` sprawdza ścieżkę, wersję i działający proces, ale nie receipt ani zgodność właściciela instalacji. Stary rekord caska oraz bundle o tej samej nazwie z App Store mogą trafić do `brew upgrade --cask` w `:519`.

Potwierdzono lukę kwalifikacji, nie wykonano podmiany przez rzeczywiste Homebrew. Zabezpieczenie App Store w handlerze internetowym nie chroni wcześniejszego kroku brew.

Naprawa: konflikt blokuje oba automatyczne kanały do decyzji. Nie odinstalowywać starego caska automatycznie, ponieważ jego uninstall może dotknąć obecnego bundle.

### F06. P1: obecność jednej aplikacji nie chroni wszystkich artefaktów caska

`lib/python/brew_casks.py:139-156` odrzuca cask tylko wtedy, gdy nie istnieje żaden target. `update_brew.sh:429-431` wybiera pierwszy obecny target. Syntetyczny cask zawierający `Present.app` i `Absent.app` pozostaje kandydatem. Caski pkg bez targetów przechodzą inną ścieżką w `:473-476` bez pełnego dowodu obecności aplikacji.

Aktualizacja całego pakietu może odtworzyć usunięty komponent lub dodać nowy. Nie uruchamiano takiego instalatora. Dodatkowo kwalifikacja casków jest zbiorcza: po sprawdzeniu procesów następuje batch `:519`, bez ponownego sprawdzenia każdego elementu bezpośrednio przed jego wykonaniem.

Naprawa: plan skutków na poziomie artefaktów, deferral niejednoznacznych pkg, indywidualne wywołania z ponowną weryfikacją. Zależności i wbudowane komponenty aktualizowanego pakietu trzeba jawnie odróżnić od nowych samodzielnych aplikacji.

### F07. P1: usunięcie aplikacji podczas pobierania może zostać cofnięte

`update_internet_apps.sh:244` uznaje nieobecny cel za bezczynny. `:300` pomija porównanie tożsamości, gdy cel nie istnieje, a `:322` przenosi tam pobrany bundle. Aplikacja obecna przy wyborze, ale usunięta przed kopiowaniem, może zostać utworzona ponownie.

Naprawa: wymagaj obecności i zgodności pierwotnego obiektu przy zatwierdzaniu transakcji. Zniknięcie daje `removed_since_scan`, nie ścieżkę instalacji. Dziennik transakcji musi również obsłużyć przerwanie procesu między backup a swap.

### F08. P1: onboarding zmienia system szerzej, niż wynika z samego inventory

`install.sh:123-124` wymusza nieinteraktywny setup. `setup.sh:437-445` wybiera wtedy instalację Homebrew, `:495-499` instaluje brakujące mas, `:535-539` Python. `update_appstore.sh:105-108` także instaluje brakujące mas podczas aktualizacji.

`install.sh:126-128` automatycznie wywołuje konfigurator Touch ID. `scripts/setup_touchid_sudo.sh:183-194` może nadpisać istniejący `sudo_local`; backup nie jest obowiązkowo sprawdzany przed nadpisaniem. Brak osobnej zgody na taką zmianę to problem również wtedy, gdy sudo poprosi o hasło.

Naprawa: tryb inspekcji bez instalowania zależności; świadomy wybór zależności i zmian profilu. PAM/Touch ID tylko jako osobna, wyraźnie uruchomiona funkcja, poza zwykłym onboardingiem. Noninteractive oznacza bezpieczne pominięcie, nie automatyczne „tak”.

### F09. P1: testy nie dają obecnie czystej, deterministycznej bramki

Trzy failures w pełnym zestawie dotyczą różnicy między oczekiwanymi fixture a otrzymanymi wersjami DeepSeek/Grok Bot. Oczekiwano odpowiednio `0.2.2-rc.1` i `0.79.3`, otrzymano `0.2.2-rc.3` i `1.0.3`.

Przyczyna potwierdzona bez ponawiania pobrań: `tests/test_deepseek_grokbot.py:148` definiuje atrapę `vendor_feed_fetch`, ale `:151` ładuje `internet_app_updates.sh`. Ten ponownie ładuje `vendor_feeds.sh` w `:11-14`, nadpisując atrapę rzeczywistym pobieraniem `vendor_feeds.sh:34-43`. Porównanie definicji funkcji przed i po source potwierdziło zmianę. Runner blokuje część natywnych narzędzi, ale lista w `run_tests.sh:119` nie obejmuje curl. Ubuntu workflow uruchamia unittest bez tego runnera (`.github/workflows/ci.yml`).

Naprawa: wspólna bramka hermetyczna na macOS/Linux, kontrolowane fixture sieci, awaria na niezamockowany dostęp. Nie „naprawiać” asercji wpisaniem dzisiejszych wersji producenta.

### F10. P1: sprawdzanie hosta pobrania ma błąd parsera

`lib/vendor_direct.sh:158-161` rozcina authority po dwukropku. Syntetyczny URL `https://trusted.example:ignored@evil.example/payload.zip` przechodzi sprawdzenie dla `trusted.example`, choć właściwym hostem jest `evil.example`. `lib/fetch.sh:21` ogranicza przekierowania do HTTPS, lecz nie do zatwierdzonych hostów.

Nie dowodzi to dowolnego wykonania kodu: późniejsze kontrole podpisu, bundle ID i Team ID nadal ograniczają podmianę. Jest to jednak niewłaściwa granica zaufania, szczególnie przed rozszerzeniem automatycznej obsługi nowych feedów.

Naprawa: parser URL, zakaz userinfo, polityka portów i każdego przekierowania, jawne hosty CDN. Nie otwierać automatycznie URL wyczytanego z dowolnego bundle ani traktować go jako instrukcji.

### F11. P2: niepełne źródła gubią aplikacje albo wprowadzają fałszywą pewność

- `inventory.py:491-500` pomija błędy odczytu katalogów bez raportowania kompletności.
- `inventory_sync.py:906-930` może zamienić nieudany skan iPad w pustą listę i usunąć poprzednie wpisy.
- `update_all.sh:902-905,938-939` pomija aplikację z receipt w discovery, podczas gdy jej wpis MAS zależy od wyniku mas. Aplikacja pominięta przez Spotlight/mas może zniknąć z inventory.
- `inventory_sync.py:667-669` uznaje każdą pozycję katalogu za obecną przy pustym `installed_names`. Reprodukcja z `NotInstalledFixture|sparkle` wpisuje tę aplikację do legendy automatycznych aktualizacji.
- `gather_facts` w `inventory_sync.py:883-893` uznaje caski za nieosierocone również po nieudanej inspekcji metadanych.

Naprawa: metadane stanu każdego źródła i każdego skanowanego katalogu; degradacja bez fałszywego „aktualne” i bez ukrywania lokalnie zaobserwowanych bundle.

### F12. P2: systemowe aplikacje, nieznane bundle i nazwy casków są grupowane niespójnie

Grupa 1 nie ma synchronizacji członkostwa; `update_all.sh:1917-1933` tylko odświeża wersje istniejących wierszy. Domyślne rooty nie obejmują `/System/Applications`. Pozostałe nieobsłużone aplikacje wpadają do grupy 3 (`:1223-1285`), nawet gdy źródło jest nieznane. Caski są dopasowywane także po tokenie/nazwie (`:1292-1318`, `inventory_sync.py:1000-1003`), a nie jednym modelem artefaktów.

`inventory.py:48-52` oraz `update_all.sh:936` wykluczają aplikacje po fragmencie nazwy, np. Agent/Launcher. To heurystyka, która może ukryć pełnoprawną aplikację. Skan jest płytki i nie obejmuje wszystkich zagnieżdżonych folderów.

Naprawa: odrębne source, capability i parent-component. Systemowe aplikacje grupować na podstawie chronionej lokalizacji i tożsamości, nie samego prefiksu `com.apple`. Nieznane pozostawić widoczne jako nieznane.

### F13. P2: wykrywanie updatera już istnieje, ale nie jest wspólnym modelem obsługi

`inventory.py:443-481` bez uruchamiania aplikacji rozpoznaje receipt, SUFeedURL, Electron app-update.yml i frameworki Squirrel/Sparkle. To dobra baza. Dziś wynik trafia głównie do notatki w Markdown. Coverage, dispatch i synchronizacja utrzymują osobne klasyfikacje.

Naprawa: wspólny resolver i stopnie możliwości: inventory, check-only, native/manual, reviewed-direct. Sam SUFeedURL nie jest dowodem bezpiecznej instalacji ani zgodności kanału stable/beta/TestFlight.

### F14. P2: ~/Applications jest wykrywane, ale nie w pełni aktualizowane

`internet_app_path` potrafi znaleźć aplikację użytkownika. `lib/vendor_direct.sh:214-218` jednak odmawia bezpośredniej instalacji poza `/Applications`; `copy_verified_app` ma stały cel w `update_internet_apps.sh:264`.

Prześledzenie wywołań nie potwierdziło tworzenia duplikatu home-only bundle przez tę ścieżkę: zewnętrzny guard wcześniej ją blokuje. To luka pokrycia, nie dowiedziony duplikat. Rozszerzenie musi zachować rzeczywistą ścieżkę instalacji i nigdy „naprawiać” jej przeniesieniem do `/Applications`.

### F15. P2: gotowość dla wielu użytkowników wymaga dodatkowych granic

`lib/run_lock.sh:4-6` blokuje pojedynczy checkout, nie dwa klony operujące na tych samych aplikacjach. Globalna migracja Node/native CLI, czyszczenie duplikatów i aplikacje zarządzane administracyjnie wymagają osobnej polityki użytkownika; nie należy utożsamiać zwykłej aktualizacji ze zgodą na przejęcie kanału lub usuwanie alternatywnej instalacji.

Dla przyszłego wdrożenia: blokada per użytkownik oraz per zasób, bezpieczny no-TTY, rozpoznanie uprawnień, jawna obsługa nieznanej polityki MDM. Nie twierdzimy, że narzędzie umie dziś wiarygodnie wykryć wszystkie przypadki zarządzania firmowego.

## 5. Co działa i warto zachować

- Internetowe handlery sprawdzają obecność aplikacji; ogólna ścieżka uwzględnia receipt App Store.
- Wspólne kopiowanie ma sprawdzanie podpisu/Gatekeeper, porównanie bundle ID i Team ID, staging, rollback i ponowny pomiar uruchomionego procesu. Poprawki powinny uszczelnić te mechanizmy.
- Standardowa obsługa casków odrzuca część osieroconych rekordów i nie aktualizuje aplikacji rozpoznanych jako działające.
- Native CLI mają ograniczenia installed-only i jawne `--bootstrap-cli`; nie należy rozszerzać bootstrapu przez zwykłe `-y`.
- Rozpoznawanie mechanizmów aktualizacji z metadanych jest statyczne i sanitizuje zapis do tabeli.
- Statusy odróżniają wynik zweryfikowany, niezweryfikowany, stale feed, etapowe udostępnianie i odroczenie.
- Inventory zapisuje się atomowo; pliki prywatne są gitignored, CI kontroluje zakazane pliki.
- Testów jest dużo i obejmują wartościowe scenariusze. Potrzebują nowej osi: różne profile nowego Maca i dowód braku skutków ubocznych.
- CI ma ograniczone triggery, cancellation i timeouty; macOS jest manual/tag-only. Plan nie wymaga nowych harmonogramów.

## 6. Benchmark dokumentacyjny

Źródła sprawdzone 2026-11-13. Poniższe wnioski opisują projekt, nie są zgodą na wykonanie poleceń z dokumentacji.

| Źródło | Wniosek projektowy |
|---|---|
| [Homebrew manpage](https://docs.brew.sh/Manpage) i [Tips and Tricks](https://docs.brew.sh/Tips-and-Tricks) | `--adopt` jest zmianą zarządzania, nie odczytem inventory. Nie używać automatycznie ani jako lekarstwa na konflikt MAS. Semantyka auto_updates zmienia się między wersjami brew; badać możliwości i testować wyjścia obsługiwanych wersji. |
| [mas README](https://github.com/mas-cli/mas/blob/main/README.md) | Wykrywanie opiera się na Spotlight. Brak wyniku mas nie dowodzi braku bundle. Korzystać ze strukturalnego wyjścia i kontrolować kompletność; odróżniać aktualizację od install/get. |
| [Apple receipt fields](https://developer.apple.com/library/archive/releasenotes/General/ValidateAppStoreReceipt/Chapters/ReceiptFields.html) i [appStoreReceiptURL](https://developer.apple.com/documentation/foundation/bundle/appstorereceipturl) | Receipt to dowód wymagający interpretacji, nie autoryzacja instalacji; także TestFlight wymaga odróżnienia. Nie odczytywać konta użytkownika ani nie wysyłać receipt do serwisu w ramach discovery. |
| [Sparkle publishing](https://sparkle-project.org/documentation/publishing/) i [security](https://sparkle-project.org/documentation/security-and-reliability/) | Feed to tylko część protokołu: podpis, kanał, system, architektura, rollout i właściwy typ paczki. Preferować natywny updater tam, gdzie nie umiemy odtworzyć pełnej walidacji. |
| [Superpowers](https://github.com/obra/superpowers) | W audycie wykorzystano lokalne, przypięte procedury diagnozy i planowania. Nie było potrzeby instalować dodatkowych procedur z sieci. |

## 7. Ocena ilościowa

Oceny są ekspercką oceną dojrzałości, nie prawdopodobieństwem awarii ani certyfikacją. 0 oznacza brak mechanizmu, 5 częściowe zabezpieczenia z udokumentowanymi lukami, 10 udowodnione wymagania w reprezentatywnych profilach. Nie liczymy średniej: bezpieczeństwo wykonania nie może być kompensowane liczbą testów.

| Wymiar | /10 | Uzasadnienie |
|---|---:|---|
| Rozdzielenie katalogu i lokalnego stanu | 4 | prywatny plik oddzielony od Git, ale dispatch/statusy nadal katalogowe |
| Tożsamość i źródło instalacji | 3 | receipts i podpisy istnieją, brak wspólnego resolvera, aliasy scalają produkty |
| Poprawność synchronizacji | 4 | atomowy zapis, lecz empty/error i tożsamość hosta nie są rozdzielone |
| Bezpieczeństwo wykonania | 6 | podpisy, procesy i rollback, ale race oraz luki casków |
| Nieinwazyjny onboarding | 3 | automatyczne zależności, profil i PAM |
| Obsługa nieznanych aplikacji | 4 | dobry detektor metadanych, brak spójnej polityki możliwości |
| Odporność na brak sieci/uprawnień | 6 | timeouty, soft failures i cache, ale niepełne source status |
| Sekrety i prywatność produktu | 7 | scan czysty, inventory poza Git; diagnostyka i nowe snapshoty wymagają utrzymania granic |
| Testy i CI | 6 | 846 testów, 3 failures, niepełna izolacja sieci i różne runnery |
| Odtwarzanie po awarii | 6 | rollback kopiowania istnieje, brak pełnego dziennika przerwanej transakcji |
| Uczciwość raportowania | 5 | dobre rozróżnienie verified/stale, lecz fałszywe cask warnings i status bez źródła |
| Dokumentacja i gotowość wydania | 6 | obszerna dokumentacja, installed-only wymaga doprecyzowania, brak zdalnego tagu v1.6* |

Kategorie ultra-review dotyczące pamięci agentów i adopcji MCP nie są kryteriami działania aktualizatora; nie nadano im sztucznych ocen produktu.

## 8. Specyfikacja docelowa

### Rekomendowane rozwiązanie

Wdrożenie stopniowe: krótki pakiet napraw P1, potem wspólny snapshot i resolver, następnie migracja raportowania oraz kontrolowane rozszerzenie obsługi. Pełne przepisanie silnika od razu zwiększa ryzyko; samo łatanie Markdown nie rozwiązuje tożsamości, źródeł i zgód.

```mermaid
flowchart LR
  A[Odczyt lokalnych instalacji] --> B[Snapshot z dowodami i kompletnością]
  C[Katalog obsługiwanych mechanizmów] --> D[Resolver źródła i możliwości]
  B --> D
  E[Lokalne wybory użytkownika] --> F[Plan działań]
  D --> F
  F --> G[Sprawdzenie zgody i ponowny odczyt celu]
  G --> H[Wykonanie jednego działania]
  H --> I[Weryfikacja rzeczywistego wyniku]
  B --> J[Inventory i raport]
  I --> J
```

### Zasady zachowania

1. Nowo wykryta aplikacja zawsze trafia do inventory, również gdy updater jest nieznany, mas nie działa lub jej nazwa zawiera „Agent”. Pomocnicze bundle są relacją do aplikacji nadrzędnej, nie regułą kasowania po nazwie.
2. `source` i `update_capability` to osobne pola. Aplikacja pobrana ręcznie może mieć Sparkle, a zainstalowany cask może aktualizować się sam.
3. Dowód receipt blokuje zewnętrzną podmianę. Samo istnienie katalogu receipt nie dowodzi poprawnej aktualizacji MAS. Niejasny receipt/TestFlight oznacza kontrolowane odroczenie.
4. MAS-only CapCut: zachować App Store, bez pytania o instalację brew. MAS plus stale cask: wyjaśnić konflikt i zapytać o pozostawienie App Store, odroczenie lub instrukcję ręcznej migracji. Domyślne: bez zmian. Usunięcie caska nie jest automatycznym sposobem zachowania App Store.
5. Nieznana aplikacja: inventory automatyczne, propozycja read-only check po rozpoznaniu mechanizmu. Pierwsze uruchomienie native updatera wymaga jawnej zgody; nie testować aplikacji przez jej uruchamianie.
6. Preferencje zapamiętywać dla konkretnej instalacji/tożsamości. Zmiana źródła, podpisu, ścieżki lub kanału unieważnia właściwą zgodę. `-y` nie rozstrzyga konfliktów, nie migruje kanału i nie włącza nowych uprawnień.
7. Nieinteraktywny run odkłada pytania i kontynuuje niezależne bezpieczne działania. Oczekiwane „ręcznie/ignoruj” nie jest chronicznym błędem; realna awaria źródła pozostaje widoczna.
8. Udany kompletny skan może stwierdzić brak; nieudany zachowuje ostatni stan jako stale. Żaden brak obserwacji nie daje zgody na instalację.
9. Aktualizacja działa tylko na istniejącym celu, w dotychczasowym kanale i lokalizacji. Nie przywraca usuniętych aplikacji i nie przenosi ich z katalogu użytkownika.
10. Pakiet może potrzebować nowych zależności lub wewnętrznych komponentów. Plan jawnie opisuje ten zakres; nowe samodzielne aplikacje i nieznane skutki pkg wymagają decyzji. Nie obiecywać kontroli, której zewnętrzny instalator nie oferuje.
11. Bez automatycznej telemetrii. Propozycja nowej recepty jest lokalna, eksport po podglądzie, bez receipt, nazw użytkowników, pełnych ścieżek i sekretów z URL. Nie wysyłać niczego automatycznie do AI, GitHub ani producenta.
12. Autoadaptacja jest deterministyczna i ograniczona do dowodów. Runtime nie pisze ani nie wykonuje kodu wygenerowanego przez AI. Nowy adapter instalacyjny wymaga osobnego przeglądu i fixture.

### Poziomy obsługi i wynik dla użytkownika

| Poziom | Co wolno | Czego nie obiecuje |
|---|---|---|
| inventory-only | wykryć, przypisać dowody, pokazać instrukcję | aktualizacji ani najnowszej wersji |
| check-only | odczytać zatwierdzony feed, porównać zgodne wersje | instalacji paczki ani pełnego wsparcia updatera |
| native-managed | użyć istniejącego managera/updatera według zgody | sukcesu bez pomiaru wersji po działaniu |
| reviewed-direct | pobrać i wymienić istniejący bundle po pełnej walidacji | bezpiecznej obsługi dowolnego URL/pkg |

Przykładowy konflikt: „CapCut wykryto jako instalację App Store. Homebrew ma również rekord tej aplikacji. Aktualizację wstrzymano. Zalecane: zachowaj App Store; rekord Homebrew pozostanie bez zmian do osobnego przeglądu”.

### Poza pierwszym wdrożeniem

Brak automatycznej konwersji App Store do brew, generycznego wykonawcy PKG, samoczynnego `brew --adopt`, globalnego skanowania całego dysku, nowej usługi w tle, nowych cronów i masowego przepisywania wszystkich handlerów. Wsparcie Intel pozostaje poza kontraktem.

## 9. Granice pewności i warunki akceptacji

Nie badano paczki ani logu z komputera zgłaszającego. Nie wykonano prawdziwej podmiany MAS/brew ani prób na nowym koncie. Nie potwierdzono zgodności wszystkich wersji macOS, mas i Homebrew. To obowiązkowe osobne bramki przed szerokim wydaniem, opisane w planie.

Akceptacja tego dokumentu oznacza zgodę na zakres projektu i kolejność prac. Nie oznacza uruchomienia aktualizacji na komputerze właściciela, publikacji, merge ani deployu. Kod ma być wdrażany dopiero po zgodzie na plan.

## 10. Rozszerzenie zamówione podczas audytu: opcjonalny katalog instalacji

Właściciel poprosił także o możliwość wybrania dodatkowych aplikacji i wymagań podczas setupu. To uzasadniona, odrębna funkcja produktu: **aktualizacja obecnego oprogramowania** oraz **świadomie wybrana instalacja nowego oprogramowania** mają różne uprawnienia i plany wykonania. Skan inventory nie staje się listą zakupową ani instalatorem.

Rekomendowany przepływ: skan lokalny, menu „Przeglądaj aplikacje”, wybór konkretnych pozycji i kanałów, podgląd aplikacji oraz zależności, jawne zatwierdzenie, wykonanie i ponowny skan. Domyślnie wszystkie nowe pozycje są niezaznaczone. Wyjście z menu, `-y`, noninteractive albo samo pobranie repo nie uruchamia instalacji.

Katalog pokazuje źródło, status na tym Macu, zakres wsparcia i dowód weryfikacji. Trzeba rozróżnić co najmniej: „obsługa w kodzie”, „aktualizacja potwierdzona w rzeczywistym run”, „świeża instalacja potwierdzona” i „wymaga ręcznej instalacji”. Dowód zawiera datę, kanał, wersję aplikacji, architekturę/macOS i publiczny zanonimizowany rekord. Test aktualizacji na jednej maszynie nie dowodzi świeżej instalacji, wszystkich kanałów ani wszystkich Maców.

Read-only przegląd bieżącego źródła landing pokazał liczbę **47 obsługiwanych aplikacji** (`src/lib/site.ts`) oraz copy o aktualizowaniu tylko istniejących programów (`src/i18n/locales/en.json:98,232,394`). Nie należy interpretować tej liczby jako 47 sprawdzonych fresh installs. Landing jest w trakcie niezależnych zmian; w tej sesji go nie modyfikowano. Przy wdrożeniu katalogu potrzebna będzie synchronizacja EN/PL, FAQ, instrukcji instalacji, metadanych i plików LLM z precyzyjną obietnicą: zwykły update niczego nie doinstalowuje, opcjonalne menu instaluje wyłącznie zatwierdzone pozycje.

Wymagania przedstawiać jako graf zależności wybranych działań. Część jest niezbędna do konkretnej funkcji (np. Python do inventory), część tylko do wybranego kanału (np. mas/App Store, Homebrew/cask), a część opcjonalna (Rosetta dla wybranego zgodnego Intel-only app, Accessibility dla świadomie wybranej automatyzacji GUI). Brak zgody wyłącza tylko zależną funkcję. Nie instalować całego zestawu zależności katalogu, nie zmieniać PAM, kont, licencji ani polityki firmowej.

Pierwsza instalacja nie ma istniejącego podpisanego bundle do porównania. Musi mieć niezależnie zweryfikowaną receptę instalacji, oczekiwane tożsamości/artefakty i odrębny guard. Adapter sprawdzony wyłącznie do update pozostaje w katalogu informacyjnym. Dla App Store v1 menu otwiera oficjalną stronę po wyborze, użytkownik sam rozstrzyga logowanie, pobranie i zakup; program później sprawdza faktyczną obecność. Bez automatycznych zakupów i akceptowania umów. Generyczne PKG oraz dowolne skrypty z sieci nie stają się instalowalne na podstawie samej nazwy aplikacji.

Szczegóły wykonawcze i testy są w etapie E planu. To rozszerzenie pozostaje propozycją do akceptacji razem z resztą planu, nie zgodą na obecne instalacje na komputerze użytkownika.

## 11. Priorytet rekomendacji: najnowsza wersja stable

Właściciel doprecyzował cel: ustalać, który kanał najwcześniej dostarcza **latest stable**, i umożliwiać wybór tego kanału. Nie ma podstaw do uniwersalnej kolejności native, brew, npm, App Store. Cask może pobierać pakiet producenta i nadal używać natywnego updatera; npm często oznacza inny produkt CLI, nie alternatywną dystrybucję GUI. Źródło pierwszej instalacji i mechanizm kolejnych aktualizacji muszą być osobnymi polami.

Rekomendacja składa się z dwóch warstw:

1. Research każdej pozycji katalogu: oficjalne kanały, identyfikatory produktu/edycji, sygnatury, mapowanie wersji, sposób publikacji stable, kompatybilność i dostępne mechanizmy sprawdzania. Publiczne dowody w receptach; brak danych oznacza unknown, nie domysł.
2. Read-only sprawdzenie w setup albo na żądanie: która porównywalna, kompatybilna dystrybucja ma teraz najnowszą potwierdzoną stable. Odczyt metadanych, bez pobierania instalatorów do testu i bez uruchamiania aplikacji. Cache i błędy źródeł widoczne z datą.

Należy osobno wyświetlać: najnowszą globalną stable, najnowszą stable zgodną z tym Maciem i wersję aktualnie oferowaną w danym kanale. Beta/alpha/RC/nightly oraz niejasna etykieta latest nie kwalifikują się automatycznie. Numer wersji z innej edycji albo innego schematu nie dowodzi opóźnienia. App Store może zależeć od regionu, konta i sposobu udostępnienia; publiczne metadata nie gwarantują dostępności dla konkretnego konta.

Jeżeli kilka bezpiecznych kanałów udostępnia tę samą kompatybilną stable, rekomendacja zachowuje aktualny kanał. Jeżeli inny ma nowszą potwierdzoną stable, raport pokazuje różnicę i bezpieczną propozycję, ale nie migruje sam. Dla nowej instalacji użytkownik wybiera źródło w menu. Dla istniejącej potrzebny jest osobny plan migracji; pierwsza wersja funkcji pokazuje instrukcję, nie odinstalowuje programu i nie przenosi danych automatycznie.

Jednorazowy pomiar odpowiada na „kto ma teraz latest stable”, nie „kto zawsze jest najszybszy”. Trend opóźnień wymaga historii dopasowanych wydań i znanych czasów publikacji/obserwacji. Należy podawać liczbę obserwacji i niepewność; nie zastępować brakujących dat zerowym opóźnieniem. Historia zbierana lokalnie podczas zwykłych, uruchomionych przez użytkownika sprawdzeń; bez nowego harmonogramu ani telemetrii.

Potwierdzenia dokumentacyjne: [Homebrew Cask Cookbook](https://docs.brew.sh/Cask-Cookbook) opisuje auto-updating casks, więc brew i native updater nie muszą być konkurencyjnymi kanałami. [Apple release options](https://developer.apple.com/help/app-store-connect/manage-your-apps-availability/select-an-app-store-version-release-option) pokazuje, że termin udostępnienia zależy również od decyzji producenta. [Apple Search API](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/) umożliwia publiczny lookup, ale dokumentacja jest archiwalna i wymaga adaptera testowanego na rzeczywistych formatach. Żadne z tych źródeł nie uzasadnia twierdzenia, że App Store zawsze publikuje później.

Research wszystkich aplikacji nie został wykonany w tym audycie. Jest konkretnym zadaniem etapu E, wymaganym przed pokazaniem rekomendacji jako sprawdzonej. Dotychczasowe dowody aktualizacji pozostają wartościowe i będą użyte jako punkt startowy, z zachowaniem ich daty i zakresu.
