# Guia do utilizador (Português)

**Versão:** 1.4.1 · **Apple Silicon, macOS 13+**

## O que faz

macOS Updates orquestra atualizações em **Macs Apple Silicon com macOS 13+**:

1. Pré-análise e inventário
2. App Store (`sudo mas upgrade` + Track 2 GUI separado)
3. Node/Bun e CLIs npm globais
4. Homebrew (`--greedy`)
5. Apps instaladas: handlers diretos, CLI ou acionadores integrados
6. Pós-atualização atómica do inventário/histórico
7. macOS (`softwareupdate -ia -R`) por último; ignorado após erro anterior

**Não instala novas aplicações.** Cada Mac constrói o seu inventário (`build_inventory.sh`).

## Instalação

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Relatório de cobertura

```bash
bash scripts/report_update_coverage.sh
```

Estados: **verified direct**, **triggered-unverified**, **externally managed**, **manual**, **unknown**. Um arranque silencioso não prova a atualização. Inkscape usa Homebrew; UniFi/WiFiman/Picsart Track 2; Office `msupdate`; Teams o próprio updater com fallback MAU `TEAMS21` observado e verificado. Só IPMIView e DJI Assistant 2 permanecem manuais.

## Adicionar app da Internet

1. Instalar a app no Mac.
2. `bash build_inventory.sh`
3. `bash scripts/scaffold_internet_app.sh "Nome" silent_launch`
4. `bash run_tests.sh`

## Resolução de problemas

| Problema | Solução |
|----------|---------|
| Mac Intel | Não suportado |
| Catálogo errado | `bash build_inventory.sh` |
| App não atualiza | `bash scripts/report_update_coverage.sh` |
| Falta `APPLICATIONS.md` | `build_inventory.sh` ou `dev_sync/dev-sync-import.sh` |

Completo: [../../agents/troubleshooting.md](../../agents/troubleshooting.md)
