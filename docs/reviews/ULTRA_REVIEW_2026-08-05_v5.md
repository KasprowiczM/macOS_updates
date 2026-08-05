# ULTRA REVIEW v5 — weryfikacja v1.3.0 + naprawa promptów sudo/Touch ID
**Data:** 2026-08-05 (noc) · **Stan:** v1.3.0, **niezacommitowane** · **Naprawa sudo wykonana w tej sesji**

---

## WERDYKT: 🟡 BARDZO BLISKO — 1 bloker funkcjonalny + porządki przed commitem

**Najważniejsze: cel biznesowy został osiągnięty.** Dziewięć aplikacji zdjęto z Homebrew i **wszystkie zachowały najnowsze wersje**:

| Aplikacja | Groziło cofnięcie do | Jest |
|-----------|----------------------|------|
| Comet | 145.2.7632.4581 | **150.0.7871.228** ✅ |
| Cursor | 3.7.21 | **3.14.27** ✅ |
| Warp | 0.2026.05.27 | **0.2026.07.29.09.05.02** ✅ |
| Antigravity | 2.0.10 | **2.5.0** ✅ |
| Proton Mail | 1.13.3 | **1.13.4** ✅ |
| Claude Desktop | — | **1.25927.0** ✅ |

Żadna aplikacja nie została skasowana przy odpinaniu casków. To był największy punkt ryzyka i przeszedł czysto.

Zostało: jeden bloker (`vendor_latest` to etykieta bez implementacji), zawyżona metryka pokrycia i porządki przed commitem.

---

## 1. Prompty sudo / Touch ID — przyczyna i naprawa (zrobione w tej sesji)

Twoje zgłoszenie: *„co chwilę pytał o sudo i Touch ID, jakby każda komenda w Antigravity IDE wymagała elewacji"*. Znalazłem trzy nakładające się błędy w `update_all.sh`.

### Przyczyna główna — `sudo -v` w gałęzi bez TTY

```bash
if [ "$_needs_sudo" -eq 1 ]; then
    if [ -t 0 ]; then
        ...
    else
        if ! sudo -v; then          # ← linia 229, gałąź BEZ terminala
```

Gdy skrypt jest uruchamiany z IDE, agenta albo dowolnego podprocesu, `stdin` nie jest terminalem. Kod wchodził do `else` i wywoływał **gołe `sudo -v`**. Bez terminala sudo eskaluje do **graficznego okna askpass / Touch ID** — i stąd prompt przy każdym uruchomieniu.

To dokładne odwrócenie kontraktu z poprzedniego promptu: bez TTY skrypt miał **nie pytać**, tylko ustawić `MAC_UPDATE_NO_SUDO=1` i pominąć kroki wymagające roota.

### Błąd drugi — osierocony proces keep-alive

```
226:        SUDO_KEEPALIVE_PID=$!      ← pierwszy keep-alive wystartował
240: SUDO_KEEPALIVE_PID=""            ← PID WYMAZANY
246:        SUDO_KEEPALIVE_PID=$!      ← drugi keep-alive
```

Blok inicjalizujący został wklejony **po** starcie pierwszego keep-alive. `cleanup_session_dir()` zabijał tylko drugi PID. Pierwszy zostawał **żywy po zakończeniu skryptu** — jeden osierocony proces odświeżający sudo na każde uruchomienie.

### Błąd trzeci — brak osłony `--dry-run`

`sudo -v` odpalało się także przy `--dry-run`. Podgląd nigdy nie powinien prosić o hasło.

### Błąd czwarty — `MAC_UPDATE_NO_SUDO` nigdy nie ustawiane

`update_appstore.sh:247` czyta tę zmienną, ale **nikt jej nie ustawiał**. Cała ścieżka „bez TTY pomiń tor roota" była martwa.

### Co naprawiłem

`update_all.sh` — jeden punkt decyzyjny zamiast trzech rozrzuconych:

```bash
SUDO_KEEPALIVE_PID=""                       # inicjalizacja PRZED startem

_needs_sudo=0
[ "${MAC_UPDATE_SKIP_APPSTORE:-0}" != "1" ] && _needs_sudo=1
[ "${MAC_UPDATE_SKIP_SYSTEM:-0}"   != "1" ] && _needs_sudo=1
[ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ] && _needs_sudo=0      # dry-run nigdy nie pyta

if [ "$_needs_sudo" -eq 1 ] && [ ! -t 0 ]; then
    export MAC_UPDATE_NO_SUDO=1              # bez TTY: nie pytaj, poinformuj dzieci
    print_info "$L_ALL_SUDO_NO_TTY"
    _needs_sudo=0
fi

if [ "$_needs_sudo" -eq 1 ]; then
    if sudo -n true 2>/dev/null; then
        :                                     # timestamp ciepły — nie pytaj ponownie
    elif ...
        sudo -v ...
    fi
    if [ "${MAC_UPDATE_NO_SUDO_KEEPALIVE:-0}" != "1" ] && sudo -n true 2>/dev/null; then
        ( while true; do sudo -n true 2>/dev/null || exit 0; sleep 50; done ) &
        SUDO_KEEPALIVE_PID=$!                 # startowany dokładnie raz
    fi
fi
```

