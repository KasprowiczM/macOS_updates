"""lib/python/inventory_sync.py — Complete inventory synchronization without drift.

Synchronizes all groups in APPLICATIONS.md (Apple System, App Store, iPad,
Internet apps, Homebrew Formulae, Casks, Native CLI) against current system
facts, recomputes the summary and legend, and guards against flaky wipes.
"""

from __future__ import annotations

import json
import os
import plistlib
import re
import shutil
import subprocess
from datetime import datetime
from typing import Callable, Dict, List, Optional, Set, Tuple

import brew_casks
from inventory import APP_ALIASES, norm_name


def minimal_template(
    user: Optional[str] = None,
    os_label: Optional[str] = None,
    build: Optional[str] = None,
    home: Optional[str] = None,
    script_dir: Optional[str] = None,
    today: Optional[str] = None,
    run: Callable = subprocess.run,
) -> str:
    """Standardized minimal template for APPLICATIONS.md."""
    if user is None:
        user = os.environ.get("USER", "user")
    if build is None:
        try:
            build = run(["sw_vers", "-buildVersion"], capture_output=True, text=True).stdout.strip() or "unknown"
        except Exception:
            build = "unknown"
    if os_label is None:
        try:
            pv = run(["sw_vers", "-productVersion"], capture_output=True, text=True).stdout.strip() or "unknown"
            major = int(pv.split(".", 1)[0]) if pv and pv[0].isdigit() else 0
        except Exception:
            pv, major = "unknown", 0
        codename = {13: "Ventura", 14: "Sonoma", 15: "Sequoia", 26: "Tahoe", 27: "Golden Gate"}.get(major, "")
        os_label = f"macOS {pv}" + (f" {codename}" if codename else "")
    if home is None:
        home = os.path.expanduser("~")
    if script_dir is None:
        script_dir = os.environ.get("SCRIPT_DIR", "")
    if today is None:
        today = datetime.now().strftime("%Y-%m-%d")
    return (
        f"# 📱 ZAINSTALOWANE APLIKACJE — MacBook {user} ({os_label})\n\n"
        f"> **Data analizy:** {today}\n"
        f"> **Użytkownik:** {user} | **Home:** `{home}`\n"
        f"> **System:** {os_label} (Build {build})\n"
        f"> **Architektura:** Apple Silicon (arm64)\n"
        f"> **Folder skryptów:** `{script_dir}`\n\n"
        "---\n\n"
        "## GRUPA 1 — Aplikacje Systemowe Apple 🍎\n\n"
        "| Nazwa | Wersja |\n"
        "|-------|--------|\n\n"
        "---\n\n"
        "## GRUPA 2 — Aplikacje z App Store 🛍️\n"
        "> Aktualizowane: **App Store → Uaktualnienia**\n\n"
        "| Nazwa | App ID |\n"
        "|-------|--------|\n\n"
        "### 📱 Aplikacje iPad na Apple Silicon (App Store)\n\n"
        "| Nazwa | App ID | Wersja |\n"
        "|-------|--------|--------|\n\n"
        "> **Uwaga:** Aplikacje iPad działające na Apple Silicon pobrane z App Store.\n\n"
        "---\n\n"
        "## GRUPA 3 — Aplikacje pobrane z Internetu 🌐\n\n"
        "### ☁️ Przechowywanie w chmurze\n\n"
        "| Nazwa | Wersja | Strona aktualizacji |\n"
        "|-------|--------|---------------------|\n\n"
        "---\n\n"
        "## GRUPA 4 — Homebrew 🍺\n\n"
        "### 4a. Kluczowe pakiety ⭐\n\n"
        "| Pakiet | Wersja | Opis |\n"
        "|--------|--------|------|\n\n"
        "### 4b. Formulae (zależności)\n\n"
        "| Pakiet | Wersja | Opis |\n"
        "|--------|--------|------|\n\n"
        "### 4c. Casks (aplikacje GUI przez Homebrew)\n\n"
        "| Pakiet | Wersja | Opis |\n"
        "|--------|--------|------|\n\n"
        "### 4d. Native CLI + npm global\n\n"
        "| Pakiet | Wersja | Opis |\n"
        "|--------|--------|------|\n\n"
        "> **Uwaga:** Native CLI + npm żyją poza Homebrew.\n\n"
        "---\n\n"
        "## Podsumowanie\n\n"
        "| Grupa | Liczba |\n"
        "|-------|--------|\n"
        "| 🍎 Systemowe Apple | 0 |\n"
        "| 🛍️ App Store | 0 |\n"
        "| 📱 App Store — iPad | 0 |\n"
        "| 🌐 Pobrane z Internetu | 0 |\n"
        "| 🍺 Homebrew Formulae (kluczowe) | 0 |\n"
        "| 🍺 Homebrew Formulae (biblioteki) | 0 |\n"
        "| 🍺 Homebrew Casks | 0 |\n"
        "| 🧰 Native CLI + npm | 0 |\n"
        "| **RAZEM** | **0** |\n\n"
        "---\n\n"
        "## Legenda aktualizacji\n\n"
        "| Metoda | Aplikacje |\n"
        "|--------|-----------|\n\n"
        "---\n"
        f"*Zaktualizowano: {today} | {os_label} arm64 | Użytkownik: {user}*\n"
    )


