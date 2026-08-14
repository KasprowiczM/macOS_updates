# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

> **v1.4.0** — Orquestrador de atualizações num único comando pronto para produção em **Macs Apple Silicon com macOS 13–26**. Coordena atualizações verificadas para programas já instalados neste Mac. **Multilíngue** (7 idiomas). Camada privada opcional na nuvem via [`dev_sync/`](dev_sync/README.md).

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

## Configuração por máquina (**não** chega com `git pull`)

Dois elementos vivem fora do repositório e por isso têm de ser configurados uma vez **em cada
Mac**. Clonar ou fazer pull numa segunda máquina não os transfere — é a confusão mais comum
neste projeto.

| Passo | Comando | Porque não pode estar no Git |
|-------|---------|------------------------------|
| Touch ID para `sudo` | `bash scripts/setup_touchid_sudo.sh` | Escreve `/etc/pam.d/sudo_local` — ficheiro pertencente ao root, local à máquina |
| Execução semanal em segundo plano | `bash scripts/install_launchagent.sh --day 1 --hour 9` | Escreve `~/Library/LaunchAgents/…plist` — por utilizador e máquina |

`setup_touchid_sudo.sh` nunca toca em `/etc/sudoers` nem concede `sudo` sem palavra-passe.

**A execução agendada não instala atualizações do macOS nem da App Store.** Ambas exigem
autenticação do utilizador — em Apple Silicon o `softwareupdate` exige credenciais de
proprietário do volume. Execute `bash update_all.sh` de forma interativa para as aplicar.

**Contrato do sudo (v1.4.0):** no máximo um pedido por execução; **nunca** sem um TTY de
controlo (é exportada `MAC_UPDATE_NO_SUDO=1` em vez disso); nunca com `--dry-run`.

---

## Funcionalidades e variáveis de ambiente na v1.4.0

- **Pré-autorização Sudo / Touch ID**: Deteta `pam_tid.so` e mantém a sessão sudo ativa.
- **Suporte LaunchAgent e Execução em Segundo Plano**: Suporta `MAC_UPDATE_NO_SUDO=1` para execuções não supervisionadas.
- **`vendor_latest` e proteção contra downgrades**: Evita downgrades de Casks Homebrew para aplicações com atualização rápida.
- **Variáveis de controlo**:
  - `MAC_UPDATE_YES=1` (`-y`) — Confirmação não interativa de todos os passos.
  - `MAC_UPDATE_SKIP_SYSTEM=1` (`--skip-system`) — Omite as atualizações do sistema macOS.
  - `MAC_UPDATE_VERIFY_ONLY=1` (`--verify-only`) — Verifica as versões instaladas contra o histórico sem alterações.
  - `MAC_UPDATE_NONINTERACTIVE=1` — Suprime diálogos interativos.
  - `MAC_UPDATE_MAU_CLEAR_DEFERRALS=1` — Remove as chaves de adiamento bloqueadoras do MAU.

```bash
# Exemplo de verificação de versões sem atualizar:
bash update_all.sh --verify-only

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
