# Przewodnik użytkownika (Polski)

**Wersja:** 1.4.1 · **Apple Silicon, macOS 13+**

## Co robi ten zestaw

macOS Updates koordynuje aktualizacje na **Macach Apple Silicon z macOS 13+** w kolejności:

1. Prescan i inwentarz tego Maca
2. App Store (`sudo mas upgrade` + osobny GUI Track 2 dla aplikacji iPad)
3. Node/Bun i globalne CLI npm
4. Homebrew (formuły i caski `--greedy`)
5. Zainstalowane aplikacje internetowe: bezpośrednie handlery, CLI lub wyzwalanie aktualizatora
6. Atomowy postupdate inwentarza i historii
7. macOS (`softwareupdate -ia -R`) na końcu; pomijany po wcześniejszym błędzie

**Nie instaluje nowych aplikacji.** Każdy Mac buduje własny katalog (`build_inventory.sh` lub prescan w `update_all.sh`).

## Instalacja

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Raport pokrycia

```bash
bash scripts/report_update_coverage.sh
```

Pokazuje stany: **verified direct**, **triggered-unverified**, **externally managed**, **manual** i **unknown**. Ciche uruchomienie nie jest dowodem zakończonej aktualizacji. Inkscape obsługuje Homebrew; UniFi/WiFiman/Picsart — App Store Track 2; Office — `msupdate`; Teams — własny updater z obserwowanym, weryfikowanym fallbackiem MAU `TEAMS21`. Ręczne są tylko IPMIView i DJI Assistant 2.

## Dodawanie aplikacji z internetu

1. Zainstaluj aplikację na Macu.
2. `bash build_inventory.sh`
3. `bash scripts/scaffold_internet_app.sh "Nazwa" silent_launch`
4. `bash run_tests.sh`

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---------|-------------|
| Intel Mac | Nieobsługiwany |
| Zły katalog aplikacji | `bash build_inventory.sh` |
| Brak aktualizacji aplikacji | `bash scripts/report_update_coverage.sh` |
| Brak `APPLICATIONS.md` | `build_inventory.sh` lub `dev_sync/dev-sync-import.sh` (właściciel) |

Pełna lista: [../../agents/troubleshooting.md](../../agents/troubleshooting.md)