def section_span(md: str, heading_re: str) -> Optional[Tuple[int, int]]:
    """Return (start, end) byte-slice of a section from heading_re to next same/higher heading or EOF."""
    m = re.search(heading_re, md, re.MULTILINE)
    if not m:
        return None
    start = m.start()
    matched_heading = m.group(0).lstrip()
    level = len(matched_heading) - len(matched_heading.lstrip('#'))
    if level == 0:
        level = 2

    # Next heading of level <= level
    pattern = rf'^\s*#{{1,{level}}}\s+'
    next_m = re.search(pattern, md[m.end():], re.MULTILINE)
    if next_m:
        end = m.end() + next_m.start()
    else:
        end = len(md)
    return start, end


def _count_table_data_rows(text: str) -> int:
    """Count markdown table data rows (ignoring header and separator)."""
    count = 0
    header_keywords = {"nazwa", "nazwa aplikacji", "pakiet", "grupa", "metoda", "komponent"}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith('|'):
            continue
        parts = [p.strip() for p in line.split('|')[1:-1]]
        if not parts:
            continue
        if all(re.match(r'^-+$', p) for p in parts):
            continue
        if any(p.lower() in header_keywords for p in parts):
            continue
        count += 1
    return count


def sync_mas_group(
    md: str,
    mas_apps: Optional[Dict[str, Tuple[str, str]]],
) -> Tuple[str, List[str], List[str]]:
    """Sync GRUPA 2 App Store table with installed mas apps.

    mas_apps: dict of adam_id -> (name, version).
    Returns (new_md, added_ids, removed_ids).
    """
    if mas_apps is None:
        return md, [], []

    span = section_span(md, r'^## GRUPA 2\b')
    if not span:
        return md, [], []

    start, end = span
    sec_text = md[start:end]

    # Find the boundary for the main table (before iPad subsection or legacy quote block)
    ipad_m = re.search(
        r'(### 📱 Aplikacje iPad\b|> ⚠️ \*\*Aplikacje iPad\b)',
        sec_text,
    )
    if ipad_m:
        main_part = sec_text[:ipad_m.start()]
        tail_part = sec_text[ipad_m.start():]
    else:
        # Check if there is a trailing separator before next section
        sep_m = re.search(r'\n---\s*$', sec_text)
        if sep_m:
            main_part = sec_text[:sep_m.start()]
            tail_part = sec_text[sep_m.start():]
        else:
            main_part = sec_text
            tail_part = ""

    # Extract all 2-column rows: | Name | <6+ digits> |
    row_re = re.compile(r'^\s*\|\s*([^|\n]+?)\s*\|\s*(\d{6,})\s*\|\s*$', re.MULTILINE)
    existing_rows: Dict[str, str] = {}
    for m in row_re.finditer(main_part):
        raw_name = m.group(1).strip()
        app_id = m.group(2).strip()
        clean_name = raw_name.replace(" 🆕", "").strip()
        existing_rows[app_id] = clean_name

    removed_ids = [aid for aid in existing_rows if aid not in mas_apps]
    added_ids = [aid for aid in mas_apps if aid not in existing_rows]

    # Collect final rows: keep existing name (clean) or use mas name
    final_rows: List[Tuple[str, str]] = []
    for aid, (mas_name, _) in mas_apps.items():
        name = existing_rows.get(aid, mas_name).strip()
        final_rows.append((name, aid))

    final_rows.sort(key=lambda r: r[0].lower())

    # Build the single new table
    table_lines = ["| Nazwa | App ID |", "|-------|--------|"]
    for name, aid in final_rows:
        table_lines.append(f"| {name} | {aid} |")
    new_table_str = "\n".join(table_lines) + "\n"

    # In main_part, keep leading quote lines and header
    lines = main_part.splitlines()
    header_lines: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## GRUPA 2") or line.startswith(">") or line.strip() == "":
            header_lines.append(line)
            i += 1
        else:
            break

    # Strip trailing blank lines from header
    while header_lines and header_lines[-1].strip() == "":
        header_lines.pop()

    new_sec_text = "\n".join(header_lines) + "\n\n" + new_table_str + "\n" + tail_part
    new_md = md[:start] + new_sec_text + md[end:]
    return new_md, added_ids, removed_ids


def refresh_system_line(md: str, os_label: str, build: str) -> str:
    """Replace the first `> **System:** ...` line with `> **System:** {os_label} (Build {build})`."""
    return re.sub(
        r'^>\s*\*\*System:\*\*.*$',
        f'> **System:** {os_label} (Build {build})',
        md,
        count=1,
        flags=re.MULTILINE,
    )


