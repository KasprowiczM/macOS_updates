# Bezpieczne inventory i aktualizacje nowych użytkowników: plan wdrożenia

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Apply the session's orchestration and cost rules; do not create a reviewer for every small task.

**Goal:** Każdy Mac ma inventory swoich instalacji, zachowane źródła i zgody; rekomendacje wskazują kanał z najnowszą kompatybilną stable, a opcjonalne menu pozwala wybrać źródło oraz doinstalować aplikacje z potrzebnymi zależnościami.

**Architecture:** Lokalny snapshot, wspólny resolver i polityka zgód tworzą plan aktualizacji istniejących celów. Osobny InstallPlan obejmuje jawnie wybrane nowe aplikacje i zależności, z innym warunkiem obecności i niezależną walidacją pierwszej instalacji. Markdown jest czytelnym widokiem, nie autoryzacją instalacji.

**Tech Stack:** Bash 3.2, Python 3 z biblioteką standardową, JSON lokalny, unittest, istniejące Homebrew/mas i handlery. Bez nowego demona, bazy SQL, runtime AI i zależności sieciowej do klasyfikowania inventory.

**Spec:** [Audyt i specyfikacja docelowa, 2026-11-13](../../implementation/NEW_USER_AUDIT_2026-11-13.md), szczególnie rozdziały 4, 8, 10 i 11. Plan obejmuje 15 zadań w etapach A-E.

**Status:** Etap A i research źródeł wdrożone lokalnie jako 1.6.1. Etap B (T04-T05) zaakceptowany 2026-11-13, wdrożenie obserwacyjne 1.6.2 na bazie `5daf24d`. Bez publikacji, prawdziwych aktualizacji i zmian w landing page. Etap C (T06-T09) wdrożono lokalnie jako 1.6.3; jego pełna bramka przeszła 1101 przypadków, jeden jawnie pominięty. D i E są w integracji. Po każdym etapie zwiększamy trzeci człon wersji; po ukończeniu całości wersja 1.7.0.

**Wdrożenie etapu A:** [zapis implementacji 1.6.1](../../implementation/STAGE_A_1.6.1.md). Research kanałów: [47 pozycji katalogu](../../catalog/SOURCE_RESEARCH.md). T06-T09 są zamknięte w [etapie C](../../implementation/STAGE_C_1.6.3.md); T10-T15 są w integracji. **Etap B:** [zapis implementacji 1.6.2](../../implementation/STAGE_B_1.6.2.md).

## Global Constraints

- Apple Silicon arm64, macOS 13-27, Bash 3.2, bez `set -e` w orchestratorach, z `set -o pipefail`.
- Python 3.9 jako minimalny cel zgodności tego planu, bez nowych zależności; zweryfikować ten cel na początku prac i zachować działanie na aktualnym Pythonie.
- Bez nowych samodzielnych entrypointów Python dla pipeline; moduły pod `lib/python/`, wywołania z istniejących entrypointów shell.
- UpdatePlan aktualizuje tylko istniejącą instalację. Nowe aplikacje wyłącznie przez osobny InstallPlan wybrany i zatwierdzony w menu setup; bootstrap CLI pozostaje osobną, jawną opcją. `-y` nie udziela nowych zgód ani nie uruchamia katalogu instalacji.
- Nie zmieniać źródła, lokalizacji, profilu powłoki, PAM, uprawnień, MDM, harmonogramu ani uruchomionych aplikacji bez właściwej zgody.
- Brak obecności, niepełny skan, niespójna tożsamość lub konflikt blokują mutację danego celu, nie cały niezależny run.
- Weryfikacja wyniku na podstawie obserwacji po operacji, nigdy wyłącznie exit code instalatora.
- Zmiany stringów i instrukcji użytkownika obejmują wszystkie 7 języków. Żadne nowe widoczne teksty/dokumentacja nie używają znaków em dash ani en dash.
- Brak prywatnych ścieżek, inventory, receipt, logów maszyn i danych pamięci w plikach śledzonych.
- Bez produkcyjnych prób jako testów. Fixture, tymczasowe HOME/PATH i failing guards są obowiązkowe.
- Zachować istniejący kontrakt exit `0/10/1` i struktury run summary v4; pola dodawać kompatybilnie, nie zmieniać znaczenia starych po cichu.
- Brak nowych scheduled Actions. Ewentualne zmiany CI tylko w istniejących jobach, z pomiarem minut i bez poszerzania triggerów/macOS runnerów.
- Prace lokalne i odwracalne; push/merge/tag/release/live run wymagają odrębnej zgody właściciela.

## Review Focus

1. Pusty poprawny skan kontra nieudany/niepełny skan; usuwanie tylko przy kompletnym pokryciu. Testy T02/T04/T07.
2. MAS plus stale cask oraz dwie kopie tego samego bundle w różnych rootach; brak automatycznej migracji. Testy T05/T06/T08.
3. Aplikacja znika, zmienia podpis lub zaczyna działać między planem a wykonaniem; brak odtworzenia/podmiany. Testy T06/T09.
4. Pierwszy start bez Homebrew, mas, sieci, sudo albo GUI; inventory nadal użyteczne, brak samoczynnych instalacji. Testy T03/T04/T10.
5. Nieznana aplikacja z niebezpiecznym URL, nazwą, plist lub updaterem; tylko obserwacja, bez wykonania i bez eksportu prywatnych danych. Testy T04/T09/T10.

## 1. Kolejność i zakres wydawania

| Etap | Zadania | Dostarczony wynik |
|---|---|---|
| A: wiarygodna bramka i pilne naprawy | T01-T03 | deterministyczne testy, uczciwe statusy, bez automatycznego bootstrapu/PAM |
| B: wspólny model lokalnego stanu | T04-T05 | snapshot i jednoznaczne decyzje o źródle |
| C: bezpieczne wykonanie i migracja | T06-T09 | guard wszystkich mutacji, odwracalne przejście z Markdown, zgody i poprawione pobieranie |
| D: autoadaptacja i akceptacja | T10-T11 | nowe aplikacje jako bezpieczne propozycje, profile nowych Maców, ograniczony rollout |
| E: źródła latest stable i opcjonalny instalator | T12-T15 | research kanałów, bieżące porównanie stable, menu źródeł, zatwierdzany plan zależności/instalacji, osobna akceptacja i spójna komunikacja landing |

Etap A może być kandydatem na małe wydanie naprawcze po swoich testach, lecz nie usuwa wszystkich ograniczeń audytu. Nie komunikować pełnego rozwiązania multi-source przed etapem C. T04/T05 i T07 przygotowywać w shadow mode; nowy wykonawca nie może działać na połowie starego i połowie nowego modelu. Jeden spójny punkt aktywacji na koniec C.

Etap E jest rozszerzeniem zamówionym po pierwszej wersji audytu. Wymaga zabezpieczeń B/C i nie opóźnia etapu A. T11 jest bramką silnika aktualizacji, T15 dodatkową bramką nowej funkcji. Menu może pokazywać cały katalog możliwości, ale instalowalne są wyłącznie pozycje z odpowiednią receptą i dowodami pierwszej instalacji. Research T12 można przygotowywać równolegle z bezpiecznymi pracami A-D; wykonawca instalacji dopiero po ich bramkach.

## 2. Kontrakt danych

Typy poniżej to specyfikacja implementacji, nie istniejące dziś API. Definicje umieścić w `lib/python/inventory_model.py` jako typowane struktury walidowane podczas odczytu. JSON jest formatem wymiany; ścieżki i identyfikatory przekazywać argumentami, nigdy `eval`.

### SourceResult

`status`: `ok | unavailable | error | partial`. `items`: lista rekordów. `observed_at`: UTC ISO 8601. `covered_roots`: lista canonical paths. `complete`: bool. `reason_code`: null albo stabilny kod. `schema_version`: 1.

Pusta lista z `status=ok, complete=true` jest prawidłowa. Timeout, niepoprawny JSON, błąd katalogu lub brak części metadanych nie mogą stać się takim wynikiem. Brak binarnego mas to `unavailable`, a nie puste MAS. Udane `mas list` jest kompletne względem odpowiedzi mas, lecz samo nie dowodzi kompletności skanu wszystkich lokalnych bundle. Nie usuwa niezależnych obserwacji receipt.

### InstalledInstance

`instance_id`: losowy lokalny identyfikator utrzymany po jednoznacznym reconcile, nigdy UUID sprzętu. `path` i `real_path`, `scope` (`user | system | optional_root`), `bundle_id`, `team_id`, `name`, `short_version`, `build_version`, `architectures`, `minimum_os`, `channel` (`stable | beta | testflight | unknown`), `observed_at`, `evidence`, `presence` (`present | absent | unobserved`), `freshness` (`fresh | stale`), `parent_instance_id`.

Nieznane dane mają null, nie wymyślone wartości. `evidence` zawiera pochodzenie: lokalne Info.plist, receipt signal, mas ID, brew token plus rzeczywista ścieżka artefaktu, reviewed recipe ID, macOS protected root. Sekrety w URL nie trafiają do pól prezentacyjnych. W snapshot nie kopiować zawartości receipt ani danych konta.

