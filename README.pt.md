# Atualizações do macOS

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

**Versão 2.0.10** · Mac com Apple Silicon · macOS 13 ou posterior · [Site](https://macos-updates.64bit.site) · [Licença MIT](LICENSE) · [Alterações](CHANGELOG.md)

Um só comando, `mac-update`, mantém o software do seu Mac atualizado. Só mexe no que já está instalado.

## O que atualiza

Cada execução percorre estes grupos, por esta ordem:

1. Apps da App Store
2. Ferramentas do Terminal (npm, bun, ferramentas de linha de comandos)
3. Fórmulas e casks do Homebrew
4. Apps da internet (a partir do feed de atualizações do fabricante, de uma transferência direta verificada ou do atualizador da própria app)
5. A lista das suas apps
6. O macOS, sempre no fim

Não tem de aprovar app a app. Se quiser um comportamento diferente para uma app, defina-a como manual ou ignorar no separador **Apps**. O próprio macOS pode ser definido para instalar, só avisar ou desligado nas **Definições**.

## Instalação

Cole isto no Terminal:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/KasprowiczM/macOS_updates/releases/latest/download/install.sh)"
```

O instalador transfere o pacote da versão mais recente, verifica a sua soma de verificação SHA-256, coloca o programa em `~/.local/share/mac-update` e liga o comando `mac-update` em `~/.local/bin`. Não precisa de `git`, nunca usa `sudo` e mantém as suas definições quando atualiza. Para ver primeiro o que faria, junte `--dry-run`: `... install.sh | bash -s -- --dry-run`. Detalhes: [docs/INSTALL.md](docs/INSTALL.md) (em inglês).

Se o `mac-update` não for encontrado depois, abra uma nova janela do Terminal. Se continuar sem ser encontrado, execute o instalador novamente com `--configure-shell`.

## Primeira execução

```bash
mac-update
```

Num terminal, abre-se uma interface com separadores: Painel, Apps, Catálogo, Histórico, Definições, Diagnóstico, Ajuda. Escolha **Pré-visualizar (sem mudanças)** para ver o que aconteceria e depois **Atualizar tudo**. O ecrã de resultado mostra o que foi **Atualizadas**, o que está **Em dia** e o que **Precisam de si**, com um motivo e um próximo passo para cada uma.

Em texto simples: `mac-update run`. `mac-update --cli` (também `--plain`) é o mesmo que `mac-update run`, `mac-update --tui` é o mesmo que `mac-update` sozinho, e `macos-update` é o mesmo comando com um nome mais longo. Todos funcionam a partir de qualquer pasta. Pré-visualização em texto simples: `mac-update preview`. Verificar o Mac sem atualizar: `mac-update doctor`. Todos os comandos: `mac-update help`. Falta alguma coisa (Command Line Tools, Homebrew nativo, Python, `mas`)? `mac-update doctor` lista-o e `mac-update prepare` instala-o após uma única pergunta.

Vem de uma cópia antiga feita com git? Execute `mac-update migrate` para trazer as suas definições (mostra primeiro uma pré-visualização).

## Segurança

- As apps que tem abertas nunca são fechadas. São indicadas em «Precisam de si».
- As transferências vêm apenas de servidores permitidos e têm de passar na verificação da assinatura de código e no Gatekeeper.
- Uma atualização nunca instala uma app que não tem.
- Um item que falhe não impede os outros, e o macOS continua a ser atualizado no fim.
- As palavras-passe são escritas no terminal e nunca guardadas. Uma execução automática nunca faz perguntas.

## Execuções automáticas

Desativadas por defeito, sem hora predefinida. Para as ativar, abra as **Definições**, secção **Execuções automáticas**: escolha uma hora do dia, «ao iniciar sessão» ou ambos, e como quer ser notificado. Uma execução automática não instala atualizações do macOS, a menos que as ative. Veja [Operações](docs/user/pt/OPERATIONS.md).

## Documentação

| Idioma | Início rápido | Guia | Operações |
|--------|---------------|------|-----------|
| Português | [Início rápido](docs/user/pt/QUICK_START.md) | [Guia](docs/user/pt/GUIDE.md) | [Operações](docs/user/pt/OPERATIONS.md) |

Todos os idiomas: [docs/user/INDEX.md](docs/user/INDEX.md) · [Instalação](docs/INSTALL.md) (em inglês) · [Desinstalação](docs/UNINSTALL.md) (em inglês)

## Licença

[MIT](LICENSE)
