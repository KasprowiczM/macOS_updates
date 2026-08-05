# IMPLEMENTATION_LOG_2026-08-05.md

## FAZA 1 — Bugfixy krytyczne (blokujące bezobsługowość)

**Commit:** `[FAZA 1]` 965ac86  
**Data:** 2026-08-05  
**Wynik `run_tests.sh`:** ✅ 134 tests, ALL CHECKS PASSED  

---

### 1.1 — BUG-1: stdout pollution w `internet_handler_silent_launch`

**Co zrobiono:**
- Przerobiłem wszystkie 3 funkcje w `lib/internet_handlers.sh` na wzorzec `INTERNET_LAST_STATUS` globalny:
  - `internet_handler_silent_launch()` — L23,26: `echo` → `INTERNET_LAST_STATUS=`
  - `internet_handler_manual()` — L39: `echo` → `INTERNET_LAST_STATUS=`
  - `internet_handler_keystone()` — L88: `echo` → `INTERNET_LAST_STATUS=`
- Dodałem inicjalizację `INTERNET_LAST_STATUS=""` na górze pliku (L10)
- Dodałem komentarz nagłówkowy wyjaśniający kontrakt (L4-8)
- Zaktualizowałem `internet_dispatch_silent_launch()` (L104-110):
  - Usunięto `local st` i `st="$(internet_handler_silent_launch ...)"`
  - Bezpośrednie wywołanie + odczyt `$INTERNET_LAST_STATUS`

**Skan `lib/internet_app_updates.sh` (87 KB):**
- Jedyne wywołanie `$(internet_handler_...)` w command substitution było w `internet_handlers.sh:106` — to centralna dispatch. Żaden handler `iu_*` nie wywołuje `internet_handler_silent_launch` bezpośrednio.
- `internet_handler_keystone()` i `internet_handler_manual()` — zdefiniowane, ale niewywoływane z żadnego zewnętrznego pliku (keystone w `iu_google_chrome` używa `google_keystone_check`). Przerobiłem je mimo to dla konsystencji.

**Pliki zmienione:** `lib/internet_handlers.sh` (L1-10, L23, L26, L39, L88, L104-110)

---

### 1.2 — BUG-2: Settle-loop + literówki

**Co zrobiono:**

1. **Literówki naprawione** — zastąpione przez eliminację hardkodowanej listy:
   - `STATUS_PROTON_MAIL` (L468, L491) → nie istnieje już w kodzie
   - `STATUS_PROTON_DRIVE` (L468, L493) → nie istnieje już w kodzie
   - Kanoniczne nazwy (`STATUS_PROTONMAIL`, `STATUS_PROTONDRIVE`) są teraz czytane z configu

2. **Pełny skan rozbieżności STATUS_*:**
   | Zmienna w settle-loop | Zmienna w config | Init w orchestratorze | Podsumowanie | Status |
   |---|---|---|---|---|
   | `STATUS_PROTON_MAIL` | `STATUS_PROTONMAIL` | `STATUS_PROTONMAIL` | `$STATUS_PROTONMAIL` | LITERÓWKA — naprawiona |
   | `STATUS_PROTON_DRIVE` | `STATUS_PROTONDRIVE` | `STATUS_PROTONDRIVE` | `$STATUS_PROTONDRIVE` | LITERÓWKA — naprawiona |
   | Pozostałe 17 | zgodne | zgodne | zgodne | OK |

3. **Zastąpiono hardkodowaną listę 19 zmiennych** config-driven generowaniem z `config/internet_app_methods.txt`

4. **Zastąpiono hardkodowany case (19 gałęzi)** dynamicznym rozwiązywaniem ścieżek przez `capture_app_path` + `internet_app_path`

5. **Dodano twardy limit czasu i log diagnostyczny**: `Settle wait: Xs (limit Ys, N stable readings)`

**Pliki zmienione:** `update_internet_apps.sh` (L466-520)

---

### 1.3 — BUG-3: sudo keep-alive

**Co zrobiono:**
- Dodano subprocess keep-alive tuż po `sudo -v` (L207-220)
- Dodano bezwarunkowe kill w `cleanup_session_dir()` (L226-231)
- Warunki: `MAC_UPDATE_NO_SUDO_KEEPALIVE!=1` && `MAC_UPDATE_SKIP_SYSTEM!=1` && `[ -t 0 ]` && `sudo -n true` powiodło się

**Pliki zmienione:** `update_all.sh` (L207-220, L226-231)

---

### 1.4 — BUG-4: sudo -v stderr

**Co zrobiono:**
- `2>/dev/null` warunkowe — tylko gdy `MAC_UPDATE_JSON_SUMMARY=1`
- W trybie interaktywnym stderr PAM jest widoczne

**Pliki zmienione:** `update_all.sh` (L192-205)

---

### 1.5 — Testy regresyjne

4 nowe testy + potwierdzenie istniejącego testu i18n:

1. `test_internet_handlers_do_not_echo_status_in_command_substitution` — ✅
2. `test_internet_handlers_set_last_status_global` — ✅
3. `test_update_all_has_sudo_keepalive` — ✅
4. `test_settle_list_generated_from_config` — ✅
5. `test_all_languages_have_same_keys` — już istnieje jako `test_i18n_lang_files_key_parity` (L794-807)

**Pliki zmienione:** `tests/test_safety_static.py` (L1501-1569)

---

### Bramka wyjścia

| Sprawdzenie | Wynik |
|---|---|
| `bash run_tests.sh` | ✅ 134 tests, ALL CHECKS PASSED |
| `bash -n` na wszystkich skryptach | ✅ clean |
| `bash update_all.sh --dry-run -y` | ✅ bez błędów |
| `bash update_all.sh -y --skip-system` | Do uruchomienia interaktywnie |

### Nowe zmienne środowiskowe

| Zmienna | Domyślnie | Cel |
|---|---|---|
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | `0` | Wyłącza keep-alive sudo |

### Nowe klucze i18n

Brak — Faza 1 nie wymaga nowych kluczy.

### Odłożone

Pełny run `bash update_all.sh -y --skip-system` — wymaga interaktywnej sesji z zainstalowanymi aplikacjami. Weryfikacja poprawności UI do wykonania przy następnym runie.