Brew formula/CLI/package mają analogiczne rekordy `InstalledPackage`: `package_id`, `manager`, `prefix`, `version`, `installed_receipt`, `explicitly_installed`, `related_instance_ids`, `evidence`, `presence`, `freshness`, `observed_at`, `source_identity`, `channel`. Tożsamość pakietu obejmuje manager, canonical prefix i receipt/zweryfikowaną instalację, nie samą nazwę komendy. Nieznany receipt lub provenance nie daje prawa do migracji ani nadpisania pliku z PATH.

Wspólne `TargetRef` ma `{kind: app | package, id: string}`. `CurrentTarget` to walidowany InstalledInstance albo InstalledPackage z odpowiadającym TargetRef. Resolution, PolicyDecision, Action, GuardResult i ActionResult zawsze odnoszą się do `target`, nigdy do niejednoznacznego ID bez typu. Dla obu klas obowiązują presence, freshness, source identity i ponowna autoryzacja; lista powiązanych bundle nie zastępuje tych kontroli dla pakietu.

### Resolution

`target: TargetRef`, `source` (`app_store | homebrew | npm | vendor | apple_system | enterprise_managed | unknown | conflict`), `capability` (`inventory_only | check_only | native_managed | reviewed_direct`), `adapter_id`, `evidence_grade` (`confirmed | probable | unknown | conflicting`), `reason_codes`, `candidate_sources`.

Hierarchia nie oznacza, że „MAS zawsze wygrywa i ignorujemy brew”. Przy zgodnych dowodach wybieramy źródło; przy niezgodnych zwracamy konflikt. Receipt chroni przed zewnętrzną podmianą również wtedy, gdy nie pozwala jeszcze wybrać konkretnego store ID. Nie budujemy procentowego „confidence score” udającego pewność.

### PolicyDecision i ActionPlan

`PolicyDecision`: `target: TargetRef`, `identity_fingerprint`, `source_fingerprint`, `action_scope`, `choice` (`preserve_source | allow_check | allow_update_same_source | allow_native_launch | defer | ignore`), `created_at`, `expires_at`, `reason`. Zgoda zależy od ścieżki/prefixu, tożsamości podpisu/receipt, źródła i kanału. Zwykła zmiana wersji nie unieważnia wyboru źródła. `defer` ma domyślnie 7 dni, `ignore` jest jawny i odwoływalny; zmiana dowodów konfliktu pozwala ponownie ocenić decyzję.

`action_scope` ma dokładnie `local_observation | network_check | manager_update | direct_update | native_launch`. `preserve_source` wybiera preferencję źródła i sam **nie autoryzuje mutacji**. `allow_check` pozwala na zatwierdzony network_check; `allow_update_same_source` pozwala tylko na manager_update lub direct_update wskazany zakresem i nie obejmuje zmiany artefaktów, kanału ani bootstrapu. Native launch wymaga allow_native_launch. Local observation/manual/skip nie potrzebują zgody na mutację. Reboot, privileged bootstrap, migracja i PAM pozostają osobnymi ścieżkami poza tym automatycznym planem.

Przy pierwszym przejściu na model zgód pokazać jeden zbiorczy plan dla aktualnie wykrytych, bezkonfliktowych instalacji i zapisać zakres tylko po świadomym wyborze. Stare Markdown/prefs nie tworzą takich zgód. Kolejne update_all realizuje już zatwierdzone zakresy; nowa instalacja lub większe skutki wymagają nowej decyzji. W noninteractive/`-y` przy braku zgody wykonać wyłącznie obserwację i odroczyć mutację. Jednorazowa zgoda może być związana z plan_id i wygasa z planem zamiast być trwałą preferencją.

`Action`: `action_id`, `target: TargetRef`, `kind` (`check | update | open_native_updater | manual | skip`), `action_scope`, `adapter_id`, `target_path`, `expected_identity`, `expected_source`, `from_version`, `to_version`, `artifact_effects`, `consent_required`, `reason_codes`.

`ActionPlan`: `plan_id`, `snapshot_id`, `created_at`, `policy_revision`, `actions`, `readiness`. Maksymalny wiek wykonania planu: 15 minut. Ponowna weryfikacja celu jest obowiązkowa także dla świeżego planu. Token zatwierdzenia jest lokalnym dowodem decyzji interfejsu, nie zabezpieczeniem przed złośliwym procesem działającym jako ten sam użytkownik.

`GuardResult`: `target`, `allowed`, `reason_code`, `observed_identity`. `ActionResult`: `target`, `status`, `verified`, `before`, `after`, `reason_code`, `retry_after`, `recovery_required`. Wyświetlane tłumaczenie nigdy nie steruje logiką statusu.

### Snapshot i położenie danych

`Snapshot`: `schema_version=1`, `snapshot_id` (losowy UUID), `profile_id` (lokalny losowy ID), `created_at`, `generation` (monotoniczny licznik zapisu), `previous_snapshot_id`, `sources`, `instances`, `packages`. `sources` ma klucze `filesystem:<canonical_root>`, `mas`, `brew:<canonical_prefix>`, `cli:<canonical_prefix>` i wartości SourceResult. Wynik managera może usunąć membership jego pakietów tylko w objętym skanem prefixie; nie usuwa niezależnie zaobserwowanego bundle. Absence aplikacji wymaga udanego kompletnego skanu obejmującego poprzednią ścieżkę, a nie pustego mas. Przeniesienie do nieskanowanej lokalizacji pozostaje ograniczeniem pokrycia, bez instalacyjnego fallbacku. Powiązanie profilu i generacji kontroluje store przed zapisem i wykonaniem.

Lokalne dane: `${XDG_STATE_HOME:-$HOME/.local/state}/mac-update/`, katalog 0700, pliki 0600, atomowy replace. `inventory.json`, `policy.json`, `transactions/`, `migration/`. Identyfikator lokalnego profilu bez danych sprzętowych; nie przenosić zgód między Macami ani kontami. Jawne nadpisanie rootu w testach.

`APPLICATIONS.md` pozostaje wygodnym lokalnym raportem, nadal gitignored. Ręczne notatki migrować do `inventory-notes.json` w tym samym prywatnym root. Konfiguracje `config/*.txt` pozostają katalogiem adapterów; nie wpisywać do nich instalacji użytkownika podczas skanu.

Publiczna recepta: `config/app_recipes.json`, schema 1, reviewed bundle IDs/Team IDs, adapter, kanały, obsługiwane architektury/systemy, hosty pobrań i dozwolone artefakty. Nie ma dowolnych komend shell. Istniejący katalog TXT dostaje adapter zgodności, nie jest przepisywany w jednym kroku.

### Rozszerzenie E: kanały i latest stable

Recepta obejmuje `product_id`, `edition` (`gui | cli | suite`), `installation_sources`, `compatible_updaters`, `version_comparison_policy`, `stable_policy`, `requirements` i `verification`. `source` w Resolution oznacza pochodzenie/managera instalacji; dodatkowe `update_authority` wskazuje zatwierdzony mechanizm aktualizacji. Homebrew plus zgodny native updater producenta nie oznacza samo w sobie konfliktu; receipt MAS i próba zewnętrznej podmiany tej samej ścieżki nadal oznaczają konflikt.

`ChannelObservation`: `product_id`, `edition`, `source_id`, `updater_id`, `release_channel`, `version`, `build`, `release_identity`, `published_at` (nullable), `observed_at`, `availability` (`offered | listed | staged | unavailable | unknown`), `compatibility`, `region` (nullable), `evidence_url`, `fetch_status`, `cached`. Normalizowanie wersji tylko według zbadanej polityki danego produktu; numer GUI nie jest porównywany z numerem CLI.

`ChannelRecommendation`: `product_id`, `latest_global_stable`, `latest_compatible_stable`, `recommended_source_id`, `recommended_updater_id`, `reason_codes`, `evidence`, `as_of`, `uncertainty`, `migration_required`, `historical_sample_size`. Pola latest/recommended mogą być null. Najpierw zgodność produktu, stable, bezpieczeństwa i systemu, potem dostępność wersji. Przy remisie preferuj obecny kanał i najmniejszą zmianę. Użytkownik może wybrać inny obsługiwany kanał, ale nie ominąć hard constraints. Brak danych nie może być rekomendacją nowszej wersji.

`verification` osobno opisuje `implementation_tested`, `update_live_tested`, `fresh_install_live_tested`, z datą, wersją, source/updater, OS/arch, publicznym sanitized evidence ID i ograniczeniami. Liczba obsługiwanych aplikacji nie jest liczbą zweryfikowanych fresh installs. Dowody historyczne nie wygasają jako fakty, lecz zmiana recepty/podpisu/instalatora wymaga ponownej kwalifikacji current support. Po 90 dniach bez walidacji oznacz review_due, nie „najnowsza na pewno”.

### Rozszerzenie E: odrębny InstallPlan

`InstallSelection`: `recipe_id`, `product_id`, `source_id`, `updater_id`, `release_channel=stable`, `destination`, `requested_version`, `catalog_revision`. Brak instance_id, bo instalacji jeszcze nie ma. `InstallPlan`: `plan_id`, `schema_version=1`, `profile_id`, `created_at`, `expires_at`, `catalog_revision`, `selections`, `dependency_graph`, `ordered_actions`, `expected_effects`, `privileges`, `manual_steps`, `plan_digest`, `consent`.