def sync_ipad_section(
    md: str,
    ipad_apps: Optional[List[Tuple]],
) -> Tuple[str, int]:
    """Sync the iPad applications subsection inside GRUPA 2.

    ipad_apps: list of (app_name, app_id, version[, item_name]).
    Returns (new_md, count).
    """
    if ipad_apps is None:
        return md, 0

    sorted_apps = sorted(ipad_apps, key=lambda a: a[0].lower())
    rows = ["| Nazwa | App ID | Wersja |", "|-------|--------|--------|"]
    for item in sorted_apps:
        name = item[0]
        aid = item[1]
        ver = item[2]
        rows.append(f"| {name} | {aid} | {ver} |")

    table_text = "\n".join(rows)
    new_subsection = (
        "### 📱 Aplikacje iPad na Apple Silicon (App Store)\n\n"
        f"{table_text}\n\n"
        "> **Uwaga:** Aplikacje iPad działające na Apple Silicon pobrane z App Store.\n"
    )

    span = section_span(md, r'^## GRUPA 2\b')
    if not span:
        return md, 0

    start, end = span
    sec_text = md[start:end]

    # Look for existing iPad subsection
    existing_sub = re.search(r'### 📱 Aplikacje iPad.*?(?=\n---|\n##|\Z)', sec_text, re.DOTALL)
    if existing_sub:
        sec_text = sec_text[:existing_sub.start()] + new_subsection + sec_text[existing_sub.end():]
    else:
        # Look for legacy quote block: > ⚠️ **Aplikacje iPad...
        legacy_quote = re.search(r'> ⚠️ \*\*Aplikacje iPad.*?(?=\n---|\n##|\Z)', sec_text, re.DOTALL)
        if legacy_quote:
            sec_text = sec_text[:legacy_quote.start()] + new_subsection + sec_text[legacy_quote.end():]
        else:
            # Insert before trailing separator or at end
            sep_m = re.search(r'\n---\s*$', sec_text)
            if sep_m:
                sec_text = sec_text[:sep_m.start()] + "\n" + new_subsection + "\n" + sec_text[sep_m.start():]
            else:
                sec_text = sec_text.rstrip() + "\n\n" + new_subsection

    new_md = md[:start] + sec_text + md[end:]
    return new_md, len(sorted_apps)