Zmiany:
- **bez TTY → zero wywołań sudo**, `MAC_UPDATE_NO_SUDO=1` eksportowane do dzieci
- **`--dry-run` → zero wywołań sudo**
- **`sudo -n true` przed promptem** — ciepły timestamp nie powoduje ponownego pytania
- **keep-alive startowany raz**, PID inicjalizowany przed startem
- podpowiedź o Touch ID tylko tam, gdzie prompt może się faktycznie pojawić
- 3 nowe klucze i18n (`L_ALL_SUDO_NO_TTY`, `L_ALL_TOUCHID_HINT`, `L_ALL_SUDO_PREAUTH_FAILED`) — **7/7 języków, zweryfikowane**

### Cztery testy **behawioralne**

Dodałem do `tests/test_safety_static.py`:

| Test | Co sprawdza |
|------|-------------|
| `test_sudo_is_never_attempted_without_a_tty` | gałąź bez TTY eksportuje `MAC_UPDATE_NO_SUDO=1` i **nie zawiera** `sudo -v` / `sudo -A` / `sudo true` |
| `test_sudo_is_acquired_at_exactly_one_place` | dokładnie 2 wzajemnie wykluczające się wywołania, wszystkie w bloku akwizycji, `sudo -n true` **przed** promptem |
| `test_dry_run_never_requests_sudo` | osłona `MAC_UPDATE_DRY_RUN` obecna |
| `test_sudo_keepalive_pid_is_not_reset_after_start` | PID inicjalizowany przed startem, start dokładnie raz, brak drugiego resetu |

**Dowód, że testy potrafią zawieść** — puściłem asercje przeciwko odtworzonemu kodowi v1.2.0:
```
  FAIL  non-TTY branch must not call sudo
  FAIL  dry-run guard present
  FAIL  keepalive started exactly once
  PASS  PID reset appears only once
  FAIL  PID initialised before start
→ 4/5 asercji poprawnie ODRZUCA zepsutą wersję
```
To jest różnica względem testów, które krytykowałem w v4 — tamte przechodziły niezależnie od stanu kodu.

**`bash run_tests.sh` → 146/146 PASS.**

---

## 2. 🔴 BLOKER — `vendor_latest` to etykieta bez implementacji

```bash
grep -rn "vendor_latest" --include="*.sh" --include="*.py" .
→ scripts/report_update_coverage.sh:227
→ scripts/fix_inventory_dedup.py:7
```

**Nie istnieje żaden handler.** Ani `internet_handler_vendor_latest`, ani gałąź w dispatcherze. Dziewięć aplikacji spada do swoich starych funkcji `iu_*`, czyli zachowuje się jak `silent_launch`.

Widać to wprost w logu ostatniego runu:
```
ChatGPT / Codex:      ⏳ Uruchomiony (niezweryfikowany)
Comet:                ⏳ Uruchomiony (niezweryfikowany)
Antigravity:          ⏳ Uruchomiony (niezweryfikowany)
Cursor:               ⏳ Uruchomiony (niezweryfikowany)
Warp:                 ⏳ Uruchomiony (niezweryfikowany)
Proton Mail:          ⏳ Uruchomiony (niezweryfikowany)
Proton Drive:         ⏳ Uruchomiony (niezweryfikowany)
```

Cała idea `vendor_latest` — *odpytaj feed producenta, porównaj wersje, powiedz mi czy mam najnowsze* — nie została napisana. Zmieniono etykietę w configu.

**Dlaczego to boli akurat Ciebie:** to są dokładnie te aplikacje, o których powiedziałeś „muszę mieć zawsze najnowsze". Dziś nie masz **żadnego sygnału**, gdy któraś przestanie się aktualizować. Odzyskaliśmy je z Homebrew — ale wróciły do stanu „odpalone i nadzieja".

### 🔴 Konsekwencja: zawyżona metryka pokrycia

`scripts/report_update_coverage.sh:227`:
```python
DIRECT_METHODS = {"keystone", "github_dmg", "msupdate", "docker_cli", "sparkle_appcast", "vendor_latest"}
```

`vendor_latest` jest liczony jako **weryfikacja bezpośrednia**. Raport pokrycia twierdzi więc, że 9 aplikacji jest zweryfikowanych, podczas gdy żadna nie jest. **Metryka, którą oceniamy projekt, jest napompowana o 9 pozycji.**

Dodatkowo `vendor_latest` nie ma wpisu w `METHOD_LABELS` (7 sekcji językowych) — etykieta będzie pusta.

---

## 3. Pozostałe znaleziska

