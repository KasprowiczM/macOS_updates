# Guía de usuario (Español)

**Versión:** 1.6.3 · **Apple Silicon, macOS 13+**

## Configuración segura y fuentes de aplicaciones

`bash setup.sh --inspect` comprueba la preparación sin instalar dependencias, cambiar perfiles ni configurar Touch ID. Una herramienta ausente deja su función no disponible. En un terminal, `bash setup.sh --install-dependencies` muestra dependencias opcionales y pregunta antes de cada instalación; `bash setup.sh --configure-shell` presenta por separado el cambio de perfil. Rechazar una dependencia no bloquea funciones independientes. Si falta Python, instálalo explícitamente antes de crear el inventario. Un `mas` ausente o antiguo se indica sin instalarlo ni actualizarlo automáticamente.

El informe normal muestra aplicaciones instaladas. `bash scripts/report_update_coverage.sh --show-supported` muestra recetas ausentes del catálogo. Todavía no es un menú de instalación. Un recibo de App Store para CapCut conserva esa fuente incluso sin cask. Sin propiedad Homebrew confirmada se propone elegir fuente, sin adopción ni instalación. La resolución completa y selección interactiva corresponden a etapas posteriores.

## Qué hace

macOS Updates orquesta actualizaciones en **Macs Apple Silicon con macOS 13+**:

1. Escaneo previo e inventario
2. App Store (`sudo mas upgrade <app-id>` + Track 2 GUI separado)
3. Primero las CLI nativas existentes, después Node/Bun y alternativas npm
4. Homebrew (greedy solo para los casks registrados como `brew_cask`)
5. Apps instaladas: handlers directos, CLI o activadores integrados
6. Post-actualización atómica del inventario/historial
7. macOS (`softwareupdate -i <label> -R`) al final; aplazado ante un error bloqueante o falta de autorización

**No instala aplicaciones nuevas.** Cada Mac construye su inventario (`build_inventory.sh`).

## Instalación

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Informe de cobertura

```bash
bash scripts/report_update_coverage.sh
```

Estados: **verified direct**, **triggered-unverified**, **externally managed**, **manual**, **unknown**. Un inicio silencioso no prueba una actualización. Inkscape usa Homebrew; UniFi/WiFiman/Picsart Track 2; Office `msupdate`; Teams su propio updater con fallback MAU `TEAMS21` observado y verificado. Actualmente ninguna app registrada es «manual»; IPMIView usa App Store Track 2.

## Añadir app de Internet

1. Instalar la app en el Mac.
2. `bash build_inventory.sh`
3. `bash scripts/scaffold_internet_app.sh "Nombre" silent_launch`
4. `bash run_tests.sh`

## Solución de problemas

| Problema | Solución |
|----------|----------|
| Mac Intel | No compatible |
| Catálogo incorrecto | `bash build_inventory.sh` |
| App sin actualizar | `bash scripts/report_update_coverage.sh` |
| Falta `APPLICATIONS.md` | `build_inventory.sh` o `dev_sync/dev-sync-import.sh` |

Completo: [../../agents/troubleshooting.md](../../agents/troubleshooting.md)

La etapa C activa inventario JSON local y planes con permisos específicos. `bash update_all.sh --plan` y `--dry-run` muestran las mismas decisiones sin guardar. Un proceso interactivo pregunta una vez por los alcances mostrados; `-y`, EOF y ejecución desatendida no conceden permisos nuevos. Use `--preferences` para revisar o restablecer decisiones. Las actualizaciones conservan origen y destino observados; conflictos, destinos ausentes o evidencia incierta aplazan ese destino. `build_inventory.sh --migration --preview` conserva bytes originales de Markdown y notas; acepte expresamente el ID mostrado. Las actualizaciones genéricas del proveedor siguen siendo manuales hasta verificar identidad y adaptador. Una entrada de catálogo no demuestra instalación ni consentimiento.
