# Przewodnik (polski)

**Aktualizacje macOS 2.0.10** · Mac z Apple Silicon · macOS 13 lub nowszy

## Co robi program

Jedno uruchomienie aktualizuje po kolei:

1. aplikacje z App Store,
2. narzędzia terminala (npm, bun i narzędzia wiersza poleceń, które same się aktualizują),
3. formuły i aplikacje Homebrew (formulae i casks),
4. aplikacje z internetu: pobrane ze strony producenta, aktualizowane z jego kanału aktualizacji, sprawdzonym bezpośrednim pobraniem albo własnym aktualizatorem aplikacji,
5. spis Twoich aplikacji (odświeżany),
6. macOS, zawsze na końcu.

Nie pyta o zgodę dla każdej aplikacji. Działa tylko na tym, co jest już zainstalowane.

## Czego program nigdy nie robi

- Nie zamyka otwartej aplikacji. Taka aplikacja trafia do pozycji „Wymaga Ciebie”.
- Nie instaluje aplikacji, której nie masz. (Jedynie opcjonalna karta Katalog może coś zainstalować, i to tylko to, co sam wybierzesz.)
- Nie ufa pobranym plikom w ciemno. Plik musi pochodzić z dozwolonego serwera, mieć poprawny podpis kodu i przejść kontrolę Gatekeepera.
- Nie przerywa wszystkiego przez jeden błąd. Pozostałe pozycje, kolejne kroki i aktualizacja macOS i tak się wykonają.

## Otwieranie interfejsu

```bash
mac-update
```

W terminalu otworzy się interfejs. W skrypcie, przez SSH bez terminala albo z `MAC_UPDATE_NONINTERACTIVE=1` dostaniesz zwykły tekst. `mac-update run` zawsze daje zwykły tekst. `mac-update --cli` (także `--plain`) robi to samo co `mac-update run`, `mac-update --tui` otwiera interfejs jak samo `mac-update`, a `macos-update` to to samo polecenie pod dłuższą nazwą. Wszystkie działają z dowolnego folderu. Okno musi mieć co najmniej 40 kolumn na 12 wierszy. Większe jest przyjemniejsze: jeśli zostawisz włączone „Dopasuj rozmiar okna automatycznie”, interfejs przy starcie prosi terminal o 120 na 36 i przywraca rozmiar przy wyjściu.

Poruszasz się strzałkami. Enter otwiera lub potwierdza, Tab przechodzi do następnego panelu, Esc cofa, `1` do `7` przeskakuje do karty, `?` otwiera pomoc, `L` pokazuje cały dziennik, `q` kończy. Działa też mysz. Dolny wiersz zawsze pokazuje klawisze, które działają w tej chwili.

## Karty

```
 Aktualizacje macOS                          Ostatnio: zakończone, 2 godz. temu
 Pulpit   Aplikacje   Katalog   Historia   Ustawienia   Diagnostyka   Pomoc
 +- Grupy aktualizacji ------------------------------------------------+
 | > v Sprawdzenie wstępne  ############  gotowe                        |
 |   v App Store            ############  v3 .5                         |
 |   v Narzędzia terminala  ############  v2 .9                         |
 |   * Homebrew             ######......  4/9  v1 .3                    |
 |   . Aplikacje z internetu ...........  czeka                         |
 |   . Spis aplikacji       ............  czeka                         |
 |   . System macOS         ............  czeka                         |
 +---------------------------------------------------------------------+
   [ Aktualizuj wszystko ]   [ Podgląd (bez zmian) ]
   v zaktualizowane   . aktualne   ! wymaga Ciebie   x błąd
```

To uproszczony rysunek. Prawdziwy ekran ma kolory i symbole.

