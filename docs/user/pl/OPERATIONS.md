# Obsługa (polski)

**Aktualizacje macOS 2.0.10** · dla osób, które uruchamiają program z terminala, ze skryptu lub z harmonogramu.

| Polecenie | Co się dzieje |
|-----------|---------------|
| `mac-update` | Otwiera interfejs (potrzebny terminal). |
| `mac-update run [opcje]` | Uruchomienie w zwykłym tekście. Opcje trafiają do programu aktualizującego, np. `-y`, `--skip-system`, `--non-interactive`. |
| `mac-update --cli [options]` | To samo co `mac-update run` (także `--plain`). |
| `mac-update --tui` | To samo co `mac-update`: otwiera interfejs. |
| `mac-update preview` | Przechodzi przez każdy krok i wypisuje, co by się stało. Nic nie jest aktualizowane. |
| `mac-update scan` | Odbudowuje spis aplikacji na tym Macu. Tylko odczyt. |
| `mac-update doctor` | Raport gotowości tylko do odczytu. Bez hasła, bez dziennika uruchomienia. |
| `mac-update settings` | Otwiera interfejs na karcie Ustawienia. |
| `mac-update update-self` | Sprawdza, czy jest nowsze mac-update (`--check`, domyślnie, albo `--prepare`). |
| `mac-update migrate` | Przenosi ustawienia ze starszej kopii git: `--preview` (domyślnie), `--apply`, `--undo MANIFEST`. |
| `mac-update uninstall` | Usuwa mac-update. Zobacz [UNINSTALL.md](../../UNINSTALL.md). |
| `mac-update version`, `mac-update help` | Wersja i lista poleceń. |

`macos-update` to to samo polecenie co `mac-update`, tylko pod dłuższą nazwą. Instalator dodaje oba łącza do `~/.local/bin`, a oba działają z dowolnego folderu.

`mac-update` wywołuje `update_all.sh` w folderze programu `~/.local/share/mac-update`. Jeśli pracujesz na kopii z gita, uruchom tam `bash update_all.sh`; poniższe opcje są takie same. Z `MAC_UPDATE_NONINTERACTIVE=1` interfejs nigdy się nie otwiera i nic nie czeka na odpowiedź.

## Opcje `update_all.sh`

| Opcja | Znaczenie |
|-------|-----------|
| `-y`, `--yes` | Pomiń pytanie o potwierdzenie |
| `-h`, `--help` | Pokaż listę opcji |
| `--tui`, `--cli` | Wybierz interfejs albo zwykły tekst. `--tui` bez sprawnego terminala kończy się komunikatem; można do niego dodać tylko `--dry-run` i `--skip-...`. |
| `--dry-run` | Podgląd, bez zmian |
| `--doctor` | Raport gotowości. Kod wyjścia 0: w porządku, 10: ostrzeżenia, 1: problem |
| `--verify-only` | Porównaj zainstalowane wersje z historią, niczego nie zmieniaj |
| `--json-summary` | Wypisz podsumowanie w formacie JSON na końcu |
| `--bootstrap-cli` | Zainstaluj też brakujące zarządzane narzędzie Node, Bun lub natywne narzędzie wiersza poleceń. Domyślnie wyłączone. |
| `--skip-prescan` | Pomiń wstępne sprawdzenie spisu aplikacji |
| `--skip-appstore` | Pomiń aplikacje z App Store |
| `--skip-npm` | Pomiń narzędzia terminala (npm, bun, natywne narzędzia wiersza poleceń) |
| `--skip-brew` | Pomiń Homebrew |
| `--skip-internet` | Pomiń aplikacje z internetu |
| `--skip-postupdate` | Pomiń odświeżenie spisu aplikacji i historii |
| `--skip-system` | Pomiń aktualizację macOS |
| `--skip-doctor` | Pomiń `brew doctor` w kroku Homebrew |
| `--treat-appstore-ax-as-warning` | Brak uprawnienia Dostępność zgłoś jako ostrzeżenie |
| `--non-interactive` | Dla harmonogramów: bez pytań (jak `MAC_UPDATE_NONINTERACTIVE=1`) |
| `--notify` | Pokaż powiadomienie macOS po zakończeniu |

Kroki zawsze idą w tej kolejności: sprawdzenie wstępne, App Store, narzędzia terminala, Homebrew, aplikacje z internetu, spis aplikacji, macOS. macOS jest na końcu, bo może zrestartować Maca. Jeśli wcześniejszy krok zakończył się poważnym błędem, aktualizacja macOS czeka do następnego uruchomienia.

## Zmienne środowiskowe

