# Receptury i natywne updatery: ustalenia z 2026-11-14

Zakres: analiza istniejącego logu, kodu i dokumentacji. Nie uruchamiano aplikacji, updaterów, instalatorów ani aktualizacji systemu. Polecenia opisane poniżej są materiałem do walidacji, nie instrukcją wykonania na komputerze właściciela.

## Ostatni przebieg

Przebieg trwał **778 s, czyli 12 min 58 s**. Etap aplikacji internetowych zajął **625 s, czyli 80,3% całości**. App Store: 84 s; CLI/npm: 33 s; Homebrew: 26 s; prescan: 2 s; postupdate: 2 s; system: 3 s. Pozostałe 3 s to narzut poza etapami.

Log znajduje się w starszym checkoutcie, którego obecny czysty kod ma VERSION 1.6.0. Sam log nie zawiera SHA ani wersji narzędzia, więc dokładna tożsamość wykonanych źródeł jest wnioskiem z lokalizacji i zachowania, nie zapisanym dowodem. Nie jest to potwierdzenie działania nowego wykonawcy 1.7.0.

Raport wykazuje jedną aktualizację App Store, cztery zmiany wersji narzędzi CLI, cztery formulae i siedem aplikacji internetowych. Nie pozostały oczekujące aktualizacje w sprawdzonych zestawach App Store, brew, MAU ani systemu. Przebieg zakończył się z ostrzeżeniami, bez błędu blokującego. To uzasadnia ocenę „większość działań się udała”, nie „wszystko zostało zaktualizowane”.

DeepSeek Harness pozostał na `0.2.2-rc.2`; feed oferował `0.2.2-rc.3`. Statyczny odczyt zainstalowanego pakietu potwierdził kanał `nightly`, dostawcę `generic` i obecność Electron/Squirrel. Ponowny odczyt oficjalnego feedu 2026-11-14 nadal wskazywał `rc.3`. Nie ustalono sygnału gotowości instalacji ani udokumentowanego zewnętrznego polecenia aktualizacji tej aplikacji. Zgoda na stable nie jest zgodą na nightly/RC.

Pięć cykli uruchamiania updatera działało kolejno. Stary handler domyślnie czeka do 90 s przed prośbą o zamknięcie i do 10 s po niej; osobny mechanizm zamykania ma dalszy budżet. Liczniki obejmują głównie `sleep`, a wywołania wykrywające proces lub zamykające aplikację też mogą czekać. Dlatego nie są to ścisłe limity czasu rzeczywistego. Te ustawienia dobrze wyjaśniają skalę opóźnienia, ale bez znaczników per aplikacja nie można przypisać dokładnych sekund poszczególnym programom.

Odczyty feedów w logu trwały poniżej 0,9 s każdy. Nie zmierzono osobno pobrań artefaktów. Nie należy twierdzić ani że całość była pobieraniem, ani że dokładnie pięć razy wykonano pełne 90 s. Wynik „30 zweryfikowanych” łączy świeże porównania, zmiany wersji i wcześniejsze zapisy historii updatera. To różne klasy dowodu.

Zidentyfikowano też błąd prezentacji: `duration_formatted` pokazuje `12m 3s`, chociaż `duration_seconds=778`. W `lib/python/run_summary.py` zmienna reszty sekund jest nadpisywana podczas iterowania po czasach etapów. Naprawa jest zadaniem planu, nie została wykonana w tej analizie.

## Co rzeczywiście dokumentują producenci

Weryfikacja źródeł: 2026-11-14. Dokumentacja na gałęziach main/develop jest zmienna; przy zatwierdzaniu receptury trzeba utrwalić rewizję i hash. Dowód istnienia API nie zastępuje testu konkretnej aplikacji.