| # | Znalezisko | Waga |
|---|-----------|------|
| 1 | **Claude Desktop: `⏭️ Pominięty`** w podsumowaniu, a inwentarz ma `1.25927.0`. Handler szuka innej nazwy/ścieżki niż faktyczna | 🟡 |
| 2 | **ChatGPT Atlas: `⏭️ Nieznana wersja`** — `sparkle_appcast` nie parsuje feedu. Jedna z dwóch aplikacji na tej metodzie nie działa | 🟡 |
| 3 | **Nic nie zacommitowane** — 20+ zmodyfikowanych plików, `VERSION`=1.3.0, w `.git` leży `index.lock` po przerwanej operacji | 🟡 |
| 4 | `lib/internet_app_updates.sh` nadal ~86 KB, 36 funkcji `iu_*` — dług świadomie odłożony | 🟢 |

---

## 4. Co w v1.3.0 zweryfikowałem jako zrobione dobrze

| Element | Dowód |
|---------|-------|
| **F1 — bezpiecznik downgrade** | `update_brew.sh:240–283`: `brew info --json=v2`, nazwa aplikacji z `artifacts[].app`, **odwrócone argumenty** `internet_version_relation "$installed_ver" "$cask_ver"` = `"newer"` → downgrade. Wszystkie trzy błędy z v4 naprawione ✅ |
| **F2.2 — odpięcie 9 aplikacji** | `brew_cask` 19 → 11 w configu; §4c ma 12 casków; **wszystkie 9 aplikacji żyją z najnowszymi wersjami** ✅ |
| **F3 — deduplikacja** | Przekrój GRUPA 3 ↔ §4c przy normalizacji nazw: **0** (36 vs 12). Prawdziwa naprawa, nie pozorna. Dodano `scripts/fix_inventory_dedup.py` ✅ |
| **F3.3 — opisy casków** | 0 placeholderów `opis do uzupełnienia`, opisy pobrane z Homebrew ✅ |
| **F5.1 — READMEs** | Wszystkie 5 tłumaczeń dostało merytoryczne sekcje v1.3.0 (`vendor_latest`, flagi, downgrade guard). Pliki zmalały, bo rozwlekłą prozę zastąpiono listami — to legalna edycja, sprawdziłem diff ✅ |
| **Prawdziwe runy** | 4 runy 18:42–18:51, wszystkie kroki OK, brak `CASK_MISSING` ✅ |
| **Testy** | 146/146 PASS ✅ |

---

## 5. Metryki

| Metryka | v1.2.0 | **v1.3.0 (zweryfikowane)** |
|---------|--------|---------------------------|
| Aplikacje zagrożone cofnięciem | **4** | **0** ✅ |
| Bezpiecznik downgrade | martwy kod | **działa** ✅ |
| Aplikacje zdublowane w inwentarzu | **18** | **0** ✅ |
| Prompty sudo bez TTY | **przy każdym uruchomieniu** | **0** ✅ (naprawione dziś) |
| Osierocone procesy keep-alive | **1 na run** | **0** ✅ (naprawione dziś) |
| Aplikacje `vendor_latest` | 0 | 9 — **etykieta bez kodu** 🔴 |
| Aplikacje realnie zweryfikowane | ~14 | **~14** (raport twierdzi ~23) 🔴 |
| Placeholdery w §4c | 20 | **0** ✅ |
| Testy | 141 | **146** ✅ |
| Testy behawioralne dot. sudo | 0 | **4** ✅ |

---

## 6. Ocena

| Obszar | v1.2.0 | **v1.3.0** |
|--------|--------|-----------|
| Ochrona przed cofnięciem wersji | 5/10 | **9/10** ↑↑ |
| Integralność inwentarza | 4/10 | **9/10** ↑↑ |
| Bezobsługowość / brak promptów | 9/10 | **9/10** = (po naprawie z dziś) |
| **Weryfikacja „always latest"** | — | **3/10** 🔴 (etykieta bez kodu) |
| Wiarygodność metryk | 6/10 | **4/10** ↓ (pokrycie zawyżone o 9) |
| Jakość kodu | 7/10 | **8/10** ↑ |
| Jakość testów | 5/10 | **8/10** ↑↑ |
| Dokumentacja | 7/10 | **9/10** ↑ |

**Średnia: 7.4/10** (1.1.1: 6.9 · 1.2.0: 6.4)

Najlepszy stan projektu do tej pory. Do produkcji brakuje **jednej rzeczy z prawdziwą treścią** — implementacji `vendor_latest` — plus poprawki metryki i commita. To jest praca na jedno posiedzenie, nie na kolejną rundę.

Powtarzający się wzorzec, który warto nazwać wprost: **zmiana etykiety w configu jest raportowana jako wdrożenie metody.** Zdarzyło się to przy `brew_cask` (v1.1.0) i teraz przy `vendor_latest` (v1.3.0). Za każdym razem konfiguracja obiecuje zachowanie, którego kod nie realizuje. Dlatego finalny prompt wymaga dowodu w postaci **linii z logu runu pokazującej porównanie wersji zdalnej**, a nie wpisu w pliku.
