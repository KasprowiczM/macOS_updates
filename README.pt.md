# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

> **v1.3.0** — Orquestrador de atualizações num único comando pronto para produção em **Macs Apple Silicon com macOS 13–26**. Coordena atualizações verificadas para programas já instalados neste Mac. **Multilíngue** (7 idiomas). Camada privada opcional na nuvem via [`dev_sync/`](dev_sync/README.md).

**Repositório público:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · Release: [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md)

---

## Instalação numa única linha (novos utilizadores)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

O instalador clona o repositório, solicita a **seleção de idioma** (português disponível), instala dependências, gera o seu ficheiro `APPLICATIONS.md` com base nas aplicações presentes no seu Mac e mostra quais as aplicações que podem ser atualizadas.

Consulte [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## O que esta ferramenta faz

O `update_all.sh` executa sete passos:

| Passo | Ação |
|-------|------|
| 0 | **Pré-verificação** — deteta aplicações instaladas → atualiza `APPLICATIONS.md` |
| 1 | **App Store** — Faixa 1: `sudo mas upgrade`; Faixa 2: GUI AppleScript para aplicações iPad |
| 2 | **CLI nativa + npm** — Node, Bun, ferramentas globais npm |
| 3 | **Homebrew** — Fórmulas e Casks (`--greedy-auto-updates`) + proteção contra downgrades |
| 4 | **Aplicações de Internet** — manipuladores verificados, `vendor_latest`, Sparkle Appcast |
| 5 | **Pós-atualização/Histórico** — atualiza inventário e histórico de forma atómica |
| 6 | **macOS (final)** — `softwareupdate -ia -R`; ignorado em caso de erro anterior |

---

## Funcionalidades e variáveis de ambiente na v1.3.0

- **Pré-autorização Sudo / Touch ID**: Deteta `pam_tid.so` e mantém a sessão sudo ativa.
- **Suporte LaunchAgent e Execução em Segundo Plano**: Suporta `MAC_UPDATE_NO_SUDO=1` para execuções não supervisionadas.
- **Método `vendor_latest`**: Evita downgrades de Casks Homebrew para aplicações com atualização rápida (Cursor, Warp, Antigravity, Proton Mail, Proton Drive, Claude, Comet, ChatGPT).
- **Variáveis de controlo**:
  - `MAC_UPDATE_YES=1` (`-y`) — Confirmação não interativa de todos os passos.
  - `MAC_UPDATE_SKIP_SYSTEM=1` (`--skip-system`) — Omite as atualizações do sistema macOS.
  - `MAC_UPDATE_NONINTERACTIVE=1` — Suprime diálogos interativos.

```bash
# Exemplo de execução automatizada em segundo plano:
MAC_UPDATE_NONINTERACTIVE=1 bash update_all.sh -y --skip-system
```

---

## Início rápido

### Novo utilizador (sem nuvem)

```bash
# Opção A — uma linha (recomendado)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"

# Opção B — manual
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh
bash build_inventory.sh
bash update_all.sh
```

---

## Documentação

| Público | Comece aqui |
|---------|-------------|
| Utilizadores | [docs/user/pt/QUICK_START.md](docs/user/pt/QUICK_START.md) |
| Instalação / Desinstalação | [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md) |
| Desenvolvedores | [docs/agents/scripts.md](docs/agents/scripts.md) |
| Sincronização na Nuvem | [dev_sync/README.md](dev_sync/README.md) |
| Contexto IA | `AGENTS.md` |

---

## Notas técnicas críticas

- **`softwareupdate` DEVE usar `-R`** — caso contrário as atualizações são descarregadas mas nunca aplicadas.
- **`mas upgrade` DEVE usar `sudo`** no macOS 14.8+/15.7+/26.x (CVE-2025-43411).
- **Bash 3.2+** em todo o projeto — sem `declare -A`, `mapfile` ou `readarray`.
