# Przewodnik użytkownika (Polski)

**Wersja:** 1.0.18 · **Tylko Apple Silicon**

## Co robi ten zestaw

macOS Updates automatyzuje aktualizacje na **Macach Apple Silicon**:

1. System macOS (`softwareupdate -ia -R`)
2. App Store (`sudo mas upgrade` + GUI dla aplikacji iPad)
3. Node/Bun i globalne CLI npm
4. Homebrew (formuły i caski)
5. 40+ aplikacji z internetu — **tylko jeśli są zainstalowane**
6. Katalog `APPLICATIONS.md` i historia `UPDATES.md`

**Nie instaluje nowych aplikacji.** Każdy Mac buduje własny katalog (`build_inventory.sh` lub prescan w `update_all.sh`).

## Instalacja

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Raport pokrycia

```bash
bash scripts/report_update_coverage.sh
```

Pokazuje: zainstalowane i obsługiwane, obsługiwane ale niezainstalowane, zainstalowane bez handlera (do dodania przez agenta AI).

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
