# Weryfikacja receptur i szybsze natywne aktualizacje: plan wdrożenia

> **For agentic workers:** Use subagent-driven-development or executing-plans after approval. Zachowaj tryb orkiestra, rozdziel własność plików i wykonaj jeden wspólny przegląd bezpieczeństwa przed aktywacją adapterów.

**Goal:** Włączać aktualizacje i pierwsze instalacje pojedynczych, zweryfikowanych produktów po odpowiedniej zgodzie, kończąc oczekiwanie na rzeczywistym sygnale gotowości zamiast po stałym opóźnieniu.

**Architecture:** Wspólny profil produktu i osobne dowody dla check/update/install/launch/restart. Rejestr wykonawców mapuje zamknięte identyfikatory na kod, bez poleceń shell z JSON. Dziennik stanów i ponowna obserwacja celu pozostają nadrzędne względem exit code updatera.

**Tech Stack:** Bash 3.2, Python 3.9+, standard library, obecny JSON inventory, polityki, blokady i transakcje. Sparkle CLI lub inne narzędzie jest osobno wersjonowanym i weryfikowanym wymaganiem, nie zależnością instalowaną w tle.

**Spec:** [Ustalenia i źródła](../../catalog/RECIPE_VERIFICATION_RESEARCH_2026-11-14.md), [stan 1.7.0](../../implementation/FINAL_1.7.0.md), [wcześniejszy plan](2026-11-13-source-aware-inventory.md). Data planu: 2026-11-14. To propozycja do zatwierdzenia, a nie wykonana aktywacja receptur.

## Global Constraints

- Apple Silicon arm64, macOS 13-27, Bash 3.2, Python 3.9+, exit 0/10/1 i addytywna zgodność summary v4.
- W obecnym zadaniu: bez prawdziwych aktualizacji, instalacji, uruchamiania i zamykania aplikacji na komputerze właściciela. Testy lokalne wyłącznie przez guard runner, fixture i tymczasowe katalogi.
- Zgoda na aktualizację istniejącej aplikacji nie zezwala na instalację nieobecnej, migrację źródła, instalację dodatkowych zależności, zmianę kanału ani restart sesji użytkownika.
- Stable jest domyślne. RC/beta/nightly wymagają odrębnej receptury i jawnego wyboru kanału; sama obecność RC nie dziedziczy tej zgody.
- Aplikację wcześniej otwartą przez użytkownika pozostaw otwartą. Zamknięcie tylko dla procesu uruchomionego w tej transakcji i tylko gdy aplikacja nie została przejęta do pracy przez użytkownika. Brak wiarygodnego rozróżnienia oznacza brak automatycznego zamknięcia.
- Nigdy `kill -9` GUI, automatyczne `--force/--adopt`, wyłączanie Gatekeeper/SIP/TCC, wstrzykiwanie kodu ani wyłączanie podpisu updatera. Brak zgody lub nieznany stan daje odroczenie, nie obejście.
- Dane kont, receipt, rzeczywiste ścieżki i logi użytkownika zostają lokalnie. Publiczne rekordy testów są zredagowane i nie zawierają surowego inventory.
- Nie poszerzać harmonogramów ani macOS runnerów CI. Żadne oznaczenie live-passed nie może pochodzić z mocka.
- Landing synchronizuje wyłącznie fakty już wdrożone. Uprawnienie do jego publikacji i scalenia istniejącej 1.7.0 nie jest zgodą na live testy tego planu.

## Review Focus

1. Updater obejmuje więcej aplikacji niż wybrano, np. Google `--update-apps`: blokada lub osobny plan pełnego zestawu. Test T3.
2. Użytkownik otwiera dokument w aplikacji uruchomionej przez toolkit: cofnięcie automatycznego zamknięcia. Test T4.
3. CLI kończy się, ale downloader/helper nadal działa: zakaz drugiej operacji i utraty blokady. Test T4.
4. Nazwa produktu, bundle/Team ID albo źródło zmieniają się przy rebrandingu: ponowny review, nie automatyczne dopasowanie. Test T2.
5. Ten sam numer wersji ma nowy build lub payload, albo feed cofnął wersję: tożsamość wydania i brak downgrade'u. Test T2/T5.