| Karta | Do czego służy |
|-------|----------------|
| **Pulpit** | Uruchamianie aktualizacji. Pokazuje każdą grupę z postępem na żywo (zrobione z wszystkich), a w trakcie pracy także przewijaną listę aplikacji w grupie. Enter lub spacja na grupie włącza albo wyłącza ją przy następnym uruchomieniu. Panel z boku pokazuje ostatnie uruchomienie, to, co nadal wymaga Ciebie, najbliższe uruchomienie automatyczne i stan tego Maca. |
| **Aplikacje** | Wszystkie aplikacje i pakiety znalezione na tym Macu (aplikacje pomocnicze i działające w tle są pominięte). Dla każdej wybierasz sposób aktualizacji. |
| **Katalog** | Wszystkie sprawdzone aplikacje: najpierw te, które można jeszcze dodać, potem już zainstalowane (tylko do wglądu). Nic nie jest zaznaczone, dopóki sam nie wybierzesz, a instalator pyta przed każdą zmianą. Aktualizacja go nie używa. |
| **Historia** | Wcześniejsze uruchomienia, najnowsze na górze, każde z wynikiem. Po wybraniu uruchomienia zobaczysz, co zaktualizowano i co wymagało Ciebie. Enter otwiera jego cały dziennik. |
| **Ustawienia** | Co aktualizować, zabezpieczenia, uruchamianie automatyczne, język i wygląd. Każda zmiana zapisuje się od razu. |
| **Diagnostyka** | Sprawdzenia do uruchomienia: sprawdź tego Maca, sprawdź wymagania, jak aktualizowane są aplikacje (tabela wszystkich aplikacji i tego, skąd znana jest metoda), sprawdź kanały aktualizacji, odśwież spis aplikacji, dokończ przerwane aktualizacje, sprawdź nową wersję programu. |
| **Pomoc** | Krótki przewodnik: pierwsze kroki, jak działa aktualizacja, do czego służy każda karta, co znaczy „Wymaga Ciebie”. |

## Uruchamianie aktualizacji

- **Aktualizuj wszystko** sprawdza i aktualizuje każdą włączoną grupę.
- **Podgląd (bez zmian)** przechodzi przez te same kroki i pokazuje, co by się stało. Niczego nie instaluje i nie zapisuje historii.

W trakcie widzisz każdą grupę i aplikację: sprawdzanie, pobieranie, weryfikacja, instalacja. Klawisz `L` otwiera cały dziennik. **Zatrzymaj** kończy pracę bezpiecznie: aplikacje, które już się zaktualizowały, zostają zaktualizowane.

Pytania (np. o ponowne uruchomienie) czekają na Twoją odpowiedź. Jeśli nie odpowiesz na czas, zostanie użyta bezpieczna odpowiedź domyślna. Hasło administratora wpisujesz w terminalu. Nie jest zapisywane ani pokazywane.

Ekran wyniku pokazuje:

- **Zaktualizowane**: teraz aktualne.
- **Aktualne**: nic nie było do zrobienia.
- **Wymaga Ciebie**: patrz niżej.

## Jak aktualizowane są aplikacje z internetu

- Aplikacje ze zweryfikowanym pobraniem od producenta (na przykład Claude i Antigravity IDE) są instalowane bezpośrednio, zamiast być otwierane i oczekiwane. Gdy pobranie się nie powiedzie, nadal działa własny updater aplikacji.
- Aplikacja otwarta, aby sama się zaktualizowała, jest zamykana, gdy tylko jej aktualizacja zostanie przygotowana (Warp), zamiast czekać pełny czas.
- Chrome podczas stopniowego wdrażania jest raportowany od razu, gdy updater Google odpowiedział już „brak aktualizacji” dla Twojej wersji.
- Aplikacje Google (Gemini, Chrome, Google Drive) pokazują, kiedy updater Google ostatnio sprawdzał i kiedy sprawdzi ponownie, albo że aplikacja zaktualizowała się sama.
- Aplikacja z Homebrew, która była otwarta i już sama się zaktualizowała, jest raportowana jako aktualna, bez ostrzeżenia.
- Gdy macOS blokuje aplikację w sekcji **Rzeczy otwierane podczas logowania i rozszerzenia** (zamyka się zaraz po otwarciu), wynik mówi o tym i wskazuje, gdzie ją zezwolić: Ustawienia systemowe › Ogólne › Rzeczy otwierane podczas logowania i rozszerzenia.

## Ustawienia dla pojedynczej aplikacji

Otwórz kartę **Aplikacje**. Klawisz `/` pozwala szukać po nazwie lub źródle. Enter na aplikacji otwiera wybór. Spacja zaznacza kilka aplikacji, żeby zmienić je razem.

| Tryb | Znaczenie |
|------|-----------|
| **automatycznie** | Program sam ją aktualizuje. To ustawienie domyślne. |
| **ręcznie** | Program tylko informuje, że czeka aktualizacja. |
| **pomiń** | Program jej nie dotyka. |