`InstallAction`: `action_id`, `kind` (`install_app | install_dependency | manual_acquisition`), `recipe_id`, `source_id`, `version`, `expected_bundle_id/team_id` albo zweryfikowany package receipt/publisher, `destination`, `expected_absent`, `artifact_integrity`, `depends_on`, `effects`, `recovery_policy`. Zgoda dotyczy tego planu i jego skutków, ważna maksymalnie 15 minut i jednorazowa dla wybranych akcji. `-y` nie tworzy zgody. Przerwanie wymaga nowego preview pozostałych działań, bez automatycznego resume przy następnym update_all.

`Requirement`: `id`, `kind` (`dependency | permission | account | license | system_compatibility`), `required_by`, `already_satisfied`, `optional`, `action_id`, `privilege`, `effect`. DAG wykrywa cykle i scala wspólne zależności. Domknięcie grafu ma być widoczne przed zgodą; nowa zależność lub zmieniona wersja źródła przy wykonaniu unieważnia objęty nią plan. Permissions/accounts/licenses są instrukcjami i osobnymi decyzjami, nie komendami instalacyjnymi.

Update guard **wymaga obecności**, install guard **wymaga zatwierdzonej nieobecności** i zewnętrznego dowodu tożsamości oczekiwanej aplikacji. Żaden nie przełącza się automatycznie w drugi. Jeśli aplikacja pojawiła się po preview, instalator odkłada akcję i wykonuje ponowny skan zamiast nadpisywać lub adoptować. Nowa instalacja nie jest zgłaszana jako zaktualizowana.

## 3. Zadania wykonawcze

### T01. Napraw izolację testów i utrwal bazę audytu

Status A: wdrożone lokalnie z odstępstwami opisanymi w raporcie 1.6.1. Commity zadań zastępuje jeden commit integracyjny etapu. Czas lokalnych unittest: 268.731 s; rzeczywisty przyrost minut Ubuntu CI pozostaje niezmierzony, ponieważ nie publikujemy zmian. Poprawka kolejności mocków DeepSeek/Grok była już w oczyszczonej bazie `10dc0e4`.

**Files:** modify `tests/test_deepseek_grokbot.py`, `run_tests.sh`, `.github/workflows/ci.yml`; create `tests/test_test_isolation.py`; w razie potrzeby pomocniczy `tests/support.py`.

**Interfaces:** wspólny test-only guard runner; brak zmiany API produktu. Nowe `bash run_tests.sh --unit-only --pattern 'test_*.py'` uruchamia tylko unittest z tymi samymi guardami co pełna bramka. Bez argumentów zachowuje dotychczasowe 4 fazy.

- [x] Dodaj test, który ładuje biblioteki w rzeczywistej kolejności i wykazuje nadpisanie fixture; dopisz test niezamockowanego curl kończący runner błędem. Dozwolone mocki muszą rejestrować wywołania.
- [x] Uruchom testy w izolacji i potwierdź niepowodzenie bez wykonania sieci.
- [x] Przenieś wszystkie atrapy po ostatnim source; dodaj failing curl/wget oraz blokadę bezpośrednich Python socket/urllib w kontekście testów. Nie blokuj testowych serwerów lokalnych bez jawnego opt-in testu.
- [x] Zharmonizuj Ubuntu i macOS przez ten sam `--unit-only`; macOS pełne 4 fazy bez zmian. Nie eksportuj globalnego PYTHONPATH, które maskuje braki importów produktu.
- [x] Zweryfikuj testami brak realnych `open`, `osascript`, `defaults`, `hdiutil`, `ditto`, `codesign/spctl` poza atrapami; lista guardów nie chroni absolutnych ścieżek, więc dodać statyczną kontrolę testów i negatywne próby obejścia. Prawdziwe testy systemowe tylko w disposable środowisku.
- [x] Uruchom `bash run_tests.sh --unit-only --pattern 'test_deepseek_grokbot.py'`, potem pełny runner. 846 historycznych testów plus nowe powinny przejść bez sieci. Nie aktualizuj oczekiwanych wersji do dzisiejszych feedów.
- [ ] Zapisz czas jobów. Zachowaj istniejące triggery; szacowany przyrost miesięczny = liczba zdarzeń razy zmierzona różnica czasu, punkt odniesienia 60 zdarzeń/miesiąc. Bez nowych runnerów i harmonogramów.
- [x] Lokalny commit tylko plików tego zadania po zielonym wyniku.

### T02. Pilna naprawa list i statusów bez przebudowy silnika

**Files:** modify `update_internet_apps.sh`, `lib/internet_app_updates.sh`, `lib/internet_handlers.sh`, `lib/internet_status.sh`, `lib/python/inventory_sync.py`, `scripts/report_update_coverage.sh`, `tests/test_inventory_sync.py`, `i18n/lang_{en,pl,de,fr,es,it,pt}.sh`; create `tests/test_new_user_reporting.py`.

**Interfaces:** tymczasowy filtr obecności przed dispatch; statusy nie mogą odczytywać intencji z katalogu. `report_update_coverage.sh --show-supported` jawnie pokazuje nieobecne pozycje. Zwykły raport podaje tylko lokalne instalacje i zbiorczą liczbę dostępnych recept.

- [x] Dodaj fixtures: pusty Mac, jedna nieznana aplikacja, MAS CapCut bez caska, nieobecny CapCut, brew unavailable. Asercje: brak nieobecnych nazw i nagłówków w normalnym przebiegu; zero cask warnings/soft failure za sam brak aplikacji; MAS status zachowany.
- [x] Osobny test regresji zgłoszenia: katalog ma brew_cask, brew działa, token nie jest zainstalowany, aplikacji brak. Cały mockowany update_all kończy się exit 0, bez degraded/cask_missing w summary i bez install/adopt. Wariant z lokalnym MAS bundle zachowuje MAS, wariant z manual bundle proponuje obsługę, a błąd odczytu brew daje source_unavailable, nie fałszywe „brak caska”.
- [x] Sprawdź failing przypadki przez nowy guard runner.
- [x] Przenieś filtr przed nagłówki/dispatch i przed walidację caska. Rozpoznanie receipt musi objąć także CapCut i inne pozycje wyłączone w dispatch_order z powodu migracji autora do brew; nie wystarczy test bezpośrednio wywołujący iu_capcut. Nie omijaj faktycznie zainstalowanego MAU w jego niestandardowej lokalizacji.
- [x] Usuń fallback legendy „puste installed_names oznacza wszystko”. Zachowaj odrębny stan nieudanego skanu; nie wycinaj bezwarunkowo wszystkich guards empty/error przed T04.
- [x] Zachowaj istniejące filtrowanie końcowej tabeli; nie rozwiązuje ono agregacji statusów, która również wymaga filtra.
- [x] Uruchom `--pattern 'test_new_user_reporting.py'` i `--pattern 'test_inventory_sync.py'`; pełny gate na końcu etapu A. Aktualizuj wszystkie tłumaczenia i opis nowej opcji.
- [x] Lokalny commit z opisem ograniczeń: to naprawa symptomów raportowania, jeszcze nie resolver.

### T03. Nieinwazyjny setup i jawne zależności

**Files:** modify `install.sh`, `setup.sh`, `update_appstore.sh`, `scripts/setup_touchid_sudo.sh`, `i18n/lang_{en,pl,de,fr,es,it,pt}.sh`; create `tests/test_setup_consent.py`; modify `docs/INSTALL.md` i odpowiednie user guides.

**Interfaces:** `setup.sh --inspect` odczytuje gotowość; `--install-dependencies` jest jawnie wybierane po podglądzie listy. Brak opcji w noninteractive nie instaluje. Dodatkowa świadoma opcja `--configure-shell` obejmuje zmianę profilu; nie jest częścią skanu. Touch ID uruchamiane tylko osobnym poleceniem użytkownika.

- [x] Tests: brak brew/mas/Python, brak TTY, read-only HOME, sudo niedostępne, istniejący cudzy sudo_local, ponowne setup. Przy braku zgody command log ma zero install/PAM/profile mutations.
- [x] Uruchom i potwierdź failing test dla obecnego `install.sh` oraz automatycznego `brew install mas`.
- [x] Usuń automatyczne wywołanie Touch ID z install. Setup najpierw przedstawia plan zależności; odrzucenie jednej pozostawia działające niezależne funkcje. Gdy brak Python, pokaż instrukcję i uczciwy status niedostępnego skanu, bez pustego inventory.
- [x] Brak mas podczas zwykłego update daje `source_unavailable` i wskazówkę, nie instalację. Gdy brew/mas działa bez sudo, nie wymuszaj sprawdzania interaktywnego hasła w readiness.
- [x] Jeżeli osobny konfigurator Touch ID pozostaje: chronić obcą zawartość, wymagać skutecznego backupu, preview i osobnej zgody; unattended odmawia. Nie używać „plik jest nasz” jako założenia.
- [x] `--pattern 'test_setup_consent.py'`, pełne `bash run_tests.sh`, instrukcje 7 języków, commit etapu A.

### T04. Snapshot ze źródłami i pełnymi tożsamościami

Etap B ukończony lokalnie jako 1.6.2. Dowody i konserwatywne ograniczenia w raporcie etapu; aktywacja wykonawcy pozostaje C. Po zamknięciu B właściciel zlecił kontynuację C-E do końca, nadal bez publikacji, live updates i zmian landing.

