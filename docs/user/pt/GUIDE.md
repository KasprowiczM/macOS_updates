# Guia do utilizador (Português)

**Versão:** 1.0.19 · **Apenas Apple Silicon**

## O que faz

macOS Updates automatiza atualizações em **Macs Apple Silicon**:

1. Sistema macOS (`softwareupdate -ia -R`)
2. App Store (`sudo mas upgrade` + GUI para apps iPad)
3. Node/Bun e CLIs npm globais
4. Homebrew
5. 40+ apps da Internet — **apenas se instaladas**
6. Catálogo `APPLICATIONS.md` e histórico `UPDATES.md`

**Não instala novas aplicações.** Cada Mac constrói o seu inventário (`build_inventory.sh`).

## Instalação

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Relatório de cobertura

```bash
bash scripts/report_update_coverage.sh
```

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