Jeśli aplikacja ma kilka źródeł, możesz też wybrać **preferowane źródło**: źródło domyślne, Homebrew, App Store, strona producenta lub wbudowany aktualizator. Kolumna **Metoda** pokazuje, skąd program zna aplikację: sprawdzona (jest na liście przetestowanej w programie), wykryta (rozpoznana po potwierdzeniu z App Store, Homebrew, kanale aktualizacji lub wbudowanym aktualizatorze) albo ręczna (nic nie rozpoznano). Ustawienie „Nowo znalezione aplikacje” decyduje, co dzieje się z aplikacjami znalezionymi przy skanowaniu, których nie ma na liście sprawdzonych: według pewności (automatycznie, gdy sposób aktualizacji jest jasny, w przeciwnym razie ręcznie), zawsze automatycznie albo zawsze ręcznie.

Jeśli lista jest pusta, wybierz **Skanuj teraz**. Skanowanie tylko odczytuje dane z Maca.

Wybory zapisują się w pliku `~/.config/mac-update/overrides.tsv`, po jednym wierszu na aplikację: grupa, nazwa, tryb, źródło (rozdzielone tabulatorami). Usuń plik, a każda aplikacja wróci do trybu automatycznego.

## Ustawienia

Na początek wybierz profil: **W pełni automatyczny** (wszystko), **Ostrożny** (bez aktualizacji macOS i dużych skoków wersji), **Tylko sprawdzanie** (nic się nie instaluje). Każda ręczna zmiana pokazuje profil **Własny**.

| Sekcja | Pozycje |
|--------|---------|
| Co aktualizować | Przełącznik dla każdej grupy; Tylko sprawdzaj, nie instaluj; Zezwalaj na duże aktualizacje (wyłączone zostawia bieżącą wersję główną); Aktualizacje macOS: instaluj, tylko powiadamiaj albo wyłączone (o ponowne uruchomienie program zawsze pyta) |
| Aplikacje i źródła | Nowo znalezione aplikacje (według pewności, automatycznie, ręcznie); Tryb i źródło dla aplikacji (otwiera kartę Aplikacje); Wykluczone aplikacje (`config/inventory_exclusions.txt`); Śledzone narzędzia npm (`config/npm_global_clis.txt`) |
| Uruchamianie automatyczne | Codzienna automatyzacja (domyślnie wyłączona, bez ustawionej pory): kiedy się uruchamia (codziennie o wybranej godzinie, po zalogowaniu albo jedno i drugie) oraz powiadomienie po uruchomieniu (po każdym uruchomieniu, tylko gdy coś wymaga mojej uwagi, nigdy); Uruchom test teraz |
| Zabezpieczenia | Czekanie na zamknięcie aplikacji (s); Pobieranie ze stron producentów; Minimum wolnego miejsca (GB, domyślnie 15); Minimalny poziom baterii (%, domyślnie 30) |
| Sieć i szybkość | Ważność sprawdzenia wersji (godz.); Czas na odpowiedź (s, domyślnie 120); Limit czasu App Store (s) |
| Powiadomienia i raporty | Powiadomienie po zakończeniu; Otwórz ostatni dziennik; Liczba przechowywanych dzienników (domyślnie 30) |
| Język i wygląd | Język (English, Polski, Deutsch, Español, Français, Italiano, Português); Kolory; Kolor wyróżnienia (domyślnie niebieski, fioletowy, bursztynowy, szałwiowy, różowy, grafitowy); Odstępy; Proste znaki; Dopasuj rozmiar okna automatycznie; Mysz; Panel pomocy na starcie |
| System i konserwacja | Opóźnienie Microsoft Office (dni); Nie usypiaj Maca; Odśwież spis aplikacji; Zaktualizuj ten program; Eksportuj ustawienia; Importuj ustawienia; Przywróć domyślne |

Ustawienia zapisują się w pliku `~/.local/state/mac-update/tui-settings.json`, a Twój język w `~/.config/mac-update/lang`. Pozycja ustawiona zmienną środowiskową pokazuje tę zmienną i nie da się jej zmienić w oknie. „Czekanie na zamknięcie aplikacji” dotyczy aplikacji uruchomionych przez sam program.

