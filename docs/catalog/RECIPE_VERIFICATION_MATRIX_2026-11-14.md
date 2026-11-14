# Kolejka weryfikacji receptur, 2026-11-14

Macierz obejmuje wszystkie 48 identyfikatorów z `config/channel_sources.json`, odpowiadające 47 wierszom historycznego rejestru. Nazwy i podział ChatGPT/Codex są stanem katalogu, nie rozstrzygnięciem aktualnego rebrandingu. To kolejka badań do [planu](../superpowers/plans/2026-11-14-recipe-verification-and-native-updaters.md), a nie lista zaakceptowanych automatycznych receptur. Dokumentacja mechanizmów jest w [raporcie źródeł](RECIPE_VERIFICATION_RESEARCH_2026-11-14.md); wcześniejsze źródła per produkt pozostają w [SOURCE_RESEARCH.md](SOURCE_RESEARCH.md).

**Wspólna bramka:** oficjalne źródło, produkt/edycja/kanał, bundle i Team ID, zgodność OS/arch, zakres skutków, warunki/licencja, podpisany artefakt i brak downgrade'u. Potem fixture, osobno live update, osobno live first install oraz ewentualnie lifecycle. Każda pozycja poniżej ma status **pending acceptance**. Żadna nie uzyskuje automatycznego wykonania z samej nazwy mechanizmu.

„Artefakt” oznacza kandydata do sprawdzenia, nie potwierdzenie bezpiecznego single-bundle install. „Manager” oznacza istniejący, potwierdzony receipt i sprawdzenie pełnego scope przy każdym wykonaniu. App Store nie przechodzi automatycznie na brew ani odwrotnie. Zainstalowana aplikacja nigdy nie jest usuwana w celu poprawienia source conflict.

