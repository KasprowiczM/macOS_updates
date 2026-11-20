# Operações (Português)

**macOS Updates 2.0.10** · para quem executa o programa a partir de um terminal, de um script ou de uma execução automática.

## Formas de executar

| Comando | O que acontece |
|---------|----------------|
| `mac-update` | Abre a interface (precisa de um terminal). |
| `mac-update run [options]` | Execução em texto simples. As opções passam ao programa de atualização, por exemplo `-y`, `--skip-system`, `--non-interactive`. |
| `mac-update --cli [options]` | O mesmo que `mac-update run` (também `--plain`). |
| `mac-update --tui` | O mesmo que `mac-update`: abre a interface. |
| `mac-update preview` | Percorre todos os passos e mostra o que aconteceria. Nada é atualizado. |
| `mac-update scan` | Refaz a lista das apps deste Mac. Só lê. |
| `mac-update doctor` | Relatório de preparação só de leitura. Sem palavra-passe e sem registo de execução. |
| `mac-update settings` | Abre a interface no separador Definições. |
| `mac-update update-self` | Verifica se existe um mac-update mais recente (`--check`, a predefinição, ou `--prepare`). |
| `mac-update migrate` | Traz as definições de uma cópia antiga feita com git: `--preview` (predefinição), `--apply`, `--undo MANIFEST`. |
| `mac-update uninstall` | Remove o mac-update. Veja [UNINSTALL.md](../../UNINSTALL.md) (em inglês). |
| `mac-update version`, `mac-update help` | Versão e lista de comandos. |

`macos-update` é o mesmo comando que `mac-update`, com um nome mais longo. O instalador liga ambos em `~/.local/bin`, e ambos funcionam a partir de qualquer pasta.

O `mac-update` chama o `update_all.sh` na pasta do programa `~/.local/share/mac-update`. Se trabalhar a partir de uma cópia git, execute `bash update_all.sh` aí; as opções abaixo são as mesmas. Com `MAC_UPDATE_NONINTERACTIVE=1` a interface nunca abre e nada espera por uma resposta.

## Opções do `update_all.sh`

| Opção | Significado |
|-------|-------------|
| `-y`, `--yes` | Saltar a pergunta de confirmação |
| `-h`, `--help` | Mostrar a lista de opções |
| `--tui`, `--cli` | Escolher a interface ou o texto simples. `--tui` falha com uma mensagem se não houver um terminal utilizável; só se podem acrescentar `--dry-run` e `--skip-...`. |
| `--dry-run` | Pré-visualizar, sem alterar nada |
| `--doctor` | Relatório de preparação. Código de saída 0 ok, 10 avisos, 1 problema |
| `--verify-only` | Comparar as versões das apps instaladas com o histórico, sem alterar nada |
| `--json-summary` | Mostrar um resumo em JSON no fim |
| `--bootstrap-cli` | Instalar também uma ferramenta de linha de comandos gerida (Node, Bun ou nativa) que falte. Desativada por defeito. |
| `--skip-prescan` | Saltar a primeira verificação da lista de apps |
| `--skip-appstore` | Saltar as apps da App Store |
| `--skip-npm` | Saltar as ferramentas do Terminal (npm, bun, ferramentas de linha de comandos nativas) |
| `--skip-brew` | Saltar o Homebrew |
| `--skip-internet` | Saltar as apps da internet |
| `--skip-postupdate` | Saltar a atualização da lista de apps e do histórico |
| `--skip-system` | Saltar a atualização do macOS |
| `--skip-doctor` | Saltar `brew doctor` dentro do passo do Homebrew |
| `--treat-appstore-ax-as-warning` | Indicar a falta da permissão de Acessibilidade como aviso |
| `--non-interactive` | Para agendadores: sem perguntas (igual a `MAC_UPDATE_NONINTERACTIVE=1`) |
| `--notify` | Mostrar uma notificação do macOS quando a execução terminar |

Os passos decorrem sempre por esta ordem: verificação do sistema, App Store, ferramentas do Terminal, Homebrew, apps da internet, lista de apps, macOS. O macOS vem no fim porque pode reiniciar o Mac. Se um passo anterior falhou gravemente, o passo do macOS espera pela execução seguinte.