## 1. Co blokuje automatyzację w 1.7.0

Nie wystarczy dopisać nazw i zmienić flagi na `verified`.

- `config/app_recipes.json` ma pustą listę receptur. Istniejący schema v1 opisuje tożsamość i artefakty, ale nie pełny kontrakt wykonania, dowody akceptacji ani cykl natywnego updatera.
- `policy_runtime._prepare_command()` dopuszcza tylko `manager_update`. Sama receptura `reviewed_direct` nie podłącza jeszcze automatycznej ścieżki producenta.
- `update_plan.build_plan()` nie tworzy obecnie pełnego cyklu `open_native_updater`/restart. Potrzebne są adapter, zakres skutków oraz osobne pozwolenia na procesy.
- `setup_catalog.load_setup_catalog()` celowo buduje pozycje ręczne. `install_recipe_eligible()` dopuszcza tylko staged `vendor_bundle` z akceptacją dokładnej rewizji, wersji i źródła. Publiczny katalog nie dostarcza takich receptur ani kompletnego acquire/stage pipeline.
- Obecne manager guards odraczają m.in. nieprzejrzyste artefakty, dodatkowe cask dependencies oraz npm bin/scripts/dependencies. Ich odblokowanie wymaga zdefiniowanego zakresu, a nie osłabienia guardów.

## 2. Dowody i niezależne uprawnienia

| Poziom | Wymagany dowód | Co pozwala włączyć |
|---|---|---|
| metadata-reviewed | Produkt/edycja, oficjalny adres, kanał, zgodność wersji, data | Opis i porównanie wersji |
| artifact-reviewed | Podpis/Team ID/bundle, hash wydania, minOS/arch, wymagania i wszystkie skutki | Pobranie/staging w kontrolowanym środowisku; bez prawa instalacji |
| contract-tested | Fixture sukcesu, błędów, scope, zgód, odroczenia i odzyskiwania | Kandydat adaptera; bez oznaczenia live |
| update-accepted | Rzeczywiste N→N+1 w środowisku disposable, wynik po wykonaniu | Aktualizacja tylko obecnego, zgodnego celu |
| install-accepted | Rzeczywista pierwsza instalacja w pustym środowisku, komplet skutków i requirements | Pierwsza instalacja tego wariantu po osobnej zgodzie |
| lifecycle-accepted | Obserwowane trigger/download-ready/apply/restart/verify/close i odmowa zamknięcia | Wyłącznie udowodnione operacje procesu |

Update acceptance nie zastępuje install acceptance, a skuteczny direct download nie certyfikuje natywnego updatera. Receptura ma osobne pola uprawnień. Każde wykonanie ponownie weryfikuje artefakt i tożsamość. W v1 planu zachować przypięcie do dokładnej przetestowanej wersji; przejście na certyfikację zakresu wersji wymaga oddzielnego projektu i dowodów, żeby nie rozszerzyć zgody po cichu.

Natywny trigger, który sam wybiera i instaluje „latest”, musi mieć udokumentowaną możliwość przypięcia zaakceptowanego wydania lub niezmiennego kandydata. Sam check przed triggerem i porównanie po instalacji nie zabezpieczają przed zmianą feedu między zgodą a wykonaniem. Bez takiego kontraktu pozostaje read-only/manual albo przechodzi na zweryfikowany artefakt. Dotyczy to także MAU, Docker i Sparkle: istnienie oficjalnej komendy nie rozwiązuje automatycznie tej bramki.

## 3. Model natywnej aktualizacji

`observed → consented → checking → downloading → ready_to_apply → applying → installed_observed → verified → cleanup_done`