Wpisz je przed poleceniem, np. `MAC_UPDATE_MIN_FREE_GB=30 mac-update run`. Większość ma też odpowiednik w Ustawieniach. Pozycji ustawionej zmienną nie da się zmienić w interfejsie.

| Zmienna | Domyślnie | Do czego |
|---------|-----------|----------|
| `MAC_UPDATE_NONINTERACTIVE` | wył. | `1`: bez interfejsu i bez pytań |
| `MAC_UPDATE_DRY_RUN` | wył. | `1`: jak `--dry-run` |
| `MAC_UPDATE_SKIP_APPSTORE`, `_NPM`, `_BREW`, `_INTERNET`, `_SYSTEM`, `_PRESCAN`, `_POSTUPDATE`, `_DOCTOR` | wył. | `1`: jak odpowiednia opcja `--skip-...` |
| `MAC_UPDATE_SYSTEM_MODE` | `auto` | Aktualizacje macOS: `auto` instaluje, `notify` tylko zgłasza, `skip` nie sprawdza |
| `MAC_UPDATE_NEW_APP_MODE` | według pewności | `auto` albo `manual` dla nowo znalezionych aplikacji spoza listy sprawdzonych |
| `MAC_UPDATE_NOTIFY` | wył. | `1`: powiadomienie po zakończeniu. Dla uruchomień automatycznych: `always`, `needs_you` albo `never` |
| `MAC_UPDATE_LANG` | język systemu | `en`, `pl`, `de`, `fr`, `es`, `it`, `pt` |
| `MAC_UPDATE_HOME` | `~/.local/share/mac-update` | Folder programu |
| `MAC_UPDATE_CONFIG_DIR` | `~/.config/mac-update` | Folder ustawień |
| `MAC_UPDATE_STATE_DIR` | `~/.local/state/mac-update` | Dzienniki, pamięć podręczna, kopie zapasowe |
| `MAC_UPDATE_LOGS_DIR` | `logs` w folderze stanu | Dzienniki uruchomień |
| `MAC_UPDATE_OVERRIDES_FILE` | `overrides.tsv` w folderze ustawień | Plik wyborów dla aplikacji |
| `MAC_UPDATE_MAX_LOGS` | 30 | Ile dzienników przechowywać |
| `MAC_UPDATE_PROMPT_TIMEOUT` | 120 | Sekundy na odpowiedź, zanim użyta zostanie bezpieczna odpowiedź |
| `MAC_UPDATE_MIN_FREE_GB` | 15 | Poniżej tej ilości wolnego miejsca: ostrzeżenie i ograniczone uruchomienie |
| `MAC_UPDATE_MIN_BATTERY` | 30 | Na baterii poniżej tego poziomu (%) krok macOS jest pomijany (uruchomienie automatyczne jest wtedy pominięte w całości) |
| `MAC_UPDATE_NO_CAFFEINATE` | wył. | `1`: nie utrzymuj Maca w stanie czuwania podczas pracy |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | wył. | `1`: nie odświeżaj hasła administratora |
| `MAC_UPDATE_SUDO_KEEPALIVE_MAX` | 14400 | Przez ile sekund odświeżać (300 do 14400) |
| `MAC_UPDATE_QUIT_WAIT` | 60 | Sekundy czekania na zamknięcie aplikacji uruchomionej przez program (0 do 300) |
| `MAC_UPDATE_STAGE_WAIT` | 90 | Sekundy czekania, aż aplikacja otwarta przez program zainstaluje własną aktualizację (0 do 600) |
| `MAC_UPDATE_POST_QUIT_WAIT` | 10 | Sekundy czekania po zamknięciu takiej aplikacji, gdy aktualizacja została przygotowana |
| `MAC_UPDATE_POST_QUIT_WAIT_IDLE` | 3 | To samo, gdy aktualizacja nie została przygotowana |
| `MAC_UPDATE_OMAHA_WAIT` | 45 | Sekundy czekania na odpowiedź updatera Google (0 do 180) |
| `MAC_UPDATE_OMAHA_MAX_AGE_H` | 6 | Godziny, przez które kontrola updatera Google uchodzi za świeżą |
| `MAC_UPDATE_BTM_CHECK` | włączone | `0`: nie sprawdzaj, czy macOS blokuje aplikację w sekcji Rzeczy otwierane podczas logowania i rozszerzenia |
| `MAC_UPDATE_BTM_TIMEOUT` | 4 | Sekundy przeznaczone na to sprawdzenie |
| `MAC_UPDATE_BTM_DUMP`, `MAC_UPDATE_GOOGLE_USER_LOG`, `MAC_UPDATE_GOOGLE_SYS_LOG` | brak | Tylko do diagnostyki i testów: zapisany wykaz elementów logowania lub pliki logów updatera Google, czytane zamiast prawdziwych |
| `MAC_UPDATE_VENDOR_DIRECT` | wł. | `0`: bez pobierania bezpośrednio od twórcy aplikacji |
| `MAC_UPDATE_ALLOW_MAJOR_UPGRADE` | wył. | `1`: zezwól na duże skoki wersji, także na nową wersję główną macOS |
| `MAC_UPDATE_MAU_DEFERRAL_DAYS` | 7 | Ile dni odczekać z instalacją nowego wydania Microsoft Office |
| `MAC_UPDATE_FEED_CACHE_TTL_H` | 24 | Ile godzin używać zapamiętanych informacji o wersjach |
| `MAC_UPDATE_MAS_UPGRADE_TIMEOUT` | 1800 | Sekundy, po których jedna aktualizacja z App Store zostaje przerwana i zgłoszona |
| `MAC_UPDATE_DOCTOR_PROBE_AX` | wył. | `1`: pozwól `doctor` sprawdzić uprawnienie Dostępność (macOS może zapytać) |
| `GITHUB_TOKEN` | brak | Opcjonalny. Podnosi limit pobrań z GitHuba. Ustaw go w profilu powłoki |

