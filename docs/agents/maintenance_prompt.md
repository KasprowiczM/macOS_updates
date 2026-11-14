# Uniwersalny prompt pełnego audytu

Prompt dla dowolnego przyszłego modelu i narzędzia. Wklej blok w sesji projektu. Audyt nie jest zgodą na aktualizowanie komputera ani publikację zmian.

```text
Przeprowadź dogłębny, oparty na dowodach ultra-review projektu macOS Updates. Pracuj w trybie orkiestra zgodnie z rzeczywiście dostępnymi modelami i drabiną kosztów. Nie zakładaj nazwy ani możliwości swojego modelu. Dobierz dostępne zaufane skills do audytu, debugowania, bezpieczeństwa, testów i aktualnej dokumentacji. Nie instaluj narzędzi ani skills bez odpowiedniej autoryzacji.

Najpierw załaduj najnowszy kontekst/handoff projektu, przeczytaj AGENTS.md i właściwe dokumenty architektury, bezpieczeństwa oraz kodów wyjścia. Zweryfikuj pamięć względem repozytorium. Ustal właściwy publiczny checkout, stan zmian użytkownika, branch, remote, VERSION, najnowszy tag i wyniki CI. Nie przepisuj historii i nie nadpisuj cudzej pracy.

Cel: znaleźć rzeczywiste błędy i luki, sprawdzić założenia poprzednich modeli oraz zaproponować uzasadniony rozwój produktu. Nie zakładaj, że wcześniejszy audyt był poprawny albo że nowszy model musi znaleźć więcej błędów.

Jeżeli bieżąca zmiana zawiera terminalowe środowisko (TUI), sprawdź też aplikację terminalową i wersję, rozmiar okna, font, TERM oraz multiplexer. Rozróżnij bare command w interaktywnym TTY od jawnych trybów `--tui` i `--cli`; sprawdź trwałość kreatora i ustawień we wszystkich wspieranych językach. Oceń ograniczenie grup, widoczność operacji i promptów, jawne wklejanie, maskowanie haseł, awaryjne przekazanie aktywnej pracy do trybu tekstowego i przywrócenie poprzedniego rozmiaru. Zmiana rozmiaru jest najlepszą prośbą terminala, a minimum potrzebne do działań zmieniających stan musi być jasne. Nie wykonuj aktualizacji hosta bez świeżego, konkretnego zakresu działań i zgody.

A. Dowody i architektura
- Zmapuj wejścia programu, źródła inventory, resolver, polityki/zgody, plany, acquisition, wykonawców, recovery, scheduler, raporty i instalator.
- Przeczytaj najnowsze realne logi z JSON; odróżnij błędy, odmowy, niepełną obserwację, ostrzeżenia i potwierdzone zmiany. Nie uznawaj samych kodów wyjścia ani historycznych receipt za świeży sukces.
- Sprawdź spójność źródeł, testów, README, siedmiu języków, instrukcji instalacji i landing page. Osobno licz produkty katalogowe, aktywne receptury i operacje zaakceptowane na żywo.

B. Scenariusze i bezpieczeństwo
- Nowy Mac, brak brew/mas/Pythona, standardowy użytkownik, offline/429, locale/Unicode, potoki, brak TTY, ścieżki ze spacjami, wiele checkoutów i niestandardowe katalogi.
- Tożsamość bundle/Team, App Store versus brew/vendor, duplikaty, aplikacje spoza katalogu, stable versus preview, rollout/offered versus listed, wersja/build i minimum OS.
- Zmiana feedu po zgodzie, źródła, artefaktu lub zależności; downgrade; źle podpisany pakiet; ZIP traversal/symlinki; nieznane efekty instalatora; brak automatycznej adopcji, migracji i instalacji nieobecnego celu.
- Otwarte dokumenty, przejęcie aplikacji przez użytkownika, PID reuse, save dialog, helper żywy po wyjściu CLI, timeout/crash/restart, jedyna dobra kopia, odzyskiwanie i wyścigi.
- Globalna kolejka i współdzielone zasoby, anulowanie, świeża zgoda przed mutacją, atomowy zapis inventory oraz uczciwe raporty. Nie pozwól, by blokada uniemożliwiała zebranie dowodu potrzebnego do jej zwolnienia.

C. Weryfikacja
- Używaj aktualnej oficjalnej dokumentacji producentów/managerów/frameworków; odnotuj datę i rozróżnij publiczny kontrakt od hipotezy.
- Odtwarzaj defekty na izolowanych fixture z guard runnerem. Dodawaj testy rzeczywistych granic, nie testy kopiujące implementację. Pełny zestaw uruchom po integracji; nie powtarzaj kosztownych kontroli bez powodu.
- Nie wykonuj prawdziwych aktualizacji, instalacji, sudo, mount, launch/quit ani restartu na Macu właściciela. T6/live testy wymagają osobnego, wskazanego środowiska i zakresu. Nie fabrykuj live acceptance i nie aktywuj nieprzetestowanych receptur. Feedback jest wskazówką, nie automatycznym dowodem.

D. Wynik i rozwój
- Każde ustalenie: priorytet P0-P3, konkretny scenariusz, plik/linia, dowód, wpływ, proponowana poprawka i test. Oddziel potwierdzone defekty, wnioski z kodu i hipotezy. Nie produkuj ustaleń na siłę.
- Zaproponuj usprawnienia wydajności, UX, niezawodności i obsługi nowych aplikacji. Dla każdej idei podaj wartość dla użytkownika, koszt, ryzyko, zależności i mierzalne kryterium sukcesu. Bez obietnic szybkości opartych na pojedynczym przebiegu.
- Przygotuj plan etapami w Markdown: szybkie naprawy, istotne zmiany, eksperymenty i tematy odłożone. Wyraźnie wskaż decyzje właściciela i brakujące dowody.
- Domyślnie wykonaj audyt i przygotuj plan. Implementację, publikację, merge, tag i deploy wykonuj w zakresie udzielonej zgody, nie dlatego, że wspomina o nich ten prompt. Aktualizuj bieżącą dokumentację razem ze zmianą; nie zmieniaj historycznych receipt.
- Na końcu podaj wykonane i niewykonane kontrole, ograniczenia, role subagentów oraz własną weryfikację. Zapisz handoff z dokładnymi następnymi krokami. Nie wklejaj prywatnych ścieżek, inventory ani danych kont do publicznego repozytorium.
```
