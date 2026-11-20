# Guia do utilizador (Português)

**macOS Updates 2.0.10** · Mac com Apple Silicon · macOS 13 ou posterior

## O que faz

Cada execução atualiza, por esta ordem:

1. Apps da App Store
2. Ferramentas do Terminal (npm, bun e ferramentas de linha de comandos que se atualizam sozinhas)
3. Fórmulas e casks do Homebrew
4. Apps da internet: apps que transferiu do site do fabricante, atualizadas a partir do feed de atualizações do fabricante, de uma transferência direta verificada ou do atualizador da própria app
5. A lista das suas apps (atualizada)
6. O macOS, sempre no fim

Não lhe pede que aprove cada app. Só atua sobre o que já está instalado.

## O que nunca faz

- Nunca fecha uma app que tem aberta. Essa app é indicada em «Precisam de si».
- Nunca instala uma app que não tem. (O separador opcional Catálogo é o único sítio que pode instalar, e apenas o que escolher.)
- Nunca confia cegamente numa transferência. Uma transferência tem de vir de um servidor permitido, ter uma assinatura de código válida e passar no Gatekeeper.
- Nunca pára tudo por causa de um item que falhou. Os outros itens, os passos seguintes e a atualização do macOS continuam a decorrer.

## Abrir a interface

```bash
mac-update
```

Num terminal, isto abre a interface. Num script, por SSH sem terminal, ou com `MAC_UPDATE_NONINTERACTIVE=1`, obtém texto simples. `mac-update run` dá sempre texto simples. `mac-update --cli` (também `--plain`) é o mesmo que `mac-update run`, `mac-update --tui` é o mesmo que `mac-update` sozinho, e `macos-update` é o mesmo comando com um nome mais longo. Todos funcionam a partir de qualquer pasta. A janela precisa de pelo menos 40 colunas por 12 linhas. Maior é melhor: se deixar «Ajustar a janela automaticamente» ligado, a interface pede ao terminal 120 por 36 ao iniciar e repõe o tamanho quando sair.

Mova-se com as setas. Enter abre ou confirma, Tab passa ao painel seguinte, Esc volta atrás, `1` a `7` saltam para um separador, `?` abre a ajuda, `L` mostra o registo completo, `q` sai. O rato também funciona. A linha de baixo mostra sempre as teclas que funcionam nesse momento.

## Os separadores

```
 macOS Updates                                  Última vez: concluído, há 2 h
 Painel   Apps   Catálogo   Histórico   Definições   Diagnóstico   Ajuda
 +- Grupos de atualização ---------------------------------------------+
 | > ✓ Verificação do sistema  ############  concluído                 |
 |   ✓ App Store               ############  ✓3 •5                     |
 |   ✓ Ferramentas do Terminal ############  ✓2 •9                     |
 |   * Homebrew                ######......  4/9  ✓1 •3                |
 |   . Apps da internet        ............  em espera                 |
 |   . Lista de apps           ............  em espera                 |
 |   . Sistema macOS           ............  em espera                 |
 +---------------------------------------------------------------------+
   [ Atualizar tudo ]   [ Pré-visualizar (sem mudanças) ]
   ✓ atualizadas  • em dia  ! precisam de si  ✗ falharam
```

Este é um desenho simplificado. O ecrã real usa cores e símbolos.

| Separador | Para que serve |
|-----------|----------------|
| **Painel** | Iniciar uma atualização. Mostra cada grupo com o progresso em direto (feitas em relação ao total) e uma lista deslocável das apps dentro dele enquanto decorre. Enter ou Espaço num grupo ativa-o ou desativa-o para a próxima execução. Um painel lateral mostra a última execução, o que ainda precisa de si, a próxima execução automática e o estado deste Mac. |
| **Apps** | Todas as apps e pacotes encontrados neste Mac (as apps auxiliares e de segundo plano ficam de fora). Escolha como cada um é atualizado. |
| **Catálogo** | Todas as apps testadas: primeiro as que ainda podem ser adicionadas, depois as já instaladas (apenas mostradas). Nada fica selecionado até escolher, e o instalador pergunta antes de cada alteração. As atualizações nunca o usam. |
| **Histórico** | Execuções anteriores, das mais recentes para as mais antigas, cada uma com o seu resultado. Escolha uma execução para ver o que foi atualizado e o que precisou de si. Enter abre o registo completo. |
| **Definições** | O que atualizar, limites de segurança, execuções automáticas, idioma e aspeto. Cada alteração é guardada de imediato. |
| **Diagnóstico** | Verificações que pode executar: verificar este Mac, verificar requisitos, como as apps são atualizadas (uma tabela com todas as apps e a forma como o método de cada uma foi descoberto), verificar feeds de atualização, refazer a lista de apps, concluir atualizações interrompidas, procurar atualização do programa. |
| **Ajuda** | Um guia curto: primeiros passos, como funciona a atualização, para que serve cada separador, o que significa «Precisam de si». |

