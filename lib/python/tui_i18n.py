"""Complete dashboard copy for all seven toolkit languages; no runtime I/O."""

LANGUAGES = ("en", "pl", "de", "es", "fr", "it", "pt")

CATALOGS = {'en': {'app_title': 'macOS Updates',
        'nav_home': 'Dashboard',
        'nav_updates': 'Updates',
        'nav_inventory': 'Inventory',
        'nav_catalog': 'App catalog',
        'nav_diagnostics': 'Diagnostics',
        'nav_history': 'History',
        'nav_settings': 'Settings',
        'nav_wizard': 'First-use guide',
        'nav_help': 'Help',
        'action_preview': 'Preview update plan',
        'desc_preview': 'Show proposed scopes without updating software or granting permission.',
        'action_update': 'Run update workflow',
        'desc_update': 'Check installed software and review eligible actions. Existing confirmations still '
                       'apply.',
        'action_inventory': 'Refresh inventory',
        'desc_inventory': 'Observe installed software and rebuild local inventory reports.',
        'action_setup_inspect': 'Inspect setup',
        'desc_setup_inspect': 'Check requirements without installing dependencies or changing shell '
                              'profiles.',
        'action_setup_dependencies': 'Review optional dependencies',
        'desc_setup_dependencies': 'Preview optional tools and request separate permission for each '
                                   'installation.',
        'action_setup_shell': 'Review shell configuration',
        'desc_setup_shell': 'Preview a shell-profile change and ask before applying it.',
        'action_catalog': 'Open app catalog',
        'desc_catalog': 'Browse optional products. Opening the catalog selects and installs nothing.',
        'action_preferences': 'Review update permissions',
        'desc_preferences': 'Review or reset saved per-target choices. Review alone grants no new '
                            'permission.',
        'action_doctor': 'Check readiness',
        'desc_doctor': 'Read-only diagnostics for tools, permissions and toolkit readiness.',
        'action_coverage': 'Show update coverage',
        'desc_coverage': 'Report observed sources and available methods for installed software.',
        'action_sources': 'Inspect source evidence',
        'desc_sources': 'Review source evidence and stable-version advice without migrating software.',
        'action_migration_preview': 'Preview inventory migration',
        'desc_migration_preview': 'Compare older Markdown inventory with structured observations before '
                                  'separate acceptance.',
        'actions': 'Actions',
        'groups': 'Update groups',
        'details': 'Details',
        'live_log': 'Live output',
        'tasks': 'Operations',
        'idle': 'Idle',
        'running': 'Running',
        'completed': 'Completed',
        'warnings': 'Warnings',
        'failed': 'Failed',
        'waiting': 'Waiting for input',
        'elapsed': 'Elapsed',
        'progress': 'Progress',
        'unknown': 'Unknown',
        'none': 'None',
        'start': 'Start',
        'confirm': 'Confirm',
        'cancel': 'Cancel',
        'back': 'Back',
        'next': 'Next',
        'finish': 'Finish',
        'save': 'Save',
        'saved': 'Saved',
        'input': 'Answer',
        'secret_input': 'Hidden answer',
        'input_hint': 'Use i to open the answer dialog; Enter submits your typed answer there. Passwords are '
                      'masked, never stored or copied.',
        'confirm_body': 'Start the displayed operation? Existing per-app and system confirmations still '
                        'apply.',
        'interrupt_body': 'Request interruption? An updater may still be running and its state may remain '
                          'unresolved. Never delete recovery journals or leases to continue.',
        'busy': 'An operation is running. Review its output or wait for completion.',
        'no_history': 'No operation history yet.',
        'history_hint': 'Review local operation results. A successful exit alone does not prove an update.',
        'help_title': 'Dashboard help',
        'shortcut_hint': 'Up/Down select; Tab change pane; Enter open; F1 help; Ctrl-P actions.',
        'resize': 'Enlarge the terminal to at least 80x24 or use the plain CLI.',
        'palette': 'Action palette',
        'search': 'Search actions',
        'language': 'Language',
        'theme': 'Theme',
        'ascii': 'ASCII display',
        'wizard_complete': 'First-use review complete. Starting updates remains a separate choice.',
        'wizard_intro': 'Review requirements, inventory, sources and settings, then inspect a plan. Changes '
                        'retain their own confirmations.',
        'settings_hint': 'These settings affect the dashboard. Saved update permissions remain separate.',
        'groups_hint': 'Select groups with Space. Selection limits scope and does not authorize an update.',
        'serial_notice': 'Operations run one at a time. Shared managers and unresolved helpers keep their '
                         'safety locks.',
        'readonly_notice': 'Navigation changes no software. Start each operation explicitly; its own '
                           'permission checks still apply.',
        'error': 'Error: {message}',
        'quit_body': 'Leave the dashboard? An active updater may continue; unresolved state requires '
                     'reviewed recovery.',
        'not_available': 'This operation is unavailable in the current environment.',
        'job_finished': 'Operation finished with exit code {code}.',
        'scan_hint': 'Observed inventory is evidence, not a guarantee that an update is available.',
        'copy': 'Copy',
        'paste': 'Paste',
        'copied': 'Copied',
        'clipboard_unavailable': 'Clipboard is unavailable. Use terminal selection instead.',
        'copy_command': 'Copy command',
        'copy_log': 'Copy visible output',
        'copy_summary': 'Copy summary',
        'group_appstore': 'App Store',
        'group_npm': 'Native CLI and npm',
        'group_brew': 'Homebrew',
        'group_internet': 'Vendor applications',
        'group_system': 'macOS system',
        'wizardstep_welcome': 'Welcome',
        'wizarddesc_welcome': 'Learn how this dashboard separates observation, selection and consent.',
        'wizardstep_requirements': 'Requirements',
        'wizarddesc_requirements': 'Inspect tools and readiness. Missing dependencies require separate '
                                   'approval.',
        'wizardstep_inventory': 'Inventory',
        'wizarddesc_inventory': 'Observe installed software and refresh local inventory when you choose.',
        'wizardstep_sources': 'Sources',
        'wizarddesc_sources': 'Inspect observed installation sources. Unresolved ownership stays manual.',
        'wizardstep_settings': 'Settings',
        'wizarddesc_settings': 'Choose the dashboard language, theme and ASCII display.',
        'wizardstep_preview': 'Preview',
        'wizarddesc_preview': 'Review proposed scopes without updating apps or granting new permission.',
        'wizardstep_finish': 'Review complete',
        'wizarddesc_finish': 'Review the summary. Starting updates is a separate operation.',
        'help_body': 'First use: open the first-use guide to inspect requirements, inventory and sources, '
                     'then preview a plan.\n'
                     'Choose update groups with Space. Selection grants no consent; existing per-app and '
                     'system confirmations still apply.\n'
                     'The live log follows the running operation. Use i to answer only in the explicit input '
                     'dialog. Passwords are masked and never stored or copied.\n'
                     'Use c to copy the focused command, output or summary. Ctrl-V pastes only in the answer '
                     'dialog; Enter is still required to submit. Never copy secret input.\n'
                     'Resize to at least 80x24. Settings control language, theme and ASCII display. All '
                     'seven toolkit languages are available.\n'
                     'Interruption can leave an updater active or its state unknown. Review recovery '
                     'evidence; never delete journals or leases to bypass a safety block.\n'
                     'Up/Down selects; Tab changes pane; Space selects groups; Enter opens. r starts the '
                     'selected operation; d previews; i opens the answer dialog.\n'
                     'F1 or ? opens help; Ctrl-P opens the action palette; Esc goes back; q requests exit; '
                     'PgUp/PgDn scrolls the log.\n'
                     'Automatic resizing is optional; the terminal may ignore requests. The previous window '
                     'size is requested on exit. Below 80x24, operations that change state are blocked.',
        'auto_resize': 'Automatic window size',
        'window_hint': 'Automatic resizing is optional; the terminal may ignore requests. The previous '
                       'window size is requested on exit. Below 80x24, operations that change state are '
                       'blocked.'},
 'pl': {'app_title': 'macOS Updates',
        'nav_home': 'Panel główny',
        'nav_updates': 'Aktualizacje',
        'nav_inventory': 'Inwentarz',
        'nav_catalog': 'Katalog aplikacji',
        'nav_diagnostics': 'Diagnostyka',
        'nav_history': 'Historia',
        'nav_settings': 'Ustawienia',
        'nav_wizard': 'Pierwsze uruchomienie',
        'nav_help': 'Pomoc',
        'action_preview': 'Podejrzyj plan aktualizacji',
        'desc_preview': 'Pokaż proponowane zakresy bez aktualizowania oprogramowania i nadawania zgody.',
        'action_update': 'Uruchom przebieg aktualizacji',
        'desc_update': 'Sprawdź zainstalowane oprogramowanie i przejrzyj dopuszczone działania. '
                       'Dotychczasowe potwierdzenia nadal obowiązują.',
        'action_inventory': 'Odśwież inwentarz',
        'desc_inventory': 'Sprawdź zainstalowane oprogramowanie i odbuduj lokalne raporty inwentarza.',
        'action_setup_inspect': 'Sprawdź konfigurację',
        'desc_setup_inspect': 'Sprawdź wymagania bez instalowania zależności i zmiany profili powłoki.',
        'action_setup_dependencies': 'Przejrzyj opcjonalne zależności',
        'desc_setup_dependencies': 'Pokaż opcjonalne narzędzia i poproś o osobną zgodę na każdą instalację.',
        'action_setup_shell': 'Przejrzyj konfigurację powłoki',
        'desc_setup_shell': 'Pokaż zmianę profilu powłoki i zapytaj przed jej zastosowaniem.',
        'action_catalog': 'Otwórz katalog aplikacji',
        'desc_catalog': 'Przeglądaj opcjonalne produkty. Otwarcie katalogu niczego nie wybiera ani nie '
                        'instaluje.',
        'action_preferences': 'Przejrzyj zgody na aktualizacje',
        'desc_preferences': 'Przejrzyj lub wyzeruj zapisane decyzje dla poszczególnych celów. Sam przegląd '
                            'nie nadaje nowej zgody.',
        'action_doctor': 'Sprawdź gotowość',
        'desc_doctor': 'Diagnostyka narzędzi, uprawnień i gotowości toolkita bez wprowadzania zmian.',
        'action_coverage': 'Pokaż pokrycie aktualizacji',
        'desc_coverage': 'Pokaż zaobserwowane źródła i dostępne metody dla zainstalowanego oprogramowania.',
        'action_sources': 'Sprawdź dowody źródeł',
        'desc_sources': 'Przejrzyj dowody źródeł i porady o wersjach stabilnych bez migracji oprogramowania.',
        'action_migration_preview': 'Podejrzyj migrację inwentarza',
        'desc_migration_preview': 'Porównaj starszy inwentarz Markdown z obserwacjami strukturalnymi przed '
                                  'osobną akceptacją.',
        'actions': 'Działania',
        'groups': 'Grupy aktualizacji',
        'details': 'Szczegóły',
        'live_log': 'Bieżące wyjście',
        'tasks': 'Operacje',
        'idle': 'Bezczynny',
        'running': 'W trakcie',
        'completed': 'Zakończono',
        'warnings': 'Ostrzeżenia',
        'failed': 'Niepowodzenie',
        'waiting': 'Oczekiwanie na odpowiedź',
        'elapsed': 'Upłynęło',
        'progress': 'Postęp',
        'unknown': 'Nieznane',
        'none': 'Brak',
        'start': 'Uruchom',
        'confirm': 'Potwierdź',
        'cancel': 'Anuluj',
        'back': 'Wstecz',
        'next': 'Dalej',
        'finish': 'Zakończ',
        'save': 'Zapisz',
        'saved': 'Zapisano',
        'input': 'Odpowiedź',
        'secret_input': 'Ukryta odpowiedź',
        'input_hint': 'Odpowiedź wpisujesz w oknie otwieranym klawiszem i; Enter wysyła ją dopiero z tego '
                      'okna. Hasła są maskowane, nigdy zapisywane ani kopiowane.',
        'confirm_body': 'Uruchomić pokazaną operację? Dotychczasowe potwierdzenia aplikacji i systemu nadal '
                        'obowiązują.',
        'interrupt_body': 'Poprosić o przerwanie? Updater może nadal działać, a jego stan pozostać '
                          'nierozstrzygnięty. Nigdy nie usuwaj dzienników odzyskiwania ani blokad, aby '
                          'kontynuować.',
        'busy': 'Trwa operacja. Przejrzyj jej wyjście lub zaczekaj na zakończenie.',
        'no_history': 'Brak historii operacji.',
        'history_hint': 'Przejrzyj lokalne wyniki operacji. Sam poprawny kod wyjścia nie potwierdza '
                        'aktualizacji.',
        'help_title': 'Pomoc panelu',
        'shortcut_hint': 'Up/Down wybór; Tab zmiana panelu; Enter otwarcie; F1 pomoc; Ctrl-P działania.',
        'resize': 'Powiększ terminal do co najmniej 80x24 lub użyj zwykłego CLI.',
        'palette': 'Paleta działań',
        'search': 'Szukaj działań',
        'language': 'Język',
        'theme': 'Motyw',
        'ascii': 'Widok ASCII',
        'wizard_complete': 'Przegląd pierwszego uruchomienia zakończony. Rozpoczęcie aktualizacji wymaga '
                           'osobnej decyzji.',
        'wizard_intro': 'Przejrzyj wymagania, inwentarz, źródła i ustawienia, a następnie plan. Zmiany '
                        'zachowują własne potwierdzenia.',
        'settings_hint': 'Te ustawienia dotyczą panelu. Zapisane zgody na aktualizacje pozostają osobne.',
        'groups_hint': 'Wybierz grupy klawiszem Space. Wybór ogranicza zakres i nie udziela zgody na '
                       'aktualizację.',
        'serial_notice': 'Operacje są wykonywane pojedynczo. Wspólne menedżery i nierozstrzygnięte procesy '
                         'pomocnicze zachowują blokady bezpieczeństwa.',
        'readonly_notice': 'Nawigacja nie zmienia oprogramowania. Każdą operację uruchom jawnie; jej własne '
                           'kontrole zgody nadal obowiązują.',
        'error': 'Błąd: {message}',
        'quit_body': 'Opuścić panel? Aktywny updater może kontynuować pracę; nierozstrzygnięty stan wymaga '
                     'sprawdzonego odzyskania.',
        'not_available': 'Ta operacja jest niedostępna w bieżącym środowisku.',
        'job_finished': 'Operacja zakończona kodem {code}.',
        'scan_hint': 'Zaobserwowany inwentarz jest dowodem, a nie gwarancją dostępności aktualizacji.',
        'copy': 'Kopiuj',
        'paste': 'Wklej',
        'copied': 'Skopiowano',
        'clipboard_unavailable': 'Schowek jest niedostępny. Użyj zaznaczenia w terminalu.',
        'copy_command': 'Kopiuj polecenie',
        'copy_log': 'Kopiuj widoczne wyjście',
        'copy_summary': 'Kopiuj podsumowanie',
        'group_appstore': 'App Store',
        'group_npm': 'Natywne CLI i npm',
        'group_brew': 'Homebrew',
        'group_internet': 'Aplikacje producentów',
        'group_system': 'System macOS',
        'wizardstep_welcome': 'Powitanie',
        'wizarddesc_welcome': 'Poznaj rozdział obserwacji, wyboru i zgody w tym panelu.',
        'wizardstep_requirements': 'Wymagania',
        'wizarddesc_requirements': 'Sprawdź narzędzia i gotowość. Brakujące zależności wymagają osobnej '
                                   'zgody.',
        'wizardstep_inventory': 'Inwentarz',
        'wizarddesc_inventory': 'Sprawdź zainstalowane oprogramowanie i odśwież lokalny inwentarz, gdy '
                                'zdecydujesz.',
        'wizardstep_sources': 'Źródła',
        'wizarddesc_sources': 'Przejrzyj zaobserwowane źródła instalacji. Nierozstrzygnięte przypisanie '
                              'pozostaje ręczne.',
        'wizardstep_settings': 'Ustawienia',
        'wizarddesc_settings': 'Wybierz język panelu, motyw i widok ASCII.',
        'wizardstep_preview': 'Podgląd',
        'wizarddesc_preview': 'Przejrzyj proponowane zakresy bez aktualizowania aplikacji i udzielania nowej '
                              'zgody.',
        'wizardstep_finish': 'Przegląd zakończony',
        'wizarddesc_finish': 'Przejrzyj podsumowanie. Rozpoczęcie aktualizacji jest osobną operacją.',
        'help_body': 'Pierwsze użycie: otwórz przewodnik pierwszego uruchomienia, sprawdź wymagania, '
                     'inwentarz i źródła, a następnie plan.\n'
                     'Wybierz grupy aktualizacji klawiszem Space. Wybór nie nadaje zgody; dotychczasowe '
                     'potwierdzenia aplikacji i systemu nadal obowiązują.\n'
                     'Bieżący log pokazuje przebieg operacji. Klawisz i otwiera jawne okno odpowiedzi. Hasła '
                     'są maskowane i nigdy zapisywane ani kopiowane.\n'
                     'Klawisz c kopiuje aktywne polecenie, wyjście lub podsumowanie. Ctrl-V wkleja tylko w '
                     'oknie odpowiedzi; wysłanie nadal wymaga Enter. Nigdy nie kopiuj tajnej odpowiedzi.\n'
                     'Ustaw rozmiar co najmniej 80x24. Ustawienia obejmują język, motyw i widok ASCII. '
                     'Dostępnych jest siedem języków toolkita.\n'
                     'Przerwanie może pozostawić działający updater lub nieznany stan. Sprawdź dowody '
                     'odzyskiwania; nigdy nie usuwaj dzienników ani blokad, aby ominąć zabezpieczenie.\n'
                     'Up/Down wybiera; Tab zmienia panel; Space wybiera grupy; Enter otwiera. r uruchamia '
                     'wybraną operację; d pokazuje podgląd; i otwiera odpowiedź.\n'
                     'F1 lub ? otwiera pomoc; Ctrl-P paletę działań; Esc wraca; q prosi o wyjście; PgUp/PgDn '
                     'przewija log.\n'
                     'Automatyczna zmiana rozmiaru jest opcjonalna; terminal może zignorować żądanie. Przy '
                     'wyjściu żądany jest poprzedni rozmiar okna. Poniżej 80x24 polecenia wprowadzające '
                     'zmiany są blokowane.',
        'auto_resize': 'Automatyczny rozmiar okna',
        'window_hint': 'Automatyczna zmiana rozmiaru jest opcjonalna; terminal może zignorować żądanie. Przy '
                       'wyjściu żądany jest poprzedni rozmiar okna. Poniżej 80x24 polecenia wprowadzające '
                       'zmiany są blokowane.'},
 'de': {'app_title': 'macOS Updates',
        'nav_home': 'Übersicht',
        'nav_updates': 'Aktualisierungen',
        'nav_inventory': 'Inventar',
        'nav_catalog': 'App-Katalog',
        'nav_diagnostics': 'Diagnose',
        'nav_history': 'Verlauf',
        'nav_settings': 'Einstellungen',
        'nav_wizard': 'Erste Schritte',
        'nav_help': 'Hilfe',
        'action_preview': 'Updateplan anzeigen',
        'desc_preview': 'Vorgeschlagene Bereiche anzeigen, ohne Software zu aktualisieren oder '
                        'Berechtigungen zu erteilen.',
        'action_update': 'Updateablauf starten',
        'desc_update': 'Installierte Software prüfen und zulässige Aktionen ansehen. Bestehende '
                       'Bestätigungen bleiben erforderlich.',
        'action_inventory': 'Inventar aktualisieren',
        'desc_inventory': 'Installierte Software erfassen und lokale Inventarberichte neu erstellen.',
        'action_setup_inspect': 'Einrichtung prüfen',
        'desc_setup_inspect': 'Voraussetzungen prüfen, ohne Abhängigkeiten zu installieren oder Shellprofile '
                              'zu ändern.',
        'action_setup_dependencies': 'Optionale Abhängigkeiten prüfen',
        'desc_setup_dependencies': 'Optionale Werkzeuge anzeigen und jede Installation gesondert bestätigen '
                                   'lassen.',
        'action_setup_shell': 'Shellkonfiguration prüfen',
        'desc_setup_shell': 'Eine Änderung am Shellprofil anzeigen und vor der Anwendung nachfragen.',
        'action_catalog': 'App-Katalog öffnen',
        'desc_catalog': 'Optionale Produkte ansehen. Das Öffnen wählt und installiert nichts.',
        'action_preferences': 'Updateberechtigungen prüfen',
        'desc_preferences': 'Gespeicherte Entscheidungen je Ziel prüfen oder zurücksetzen. Die Ansicht '
                            'erteilt keine neue Berechtigung.',
        'action_doctor': 'Bereitschaft prüfen',
        'desc_doctor': 'Schreibgeschützte Diagnose von Werkzeugen, Berechtigungen und Betriebsbereitschaft.',
        'action_coverage': 'Updateabdeckung anzeigen',
        'desc_coverage': 'Beobachtete Quellen und verfügbare Methoden für installierte Software anzeigen.',
        'action_sources': 'Quellennachweise prüfen',
        'desc_sources': 'Quellennachweise und Hinweise zu stabilen Versionen ohne Softwaremigration prüfen.',
        'action_migration_preview': 'Inventarmigration ansehen',
        'desc_migration_preview': 'Älteres Markdown-Inventar vor einer gesonderten Annahme mit '
                                  'strukturierten Beobachtungen vergleichen.',
        'actions': 'Aktionen',
        'groups': 'Updategruppen',
        'details': 'Einzelheiten',
        'live_log': 'Laufende Ausgabe',
        'tasks': 'Vorgänge',
        'idle': 'Bereit',
        'running': 'Läuft',
        'completed': 'Abgeschlossen',
        'warnings': 'Warnungen',
        'failed': 'Fehlgeschlagen',
        'waiting': 'Wartet auf Eingabe',
        'elapsed': 'Vergangen',
        'progress': 'Fortschritt',
        'unknown': 'Unbekannt',
        'none': 'Keine',
        'start': 'Starten',
        'confirm': 'Bestätigen',
        'cancel': 'Abbrechen',
        'back': 'Zurück',
        'next': 'Weiter',
        'finish': 'Abschließen',
        'save': 'Speichern',
        'saved': 'Gespeichert',
        'input': 'Antwort',
        'secret_input': 'Verdeckte Antwort',
        'input_hint': 'Mit i lässt sich der Antwortdialog öffnen; Enter sendet die dort eingegebene Antwort. '
                      'Passwörter werden maskiert, niemals gespeichert oder kopiert.',
        'confirm_body': 'Den angezeigten Vorgang starten? Bestehende Bestätigungen für Apps und System '
                        'gelten weiterhin.',
        'interrupt_body': 'Unterbrechung anfordern? Ein Updater kann weiterlaufen und sein Zustand ungeklärt '
                          'bleiben. Zum Fortsetzen niemals Wiederherstellungsjournale oder Sperren löschen.',
        'busy': 'Ein Vorgang läuft. Ausgabe prüfen oder auf den Abschluss warten.',
        'no_history': 'Noch kein Vorgangsverlauf.',
        'history_hint': 'Lokale Ergebnisse prüfen. Ein erfolgreicher Rückgabecode allein belegt kein Update.',
        'help_title': 'Hilfe zur Übersicht',
        'shortcut_hint': 'Up/Down auswählen; Tab Bereich wechseln; Enter öffnen; F1 Hilfe; Ctrl-P Aktionen.',
        'resize': 'Terminal auf mindestens 80x24 vergrößern oder die normale CLI verwenden.',
        'palette': 'Aktionspalette',
        'search': 'Aktionen suchen',
        'language': 'Sprache',
        'theme': 'Darstellung',
        'ascii': 'ASCII-Ansicht',
        'wizard_complete': 'Erste Prüfung abgeschlossen. Updates zu starten bleibt eine gesonderte '
                           'Entscheidung.',
        'wizard_intro': 'Voraussetzungen, Inventar, Quellen und Einstellungen prüfen, danach einen Plan '
                        'ansehen. Änderungen behalten eigene Bestätigungen.',
        'settings_hint': 'Diese Einstellungen betreffen die Übersicht. Gespeicherte Updateberechtigungen '
                         'bleiben getrennt.',
        'groups_hint': 'Gruppen mit Space auswählen. Die Auswahl begrenzt den Umfang und erlaubt noch kein '
                       'Update.',
        'serial_notice': 'Vorgänge laufen einzeln. Gemeinsame Manager und ungeklärte Helfer behalten ihre '
                         'Sicherheitssperren.',
        'readonly_notice': 'Navigation ändert keine Software. Jeden Vorgang ausdrücklich starten; seine '
                           'Berechtigungsprüfungen gelten weiterhin.',
        'error': 'Fehler: {message}',
        'quit_body': 'Übersicht verlassen? Ein aktiver Updater kann weiterlaufen; ungeklärter Zustand '
                     'erfordert geprüfte Wiederherstellung.',
        'not_available': 'Dieser Vorgang ist in der aktuellen Umgebung nicht verfügbar.',
        'job_finished': 'Vorgang mit Rückgabecode {code} beendet.',
        'scan_hint': 'Das erfasste Inventar ist ein Nachweis, keine Garantie für ein verfügbares Update.',
        'copy': 'Kopieren',
        'paste': 'Einfügen',
        'copied': 'Kopiert',
        'clipboard_unavailable': 'Zwischenablage nicht verfügbar. Stattdessen im Terminal markieren.',
        'copy_command': 'Befehl kopieren',
        'copy_log': 'Sichtbare Ausgabe kopieren',
        'copy_summary': 'Zusammenfassung kopieren',
        'group_appstore': 'App Store',
        'group_npm': 'Native CLI und npm',
        'group_brew': 'Homebrew',
        'group_internet': 'Herstelleranwendungen',
        'group_system': 'macOS-System',
        'wizardstep_welcome': 'Willkommen',
        'wizarddesc_welcome': 'Erfahren, wie diese Übersicht Beobachtung, Auswahl und Zustimmung trennt.',
        'wizardstep_requirements': 'Voraussetzungen',
        'wizarddesc_requirements': 'Werkzeuge und Bereitschaft prüfen. Fehlende Abhängigkeiten benötigen '
                                   'eine gesonderte Zustimmung.',
        'wizardstep_inventory': 'Inventar',
        'wizarddesc_inventory': 'Installierte Software erfassen und das lokale Inventar nach eigener Wahl '
                                'aktualisieren.',
        'wizardstep_sources': 'Quellen',
        'wizarddesc_sources': 'Beobachtete Installationsquellen prüfen. Ungeklärte Zuordnung bleibt manuell.',
        'wizardstep_settings': 'Einstellungen',
        'wizarddesc_settings': 'Sprache, Darstellung und ASCII-Ansicht der Übersicht wählen.',
        'wizardstep_preview': 'Vorschau',
        'wizarddesc_preview': 'Vorgeschlagene Bereiche ohne App-Updates oder neue Berechtigungen prüfen.',
        'wizardstep_finish': 'Prüfung abgeschlossen',
        'wizarddesc_finish': 'Zusammenfassung prüfen. Updates zu starten ist ein eigener Vorgang.',
        'help_body': 'Erste Nutzung: Die Einführung öffnen, Voraussetzungen, Inventar und Quellen prüfen und '
                     'dann einen Plan ansehen.\n'
                     'Updategruppen mit Space wählen. Die Auswahl erteilt keine Zustimmung; Bestätigungen '
                     'für Apps und System bleiben erforderlich.\n'
                     'Die laufende Ausgabe zeigt den Vorgang. Mit i nur im ausdrücklichen Eingabedialog '
                     'antworten. Passwörter werden maskiert und niemals gespeichert oder kopiert.\n'
                     'Mit c den fokussierten Befehl, die Ausgabe oder die Zusammenfassung kopieren. Ctrl-V '
                     'fügt nur im Antwortdialog ein; Enter sendet die Antwort. Geheime Eingaben niemals '
                     'kopieren.\n'
                     'Auf mindestens 80x24 vergrößern. Einstellungen steuern Sprache, Darstellung und '
                     'ASCII-Ansicht. Alle sieben Toolkit-Sprachen sind verfügbar.\n'
                     'Eine Unterbrechung kann einen aktiven Updater oder einen ungeklärten Zustand '
                     'hinterlassen. Wiederherstellungsnachweise prüfen; niemals Journale oder Sperren zum '
                     'Umgehen einer Schutzsperre löschen.\n'
                     'Up/Down wählt; Tab wechselt den Bereich; Space wählt Gruppen; Enter öffnet. r startet '
                     'den gewählten Vorgang; d zeigt die Vorschau; i öffnet den Antwortdialog.\n'
                     'F1 oder ? öffnet Hilfe; Ctrl-P die Aktionspalette; Esc geht zurück; q fordert das '
                     'Beenden an; PgUp/PgDn blättert durch die Ausgabe.\n'
                     'Automatische Größenänderung ist optional; das Terminal kann Anfragen ignorieren. Beim '
                     'Beenden wird die vorherige Fenstergröße angefordert. Unter 80x24 sind zustandsändernde '
                     'Vorgänge gesperrt.',
        'auto_resize': 'Automatische Fenstergröße',
        'window_hint': 'Automatische Größenänderung ist optional; das Terminal kann Anfragen ignorieren. '
                       'Beim Beenden wird die vorherige Fenstergröße angefordert. Unter 80x24 sind '
                       'zustandsändernde Vorgänge gesperrt.'},
 'es': {'app_title': 'macOS Updates',
        'nav_home': 'Panel principal',
        'nav_updates': 'Actualizaciones',
        'nav_inventory': 'Inventario',
        'nav_catalog': 'Catálogo de aplicaciones',
        'nav_diagnostics': 'Diagnóstico',
        'nav_history': 'Historial',
        'nav_settings': 'Ajustes',
        'nav_wizard': 'Primeros pasos',
        'nav_help': 'Ayuda',
        'action_preview': 'Ver plan de actualización',
        'desc_preview': 'Muestra los alcances propuestos sin actualizar software ni otorgar permisos.',
        'action_update': 'Iniciar flujo de actualización',
        'desc_update': 'Comprueba el software instalado y revisa las acciones permitidas. Se mantienen las '
                       'confirmaciones existentes.',
        'action_inventory': 'Actualizar inventario',
        'desc_inventory': 'Observa el software instalado y reconstruye los informes locales del inventario.',
        'action_setup_inspect': 'Revisar configuración',
        'desc_setup_inspect': 'Comprueba los requisitos sin instalar dependencias ni cambiar perfiles de '
                              'shell.',
        'action_setup_dependencies': 'Revisar dependencias opcionales',
        'desc_setup_dependencies': 'Muestra herramientas opcionales y solicita permiso separado para cada '
                                   'instalación.',
        'action_setup_shell': 'Revisar configuración del shell',
        'desc_setup_shell': 'Muestra el cambio del perfil de shell y pregunta antes de aplicarlo.',
        'action_catalog': 'Abrir catálogo de aplicaciones',
        'desc_catalog': 'Explora productos opcionales. Abrir el catálogo no selecciona ni instala nada.',
        'action_preferences': 'Revisar permisos de actualización',
        'desc_preferences': 'Revisa o restablece decisiones guardadas por destino. La revisión no otorga '
                            'permisos nuevos.',
        'action_doctor': 'Comprobar preparación',
        'desc_doctor': 'Diagnóstico de solo lectura de herramientas, permisos y preparación del toolkit.',
        'action_coverage': 'Ver cobertura de actualizaciones',
        'desc_coverage': 'Muestra fuentes observadas y métodos disponibles para el software instalado.',
        'action_sources': 'Revisar pruebas de las fuentes',
        'desc_sources': 'Revisa fuentes y recomendaciones de versiones estables sin migrar software.',
        'action_migration_preview': 'Ver migración del inventario',
        'desc_migration_preview': 'Compara el inventario Markdown anterior con observaciones estructuradas '
                                  'antes de una aceptación separada.',
        'actions': 'Acciones',
        'groups': 'Grupos de actualización',
        'details': 'Detalles',
        'live_log': 'Salida en directo',
        'tasks': 'Operaciones',
        'idle': 'En espera',
        'running': 'En curso',
        'completed': 'Completado',
        'warnings': 'Advertencias',
        'failed': 'Error',
        'waiting': 'Esperando respuesta',
        'elapsed': 'Tiempo transcurrido',
        'progress': 'Progreso',
        'unknown': 'Desconocido',
        'none': 'Ninguno',
        'start': 'Iniciar',
        'confirm': 'Confirmar',
        'cancel': 'Cancelar',
        'back': 'Volver',
        'next': 'Siguiente',
        'finish': 'Finalizar',
        'save': 'Guardar',
        'saved': 'Guardado',
        'input': 'Respuesta',
        'secret_input': 'Respuesta oculta',
        'input_hint': 'Usa i para abrir el diálogo de respuesta; Enter envía lo escrito allí. Las '
                      'contraseñas se ocultan y nunca se guardan ni se copian.',
        'confirm_body': '¿Iniciar la operación mostrada? Se mantienen las confirmaciones de cada aplicación '
                        'y del sistema.',
        'interrupt_body': '¿Solicitar una interrupción? Un actualizador puede seguir activo y su estado '
                          'quedar sin resolver. Nunca borres diarios de recuperación ni bloqueos para '
                          'continuar.',
        'busy': 'Hay una operación en curso. Revisa su salida o espera a que termine.',
        'no_history': 'Todavía no hay historial de operaciones.',
        'history_hint': 'Revisa resultados locales. Un código de salida correcto no demuestra por sí solo '
                        'una actualización.',
        'help_title': 'Ayuda del panel',
        'shortcut_hint': 'Up/Down selecciona; Tab cambia de panel; Enter abre; F1 ayuda; Ctrl-P acciones.',
        'resize': 'Amplía el terminal a un mínimo de 80x24 o utiliza la CLI habitual.',
        'palette': 'Paleta de acciones',
        'search': 'Buscar acciones',
        'language': 'Idioma',
        'theme': 'Tema',
        'ascii': 'Vista ASCII',
        'wizard_complete': 'Revisión inicial completada. Iniciar actualizaciones sigue siendo una decisión '
                           'separada.',
        'wizard_intro': 'Revisa requisitos, inventario, fuentes y ajustes; después inspecciona un plan. Los '
                        'cambios conservan sus propias confirmaciones.',
        'settings_hint': 'Estos ajustes afectan al panel. Los permisos de actualización guardados siguen '
                         'separados.',
        'groups_hint': 'Selecciona grupos con Space. La selección limita el alcance y no autoriza una '
                       'actualización.',
        'serial_notice': 'Las operaciones se ejecutan de una en una. Los gestores compartidos y auxiliares '
                         'sin resolver conservan sus bloqueos de seguridad.',
        'readonly_notice': 'Navegar no cambia el software. Inicia cada operación explícitamente; sus '
                           'controles de permisos siguen vigentes.',
        'error': 'Error: {message}',
        'quit_body': '¿Salir del panel? Un actualizador activo puede continuar; un estado sin resolver '
                     'requiere recuperación revisada.',
        'not_available': 'Esta operación no está disponible en el entorno actual.',
        'job_finished': 'Operación finalizada con código de salida {code}.',
        'scan_hint': 'El inventario observado es una prueba, no una garantía de que haya una actualización.',
        'copy': 'Copiar',
        'paste': 'Pegar',
        'copied': 'Copiado',
        'clipboard_unavailable': 'El portapapeles no está disponible. Utiliza la selección del terminal.',
        'copy_command': 'Copiar comando',
        'copy_log': 'Copiar salida visible',
        'copy_summary': 'Copiar resumen',
        'group_appstore': 'App Store',
        'group_npm': 'CLI nativas y npm',
        'group_brew': 'Homebrew',
        'group_internet': 'Aplicaciones del proveedor',
        'group_system': 'Sistema macOS',
        'wizardstep_welcome': 'Bienvenida',
        'wizarddesc_welcome': 'Conoce cómo el panel separa observación, selección y consentimiento.',
        'wizardstep_requirements': 'Requisitos',
        'wizarddesc_requirements': 'Comprueba herramientas y preparación. Las dependencias faltantes '
                                   'requieren aprobación separada.',
        'wizardstep_inventory': 'Inventario',
        'wizarddesc_inventory': 'Observa el software instalado y actualiza el inventario local cuando lo '
                                'decidas.',
        'wizardstep_sources': 'Fuentes',
        'wizarddesc_sources': 'Revisa las fuentes de instalación observadas. La propiedad sin resolver '
                              'permanece manual.',
        'wizardstep_settings': 'Ajustes',
        'wizarddesc_settings': 'Elige idioma, tema y vista ASCII del panel.',
        'wizardstep_preview': 'Vista previa',
        'wizarddesc_preview': 'Revisa los alcances propuestos sin actualizar aplicaciones ni otorgar nuevos '
                              'permisos.',
        'wizardstep_finish': 'Revisión completada',
        'wizarddesc_finish': 'Revisa el resumen. Iniciar actualizaciones es una operación separada.',
        'help_body': 'Primer uso: abre la guía inicial para revisar requisitos, inventario y fuentes; '
                     'después consulta un plan.\n'
                     'Selecciona grupos con Space. La selección no otorga consentimiento; se mantienen las '
                     'confirmaciones de aplicaciones y del sistema.\n'
                     'La salida en directo sigue la operación. Usa i para responder solo en el diálogo '
                     'explícito. Las contraseñas se ocultan y nunca se guardan ni se copian.\n'
                     'Usa c para copiar el comando, la salida o el resumen enfocado. Ctrl-V pega solo en el '
                     'diálogo de respuesta; Enter sigue siendo necesario para enviar. Nunca copies una '
                     'respuesta secreta.\n'
                     'Amplía a un mínimo de 80x24. Los ajustes controlan idioma, tema y vista ASCII. Están '
                     'disponibles los siete idiomas del toolkit.\n'
                     'Una interrupción puede dejar un actualizador activo o un estado desconocido. Revisa '
                     'las pruebas de recuperación; nunca borres diarios ni bloqueos para saltarte una '
                     'protección.\n'
                     'Up/Down selecciona; Tab cambia de panel; Space selecciona grupos; Enter abre. r inicia '
                     'la operación seleccionada; d muestra la vista previa; i abre el diálogo de respuesta.\n'
                     'F1 o ? abre la ayuda; Ctrl-P la paleta de acciones; Esc vuelve; q solicita salir; '
                     'PgUp/PgDn desplaza la salida.\n'
                     'El cambio automático de tamaño es opcional; el terminal puede ignorarlo. Al salir se '
                     'solicita el tamaño anterior. Por debajo de 80x24 se bloquean las operaciones que '
                     'modifican el estado.',
        'auto_resize': 'Tamaño automático de ventana',
        'window_hint': 'El cambio automático de tamaño es opcional; el terminal puede ignorarlo. Al salir se '
                       'solicita el tamaño anterior. Por debajo de 80x24 se bloquean las operaciones que '
                       'modifican el estado.'},
 'fr': {'app_title': 'macOS Updates',
        'nav_home': 'Tableau de bord',
        'nav_updates': 'Mises à jour',
        'nav_inventory': 'Inventaire',
        'nav_catalog': 'Catalogue d’applications',
        'nav_diagnostics': 'Diagnostic',
        'nav_history': 'Historique',
        'nav_settings': 'Réglages',
        'nav_wizard': 'Premiers pas',
        'nav_help': 'Aide',
        'action_preview': 'Voir le plan de mise à jour',
        'desc_preview': 'Afficher les périmètres proposés sans mettre à jour de logiciel ni accorder '
                        'd’autorisation.',
        'action_update': 'Lancer le parcours de mise à jour',
        'desc_update': 'Vérifier les logiciels installés et examiner les actions admissibles. Les '
                       'confirmations existantes restent requises.',
        'action_inventory': 'Actualiser l’inventaire',
        'desc_inventory': 'Observer les logiciels installés et reconstruire les rapports locaux '
                          'd’inventaire.',
        'action_setup_inspect': 'Vérifier la configuration',
        'desc_setup_inspect': 'Vérifier les prérequis sans installer de dépendances ni modifier les profils '
                              'du shell.',
        'action_setup_dependencies': 'Examiner les dépendances facultatives',
        'desc_setup_dependencies': 'Afficher les outils facultatifs et demander une autorisation distincte '
                                   'pour chaque installation.',
        'action_setup_shell': 'Examiner la configuration du shell',
        'desc_setup_shell': 'Afficher la modification du profil du shell et demander avant de l’appliquer.',
        'action_catalog': 'Ouvrir le catalogue d’applications',
        'desc_catalog': 'Parcourir les produits facultatifs. L’ouverture ne sélectionne et n’installe rien.',
        'action_preferences': 'Examiner les autorisations',
        'desc_preferences': 'Examiner ou réinitialiser les choix enregistrés par cible. La consultation '
                            'n’accorde aucune nouvelle autorisation.',
        'action_doctor': 'Vérifier la disponibilité',
        'desc_doctor': 'Diagnostic en lecture seule des outils, autorisations et prérequis du toolkit.',
        'action_coverage': 'Voir la couverture des mises à jour',
        'desc_coverage': 'Afficher les sources observées et les méthodes disponibles pour les logiciels '
                         'installés.',
        'action_sources': 'Examiner les preuves des sources',
        'desc_sources': 'Examiner les sources et les conseils de versions stables sans migrer de logiciel.',
        'action_migration_preview': 'Voir la migration de l’inventaire',
        'desc_migration_preview': 'Comparer l’ancien inventaire Markdown aux observations structurées avant '
                                  'une acceptation distincte.',
        'actions': 'Actions',
        'groups': 'Groupes de mise à jour',
        'details': 'Détails',
        'live_log': 'Sortie en direct',
        'tasks': 'Opérations',
        'idle': 'Au repos',
        'running': 'En cours',
        'completed': 'Terminé',
        'warnings': 'Avertissements',
        'failed': 'Échec',
        'waiting': 'En attente de réponse',
        'elapsed': 'Temps écoulé',
        'progress': 'Progression',
        'unknown': 'Inconnu',
        'none': 'Aucun',
        'start': 'Démarrer',
        'confirm': 'Confirmer',
        'cancel': 'Annuler',
        'back': 'Retour',
        'next': 'Suivant',
        'finish': 'Terminer',
        'save': 'Enregistrer',
        'saved': 'Enregistré',
        'input': 'Réponse',
        'secret_input': 'Réponse masquée',
        'input_hint': 'La touche i ouvre le dialogue de réponse ; Enter envoie la réponse saisie dans ce '
                      'dialogue. Les mots de passe sont masqués, jamais enregistrés ni copiés.',
        'confirm_body': 'Démarrer l’opération affichée ? Les confirmations propres aux applications et au '
                        'système restent requises.',
        'interrupt_body': 'Demander une interruption ? Un programme de mise à jour peut rester actif et son '
                          'état non résolu. Ne jamais supprimer les journaux de récupération ou les verrous '
                          'pour continuer.',
        'busy': 'Une opération est en cours. Consulter sa sortie ou attendre la fin.',
        'no_history': 'Aucun historique d’opérations.',
        'history_hint': 'Consulter les résultats locaux. Un code de sortie réussi ne prouve pas à lui seul '
                        'une mise à jour.',
        'help_title': 'Aide du tableau de bord',
        'shortcut_hint': 'Up/Down sélection ; Tab change de panneau ; Enter ouvre ; F1 aide ; Ctrl-P '
                         'actions.',
        'resize': 'Agrandir le terminal à au moins 80x24 ou utiliser la CLI classique.',
        'palette': 'Palette d’actions',
        'search': 'Rechercher des actions',
        'language': 'Langue',
        'theme': 'Thème',
        'ascii': 'Affichage ASCII',
        'wizard_complete': 'Vérification initiale terminée. Démarrer les mises à jour reste un choix '
                           'distinct.',
        'wizard_intro': 'Examiner les prérequis, l’inventaire, les sources et les réglages, puis un plan. '
                        'Chaque modification conserve ses confirmations.',
        'settings_hint': 'Ces réglages concernent le tableau de bord. Les autorisations de mise à jour '
                         'enregistrées restent distinctes.',
        'groups_hint': 'Sélectionner les groupes avec Space. La sélection limite le périmètre sans autoriser '
                       'une mise à jour.',
        'serial_notice': 'Les opérations s’exécutent une par une. Les gestionnaires partagés et les '
                         'auxiliaires non résolus conservent leurs verrous de sécurité.',
        'readonly_notice': 'La navigation ne modifie aucun logiciel. Démarrer chaque opération explicitement '
                           '; ses contrôles d’autorisation restent applicables.',
        'error': 'Erreur : {message}',
        'quit_body': 'Quitter le tableau de bord ? Une mise à jour active peut continuer ; un état non '
                     'résolu exige une récupération vérifiée.',
        'not_available': 'Cette opération est indisponible dans l’environnement actuel.',
        'job_finished': 'Opération terminée avec le code de sortie {code}.',
        'scan_hint': 'L’inventaire observé est une preuve, pas une garantie qu’une mise à jour soit '
                     'disponible.',
        'copy': 'Copier',
        'paste': 'Coller',
        'copied': 'Copié',
        'clipboard_unavailable': 'Presse-papiers indisponible. Utiliser la sélection du terminal.',
        'copy_command': 'Copier la commande',
        'copy_log': 'Copier la sortie visible',
        'copy_summary': 'Copier le résumé',
        'group_appstore': 'App Store',
        'group_npm': 'CLI natives et npm',
        'group_brew': 'Homebrew',
        'group_internet': 'Applications des éditeurs',
        'group_system': 'Système macOS',
        'wizardstep_welcome': 'Bienvenue',
        'wizarddesc_welcome': 'Découvrir la séparation entre observation, sélection et consentement.',
        'wizardstep_requirements': 'Prérequis',
        'wizarddesc_requirements': 'Vérifier les outils et leur disponibilité. Les dépendances manquantes '
                                   'exigent une approbation distincte.',
        'wizardstep_inventory': 'Inventaire',
        'wizarddesc_inventory': 'Observer les logiciels installés et actualiser l’inventaire local lorsque '
                                'vous le décidez.',
        'wizardstep_sources': 'Sources',
        'wizarddesc_sources': 'Examiner les sources d’installation observées. Une propriété non résolue '
                              'reste manuelle.',
        'wizardstep_settings': 'Réglages',
        'wizarddesc_settings': 'Choisir la langue, le thème et l’affichage ASCII du tableau de bord.',
        'wizardstep_preview': 'Aperçu',
        'wizarddesc_preview': 'Examiner les périmètres proposés sans mettre à jour les apps ni accorder '
                              'd’autorisation.',
        'wizardstep_finish': 'Vérification terminée',
        'wizarddesc_finish': 'Examiner le résumé. Démarrer les mises à jour est une opération distincte.',
        'help_body': 'Première utilisation : ouvrir le guide initial pour vérifier les prérequis, '
                     'l’inventaire et les sources, puis consulter un plan.\n'
                     'Sélectionner les groupes avec Space. La sélection n’accorde aucun consentement ; les '
                     'confirmations des applications et du système restent requises.\n'
                     'La sortie en direct suit l’opération. Utiliser i pour répondre uniquement dans le '
                     'dialogue explicite. Les mots de passe sont masqués, jamais enregistrés ni copiés.\n'
                     'Utiliser c pour copier la commande, la sortie ou le résumé actif. Ctrl-V colle '
                     'uniquement dans le dialogue de réponse ; Enter reste nécessaire pour envoyer. Ne '
                     'jamais copier une réponse secrète.\n'
                     'Agrandir à au moins 80x24. Les réglages contrôlent langue, thème et affichage ASCII. '
                     'Les sept langues du toolkit sont disponibles.\n'
                     'Une interruption peut laisser une mise à jour active ou un état inconnu. Examiner les '
                     'preuves de récupération ; ne jamais supprimer les journaux ou les verrous pour '
                     'contourner une protection.\n'
                     'Up/Down sélectionne ; Tab change de panneau ; Space sélectionne les groupes ; Enter '
                     'ouvre. r lance l’opération sélectionnée ; d affiche l’aperçu ; i ouvre la réponse.\n'
                     'F1 ou ? ouvre l’aide ; Ctrl-P la palette d’actions ; Esc revient ; q demande à quitter '
                     '; PgUp/PgDn fait défiler la sortie.\n'
                     'Le redimensionnement automatique est facultatif ; le terminal peut ignorer les '
                     'demandes. La taille précédente est demandée à la sortie. En dessous de 80x24, les '
                     'opérations modifiant l’état sont bloquées.',
        'auto_resize': 'Taille automatique de la fenêtre',
        'window_hint': 'Le redimensionnement automatique est facultatif ; le terminal peut ignorer les '
                       'demandes. La taille précédente est demandée à la sortie. En dessous de 80x24, les '
                       'opérations modifiant l’état sont bloquées.'},
 'it': {'app_title': 'macOS Updates',
        'nav_home': 'Pannello principale',
        'nav_updates': 'Aggiornamenti',
        'nav_inventory': 'Inventario',
        'nav_catalog': 'Catalogo applicazioni',
        'nav_diagnostics': 'Diagnostica',
        'nav_history': 'Cronologia',
        'nav_settings': 'Impostazioni',
        'nav_wizard': 'Primo utilizzo',
        'nav_help': 'Aiuto',
        'action_preview': 'Visualizza piano aggiornamenti',
        'desc_preview': 'Mostra gli ambiti proposti senza aggiornare software o concedere autorizzazioni.',
        'action_update': 'Avvia procedura aggiornamenti',
        'desc_update': 'Controlla il software installato ed esamina le azioni ammissibili. Restano valide le '
                       'conferme esistenti.',
        'action_inventory': 'Aggiorna inventario',
        'desc_inventory': 'Osserva il software installato e ricostruisce i rapporti locali dell’inventario.',
        'action_setup_inspect': 'Controlla configurazione',
        'desc_setup_inspect': 'Verifica i requisiti senza installare dipendenze o modificare i profili della '
                              'shell.',
        'action_setup_dependencies': 'Esamina dipendenze facoltative',
        'desc_setup_dependencies': 'Mostra gli strumenti facoltativi e chiede un’autorizzazione separata per '
                                   'ogni installazione.',
        'action_setup_shell': 'Esamina configurazione shell',
        'desc_setup_shell': 'Mostra la modifica al profilo della shell e chiede prima di applicarla.',
        'action_catalog': 'Apri catalogo applicazioni',
        'desc_catalog': 'Esplora i prodotti facoltativi. Aprire il catalogo non seleziona e non installa '
                        'nulla.',
        'action_preferences': 'Esamina autorizzazioni',
        'desc_preferences': 'Esamina o azzera le scelte salvate per ogni destinazione. La consultazione non '
                            'concede nuovi permessi.',
        'action_doctor': 'Verifica preparazione',
        'desc_doctor': 'Diagnostica in sola lettura di strumenti, autorizzazioni e preparazione del toolkit.',
        'action_coverage': 'Mostra copertura aggiornamenti',
        'desc_coverage': 'Mostra le fonti osservate e i metodi disponibili per il software installato.',
        'action_sources': 'Esamina prove delle fonti',
        'desc_sources': 'Esamina fonti e consigli sulle versioni stabili senza migrare software.',
        'action_migration_preview': 'Visualizza migrazione inventario',
        'desc_migration_preview': 'Confronta il vecchio inventario Markdown con osservazioni strutturate '
                                  'prima dell’accettazione separata.',
        'actions': 'Azioni',
        'groups': 'Gruppi di aggiornamento',
        'details': 'Dettagli',
        'live_log': 'Uscita in tempo reale',
        'tasks': 'Operazioni',
        'idle': 'Inattivo',
        'running': 'In corso',
        'completed': 'Completato',
        'warnings': 'Avvisi',
        'failed': 'Non riuscito',
        'waiting': 'In attesa di risposta',
        'elapsed': 'Tempo trascorso',
        'progress': 'Avanzamento',
        'unknown': 'Sconosciuto',
        'none': 'Nessuno',
        'start': 'Avvia',
        'confirm': 'Conferma',
        'cancel': 'Annulla',
        'back': 'Indietro',
        'next': 'Avanti',
        'finish': 'Termina',
        'save': 'Salva',
        'saved': 'Salvato',
        'input': 'Risposta',
        'secret_input': 'Risposta nascosta',
        'input_hint': 'Usa i per aprire la finestra di risposta; Enter invia quanto scritto al suo interno. '
                      'Le password sono mascherate, mai salvate o copiate.',
        'confirm_body': 'Avviare l’operazione mostrata? Restano valide le conferme delle singole '
                        'applicazioni e del sistema.',
        'interrupt_body': 'Richiedere l’interruzione? Un programma di aggiornamento può restare attivo e il '
                          'suo stato irrisolto. Non eliminare mai registri di recupero o blocchi per '
                          'continuare.',
        'busy': 'È in corso un’operazione. Esamina l’uscita o attendi la conclusione.',
        'no_history': 'Non ci sono ancora operazioni nella cronologia.',
        'history_hint': 'Esamina i risultati locali. Un codice di uscita riuscito da solo non dimostra un '
                        'aggiornamento.',
        'help_title': 'Aiuto del pannello',
        'shortcut_hint': 'Up/Down seleziona; Tab cambia riquadro; Enter apre; F1 aiuto; Ctrl-P azioni.',
        'resize': 'Allarga il terminale ad almeno 80x24 oppure usa la CLI normale.',
        'palette': 'Tavolozza azioni',
        'search': 'Cerca azioni',
        'language': 'Lingua',
        'theme': 'Tema',
        'ascii': 'Visualizzazione ASCII',
        'wizard_complete': 'Verifica iniziale completata. Avviare gli aggiornamenti resta una scelta '
                           'separata.',
        'wizard_intro': 'Esamina requisiti, inventario, fonti e impostazioni, poi un piano. Le modifiche '
                        'mantengono le proprie conferme.',
        'settings_hint': 'Queste impostazioni riguardano il pannello. Le autorizzazioni salvate restano '
                         'separate.',
        'groups_hint': 'Seleziona i gruppi con Space. La selezione limita l’ambito e non autorizza un '
                       'aggiornamento.',
        'serial_notice': 'Le operazioni si eseguono una alla volta. I gestori condivisi e gli ausiliari '
                         'irrisolti mantengono i blocchi di sicurezza.',
        'readonly_notice': 'La navigazione non cambia il software. Avvia esplicitamente ogni operazione; '
                           'restano validi i suoi controlli di autorizzazione.',
        'error': 'Errore: {message}',
        'quit_body': 'Uscire dal pannello? Un aggiornamento attivo può proseguire; uno stato irrisolto '
                     'richiede un recupero verificato.',
        'not_available': 'Questa operazione non è disponibile nell’ambiente attuale.',
        'job_finished': 'Operazione terminata con codice di uscita {code}.',
        'scan_hint': 'L’inventario osservato è una prova, non una garanzia di un aggiornamento disponibile.',
        'copy': 'Copia',
        'paste': 'Incolla',
        'copied': 'Copiato',
        'clipboard_unavailable': 'Appunti non disponibili. Usa la selezione del terminale.',
        'copy_command': 'Copia comando',
        'copy_log': 'Copia uscita visibile',
        'copy_summary': 'Copia riepilogo',
        'group_appstore': 'App Store',
        'group_npm': 'CLI native e npm',
        'group_brew': 'Homebrew',
        'group_internet': 'Applicazioni dei produttori',
        'group_system': 'Sistema macOS',
        'wizardstep_welcome': 'Benvenuto',
        'wizarddesc_welcome': 'Scopri come il pannello distingue osservazione, selezione e consenso.',
        'wizardstep_requirements': 'Requisiti',
        'wizarddesc_requirements': 'Controlla strumenti e preparazione. Le dipendenze mancanti richiedono '
                                   'un’approvazione separata.',
        'wizardstep_inventory': 'Inventario',
        'wizarddesc_inventory': 'Osserva il software installato e aggiorna l’inventario locale quando lo '
                                'decidi.',
        'wizardstep_sources': 'Fonti',
        'wizarddesc_sources': 'Esamina le fonti di installazione osservate. La proprietà irrisolta resta '
                              'manuale.',
        'wizardstep_settings': 'Impostazioni',
        'wizarddesc_settings': 'Scegli lingua, tema e visualizzazione ASCII del pannello.',
        'wizardstep_preview': 'Anteprima',
        'wizarddesc_preview': 'Esamina gli ambiti proposti senza aggiornare applicazioni o concedere nuovi '
                              'permessi.',
        'wizardstep_finish': 'Verifica completata',
        'wizarddesc_finish': 'Esamina il riepilogo. Avviare gli aggiornamenti è un’operazione separata.',
        'help_body': 'Primo utilizzo: apri la guida iniziale per controllare requisiti, inventario e fonti, '
                     'poi esamina un piano.\n'
                     'Seleziona i gruppi con Space. La selezione non concede consenso; restano valide le '
                     'conferme delle applicazioni e del sistema.\n'
                     'L’uscita in tempo reale segue l’operazione. Usa i per rispondere solo nella finestra '
                     'esplicita. Le password sono mascherate, mai salvate o copiate.\n'
                     'Usa c per copiare comando, uscita o riepilogo attivo. Ctrl-V incolla solo nella '
                     'finestra di risposta; Enter resta necessario per inviare. Non copiare mai risposte '
                     'segrete.\n'
                     'Allarga ad almeno 80x24. Le impostazioni controllano lingua, tema e vista ASCII. Sono '
                     'disponibili tutte e sette le lingue del toolkit.\n'
                     'Un’interruzione può lasciare un aggiornamento attivo o uno stato sconosciuto. Esamina '
                     'le prove di recupero; non eliminare mai registri o blocchi per aggirare una '
                     'protezione.\n'
                     'Up/Down seleziona; Tab cambia riquadro; Space seleziona i gruppi; Enter apre. r avvia '
                     'l’operazione scelta; d mostra l’anteprima; i apre la risposta.\n'
                     'F1 o ? apre l’aiuto; Ctrl-P la tavolozza azioni; Esc torna indietro; q richiede '
                     'l’uscita; PgUp/PgDn scorre l’uscita.\n'
                     'Il ridimensionamento automatico è facoltativo; il terminale può ignorare le richieste. '
                     'All’uscita viene richiesta la dimensione precedente. Sotto 80x24 sono bloccate le '
                     'operazioni che modificano lo stato.',
        'auto_resize': 'Dimensione automatica finestra',
        'window_hint': 'Il ridimensionamento automatico è facoltativo; il terminale può ignorare le '
                       'richieste. All’uscita viene richiesta la dimensione precedente. Sotto 80x24 sono '
                       'bloccate le operazioni che modificano lo stato.'},
 'pt': {'app_title': 'macOS Updates',
        'nav_home': 'Painel principal',
        'nav_updates': 'Atualizações',
        'nav_inventory': 'Inventário',
        'nav_catalog': 'Catálogo de aplicações',
        'nav_diagnostics': 'Diagnóstico',
        'nav_history': 'Histórico',
        'nav_settings': 'Definições',
        'nav_wizard': 'Primeira utilização',
        'nav_help': 'Ajuda',
        'action_preview': 'Ver plano de atualização',
        'desc_preview': 'Mostra os âmbitos propostos sem atualizar software nem conceder permissões.',
        'action_update': 'Iniciar processo de atualização',
        'desc_update': 'Verifica o software instalado e revê ações elegíveis. As confirmações existentes '
                       'continuam válidas.',
        'action_inventory': 'Atualizar inventário',
        'desc_inventory': 'Observa o software instalado e reconstrói os relatórios locais do inventário.',
        'action_setup_inspect': 'Inspecionar configuração',
        'desc_setup_inspect': 'Verifica requisitos sem instalar dependências nem alterar perfis da shell.',
        'action_setup_dependencies': 'Rever dependências opcionais',
        'desc_setup_dependencies': 'Mostra ferramentas opcionais e pede autorização separada para cada '
                                   'instalação.',
        'action_setup_shell': 'Rever configuração da shell',
        'desc_setup_shell': 'Mostra a alteração do perfil da shell e pergunta antes de a aplicar.',
        'action_catalog': 'Abrir catálogo de aplicações',
        'desc_catalog': 'Explora produtos opcionais. Abrir o catálogo não seleciona nem instala nada.',
        'action_preferences': 'Rever permissões de atualização',
        'desc_preferences': 'Revê ou repõe decisões guardadas por destino. A consulta não concede novas '
                            'permissões.',
        'action_doctor': 'Verificar preparação',
        'desc_doctor': 'Diagnóstico só de leitura de ferramentas, permissões e preparação do toolkit.',
        'action_coverage': 'Mostrar cobertura de atualizações',
        'desc_coverage': 'Mostra fontes observadas e métodos disponíveis para o software instalado.',
        'action_sources': 'Rever provas das fontes',
        'desc_sources': 'Revê fontes e recomendações de versões estáveis sem migrar software.',
        'action_migration_preview': 'Ver migração do inventário',
        'desc_migration_preview': 'Compara o inventário Markdown anterior com observações estruturadas antes '
                                  'da aceitação separada.',
        'actions': 'Ações',
        'groups': 'Grupos de atualização',
        'details': 'Detalhes',
        'live_log': 'Saída em direto',
        'tasks': 'Operações',
        'idle': 'Inativo',
        'running': 'Em execução',
        'completed': 'Concluído',
        'warnings': 'Avisos',
        'failed': 'Falhou',
        'waiting': 'À espera de resposta',
        'elapsed': 'Tempo decorrido',
        'progress': 'Progresso',
        'unknown': 'Desconhecido',
        'none': 'Nenhum',
        'start': 'Iniciar',
        'confirm': 'Confirmar',
        'cancel': 'Cancelar',
        'back': 'Voltar',
        'next': 'Seguinte',
        'finish': 'Concluir',
        'save': 'Guardar',
        'saved': 'Guardado',
        'input': 'Resposta',
        'secret_input': 'Resposta oculta',
        'input_hint': 'Utilize i para abrir a janela de resposta; Enter envia o texto escrito nessa janela. '
                      'As palavras-passe são ocultadas, nunca guardadas nem copiadas.',
        'confirm_body': 'Iniciar a operação apresentada? As confirmações de cada aplicação e do sistema '
                        'continuam válidas.',
        'interrupt_body': 'Pedir interrupção? Um atualizador pode continuar ativo e o seu estado ficar por '
                          'resolver. Nunca elimine diários de recuperação ou bloqueios para continuar.',
        'busy': 'Está uma operação em execução. Reveja a saída ou aguarde a conclusão.',
        'no_history': 'Ainda não existe histórico de operações.',
        'history_hint': 'Reveja os resultados locais. Um código de saída bem-sucedido não comprova, por si '
                        'só, uma atualização.',
        'help_title': 'Ajuda do painel',
        'shortcut_hint': 'Up/Down seleciona; Tab muda de painel; Enter abre; F1 ajuda; Ctrl-P ações.',
        'resize': 'Aumente o terminal para pelo menos 80x24 ou utilize a CLI normal.',
        'palette': 'Paleta de ações',
        'search': 'Procurar ações',
        'language': 'Idioma',
        'theme': 'Tema',
        'ascii': 'Vista ASCII',
        'wizard_complete': 'Revisão inicial concluída. Iniciar atualizações continua a ser uma escolha '
                           'separada.',
        'wizard_intro': 'Reveja requisitos, inventário, fontes e definições; depois inspecione um plano. As '
                        'alterações mantêm as suas confirmações.',
        'settings_hint': 'Estas definições afetam o painel. As permissões de atualização guardadas '
                         'permanecem separadas.',
        'groups_hint': 'Selecione grupos com Space. A seleção limita o âmbito e não autoriza uma '
                       'atualização.',
        'serial_notice': 'As operações executam-se uma de cada vez. Gestores partilhados e auxiliares por '
                         'resolver mantêm os bloqueios de segurança.',
        'readonly_notice': 'Navegar não altera o software. Inicie cada operação explicitamente; as suas '
                           'verificações de permissão continuam válidas.',
        'error': 'Erro: {message}',
        'quit_body': 'Sair do painel? Um atualizador ativo pode continuar; um estado por resolver exige '
                     'recuperação revista.',
        'not_available': 'Esta operação não está disponível no ambiente atual.',
        'job_finished': 'Operação concluída com o código de saída {code}.',
        'scan_hint': 'O inventário observado é uma prova, não uma garantia de atualização disponível.',
        'copy': 'Copiar',
        'paste': 'Colar',
        'copied': 'Copiado',
        'clipboard_unavailable': 'A área de transferência está indisponível. Utilize a seleção do terminal.',
        'copy_command': 'Copiar comando',
        'copy_log': 'Copiar saída visível',
        'copy_summary': 'Copiar resumo',
        'group_appstore': 'App Store',
        'group_npm': 'CLI nativas e npm',
        'group_brew': 'Homebrew',
        'group_internet': 'Aplicações dos fornecedores',
        'group_system': 'Sistema macOS',
        'wizardstep_welcome': 'Bem-vindo',
        'wizarddesc_welcome': 'Saiba como o painel separa observação, seleção e consentimento.',
        'wizardstep_requirements': 'Requisitos',
        'wizarddesc_requirements': 'Verifique ferramentas e preparação. As dependências em falta exigem '
                                   'aprovação separada.',
        'wizardstep_inventory': 'Inventário',
        'wizarddesc_inventory': 'Observe o software instalado e atualize o inventário local quando decidir.',
        'wizardstep_sources': 'Fontes',
        'wizarddesc_sources': 'Reveja as fontes de instalação observadas. A propriedade por resolver '
                              'permanece manual.',
        'wizardstep_settings': 'Definições',
        'wizarddesc_settings': 'Escolha o idioma, o tema e a vista ASCII do painel.',
        'wizardstep_preview': 'Pré-visualização',
        'wizarddesc_preview': 'Reveja os âmbitos propostos sem atualizar aplicações nem conceder novas '
                              'permissões.',
        'wizardstep_finish': 'Revisão concluída',
        'wizarddesc_finish': 'Reveja o resumo. Iniciar atualizações é uma operação separada.',
        'help_body': 'Primeira utilização: abra o guia inicial para verificar requisitos, inventário e '
                     'fontes; depois reveja um plano.\n'
                     'Selecione grupos com Space. A seleção não concede consentimento; as confirmações das '
                     'aplicações e do sistema continuam válidas.\n'
                     'A saída em direto acompanha a operação. Utilize i para responder apenas na janela '
                     'explícita. As palavras-passe são ocultadas, nunca guardadas nem copiadas.\n'
                     'Utilize c para copiar o comando, a saída ou o resumo ativo. Ctrl-V cola apenas na '
                     'janela de resposta; Enter continua a ser necessário para enviar. Nunca copie respostas '
                     'secretas.\n'
                     'Aumente para pelo menos 80x24. As definições controlam idioma, tema e vista ASCII. '
                     'Estão disponíveis os sete idiomas do toolkit.\n'
                     'Uma interrupção pode deixar um atualizador ativo ou um estado desconhecido. Reveja as '
                     'provas de recuperação; nunca elimine diários ou bloqueios para contornar uma '
                     'proteção.\n'
                     'Up/Down seleciona; Tab muda de painel; Space seleciona grupos; Enter abre. r inicia a '
                     'operação escolhida; d mostra a pré-visualização; i abre a resposta.\n'
                     'F1 ou ? abre a ajuda; Ctrl-P a paleta de ações; Esc volta; q pede a saída; PgUp/PgDn '
                     'desloca a saída.\n'
                     'O redimensionamento automático é opcional; o terminal pode ignorar os pedidos. Ao sair '
                     'é pedido o tamanho anterior da janela. Abaixo de 80x24, as operações que alteram o '
                     'estado são bloqueadas.',
        'auto_resize': 'Tamanho automático da janela',
        'window_hint': 'O redimensionamento automático é opcional; o terminal pode ignorar os pedidos. Ao '
                       'sair é pedido o tamanho anterior da janela. Abaixo de 80x24, as operações que '
                       'alteram o estado são bloqueadas.'}}