**Files:** create `lib/python/inventory_model.py`, `lib/python/inventory_collect.py`, `tests/test_inventory_collect.py`, `tests/fixtures/new_user/`; modify `lib/python/inventory.py`, `lib/python/inventory_sync.py`, `lib/brew.sh`.

**Interfaces:** `collect_snapshot(roots: list[str], providers: Providers, previous: dict | None) -> dict`; `validate_snapshot(value: dict) -> dict`. `Providers` zawiera wstrzykiwalne funkcje `read_bundle(path)`, `list_mas()`, `list_brew(prefix)`, `list_cli(prefix)`, każda zwraca SourceResult; nie uruchamia nieznanych binariów.

- [x] Testy rozdzielają ok-empty, brak narzędzia, timeout, uszkodzony JSON, częściowy skan i permission denied. Receipt bundle musi pozostać nawet przy pustym/nieudanym mas. Package targets mają te same testy presence/freshness/source, także dwa prefixy npm i Node spoza zarządzanego prefixu.
- [x] Testy zachowują dwie ścieżki tej samej aplikacji, rozdzielają ChatGPT/Codex, warianty beta, aplikacje o zmienionej nazwie i app bez bundle ID. Nie utożsamiaj nazwy ani bundle ID z jedną instalacją.
- [x] Zbieraj static metadata bez launch. Domyślne rooty `/Applications`, `~/Applications`, `/System/Applications`; kontrolowane zagłębienie do 3 poziomów folderów organizacyjnych, zatrzymanie na bundle. Bez wejścia do Contents, innych HOME, podmontowanych DMG i zewnętrznych woluminów. Jawne optional roots, limit rekordów i rozmiaru metadanych.
- [x] Lstat/realpath, ochrona przed pętlą symlink, duplikatami i wyjściem poza zatwierdzone rooty. Zachowaj lokalną ścieżkę i flagę symlink; symlink celu aktualizacji wymaga dodatkowej kontroli.
- [x] Brew metadata pozyskuj przez wspólną warstwę. Zmapuj cask artifact paths i target rename; uwzględnij prefix/AppDir. Brak metadata oznacza partial, nie potwierdzone ownership.
- [x] Scan package/CLI z receipt/manifestów managerów; nie wykonuj `--version` dla dowolnego pliku odnalezionego w PATH. Istniejące znane CLI probes mają whitelist i timeout.
- [x] Testy nazw Unicode, znaków sterujących, pipe, uszkodzonego plist, ogromnego pliku, linków i dwóch rootów. Brak ręcznego podpinania folderu „Agent” do wykluczeń.
- [x] `--pattern 'test_inventory_collect.py'`; zapis snapshotu w shadow mode 0600/0700, brak zmiany wyboru działań. Commit.

### T05. Wspólny resolver pochodzenia i możliwości

**Files:** create `lib/python/source_resolver.py`, `lib/python/app_recipes.py`, `config/app_recipes.json`, `tests/test_source_resolver.py`; modify `lib/internet_registry.sh`, `lib/python/brew_casks.py`.

**Interfaces:** `resolve_target(target: dict, snapshot: dict, recipes: dict) -> dict` przyjmuje CurrentTarget i zwraca Resolution z TargetRef, zarówno dla aplikacji jak i pakietów. `load_recipes(path: str) -> dict` waliduje schema i odrzuca komendy/nieznane pola. Adapter zgodności odczytuje obecny TXT jako możliwości, bez deklaracji lokalnego ownership.

- [x] Tabela testów: MAS-only, brew-only, vendor-only, MAS+brew, user/system duplicate, źródło unknown, niezgodny Team ID, cask token różny od bundle name, cask wiele artefaktów, TestFlight, enterprise signal.
- [x] MAS-only CapCut wybiera app_store. Stale brew record plus receipt daje conflict i brak prawa do brew/vendor. Sam cask w katalogu publicznym nie jest dowodem brew ownership.
- [x] Framework Sparkle/Electron jest capability evidence, nie źródłem ani handlerem z prawem do instalacji. Unknown źródło z SUFeedURL pozostaje unknown/check-only-candidate.
- [x] Usuń aliasy łączące różne produkty; renames wiąż tylko z dowodem tożsamości. Apple/system wymaga chronionej lokalizacji, nie nazwy/prefiksu bundle ID.
- [x] Recepty zaczynają od istniejących znanych adapterów. Nowa niezbadana aplikacja nie dostaje automatycznie reviewed_direct. Zmiana Team ID lub transfer producenta wymaga review recepty.
- [x] `--pattern 'test_source_resolver.py'`, tests registry safety. Commit.

### T06. Jeden plan działań i guard przed każdą mutacją

**Files:** create `lib/python/update_plan.py`, `lib/update_policy.sh`, `tests/test_update_plan.py`; modify `update_all.sh`, `update_internet_apps.sh`, `update_brew.sh`, `update_appstore.sh`, `update_npm_cli.sh`, `lib/vendor_direct.sh`, `lib/run_lock.sh`.

**Interfaces:** `build_plan(snapshot: dict, resolutions: list[dict], policies: dict, now: str) -> dict`; `authorize_action(action: dict, current: dict, policy: dict, now: str) -> dict`. Bash `mac_update_authorize_action <plan_path> <action_id>` zwraca 0 allowed, 10 deferred, 1 error i zapisuje strukturalny GuardResult do session dir.

- [x] Dodaj tests komend: absent, stale, unknown, source_conflict, changed identity/path, removed after plan, user-opened app, old plan i policy change zawsze mają zero mutacji.
- [x] Wdróż plan read-only pod `update_all.sh --plan`; `--dry-run` korzysta z tych samych decyzji. Dopuszczalne są własne logi/session files, bez zmian inventory/history/preferences i bez pobierania payloadów. Odróżnij check wymagający sieci od offline scan.
- [x] Każdy entrypoint uruchomiony bez orchestratora buduje albo wymaga planu; nie może ominąć guard. Nie przekazuj autoryzacji jako samego globalnego `YES=1`.
- [x] Brew wykonuj per cask po powtórnym odczycie, nie jednym batch po dawnej kwalifikacji. Uwzględnij wszystkie top-level artifacts; absent/new artifact i opaque pkg są manual/deferred do przeglądu skutków. Wykryty receipt blokuje zewnętrzny kanał.
- [x] MAS: tylko ID z lokalnej instalacji i pomiaru outdated; nie `install/get` ani katalogowe ID. Brak App Store ID oznacza manual/check, nie wyszukanie po nazwie i instalację pierwszego trafienia.
- [x] Node/native CLI: zachowuj istniejący manager/prefix. Przejście npm do native, usuwanie duplikatów i instalacja zarządzanego Node to osobny plan ze zgodą, nie efekt zwykłej aktualizacji. Znane bootstrap CLI nadal wyłącznie jawnie.
- [x] Blokada per użytkownik i canonical target między checkoutami, identyfikacja żywego właściciela, stale recovery. Nie kasować cudzej aktywnej blokady. Test dwóch klonów z tym samym fixture zasobem.
- [x] `--pattern 'test_update_plan.py'`, obecne tests run_lock/cli_duplicates/brew/appstore/shared guards; commit. Shadow mode do zakończenia T09.

### T07. Odwracalna migracja inventory i notatek

**Files:** create `lib/python/inventory_store.py`, `lib/python/inventory_render.py`, `tests/test_inventory_migration.py`; modify `build_inventory.sh`, `update_all.sh`, `lib/python/inventory_sync.py`, `templates/APPLICATIONS.md.template`, `.gitignore`, `dev_sync` selection rules tylko jeśli konieczne.

**Interfaces:** `reconcile_inventory(previous: dict | None, snapshot: dict) -> dict`; `prepare_migration(markdown: str, snapshot: dict) -> dict`; `commit_migration(proposal: dict, state_dir: str, report_path: str) -> dict`; `render_inventory(inventory: dict, notes: dict, locale: str) -> str`.

- [x] Tests poprawny empty usuwa bieżące membership; unknown/partial zachowuje stale, bez prawa do update. Zastąp istniejący test `test_inventory_sync.py:122-140` odrębnymi testami obu znaczeń.
- [x] Świeży użytkownik startuje z pustego lokalnego snapshotu. Stary Markdown nie ustala obecności; notes są zachowane. Grupa 1 również generowana z obserwacji. Obce lub nieznane pochodzenie dostaje review migration, bez odziedziczenia zgód.
- [x] Migracja tworzy backup oryginalnych bajtów z SHA-256, proposal, mapowanie zachowanych notatek i listę orphan notes, bez ich kasowania. Ogranicz ilość danych w podsumowaniu, bez autoeksportu.
- [x] Store zapisuje hash ostatniego wygenerowanego Markdown. Zmiana ręczna przed przygotowaniem migracji, między prepare i commit albo przy późniejszym renderowaniu blokuje nadpisanie. Zachowaj zmodyfikowane bajty, przygotuj import notatek z podglądem; dopiero jego akceptacja pozwala renderować nowy raport. Bezpieczny unattended pozostawia plik i zgłasza konflikt, nie traci notatek. Test compare-and-swap sprawdza ponownie hash tuż przed replace.
- [x] Przed commit sprawdź schema, uprawnienia, wolne miejsce i kompletność minimum lokalnego skanu; zapisz journal. Zapis JSON i raportu jest wieloplikowy, więc użyj generation ID i recoverable commit marker; nie udawaj atomowości całego zestawu przez jeden rename.
- [x] `build_inventory.sh --rebuild` oznacza ponowne zebranie obserwacji, zachowuje notatki i jawne wybory pasujące do tożsamości. Zwykły rebuild nie importuje prywatnych plików z innej maszyny.
- [x] W razie awarii rollback przywraca bajty poprzedniego raportu, poprzedni generation i polityki. Nie zmienia aplikacji. Idempotentny rerun kończy albo wycofuje rozpoczętą migrację.
- [x] Test fault injection po każdym zapisie: pełny dysk, brak permissions, SIGTERM/niekompletny journal, corrupt JSON, nieobsługiwany schema major, ręczne dopiski i dwie równoległe migracje. Unknown schema oznacza odmowę nadpisania.
- [x] `--pattern 'test_inventory_migration.py'`, idempotencja drugiego skanu i rollback round-trip. Jeden niezależny przegląd migracji przed aktywacją. Commit.

