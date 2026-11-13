# Guia do utilizador (Português)

**Versão:** 1.6.3 · **Apple Silicon, macOS 13+**

## Configuração segura e fontes das aplicações

`bash setup.sh --inspect` verifica a prontidão sem instalar dependências, alterar perfis ou configurar Touch ID. Uma ferramenta ausente deixa a função dependente indisponível. Num terminal, `bash setup.sh --install-dependencies` apresenta dependências opcionais e pergunta antes de cada instalação; `bash setup.sh --configure-shell` apresenta separadamente a alteração do perfil. Recusar uma dependência não bloqueia funções independentes. Sem Python, instale-o explicitamente antes de criar o inventário. `mas` ausente ou antigo é comunicado sem instalação ou atualização automática.

O relatório normal mostra aplicações instaladas. `bash scripts/report_update_coverage.sh --show-supported` mostra receitas ausentes. Ainda não é um menu de instalação. Um recibo App Store do CapCut mantém essa fonte mesmo sem cask. Sem propriedade Homebrew confirmada, propõe-se escolher uma fonte sem adoção ou instalação. A resolução completa e a seleção interativa pertencem às etapas seguintes.

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
