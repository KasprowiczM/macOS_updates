# macOS Updates

## Installation und Nutzung

Installiere das Programm aus dem öffentlichen Repository, prüfe die Bereitschaft und öffne die Vorschau.

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git
cd macOS_updates
bash setup.sh --inspect
bash build_inventory.sh --cli
bash update_all.sh --dry-run -y
bash update_all.sh
```

Im Arbeitsbereich prüfst du installierte Programme, Aktualisierungen und Ausschlüsse. Eine gespeicherte Auswahl gilt nur für den bestätigten Umfang; neue oder geänderte Bereiche erfordern eine Prüfung. Manche Apps erfordern manuelle Schritte.

Ein laufender oder unbestätigter Helfer kann spätere Updates blockieren. Prüfe die Wiederherstellung in der Diagnose; lösche Journale und Sperren nicht selbst.

Unter Informationen kannst du ein Programmupdate prüfen und ausdrücklich anwenden. Lokale Änderungen werden vorher geprüft.

```bash
bash uninstall.sh
```

Nach dem Ersetzen der öffentlichen Historie behalte den alten Checkout und deine lokalen Dateien. Wähle für eine Neuinstallation ein noch nicht vorhandenes Verzeichnis und ersetze `vX.Y.Z` durch den geprüften Release-Tag. Führe den Befehl im Verzeichnis mit `install.sh` aus.

```bash
MAC_UPDATE_DIR="$HOME/Dev_Env/macOS_updates-new" MAC_UPDATE_REF="vX.Y.Z" bash install.sh
```