### T08. Zapamiętywane decyzje i uczciwe wyniki

**Files:** create `lib/python/user_policy.py`, `tests/test_user_policy.py`; modify `lib/ui.sh`, `lib/python/run_summary.py`, `scripts/report_chronic_warnings.sh`, `scripts/report_update_coverage.sh`, wszystkie locale.

**Interfaces:** `get_decision(target: dict, resolution: dict, policies: dict, now: str) -> dict | None`; `record_decision(decision: dict, policies: dict) -> dict`; `decision_is_valid(decision: dict, target: dict, resolution: dict, now: str) -> bool`. Target to CurrentTarget dla aplikacji albo pakietu; lookup polityk używa TargetRef.

- [x] Test wyboru preserve-source, 7-dniowego defer, ignore, expiry i unieważnienia po zmianie źródła/tożsamości. Testy dowodzą, że preserve_source nie autoryzuje update, manager_update nie autoryzuje direct_update ani native_launch, a brak decyzji w `-y` daje defer także dla formula/npm/Node. Zmiana wersji sama nie wymusza nowego pytania.
- [x] Pytanie tylko o rzeczywistą niejednoznaczność/skutek. Dla MAS-only CapCut brak pytania o brew; dla MAS+stale cask czytelny konflikt z domyślnym odroczeniem i opcją zachowania MAS bez usuwania caska.
- [x] `-y`, EOF, timeout i noninteractive nie wybierają migracji ani pierwszego launch. Decyzje do podjęcia pokaż raz w końcowym zestawieniu; pozostałe aplikacje kontynuują.
- [x] Wyniki: `manual_by_policy`, `ignored_by_policy`, `deferred_by_user`, `source_conflict`, `source_unavailable`, `scan_partial`, `removed_since_scan`, `current_verified`, `update_unverified`, `update_failed`, `recovery_required`. Mapuj na istniejące summary v4 addytywnie.
- [x] Oczekiwane manual/ignore nie zwiększa chronic warning streak. Awaria uzgodnionego działania i aktywny konflikt nadal widoczne. Stale cache nigdy nie zamienia się w świeże verified.
- [x] Jeden resolver dla terminala, coverage, Markdown i JSON; usunąć niezależne klasyfikacje i logikę opartą na tekstach tłumaczeń.
- [x] `--pattern 'test_user_policy.py'` i obecne summary/status/feed_state tests; commit.

### T09. Domknij pobieranie i transakcję wymiany

**Files:** create `lib/python/download_policy.py`, `lib/python/update_transaction.py`, `tests/test_download_policy.py`, `tests/test_update_transaction.py`; modify `lib/fetch.sh`, `lib/vendor_direct.sh`, `update_internet_apps.sh` i istniejące copy callers.

**Interfaces:** `validate_download_url(url: str, allowed_hosts: list[str]) -> str`; `validate_redirect_chain(urls: list[str], allowed_hosts: list[str]) -> bool`; `prepare_transaction(action: dict, current: dict) -> dict`; `recover_transaction(journal: dict, observed: dict) -> dict`. Shell `copy_verified_app <staged_app> <absolute_existing_dest> <action_id>`; migracja wszystkich callerów, bez fallbacku do domyślnej /Applications.

- [x] Tests URL userinfo, port, Unicode/IDNA, host suffix tricks, HTTPS downgrade, cross-host redirect, localhost/private IP, IPv6, DNS rebinding policy i signed URL. Userinfo odrzucać; port domyślnie 443. Dla bezpośredniej instalacji wyłącznie reviewed hosty i jawne CDN.
- [x] Waliduj każdy redirect przed kolejnym pobraniem; samo końcowe `effective_url` wykrywa problem za późno. Nie poszerzaj allowlist automatycznie. Dla sieci firmowej/proxy nie wyłączaj TLS; kontrolowane odroczenie.
- [x] Wymagaj pierwotnego celu i identity fingerprint przed staging oraz bezpośrednio przed swap. Brak celu daje removed_since_scan. Cel z niezgodnym receipt/source/team albo działający/unknown-state jest odroczony.
- [x] Dest może być w zatwierdzonym ~/Applications albo /Applications, staging i backup na tym samym woluminie. Bez rozszerzania uprawnień ani przenoszenia aplikacji.
- [x] Journal: prepared, backed_up, swapped, verified, rolled_back/recovery_required. SIGKILL/power loss obsługiwane przy kolejnym uruchomieniu przez odczyt journal i obserwację obu bundle; zachowaj jedyną dobrą kopię, nie usuwaj backupu przy niepewności.
- [x] Zachowaj signature, Team ID, bundle ID, minOS/arch/channel, kontrolę wersji i rollback. Generic Sparkle direct jest wyłączony, jeśli nie potrafimy zweryfikować wymaganego podpisu EdDSA lub reguł update; użyj reviewed recipe/native path.
- [x] Tests wyłącznie na fixture root, stuby native tools, fault injection na każdym etapie; żadnych prawdziwych /Applications zapisów. Dodatkowo test obecny cel znika podczas download i test user otwiera app w trakcie staging.
- [x] `--pattern 'test_download_policy.py'`, `--pattern 'test_update_transaction.py'`, pełny gate. Jeden przegląd bezpieczeństwa połączony z migracją T07; aktywuj model B/C dopiero po jego uwagach. Commit.

### T10. Bezpieczna autoadaptacja nowych aplikacji

**Files:** create `lib/python/app_capabilities.py`, `tests/test_app_capabilities.py`; modify `lib/python/inventory.py`, `scripts/scan_update_feeds.sh`, `scripts/scaffold_internet_app.sh`, `scripts/report_update_coverage.sh`, user guides.

**Interfaces:** `detect_capabilities(instance: dict, metadata: dict) -> list[dict]`; `propose_recipe(instance: dict, capabilities: list[dict]) -> dict`; `redact_proposal(proposal: dict) -> dict`. Propozycja nigdy nie trafia do wykonywalnego config bez review.

- [ ] Wykorzystaj istniejący detektor Sparkle/Electron/Squirrel/receipt; nie duplikuj parserów. Inventory automatycznie nadaje źródło tylko tam, gdzie istnieje wystarczający dowód; capability może pozostać probable.
- [ ] Testy dowodzą: nowe app pojawia się raz, bez install/launch/network; maszyna z 50 nieznanymi app nie generuje 50 błędów. Pokazuje „50 wykrytych, 12 z możliwym updaterem, wybierz obsługę”.
- [ ] Opcjonalne check-only wymaga zatwierdzonego feedu/polityki, ograniczeń HTTP, schema/size/timeouts i zgodności kanału. Brak sprawdzalnego feedu to manual, nie błąd.
- [ ] Native updater uruchamiany tylko po pierwszej zgodzie, z informacją, że aplikacja może się otworzyć. Samo launch nie daje updated/current_verified; sprawdź wynik albo wyświetl unverified.
- [ ] Recepty mogą korzystać z read-only danych Homebrew jako propozycji. Nie uruchamiaj `brew install --adopt`, uninstall ani naprawy źródła w tle. Zgodność nazwy lub wersji nie oznacza tożsamości.
- [ ] Eksport propozycji dopiero po preview. Usuwa path/user/receipt/URL query/tokens; pozostawia publiczne bundle ID, dane adaptera i syntetyczny przykład. Brak automatycznego uploadu/zgłoszenia issue.
- [ ] Fixture kontraktowy każdej nowej recepty: absent, current, newer, older/feed regression, offline, bad signature, wrong identity, wrong arch/minOS, running, source conflict. Dopiero potem podniesienie capability do reviewed_direct.
- [ ] `--pattern 'test_app_capabilities.py'`, full gate, docs w 7 językach; commit.

### T11. Akceptacja, dokumentacja i ograniczone wydanie

**Files:** create `tests/test_new_user_profiles.py`, `tests/fixtures/new_user/profiles/`; modify `docs/agents/acceptance_checklist.md`, `docs/agents/{architecture,critical_rules,scripts,exit_codes,security}.md`, `docs/INSTALL.md`, `docs/user/*/GUIDE.md`, wszystkie README, `CHANGELOG.md`; nowy datowany raport wyników. VERSION/tag tylko po decyzji.

**Interfaces:** profile fixture opisują snapshot źródeł, oczekiwany plan, dozwolone komendy i efekty. Kontrola listy wykonanych poleceń jest równie ważna jak końcowy tekst.

