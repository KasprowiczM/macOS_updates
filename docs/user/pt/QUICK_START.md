# Início rápido (Português)

**macOS Updates 2.0.10** · Mac com Apple Silicon · macOS 13 ou posterior · cerca de 5 minutos

O macOS Updates mantém atualizado o software que já está no seu Mac: apps da App Store, ferramentas do Terminal, pacotes do Homebrew, apps que transferiu da internet e o próprio macOS. Nunca instala apps que não tem.

## 1. Instalar

Cole isto no Terminal:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/KasprowiczM/macOS_updates/releases/latest/download/install.sh)"
```

O instalador transfere o pacote da versão, verifica a soma de verificação e acrescenta o comando `mac-update`. Não atualiza nada e não precisa de `git` nem de `sudo`. Precisa de Python 3.9 ou posterior (se faltar, o instalador diz-lhe para executar `xcode-select --install`). Detalhes: [INSTALL.md](../../INSTALL.md) (em inglês).

Depois, abra uma nova janela do Terminal para o comando ser encontrado. Se o `mac-update` continuar sem ser encontrado, execute o instalador novamente com `bash -s -- --configure-shell` a seguir ao pipe, como explica o INSTALL.md.

## 2. Pré-visualizar

```bash
mac-update
```

Num terminal, abre-se a interface no **Painel**. Passe para **Pré-visualizar (sem mudanças)** com a seta para a direita e prima Enter. Nada é instalado. Vê o que seria atualizado.

Prefere texto simples? Execute `mac-update preview`. `mac-update --cli` (também `--plain`) é o mesmo que `mac-update run`, `mac-update --tui` é o mesmo que `mac-update` sozinho, e `macos-update` é o mesmo comando com um nome mais longo. Todos funcionam a partir de qualquer pasta.

## 3. Atualizar

No Painel, escolha **Atualizar tudo** e prima Enter. Vê cada grupo (App Store, Ferramentas do Terminal, Homebrew, Apps da internet, Lista de apps, Sistema macOS) e cada app à medida que é atualizada. Se o macOS pedir a sua palavra-passe, escreva-a no terminal; o programa nunca a guarda.

Pode parar a qualquer momento. As apps já atualizadas continuam atualizadas.

## 4. Ler o resultado

O ecrã de resultado tem três listas:

- **Atualizadas**: estas apps estão agora em dia.
- **Em dia**: não foi preciso fazer nada.
- **Precisam de si**: o programa não conseguiu concluir estas sozinho. Cada linha diz porquê e o que fazer. Motivos típicos: a app estava aberta, a App Store precisa que inicie sessão ou é preciso reiniciar. Veja o [guia](GUIDE.md).

As apps que tem abertas nunca são fechadas. Feche-as e execute a atualização novamente.

## 5. Próximos passos

| Quero... | Faça isto |
|----------|-----------|
| Mudar a forma como uma app é atualizada | Separador Apps, Enter na app: automático, manual ou ignorar |
| Desativar um grupo ou as atualizações do macOS | Painel: vá ao grupo e prima Espaço. Ou Definições, «Atualizações do macOS» |
| Executar sem a interface | `mac-update run` |
| Verificar o Mac sem atualizar | `mac-update doctor` |
| Executar sozinho | Definições, secção «Execuções automáticas». Veja [OPERATIONS.md](OPERATIONS.md) |
| Ver o que correu mal | Separador Histórico, depois Enter numa execução para abrir o seu registo |
| Trazer as definições de uma cópia antiga com git | `mac-update migrate` (mostra primeiro uma pré-visualização) |

Mais: [GUIDE.md](GUIDE.md) · [OPERATIONS.md](OPERATIONS.md) · [UNINSTALL.md](../../UNINSTALL.md) (em inglês)