## Uruchamianie automatyczne (opcjonalne)

Uruchamianie automatyczne jest domyślnie wyłączone i nie ma ustawionej pory. Włączysz je w **Ustawieniach**, sekcja **Uruchamianie automatyczne**, pozycja „Codzienna automatyzacja”. Wybierasz:

- kiedy: codziennie o godzinie, którą wpiszesz (24 h, np. 08:30), po zalogowaniu albo jedno i drugie;
- jak program da znać: po każdym uruchomieniu, tylko gdy coś wymaga Ciebie (domyślnie) albo nigdy.

Widzisz dokładnie, co zostanie zainstalowane, i potwierdzasz, zanim cokolwiek zostanie zapisane. „Uruchom test teraz” planuje jedno dodatkowe uruchomienie za kilka minut.

To samo z terminala, poleceniem `bash ~/.local/share/mac-update/scripts/install_launchagent.sh`:

```bash
bash scripts/install_launchagent.sh --daily 08:30 --notify needs_you      # codziennie o 08:30
bash scripts/install_launchagent.sh --daily 08:30 --days 1,3,5            # tylko w wybrane dni (numery 1 do 7)
bash scripts/install_launchagent.sh --at-login --delay-min 10             # po zalogowaniu, po 10 minutach sesji
bash scripts/install_launchagent.sh --once-in 5                           # jedno próbne uruchomienie za 5 minut
bash scripts/install_launchagent.sh --status                              # czy jest zainstalowane? (--check albo --status --json)
bash scripts/install_launchagent.sh --uninstall                           # usuń każdy harmonogram mac-update
```

Uruchamiaj je w folderze programu. `--notify` przyjmuje `always`, `needs_you` albo `never`.

Co robi uruchomienie automatyczne:

- Działa bez terminala i nigdy nie zadaje pytań.
- Pomija aktualizacje macOS, chyba że je włączysz; macOS tylko zgłasza wtedy, co jest dostępne.
- Pomija się samo, gdy trwa inne uruchomienie, gdy bateria jest słaba albo gdy ostatnie udane uruchomienie było mniej niż 12 godzin temu.
- To, co wymaga hasła albo ponownego uruchomienia, jest pomijane i zgłaszane jako „Wymaga Ciebie”. Dokończ to, uruchamiając `mac-update` samodzielnie.
- Wysyła jedno powiadomienie, tak jak wybrałeś. Wyniki trafiają do `launchd.out` i `launchd.err` w folderze dzienników.

## Hasła

Kroki macOS i App Store mogą potrzebować hasła administratora. W terminalu program pyta najwyżej raz na uruchomienie i odświeża je do końca pracy. Nigdy nie pyta w podglądzie ani bez terminala (uruchomienia automatyczne pomijają wtedy te kroki). Opcjonalnie: `bash scripts/setup_touchid_sudo.sh --check` pokazuje, czy Touch ID może zastąpić hasło w `sudo`. Uruchomiony bez `--check` pokaże podgląd zmiany i zapyta o zgodę.

## Gdzie co jest