| ID produktu | Kandydat update | Kandydat pierwszej instalacji | Szczególny dowód lub blokada | Fala |
|---|---|---|---|---|
| `google-chrome-gui` | GoogleUpdater lub obecny manager | Oficjalny artefakt | Zakres wszystkich zarejestrowanych aplikacji; offered rollout; usługi updatera | 3 |
| `firefox-developer-edition-gui` | Osobny kanał Developer Edition | Oficjalny artefakt preview | To nie stable Firefox; osobna zgoda i tożsamość kanału | 4 |
| `brave-browser-gui` | Updater producenta lub manager | Oficjalny artefakt | Własny kontrakt updatera; nie dziedziczyć flag Google | 2 |
| `chatgpt-gui` | Po ponownym identity review | Po ponownym identity review | Classic/nowy desktop, bundle, Team ID i relacja do Codex | 4 |
| `codex-gui` | Po ponownym identity review | Po ponownym identity review | Zmienione adresy dokumentacji; odróżnić GUI od CLI i ChatGPT | 4 |
| `claude-gui` | Natywny updater lub artefakt | Oficjalny artefakt | Claude Desktop to nie Claude Code; brak zewnętrznego ready API w badanych źródłach | 4 |
| `comet-gui` | Updater producenta lub artefakt | Oficjalny artefakt | Osobny kontrakt; Chromium nie dowodzi zgodności z GoogleUpdater | 4 |
| `gemini-gui` | Po identity review | Po identity review | Potwierdzić oficjalny produkt macOS, edycję i podpis; nie pomylić z PWA | 4 |
| `perplexity-gui` | Zachować wykryte źródło | App Store lub oficjalny artefakt po review | Oddzielić desktop od Comet, receipt od vendor feed | 4 |
| `antigravity-gui` | Po identity review | Po identity review | App, IDE i CLI mają odrębne tożsamości i wymagania | 4 |
| `antigravity-ide-gui` | Artefakt lub udokumentowany przepływ GUI | Oficjalny artefakt | Brak potwierdzonego zewnętrznego CLI aktualizacji | 4 |
| `lm-studio-gui` | Artefakt lub natywny updater | Oficjalny artefakt | Oddzielić wersję GUI, runtime i modeli; nie kończyć aktywnej inferencji | 3 |
| `opencode-gui` | Oficjalny artefakt | Oficjalny artefakt | GUI kontra CLI, tożsamość Electron feedu, względne URL i arm64 | 2 |
| `cursor-gui` | Artefakt lub udokumentowany przepływ GUI | Oficjalny artefakt | CLI edytora nie jest API aktualizacji; ochrona otwartych projektów | 4 |
| `open-design-gui` | Oficjalny artefakt | Oficjalny artefakt | Nie uruchamiać dla testu wersji; ustalić payload i kanał | 2 |
| `hyperframes-gui` | Oficjalny artefakt | Oficjalny artefakt | Historia direct update nie certyfikuje nowej instalacji | 2 |
| `superset-gui` | Oficjalny artefakt | Oficjalny artefakt | Tożsamość produktu, dodatkowe narzędzia i skutki pierwszego startu | 2 |
| `deepseek-harness-gui` | Osobna receptura nightly | Po odrębnej zgodzie na nightly | Feed nightly oferuje RC; brak udokumentowanego zewnętrznego trigger/ready | 4 |
| `grok-bot-gui` | Po identity/channel review | Po identity/channel review | Udowodnić pochodzenie aplikacji i feedu; marka nie jest dowodem podpisu | 4 |
| `obsidian-gui` | Updater lub artefakt | Oficjalny artefakt | Wersja aplikacji kontra instalator/Electron; ochrona otwartych vaultów | 2 |
| `protonvpn-gui` | Updater producenta lub manager | Instalator po pełnym scope review | VPN, rozszerzenia i privileged helpers; aktywne połączenie | 3 |
| `keepassxc-gui` | Oficjalny artefakt | Oficjalny artefakt | Dialog download nie jest self-installerem; ochrona otwartej bazy | 1 |
| `proton-mail-gui` | Updater lub artefakt | Oficjalny artefakt | Kanał, oferta dla konta i oddzielenie od Bridge | 2 |
| `zoom-us-gui` | Updater lub manager | Instalator po scope review | Wariant administratora, helpery, aktywne spotkanie | 3 |
| `google-drive-gui` | Updater producenta | Instalator po pełnym scope review | Aktywna synchronizacja, rozszerzenia i współdzielony updater | 3 |
| `megasync-gui` | Updater producenta lub manager | Instalator po scope review | Synchronizacja, rozszerzenia i odzyskanie po przerwaniu | 3 |
| `proton-drive-gui` | Updater producenta | Instalator po scope review | Stopniowy rollout, offered versus listed, synchronizacja | 3 |
| `microsoft-excel-gui` | MAU dla vendor; App Store dla receipt | Vendor installer lub App Store | Osobne źródła; aktualizacja MAU, zakres instalatora i licencja | 2 |
| `microsoft-word-gui` | Pilotaż MAU dla vendor; App Store dla receipt | Vendor installer lub App Store | Pierwszy kontrakt MAU w fali 1; install acceptance osobno | 1 |
| `microsoft-outlook-gui` | MAU dla vendor; App Store dla receipt | Vendor installer lub App Store | Aktywna sesja, źródło i dokładny MAU app ID | 2 |
| `microsoft-powerpoint-gui` | MAU dla vendor; App Store dla receipt | Vendor installer lub App Store | Otwarta prezentacja, brak wymuszonego terminate | 2 |
| `microsoft-onenote-gui` | MAU dla vendor; App Store dla receipt | Vendor installer lub App Store | Synchronizacja, uprawnienia i wariant dystrybucji | 2 |
| `microsoft-teams-gui` | Osobny updater Teams | Instalator po scope review | Nie przenosić kontraktu MAU Office; spotkania i helpery | 3 |
| `visual-studio-code-gui` | Oficjalny artefakt lub manager | Oficjalny artefakt | CLI --wait dotyczy plików; kanał Stable kontra Insiders | 2 |
| `warp-gui` | Natywny updater lub artefakt | Oficjalny artefakt | Nie zamykać sesji terminala; menu/powiadomienie nie daje zewnętrznego ready API | 4 |
| `codeedit-gui` | Oficjalny artefakt; ocenić Sparkle | Oficjalny artefakt | Potwierdzić framework, feed/klucz i brak dodatkowych efektów | 1 |
| `docker-desktop-gui` | Docker Desktop CLI update | Instalator po pełnym scope review | Wersja pluginu, workloady, uprawnienia i oddzielna wersja GUI | 3 |
| `appcleaner-gui` | Oficjalny artefakt; ocenić Sparkle | Oficjalny artefakt | Podpis, minOS i rzeczywisty zakres single-bundle | 1 |
| `spotify-gui` | Updater producenta lub manager | Oficjalny artefakt | Bootstrap/download wrapper kontra finalny bundle, aktywna sesja | 2 |
| `capcut-gui` | App Store lub vendor zgodnie z receipt | Wybrane źródło po review | Konflikt App Store/Homebrew nie oznacza zgody na migrację | 2 |
| `ledger-live-gui` | Updater producenta lub artefakt | Oficjalny artefakt | Bez urządzenia/seed/środków w testach; nie aktualizować firmware | 3 |
| `trezor-suite-gui` | Updater producenta lub artefakt | Oficjalny artefakt | Bez urządzenia/seed/środków; oddzielić aplikację i firmware | 3 |
| `remote-desktop-manager-gui` | Updater producenta lub artefakt | Oficjalny artefakt | Edycja/licencja, aktywne połączenia i dane poświadczeń | 3 |
| `ipmiview-gui` | App Store zgodnie z receipt | Ręczne pozyskanie App Store | Potwierdzić macOS/iPad wariant i ID; bez danych serwerów w testach | 4 |
| `inkscape-gui` | Oficjalny artefakt lub manager | Oficjalny artefakt | arm64, minOS i pełny zakres artefaktów | 2 |
| `unifi-gui` | App Store zgodnie z receipt | Ręczne pozyskanie App Store | Aplikacja iPad kontra kontroler serwera; offered/account/region | 4 |
| `wifiman-gui` | App Store zgodnie z receipt | Ręczne pozyskanie App Store | Potwierdzić wariant produktu i ID; bez zmian sieci produkcyjnej | 4 |
| `picsart-gui` | App Store zgodnie z receipt | Ręczne pozyskanie App Store | Wariant macOS/iPad, oferta regionu i licencja | 4 |

Fale są priorytetem badania, nie obietnicą obsługi wszystkich pozycji. Jeśli analiza wykryje pkg, helper, brak stabilnego feedu lub nieznany zakres, pozycja przechodzi do późniejszej fali albo pozostaje ręczna. Dostępność sprawdzonego managera może umożliwiać jego obecną ograniczoną ścieżkę niezależnie od tej przyszłej receptury, ale nie certyfikuje instalacji ani native lifecycle.

Nowe aplikacje spoza katalogu: zapisać lokalne obserwacje bez przesyłania inventory, przedstawić źródło jako unknown, zaproponować kandydatów z dowodami i pozostawić ręczne wykonanie. Automatyczne wykrycie Sparkle/Electron lub podobnej nazwy nigdy nie tworzy zaufanej receptury. Dodanie produktu wymaga tego samego review i akceptacji co pozycje powyżej.
