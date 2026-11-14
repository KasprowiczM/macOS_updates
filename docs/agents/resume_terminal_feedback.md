# Prompt wznowieniowy: test interfejsu i automatyzacji 1.8.2

Skopiuj poniższy tekst do nowej sesji i dopisz uwagi z testu.

---

Pracujemy nad macOS Updates w trybie orkiestra. Odczytaj aktualny kontekst projektu, najnowszy handoff oraz instrukcje AGENTS.md. Zweryfikuj właściwy checkout i jego stan Git przed edycją. Sprawdź bieżący stan `main`, ostatni tag i rzeczywistą wersję źródeł; nie zakładaj, że wersja źródeł jest otagowanym wydaniem. Nie nadpisuj pracy innych sesji ani lokalnych ustawień.

Sprawdź najnowsze logi i podsumowanie przebiegu w publicznym checkoutcie oraz moje uwagi poniżej. Nie uruchamiaj prawdziwych aktualizacji, instalacji, restartów ani sterowania aplikacjami na moim Macu. Testy wykonuj przez izolowany `run_tests.sh`, fixture i PTY. Nie publikuj zmian ani landing page bez osobnego polecenia.

Punktem odniesienia są:

- `docs/superpowers/specs/2026-11-14-terminal-usability-design.md`
- `docs/superpowers/plans/2026-11-14-terminal-usability.md`
- `docs/implementation/AUTOMATIC_WORKFLOW_1.8.2.md`
- `docs/user/pl/GUIDE.md`

Cel: intuicyjny interfejs terminalowy inspirowany btop, z widocznym fokusem, Tab i strzałkami, polami zaznaczanymi Spacją, przyciskami uruchamianymi Enterem, stałą nawigacją i pomocą kontekstową. Prawy sidebar ma pokazywać pomoc dla każdego ekranu, także w wąskim terminalu. CLI ma pokazywać rzeczywistą aktywność grup i wyniki. Po dry-run pozostaje pełna tabela aplikacji. Przebieg aktualizacji aktualizuje te same wiersze: kolejka, aktywność, czas, wynik i szczegóły. Nie wymyślaj procentów ani sukcesu na podstawie samego uruchomienia procesu. Sprawdź wszystkie przyciski, także pusty inwentarz, zapis wykluczeń, zgody, odpowiedzi, anulowanie, mały terminal i siedem języków.

W 1.8.2 dodano zapisywaną zgodę na obsługiwane aktualizacje już zainstalowanych aplikacji z obecnego źródła. Jawny wybór w setupie lub wpisanie ENABLE zapisuje zgodę; wykluczenia, wybory ręczne, konflikty i ochrona aplikacji nadal obowiązują. Bez zapisanej zgody można osobno zatwierdzić grupę przez AUTO. Tryb grupowy obejmuje równoległe okna aplikacji natywnych i nadzorowane starsze mechanizmy pobierania. Office otrzymuje tylko wybrane identyfikatory produktów, bez zamykania aplikacji i zmieniania preferencji. Google wymaga jawnej zgody na wszystkie produkty zarejestrowane w aktualizatorze, również spoza katalogu, których pełna lista jest nieznana. Istniejące zgody na jedną aplikację nie są cicho rozszerzane. Podpis, tożsamość i źródło są sprawdzane ponownie. DeepSeek pozostaje ręczny. Open Design nie ma obecnie zaimplementowanego działającego automatycznego pobrania i zgłasza ten brak zamiast pozorować sukces.

Wspólna rezerwacja całej grupy pozwala aplikacjom internetowym działać równolegle, ale chroni je przed kolizją z innymi menedżerami i aktualizacją systemu. Menedżery mają osobne blokady, Office i Google są grupowane. Niepotwierdzona praca zachowuje rezerwację; odzyskanie wymaga potwierdzenia całej grupy i świeżej weryfikacji wszystkich członków. Nie usuwaj dzienników ani blokad. Zmiana wersji w obserwacji nie dowodzi latest stable ani zakończenia wszystkich pomocników. Testy fixture nie są rzeczywistą akceptacją produktu. Polecenie bez interfejsu: `bash update_all.sh --cli --automatic-internet-batch`; podgląd dodaje `--dry-run`.

Sprawdź także aktualizowanie samego narzędzia: podgląd konkretnej rewizji, potwierdzenie po zamknięciu interfejsu, ochrona zmienionego kodu i plików użytkownika, odzyskiwanie po niepewnym wyniku Git. Aplikacja nigdy nie wysyła zmian użytkownika do repozytorium autora. Ponowne uruchomienie instalatora zachowuje istniejący checkout.

Napraw odtworzone błędy, przeprowadź odpowiednie testy i zaktualizuj dokumentację we wszystkich językach. Raportuj osobno: co działa na fixture, co zostało potwierdzone przez użytkowników i co nadal jest niezweryfikowane. Na końcu podaj krótkie komendy do mojego testu oraz zapisz handoff. Nie przedstawiaj częściowej obsługi jako pełnej automatyzacji całego katalogu.

Moje uwagi i wyniki testu:

[Tutaj wkleję obserwacje, komunikaty i informacje o przebiegu.]
