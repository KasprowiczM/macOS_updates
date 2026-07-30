# Início rápido (Português)

**Mac com Apple Silicon obrigatório** · macOS 13+ · **v1.0.21**

## Instalação numa linha

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Novo utilizador (apenas GitHub)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh
bash build_inventory.sh
bash update_all.sh
```

`setup.sh` instala Homebrew, `mas` e Python se estiverem em falta, e permite escolher o idioma.

## Proprietário (GitHub + overlay Proton Drive)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

Os ficheiros privados (`APPLICATIONS.md`, `UPDATES.md`, `.env`) vêm do overlay na nuvem — não do GitHub.

## Comandos úteis

| Comando | Finalidade |
|---------|------------|
| `bash update_all.sh --dry-run -y` | Pré-visualizar todos os passos |
| `bash update_system.sh` | Apenas macOS |
| `bash update_appstore.sh` | Apenas App Store |
| `bash update_brew.sh` | Apenas Homebrew |
| `bash run_tests.sh` | Verificar a instalação |

Consulte [GUIDE.md](GUIDE.md) e [OPERATIONS.md](OPERATIONS.md).
