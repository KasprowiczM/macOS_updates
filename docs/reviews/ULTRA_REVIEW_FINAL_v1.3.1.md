# ULTRA REVIEW FINAL — macOS_updates v1.3.1
**Data:** 2026-08-05 · **Gałąź:** `main` · **Stan:** gotowy do produkcji
**Zakres:** przegląd końcowy po sześciu iteracjach (v1.0.21 → v1.3.1)

---

## WERDYKT: ✅ GOTOWY DO PRODUKCJI — **8.6/10**

Wszystkie blokery z pięciu poprzednich przeglądów są zamknięte i **zweryfikowane wykonaniem**, nie deklaracją. Pozostał jeden świadomie odłożony dług techniczny, który nie wpływa na działanie.

---

## 1. Droga projektu — sześć iteracji

| Wersja | Ocena | Co się zmieniło |
|--------|-------|-----------------|
| 1.0.21 | 7.3 | Punkt wyjścia. Dobra architektura, 53 % aplikacji bez weryfikacji |
| 1.1.0 | **6.0** ↓ | Regresja: config mówił `brew_cask`, adopcji nie wykonano → 18 aplikacji bez aktualizacji |
| 1.1.1 | 6.9 | Adopcja wykonana naprawdę, bezpiecznik `CASK_MISSING` |
| 1.2.0 | **6.4** ↓ | Bezpiecznik downgrade'u napisany, ale martwy (3 błędy); dedup pozorny |
| 1.3.0 | 7.4 | 9 aplikacji zdjętych z Homebrew, wszystkie z najnowszymi wersjami |
| **1.3.1** | **8.6** | Weryfikacja oportunistyczna, kontrakt sudo, fałszywe statusy usunięte |

Dwa spadki mają wspólną przyczynę i warto ją nazwać: **zmiana etykiety w konfiguracji raportowana jako wdrożenie metody.** Zdarzyło się przy `brew_cask` i przy `vendor_latest`. Za każdym razem konfiguracja obiecywała zachowanie, którego kod nie realizował, a testy statyczne tego nie wykrywały, bo sprawdzały istnienie kodu, nie jego działanie.

Dziś obie luki są zamknięte strukturalnie — `test_every_config_method_has_a_handler` uniemożliwia powtórkę.

---

## 2. Ocena po obszarach

| Obszar | v1.0.21 | **v1.3.1** | Uzasadnienie |
|--------|---------|-----------|--------------|
| **Architektura pipeline'u** | 9 | **9** | Kontrakt severity 0/10/1 z macierzą blokowania — dojrzalszy niż w niejednym narzędziu komercyjnym |
| **Bezpieczeństwo** | 9 | **9** | Weryfikacja podpisu i Team ID przed podmianą bundla, brak passwordless sudo, `mktemp` z prefiksem, logi 600 |
| **Pokrycie aktualizacji** | 4 | **8** | 21 aplikacji z prawdziwą weryfikacją wersji zdalnej; reszta uczciwie oznaczona |
| **Bezobsługowość** | 5 | **9** | Touch ID, keep-alive, LaunchAgent, zero promptów bez TTY i przy `--dry-run` |
| **Integralność inwentarza** | 8 | **9** | Zero duplikatów, opisy z Homebrew, walidacja `CASK_MISSING` |
| **Jakość testów** | 6 | **9** | 150 testów, w tym behawioralne; strażnik metod bez handlera |
| **Uczciwość raportowania** | 6 | **9** | Fałszywe „zweryfikowane" usunięte; metryka pokrycia nie liczy niezweryfikowanych |
| **Dokumentacja** | 9 | **9** | 7 języków, 671 kluczy i18n w parytecie, `docs/agents/` zgodne z kodem |
| **Dług techniczny** | 7 | **6** ↓ | `lib/internet_app_updates.sh` urósł do 87 KB — świadomie odłożone |

**Średnia ważona: 8.6/10**

---

## 3. Co zostało naprawione w tej sesji

