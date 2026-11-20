# Szybki start (polski)

**Aktualizacje macOS 2.0.10** · Mac z Apple Silicon · macOS 13 lub nowszy · około 5 minut

Program dba o to, żeby oprogramowanie, które już masz na Macu, było aktualne: aplikacje z App Store, narzędzia terminala, pakiety Homebrew, aplikacje pobrane z internetu i sam macOS. Nie instaluje niczego, czego nie masz.

## 1. Instalacja

Wklej w Terminalu:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/KasprowiczM/macOS_updates/releases/latest/download/install.sh)"
```

Instalator pobiera wydanie, sprawdza jego sumę kontrolną i dodaje polecenie `mac-update`. Niczego nie aktualizuje i nie potrzebuje `git` ani `sudo`. Potrzebujesz Pythona 3.9 lub nowszego (jeśli go brakuje, instalator podpowie, żeby uruchomić `xcode-select --install`). Szczegóły: [INSTALL.md](../../INSTALL.md).

Potem otwórz nowe okno terminala, żeby polecenie zostało znalezione. Jeśli `mac-update` nadal nie jest znalezione, uruchom instalator ponownie, dodając po znaku potoku `bash -s -- --configure-shell`, jak opisano w INSTALL.md.

## 2. Podgląd

```bash
mac-update
```

W terminalu otworzy się interfejs na ekranie **Pulpit**. Strzałką w prawo przejdź do **Podgląd (bez zmian)** i naciśnij Enter. Nic się nie zainstaluje, zobaczysz tylko, co zostałoby zaktualizowane.

Wolisz zwykły tekst? Uruchom `mac-update preview`. `mac-update --cli` (także `--plain`) robi to samo co `mac-update run`, `mac-update --tui` otwiera interfejs jak samo `mac-update`, a `macos-update` to to samo polecenie pod dłuższą nazwą. Wszystkie działają z dowolnego folderu.

## 3. Aktualizacja

Na Pulpicie wybierz **Aktualizuj wszystko** i naciśnij Enter. Zobaczysz kolejne grupy (App Store, Narzędzia terminala, Homebrew, Aplikacje z internetu, Spis aplikacji, System macOS) i każdą aplikację w trakcie aktualizacji. Jeśli macOS poprosi o hasło, wpisz je w terminalu. Program go nie zapisuje.

W każdej chwili możesz przerwać. Aplikacje, które już się zaktualizowały, zostają zaktualizowane.

## 4. Przeczytaj wynik

Ekran wyniku ma trzy listy:

- **Zaktualizowane**: te aplikacje są już aktualne.
- **Aktualne**: nic nie było do zrobienia.
- **Wymaga Ciebie**: program nie mógł dokończyć tego sam. Przy każdej pozycji jest powód i podpowiedź, co zrobić. Najczęstsze powody: aplikacja była otwarta, App Store wymaga zalogowania albo trzeba uruchomić Maca ponownie. Zobacz [przewodnik](GUIDE.md).

Otwartych aplikacji program nigdy nie zamyka. Zamknij je i uruchom aktualizację jeszcze raz.

## 5. Co dalej

| Chcę... | Zrób to |
|---------|---------|
| Zmienić sposób aktualizacji jednej aplikacji | Karta Aplikacje, Enter na aplikacji: automatycznie, ręcznie lub pomiń |
| Wyłączyć grupę albo aktualizacje macOS | Pulpit: przejdź do grupy, naciśnij spację. Albo Ustawienia, „Aktualizacje macOS” |
| Uruchomić bez interfejsu | `mac-update run` |
| Sprawdzić Maca bez aktualizowania | `mac-update doctor` |
| Uruchamiać automatycznie | Ustawienia, sekcja „Uruchamianie automatyczne”. Zobacz [OPERATIONS.md](OPERATIONS.md) |
| Zobaczyć, co poszło nie tak | Karta Historia, potem Enter na uruchomieniu, żeby otworzyć jego dziennik |
| Przenieść ustawienia ze starszej kopii git | `mac-update migrate` (najpierw pokaże podgląd) |

Więcej: [GUIDE.md](GUIDE.md) · [OPERATIONS.md](OPERATIONS.md) · [UNINSTALL.md](../../UNINSTALL.md)
