# Wznowienie po testach użytkowników

Wklej poniższy prompt w nowej sesji otwartej w repozytorium macOS Updates. Dołącz zredagowany feedback lub wskaż lokalne logi. Nie publikuj surowego inventory ani danych kont.

```text
Wznów projekt macOS Updates w trybie orkiestra. Ustal bieżący model i dostępną drabinę kosztów; deleguj niezależne zadania tylko do tańszych modeli. Najpierw załaduj kontekst projektu i najnowszy handoff, następnie sprawdź AGENTS.md, repozytorium, branch, VERSION, tagi, remote i CI. Repozytorium jest źródłem prawdy. Nie zakładaj, że katalog roboczy to aktualna publiczna kopia.

Cel: przeanalizuj feedback użytkowników po poprawce dry-run 1.7.7, odtwórz zgłoszone problemy, napraw potwierdzone błędy i oceń gotowość dalszych receptur. Nie przyjmuj, że wersja 1.7.7 jest nadal najnowsza.

1. Zidentyfikuj wersję/commit, macOS/architekturę, język/locale, terminal, dokładną komendę i sposób uruchomienia każdego zgłoszenia. Oddziel błędne znaki, pełny JSON, traceback, przerwanie przez potok i rzeczywistą awarię procesu.
2. Znajdź najnowszy rzeczywisty log update_all oraz jego JSON. Odróżnij dry_run i inventory_only; porównaj kilka poprzednich przebiegów. Zestaw aktualizacje potwierdzone, działania odroczone, niepełne skany i nierozstrzygnięte sesje. Kod wyjścia zero nie oznacza, że aplikacje zostały zaktualizowane.
3. Sprawdź zwykły --dry-run, --plan oraz --dry-run --json-summary na hermetycznych fixture. Zwykły podgląd ma być czytelny i ograniczony, JSON kompletny; oba mają wynikać z tego samego planu. Zweryfikuj brak zapisu inventory, zgód i stanu uruchomienia, Unicode, siedem języków, Bash 3.2, Python 3.9+, brak TTY i zamknięty potok.
4. Dla każdego błędu przygotuj minimalną reprodukcję i test regresji, popraw przyczynę, wykonaj właściwe testy przez run_tests.sh z blokadami hosta/sieci. Nie obchodź zabezpieczeń, by test przeszedł.
5. Zweryfikuj receptury i trwałe blokady: dokładny kandydat, podpis, wersja/build, źródło, App Store receipt, osobna zgoda na instalację oraz lifecycle, brak adopcji/migracji i ochrona otwartych aplikacji. Nie usuwaj journal ani lease, żeby odblokować przebieg bez dowodu zakończenia.
6. Feedback użytkowników traktuj jako niezweryfikowany materiał diagnostyczny. Nie zamieniaj go automatycznie w live-passed. T6 jest odroczone; nie wykonuj aktualizacji, instalacji, restartu, quit ani launch na Macu właściciela. DeepSeek pozostaje wyłączony do stable. Aktywuj T7 tylko dla konkretnych operacji/receptur z rzeczywistymi wymaganymi dowodami i zgodą.
7. Zaktualizuj dokumentację, changelog i wersję odpowiednio do zakresu. Landing synchronizuj wyłącznie z potwierdzonym stanem, osobno pokazując wersję źródeł i tag. Sprawdź komendy instalacji, linki i zgodność EN/PL.
8. Zakończ raportem potwierdzone/przypuszczalne/niezweryfikowane, wynikami testów i konkretnymi dalszymi krokami. Zapisz handoff. Publikację wykonaj tylko wtedy, gdy ta sesja ma na nią zgodę; nie dziedzicz automatycznie jednorazowego polecenia publikacji poprzedniej wersji.
```