- [ ] Przejdź macierz poniżej na fixture z deny-by-default mutacjami i siecią; brak poprawności jednego profilu blokuje deklarację wsparcia tego profilu.
- [ ] Uruchom pełny runner macOS i przenośną bramkę Linux. Python 3.9 i aktualny dostępny Python: minimum syntaktyka/importy i krytyczne testy. Nie instaluj brakujących interpreterów bez uzgodnienia; wynik nieprzeprowadzony pozostaje nieprzeprowadzony.
- [ ] Zapisz czasy, liczby pytań, nieoczekiwane komendy i false warnings. Offline static fixture 100 bundle: budżet 5 s bez sztucznych opóźnień; z providerami timeouty per source, brak nieograniczonego czekania.
- [ ] Dopiero po zgodzie: ręczne próby na disposable koncie/Macu, najpierw scan/plan, potem wybrane bezpieczne aktualizacje. Zwykły nowy account na hoście nadal widzi systemowe /Applications; nie traktować go jako pustej maszyny.
- [ ] Próby: najstarszy wspierany macOS, bieżący, co najmniej dwa profile użytkownika; mas signed-out, standard user, niestandardowy AppDir. Nie deklarować wszystkich OS na podstawie jednego hosta.
- [ ] Test rollback inventory osobno od rollback aplikacji. Odrębnie zatwierdzane prawdziwe instalacje, GUI, privileged pkg i restart systemu. Niczego takiego nie uruchamia automatycznie runner.
- [ ] Aktualizuj dokumentację w tym samym change; stare audyty i receipts pozostają niezmienione. README opisuje ograniczenie multi-artifact/pkg i źródła niepewne zamiast absolutnej obietnicy.
- [ ] Ascendo: ustalić scope parity i wersjonowanie przed release. Landing synchronizować dopiero z zatwierdzonymi faktami wydania; to osobny change z jego build gate, nie część obecnego audytu.
- [ ] Lokalny final diff i pełne testy, then review. Publikacja/merge dopiero po zgodzie i zielonym CI; po publikacji sprawdzić main, remote, tag i rzeczywisty artefakt clean-install.

### T12. Research kanałów i doradca latest stable

**Files:** create `docs/catalog/SOURCE_RESEARCH.md`, `lib/python/channel_advisor.py`, `lib/python/channel_probes.py`, `tests/test_channel_advisor.py`, `tests/fixtures/channels/`; extend `config/app_recipes.json`; modify istniejące `scripts/scan_update_feeds.sh`, `scripts/report_update_coverage.sh`.

**Interfaces:** `collect_channel_observations(recipe: dict, environment: dict, fetch: Callable, cache: dict, now: str) -> list[dict]`; `recommend_channel(recipe: dict, observations: list[dict], installed: dict | None, user_preference: dict) -> dict`; `compare_channel_releases(recipe: dict, left: dict, right: dict) -> str` zwraca `newer | equal | older | incomparable`. Shell `scripts/report_update_coverage.sh --compare-sources` jest read-only, `--refresh` pomija cache w granicach limitów.

- [x] Zrób pełną macierz każdej pozycji bieżącego rejestru: product/edition, oficjalny vendor/native updater, brew token, MAS ID i npm package tylko gdy to ten sam produkt, stable endpoints, schemat wersji, licencja, minOS/arch i istniejące dowody. Rozdziel połączone produkty takie jak ChatGPT/Codex przed liczeniem pokrycia. Nie wymyślaj brakujących Team ID i store ID; unknown wyłącza automatyczne działanie danej ścieżki.
- [x] Research wyłącznie z oficjalnych producentów, App Store i repozytoriów managerów. Każdy wiersz ma URL, datę, zakres dowodu i stan reviewed/unknown. Zbadanie źródeł nie jest live-install proof; niedostępne źródło oznacz jako niedostępne.
- [ ] Fixtures: vendor stable nowszy niż brew, brew i vendor identyczny payload, MAS pierwszy, MAS późniejszy, npm latest wskazuje prerelease, różne GUI/CLI wersje, stable nowa ale minOS za wysokie, staged rollout, region unknown, nieporównywalna numeracja. Rekomendacja nie może promować beta/RC/nightly ani wersji niekompatybilnej.
- [ ] Porównuj global latest stable, compatible stable i offered version osobno. Stable potwierdzaj regułami źródła (np. prerelease flag, kanał feedu, oficjalne release notes), nie samym słowem latest ani regexem wersji. Wersja widoczna publicznie w MAS to listed, dopóki nie potwierdzono offered dla użytkownika.
- [ ] Rekomenduj nowszą potwierdzoną kompatybilną stable; przy remisie zachowaj istniejący kanał. Gdy source unavailable/incomparable, nie stwierdzaj, że inny kanał jest szybszy. Dla istniejącej aplikacji zwracaj migration_required, bez wykonania migracji. Preferowany native updater może współistnieć z instalacją brew, jeśli zbadano zgodność ownership i polityki aktualizacji.
- [ ] Runtime sprawdza tylko lokalne/wybrane aplikacje, nie cały internet. Metadata fetch przez politykę T09, bez uruchamiania app czy package scripts. Cache 24 h z datą; per-request timeout 10 s, max 3 jednoczesne żądania i 1 na host, budżet interaktywnego sprawdzenia 60 s. Niesprawdzone pozycje pozostają pending/unknown. HTTP429 respektuje retry-after, nie blokuje setupu pętlą.
- [ ] Nieznana aplikacja: najpierw statyczna identyfikacja i match do zaufanej recepty. Automatyczny odczyt dowolnego SUFeedURL nie jest research potwierdzającym zaufanie; brak reviewed source daje propozycję weryfikacji/check-only i unknown rekomendację.
- [ ] Historia opóźnień lokalna, tylko podczas uruchomionych sprawdzeń; brak nowego harmonogramu i telemetrii. Oddziel published_at od first_observed_at, zapisuj przedziały niepewności. Etykietę „zwykle szybszy” dopuszczaj przy minimum 5 dopasowanych stabilnych wydaniach w okresie co najmniej 30 dni; pokaż sample size i podstawę czasów, nadal bez gwarancji przyszłych wydań. Jeśli brak porównywalnych dat, pokazuj wyłącznie „obecnie oferuje nowszą stable”.
- [ ] `--pattern 'test_channel_advisor.py'`, schema lint wszystkich recept i kompletność wierszy research; aktualizuj docs z konkretnymi nieustalonymi przypadkami. Commit bez twierdzenia, że każdy app/source jest sprawdzony live.

### T13. Katalog aplikacji, wybór kanału i podgląd instalacji

**Files:** create `lib/python/setup_catalog.py`, `lib/python/install_plan.py`, `lib/setup_catalog.sh`, `tests/test_setup_catalog.py`, `tests/test_install_plan.py`; modify `setup.sh`, `install.sh`, wszystkie locale i `docs/INSTALL.md`.

**Interfaces:** `build_catalog_view(snapshot: dict, recipes: dict, recommendations: list[dict], filters: dict) -> dict`; `build_install_plan(selections: list[dict], snapshot: dict, recipes: dict, now: str) -> dict`; `validate_install_plan(plan: dict) -> dict`. `setup.sh --catalog` otwiera menu, `setup.sh --install-plan <path>` wymaga konkretnego preview i świeżego potwierdzenia. `install.sh` może zaproponować wejście do menu, nigdy nie wykonuje wyboru automatycznie.

- [ ] Tests: katalog istnieje bez prywatnego inventory autora, wszystkie wybory domyślnie puste, zaznaczenie app nie uruchamia polecenia, cancel/EOF/no-TTY/`-y` nie instaluje. Zwykły build_inventory pozostaje skanem, może tylko wskazać opcję przejścia do setup --catalog.
- [ ] Menu pokazuje: już zainstalowane i ich kanał; dostępne nowe aplikacje; poziom dowodu; rekomendowany source/updater i latest stable z datą; inne zbadane kanały; ograniczenia/licencję. Nie udawaj, że każda pozycja ma brew/npm/MAS. Kliknięcie źródła z niezgodną edycją/arch nie może dodać selection.
- [ ] Dla obecnej instalacji nie oferuj domyślnie install. Pokaż aktualizację zachowującą kanał albo osobną propozycję migracji z skutkami. Pierwsze wdrożenie nie wykonuje automatycznych migracji kanału; umożliwia zapoznanie się z instrukcją i ponowny scan po ręcznej zmianie.
- [ ] Instalowalne automatycznie są tylko recepty z osobno zatwierdzonym install adapterem i fresh-install acceptance. Same update-live-tested mogą być oglądane, z oficjalnym linkiem do instalacji ręcznej. Kontrolowane testy pierwszej instalacji w disposable środowisku są możliwe jako osobna procedura walidacji recepty przed włączeniem jej w publicznym menu.
- [ ] Preview rozdziela nowe app, już spełnione requirements, wymagane nowe dependencies, opcjonalne dodatki, uprawnienia i ręczne kroki. Pokaż wersję/source/destination, potrzebę admin, koszt/licencję jako unknown gdy niezweryfikowane, rozmiar jako szacunek lub unknown. Nie pokazuj „bezpłatna” bez dowodu. Brak danych o wymaganiach uniemożliwia automatyczne uruchomienie tej pozycji.
- [ ] Zgoda dotyczy listy i plan_digest. Żadnego domyślnego „zainstaluj wszystko”; użytkownik może jawnie wybrać wiele aplikacji, widząc wspólne zależności. Rewizja recepty, wersji lub dependency graph przed wykonaniem wymaga nowego preview.
- [ ] Testuj menu w Bash3.2: cyfry, prosty wybór wielu pozycji, back/cancel, bez wymagania zewnętrznego TUI i bez instalowania narzędzi tylko do wyświetlenia menu. Gdy brak Python do pełnego planu, shell pokazuje ograniczony bootstrap preview wymaganej zależności, a reszta czeka na jego świadome wykonanie.
- [ ] `--pattern 'test_setup_catalog.py'`, `--pattern 'test_install_plan.py'`; testy 7 języków i plan serializacja/odczyt bez sekretów. Commit.