def remove_names_from_group3(
    md: str,
    names: Set[str],
) -> Tuple[str, List[str]]:
    """Remove table rows from GRUPA 3 whose first cell matches any in names (normalized + aliases)."""
    if not names:
        return md, []

    span = section_span(md, r'^## GRUPA 3\b')
    if not span:
        return md, []

    norm_targets = set()
    for n in names:
        if not n:
            continue
        norm_targets.add(norm_name(n))
        for key, val_list in APP_ALIASES.items():
            if n == key or n in val_list:
                norm_targets.add(norm_name(key))
                norm_targets.update(norm_name(a) for a in val_list)

    start, end = span
    sec_text = md[start:end]

    lines = sec_text.splitlines(True)
    new_lines: List[str] = []
    removed: List[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith('|'):
            new_lines.append(line)
            continue
        parts = [p.strip() for p in stripped.split('|')[1:-1]]
        if not parts:
            new_lines.append(line)
            continue
        cell = parts[0]
        # Skip headers / separators
        if cell in ("Nazwa", "Nazwa aplikacji", "Pakiet") or re.match(r'^-+$', cell):
            new_lines.append(line)
            continue
        # Clean cell formatting (strip bold, architecture markers, emoji)
        clean_cell = re.sub(r'^\*\*(.*?)\*\*$', r'\1', cell).strip()
        if norm_name(clean_cell) in norm_targets:
            removed.append(clean_cell)
            continue
        new_lines.append(line)

    new_sec_text = "".join(new_lines)
    new_md = md[:start] + new_sec_text + md[end:]
    return new_md, removed


def sync_formulae(
    md: str,
    installed: Optional[Set[str]],
) -> Tuple[str, List[str]]:
    """Remove rows in 4a and 4b whose formula name is not in installed."""
    if installed is None:
        return md, []

    span = section_span(md, r'^## GRUPA 4\b')
    if not span:
        return md, []

    start, end = span
    sec_text = md[start:end]

    installed_clean = {f.strip() for f in installed}
    removed: List[str] = []

    def _filter_sub_table(sub_heading_re: str, text: str) -> str:
        sub_span = section_span(text, sub_heading_re)
        if not sub_span:
            return text
        s_start, s_end = sub_span
        sub_text = text[s_start:s_end]
        lines = sub_text.splitlines(True)
        out_lines: List[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped.startswith('|'):
                out_lines.append(line)
                continue
            parts = [p.strip() for p in stripped.split('|')[1:-1]]
            if not parts:
                out_lines.append(line)
                continue
            pkg = parts[0]
            if pkg in ("Pakiet", "Nazwa") or re.match(r'^-+$', pkg):
                out_lines.append(line)
                continue
            if pkg not in installed_clean:
                removed.append(pkg)
                continue
            out_lines.append(line)
        return text[:s_start] + "".join(out_lines) + text[s_end:]

    sec_text = _filter_sub_table(r'^### 4a\b', sec_text)
    sec_text = _filter_sub_table(r'^### 4b\b', sec_text)

    new_md = md[:start] + sec_text + md[end:]
    return new_md, removed


def sync_casks(
    md: str,
    installed_nonorphan: Optional[Set[str]],
) -> Tuple[str, List[str]]:
    """Remove rows in 4c whose cask name is not in installed_nonorphan."""
    if installed_nonorphan is None:
        return md, []

    span = section_span(md, r'^## GRUPA 4\b')
    if not span:
        return md, []

    start, end = span
    sec_text = md[start:end]
    nonorphan_clean = {c.strip() for c in installed_nonorphan}
    removed: List[str] = []

    sub_span = section_span(sec_text, r'^### 4c\b')
    if not sub_span:
        return md, []

    s_start, s_end = sub_span
    sub_text = sec_text[s_start:s_end]
    lines = sub_text.splitlines(True)
    out_lines: List[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith('|'):
            out_lines.append(line)
            continue
        parts = [p.strip() for p in stripped.split('|')[1:-1]]
        if not parts:
            out_lines.append(line)
            continue
        token = parts[0]
        if token in ("Pakiet", "Nazwa") or re.match(r'^-+$', token):
            out_lines.append(line)
            continue
        if token not in nonorphan_clean:
            removed.append(token)
            continue
        out_lines.append(line)

    sec_text = sec_text[:s_start] + "".join(out_lines) + sec_text[s_end:]
    new_md = md[:start] + sec_text + md[end:]
    return new_md, removed


def rebuild_cli_section(
    md: str,
    clis: Optional[List[Tuple[str, str]]],
) -> Tuple[str, List[str], List[str]]:
    """Rebuild section 4d with detected CLIs, preserving existing descriptions."""
    if clis is None:
        return md, [], []

    span = section_span(md, r'^## GRUPA 4\b')
    if not span:
        return md, [], []

    start, end = span
    sec_text = md[start:end]

    sub_span = section_span(sec_text, r'^### 4d\b')
    if not sub_span:
        return md, [], []

    s_start, s_end = sub_span
    sub_text = sec_text[s_start:s_end]

    # Collect existing descriptions
    existing_desc: Dict[str, str] = {}
    row_re = re.compile(r'^\s*\|\s*([^|\n]+?)\s*\|\s*([^|\n]+?)\s*\|\s*([^|\n]*?)\s*\|\s*$', re.MULTILINE)
    for m in row_re.finditer(sub_text):
        name = m.group(1).strip()
        desc = m.group(3).strip()
        if name not in ("Pakiet", "Nazwa") and not re.match(r'^-+$', name):
            existing_desc[name] = desc

    detected_names = {c[0] for c in clis}
    added = [c[0] for c in clis if c[0] not in existing_desc]
    removed = [n for n in existing_desc if n not in detected_names]

    rows = ["| Nazwa | Wersja | Opis |", "|-------|--------|------|"]
    for name, ver in clis:
        desc = existing_desc.get(name, "—")
        rows.append(f"| {name} | {ver} | {desc} |")
    new_table = "\n".join(rows)

    # In 4d, preserve leading heading and trailing notes
    lines = sub_text.splitlines()
    header_line = "### 4d. Native CLI + npm global"
    notes: List[str] = []
    for line in lines:
        if line.strip().startswith(">"):
            notes.append(line)

    notes_str = "\n\n" + "\n".join(notes) if notes else ""
    sep_m = re.search(r'\n+---\s*$', sub_text)
    sep_str = "\n\n---\n" if sep_m else "\n"
    new_sub = f"{header_line}\n\n{new_table}{notes_str}{sep_str}"

    sec_text = sec_text[:s_start] + new_sub + sec_text[s_end:]
    new_md = md[:start] + sec_text + md[end:]
    return new_md, added, removed


def recompute_summary(md: str) -> str:
    """Rewrite ## Podsumowanie with exact counts according to Dodatek E."""
    # 1. System Apple: GRUPA 1
    g1_span = section_span(md, r'^## GRUPA 1\b')
    g1_count = _count_table_data_rows(md[g1_span[0]:g1_span[1]]) if g1_span else 0

    # 2. App Store: GRUPA 2 main table (excluding iPad subsection)
    g2_count = 0
    g_ipad_count = 0
    g2_span = section_span(md, r'^## GRUPA 2\b')
    if g2_span:
        g2_text = md[g2_span[0]:g2_span[1]]
        ipad_m = re.search(r'### 📱 Aplikacje iPad\b', g2_text)
        if ipad_m:
            g2_main = g2_text[:ipad_m.start()]
            ipad_sub = g2_text[ipad_m.start():]
            g_ipad_count = _count_table_data_rows(ipad_sub)
        else:
            g2_main = g2_text
        g2_count = _count_table_data_rows(g2_main)

    # 3. Pobrane z Internetu: all tables in GRUPA 3 excluding 🆕
    g3_count = 0
    g_new_count = 0
    g3_span = section_span(md, r'^## GRUPA 3\b')
    if g3_span:
        g3_text = md[g3_span[0]:g3_span[1]]
        new_m = re.search(r'### 🆕 Nowo wykryte aplikacje\b', g3_text)
        if new_m:
            new_span = section_span(g3_text, r'### 🆕 Nowo wykryte aplikacje\b')
            if new_span:
                g_new_count = _count_table_data_rows(g3_text[new_span[0]:new_span[1]])
                # Exclude the 🆕 subsection from g3_text
                g3_text_without_new = g3_text[:new_span[0]] + g3_text[new_span[1]:]
                g3_count = _count_table_data_rows(g3_text_without_new)
            else:
                g3_count = _count_table_data_rows(g3_text)
        else:
            g3_count = _count_table_data_rows(g3_text)

    # 4. Homebrew 4a, 4b, 4c, 4d
    g4a_count = 0
    g4b_count = 0
    g4c_count = 0
    g4d_count = 0
    g4_span = section_span(md, r'^## GRUPA 4\b')
    if g4_span:
        g4_text = md[g4_span[0]:g4_span[1]]
        s4a = section_span(g4_text, r'^### 4a\b')
        if s4a:
            g4a_count = _count_table_data_rows(g4_text[s4a[0]:s4a[1]])
        s4b = section_span(g4_text, r'^### 4b\b')
        if s4b:
            g4b_count = _count_table_data_rows(g4_text[s4b[0]:s4b[1]])
        s4c = section_span(g4_text, r'^### 4c\b')
        if s4c:
            g4c_count = _count_table_data_rows(g4_text[s4c[0]:s4c[1]])
        s4d = section_span(g4_text, r'^### 4d\b')
        if s4d:
            g4d_count = _count_table_data_rows(g4_text[s4d[0]:s4d[1]])

    total = (
        g1_count
        + g2_count
        + g_ipad_count
        + g3_count
        + g_new_count
        + g4a_count
        + g4b_count
        + g4c_count
        + g4d_count
    )

    rows = [
        "## Podsumowanie\n",
        "| Grupa | Liczba |",
        "|-------|--------|",
        f"| 🍎 Systemowe Apple | {g1_count} |",
        f"| 🛍️ App Store | {g2_count} |",
        f"| 📱 App Store — iPad | {g_ipad_count} |",
        f"| 🌐 Pobrane z Internetu | {g3_count} |",
    ]
    if g_new_count > 0:
        rows.append(f"| 🆕 Do skategoryzowania | {g_new_count} |")
    rows.extend([
        f"| 🍺 Homebrew Formulae (kluczowe) | {g4a_count} |",
        f"| 🍺 Homebrew Formulae (biblioteki) | {g4b_count} |",
        f"| 🍺 Homebrew Casks | {g4c_count} |",
        f"| 🧰 Native CLI + npm | {g4d_count} |",
        f"| **RAZEM** | **{total}** |",
    ])
    new_summary_text = "\n".join(rows) + "\n"

    sum_span = section_span(md, r'^## Podsumowanie\b')
    if sum_span:
        start, end = sum_span
        sep_m = re.search(r'\n+---\s*$', md[start:end])
        trailing = "\n\n---\n\n" if sep_m else "\n\n"
        return md[:start] + new_summary_text.rstrip() + trailing + md[end:].lstrip('\n')
    else:
        # Append before Legenda or EOF
        leg_span = section_span(md, r'^## Legenda aktualizacji\b')
        if leg_span:
            return md[:leg_span[0]] + new_summary_text.rstrip() + "\n\n---\n\n" + md[leg_span[0]:]
        return md.rstrip() + "\n\n" + new_summary_text.rstrip() + "\n"


def rebuild_legend(md: str, rows: List[Tuple[str, str]]) -> str:
    """Rewrite ## Legenda aktualizacji table."""
    table_lines = [
        "## Legenda aktualizacji\n",
        "| Metoda | Aplikacje |",
        "|--------|-----------|",
    ]
    for method, apps in rows:
        table_lines.append(f"| {method} | {apps} |")
    new_leg_text = "\n".join(table_lines) + "\n"

    leg_span = section_span(md, r'^## Legenda aktualizacji\b')
    if leg_span:
        start, end = leg_span
        sub_text = md[start:end]
        footer_m = re.search(r'\n+---\s*\n+(\*[^\n]+\*)\s*$', sub_text)
        if footer_m:
            footer = "\n\n---\n" + footer_m.group(1).strip() + "\n"
        else:
            sep_m = re.search(r'\n+---\s*$', sub_text)
            footer = "\n\n---\n" if sep_m else "\n"
        return md[:start] + new_leg_text.rstrip() + footer + md[end:].lstrip('\n')
    return md.rstrip() + "\n\n" + new_leg_text.rstrip() + "\n"


def legend_rows(
    methods_rows: List[str],
    installed_names: Set[str],
    casks: Set[str],
    mas_names: List[str],
    ipad_names: List[str],
    cli_names: List[str],
) -> List[Tuple[str, str]]:
    """Build legend rows matching the repository standard."""
    auto_apps: List[str] = []
    mau_apps: List[str] = []

    norm_installed = {norm_name(n) for n in installed_names if n}

    def _is_app_installed(app: str) -> bool:
        if not norm_installed:
            return True
        if norm_name(app) in norm_installed:
            return True
        for key, val_list in APP_ALIASES.items():
            if app == key or app in val_list:
                if norm_name(key) in norm_installed:
                    return True
                for a in val_list:
                    if norm_name(a) in norm_installed:
                        return True
        return False

    for line in methods_rows:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 2:
            continue
        app = parts[0]
        method = parts[1]
        if not _is_app_installed(app):
            continue
        if method == "msupdate":
            mau_apps.append(app)
        elif method not in ("mas", "appstore_gui", "brew_cask", "manual"):
            if app not in auto_apps:
                auto_apps.append(app)

    rows: List[Tuple[str, str]] = []
    if auto_apps:
        rows.append(("🤖 Auto (Skrypt `update_internet_apps.sh`)", ", ".join(auto_apps)))
    if mau_apps:
        rows.append(("💼 Microsoft AutoUpdate (`msupdate`)", ", ".join(mau_apps)))
    if mas_names:
        sorted_mas = sorted(mas_names, key=lambda s: s.lower())
        rows.append(("🛍️ App Store / `sudo mas upgrade`", ", ".join(sorted_mas)))
    if ipad_names:
        sorted_ipad = sorted(ipad_names, key=lambda s: s.lower())
        rows.append(("📱 App Store — iPad (Track 2 GUI / ręcznie)", ", ".join(sorted_ipad)))
    if cli_names:
        rows.append(("🧰 Native CLI + npm (`update_npm_cli.sh`)", ", ".join(cli_names)))
    rows.append(("🍺 Homebrew `brew upgrade`", "Wszystkie formulae i casks"))
    return rows


def detect_cli_versions(
    manifest_path: str,
    home: str,
    which: Callable[[str], Optional[str]] = shutil.which,
    run: Callable = subprocess.run,
    as_records: bool = False,
) -> List[Any]:
    """Detect versions of CLIs declared in manifest_path (display_name, version)."""
    if not os.path.isfile(manifest_path):
        return []

    def candidate_path(command: str) -> Optional[str]:
        if not re.fullmatch(r'[A-Za-z0-9._+-]+', command):
            return None
        roots = [
            os.path.join(home, '.local', 'bin'),
            os.path.join(home, '.local', 'share', 'mac-update', 'npm-global', 'bin'),
            os.path.join(home, '.local', 'share', 'mac-update', 'node', 'bin'),
            os.path.join(home, '.bun', 'bin'),
        ]
        for root in roots:
            path = os.path.join(root, command)
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        return which(command)

    detected: List[Any] = []
    try:
        with open(manifest_path, encoding='utf-8') as handle:
            for raw in handle:
                raw = raw.split('#', 1)[0].strip()
                if not raw:
                    continue
                fields = raw.split('|')
                if len(fields) != 5:
                    continue
                display, package, _method, _brew_formula, command = fields
                path = candidate_path(command)
                if not path:
                    continue
                args = [path, '-v' if display in ('node', 'claude-code') else '--version']
                try:
                    res = run(args, capture_output=True, text=True, timeout=10)
                except (OSError, subprocess.SubprocessError):
                    continue
                if res.returncode != 0:
                    continue
                first = (res.stdout or res.stderr).strip().splitlines()
                if not first:
                    continue
                version = first[0].strip()
                if display == 'claude-code':
                    version = version.split()[0]
                elif display == 'codex-cli':
                    version = version.split()[-1]
                elif display != 'node':
                    version = version.split()[0]
                if version.startswith('v'):
                    version = version[1:]
                if as_records:
                    detected.append((display, package, version, command, path))
                else:
                    detected.append((display, version))
    except OSError:
        return []

    return detected


def gather_facts(
    script_dir: str,
    home: str,
    run: Callable = subprocess.run,
) -> Dict:
    """Gather live facts about installed software from system queries.

    Any failed source sets its key to None.
    """
    facts: Dict = {
        "mas": None,
        "formulae": None,
        "casks_nonorphan": None,
        "orphans": None,
        "clis": None,
        "ipad": None,
        "installed_app_names": set(),
        "methods_rows": [],
    }

    # 1. mas list --json (fallback text)
    try:
        res = run(["mas", "list", "--json"], capture_output=True, text=True, timeout=30)
        mas_dict: Dict[str, Tuple[str, str]] = {}
        parsed_any = False
        if res.returncode == 0:
            raw_out = res.stdout.strip()
            if not raw_out:
                facts["mas"] = {}
            else:
                if raw_out.startswith('['):
                    try:
                        arr = json.loads(raw_out)
                        for item in arr:
                            aid = str(item.get("adamID") or item.get("id") or "")
                            name = str(item.get("name", ""))
                            ver = str(item.get("version", "?"))
                            if aid:
                                mas_dict[aid] = (name, ver)
                                parsed_any = True
                    except json.JSONDecodeError:
                        pass
                else:
                    for line in raw_out.splitlines():
                        if not line.strip():
                            continue
                        try:
                            obj = json.loads(line)
                            aid = str(obj.get("adamID") or obj.get("id") or "")
                            name = str(obj.get("name", ""))
                            ver = str(obj.get("version", "?"))
                            if aid:
                                mas_dict[aid] = (name, ver)
                                parsed_any = True
                        except json.JSONDecodeError:
                            pass
                if parsed_any:
                    facts["mas"] = mas_dict

        # If returncode != 0 or returncode == 0 with non-empty stdout but 0 items parsed: fallback to text mas list
        if facts["mas"] is None:
            res_txt = run(["mas", "list"], capture_output=True, text=True, timeout=30)
            if res_txt.returncode == 0:
                mas_dict = {}
                for line in res_txt.stdout.strip().splitlines():
                    m = re.match(r'^\s*(\d+)\s+(.+?)\s+\(([^()]+)\)$', line)
                    if m:
                        mas_dict[m.group(1)] = (m.group(2).strip(), m.group(3).strip())
                facts["mas"] = mas_dict
            else:
                facts["mas"] = None
    except Exception:
        facts["mas"] = None

    # 2. formulae (brew list --formula)
    try:
        res = run(["brew", "list", "--formula"], capture_output=True, text=True, timeout=60)
        if res.returncode == 0:
            facts["formulae"] = {l.strip() for l in res.stdout.splitlines() if l.strip()}
    except Exception:
        pass

    # 3. casks & orphans
    try:
        res = run(["brew", "list", "--cask"], capture_output=True, text=True, timeout=60)
        if res.returncode == 0:
            all_casks = [l.strip() for l in res.stdout.splitlines() if l.strip()]
            app_dirs = ["/Applications", os.path.join(home, "Applications")]
            # Check orphan casks
            info_res = run(["brew", "info", "--json=v2", "--cask"] + all_casks, capture_output=True, text=True, timeout=90)
            orphans: List[str] = []
            if info_res.returncode == 0:
                try:
                    cask_data = json.loads(info_res.stdout)
                    orphans = brew_casks.find_orphan_casks(cask_data, app_dirs)
                except Exception:
                    pass
            orphan_set = set(orphans)
            facts["orphans"] = orphans
            facts["casks_nonorphan"] = {c for c in all_casks if c not in orphan_set}
    except Exception:
        pass

    # 4. CLIs
    manifest_path = os.path.join(script_dir, "config", "npm_global_clis.txt")
    facts["clis"] = detect_cli_versions(manifest_path, home, run=run)

    # 5. iPad apps from /Applications and ~/Applications
    ipad_apps: List[Tuple[str, str, str, str]] = []
    app_dirs = ["/Applications", os.path.join(home, "Applications")]
    installed_names: Set[str] = set()

    for ad in app_dirs:
        if not os.path.isdir(ad):
            continue
        try:
            for item in os.listdir(ad):
                if not item.endswith(".app"):
                    continue
                app_name = item[:-4]
                installed_names.add(app_name)
                meta_path = os.path.join(ad, item, "Wrapper", "iTunesMetadata.plist")
                if os.path.isfile(meta_path):
                    try:
                        with open(meta_path, "rb") as fp:
                            meta = plistlib.load(fp)
                        item_id = str(meta.get("itemId", ""))
                        ver = str(meta.get("bundleShortVersionString", ""))
                        item_name = str(meta.get("itemName") or meta.get("bundleDisplayName") or "")
                        if item_id:
                            ipad_apps.append((app_name, item_id, ver, item_name))
                    except Exception:
                        pass
        except OSError:
            pass

    facts["ipad"] = ipad_apps
    facts["installed_app_names"] = installed_names

    # 6. config/internet_app_methods.txt
    methods_path = os.path.join(script_dir, "config", "internet_app_methods.txt")
    if os.path.isfile(methods_path):
        try:
            with open(methods_path, encoding="utf-8") as f:
                facts["methods_rows"] = [l.strip() for l in f if l.strip()]
        except OSError:
            pass

    return facts


def sync_all(
    md: str,
    facts: Dict,
    methods_rows: Optional[List[str]] = None,
) -> Tuple[str, Dict]:
    """Apply all inventory synchronizations in fixed order with safety guards."""
    report: Dict = {
        "mas_added": [],
        "mas_removed": [],
        "ipad_count": 0,
        "group3_removed": [],
        "formulae_removed": [],
        "casks_removed": [],
        "clis_added": [],
        "clis_removed": [],
        "skipped_groups": [],
    }

    if methods_rows is None:
        methods_rows = facts.get("methods_rows") or []

    new_md = md

    # 1. Sync MAS Group 2
    mas_apps = facts.get("mas")
    if mas_apps is not None:
        g2_span = section_span(new_md, r'^## GRUPA 2\b')
        old_g2_count = _count_table_data_rows(new_md[g2_span[0]:g2_span[1]]) if g2_span else 0
        cand_md, a_ids, r_ids = sync_mas_group(new_md, mas_apps)
        cand_g2_span = section_span(cand_md, r'^## GRUPA 2\b')
        cand_count = _count_table_data_rows(cand_md[cand_g2_span[0]:cand_g2_span[1]]) if cand_g2_span else 0
        if old_g2_count > 0 and (len(mas_apps) == 0 or cand_count == 0):
            report["skipped_groups"].append("GRUPA 2")
        else:
            new_md = cand_md
            report["mas_added"] = a_ids
            report["mas_removed"] = r_ids

    # 2. Sync iPad section
    ipad_apps = facts.get("ipad")
    if ipad_apps is not None:
        new_md, ipad_count = sync_ipad_section(new_md, ipad_apps)
        report["ipad_count"] = ipad_count

    # 3. Remove App Store & iPad apps from Group 3
    names_to_remove_from_g3: Set[str] = set()
    if mas_apps:
        for aid, (name, _) in mas_apps.items():
            names_to_remove_from_g3.add(name)
    if ipad_apps:
        for item in ipad_apps:
            names_to_remove_from_g3.add(item[0])
            if len(item) > 3 and item[3]:
                names_to_remove_from_g3.add(item[3])

    casks_nonorphan = facts.get("casks_nonorphan")
    if casks_nonorphan:
        for c in casks_nonorphan:
            names_to_remove_from_g3.add(c)

    g3_span = section_span(new_md, r'^## GRUPA 3\b')
    old_g3_count = _count_table_data_rows(new_md[g3_span[0]:g3_span[1]]) if g3_span else 0

    candidate_md, g3_removed = remove_names_from_group3(new_md, names_to_remove_from_g3)
    cand_g3_span = section_span(candidate_md, r'^## GRUPA 3\b')
    cand_g3_count = _count_table_data_rows(candidate_md[cand_g3_span[0]:cand_g3_span[1]]) if cand_g3_span else 0

    if old_g3_count > 0 and cand_g3_count == 0:
        report["skipped_groups"].append("GRUPA 3")
    else:
        new_md = candidate_md
        report["group3_removed"] = g3_removed

    # 4. Sync formulae
    formulae = facts.get("formulae")
    if formulae is not None:
        g4_span = section_span(new_md, r'^## GRUPA 4\b')
        old_form_count = 0
        if g4_span:
            g4_text = new_md[g4_span[0]:g4_span[1]]
            for sub in (r'^### 4a\b', r'^### 4b\b'):
                sp = section_span(g4_text, sub)
                if sp:
                    old_form_count += _count_table_data_rows(g4_text[sp[0]:sp[1]])

        cand_md, form_removed = sync_formulae(new_md, formulae)
        cand_g4_span = section_span(cand_md, r'^## GRUPA 4\b')
        cand_form_count = 0
        if cand_g4_span:
            cand_g4_text = cand_md[cand_g4_span[0]:cand_g4_span[1]]
            for sub in (r'^### 4a\b', r'^### 4b\b'):
                sp = section_span(cand_g4_text, sub)
                if sp:
                    cand_form_count += _count_table_data_rows(cand_g4_text[sp[0]:sp[1]])

        if old_form_count > 0 and (len(formulae) == 0 or cand_form_count == 0):
            report["skipped_groups"].append("Homebrew Formulae")
        else:
            new_md = cand_md
            report["formulae_removed"] = form_removed

    # 5. Sync casks
    if casks_nonorphan is not None:
        g4_span = section_span(new_md, r'^## GRUPA 4\b')
        old_cask_count = 0
        if g4_span:
            g4_text = new_md[g4_span[0]:g4_span[1]]
            sp = section_span(g4_text, r'^### 4c\b')
            if sp:
                old_cask_count += _count_table_data_rows(g4_text[sp[0]:sp[1]])

        cand_md, cask_removed = sync_casks(new_md, casks_nonorphan)
        cand_g4_span = section_span(cand_md, r'^## GRUPA 4\b')
        cand_cask_count = 0
        if cand_g4_span:
            cand_g4_text = cand_md[cand_g4_span[0]:cand_g4_span[1]]
            sp = section_span(cand_g4_text, r'^### 4c\b')
            if sp:
                cand_cask_count += _count_table_data_rows(cand_g4_text[sp[0]:sp[1]])

        if old_cask_count > 0 and (len(casks_nonorphan) == 0 or cand_cask_count == 0):
            report["skipped_groups"].append("Homebrew Casks")
        else:
            new_md = cand_md
            report["casks_removed"] = cask_removed

    # 6. Rebuild CLI section
    clis = facts.get("clis")
    if clis is not None:
        g4_span = section_span(new_md, r'^## GRUPA 4\b')
        old_cli_count = 0
        if g4_span:
            g4_text = new_md[g4_span[0]:g4_span[1]]
            sp = section_span(g4_text, r'^### 4d\b')
            if sp:
                old_cli_count += _count_table_data_rows(g4_text[sp[0]:sp[1]])

        cand_md, clis_added, clis_removed = rebuild_cli_section(new_md, clis)
        cand_g4_span = section_span(cand_md, r'^## GRUPA 4\b')
        cand_cli_count = 0
        if cand_g4_span:
            cand_g4_text = cand_md[cand_g4_span[0]:cand_g4_span[1]]
            sp = section_span(cand_g4_text, r'^### 4d\b')
            if sp:
                cand_cli_count += _count_table_data_rows(cand_g4_text[sp[0]:sp[1]])

        if old_cli_count > 0 and (len(clis) == 0 or cand_cli_count == 0):
            report["skipped_groups"].append("Native CLI")
        else:
            new_md = cand_md
            report["clis_added"] = clis_added
            report["clis_removed"] = clis_removed

    # 7. Recompute summary table
    new_md = recompute_summary(new_md)

    # 8. Rebuild legend
    mas_names = [v[0] for v in (mas_apps or {}).values()]
    ipad_names = [a[0] for a in (ipad_apps or [])]
    cli_names = [c[0] for c in (clis or [])]
    installed_app_names = facts.get("installed_app_names") or set()
    l_rows = legend_rows(
        methods_rows,
        installed_app_names,
        casks_nonorphan or set(),
        mas_names,
        ipad_names,
        cli_names,
    )
    new_md = rebuild_legend(new_md, l_rows)

    return new_md, report