## Executar uma atualização

- **Atualizar tudo** verifica e atualiza todos os grupos que estão ativados.
- **Pré-visualizar (sem mudanças)** segue os mesmos passos e mostra o que aconteceria. Não instala nada e não escreve no histórico.

Durante a execução vê cada grupo e cada app: a verificar, a transferir, a validar, a instalar. Prima `L` para ver o registo completo. **Parar** termina a execução em segurança: as apps já atualizadas continuam atualizadas.

As perguntas (por exemplo, sobre um reinício) esperam pela sua resposta. Se não responder a tempo, é usada a resposta segura. A palavra-passe de administrador é escrita no terminal e nunca é guardada nem mostrada.

O ecrã de resultado mostra:

- **Atualizadas**: agora em dia.
- **Em dia**: não foi preciso fazer nada.
- **Precisam de si**: veja abaixo.

## Como as apps da internet são atualizadas

- As apps com uma transferência verificada do fabricante (por exemplo Claude e Antigravity IDE) são instaladas diretamente em vez de serem abertas e aguardadas. Se essa transferência falhar, o atualizador da própria app continua a ser usado.
- Uma app aberta para se atualizar sozinha é fechada assim que a sua atualização fica preparada (Warp), em vez de esperar o tempo todo.
- O Chrome durante uma distribuição gradual é indicado de imediato quando o atualizador da Google já respondeu «sem atualização» para a sua versão.
- As apps da Google (Gemini, Chrome, Google Drive) mostram quando o atualizador da Google verificou pela última vez e quando voltará a verificar, ou que a app se atualizou sozinha.
- Uma app do Homebrew que estava aberta e já se atualizou sozinha é indicada como atualizada, sem aviso.
- Quando o macOS bloqueia uma app em **Itens de início de sessão e extensões** (fecha logo após abrir), o resultado di-lo e indica onde a permitir: Definições do Sistema › Geral › Itens de início de sessão e extensões.

## Ajustar cada app

Abra o separador **Apps**. Escreva `/` para pesquisar por nome ou origem. Prima Enter numa app. Espaço marca várias apps para as alterar em conjunto.

| Modo | Significado |
|------|-------------|
| **automático** | O programa atualiza-a por si. É a predefinição. |
| **manual** | O programa apenas avisa quando há uma atualização à espera. |
| **ignorar** | O programa não lhe mexe. |

Quando uma app tem mais do que uma origem, pode também escolher a **origem preferida**: origem predefinida, Homebrew, App Store, site do fabricante ou atualizador integrado. A coluna **Método** mostra como o programa conhece a app: testada (consta da lista de apps testadas do programa), detetada automaticamente (encontrada através de um recibo da App Store, do Homebrew, de um feed de atualizações ou de um atualizador integrado) ou manual (nada foi reconhecido). A definição «Apps encontradas novas» decide o que acontece às apps que uma análise encontra e que não constam da lista testada: por confiança (automático quando o método de atualização é claro, manual caso contrário), sempre automático ou sempre manual.

Se a lista estiver vazia, escolha **Analisar agora**. A análise apenas lê o seu Mac.

As suas escolhas são guardadas em `~/.config/mac-update/overrides.tsv`, uma linha por app: grupo, nome, modo, origem (separados por tabulações). Apague o ficheiro para repor todas as apps em automático.

## Definições

Escolha um perfil para começar depressa: **Automático total** (tudo), **Prudente** (sem atualização do macOS, sem grandes saltos de versão), **Só verificar** (nada é instalado). Qualquer alteração manual mostra **Personalizado**.

| Secção | Linhas |
|--------|--------|
| O que atualizar | Um interruptor por grupo; Só verificar, nunca instalar; Permitir grandes atualizações (desativado, mantém a versão principal atual); Atualizações do macOS: instalar, só avisar ou desligado (antes de reiniciar pergunta-se sempre) |
| Apps e origens | Apps encontradas novas (por confiança, automático, manual); Modo e origem por app (abre o separador Apps); Apps excluídas (`config/inventory_exclusions.txt`); Ferramentas npm acompanhadas (`config/npm_global_clis.txt`) |
| Execuções automáticas | Automação diária (desativada por defeito, sem hora predefinida): quando corre (todos os dias à hora que escolher, ao iniciar sessão, ou ambos) e a notificação após uma execução (após cada execução, só quando algo precisa de mim, nunca); Testar agora |
| Verificações de segurança | Esperar que as apps fechem (s); Transferir de sites de fabricantes; Espaço livre mínimo (GB, predefinição 15); Nível mínimo da bateria (%, predefinição 30) |
| Rede e velocidade | Reutilizar verificações durante (horas); Tempo para responder (s, predefinição 120); Limite de tempo da App Store (s) |
| Notificações e relatórios | Aviso ao terminar; Abrir o último registo; Registos a manter (predefinição 30) |
| Idioma e aspeto | Idioma (English, Polski, Deutsch, Español, Français, Italiano, Português; segue o idioma do sistema até escolher um); Cores; Cor de destaque (azul por predefinição, violeta, âmbar, verde-sálvia, rosa, grafite); Espaçamento; Carateres simples; Ajustar a janela automaticamente; Rato; Painel de ajuda aberto ao iniciar |
| Sistema e manutenção | Atraso do Microsoft Office (dias); Manter o Mac ativo; Refazer a lista de apps; Atualizar este programa; Exportar definições; Importar definições; Repor predefinições |

