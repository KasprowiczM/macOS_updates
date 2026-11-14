# Guia do utilizador (Português)

**Versão:** 1.8.2 · **Apple Silicon, macOS 13+**

## Interface de terminal

Num terminal interativo, `bash update_all.sh` abre o painel e apresenta o assistente até à sua conclusão. `bash setup.sh` abre o assistente e `bash build_inventory.sh` o inventário. Pode reabrir o assistente na navegação. A conclusão e as definições visuais são guardadas sem autorizar atualizações. `--cli` escolhe a interface de texto anterior e `--tui` pede explicitamente o painel. Opções como `--dry-run` continuam na CLI; não combine `--tui` com outras opções. `--tui` exige terminal funcional e Python. Chamadas não interativas ou sem TTY continuam na CLI.

Escolha os grupos antes de iniciar. A navegação fica à esquerda, ações e saída no centro e ajuda e detalhes à direita em todos os ecrãs. Apenas uma tarefa é supervisionada de cada vez; as confirmações existentes mantêm-se. As definições incluem idioma, tema, ASCII e tamanho automático. `?` abre a ajuda, Ctrl+P a paleta e `c` copia o comando, saída ou resumo em foco. Ctrl+V cola apenas na janela de resposta; Enter envia. A entrada é ocultada quando o processo desativa o eco.

São necessárias pelo menos 80 colunas e 24 linhas. Por defeito, são pedidas pelo menos 140 colunas e 38 linhas em terminais compatíveis e o tamanho original ao sair; o terminal pode ignorar os pedidos. O tamanho automático pode ser desativado.

## Configuração segura e fontes das aplicações

`bash setup.sh --inspect` verifica a prontidão sem instalar dependências, alterar perfis ou configurar Touch ID. Uma ferramenta ausente deixa a função dependente indisponível. Num terminal, `bash setup.sh --install-dependencies` apresenta dependências opcionais e pergunta antes de cada instalação; `bash setup.sh --configure-shell` apresenta separadamente a alteração do perfil. Recusar uma dependência não bloqueia funções independentes. Sem Python, instale-o explicitamente antes de criar o inventário. `mas` ausente ou antigo é comunicado sem instalação ou atualização automática.

O catálogo opcional começa sem seleções. O KeePassXC pode ser instalado pelo Homebrew com aprovação separada após nova verificação da origem e da ausência. A pré-visualização mostra o comando e os seus efeitos; a verificação usa o recibo do Homebrew. As restantes entradas mantêm as suas vias oficiais. As aplicações existentes nunca são migradas automaticamente.

Se o resultado de uma instalação do catálogo for incerto, volte a abrir o catálogo para uma nova verificação de recuperação. Não elimine bloqueios nem registos manualmente. A instalação do KeePassXC pelo Homebrew exige dados estáveis revistos válidos por sete dias; caso contrário, mantém-se a via manual.

## O que faz

macOS Updates orquestra atualizações em **Macs Apple Silicon com macOS 13+**:

1. Pré-análise e inventário
2. App Store (`sudo mas upgrade <app-id>` + Track 2 GUI separado)
3. Primeiro as CLI nativas existentes, depois Node/Bun e alternativas npm
4. Homebrew (greedy apenas para casks registados como `brew_cask`)
5. Apps instaladas: operações delimitadas após consentimento; atualizações de fornecedores não aceites permanecem manuais
6. Pós-atualização atómica do inventário/histórico
7. macOS (`softwareupdate -i <label> -R`) no fim; adiado após erro bloqueante ou sem autorização

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
2. `bash build_inventory.sh --cli`
3. `bash scripts/scaffold_internet_app.sh "/path/to/Observed.app" --json`
4. Reveja a proposta JSON sem execução; uma implementação posterior requer revisão e `bash run_tests.sh`.

Substitua o exemplo pelo caminho exato da aplicação instalada. O comando apresenta uma proposta com dados privados removidos para análise, sem execução. A exportação opcional exige repetir o comando com `--export --accept PREVIEW_ID` após rever o identificador apresentado. Ativar atualizações requer uma implementação revista e provas de aceitação separadas.

## Resolução de problemas

| Problema | Solução |
|----------|---------|
| Mac Intel | Não suportado |
| Catálogo errado | `bash build_inventory.sh --cli` |
| App não atualiza | `bash scripts/report_update_coverage.sh` |
| Falta `APPLICATIONS.md` | `build_inventory.sh` ou `dev_sync/dev-sync-import.sh` |

Completo: [../../agents/troubleshooting.md](../../agents/troubleshooting.md)

