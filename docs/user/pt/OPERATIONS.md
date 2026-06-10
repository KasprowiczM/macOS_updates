# Manual de operações

Guia para o operador — manutenção diária e semanal do macOS Updates.

## Plataforma

**Apenas Apple Silicon (arm64).** Os scripts terminam imediatamente em Mac Intel.

## Atualização semanal

```bash
cd ~/Dev_Env/macOS_updates
bash update_all.sh
```

Em caso de falha, consulte: `logs/update_all_<timestamp>.log` (últimas 30 execuções conservadas).

## Ordem do pipeline (`update_all.sh`)

| Passo | Script / ação | Flag de ignorar |
|-------|---------------|-----------------|
| 0 | prescan → `APPLICATIONS.md` | `--skip-prescan` |
| 1 | `update_system.sh` | `--skip-system` |
| 2 | `update_appstore.sh` | `--skip-appstore` |
| 3 | `update_npm_cli.sh` | `--skip-npm` |
| 4 | `update_brew.sh` | `--skip-brew` |
| 5 | `update_internet_apps.sh` | `--skip-internet` |
| 6 | postupdate → `APPLICATIONS.md`, `UPDATES.md` | `--skip-postupdate` |

Pré-visualização sem alterações: `bash update_all.sh --dry-run -y`

## Análise de falhas

| Passo falhado | Ficheiros a verificar |
|---------------|----------------------|
| App Store | `$SESSION_DIR/appstore_diag.txt`, instantâneo do registo |
| Apps da Internet | `$SESSION_DIR/internet_diag.txt`, `internet_before/after.txt` |
| Homebrew | `$SESSION_DIR/brew_*_before/after.txt` |
| Qualquer | `logs/update_all_*.log` (instantâneos anexados com código de saída ≠ 0) |

Acessibilidade da App Store em falta → código de saída `2`; use `--treat-appstore-ax-as-warning` ou conceda Acessibilidade ao terminal.

Referência completa de códigos de saída: `docs/agents/exit_codes.md`.

## Overlay privado (Proton Drive)

Após editar ficheiros privados localmente:

```bash
bash dev_sync/dev-sync-export.sh
bash dev_sync/dev-sync-verify-full.sh
bash dev_sync/dev-sync-prune-excluded.sh   # should report zero candidates
```

## Mac novo

**Utilizador público:**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
bash update_all.sh
```

**Proprietário (overlay na nuvem):**

```bash
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

Inventário: `bash build_inventory.sh`

## Lista de verificação pré-atualização

- [ ] Sessão iniciada na App Store (`mas account` ou app App Store)
- [ ] Terminal com Acessibilidade (para a via 2 de apps iPad)
- [ ] Espaço em disco ≥ 20 GB para atualizações grandes do macOS
- [ ] `sudo` disponível para `mas upgrade` e atualizações do sistema

## Verificação pós-atualização

```bash
mas outdated
brew outdated
softwareupdate -l
```

Lance uma amostra de apps críticas (navegador, VPN, IDE) se o passo Internet reportou avisos.
