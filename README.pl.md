# Aktualizacje macOS

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

**Wersja 2.0.10** · Mac z Apple Silicon · macOS 13 lub nowszy · [Strona](https://macos-updates.64bit.site) · [Licencja MIT](LICENSE) · [Zmiany](CHANGELOG.md)

Jedno polecenie, `mac-update`, dba o aktualność oprogramowania na Twoim Macu. Dotyka tylko tego, co jest już zainstalowane.

## Co aktualizuje

Jedno uruchomienie przechodzi po kolei przez te grupy:

1. aplikacje z App Store,
2. narzędzia terminala (npm, bun, narzędzia wiersza poleceń),
3. formuły i aplikacje Homebrew,
4. aplikacje z internetu (z kanału aktualizacji producenta, sprawdzonym bezpośrednim pobraniem albo własnym aktualizatorem aplikacji),
5. spis Twoich aplikacji,
6. macOS, zawsze na końcu.

Nie ma zatwierdzania aplikacja po aplikacji. Jeśli jedna aplikacja ma działać inaczej, ustaw ją na ręcznie albo pomiń na karcie **Aplikacje**. Aktualizacje samego macOS możesz ustawić na instalowanie, tylko powiadamianie albo wyłączone w **Ustawieniach**.

## Instalacja

Wklej w Terminalu:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/KasprowiczM/macOS_updates/releases/latest/download/install.sh)"
```

Instalator pobiera najnowszy pakiet wydania, sprawdza jego sumę kontrolną SHA-256, umieszcza program w `~/.local/share/mac-update` i dodaje polecenie `mac-update` w `~/.local/bin`. Nie potrzebuje `git`, nigdy nie używa `sudo` i przy aktualizacji zachowuje Twoje ustawienia. Żeby najpierw zobaczyć, co zrobi, dodaj `--dry-run`: `... install.sh | bash -s -- --dry-run`. Szczegóły: [docs/INSTALL.md](docs/INSTALL.md) (po angielsku).

Jeśli po instalacji `mac-update` nie jest znalezione, otwórz nowe okno terminala. Jeśli nadal nie, uruchom instalator ponownie z `--configure-shell`.

## Pierwsze uruchomienie

```bash
mac-update
```

W terminalu otworzy się interfejs z kartami: Pulpit, Aplikacje, Katalog, Historia, Ustawienia, Diagnostyka, Pomoc. Wybierz **Podgląd (bez zmian)**, żeby zobaczyć, co by się stało, a potem **Aktualizuj wszystko**. Ekran wyniku pokazuje, co zostało **Zaktualizowane**, co było **Aktualne** i co **Wymaga Ciebie**, z powodem i podpowiedzią przy każdej pozycji.

Zwykły tekst zamiast interfejsu: `mac-update run`. `mac-update --cli` (także `--plain`) robi to samo co `mac-update run`, `mac-update --tui` otwiera interfejs jak samo `mac-update`, a `macos-update` to to samo polecenie pod dłuższą nazwą. Wszystkie działają z dowolnego folderu. Podgląd w tekście: `mac-update preview`. Sprawdzenie Maca bez aktualizowania: `mac-update doctor`. Wszystkie polecenia: `mac-update help`. Czegoś brakuje (Command Line Tools, natywny Homebrew, Python, `mas`)? `mac-update doctor` to wypisze, a `mac-update prepare` zainstaluje po jednym pytaniu.

Masz starszą kopię instalowaną przez git? Uruchom `mac-update migrate`, żeby przenieść ustawienia (najpierw pokaże podgląd).

## Bezpieczeństwo

- Otwartych aplikacji program nigdy nie zamyka. Trafiają do pozycji „Wymaga Ciebie”.
- Pliki są pobierane tylko z dozwolonych serwerów i muszą przejść kontrolę podpisu kodu oraz Gatekeepera.
- Aktualizacja nigdy nie instaluje aplikacji, której nie masz.
- Jedna nieudana pozycja nie zatrzymuje pozostałych, a macOS i tak aktualizuje się na końcu.
- Hasła wpisujesz w terminalu i nigdy nie są zapisywane. Uruchomienie automatyczne nigdy nie zadaje pytań.

## Uruchamianie automatyczne

Domyślnie wyłączone, bez ustawionej pory. Żeby je włączyć, otwórz **Ustawienia**, sekcja **Uruchamianie automatyczne**: wybierz godzinę dnia, „po zalogowaniu” albo jedno i drugie, oraz sposób powiadamiania. Uruchomienie automatyczne pomija aktualizacje macOS, chyba że je włączysz. Zobacz [Obsługa](docs/user/pl/OPERATIONS.md).

## Dokumentacja

| Język | Szybki start | Przewodnik | Obsługa |
|-------|--------------|------------|---------|
| Polski | [Szybki start](docs/user/pl/QUICK_START.md) | [Przewodnik](docs/user/pl/GUIDE.md) | [Obsługa](docs/user/pl/OPERATIONS.md) |

Wszystkie języki: [docs/user/INDEX.md](docs/user/INDEX.md) · [Instalacja](docs/INSTALL.md) · [Usuwanie](docs/UNINSTALL.md)

## Licencja

[MIT](LICENSE)