| Co | Gdzie |
|----|-------|
| Program | `~/.local/share/mac-update` |
| Ustawienia i wybory dla aplikacji | `~/.config/mac-update` (`overrides.tsv`, `lang`, `reports/`) |
| Dziennik każdego uruchomienia | `~/.local/state/mac-update/logs/update_all_<data>_<godzina>.log` (przechowywane najnowsze 30, tryb 600) |
| Krótki wynik ostatniego uruchomienia | `~/.local/state/mac-update/logs/run_summary_latest.json` |
| Ustawienia interfejsu | `~/.local/state/mac-update/tui-settings.json` |
| Wyniki uruchomień automatycznych | `~/.local/state/mac-update/logs/launchd.out`, `launchd.err` |

Podgląd zapisuje dziennik w folderze tymczasowym i nie zmienia historii. W interfejsie karta **Historia** pokazuje poprzednie uruchomienia, a `L` otwiera najnowszy dziennik. Masz starszą kopię git: `mac-update migrate`.

Kod wyjścia `update_all.sh`: `0`, gdy uruchomienie przebiegło czysto albo tylko z ostrzeżeniami (aplikacja, która wymaga Ciebie, to ostrzeżenie), `1`, gdy coś się nie powiodło.

## Rozwiązywanie problemów

Zacznij od `mac-update doctor`. Sprawdza platformę, Pythona, curl, Homebrew, `mas`, Touch ID, miejsce na dysku, zasilanie, sieć i sam program.

| Problem | Co zrobić |
|---------|-----------|
| `mac-update: command not found` | Otwórz nowe okno terminala. Jeśli to nie pomaga, `~/.local/bin` nie jest w `PATH`: uruchom instalator ponownie z `--configure-shell` albo dodaj ten folder sam. |
| `mac-update` uruchamia inny program | Inny program o tej nazwie jest w `PATH` wcześniej. Instalator ostrzega o tym i podaje plik tego programu. Uruchom bezpośrednio `~/.local/bin/mac-update` albo usuń lub zmień nazwę tego drugiego pliku. |
| Interfejs się nie otwiera | Potrzebuje terminala, Pythona 3 i `TERM` innego niż `dumb`. W przeciwnym razie użyj `mac-update run`. |
| Instalator pisze, że suma kontrolna się nie zgadza | Niczego nie zainstalowano. Spróbuj później; jeśli to się powtarza, zgłoś to. |
| Aplikacja jest w „Wymaga Ciebie” | Zobacz tabelę „Co znaczy Wymaga Ciebie” w [GUIDE.md](GUIDE.md). |
| Krok App Store kończy się kodem 2 | Terminal nie ma uprawnienia Dostępność. Zezwól w Ustawieniach systemowych, Prywatność i ochrona, Dostępność, albo dodaj `--treat-appstore-ax-as-warning`. |
| Brakuje `mas` albo jest za stare | Program to zgłasza i nigdy nie instaluje go sam. Zainstaluj je samodzielnie przez Homebrew (`brew install mas`). |
| App Store wymaga zalogowania | Otwórz App Store, zaloguj się i uruchom ponownie. |
| Brakuje Homebrew | Zainstaluj go ze strony <https://brew.sh> i uruchom ponownie. |
| Spisu aplikacji brakuje lub jest błędny | `mac-update scan`. Czyta tylko Twojego Maca. Nigdy nie kopiuj cudzego spisu. |
| Aplikacja nigdy się nie aktualizuje | Diagnostyka, „Jak aktualizowane są aplikacje”, pokazuje, jak program traktuje każdą aplikację. Jeśli nie ma metody, otwórz aplikację i użyj jej opcji „Sprawdź uaktualnienia”. |
| Brak dostępu do informacji o aktualizacjach od producenta | Spróbuj później. Kanały sprawdzisz w Diagnostyce: „Sprawdź kanały aktualizacji”. |
| Mac zasnął w trakcie pracy | Zostaw włączone „Nie usypiaj Maca” (domyślnie). |
| Aktualizacja została przerwana | Diagnostyka, „Dokończ przerwane aktualizacje”. |
| Program pisze, że działa inne uruchomienie | Poczekaj, aż się skończy. Pozostałość po zawieszonym uruchomieniu jest sprzątana na początku następnego. |
| Mało miejsca lub baterii | Zwolnij miejsce albo podłącz zasilacz. Limity ustawisz w Ustawieniach, „Zabezpieczenia”. |

Nadal nie wiadomo, o co chodzi? Otwórz najnowszy plik w `logs/` i poszukaj pierwszego wiersza z błędem lub ostrzeżeniem.

## Usuwanie programu

```bash
mac-update uninstall
```

Wyłącza też uruchamianie automatyczne. Co zostaje, a co jest usuwane: [UNINSTALL.md](../../UNINSTALL.md).
