# Guia do utilizador (Português)

**Versão:** 1.8.0 · **Apple Silicon, macOS 13+**

## Interface de terminal

Num terminal interativo, `bash update_all.sh` abre o painel e apresenta o assistente até à sua conclusão. `bash setup.sh` abre o assistente e `bash build_inventory.sh` o inventário. Pode reabrir o assistente na navegação. A conclusão e as definições visuais são guardadas sem autorizar atualizações. `--cli` escolhe a interface de texto anterior e `--tui` pede explicitamente o painel. Opções como `--dry-run` continuam na CLI; não combine `--tui` com outras opções. `--tui` exige terminal funcional e Python. Chamadas não interativas ou sem TTY continuam na CLI.

Escolha os grupos antes de iniciar. A navegação fica à esquerda, ações e saída no centro e detalhes à direita quando há espaço. Apenas uma tarefa é supervisionada de cada vez; as confirmações existentes mantêm-se. As definições incluem idioma, tema, ASCII e tamanho automático. `?` abre a ajuda, Ctrl+P a paleta e `c` copia o comando, saída ou resumo em foco. Ctrl+V cola apenas na janela de resposta; Enter envia. A entrada é ocultada quando o processo desativa o eco.

São necessárias pelo menos 80 colunas e 24 linhas. Por defeito, são pedidas pelo menos 140 colunas e 38 linhas em terminais compatíveis e o tamanho original ao sair; o terminal pode ignorar os pedidos. O tamanho automático pode ser desativado.

## Configuração segura e fontes das aplicações

`bash setup.sh --inspect` verifica a prontidão sem instalar dependências, alterar perfis ou configurar Touch ID. Uma ferramenta ausente deixa a função dependente indisponível. Num terminal, `bash setup.sh --install-dependencies` apresenta dependências opcionais e pergunta antes de cada instalação; `bash setup.sh --configure-shell` apresenta separadamente a alteração do perfil. Recusar uma dependência não bloqueia funções independentes. Sem Python, instale-o explicitamente antes de criar o inventário. `mas` ausente ou antigo é comunicado sem instalação ou atualização automática.

Este guia descreve o macOS Updates 1.8.0. O gestor atua apenas sobre alvos instalados com origem observada e após nova aprovação. Os adaptadores genéricos nativos e dos fornecedores permanecem manuais até existirem receitas revistas. O catálogo público opcional abrange 48 produtos e oferece ligações oficiais revistas para obtenção manual; não há receitas aprovadas de primeira instalação automática. A lista de métodos abaixo descreve capacidades, não autoriza a execução. O relatório normal abrange aplicações instaladas. `bash scripts/report_update_coverage.sh --show-supported` continua a ser uma lista de referência. O menu opcional abre com `bash setup.sh --catalog` e não seleciona nada inicialmente. Após pré-visualização e nova aprovação, pode obter manualmente uma aplicação através de uma ligação oficial revista. Alterar a origem de uma aplicação existente exige migração manual. Um recibo App Store do CapCut mantém essa origem. Uma aplicação local sem propriedade Homebrew confirmada nunca é adotada automaticamente.

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

O catálogo público tem 47 linhas de registo para 48 produtos e zero receitas aprovadas de primeira instalação automática. Após pré-visualização e nova confirmação, pode escolher ligações oficiais revistas para obtenção manual. Abrir uma página não instala a aplicação. Alterar a origem de uma aplicação existente exige migração manual. O InstallPlan separado mostra origem, destino, versão, requisitos e permissões; licença e custo desconhecidos são assim indicados. Qualquer receita automática futura precisa de nova aprovação de primeira instalação antes de ser ativada. O catálogo não promete instalar automaticamente todos os produtos.

## Estado local das atualizações por receita

Este guia descreve o macOS Updates 1.8.0. O catálogo público inclui 48 produtos em 47 linhas de registo e zero receitas automáticas aprovadas para fornecedores, motor nativo ou primeira instalação. O gestor suporta operações delimitadas em alvos instalados após consentimento; atualizações de fornecedores sem receita aceite permanecem manuais. Os 48 dossiers e fixtures sintéticas não comprovam aceitação ao vivo. A aquisição direta de ZIP, a instalação explícita e o motor nativo estão implementados; a aceitação ao vivo T6 e a ativação T7 continuam pendentes. Não existe caminho force, adopt, migração ou bootstrap de dependências. As aplicações existentes do utilizador estão protegidas. As recomendações são estáveis por produto, sem classificação universal do canal mais rápido. Uma análise incompleta é um aviso, mas alvos inseguros são bloqueados; consulte o JSON. Os metadados Cask do host não são reparados. O scheduler permite no máximo duas mutações independentes entre checkouts cooperantes do mesmo utilizador do sistema; a execução pública permanece serial até à aceitação de efeitos independentes. A atualização do sistema obtém por último o bloqueio global exclusivo. Um reinício pendente ou helper desconhecido pode bloquear mutações até existir nova prova revista de reconciliação. Ainda não há timeout automático nem reconciliação no arranque. Consulte o [recibo central de implementação](../../implementation/RECIPE_VERIFICATION_2026-11-14.md). As aplicações abertas estão protegidas. DeepSeek Harness fica excluído até estar estável.

`--dry-run` mostra uma pré-visualização legível de até 10 alvos. `--dry-run --json-summary` ou `--plan` fornece o plano JSON completo. A pré-visualização não concede autorização nem executa atualizações.

A tela de permissões mostra dez itens elegíveis por página. Digite números como `1,3` para autorizar somente as ações exibidas; `n` e `p` mudam de página. Enter ou `q` continua sem novas permissões. O limite de 120 segundos é explicado; o fim do prazo não concede permissão. Itens bloqueados têm um resumo separado. Use `--preferences` para escolhas manuais, ignoradas ou adiadas. O registro começa antes dessa revisão.