## Variáveis de ambiente

Defina-as à frente do comando, por exemplo `MAC_UPDATE_MIN_FREE_GB=30 mac-update run`. A maioria existe também como linha nas Definições; uma linha definida por uma variável não pode ser alterada na interface.

| Variável | Predefinição | Finalidade |
|----------|--------------|------------|
| `MAC_UPDATE_NONINTERACTIVE` | desativada | `1`: sem interface e sem perguntas |
| `MAC_UPDATE_DRY_RUN` | desativada | `1`: igual a `--dry-run` |
| `MAC_UPDATE_SKIP_APPSTORE`, `_NPM`, `_BREW`, `_INTERNET`, `_SYSTEM`, `_PRESCAN`, `_POSTUPDATE`, `_DOCTOR` | desativada | `1`: igual à opção `--skip-...` correspondente |
| `MAC_UPDATE_SYSTEM_MODE` | `auto` | Atualizações do macOS: `auto` instala, `notify` só comunica, `skip` não verifica |
| `MAC_UPDATE_NEW_APP_MODE` | por confiança | `auto` ou `manual` para apps encontradas novas que não constam da lista testada |
| `MAC_UPDATE_NOTIFY` | desativada | `1`: notificação ao terminar. Nas execuções automáticas: `always`, `needs_you` ou `never` |
| `MAC_UPDATE_LANG` | idioma do sistema | `en`, `pl`, `de`, `fr`, `es`, `it`, `pt` |
| `MAC_UPDATE_HOME` | `~/.local/share/mac-update` | Pasta do programa |
| `MAC_UPDATE_CONFIG_DIR` | `~/.config/mac-update` | Pasta das definições |
| `MAC_UPDATE_STATE_DIR` | `~/.local/state/mac-update` | Registos, caches, cópias de segurança |
| `MAC_UPDATE_LOGS_DIR` | `logs` na pasta de estado | Registos de execução |
| `MAC_UPDATE_OVERRIDES_FILE` | `overrides.tsv` na pasta das definições | Ficheiro das escolhas por app |
| `MAC_UPDATE_MAX_LOGS` | 30 | Registos de execução a manter |
| `MAC_UPDATE_PROMPT_TIMEOUT` | 120 | Segundos para responder a uma pergunta antes de ser usada a resposta segura |
| `MAC_UPDATE_MIN_FREE_GB` | 15 | Avisa e executa de forma reduzida abaixo deste espaço livre |
| `MAC_UPDATE_MIN_BATTERY` | 30 | Com bateria abaixo desta percentagem, salta o passo do macOS (uma execução automática é saltada por completo) |
| `MAC_UPDATE_NO_CAFFEINATE` | desativada | `1`: não manter o Mac ativo durante a execução |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | desativada | `1`: não manter a palavra-passe de administrador válida |
| `MAC_UPDATE_SUDO_KEEPALIVE_MAX` | 14400 | Segundos durante os quais a mantém válida (300 a 14400) |
| `MAC_UPDATE_QUIT_WAIT` | 60 | Segundos a esperar que uma app iniciada pelo programa feche (0 a 300) |
| `MAC_UPDATE_STAGE_WAIT` | 90 | Segundos a esperar que uma app aberta pelo programa instale a sua própria atualização (0 a 600) |
| `MAC_UPDATE_POST_QUIT_WAIT` | 10 | Segundos a esperar depois de fechar essa app quando a atualização ficou preparada |
| `MAC_UPDATE_POST_QUIT_WAIT_IDLE` | 3 | O mesmo, quando nenhuma atualização ficou preparada |
| `MAC_UPDATE_OMAHA_WAIT` | 45 | Segundos a esperar pela resposta do atualizador da Google (0 a 180) |
| `MAC_UPDATE_OMAHA_MAX_AGE_H` | 6 | Horas durante as quais uma verificação do atualizador da Google é considerada recente |
| `MAC_UPDATE_BTM_CHECK` | ativo | `0`: não verificar se o macOS bloqueia uma app em Itens de início de sessão e extensões |
| `MAC_UPDATE_BTM_TIMEOUT` | 4 | Segundos permitidos para essa verificação |
| `MAC_UPDATE_BTM_DUMP`, `MAC_UPDATE_GOOGLE_USER_LOG`, `MAC_UPDATE_GOOGLE_SYS_LOG` | nenhum | Só para diagnóstico e testes: uma lista guardada dos itens de início de sessão ou ficheiros de registo do atualizador da Google, lidos em vez dos reais |
| `MAC_UPDATE_VENDOR_DIRECT` | ativada | `0`: sem transferências diretas do criador da app |
| `MAC_UPDATE_ALLOW_MAJOR_UPGRADE` | desativada | `1`: permitir grandes saltos de versão, incluindo um grande upgrade do macOS |
| `MAC_UPDATE_MAU_DEFERRAL_DAYS` | 7 | Dias a esperar antes de instalar uma nova versão do Microsoft Office |
| `MAC_UPDATE_FEED_CACHE_TTL_H` | 24 | Horas durante as quais se reutiliza a informação de versões do fabricante |
| `MAC_UPDATE_MAS_UPGRADE_TIMEOUT` | 1800 | Segundos até uma atualização da App Store ser parada e comunicada |
| `MAC_UPDATE_DOCTOR_PROBE_AX` | desativada | `1`: deixar o `doctor` testar a permissão de Acessibilidade (o macOS pode mostrar um aviso) |
| `GITHUB_TOKEN` | nenhuma | Opcional. Aumenta o limite de transferências do GitHub. Defina-a no perfil da sua shell |