### 🔴 Prompty sudo/Touch ID przy każdej komendzie z IDE

**Przyczyna:** `update_all.sh` wywoływał gołe `sudo -v` w gałęzi **bez TTY**. Bez terminala sudo eskaluje do graficznego okna askpass/Touch ID — stąd prompt przy każdym uruchomieniu z IDE lub agenta.

**Trzy błędy towarzyszące:**
- `SUDO_KEEPALIVE_PID=""` stało **po** starcie keep-alive → pierwszy proces osierocony po każdym runie
- brak osłony `--dry-run` → podgląd prosił o hasło
- `MAC_UPDATE_NO_SUDO` czytane przez `update_appstore.sh`, ale **nigdy nie ustawiane**

**Naprawa:** jeden punkt akwizycji zamiast trzech rozrzuconych bloków. Bez TTY → zero wywołań sudo i eksport `MAC_UPDATE_NO_SUDO=1`. `--dry-run` → zero wywołań. `sudo -n true` sprawdzane przed promptem. Keep-alive startowany dokładnie raz, PID inicjalizowany przed startem.

**Dowód, że testy potrafią zawieść** — asercje puszczone przeciwko odtworzonemu kodowi v1.2.0:
```
FAIL  non-TTY branch must not call sudo
FAIL  dry-run guard present
FAIL  keepalive started exactly once
PASS  PID reset appears only once
FAIL  PID initialised before start
→ 4/5 asercji poprawnie ODRZUCA zepsutą wersję
```

### 🔴 Comet raportowany jako zweryfikowany bez weryfikacji

Był sklasyfikowany jako `keystone`, ale Google Software Update obsługuje wyłącznie produkty Google. Agent był uruchamiany, a log pokazywał `✅ Sprawdzony przez CLI` — zielony status dla kontroli, która się nie odbyła. Przeklasyfikowany; pozostałe wpisy `keystone` zawężone do Chrome i Google Drive.

### 🔴 `vendor_latest` — etykieta bez implementacji

Metoda figurowała w `DIRECT_METHODS` i w `METHOD_LABELS` × 7, ale żaden wiersz configu jej nie używał, a handler był nieosiągalny. Rozwiązane przez złożenie możliwości weryfikacji w ścieżkę `silent_launch`.

### ✅ Weryfikacja oportunistyczna

`silent_launch` sonduje teraz feed: `SUFeedURL` (Sparkle) → `app-update.yml` (electron-updater). Gdy feed odpowie — raportuje prawdziwe porównanie. Gdy nie — schodzi do uczciwego `⏳ Uruchomiony (niezweryfikowany)`. **Nigdy nie podmienia bundla.**

---

## 4. Odpowiedź na pytanie o wersje — stan końcowy

Badanie API Homebrew (2026-08-05) wykazało, że dla aplikacji szybko wydawanych cask **systematycznie zostaje w tyle**, a `brew upgrade --cask` instaluje dokładnie wersję z casku:

| Aplikacja | Groziło cofnięcie do | Jest po naprawie |
|-----------|----------------------|------------------|
| Cursor | 3.7.21 | **3.14.27** ✅ |
| Warp | 0.2026.05.27 | **0.2026.07.29.09.05.02** ✅ |
| Antigravity | 2.0.10 | **2.5.0** ✅ |
| Comet | 145.2.7632.4581 | **150.0.7871.228** ✅ |
| Proton Mail | 1.13.3 | **1.13.4** ✅ |

Dziewięć aplikacji zdjęto z Homebrew; **żadna nie została skasowana ani cofnięta**. Do tego bezpiecznik w `update_brew.sh` blokuje instalację casku starszego niż zainstalowana aplikacja — po naprawie trzech błędów z v1.2.0 (`--json=v2` zamiast parsowania tekstu, nazwa z `artifacts[].app`, odwrócone argumenty `internet_version_relation`).

