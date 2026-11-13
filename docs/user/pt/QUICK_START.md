# Início rápido (Português)

**Mac com Apple Silicon obrigatório** · macOS 13+ · **v1.6.5**

## Configuração segura e fontes das aplicações

`bash setup.sh --inspect` verifica a prontidão sem instalar dependências, alterar perfis ou configurar Touch ID. Uma ferramenta ausente deixa a função dependente indisponível. Num terminal, `bash setup.sh --install-dependencies` apresenta dependências opcionais e pergunta antes de cada instalação; `bash setup.sh --configure-shell` apresenta separadamente a alteração do perfil. Recusar uma dependência não bloqueia funções independentes. Sem Python, instale-o explicitamente antes de criar o inventário. `mas` ausente ou antigo é comunicado sem instalação ou atualização automática.

O relatório normal mostra aplicações instaladas. `bash scripts/report_update_coverage.sh --show-supported` mostra receitas ausentes. Ainda não é um menu de instalação. Um recibo App Store do CapCut mantém essa fonte mesmo sem cask. Sem propriedade Homebrew confirmada, propõe-se escolher uma fonte sem adoção ou instalação. A resolução completa e a seleção interativa pertencem às etapas seguintes.

## Instalação numa linha

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Novo utilizador (apenas GitHub)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh --inspect
bash build_inventory.sh
bash update_all.sh
```


## Proprietário (GitHub + overlay Proton Drive)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

Os ficheiros privados (`APPLICATIONS.md`, `UPDATES.md`, `.env`) vêm do overlay na nuvem — não do GitHub.

## Comandos úteis

| Comando | Finalidade |
|---------|------------|
| `bash update_all.sh --dry-run -y` | Pré-visualizar todos os passos |
| `bash update_system.sh` | Apenas macOS |
| `bash update_appstore.sh` | Apenas App Store |
| `bash update_brew.sh` | Apenas Homebrew |
| `bash run_tests.sh` | Verificar a instalação |

Consulte [GUIDE.md](GUIDE.md) e [OPERATIONS.md](OPERATIONS.md).

A etapa B (1.6.2) acrescenta um inventário de observação opcional: `bash build_inventory.sh --shadow`. Guarda identidades locais, provas das fontes e análises incompletas em JSON privado, sem alterar `APPLICATIONS.md` nem a execução das atualizações. `--dry-run` impede a gravação, `--json` devolve resultados estruturados e várias opções `--root CAMINHO` indicam diretórios. Os conflitos são observações; a escolha de fontes e os controlos de execução pertencem à etapa C.