## Execuções automáticas (opcional)

As execuções automáticas estão desativadas por defeito e não têm hora predefinida. Ative-as nas **Definições**, secção **Execuções automáticas**, linha «Automação diária». Escolhe:

- quando: todos os dias à hora que escrever (24 horas, por exemplo 08:30), ao iniciar sessão, ou ambos;
- como é avisado: após cada execução, só quando algo precisa de si (a predefinição) ou nunca.

Vê exatamente o que será instalado e confirma antes de se escrever o que quer que seja. «Testar agora» agenda mais uma execução daqui a poucos minutos.

O mesmo a partir de um terminal, com `bash ~/.local/share/mac-update/scripts/install_launchagent.sh`:

```bash
bash scripts/install_launchagent.sh --daily 08:30 --notify needs_you      # todos os dias às 08:30
bash scripts/install_launchagent.sh --daily 08:30 --days 1,3,5            # só em dias da semana escolhidos (números 1 a 7)
bash scripts/install_launchagent.sh --at-login --delay-min 10             # ao iniciar sessão, após 10 minutos de sessão
bash scripts/install_launchagent.sh --once-in 5                           # uma execução de teste daqui a 5 minutos
bash scripts/install_launchagent.sh --status                              # está instalada? (--check, ou --status --json)
bash scripts/install_launchagent.sh --uninstall                           # remove todas as agendas do mac-update
```

Execute-os a partir da pasta do programa. `--notify` aceita `always`, `needs_you` ou `never`.

O que faz uma execução automática:

- Executa sem terminal e nunca faz perguntas.
- Salta as atualizações do macOS, a menos que as ative; o macOS apenas comunica o que está disponível.
- Salta-se a si própria quando outra execução está em curso, quando o Mac tem pouca bateria, ou quando a última execução bem-sucedida foi há menos de 12 horas.
- Tudo o que precise da sua palavra-passe ou de um reinício é saltado e indicado em «Precisam de si». Execute `mac-update` por si para concluir.
- Envia uma notificação, como escolheu. O resultado vai para `launchd.out` e `launchd.err` na pasta dos registos.

## Palavras-passe

Os passos do macOS e da App Store podem precisar da palavra-passe de administrador. Num terminal, o programa pergunta no máximo uma vez por execução e mantém-na válida até ao fim. Nunca pergunta numa pré-visualização, nem sem terminal (as execuções automáticas saltam esses passos). Opcional: `bash scripts/setup_touchid_sudo.sh --check` mostra se o Touch ID pode substituir a palavra-passe no `sudo`. Executar o script sem `--check` mostra uma pré-visualização e pergunta primeiro.

## Onde estão as coisas