Alternatywne końce: `current_verified`, `stale_evidence`, `unsupported`, `not_offered`, `channel_not_allowed`, `user_interaction_required`, `restart_deferred`, `download_timeout`, `update_unverified`, `recovery_required`. Timeout albo brak zmiany wersji nigdy nie oznacza „aktualne”.

`ready_to_apply` musi pochodzić z udokumentowanego zdarzenia/statusu danego produktu i dotyczyć dokładnego celu oraz wersji. Nie zastępują go: wyjście launchera, istnienie pliku tymczasowego, proces o podobnej nazwie, malejący transfer ani trzy identyczne odczyty wersji. Gdy updater łączy pobranie i instalację bez obserwowalnej granicy, plan pokazuje jedną taką operację i nie udaje kontroli nad nieistniejącym etapem.

Dla zamkniętej aplikacji preferowany jest udokumentowany headless updater lub zweryfikowany direct artifact, jeśli ten produkt je wspiera. GUI uruchamiać tylko wtedy, kiedy jest konieczne. Restart dopiero po gotowości i zgodzie; ponowny launch do weryfikacji tylko jeśli wymaga tego kontrakt. Zamknięcie po weryfikacji jest opcjonalnym, osobno zaakceptowanym skutkiem, nie dowodem aktualizacji.

Czasy mierzyć zegarem monotonicznym, wliczając podprocesy. Domyślny budżet proponowany do fixture: check 20 s, trigger 15 s, czekanie na postęp 120 s, cała operacja 600 s, graceful quit 20 s, weryfikacja 30 s. Receptura może zadeklarować inne limity z uzasadnieniem. Polling 1/2/4/5 s, natychmiastowy koniec po dowodzie; zero stałego minimalnego 90 s i końcowego sleep 15 s. Wygaśnięcie obserwacji nie zabija działającego instalatora. Jego lokalny journal utrzymuje blokadę logiczną do wyjaśnienia stanu.

Metadata checks mogą działać po trzy naraz, maksymalnie jeden na host. Pobrania maksymalnie dwa, z łącznym budżetem dysku i transferu. Zgodnie z doprecyzowaniem właściciela plan obejmuje także do dwóch równoległych mutacji, ale tylko dla receptur z udowodnioną niezależnością. Wdrożenie kolejki i fixture nie uruchamia prawdziwych aktualizacji na komputerze właściciela.

Każda akcja deklaruje wszystkie zasoby: bundle, współdzielone helpery/services, manager i prefix, zależności, receipt store, konto/sesję App Store oraz ewentualne usługi systemowe. Wspólny zasób wyklucza równoległość. Homebrew, npm dla tego samego prefixu, App Store i MAU mają blokady na poziomie managera, nie tylko aplikacji. GoogleUpdater obejmuje cały jego udowodniony zakres. Nieznany scope oznacza manual albo globalną wyłączność, jeśli sekwencyjne wykonanie jest niezależnie zaakceptowane; nigdy zgadywaną równoległość. Aktualizacja systemu jest na końcu, z globalną wyłącznością i bez aktywnych lub nierozstrzygniętych helperów.

Najpierw jeden plan i zgoda, następnie kolejka bez konkurujących promptów. Zamknięcie/restart GUI jest domyślnie serializowane. Przykład możliwej pary to dwie zaakceptowane transakcje single-bundle do różnych celów, bez wspólnych helperów i zależności. Dwie komendy brew nie są taką parą. Liczba slotów jest limitem, nie obowiązkiem uruchomienia dwóch operacji. Aktywność użytkownika i zmiana stanu są ponownie sprawdzane po uzyskaniu blokad.

## 4. Zadania

### T1. Dowody przebiegu i pomiar opóźnień

**Files:** modify `lib/python/run_summary.py`, `update_all.sh`, `lib/python/policy_runtime.py`; create `lib/python/operation_receipts.py`, `tests/test_operation_receipts.py`; extend `tests/test_run_summary.py`.

