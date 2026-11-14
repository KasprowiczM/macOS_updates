# macOS Updates

## Instalação e utilização

Instale a partir do repositório público, verifique a preparação e pré-visualize as atualizações.

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git
cd macOS_updates
bash setup.sh --inspect
bash build_inventory.sh --cli
bash update_all.sh --dry-run -y
bash update_all.sh
```

No espaço de trabalho pode rever programas instalados, escolhas e exclusões. Uma escolha guardada cobre apenas o âmbito aprovado; alterações exigem revisão. Algumas aplicações exigem ação manual.

Um processo pendente ou não confirmado pode bloquear atualizações posteriores. Reveja a recuperação em Diagnóstico; não elimine registos nem bloqueios.

Em Acerca de, reveja e aplique explicitamente uma atualização da ferramenta. As alterações locais são verificadas.

```bash
bash uninstall.sh
```

Depois da substituição do histórico público, mantenha a pasta antiga e os seus ficheiros locais. Para uma nova instalação, escolha uma pasta que ainda não exista e substitua `vX.Y.Z` pela etiqueta de versão verificada. Execute o comando na pasta que contém `install.sh`.

```bash
MAC_UPDATE_DIR="$HOME/Dev_Env/macOS_updates-new" MAC_UPDATE_REF="vX.Y.Z" bash install.sh
```
