# Guia do utilizador (Português)

**Versão:** 1.7.0 · **Apple Silicon, macOS 13+**

## Configuração segura e fontes das aplicações

`bash setup.sh --inspect` verifica a prontidão sem instalar dependências, alterar perfis ou configurar Touch ID. Uma ferramenta ausente deixa a função dependente indisponível. Num terminal, `bash setup.sh --install-dependencies` apresenta dependências opcionais e pergunta antes de cada instalação; `bash setup.sh --configure-shell` apresenta separadamente a alteração do perfil. Recusar uma dependência não bloqueia funções independentes. Sem Python, instale-o explicitamente antes de criar o inventário. `mas` ausente ou antigo é comunicado sem instalação ou atualização automática.

Esta é a versão do código 1.7.0 em main, sem uma etiqueta de lançamento separada. O gestor atua apenas sobre alvos instalados com origem observada e após nova aprovação. Os adaptadores genéricos nativos e dos fornecedores permanecem manuais até existirem receitas revistas. O catálogo público opcional abrange 48 produtos e oferece ligações oficiais revistas para obtenção manual; não há receitas aprovadas de primeira instalação automática. A lista de métodos abaixo descreve capacidades, não autoriza a execução. O relatório normal abrange aplicações instaladas. `bash scripts/report_update_coverage.sh --show-supported` continua a ser uma lista de referência. O menu opcional abre com `bash setup.sh --catalog` e não seleciona nada inicialmente. Após pré-visualização e nova aprovação, pode obter manualmente uma aplicação através de uma ligação oficial revista. Alterar a origem de uma aplicação existente exige migração manual. Um recibo App Store do CapCut mantém essa origem. Uma aplicação local sem propriedade Homebrew confirmada nunca é adotada automaticamente.

## O que faz

macOS Updates orquestra atualizações em **Macs Apple Silicon com macOS 13+**:

1. Pré-análise e inventário
2. App Store (`sudo mas upgrade <app-id>` + Track 2 GUI separado)
3. Primeiro as CLI nativas existentes, depois Node/Bun e alternativas npm
4. Homebrew (greedy apenas para casks registados como `brew_cask`)
5. Apps instaladas: handlers diretos, CLI ou acionadores integrados
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

Estados: **verified direct**, **triggered-unverified**, **externally managed**, **manual**, **unknown**. Um arranque silencioso não prova a atualização. Inkscape usa Homebrew; UniFi/WiFiman/Picsart Track 2; Office `msupdate`; Teams o próprio updater com fallback MAU `TEAMS21` observado e verificado. Atualmente nenhuma app registada é «manual»; o IPMIView usa App Store Track 2.

## Adicionar app da Internet

1. Instalar a app no Mac.
2. `bash build_inventory.sh`
3. `bash scripts/scaffold_internet_app.sh "Nome" silent_launch`
4. `bash run_tests.sh`

## Resolução de problemas

| Problema | Solução |
|----------|---------|
| Mac Intel | Não suportado |
| Catálogo errado | `bash build_inventory.sh` |
| App não atualiza | `bash scripts/report_update_coverage.sh` |
| Falta `APPLICATIONS.md` | `build_inventory.sh` ou `dev_sync/dev-sync-import.sh` |

Completo: [../../agents/troubleshooting.md](../../agents/troubleshooting.md)

A etapa C ativa inventário JSON local e planos com permissões específicas. `bash update_all.sh --plan` e `--dry-run` mostram as mesmas decisões sem gravar. Uma execução interativa pergunta uma vez pelos âmbitos mostrados; `-y`, EOF e execução sem terminal não concedem novas permissões. Use `--preferences` para rever ou repor escolhas. As atualizações preservam origem e destino observados; conflitos, destinos ausentes e provas incertas adiam esse destino. `build_inventory.sh --migration --preview` preserva bytes Markdown originais e notas; aceite explicitamente o ID mostrado. Atualizações genéricas do fabricante permanecem manuais até verificar identidade e adaptador. Uma entrada no catálogo não comprova instalação nem consentimento.


## Catálogo opcional e primeira instalação

Os novos sinais de aplicações são propostas para revisão, não receitas executáveis. `bash scripts/scan_update_feeds.sh` apresenta um resumo agregado. A exportação permite pré-visualizar e aceitar explicitamente; é redigida, fica local e nunca é carregada. `bash setup.sh --catalog` abre o catálogo sem seleções. `-y`, execuções não interativas e EOF não instalam nada. No menu, `check <number>` compara apenas as origens escolhidas. Os resultados indicam a versão estável compatível mais recente confirmada e a data; a cache dura 24 horas. O desconhecido continua desconhecido. Uma ficha pública da Mac App Store não prova que a aplicação é oferecida à sua conta. Nenhum canal é sempre o mais rápido.

O catálogo público tem 47 linhas de registo para 48 produtos e zero receitas aprovadas de primeira instalação automática. Após pré-visualização e nova confirmação, pode escolher ligações oficiais revistas para obtenção manual. Abrir uma página não instala a aplicação. Alterar a origem de uma aplicação existente exige migração manual. O InstallPlan separado mostra origem, destino, versão, requisitos e permissões; licença e custo desconhecidos são assim indicados. Qualquer receita automática futura precisa de nova aprovação de primeira instalação antes de ser ativada. O catálogo não promete instalar automaticamente todos os produtos.