O inventário JSON local e os planos de ações delimitadas estão disponíveis. `bash update_all.sh --plan` e `--dry-run` mostram as mesmas decisões sem gravar. Uma execução interativa pergunta uma vez pelos âmbitos mostrados; `-y`, EOF e execução sem terminal não concedem novas permissões. Use `--preferences` para rever ou repor escolhas. As atualizações preservam origem e destino observados; conflitos, destinos ausentes e provas incertas adiam esse destino. `build_inventory.sh --migration --preview` preserva bytes Markdown originais e notas; aceite explicitamente o ID mostrado. Atualizações genéricas do fabricante permanecem manuais até verificar identidade e adaptador. Uma entrada no catálogo não comprova instalação nem consentimento.


## Catálogo opcional e primeira instalação

Os novos sinais de aplicações são propostas para revisão, não receitas executáveis. `bash scripts/scan_update_feeds.sh` apresenta um resumo agregado. A exportação permite pré-visualizar e aceitar explicitamente; é redigida, fica local e nunca é carregada. `bash setup.sh --catalog` abre o catálogo sem seleções. `-y`, execuções não interativas e EOF não instalam nada. No menu, `check <number>` compara apenas as origens escolhidas. Os resultados indicam a versão estável compatível mais recente confirmada e a data; a cache dura 24 horas. O desconhecido continua desconhecido. Uma ficha pública da Mac App Store não prova que a aplicação é oferecida à sua conta. Nenhum canal é sempre o mais rápido.

O catálogo opcional começa sem seleções. O KeePassXC pode ser instalado pelo Homebrew com aprovação separada após verificar a fonte e a ausência da aplicação. A pré-visualização mostra o comando e os efeitos declarados; a prova é o recibo Homebrew, não a aceitação de uma receita do fornecedor. As restantes entradas mantêm vias oficiais revistas. As aplicações existentes nunca são migradas automaticamente. As recomendações dependem dos dados disponíveis de versões estáveis.

## Estado local das atualizações por receita

O catálogo opcional começa sem seleções. O KeePassXC pode ser instalado pelo Homebrew com aprovação separada após verificar a fonte e a ausência da aplicação. A pré-visualização mostra o comando e os efeitos declarados; a prova é o recibo Homebrew, não a aceitação de uma receita do fornecedor. As restantes entradas mantêm vias oficiais revistas. As aplicações existentes nunca são migradas automaticamente. As recomendações dependem dos dados disponíveis de versões estáveis.

`--dry-run` mostra uma pré-visualização legível de até 10 alvos. `--dry-run --json-summary` ou `--plan` fornece o plano JSON completo. A pré-visualização não concede autorização nem executa atualizações.

A tela de permissões mostra dez itens elegíveis por página. Digite números como `1,3` para autorizar somente as ações exibidas; `n` e `p` mudam de página. Enter ou `q` continua sem novas permissões. O limite de 120 segundos é explicado; o fim do prazo não concede permissão. Itens bloqueados têm um resumo separado. Use `--preferences` para escolhas manuais, ignoradas ou adiadas. O registro começa antes dessa revisão.

## Controlos e lista de aplicações

Tab alterna entre navegação, área de trabalho, saída e botões inferiores. As setas selecionam, Espaço marca caixas e Enter ativa o botão realçado. As perguntas abrem automaticamente o campo de resposta. Enviar confirma; Cancelar fecha o campo sem responder.

O inventário mostra aplicações guardadas agrupadas por origem, com pesquisa, filtros e ordenação. Guardar seleção grava exclusões sem instalar ou desinstalar aplicações. Reativar exige consentimento separado para atualizar. A lista permanece visível após a simulação. O registo detalhado está separado do estado das aplicações.

Sobre contém o autor, ligações e a verificação explícita de atualizações da ferramenta. A pré-visualização fixa uma revisão. Aplicar fecha a interface e pede confirmação no terminal. Código alterado, um ramo inesperado ou conflitos de ficheiros bloqueiam a atualização. As alterações locais nunca são enviadas para o repositório do autor.

O modo automático usa a autorização guardada se abranger o grupo elegível; caso contrário oferece uma revisão AUTO separada. As janelas nativas autorizadas abrem em paralelo e as transferências partilham o grupo supervisionado; as tarefas Microsoft e Google são agrupadas. A gestão App Store e Homebrew permanece separada. DeepSeek Harness continua manual; Open Design indica atualmente um método automático indisponível. O fornecedor escolhe versões conforme as definições de canal existentes. Uma mudança de versão não prova a conclusão verificada. O trabalho não confirmado mantém o bloqueio do grupo e adia a atualização do sistema; Diagnóstico oferece recuperação explícita com nova verificação de identidade. O consentimento Google abrange todos os produtos registados no seu atualizador, incluindo fora do catálogo, cuja lista completa é desconhecida. Isto é separado da aceitação de uma receita para uma versão concreta. `bash update_all.sh --cli --automatic-internet-batch` apresenta a mesma revisão sem interface de terminal; adiciona `--dry-run` para uma simulação sem alterações.
