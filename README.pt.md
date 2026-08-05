# Atualizações macOS

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

> **v1.2.0** — Orquestrador de atualizações de um comando pronto para produção para **Macs com Apple Silicon e macOS 13+**. Coordena atualizações verificadas para software instalado. **Multilíngue** (7 idiomas). Camada de nuvem privada opcional via [`dev_sync/`](dev_sync/README.md).

**Repositório público:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · Lançamento: [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md)

---

## Instalação em uma linha (novos usuários)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

O instalador clona o repositório, solicita a seleção do **idioma** (português disponível), instala as dependências, cria **seu** arquivo `APPLICATIONS.md` com base nos aplicativos já presentes no seu Mac e mostra quais aplicativos podem ser atualizados. Ele nunca importa o inventário de outro usuário nem instala novos aplicativos para você.

Veja [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## O que esta ferramenta faz

`update_all.sh` executa sete etapas:

| Etapa | Ação |
|------|--------|
| 0 | **Pré-análise** — detecta apps instalados → atualiza `APPLICATIONS.md` |
| 1 | **App Store** — Track 1: `sudo mas upgrade`; Track 2: GUI AppleScript para apps iPad |
| 2 | **CLI Nativos + npm** — Node, Bun, ferramentas globais npm |
| 3 | **Homebrew** — fórmulas e casks (`--greedy`) + limpeza |
| 4 | **Apps da Internet** — handlers verificados, CLI do fornecedor e acionamentos honestos |
| 5 | **Pós-atualização/histórico** — inventário e histórico atômicos |
| 6 | **macOS (por último)** — `softwareupdate -ia -R`; ignorado se uma etapa anterior falhar |

**Importante:** As atualizações afetam apenas os softwares já instalados no seu Mac. Aplicativos suportados, mas ausentes, são relatados, não instalados.

A cobertura distingue **verified direct**, **triggered-unverified**, **externally managed**, **manual** e **unknown**; iniciar um app não confirma a atualização. Inkscape usa Homebrew Cask; UniFi, WiFiman e Picsart App Store Track 2; Office usa `msupdate`; Teams usa o próprio updater com fallback MAU `TEAMS21` observado e verificado quando a Microsoft o oferece. Só IPMIView e DJI Assistant 2 permanecem manuais.

```bash
bash scripts/report_update_coverage.sh   # relatório de cobertura
bash build_inventory.sh                  # reconstruir APPLICATIONS.md
```

---

## Início rápido

### Novo usuário (sem nuvem)

```bash
# Opção A — linha única (recomendado)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"

# Opção B — manual
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh
bash build_inventory.sh
bash update_all.sh
```

### Proprietário (GitHub + nuvem)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

---

## Documentação

| Público | Comece aqui |
|----------|------------|
| Usuários | [docs/user/pt/QUICK_START.md](docs/user/pt/QUICK_START.md) |
| Instalação / Desinstalação | [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md) |
| Desenvolvedores | [docs/agents/scripts.md](docs/agents/scripts.md) |
| Sincronização em nuvem | [dev_sync/README.md](dev_sync/README.md) |
| Contexto IA | `AGENTS.md` |

---

## Notas técnicas importantes

- **`softwareupdate` deve usar `-R`** — caso contrário, as atualizações são baixadas, mas nunca aplicadas.
- **`mas upgrade` deve usar `sudo`** no macOS 26.x (CVE-2025-43411).
- **Bash 3.2+** em todo o código — sem `declare -A`, `mapfile` ou `readarray`.