**Interfaces:** `append_phase_event(session_dir: str, event: dict) -> None`; event zawiera run_id, action_id, recipe_revision, phase, start/end, elapsed_ms, outcome i typ dowodu. Provenance: toolkit_version, git_sha/unknown, dirty, effective wait budgets. Prywatne ścieżki nie wychodzą do eksportu.

- [ ] RED: `test_duration_778_formats_12m58s_with_final_step_3s`; niezależność czasu całego przebiegu od pętli etapów.
- [ ] RED: testy historii updatera kontra świeżego porównania, niepotwierdzonego quit, brakującego SHA i zredagowanego eksportu.
- [ ] Implementacja receipt i poprawka formatowania; zachować istniejące pola summary v4 i dodać klasę/freshness dowodu.
- [ ] GREEN: `bash run_tests.sh --unit-only --pattern 'test_*receipts.py'` oraz `test_run_summary.py`; brak host/network guard hits. Commit i aktualizacja opisów wyników.

### T2. Schemat receptury i pakiet dowodów

**Files:** modify `lib/python/app_recipes.py`, `lib/python/source_resolver.py`; create `config/verified_recipes.json`, `lib/python/recipe_acceptance.py`, `docs/catalog/recipes/README.md`, `tests/test_recipe_acceptance.py`.

**Interfaces:** `load_verified_recipes(path: str) -> dict`; `validate_recipe_evidence(recipe: dict, operation: str, environment: dict) -> dict` zwraca allowed, reasons, evidence_ids. Schema v2 ma product/edition, revision, bundle/team IDs, installation_source, update_mechanism, kanał, minOS/arch, artefakty/hosty, requirement graph, effect scope, adapter ID, observation contract, limits i osobne acceptance records update/install/lifecycle.

- [ ] RED: odrzucenie dopasowania po nazwie, obcego podpisu, zmiany produktu, App Store receipt na zewnętrznej ścieżce, unknown minOS i niezgodnej rewizji testu.
- [ ] RED: prerelease przy stable, ten sam numer z innym build/hash, cofnięcie feedu, zmiana requirements po zgodzie oraz brak live record mimo fixture-passed.
- [ ] Wdrożyć wersjonowany loader bez wykonywalnego tekstu, shell snippets ani automatycznego awansu dawnych capability rows. Rekord dowodu: data, recipe/artifact hash, OS/arch, uprawnienia, wynik, ograniczenia i zredagowane ślady.
- [ ] GREEN: `bash run_tests.sh --unit-only --pattern 'test_recipe_acceptance.py'`; schema/coverage obejmuje wszystkie identyfikatory macierzy, ale żadna pozycja nie uzyskuje zgody od samego wpisu. Commit.

### T3. Rejestr wykonawców, acquisition i zakres managerów

**Files:** create `lib/python/recipe_adapters.py`, `lib/python/artifact_acquisition.py`, `tests/test_recipe_adapters.py`, `tests/test_artifact_acquisition.py`; modify `lib/python/{policy_runtime,update_plan,setup_catalog,install_plan,install_execution}.py` i istniejące helpery transportu/transakcji tylko przez ich kontrakty.

**Interfaces:** `prepare_recipe_action(recipe: dict, target: dict, operation: str) -> dict`; `acquire_candidate(action: dict, staging_root: str) -> dict`; `execute_recipe_action(action: dict, observer, journal) -> dict`. Adapter zwraca strukturalny status, dowody i rzeczywisty zbiór skutków, nie sam kod wyjścia.