As definições são guardadas em `~/.local/state/mac-update/tui-settings.json` e o idioma em `~/.config/mac-update/lang`. Uma linha definida por uma variável de ambiente mostra essa variável e não pode ser alterada na janela. «Esperar que as apps fechem» aplica-se às apps que o próprio programa iniciou.

As cores acompanham o seu terminal. A predefinição, **automático**, pergunta ao terminal se a janela é clara ou escura e usa o esquema correspondente. O aspeto claro deixa à página o fundo branco e a cor de texto do próprio terminal; só a barra de cima, a barra de teclas, a linha selecionada e as caixas de diálogo ficam em cinzento-claro, e todas as cores continuam legíveis numa janela branca. O esquema escuro não mudou. Um «escuras» guardado por uma versão anterior é tratado uma vez como automático; se quiser sempre escuras, escolha-as de novo em Definições, Idioma e aspeto, Cores.

## O que significa «Precisam de si»

Cada linha do ecrã de resultado tem um motivo e um próximo passo.

| Motivo | O que fazer |
|--------|-------------|
| **A app estava aberta** | Feche a app e execute a atualização novamente. O programa nunca a fecha por si. |
| **É preciso iniciar sessão** (App Store) | Abra a App Store, inicie sessão e execute a atualização novamente. |
| **Era necessária uma palavra-passe** | Execute a atualização novamente a partir de um terminal e introduza a palavra-passe de administrador quando for pedida. As execuções automáticas não podem perguntar, por isso indicam este motivo. |
| **É preciso reiniciar** | A atualização está instalada, mas só tem efeito após reiniciar. Reinicie o Mac quando lhe for conveniente. |
| **Não existe um método automático** | Não existe uma forma automática segura de atualizar esta app. Abra a app e use a sua própria opção «Procurar atualizações». |
| **A transferência falhou** | Verifique a ligação à internet e execute a atualização novamente. |
| **A soma de verificação não coincide** | A transferência não coincidia com a sua soma de verificação, por isso nada foi instalado. Tente mais tarde; se continuar a falhar, atualize a app manualmente. |
| **Modo manual** | Definiu esta app como manual. Atualize-a por si ou mude-a para automático no separador Apps. |
| **Não foi possível aceder às informações de atualização do fabricante** | Tente mais tarde. O site do fabricante pode estar em baixo. |
| **Está disponível uma nova versão principal** | Os grandes upgrades estão desativados. Permita-os nas Definições ou atualize a app manualmente. |
| **Pouco espaço em disco / bateria fraca** | Liberte algum espaço ou ligue o transformador e execute a atualização novamente. |
| **Demorou demasiado** | Execute a atualização novamente. Abra o registo completo (`L`) se se repetir. |
| **O atualizador da própria app foi aberto** | Conclua a atualização na janela que a app abriu. |

Algumas apps instalam a atualização quando fecham. Se o próprio programa iniciou uma app assim, fecha-a assim que a atualização estiver pronta. Uma app que abriu por si nunca é fechada.

Se o motivo disser que não é conhecido, abra o registo completo com `L`.

O cabeçalho, o Painel e o Histórico mostram sempre os mesmos números. Uma app de iPad que a App Store ainda está a instalar depois da atualização aparece como «ainda a instalar na App Store», sem nada para clicar: espere alguns minutos e verifique de novo. Um atualizador em segundo plano que foi iniciado mas não indicou resultado aparece como «sem resultado registado, nada para clicar»; a sua versão é lida de novo depois, por isso uma atualização concluída aparece como atualizada.

## Onde estão as coisas

| O quê | Onde |
|-------|------|
| Registos das execuções (guardados os 30 mais recentes) | `~/.local/state/mac-update/logs/` |
| As suas escolhas por app, o idioma e a lista das suas apps | `~/.config/mac-update/` (`overrides.tsv`, `lang`, `reports/`) |
| O programa | `~/.local/share/mac-update/` |

Para opções, variáveis de ambiente e resolução de problemas, veja [OPERATIONS.md](OPERATIONS.md). Para instalar, atualizar ou remover o programa, veja [INSTALL.md](../../INSTALL.md) e [UNINSTALL.md](../../UNINSTALL.md) (em inglês).