Przykładowy widok, bez twierdzenia o rzeczywistych wersjach konkretnego produktu:

```text
Example App                  nie jest zainstalowana
Rekomendacja: producent      najnowsza zgodna stable, sprawdzono dzisiaj
Aktualizacje: native updater
Homebrew: ta sama stable     dodatkowo wymaga Homebrew
App Store: starsza stable    data publikacji potwierdzona; dostępność konta nieznana
Dowody: aktualizacja testowana; pierwsza instalacja producenta wymaga weryfikacji

[ ] Wybierz aplikację i źródło
    Podejrzyj wymagania
    Pomiń / wróć
```

### T14. Zatwierdzane requirements i bezpieczny wykonawca pierwszej instalacji

**Files:** create `lib/setup_install.sh`, `lib/python/install_execution.py`, `tests/test_install_execution.py`, `tests/test_setup_requirements.py`; modify `setup.sh`, `lib/fetch.sh` tylko przez zatwierdzone API, moduły store/lock oraz 7 locale.

**Interfaces:** `resolve_requirements(selections: list[dict], environment: dict, recipes: dict) -> dict` zwraca DAG i brakujące warunki; `authorize_install(action: dict, current: dict, consent: dict, now: str) -> dict`; `record_install_result(action: dict, observed: dict, journal: dict) -> dict`. Shell `setup_execute_install_action <plan_path> <action_id>` oraz odrębny `install_verified_app <staged_app> <expected_absent_destination> <action_id>`; nie osłabiaj copy_verified_app/update guard.

- [ ] Failing tests: app pojawia się po preview, destination symlink, source conflict, changed plan, wygasła zgoda, nieznany dependency, cycle, istniejący nowszy dependency, partial failure i cancel. Dozwolone mutacje dokładnie równają się zatwierdzonym akcjom; zero update/adopt/uninstall jako ukrytego fallbacku install.
- [ ] Requirements rozpoznawaj przed instalacją: wymagany Python/CLT, Homebrew tylko dla wybranego kanału, mas tylko dla funkcji które go potrzebują, Rosetta tylko dla wybranej zgodnej aplikacji i po osobnym świadomym wyborze. Dostępność Intel-only app nie znosi ograniczeń wspieranego macOS. Accessibility, Apple Account, licencje i MDM nie są automatycznie „naprawiane”. PAM/Touch ID pozostaje poza procesem.
- [ ] Rozwiązuj DAG i wersje do konkretnego planu; już spełnionych requirements nie reinstaluj/downgraduj. Jeśli Homebrew może doinstalować zależności, uwzględnij je w preview. Gdy nie da się określić skutków zewnętrznego instalatora, ręczna ścieżka zamiast obietnicy pełnej kontroli.
- [ ] Dla brew: reviewed token/tap i konkretny zakres artefaktów, brak --force/--adopt/zap. Rewalidacja po aktualizacji metadanych i tuż przed install; nowa zależność lub artefakt powoduje ponowny plan. Nie instaluj przypadkowego tokena uzyskanego przez dopasowanie nazwy.
- [ ] Dla pierwszej instalacji vendor bundle: niezależnie reviewed bundle ID/Team ID i source, HTTPS/redirect allowlist, podpis/Gatekeeper/minOS/arch/channel i integralność artefaktu. Checksum z tego samego feedu nie zastępuje tożsamości producenta. Nie wykonuj dowolnego vendor shell ani generycznego pkg; adaptery takiego typu wymagają oddzielnego kontraktu i testów.
- [ ] App Store v1: manual_acquisition otwiera oficjalną stronę tylko po wyborze. Użytkownik sam loguje się, akceptuje warunki i decyduje o zakupie. Po powrocie ponowny scan potwierdza źródło/tożsamość; samo otwarcie sklepu nie jest installed. Brak mas nie blokuje otwarcia oficjalnej strony.
- [ ] Instalator i updater współdzielą blokadę zasobów. Nowy app instaluj przez staging do zatwierdzonej pustej ścieżki, bez launch po instalacji. Jeśli destination pojawi się w trakcie, zatrzymaj akcję. Capture podpisu po instalacji i nowy snapshot, dopiero wtedy wynik installed_verified.
- [ ] Journal rozróżnia nowo utworzone pliki od istniejących. Po porażce usuwa wyłącznie własne niesfinalizowane staging; nie usuwa współdzielonych zależności ani innej aplikacji. Częściowo udane instalacje zostają jawnie wykazane. Resume jest nowym planem z preview, nie efektem zwykłego update_all.
- [ ] `--pattern 'test_install_execution.py'`, `--pattern 'test_setup_requirements.py'`, pełny gate. Jeden przegląd bezpieczeństwa etapu E przed publicznym włączeniem wykonawcy, bez osobnego review każdego helpera. Commit.

### T15. Akceptacja katalogu i synchronizacja obietnic produktu

**Files:** create `tests/test_catalog_acceptance.py`, `docs/catalog/ACCEPTANCE.md`; modify wszystkie README/user guides, `docs/INSTALL.md`, `docs/agents/acceptance_checklist.md`, `CHANGELOG.md`. Osobny change repo landing: `src/lib/site.ts`, locale EN/PL i chrome EN/PL, strony/FAQ/instrukcje objęte zmianą, JSON-LD generator gdy wymaga go treść, `public/llms.txt`, `public/llms-full.txt` i dokumentacja.

**Interfaces:** publiczny sanitized catalog manifest z app/source/updater i verification state; audytowany eksport z recept, bez danych maszyn. Liczniki „obsługiwane”, „sprawdzone aktualizacje”, „sprawdzone pierwsze instalacje” mają różne definicje; jedna aplikacja z trzema źródłami nie staje się trzema aplikacjami w liczniku.

- [ ] Matryca nowych testów poniżej; contract tests każdej installable recipe i rekomendacji latest stable. Każda pozycja katalogu ma research row, nawet gdy wynik to unsupported/unknown/manual.
- [ ] Na fixture: scan nigdy nie instaluje; menu bez wyboru nigdy nie instaluje; update_all nie konsumuje starego InstallPlan; instalator wykonuje wyłącznie zatwierdzone app+deps i aktualizuje lokalne inventory po faktycznej obserwacji.
- [ ] Po osobnej zgodzie wykonaj fresh-install acceptance wybranych recept w disposable macOS. Zapisz datę, wersję, kanał, system, wymagania i wynik bez prywatnych danych. Przed rozszerzeniem menu kolejne recepty przechodzą tę samą bramkę, nie dziedziczą oznaczenia autora „działa u mnie”.
- [ ] Potwierdź recommendator na minimum: vendor ahead, brew ahead/identyczny, MAS ahead, brak danych, incompatible latest i prerelease-only. Uczciwie oddziel bieżącą dostępność od historycznej szybkości; bez źródła dat brak etykiety „najszybszy”.
- [ ] Copy produktu: „Aktualizacje dotyczą zainstalowanych aplikacji. Opcjonalny katalog pozwala wybrać nowe aplikacje, źródła i zatwierdzić ich instalację wraz z wymaganiami”. Nie obiecywać, że wszystkie 47 pozycji mają sprawdzoną instalację ani że App Store zawsze jest opóźniony.
- [ ] Landing synchronizuj dopiero z rzeczywistym wdrożeniem i zgodnie z jego równoległymi zmianami; nie nadpisuj cudzej pracy. Fakty w site.ts, EN/PL parity, metadane/LLM zgodne. `npm run build` w landing ma raportować wszystkie EN/PL routes,404 i sitemap. Testy/update counts tylko z bieżącego upstream evidence.
- [ ] Pełne `bash run_tests.sh`, schema/catalog coverage, rendering/links/privacy docs, osobny landing build. Publikacja obu produktów wyłącznie po akceptacji właściciela i zgodnie z zasadą wersjonowania/parity.

## 4. Macierz akceptacyjna