- [ ] RED: receptura bez adaptera nigdy nie przechodzi do legacy handlera; zwykły UpdatePlan odrzuca InstallPlan; brak celu nie prowadzi do instalacji.
- [ ] RED: Google force-all z aplikacją poza zatwierdzonym zestawem, nowy cask artifact/dependency i npm bin/script poza planem kończą się defer przed komendą.
- [ ] RED: feed zmienia oferowane wydanie po zgodzie; adapter bez przypięcia kandydata nie uruchamia mutacji, nawet gdy potrafi potem odczytać wersję.
- [ ] Podłączyć najpierw prosty single-bundle vendor adapter i jawnie ograniczony manager adapter; wykorzystać obecne SSRF/redirect, signature, same-volume staging, TargetLock i reobserve. Dodać bounded extraction bez traversal/symlink escape i bez mount/execute w testach hosta.
- [ ] Instalator pobiera wyłącznie zatwierdzony artefakt i po weryfikacji przekazuje staging do istniejącego exclusive install. Wymagania z bootstrapem/privileged pkg pozostają ręczne do osobnej akceptacji ich adaptera. Nie instalować globalnych narzędzi, żeby narysować menu.
- [ ] GREEN: wzorce `test_recipe_adapters.py`, `test_artifact_acquisition.py`, `test_install_*.py`, `test_policy_runtime.py`; kod i wszystkie siedem instrukcji zgodne z faktycznie aktywnymi adapterami. Commit.

### T4. Obserwowalny native lifecycle

**Files:** create `lib/python/native_update_session.py`, `tests/test_native_update_session.py`, `tests/fixtures/native_updaters/`; modify `lib/python/{recipe_adapters,user_policy,update_plan,policy_runtime}.py`.

**Interfaces:** `advance_native_session(state: dict, observation: dict, now_monotonic: float) -> dict`; `may_control_process(action: dict, observation: dict) -> dict`; `recover_native_sessions(state_dir: str) -> list[dict]`. Stan przechowuje PID + czas startu + bundle identity, źródło gotowości i własność procesu. Sam PID ani nazwa nie wystarczają.

- [ ] RED: już uruchomiona aplikacja, ponowne użycie PID, otwarcie dokumentu po launch, dialog save/cancel, wznowienie komputera, relaunch przez updater i helper żywy po wyjściu CLI.
- [ ] RED: timeout lub crash toolkitu zwalnia kernel lock, ale kolejny manager/direct/install nadal odmawia działania na celu z nierozstrzygniętą sesją helpera. Sprawdzić wszystkie wejścia zapisujące, także inny checkout.
- [ ] RED: ready natychmiast kończy polling; brak sygnału nigdy nie prowadzi do restartu; wywołanie blokujące 10 s zużywa prawdziwy deadline; timeout nie usuwa jedynej dobrej kopii ani journal.
- [ ] Wdrożyć maszynę stanów, pojedynczy trigger, kontrolowany graceful quit, opcjonalny restart i potwierdzenie wersji/build/podpisu. Minimalny ekran danych użytkownika oznacza przejęcie sesji; gdy adapter nie potrafi tego wykryć, pozostawia aplikację i raportuje restart_deferred.
- [ ] Oddzielić download-ready od install-complete; `--defer-install` Sparkle i odpowiedniki utrzymują stan pending. Przy restarcie toolkitu tylko reobserve/reconcile, bez ponownego triggera w ciemno.
- [ ] Native mutations nie używają obecnego `_run()` opartego na `subprocess.run(timeout=...)`, które zabija uruchomione dziecko po limicie. Wprowadzić nadzorowany cykl procesu, oddzielny deadline obserwatora i trwały pending-session barrier sprawdzany przez każdego writer przed `TargetLock` oraz ponownie pod blokadą. Kernel lock sam nie przeżywa procesu właściciela. Zapis journal musi poprzedzać trigger; nieznany stan po crash pozostaje recovery_required do udowodnionego zakończenia helperów i ponownej obserwacji celu.
- [ ] GREEN: `bash run_tests.sh --unit-only --pattern 'test_native_update_session.py'`, fake clock, zero prawdziwych GUI i native helpers. Jeden wspólny przegląd T2-T4 przed podłączeniem pilota. Commit.

### T5. Weryfikacja produktów falami