# Phase labels and safe fallback are UI observations, not update acceptance.
CATALOGS['en'].update({'queued': 'Queued', 'skipped': 'Skipped', 'ui_recovery': 'The dashboard stopped, but the current task is still running. Continue in this text terminal. Answers are forwarded only when you type them; passwords are not echoed.'})
CATALOGS['pl'].update({'queued': 'W kolejce', 'skipped': 'Pominięte', 'ui_recovery': 'Panel przestał działać, ale bieżące zadanie nadal trwa. Kontynuuj w tym terminalu tekstowym. Przekazywane są tylko wpisane przez Ciebie odpowiedzi; hasła nie są wyświetlane.'})
CATALOGS['de'].update({'queued': 'In Warteschlange', 'skipped': 'Übersprungen', 'ui_recovery': 'Das Dashboard wurde beendet, aber die Aufgabe läuft weiter. Fahren Sie in diesem Textterminal fort. Nur Ihre eingegebenen Antworten werden weitergegeben; Passwörter werden nicht angezeigt.'})
CATALOGS['es'].update({'queued': 'En cola', 'skipped': 'Omitido', 'ui_recovery': 'El panel se detuvo, pero la tarea sigue activa. Continúa en este terminal de texto. Solo se envían las respuestas que escribas; las contraseñas no se muestran.'})
CATALOGS['fr'].update({'queued': 'En attente', 'skipped': 'Ignoré', 'ui_recovery': 'Le tableau de bord s’est arrêté, mais la tâche continue. Poursuivez dans ce terminal texte. Seules vos réponses saisies sont transmises ; les mots de passe ne sont pas affichés.'})
CATALOGS['it'].update({'queued': 'In coda', 'skipped': 'Saltato', 'ui_recovery': 'Il pannello si è fermato, ma l’attività è ancora in corso. Continua in questo terminale testuale. Vengono inviate solo le risposte che digiti; le password non sono visualizzate.'})
CATALOGS['pt'].update({'queued': 'Na fila', 'skipped': 'Ignorado', 'ui_recovery': 'O painel parou, mas a tarefa continua em execução. Continue neste terminal de texto. Só as respostas que digitar são enviadas; as senhas não são exibidas.'})

# Theme choices are explicit labels in the settings pane.
CATALOGS['en'].update({'theme_dark': 'Dark', 'theme_light': 'Light'})
CATALOGS['pl'].update({'theme_dark': 'Ciemny', 'theme_light': 'Jasny'})
CATALOGS['de'].update({'theme_dark': 'Dunkel', 'theme_light': 'Hell'})
CATALOGS['es'].update({'theme_dark': 'Oscuro', 'theme_light': 'Claro'})
CATALOGS['fr'].update({'theme_dark': 'Sombre', 'theme_light': 'Clair'})
CATALOGS['it'].update({'theme_dark': 'Scuro', 'theme_light': 'Chiaro'})
CATALOGS['pt'].update({'theme_dark': 'Escuro', 'theme_light': 'Claro'})


def tr(key, lang="en", **values):
    """Translate a closed UI key; unsupported languages use English.

    Missing values remain visible rather than crashing a running dashboard.
    User-provided values are text only and never become catalog keys or code.
    """
    catalog = CATALOGS.get(lang, CATALOGS["en"])
    template = catalog.get(key, key)
    if not values:
        return template
    try:
        return template.format(**values)
    except (KeyError, ValueError, IndexError):
        return template