| Mechanizm | Udokumentowany zakres | Wniosek dla receptury |
|---|---|---|
| Sparkle 2 | Oficjalne `sparkle-cli` obsługuje obce bundle. `--probe` sprawdza, `--check-immediately` rozpoczyna aktualizację; domyślnie może zakończyć działającą aplikację i uruchomić ją ponownie. `--defer-install` może pozostawić pomocniczy proces po wyjściu CLI. | Dobry kandydat po sprawdzeniu wersji frameworka, feedu, klucza i reguł konkretnego produktu. Własne delegaty aplikacji mogą zmieniać porównywanie wersji lub adres feedu. Nie uruchamiać na otwartej aplikacji użytkownika i nie zmieniać jej preferencji automatycznie. [S1, S2] |
| Microsoft Office / MAU | `msupdate --install --apps` wybiera identyfikatory aplikacji; `--format plist` daje dane; `--wait` zwraca bieżący stan po limicie, a nie gwarancję sukcesu. | Pilotaż Word/Excel, następnie pozostałe Office. Najpierw obsłużyć wymagany update MAU. Nie używać `--terminate` do zamknięcia wcześniej otwartej aplikacji. Teams wymaga osobnej receptury: dokumentacja wyłącza administracyjne zarządzanie nim przez msupdate. [S3] |
| GoogleUpdater | Dokumentacja macOS opisuje `--update-apps` dla wszystkich zarejestrowanych aplikacji w danym zakresie. `--wake`, `--wake-all` i `--update` mają inne znaczenia. | Nie wolno podstawić polecenia „wszystkie aplikacje” pod zgodę dotyczącą jednego Chrome. Potrzebny dowód zakresu i wynik osobno dla każdego celu. Comet nie dziedziczy receptury Google. [S4, S5] |
| Docker Desktop | Oficjalne `docker desktop update --check-only` sprawdza; `--quiet` sprawdza i stosuje aktualizację. Istnieją osobne polecenia status/start/stop/restart. | Sprawdzić minimalną wersję pluginu i Desktop, aktywne workloady oraz zgodę na przerwę. Wersja silnika lub pluginu CLI nie jest wersją GUI. Sygnał staged-ready i semantyka wyjścia wymagają akceptacji. [S6, S7] |
| Electron | `checkForUpdates`, `update-downloaded`, `quitAndInstall` to API procesu aplikacji. | Model stanów jest przydatny, ale nie daje dowolnej aplikacji zewnętrznej flagi CLI. Nie wstrzykiwać JS, nie włączać debuggera i nie wykonywać kodu znalezionego w pakiecie. [S8] |
| Cursor, Antigravity IDE | Dokumentowane są komendy w GUI/palecie i restart po pobraniu. Antigravity App, IDE i CLI to odrębne powierzchnie. | Brak potwierdzonego zewnętrznego kontraktu CLI w sprawdzonych źródłach. Wybrać zweryfikowany artefakt albo osobno testowany przepływ GUI; nie zgadywać flag. [S9, S10] |
| Warp, Claude Desktop | Dokumentowane są sprawdzanie przy uruchomieniu i/lub pozycja w menu, następnie powiadomienie o aktualizacji. | Bez dowodu gotowości nie zamykać aplikacji „bo minęło 90 s”. CLI Claude Code nie aktualizuje Desktop; terminala z sesją użytkownika nie zamykać. [S11, S12] |
| ChatGPT / Codex | Aktualna dokumentacja przekierowuje dawny adres aplikacji Codex do przewodnika ChatGPT desktop; starsze noty nazywają poprzednią aplikację ChatGPT Classic. | Trzeba zmapować bieżące bundle, produkty, edycje, kanały i zmianę nazwy. Nie zakładać ani stałej równoważności, ani wiecznej odrębności nazw katalogowych. [S13, S14] |
| VS Code | Referencja CLI opisuje pliki, rozszerzenia i diagnostykę. `--wait` dotyczy zamknięcia edytowanych plików. | To nie sygnał gotowości updatera. Nie dziedziczyć nieudokumentowanych flag w Cursor/Antigravity. [S15] |
| KeePassXC | Kod dialogu sprawdzania aktualizacji kieruje do pobrania ze strony. | „Sprawdź aktualizację” nie dowodzi samodzielnej instalacji. Rozważyć zweryfikowany artefakt i istniejący kontrakt podmiany. [S16] |

## Źródła

- S1: https://sparkle-project.org/documentation/sparkle-cli/
- S2: https://sparkle-project.org/documentation/security-and-reliability/ . Uwzględnić opisane poprawki, w tym 2.9.6 dla narzędzi/daemonów; receptura nie może zakładać bezpieczeństwa dowolnej starej wersji.
- S3: https://learn.microsoft.com/en-us/microsoft-365-apps/mac/update-office-for-mac-using-msupdate . Dokument z 2026-09-18.
- S4: https://chromium.googlesource.com/chromium/src/+/main/docs/updater/user_manual.md?format=TEXT
- S5: https://chromium.googlesource.com/chromium/src/+/main/docs/updater/functional_spec.md?format=TEXT
- S6: https://docs.docker.com/reference/cli/docker/desktop/update/
- S7: https://docs.docker.com/desktop/features/desktop-cli/
- S8: https://raw.githubusercontent.com/electron/electron/main/docs/api/auto-updater.md
- S9: https://prod.cursor.com/help/troubleshooting/install-issues
- S10: https://antigravity.google/docs/getting-started
- S11: https://docs.warp.dev/support-and-community/troubleshooting-and-support/updating-warp . Dokument z 2026-11-11.
- S12: https://code.claude.com/docs/en/desktop.md
- S13: https://help.openai.com/en/articles/9703738-chatgpt-macos-app-release-notes
- S14: https://developers.openai.com/codex/app oraz cel przekierowania https://learn.chatgpt.com/docs/app
- S15: https://code.visualstudio.com/docs/configure/command-line
- S16: https://raw.githubusercontent.com/keepassxreboot/keepassxc/develop/src/gui/UpdateCheckDialog.cpp
- S17: https://download.deepseek.com/dsh-desk/feeds/mac-arm64/nightly-mac.yml . W odczycie 2026-11-14: `0.2.2-rc.3`, data wydania `2026-11-13T07:40:14.455Z`.

## Procedury badania

Zastosowano orkiestra, systematic-debugging i writing-plans, wyszukiwanie lokalne skill-finder, Context7 oraz bezpośrednią weryfikację dokumentacji producentów. Przeszukanie półki nie wskazało lepszego zaufanego skilla; znaleziony archiwalny os-scripting pochodził z wycofanego agregatora. Nie przywracano go. Skill deep-research po przeczytaniu okazał się wrapperem zewnętrznego płatnego agenta, więc nie został uruchomiony. Nie instalowano skilli ani narzędzi.