| Profil / zdarzenie | Oczekiwany wynik | Zabroniony skutek |
|---|---|---|
| Pusty Mac, brak managerów | pusty inventory + capabilities unavailable | nazwy z katalogu jako lokalne, bootstrap |
| MAS CapCut, brak caska | App Store, bez konfliktu i bez cask warning | brew install/upgrade CapCut |
| MAS CapCut + stary cask | source_conflict, jedna decyzja | upgrade albo uninstall caska |
| CapCut manualny, tylko recepta brew | manual/check propozycja | automatyczne adopt |
| Tylko cask CapCut | aktualizacja tym kanałem po guard | równoległy vendor handler |
| Dwie kopie/nazwa ta sama | dwa instance records, jasna ścieżka | scalenie lub wybór po basename |
| ChatGPT i Codex | dwa niezależne produkty | aliasowa deduplikacja |
| ~/Applications tylko | zachowana ścieżka lub uczciwe defer | nowa kopia w /Applications |
| Receipt app nieobecna w mas | widoczna, MAS ID unknown | usunięcie z inventory |
| Udane zero w managerze | brak bieżących wpisów jego nieobecnych pakietów | zachowanie jako installed |
| Timeout/partial skanu | stale i źródło błędu | wyczyszczenie inventory lub current_verified |
| Nowy Sparkle/Electron app | inventory + propozycja capability | launch/download bez zgody |
| Framework bez feedu / zły plist | manual/unknown, sanitizacja | wykonywanie metadanych |
| Nazwa Agent/Launcher | widoczna, jeśli to app | odrzucenie tylko po nazwie |
| Symlink do innego woluminu | oznaczony scope, bez automatycznej mutacji | przejście poza zatwierdzony root |
| Opaque pkg/font/driver | jawny zakres, defer przy niepewności | udawanie zwykłego bundle swap |
| Cask 2 apps, jedna usunięta | defer/propozycja pakietowa | odtworzenie aplikacji |
| Nowy target w recepturze caska | opis rozszerzenia skutków | instalacja nowej top-level app w tle |
| Aplikacja usunięta po planie | removed_since_scan | reinstalacja |
| Użytkownik otwiera app po planie | defer, nadal działa | quit/kill/replacement |
| Changed Team ID/channel | wymaga review | obejście podpisu albo downgrade |
| Offline/429/stary feed | bounded retry, honest stale/unavailable | loop, launch dla testu, false current |
| Noninteractive, `-y`, EOF | odroczenie nowych decyzji | zgoda przez timeout |
| MDM/standard user/no sudo | kontrolowane ograniczenie funkcji | zmiana polityki lub privilege escalation |
| Homebrew/npm/native duplicates | odrębny plan migracji | automatyczne usuwanie alternatyw |
| Awaria między backup a swap | journal + recovery, dobra kopia zachowana | skasowanie jedynej sprawnej wersji |
| Dwa checkouty jednocześnie | jedna mutacja zasobu | równoległa podmiana |
| Powtórny run bez zmian | brak nowych pytań i zmian inventory | zdublowane wpisy i ostrzeżenia |
| Eksport diagnostyki/recepty | preview i redakcja | konto, receipt, ścieżki, sekrety |
| Menu katalogu bez wyboru | tylko prezentacja | instalacja domyślnych app/requirements |
| Zaznaczone 2 app z wspólną zależnością | 2 app + 1 jawna zależność w preview | zależności całego katalogu |
| Inny source ma nową stable | wersje i propozycja z dowodami | automatyczna migracja istniejącej app |
| Brew i native mają ten sam payload/stable | remis, zgodny updater i zachowany kanał | sztuczny konflikt albo podwójny update |
| App Store ma najnowszą stable | rekomendacja zgodna z dowodem | stała degradacja MAS w rankingu |
| Nowa beta/RC, starsza stable | wybór stable | traktowanie latest jako stable bez dowodu |
| Global stable wymaga nowszego macOS | najnowsza kompatybilna stable + informacja | niezgodna instalacja lub upgrade systemu |
| Nieporównywalne wersje GUI/CLI | incomparable | wybór npm jako zamiennika innego produktu |
| Brak historycznych danych release | tylko bieżące porównanie | „zawsze najszybszy” bez pomiarów |
| App pojawia się przed install | rescan/defer | nadpisanie/adopt |
| Brak zaufanej tożsamości first-install | manual/review | porównanie podpisu do nieistniejącego celu |
| Zmiana zależności/wersji po zgodzie | nowy preview | rozszerzenie zatwierdzonego planu |
| App Store manual acquisition | użytkownik decyduje, scan potwierdza | zakup, login albo sukces bez instalacji |
| Częściowa instalacja i przerwanie | jawne wyniki, nowy plan pozostałych | rollback kasujący wspólne zależności |

## 5. Bramki i komendy weryfikacji

Obecnie dostępne:

```bash
bash run_tests.sh
git ls-files '*.sh' | xargs shellcheck --severity=warning
git diff --check
git status --short
```

Po T01, dla każdego zadania używać wariantu z guardami, np.:

```bash
bash run_tests.sh --unit-only --pattern 'test_source_resolver.py'
bash run_tests.sh --unit-only --pattern 'test_new_user_profiles.py'
```

Te opcje nie istniały w bazie audytu; wdrożono je w etapie A dla wersji 1.6.1. Nie uruchamiać surowego unittest dla nowych integracyjnych fixture z pominięciem guardów. Przed final claim zawsze pełne `bash run_tests.sh`. README/build strony nie są gate repo Bash/Python; przy późniejszym osobnym sync landing obowiązuje jego `npm run build`.

Warunki końcowe:

- [ ] Zero niezamockowanych komend mutujących i zero zewnętrznej sieci w standardowym zestawie testów.
- [ ] Zero absent apps w normalnym przebiegu aktualizacji i zero false soft failures za brak katalogowego caska.
- [ ] Każda aktualizacja ma istniejący cel, zgodne źródło, dowody tożsamości, właściwą zgodę i wynik po wykonaniu.
- [ ] Conflict/partial/unknown nie może wejść do mutacji przez alternatywny entrypoint.
- [ ] Migracja i rollback zachowują ręczne notatki, źródłowy plik i działające aplikacje.
- [ ] Nieznane apps są widoczne; brak adaptera jest opisanym ograniczeniem, nie awarią całego run.
- [ ] Zgodność siedmiu języków, dokumentacja i schema validation przechodzą.
- [ ] Zapisano konkretne nieprzeprowadzone live scenariusze; żaden nie jest oznaczony jako passed na podstawie mocków.
- [ ] InstallPlan ma osobną zgodę i guard; zwykły scan/update/-y nie instaluje nowych aplikacji ani zależności.
- [ ] Każda rekomendacja latest stable ma identyfikację produktu/kanału, kompatybilność, datę i dowody lub jawne unknown.
- [ ] „Najszybszy kanał” jako trend wymaga historii; brak historii daje wyłącznie obecnie oferowaną wersję.
- [ ] Katalog i landing odróżniają wsparcie w kodzie, live update oraz live fresh install, bez kopiowania inventory autora.

## 6. Samodzielny prompt do przyszłego wdrożenia

```text
Pracuj w aktualnym publicznym checkout projektu macOS_updates. Realizuj etap wskazany przez właściciela.
Przeczytaj AGENTS.md oraz:
docs/implementation/NEW_USER_AUDIT_2026-11-13.md
docs/superpowers/plans/2026-11-13-source-aware-inventory.md
Przeczytaj zapisy etapów A i B w docs/implementation; sprawdź bieżący HEAD i zachowaj cudze pliki.
Etap A (T01-T03) i etap B (T04-T05) są wdrożone lokalnie; nie powtarzaj zakończonej pracy.
Kolejny etap C obejmuje T06-T09, zgodnie z zakresem bieżącego polecenia właściciela.
W trybie orkiestra kontynuuj plan bez publikacji, prawdziwych aktualizacji i zmian w landing page.
Zwiększaj trzeci człon wersji po każdym etapie, a po ukończeniu całości ustaw 1.7.0.
Każda zmiana zachowania ma failing regression na fixture, potem implementację
i zielony wynik przez guard runner. Nie pomijaj źródła, kompletności skanu ani
powtórnej kontroli celu przed mutacją. Katalog nie jest inventory ani zgodą.
Default: zachowaj istniejący kanał, nie instaluj nieobecnych aplikacji,
nie uruchamiaj nieznanych updaterów, nie zmieniaj PAM/MDM/profilu, nie usuwaj
duplikatów bez osobnego planu. Nowe aplikacje dodawaj do lokalnego inventory
i proponuj możliwą obsługę, z manual/unknown jako poprawnym wynikiem.
Wyjątek instalacyjny to osobne menu setup z konkretnym InstallPlan i zgodą
na wybrane nowe app oraz domknięty graf requirements. Nie osłabiaj update guard.
Zbadaj źródła każdej aplikacji katalogu, porównuj najnowszą kompatybilną stable
na podstawie dowodów. Bez stałej hierarchii native/brew/npm/MAS, bez beta/RC,
bez utożsamiania GUI z CLI. Jednorazowe sprawdzenie nie dowodzi trendu szybkości.
Instalacja i updater to osobne pola; migracje istniejących źródeł nie są automatyczne.
Utrzymuj kompatybilność Bash3.2, Python3.9+, exit0/10/1, summaryv4 i7 języków.
Jedna niezależna runda review migracji i bezpieczeństwa przed aktywacją modelu.
Bez nowych harmonogramów CI i bez produkcyjnych testów. Push/merge/tag/release
oraz live update wymagają osobnej zgody. Na koniec podaj testy, ograniczenia
i dokładny zakres rzeczywiście wdrożony, nie utożsamiaj mocków z live proof.
```

Właściciel akceptuje zakres i kolejność A-E; każdy rzeczywisty test systemowy oraz publikacja pozostają osobnymi decyzjami. Etapy A i B oraz research T12 zostały wykonane lokalnie. Następna jednostka to etap C; nie aktywować nowego wykonawcy przed zamknięciem jego zabezpieczeń i migracji.
