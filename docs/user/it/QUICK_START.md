# Avvio rapido (Italiano)

**Richiesto Mac con Apple Silicon** · macOS 13+ · **v1.4.1**

## Installazione con una riga

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Nuovo utente (solo GitHub)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh
bash build_inventory.sh
bash update_all.sh
```

`setup.sh` installa Homebrew, `mas` e Python se mancanti e consente di scegliere la lingua.

## Proprietario (GitHub + overlay Proton Drive)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

I file privati (`APPLICATIONS.md`, `UPDATES.md`, `.env`) provengono dall'overlay cloud — non da GitHub.

## Comandi utili

| Comando | Scopo |
|---------|-------|
| `bash update_all.sh --dry-run -y` | Anteprima di tutti i passaggi |
| `bash update_system.sh` | Solo macOS |
| `bash update_appstore.sh` | Solo App Store |
| `bash update_brew.sh` | Solo Homebrew |
| `bash run_tests.sh` | Verifica dell'installazione |

Vedi [GUIDE.md](GUIDE.md) e [OPERATIONS.md](OPERATIONS.md).
