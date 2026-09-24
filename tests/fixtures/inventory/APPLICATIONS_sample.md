# 📱 ZAINSTALOWANE APLIKACJE — MacBook test (macOS 27.0 Golden Gate)

> **Data analizy:** 2026-09-24
> **Użytkownik:** test | **Home:** `/Users/test`
> **System:** macOS 27.0 Golden Gate (Build 26A123)
> **Architektura:** Apple Silicon (arm64)
> **Folder skryptów:** `/Users/test/macOS_updates`

---

## GRUPA 1 — Aplikacje Systemowe Apple 🍎

| Nazwa | Wersja |
|-------|--------|
| Safari | 27.0 |
| Finder | 26.3 |

---

## GRUPA 2 — Aplikacje z App Store 🛍️
> Aktualizowane: **App Store → Uaktualnienia**
> ✅ Narzędzie `mas` (CLI dla App Store) jest zainstalowane: `7.0.0`

| Nazwa | App ID |
|-------|--------|
| Amphetamine | 937984704 |
| Copilot | 6738511300 |
| Notion Web Clipper | 1559269364 |

| GarageBand 🆕 | 682658836 |

> ⚠️ **Aplikacje iPad na Apple Silicon** — widoczne w App Store ale nieobsługiwane przez `mas`:
> UniFi, WiFiman, Picsart — aktualizuj ręcznie przez App Store → Uaktualnienia.

---

## GRUPA 3 — Aplikacje pobrane z Internetu 🌐

### 🌐 Przeglądarki i Sieć

| Nazwa | Wersja | Strona aktualizacji |
|-------|--------|---------------------|
| Chrome | 153.0 | https://google.com/chrome |
| UniFi | 10.0 | https://ui.com |

### 🆕 Nowo wykryte aplikacje (do skategoryzowania)

| Nazwa | Producent | Strona aktualizacji |
|-------|-----------|---------------------|
| S2M | 🆕 do skategoryzowania | — |

---

## GRUPA 4 — Homebrew 🍺

### 4a. Kluczowe pakiety ⭐

| Pakiet | Wersja | Opis |
|--------|--------|------|
| mas | 7.0.0 | CLI for App Store |
| stale-pkg | 1.0.0 | Removed package |

### 4b. Formulae (zależności)

| Pakiet | Wersja | Opis |
|--------|--------|------|
| ca-certificates | 2026.1 | Common CA certificates |
| old-dep | 0.9.0 | Stale dependency |

### 4c. Casks (aplikacje GUI przez Homebrew)

| Pakiet | Wersja | Opis |
|--------|--------|------|
| appcleaner | 3.7 | Application uninstaller |
| stale-cask | 1.0.0 | Stale cask |

### 4d. Native CLI + npm global

| Pakiet | Wersja | Opis |
|--------|--------|------|
| bun | 1.4.2 | Bun runtime |
| gemini-cli | 0.46.0 | Google Gemini CLI (`gemini`) |
| qwen-code | 0.17.1 | Qwen Code CLI (`qwen`) |

---

## Podsumowanie

| Grupa | Liczba |
|-------|--------|
| 🍎 Systemowe Apple | 2 |
| 🛍️ App Store | 4 |
| 🌐 Pobrane z Internetu | 2 |
| 🆕 Do skategoryzowania | 1 |
| 🍺 Homebrew Formulae (kluczowe) | 2 |
| 🍺 Homebrew Formulae (biblioteki) | 2 |
| 🍺 Homebrew Casks | 2 |
| 🧰 Native CLI + npm | 3 |
| **RAZEM** | **18** |

---

## Legenda aktualizacji

| Metoda | Aplikacje |
|--------|-----------|
| 🤖 Auto (Skrypt `update_internet_apps.sh`) | Chrome |
| 🛍️ App Store / `sudo mas upgrade` | Amphetamine, Copilot |
| 🧰 Native CLI + npm (`update_npm_cli.sh`) | bun |
| 🍺 Homebrew `brew upgrade` | Wszystkie formulae i casks |

---
*Zaktualizowano: 2026-09-24 | macOS 27.0 Golden Gate arm64 | Użytkownik: test*