**Files:** create `docs/catalog/recipes/<product-id>.md`, sanitized `tests/fixtures/recipes/<product-id>/`; populate `config/verified_recipes.json` dopiero po odpowiednich bramkach.

- [ ] Każdy produkt z macierzy przechodzi identity/source/channel review, kontrakt adaptera i deterministyczny fixture: absent, current, newer, older, offline/429, partial download, bad signature, wrong identity/OS/arch, running, duplicate, source conflict, permission denial, crash i rerun.
- [ ] Fala 1: proste bundle bez konta/helperów, np. CodeEdit, KeePassXC, AppCleaner, po dowodzie ich rzeczywistego scope. Równolegle kontrakt MAU dla jednego Office. To kandydaci, nie wpisy już zatwierdzone.
- [ ] Fala 2: pozostałe Office, sprawdzone Sparkle oraz odpowiednie caski. App Store pozostaje w swoim kanale; zewnętrzny updater nie zastępuje receipt.
- [ ] Fala 3: Docker, GoogleUpdater, VPN/synchronizacja, aplikacje z privileged helperami. Wymagana analiza pełnych skutków i aktywnych zadań; brak automatycznego force-all dla pojedynczej zgody.
- [ ] Fala 4: GUI-only/niejasna tożsamość i kanały preview. Brak opublikowanego kontraktu oznacza manual, chyba że osobny, testowany adapter GUI uzyska acceptance. DeepSeek nightly i Firefox Developer Edition nie trafiają do listy latest stable.
- [ ] GREEN: contract tests każdego kandydata; pełne `bash run_tests.sh`, ShellCheck warning-level, Python 3.9 i bieżący Python, schema/catalog coverage. Bez uruchamiania updaterów na Macu właściciela. Commit dowodów fixture bez flagi live.

### T5b. Kolejka niezależnych aktualizacji

**Files:** create `lib/python/update_scheduler.py`, `tests/test_update_scheduler.py`; modify `lib/python/{policy_runtime,recipe_adapters,operation_receipts,native_update_session}.py` i warstwę wspólnych blokad. Nie uruchamiać starych shell leaf scripts równolegle przez samo `&`.

**Interfaces:** `schedule_ready_actions(actions, resource_state, limits) -> list`; `claim_action_resources(action, journal) -> lease`. Scheduler dopuszcza maksymalnie dwa rozłączne zbiory zasobów. Blokady mają wspólną przestrzeń między checkoutami i procesami; acquire w stabilnej kolejności lub atomowo, bez deadlock. Journal jest sprawdzany przed i po acquire.

- [ ] RED: dwie niezależne aplikacje nakładają się w czasie; wspólny brew prefix, MAU, App Store, zależność lub helper wymuszają kolejność; unknown scope nie jest parallel-safe.
- [ ] RED: dwa checkouty, anulowanie, utrata procesu, pomocnik żywy po timeout, konflikt nowych zależności i aplikacja otwarta w czasie oczekiwania w kolejce. Brak podwójnego triggera lub zwolnienia zasobu pending.
- [ ] Wyłącznie akcje z kompletnym planem i zgodą; nowy efekt/wersja wymaga nowego planu. `cancel` blokuje start następnych, ale nie zabija trwających instalatorów. Uruchomione akcje kończą obserwację albo pozostają recovery_required.
- [ ] Osobne receipt per action i jeden bezpieczny agregator summary. Brak wyścigów w inventory/history, wspólnym pliku wyników, stdout i zapisie JSON. Publikacja inventory po osiągnięciu spójnego punktu, atomowo; statusy pending pozostają jawne.
- [ ] GREEN: fake clock i controlled barriers pokazują krótszy makespan tylko dla niezależnych operacji. Ten sam plan sekwencyjny i równoległy daje ten sam zestaw skutków oraz wyników. Pełny guard runner przed przekazaniem do T6.

### T6. Osobno zatwierdzane testy w środowisku disposable

