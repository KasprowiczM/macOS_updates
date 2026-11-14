# macOS Updates

## Installazione e uso

Installa dal repository pubblico, controlla la preparazione e visualizza l’anteprima degli aggiornamenti.

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git
cd macOS_updates
bash setup.sh --inspect
bash build_inventory.sh --cli
bash update_all.sh --dry-run -y
bash update_all.sh
```

Nello spazio di lavoro puoi verificare programmi installati, scelte ed esclusioni. Una scelta salvata copre solo l’ambito approvato; le modifiche richiedono una verifica. Alcune app richiedono interventi manuali.

Un processo in attesa o non confermato può bloccare gli aggiornamenti successivi. Controlla il recupero in Diagnostica; non eliminare registri o blocchi.

In Informazioni puoi esaminare e applicare esplicitamente un aggiornamento dello strumento. Le modifiche locali vengono controllate.

```bash
bash uninstall.sh
```

Dopo la sostituzione della cronologia pubblica, conserva la vecchia directory e i file locali. Per una nuova installazione scegli una directory inesistente e sostituisci `vX.Y.Z` con il tag di rilascio verificato. Esegui il comando dalla directory che contiene `install.sh`.

```bash
MAC_UPDATE_DIR="$HOME/Dev_Env/macOS_updates-new" MAC_UPDATE_REF="vX.Y.Z" bash install.sh
```
