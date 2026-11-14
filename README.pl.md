# macOS Updates

## Instalacja i użycie

Zainstaluj program z publicznego repozytorium, sprawdź gotowość i wyświetl podgląd aktualizacji.

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git
cd macOS_updates
bash setup.sh --inspect
bash build_inventory.sh --cli
bash update_all.sh --dry-run -y
bash update_all.sh
```

W obszarze roboczym sprawdzisz zainstalowane programy, wybory aktualizacji i wykluczenia. Zapisany wybór dotyczy tylko zatwierdzonego zakresu; nowy lub zmieniony zakres wymaga przeglądu. Niektóre aplikacje wymagają ręcznej aktualizacji.

Oczekujący lub niepotwierdzony proces może zablokować dalsze aktualizacje. Otwórz diagnostykę i sprawdź odzyskiwanie; nie usuwaj ręcznie dzienników ani blokad.

W sekcji Informacje przejrzyj i jawnie zastosuj aktualizację narzędzia. Przed zastosowaniem sprawdzane są lokalne zmiany.

```bash
bash uninstall.sh
```

Po wymianie publicznej historii zachowaj stary katalog i lokalne pliki. Aby zainstalować program ponownie, wybierz nowy, nieistniejący katalog i zastąp `vX.Y.Z` sprawdzonym tagiem wydania. Uruchom polecenie z katalogu zawierającego `install.sh`.

```bash
MAC_UPDATE_DIR="$HOME/Dev_Env/macOS_updates-new" MAC_UPDATE_REF="vX.Y.Z" bash install.sh
```