| O quê | Onde |
|-------|------|
| O programa | `~/.local/share/mac-update` |
| As suas definições e escolhas por app | `~/.config/mac-update` (`overrides.tsv`, `lang`, `reports/`) |
| Registo de cada execução | `~/.local/state/mac-update/logs/update_all_<date>_<time>.log` (guardados os 30 mais recentes, modo 600) |
| Resultado resumido da última execução | `~/.local/state/mac-update/logs/run_summary_latest.json` |
| Definições da interface | `~/.local/state/mac-update/tui-settings.json` |
| Resultado das execuções automáticas | `~/.local/state/mac-update/logs/launchd.out`, `launchd.err` |

Uma pré-visualização escreve o registo numa pasta temporária e deixa o seu histórico intacto. Na interface, o separador **Histórico** lista as execuções anteriores e `L` abre o registo mais recente. Vem de uma cópia antiga feita com git: `mac-update migrate`.

Código de saída de `update_all.sh`: `0` quando a execução correu bem ou teve apenas avisos (uma app que precisa de si é um aviso), `1` quando algo falhou.

## Resolução de problemas

Comece por `mac-update doctor`. Verifica a plataforma, o Python, o curl, o Homebrew, o `mas`, o Touch ID, o espaço em disco, a energia, a rede e o próprio programa.

| Problema | O que fazer |
|----------|-------------|
| `mac-update: command not found` | Abra uma nova janela do Terminal. Se continuar, a pasta `~/.local/bin` não está no seu `PATH`: execute o instalador novamente com `--configure-shell` ou acrescente essa pasta por si. |
| `mac-update` inicia outro programa | Outro programa com esse nome aparece antes no seu `PATH`. O instalador avisa disso e indica o ficheiro desse programa. Execute `~/.local/bin/mac-update` diretamente, ou elimine ou mude o nome do outro ficheiro. |
| A interface não abre | Precisa de um terminal, de Python 3 e de um `TERM` diferente de `dumb`. Caso contrário, use `mac-update run`. |
| O instalador diz que a soma de verificação não coincide | Nada foi instalado. Tente mais tarde; se se repetir, comunique-o. |
| Uma app está em «Precisam de si» | Veja a tabela «O que significa "Precisam de si"» em [GUIDE.md](GUIDE.md). |
| O passo da App Store pára com o código de saída 2 | O terminal não tem a permissão de Acessibilidade. Permita-a em Definições do Sistema, Privacidade e segurança, Acessibilidade, ou acrescente `--treat-appstore-ax-as-warning`. |
| O `mas` não existe ou é demasiado antigo | O programa comunica-o e nunca o instala sozinho. Instale-o por si com o Homebrew (`brew install mas`). |
| A App Store precisa que inicie sessão | Abra a App Store, inicie sessão e execute novamente. |
| O Homebrew não está instalado | Instale-o a partir de <https://brew.sh> e execute novamente. |
| A lista de apps não existe ou está errada | `mac-update scan`. Só lê o seu Mac. Nunca copie a lista de outra pessoa. |
| Uma app nunca é atualizada | Diagnóstico, «Como as apps são atualizadas», mostra como cada app é tratada. Se não houver método, abra a app e use a sua própria opção «Procurar atualizações». |
| Não é possível aceder às informações de atualização de um fabricante | Tente mais tarde. Verifique os feeds em Diagnóstico, «Verificar feeds de atualização». |
| O Mac entrou em suspensão durante uma execução | Mantenha «Manter o Mac ativo» ligado (predefinição). |
| Uma atualização foi interrompida | Diagnóstico, «Concluir atualizações interrompidas». |
| Uma execução diz que há outra em curso | Espere que termine. Um marcador deixado por uma execução que falhou é limpo no início da execução seguinte. |
| Pouco espaço em disco ou bateria fraca | Liberte espaço ou ligue o carregador. Os limites estão nas Definições, «Verificações de segurança». |

Ainda sem solução? Abra o ficheiro mais recente na pasta dos registos e procure a primeira linha que diga error ou warning.

## Desinstalar

```bash
mac-update uninstall
```

Também desliga as execuções automáticas. Veja [UNINSTALL.md](../../UNINSTALL.md) (em inglês) para saber o que é e o que não é removido.
