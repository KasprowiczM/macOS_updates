# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

**Site:** [macos-updates.64bit.site](https://macos-updates.64bit.site) · **Repositório:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · **Licença:** [MIT](LICENSE) · **Alterações:** [CHANGELOG.md](CHANGELOG.md)

> **v1.5.5** — Orquestrador de atualizações com um só comando, pronto para produção, para **Macs com Apple Silicon e macOS 13–27**. Coordena atualizações de pacotes verificadas e acionamentos honestos dos atualizadores das aplicações para o **software já instalado neste Mac**. **Multilingue** (7 idiomas). Camada privada opcional através de [`dev_sync/`](dev_sync/README.md).

| Em resumo | |
|-----------|--|
| Plataforma | Apenas Apple Silicon (arm64) · do macOS 13 Ventura ao macOS 27 · Bash 3.2 + Python 3 |
| Fluxo | 7 passos (0–6); a atualização do macOS vem sempre em último |
| Registo | 43 aplicações da Internet · 11 métodos de atualização (ver [Métodos de atualização](#métodos-de-atualização)) |
| Idiomas | EN, PL, ES, FR, DE, IT, PT (CLI e documentação) |
| Testes | 590 testes automáticos (`bash run_tests.sh`) |

**Novidades da v1.5.5:** Uma atualização do Homebrew que remove o `python3` durante a execução já não quebra o passo de inventário/relatório (o shell volta a procurar no `PATH`), e um passo de relatório com falha já não adia as atualizações do macOS. As mensagens finais são honestas: sem a afirmação «ficheiros atualizados» após uma falha, e os avisos de feeds desatualizados ou de aplicações que não fecharam já não são apresentados como atualizações não verificadas. As aplicações iniciadas pela ferramenta recebem pedidos repetidos para fechar (nunca forçados). As versões 1.5.x anteriores (feeds desatualizados como avisos, transferências do fabricante para ChatGPT/Proton, CLIs nativas antes do npm, proteção na substituição de pacotes) estão descritas em [CHANGELOG.md](CHANGELOG.md).

**Verdade do fornecedor (desde a v1.5.0):** a versão de cada aplicação é verificada em relação ao feed do próprio fornecedor antes de qualquer execução. As aplicações atualizadas não são tocadas; as desatualizadas são atualizadas pelo atualizador da própria aplicação ou instaladas a partir do fornecedor com verificação de assinatura e Team ID. Só o software instalado é atualizado (`--bootstrap-cli` instala deliberadamente as CLIs em falta). As aplicações removidas manualmente são detetadas e nunca reinstaladas. **As aplicações que tem abertas nunca são fechadas: a ferramenta só fecha o que ela própria iniciou.** Verifique o estado dos fornecedores em modo só de leitura com `bash scripts/check_vendor_feeds.sh`.

---

## Instalação numa única linha (novos utilizadores)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

O instalador clona o repositório, pede o **idioma** (menu em inglês, 7 idiomas), instala as dependências, cria **o seu** `APPLICATIONS.md` a partir das aplicações já presentes neste Mac e mostra quais o projeto consegue atualizar. Nunca importa o inventário de outra pessoa nem instala aplicações por si.

Consulte [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## O que esta ferramenta faz

`update_all.sh` executa sete passos:

| Passo | Ação |
|-------|------|
| 0 | **Pré-análise** — deteta as aplicações instaladas → atualiza `APPLICATIONS.md` |
| 1 | **App Store** — Via 1: `sudo mas upgrade <app-id>`; Via 2: GUI com AppleScript para aplicações de iPad |
| 2 | **CLI nativas + npm** — primeiro as CLIs nativas existentes, depois Node, Bun e as CLIs npm globais |
| 3 | **Homebrew** — fórmulas e casks (`brew_cask` + proteção contra downgrades) + limpeza e verificação de saúde |
| 4 | **Aplicações da Internet** — manipuladores diretos verificados, `sparkle_appcast`, CLIs de fornecedores e acionamentos honestos dos atualizadores |
| 5 | **Pós-atualização/histórico** — atualiza `APPLICATIONS.md` e acrescenta a `UPDATES.md` de forma atómica |
| 6 | **macOS (final)** — por etiqueta `softwareupdate -i <label> -R` (etiquetas que exigem reinício no último lote); adiado após uma falha grave bloqueante nos passos 1–4 ou sem autorização |

**Importante:** As atualizações só afetam o software já instalado no seu Mac. As aplicações suportadas mas em falta são comunicadas, não instaladas. O passo final do macOS pode reiniciar o Mac, por isso corre em último e mantém o obrigatório `-R`. O passo 5 serve apenas para relatório: uma falha nele é um erro, mas nunca adia o passo do macOS. As aplicações instaladas desconhecidas são listadas para que você (ou um agente de IA) possa acrescentar manipuladores.

A cobertura é deliberadamente explícita: **verified direct** significa que o atualizador confirmou o caminho pacote/versão; **triggered-unverified**, que a aplicação foi iniciada para o seu atualizador atuar sem que a conclusão possa ser provada; **externally managed**, que o fornecedor ou a App Store gere o ciclo de atualização; **manual** exige ação do utilizador; **unknown** não tem método registado.

```bash
bash scripts/report_update_coverage.sh   # relatório de cobertura
bash build_inventory.sh                  # reconstrói APPLICATIONS.md a partir deste Mac
```

### Métodos de atualização

O registo ([`config/internet_apps.txt`](config/internet_apps.txt), [`config/internet_app_methods.txt`](config/internet_app_methods.txt)) associa 43 aplicações a 11 métodos:

| Método | Apps | Cobertura | Como atualiza |
|--------|-----:|-----------|---------------|
| `brew_cask` | 11 | externally managed | Cask do Homebrew (greedy só para estes tokens) com proteção contra downgrades, p. ex. Brave, Obsidian, Spotify, Inkscape |
| `silent_launch` | 9 | triggered-unverified | O atualizador da própria aplicação; verificação oportunista num feed Sparkle / electron-updater, caso contrário «iniciada (não verificada)». Nunca substitui a própria aplicação |
| `github_dmg` | 6 | verified direct | DMG do fornecedor/GitHub com verificação de assinatura e Team ID, substituição por fases com rollback (Firefox Developer Edition, KeePassXC, VS Code, CodeEdit, Ledger Live, Trezor Suite) |
| `msupdate` | 5 | verified direct | Microsoft AutoUpdate (`msupdate`): Word, Excel, PowerPoint, Outlook, OneNote |
| `keystone` | 3 | verified direct | Atualizador da Google (Omaha), verificado pelo seu histórico: Chrome, Gemini, Google Drive |
| `appstore_gui` | 3 | externally managed | App Store Via 2 (AppleScript): UniFi, WiFiman, Picsart |
| `sparkle_appcast` | 1 | verified direct | Appcast Sparkle (Proton Drive) |
| `chromium_updater` | 1 | verified direct | Prova do atualizador baseado em Chromium (Comet) |
| `docker_cli` | 1 | verified direct | Docker Desktop: DMG verificado a partir do seu appcast quando inativo; alternativa `docker desktop update` |
| `mau_fallback_self_update` | 1 | triggered-unverified | Atualização própria do Teams mais um fallback MAU `TEAMS21` observado e verificado quando a Microsoft o oferece |
| `manual` | 2 | manual | IPMIView e DJI Assistant 2: apenas notificação |

---

## Opções da linha de comandos

`lib/cli.sh` é a lista de referência; `bash update_all.sh --help` mostra-a.

| Opção | Efeito |
|-------|--------|
| `-y`, `--yes` | Salta o pedido de confirmação |
| `-h`, `--help` | Mostra a ajuda e termina com `0` |
| `--dry-run` | Pré-visualiza cada passo, não altera nada e nunca pede credenciais |
| `--verify-only` | Verifica as versões instaladas em relação ao histórico sem alterar nada |
| `--json-summary` | Imprime um objeto JSON com o resultado em stdout no fim |
| `--bootstrap-cli` | Instala explicitamente as CLIs em falta (por predefinição só se atualizam as instaladas) |
| `--non-interactive` | Modo não interativo para launchd / cron (implica também `-y`) |
| `--notify` | Envia uma notificação do macOS no fim |
| `--treat-appstore-ax-as-warning` | Trata a saída `2` da App Store (Acessibilidade em falta) como aviso |
| `--skip-prescan` | Salta o passo 0 (pré-análise de `APPLICATIONS.md`) |
| `--skip-appstore` | Salta o passo 1 (App Store) |
| `--skip-npm` | Salta o passo 2 (CLI nativas + npm) |
| `--skip-brew` | Salta o passo 3 (Homebrew) |
| `--skip-internet` | Salta o passo 4 (aplicações da Internet) |
| `--skip-postupdate` | Salta o passo 5 (histórico `APPLICATIONS.md` / `UPDATES.md`) |
| `--skip-system` | Salta o passo 6 (atualização do macOS) |
| `--skip-doctor` | Salta o `brew doctor` em `update_brew.sh` |

Uma opção `-…` desconhecida termina com o código `2` depois de mostrar a ajuda.

## Variáveis de ambiente

Cada opção tem uma variável equivalente (`MAC_UPDATE_DRY_RUN=1`, `MAC_UPDATE_SKIP_SYSTEM=1`, …); estas são as mais usadas que não têm opção própria. A lista completa com os valores predefinidos está em [docs/agents/scripts.md](docs/agents/scripts.md#environment-variables).

| Variável | Predefinição | Significado |
|----------|--------------|-------------|
| `MAC_UPDATE_NONINTERACTIVE` | `0` | Nunca pergunta; salta a automação GUI da Via 2 da App Store |
| `MAC_UPDATE_NOTIFY` | `0` | Notificação no ambiente de trabalho no fim (também implícita no modo não interativo) |
| `MAC_UPDATE_NO_SUDO` | *definida automaticamente* | Exportada por `update_all.sh` sem TTY; os scripts filhos saltam as vias root em vez de falhar |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | `0` | `1` desativa a atualização em segundo plano da marca temporal do `sudo` |
| `MAC_UPDATE_STALE_DAYS` | `45` | Dias após os quais uma aplicação não verificada é comunicada como desatualizada |
| `MAC_UPDATE_MAX_LOGS` | `30` | Registos de execução mantidos em `logs/` |
| `MAC_UPDATE_INTERNET_SETTLE_SECONDS` | `15` | Pausa para um atualizador de fornecedor iniciado reescrever o `Info.plist` (`0` desativa, limitada a 120; omitida se nenhuma aplicação foi iniciada) |
| `MAC_UPDATE_QUIT_WAIT` | `60` | Segundos (0–300) que uma aplicação iniciada pela ferramenta tem para fechar após o `quit` suave; nunca forçada (v1.5.5) |
| `MAC_UPDATE_QUIT_RESEND` | `10` | Segundos (1–60) entre pedidos `quit` suaves repetidos na janela de espera (v1.5.5) |
| `MAC_UPDATE_MAS_CHECK_TIMEOUT` | `120` | Tempo limite de `mas outdated` |
| `MAC_UPDATE_MAS_UPGRADE_TIMEOUT` | `1800` | Tempo limite de `sudo mas upgrade` |
| `MAC_UPDATE_MAU_DEFERRAL_DAYS` | `7` | Janela de quarentena do Microsoft AutoUpdate (limitada ao intervalo 1–28 da Microsoft) |
| `MAC_UPDATE_MAU_CLEAR_DEFERRALS` | `0` | `1` remove com `defaults delete` as chaves de adiamento do MAU que bloqueiam |
| `MAC_UPDATE_MAU_KEEP_DEFERRALS` | `0` | `1`: a ferramenta nunca toca nas preferências de adiamento do MAU |
| `MAC_UPDATE_LANG` / `MAC_LANG` | de `.mac_update_prefs` | Idioma da interface (`en pl es it pt de fr`) |

## sudo e Touch ID — o contrato

Reescrito na v1.3.1 / v1.4.0. `update_all.sh` tem **exatamente um** ponto de chamada
interativo ao `sudo`, sujeito a três condições:

1. **No máximo uma vez por execução.** Um único `sudo -v` antes do redirecionamento
   do registo; depois, um processo em segundo plano renova a marca temporal a cada
   50 s, pelo que uma execução longa nunca volta a perguntar. O keep-alive arranca no
   máximo uma vez e a armadilha de limpeza termina-o em qualquer saída, incluindo
   `INT`/`TERM`: já não pode ficar órfão.
2. **Nunca sem um TTY de controlo.** Se o stdin não for um terminal (executor de
   tarefas do IDE, shell de um agente, launchd, cron) a ferramenta **não** chama
   `sudo -v`. Um `sudo -v` sem TTY escala para o diálogo gráfico askpass/Touch ID, e
   era por isso que cada comando parecia exigir elevação. Em vez disso exporta-se
   `MAC_UPDATE_NO_SUDO=1`, os passos que exigem root são saltados e a execução
   comunica um aviso suave.
3. **Nunca durante `--dry-run`.** Uma pré-visualização não deve pedir credenciais.

O `sudo` também não é pedido quando nem o passo 1 (App Store) nem o passo 6 (macOS)
vão correr, p. ex. `bash update_all.sh --skip-appstore --skip-system`.

---

## Configuração por máquina (**não** chega com `git pull`)

Duas coisas vivem fora do repositório e por isso têm de ser configuradas uma vez
**em cada Mac**. Clonar ou fazer pull numa segunda máquina não as traz consigo: é a
confusão mais frequente neste projeto.

| Passo | Comando | Porque não pode estar no Git |
|-------|---------|------------------------------|
| Touch ID para `sudo` | `bash scripts/setup_touchid_sudo.sh` | Escreve `/etc/pam.d/sudo_local`: ficheiro de root, local à máquina, fora do repositório |
| Execução semanal em segundo plano | `bash scripts/install_launchagent.sh --day 1 --hour 9` | Escreve `~/Library/LaunchAgents/com.<user>.macos-updates.plist`: por utilizador e por máquina |

```bash
bash scripts/setup_touchid_sudo.sh --check      # só relatório, não escreve nada
bash scripts/setup_touchid_sudo.sh              # instalar / reparar
bash scripts/setup_touchid_sudo.sh --uninstall

bash scripts/install_launchagent.sh --check
bash scripts/install_launchagent.sh --uninstall
```

`setup_touchid_sudo.sh` nunca toca em `/etc/sudoers` nem concede `sudo` sem palavra-passe.
No macOS 14+ usa `/etc/pam.d/sudo_local`, que sobrevive às atualizações do sistema;
no macOS 13 altera `/etc/pam.d/sudo`, que as atualizações do macOS apagam: volte a
executá-lo após uma atualização maior.

### O que a execução agendada em segundo plano faz e não faz

O LaunchAgent executa `update_all.sh -y --skip-system` com
`MAC_UPDATE_NONINTERACTIVE=1` e `MAC_UPDATE_NOTIFY=1`.

- **Executa:** Homebrew, CLIs nativas + npm, aplicações da Internet, inventário/histórico.
- **Não executa atualizações do macOS**: `--skip-system` é deliberado. Em Apple
  Silicon o `softwareupdate` precisa das **credenciais do proprietário do volume**,
  que um trabalho launchd sem supervisão não pode fornecer, e o passo pode reiniciar
  o Mac.
- **Não executa atualizações da App Store**: `sudo mas upgrade` exige palavra-passe
  e o caminho AppleScript da Via 2 controla a interface da App Store. Ambos são
  saltados numa sessão sem TTY e comunicados como aviso suave (código `10`), nunca
  como falha.

Ambos continuam, portanto, interativos, de propósito. Execute `bash update_all.sh`
você mesmo quando quiser aplicar as atualizações da App Store e do macOS.

---

## Requisitos

| Ferramenta | Instalada automaticamente? |
|------------|----------------------------|
| Mac com Apple Silicon (arm64) | — |
| macOS 13 Ventura ou posterior (testado até ao macOS 27) | — |
| Xcode Command Line Tools | ✅ `setup.sh` / `install.sh` |
| Homebrew | ✅ |
| `mas` (CLI da App Store) | ✅ |
| Python 3 | ✅ através do Homebrew, se faltar |
| `rclone` (opcional) | ✅ se escolhido como fornecedor de nuvem |

Macs Intel e macOS 12 ou anterior não são suportados; os scripts terminam antes de qualquer alteração.

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

### Proprietário (GitHub + camada privada na nuvem)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

---

## Estrutura do projeto

```
macOS_updates/
├── VERSION                     # Versão do pacote (única fonte de verdade)
├── install.sh                  # Instalador numa linha
├── uninstall.sh                # Remove o clone (mantém o Homebrew e as aplicações)
├── setup.sh                    # Configuração inicial (sem nuvem)
├── migration_setup.sh          # Configuração completa + assistente de nuvem
├── build_inventory.sh          # Cria APPLICATIONS.md para este Mac
├── update_all.sh               # Orquestrador principal
├── update_*.sh                 # Passos de atualização individuais
├── run_tests.sh                # Sintaxe + Python + unittest + análise de segredos
│
├── dev_sync/                   # Sincronização da camada privada (nuvem)
│   ├── provider_setup.sh
│   ├── dev-sync-export.sh      # (+ import, verify, prune, …)
│   └── dev_sync_*.py           # Backend em Python
├── dev-sync-*.sh               # Wrappers na raiz (compatibilidade)
│
├── config/                     # Registo das aplicações da Internet (público)
│   ├── internet_apps.txt
│   ├── internet_app_methods.txt
│   └── internet_dispatch_order.txt
│
├── lib/                        # Bibliotecas Bash partilhadas (+ lib/python/)
├── i18n/                       # Textos da interface em 7 idiomas
├── scripts/                    # Utilitários (relatório de cobertura, feeds de fornecedores, gerador, …)
├── templates/                  # APPLICATIONS.md.template (referência)
├── tests/                      # unittest + verificações estáticas de segurança
├── docs/
│   ├── INSTALL.md · UNINSTALL.md · PUBLIC_RELEASE.md
│   ├── user/                   # Guias para utilizadores finais (7 idiomas)
│   ├── agents/                 # Referência para programadores / agentes de IA
│   ├── reviews/                # Índice + registos de desenvolvimento atuais (archive/ = histórico)
│   └── archive/                # Planos de implementação ultrapassados
│
├── CHANGELOG.md · CONTRIBUTING.md · SECURITY.md · LICENSE
└── AGENTS.md · CLAUDE.md · GEMINI.md · CODEX.md
```

**Ficheiros privados (ignorados pelo git, apenas locais ou na nuvem):** `APPLICATIONS.md`, `UPDATES.md`, `.dev_sync_config.json`, `.mac_update_prefs`, `.env`, `logs/`

### Scripts individuais

| Script | Finalidade |
|--------|------------|
| `install.sh` | Clona + configura + cria o inventário para novos utilizadores |
| `setup.sh` | Dependências e permissões (sem nuvem) |
| `migration_setup.sh` | Migração completa + nuvem + análise das aplicações |
| `build_inventory.sh` | Análise só de leitura → atualiza `APPLICATIONS.md` de forma atómica sem histórico de atualizações |
| `update_all.sh` | Todos os passos de atualização + registo |
| `update_system.sh` … `update_brew.sh` | Atualizações de uma só camada |
| `uninstall.sh` | Remove o diretório da ferramenta |
| `run_tests.sh` | Sintaxe + Python + unittest + análise de segredos |

Referência completa dos scripts: [docs/agents/scripts.md](docs/agents/scripts.md).

---

## Adicionar suporte a uma nova aplicação

1. Instale a aplicação você mesmo (o atualizador nunca a instala por si).
2. Execute `bash build_inventory.sh` para a acrescentar a `APPLICATIONS.md`.
3. Para a atualização automática, peça a um agente de IA ou siga [docs/user/pt/GUIDE.md](docs/user/pt/GUIDE.md):

```bash
bash scripts/scaffold_internet_app.sh "Nome da app" silent_launch
bash run_tests.sh
```

Os métodos do registo são associados aos estados de cobertura acima. Por exemplo, `github_dmg` e uma CLI de fornecedor confirmada são **verified direct**; `silent_launch` é **triggered-unverified**; os fluxos geridos pela App Store ou pelo fornecedor podem ser **externally managed**; `manual` e as entradas em falta no registo permanecem explícitos.

---

## Sincronização na nuvem (`dev_sync`)

| GitHub (público) | Nuvem (privado) |
|------------------|-----------------|
| Scripts, `config/`, `docs/`, testes | `APPLICATIONS.md`, `UPDATES.md`, `.env`, `.dev_sync_config.json` |

```bash
bash dev_sync/provider_setup.sh
bash dev_sync/dev-sync-export.sh
bash dev_sync/dev-sync-import.sh
bash dev_sync/dev-sync-verify-full.sh
```

Os wrappers `dev-sync-*.sh` na raiz chamam os mesmos scripts de `dev_sync/`.

---

## Testes

A bateria cobre a sintaxe do bash, a compilação do Python, os contratos estáticos de segurança, as guardas de documentação e os testes unitários (590 testes automáticos).
Os pull requests executam o ShellCheck no Ubuntu, testes Python portáteis e a análise de segredos.
A suite completa `run_tests.sh` num runner macOS só corre com `workflow_dispatch` ou uma etiqueta `v*`, não a cada push.

```bash
bash run_tests.sh
bash update_all.sh --dry-run -y
```

---

## Notas técnicas críticas

- **`softwareupdate` tem de usar `-R`**: caso contrário as atualizações são transferidas mas nunca aplicadas.
- **`mas upgrade` tem de usar `sudo` e IDs de aplicação explícitos** no macOS 14.8.2+/15.7.2+/26.1+ (alteração de permissões, ver https://github.com/orgs/Homebrew/discussions/6550).
- **Bash 3.2+** em todo o lado: sem `declare -A`, `mapfile` nem `readarray`.
- As aplicações transferidas são verificadas, instaladas por uma substituição por fases com rollback, e os seus DMG são montados em pontos de montagem únicos por sessão.
- A escrita do inventário/histórico privados e as importações da nuvem são atómicas; as importações preparam os ficheiros aceites antes de os confirmar.

---

## Documentação

| Público | Comece aqui |
|---------|-------------|
| Utilizadores | [docs/user/INDEX.md](docs/user/INDEX.md) (início rápido, guia e manual de operações em 7 idiomas) · [início rápido em português](docs/user/pt/QUICK_START.md) |
| Instalação / desinstalação | [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md) |
| GitHub público e camada privada | [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md) · [dev_sync/README.md](dev_sync/README.md) |
| Programadores / agentes | [docs/agents/scripts.md](docs/agents/scripts.md) · [regras críticas](docs/agents/critical_rules.md) · [códigos de saída](docs/agents/exit_codes.md) · [resolução de problemas](docs/agents/troubleshooting.md) · [lista de aceitação](docs/agents/acceptance_checklist.md) |
| Contexto para agentes de IA | [AGENTS.md](AGENTS.md) (contrato partilhado) · [CLAUDE.md](CLAUDE.md) · [GEMINI.md](GEMINI.md) · [CODEX.md](CODEX.md) |
| Histórico de versões | [CHANGELOG.md](CHANGELOG.md) · [índice dos registos de desenvolvimento](docs/reviews/README.md) |
| Contribuir / segurança | [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md) |

---

## Resolução de problemas

| Problema | Solução |
|----------|---------|
| Mac novo | `install.sh` ou `setup.sh` + `build_inventory.sh` |
| Lista de aplicações errada | `build_inventory.sh`: nunca copie o `APPLICATIONS.md` de outra pessoa |
| Uma aplicação não se atualiza sozinha | `scripts/report_update_coverage.sh` → acrescente um manipulador conforme o guia |
| `APPLICATIONS.md` em falta | `build_inventory.sh` ou `dev_sync/dev-sync-import.sh` (proprietário) |
| `mas upgrade` falha | `sudo mas upgrade <app-id>` |
| Nuvem não configurada | `bash dev_sync/provider_setup.sh` |

Lista completa: [docs/agents/troubleshooting.md](docs/agents/troubleshooting.md)

---

## Licença

[MIT](LICENSE) © macOS Updates contributors