- [ ] Właściciel wybiera osobny Mac albo odtwarzalną macOS VM na Apple Silicon. Brak współdzielonych katalogów aplikacji/home/keychain, prywatnych kont, chmury i urządzeń produkcyjnych. Snapshot przed scenariuszem. Licencja/warunki aplikacji muszą pozwalać na test.
- [ ] Macierz: najstarszy system obsługiwany przez konkretny produkt i aktualny; konto standardowe oraz administrator tam, gdzie jest to uzasadnione. Nie wymagać macOS 13 dla produktu, który go nie wspiera. Wynik VM nie certyfikuje automatycznie helperów/sterowników na fizycznym Macu.
- [ ] Osobno: fresh install, update N→N+1, brak aktualizacji, zgoda/odmowa, offline, interruption/recovery i konflikt źródła. Dwie publicznie dostępne podpisane wersje albo udokumentowane wydanie testowe; brak pary wersji pozostawia update acceptance pending.
- [ ] Akceptacja równoległości jest osobna: porównanie tych samych dwóch receptur sekwencyjnie i równolegle, brak niezatwierdzonych efektów, przerwanie jednej bez uszkodzenia drugiej, wspólny helper i konkurujący checkout. Do czasu takiego dowodu receptury wykonują się sekwencyjnie.
- [ ] Zmierzyć fazy i faktyczne skutki: stworzone/zmienione bundle, helpery, services, launch agents, profile i uprawnienia. Brak dostępu do pełnego zakresu oznacza manual.
- [ ] Osobno App Store: konto testowe, region, cena/licencja, offered versus listed, brak zakupu/logowania w automacie. Darmowa instalacja także wymaga wyboru użytkownika.
- [ ] Kryterium awansu: komplet konkretnych wyników, zgodne identity/hash i brak niezatwierdzonego efektu. „Nie udało się przetestować” nie jest passed. Po każdym przerwaniu sprawdzić, że istnieje dobra kopia i można bezpiecznie rozpocząć nowy plan.

### T7. Kontrolowane włączenie i pomiar poprawy

- [ ] Włączyć wyłącznie capabilities konkretnej przetestowanej rewizji. Użytkownik widzi źródło, wersję, wymagania, zakres zmian, możliwy launch/restart/close i cenę/licencję unknown, jeśli brak dowodu.
- [ ] Tryb obserwacyjny na fixture oraz disposable środowisku musi dawać ten sam plan co executor. Po przerwaniu pozostałe akcje wymagają świeżego planu i zgody; opcja wycofania receptury nie kasuje aplikacji ani danych.
- [ ] Porównać p50/p95 check/download/apply/verify i czas bez postępu dla tej samej pary wersji oraz środowiska, minimum pięć porównywalnych prób. Nie obiecywać skrócenia całego run do określonej liczby sekund na podstawie jednego logu.
- [ ] Cel deterministyczny: obsługa readiness w ciągu maksymalnie jednego interwału pollingu, zero bezwarunkowych opóźnień i zero zamknięć nieobjętych zgodą. Pobranie i czas instalatora pozostają zależne od producenta.
- [ ] Dokumentacja i landing pokazują osobne liczby produktów, receptur update-accepted, install-accepted i historycznie testowanych handlerów. Dopiero potem osobna decyzja o wydaniu/tagu oraz aktualizacja materiałów publikacyjnych.

## 5. Akceptacja planu

Najpierw zatwierdzić T1-T5 wraz z T5b jako pracę lokalną z fixture. T6 wymaga osobnego środowiska i osobnej zgody na konkretne rzeczywiste operacje; ten plan ich nie autoryzuje. T7 może włączyć tylko ścieżki z wymaganymi dowodami. Nie należy obchodzić tej kolejności, aby DeepSeek RC zniknął z ostrzeżeń.

Macierz wszystkich produktów stanowi [załącznik](../../catalog/RECIPE_VERIFICATION_MATRIX_2026-11-14.md). Wpis „kandydat” oznacza kolejkę badań, nie gotowy adapter.