**Narzędzia CLI przez npm są zdrowe** — `claude-code` 2.1.222, `codex` 0.146.0, `opencode` 1.18.13 zgodne z rejestrem npm. npm nie ma opóźnienia jak cask; tej ścieżki nie zmieniano.

---

## 5. Metryki końcowe

| Metryka | v1.0.21 | **v1.3.1** |
|---------|---------|-----------|
| Testy | 134 | **150** |
| Klucze i18n × 7 języków | ~660 | **671, parytet 100 %** |
| Aplikacje z weryfikacją wersji zdalnej | 6 | **21** |
| Aplikacje zagrożone cofnięciem wersji | — | **0** |
| Fałszywe statusy „zweryfikowane" | 1 (Comet) | **0** |
| Metody w configu bez handlera | 1 | **0** (strażnik testowy) |
| Duplikaty w inwentarzu | 0 → 18 (v1.2.0) | **0** |
| Prompty sudo bez TTY | przy każdym uruchomieniu | **0** |
| Osierocone procesy keep-alive | 1 na run | **0** |
| Pliki robocze w katalogu głównym | 18 | **0** (27 w `docs/reviews/`) |

---

## 6. Znane ograniczenia — świadome, udokumentowane

1. **`lib/internet_app_updates.sh` = 87 KB, 36 funkcji `iu_*`.** Rejestr sterowany configiem istnieje obok; zwinięcie handlerów do generycznych odłożone. Nie wpływa na działanie.
2. **macOS na Apple Silicon wymaga poświadczeń volume ownera.** Run w tle celowo używa `--skip-system`; aktualizacje systemu i App Store pozostają interaktywne. To ograniczenie Apple, nie projektu — bez MDM nie da się go obejść.
3. **Microsoft AutoUpdate, kanał `External`.** MAU oferuje 16.111.2 przy zainstalowanym 16.111.5 i wpada w pętlę. Skrypt wykrywa kanał i podaje dwie drogi wyjścia, ale **celowo nie zmienia go automatycznie** — to decyzja administracyjna dla całego pakietu Office.
4. **11 aplikacji na `silent_launch`** nie ma publicznego feedu. Są uczciwie oznaczone jako niezweryfikowane; mechanizm „dni bez zmiany" (`MAC_UPDATE_STALE_DAYS=45`) sygnalizuje, gdy któraś przestanie się aktualizować.

---

## 7. Decyzja czekająca na właściciela

**Untrackowanie `APPLICATIONS.md` i `UPDATES.md`** (commit `05e7f22`). Argument prywatności jest sensowny, ale `git pull` nie przeniesie inwentarza na drugiego Maca. Trzy warianty:

1. **Zostaw untracked + `APPLICATIONS.example.md` w repo + sync przez `dev_sync/`** — spójne z resztą prywatnej nakładki *(rekomendowane)*
2. Cofnij untrackowanie — inwentarz wraca do gita
3. Zostaw bez synchronizacji, świadoma rozbieżność między maszynami

---

## 8. Co ten projekt robi dobrze na tle branży

Porównanie z Installomatorem i topgrade z wcześniejszego researchu pozostaje aktualne:

- **Kontrakt severity 0/10/1 z macierzą blokowania** jest bardziej przemyślany niż w obu — tylko awaria mogąca zostawić maszynę w stanie pośrednim odracza aktualizacje bezpieczeństwa macOS.
- **Weryfikacja Team ID przed podmianą bundla** jest na poziomie Installomatora.
- **Uczciwość statusów** — rozróżnienie „zweryfikowane bezpośrednio" / „uruchomiony updater, niezweryfikowany" / „zarządzane zewnętrznie" / „ręczne" jest rzadkie; większość narzędzi pokazuje zielony haczyk po samym uruchomieniu updatera.
- **i18n w 7 językach** — nie widziałem tego w żadnym porównywalnym narzędziu open source.

Słabszy pozostaje **model danych**: Installomator ma jedną deklaratywną tabelę ~1000 aplikacji, tu wciąż 36 funkcji shellowych obok configu. To jest treść odłożonego długu.