Kolory podążają za terminalem. Domyślne ustawienie, **automatyczne**, pyta terminal, czy jego okno jest jasne, czy ciemne, i używa pasującego motywu. Jasny wygląd zostawia stronie własne białe tło i kolor tekstu terminala, a tylko górny pasek, pasek klawiszy, zaznaczony wiersz i okna dialogowe mają jasnoszary kolor; każdy kolor pozostaje czytelny na białym oknie. Ciemny motyw się nie zmienił. „Ciemne” zapisane przez wcześniejszą wersję jest raz traktowane jak automatyczne; jeśli chcesz mieć zawsze ciemne, wybierz je ponownie w Ustawieniach, Język i wygląd, Kolory.

## Co znaczy „Wymaga Ciebie”

Każda pozycja na ekranie wyniku ma powód i podpowiedź, co zrobić.

| Powód | Co zrobić |
|-------|-----------|
| **Aplikacja jest otwarta** | Zamknij aplikację i uruchom aktualizację ponownie. Program nigdy nie zamyka jej za Ciebie. |
| **Wymagane logowanie** (App Store) | Otwórz App Store, zaloguj się i uruchom aktualizację ponownie. |
| **Potrzebne hasło** | Uruchom aktualizację ponownie w terminalu i wpisz hasło administratora, gdy pojawi się prośba. Uruchomienia automatyczne nie mogą pytać, więc tylko to zgłaszają. |
| **Potrzebne ponowne uruchomienie** | Aktualizacja jest zainstalowana, ale zadziała po restarcie. Uruchom Maca ponownie, kiedy Ci pasuje. |
| **Brak automatycznej metody** | Nie ma bezpiecznego sposobu, by zaktualizować tę aplikację automatycznie. Otwórz aplikację i użyj jej opcji „Sprawdź uaktualnienia”. |
| **Pobieranie się nie udało** | Sprawdź połączenie z internetem i uruchom aktualizację ponownie. |
| **Niezgodna suma kontrolna** | Plik nie zgadzał się z sumą kontrolną, więc niczego nie zainstalowano. Spróbuj później. Jeśli to się powtarza, zaktualizuj aplikację ręcznie. |
| **Tryb ręczny** | Ta aplikacja ma tryb ręczny. Zaktualizuj ją sam albo zmień tryb na automatyczny na karcie Aplikacje. |
| **Nie udało się pobrać informacji o aktualizacjach od producenta** | Spróbuj później. Strona producenta może chwilowo nie działać. |
| **Jest nowa wersja główna** | Duże aktualizacje są wyłączone. Zezwól na nie w Ustawieniach albo zaktualizuj ręcznie. |
| **Za mało miejsca na dysku / za słaba bateria** | Zwolnij miejsce albo podłącz zasilacz i uruchom ponownie. |
| **Trwało za długo** | Uruchom ponownie. Jeśli się powtarza, otwórz cały dziennik (`L`). |
| **Otworzył się aktualizator aplikacji** | Dokończ aktualizację w oknie, które otworzyła aplikacja. |

Jeśli powód to „nieznany”, otwórz cały dziennik klawiszem `L`.

Nagłówek, Pulpit i Historia zawsze pokazują te same liczby. Aplikacja na iPada, którą App Store wciąż instaluje po aktualizacji, jest opisana jako „jeszcze się instaluje w App Store”, bez niczego do kliknięcia: poczekaj kilka minut i sprawdź ponownie. Program aktualizujący w tle, który został uruchomiony, ale nie zgłosił wyniku, jest opisany jako „brak zapisanego wyniku, nic do kliknięcia”. Jego wersja jest potem odczytywana ponownie, więc zakończona aktualizacja pokazuje się jako zaktualizowana.

## Gdzie co jest

| Co | Gdzie |
|----|-------|
| Dzienniki uruchomień (przechowywane najnowsze 30) | `~/.local/state/mac-update/logs/` |
| Twoje wybory dla aplikacji, język i spis Twoich aplikacji | `~/.config/mac-update/` (`overrides.tsv`, `lang`, `reports/`) |
| Program | `~/.local/share/mac-update/` |

Opcje, zmienne środowiskowe i rozwiązywanie problemów: [OPERATIONS.md](OPERATIONS.md). Instalacja, aktualizacja i usuwanie: [INSTALL.md](../../INSTALL.md) i [UNINSTALL.md](../../UNINSTALL.md).
