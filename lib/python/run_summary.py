#!/usr/bin/env python3
"""lib/python/run_summary.py — Machine-readable run summary generator (JSON).

Composes and writes logs/run_summary_<timestamp>.json for automation & monitoring.
"""

from __future__ import annotations

import datetime
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any


FORMAT_VERSION = 4

PENDING_FILES = (
    ("pending_after_run_appstore", "pending_appstore"),
    ("pending_after_run_brew_formulae", "pending_brew_formulae"),
    ("pending_after_run_brew_casks", "pending_brew_casks"),
    ("pending_after_run_mau", "pending_mau"),
    ("pending_after_run_system", "pending_system"),
)

MAU_PRODUCT_NAMES = {
    "MSWD2019": "Microsoft Word",
    "XCEL2019": "Microsoft Excel",
    "PPT32019": "Microsoft PowerPoint",
    "ONMC2019": "Microsoft OneNote",
    "OPIM2019": "Microsoft Outlook",
    "MAU01": "Microsoft AutoUpdate",
}

SUMMARY_I18N = {
    "en": {
        "updated_title": "Updated",
        "pending_title": "Still pending / failed",
        "unconfirmed_title": "Updater launched, but update not confirmed",
        "inventory_changes": "Inventory version fields changed: %s",
        "none": "(none)",
    },
    "pl": {
        "updated_title": "Zaktualizowano",
        "pending_title": "Nadal oczekuje / niepowodzenie",
        "unconfirmed_title": "Uruchomiono updater, ale nie potwierdzono aktualizacji",
        "inventory_changes": "Zmieniono pól wersji w inventory: %s",
        "none": "(brak)",
    },
    "de": {
        "updated_title": "Aktualisiert",
        "pending_title": "Noch ausstehend / fehlgeschlagen",
        "unconfirmed_title": "Updater gestartet, aber Aktualisierung nicht bestätigt",
        "inventory_changes": "Inventar-Versionsfelder geändert: %s",
        "none": "(keine)",
    },
    "es": {
        "updated_title": "Actualizado",
        "pending_title": "Aún pendiente / fallido",
        "unconfirmed_title": "Actualizador iniciado, pero actualización no confirmada",
        "inventory_changes": "Campos de versión de inventario cambiados: %s",
        "none": "(ninguno)",
    },
    "fr": {
        "updated_title": "Mis à jour",
        "pending_title": "Toujours en attente / échoué",
        "unconfirmed_title": "Programme de mise à jour lancé, mais mise à jour non confirmée",
        "inventory_changes": "Champs de version de l'inventaire modifiés : %s",
        "none": "(aucun)",
    },
    "it": {
        "updated_title": "Aggiornato",
        "pending_title": "Ancora in sospeso / non riuscito",
        "unconfirmed_title": "Programma di aggiornamento avviato, ma aggiornamento non confermato",
        "inventory_changes": "Campi versione inventario modificati: %s",
        "none": "(nessuno)",
    },
    "pt": {
        "updated_title": "Atualizado",
        "pending_title": "Ainda pendente / falhou",
        "unconfirmed_title": "Atualizador iniciado, mas atualização não confirmada",
        "inventory_changes": "Campos de versão do inventário alterados: %s",
        "none": "(nenhum)",
    },
}


INVALID_VERSIONS = {
    "?",
    "unknown",
    "null",
    "none",
    "n/a",
    "not installed",
    "niezainstalowane",
    "(none)",
    "(brak)",
    "",
}


def is_valid_version(v: Any) -> bool:
    """Return True if v is a non-empty, recognized version string."""
    if v is None:
        return False
    s = str(v).strip()
    return bool(s) and s.lower() not in INVALID_VERSIONS


def normalize_app_key(name: str) -> str:
    """Normalize application name for cross-subsystem deduplication."""
    s = str(name).strip().lower()
    if s.endswith(".app"):
        s = s[:-4].strip()
    s = s.replace("_", " ").replace("-", " ")
    return " ".join(s.split())


def classify_step_status(val: Any) -> str:
    """Classify localized or English step message into a stable status code:

    'ok', 'warn', 'error', 'skipped', 'skipped_by_user', or 'unconfirmed'.
    """
    if val is None:
        return "unconfirmed"
    if isinstance(val, dict):
        if "code" in val and val["code"]:
            return str(val["code"])
        val = val.get("text", "")
    s = str(val).strip().lower()
    if not s:
        return "unconfirmed"

    if s in ("ok", "warn", "error", "skipped", "skipped_by_user", "unconfirmed"):
        return s

    error_tokens = ("error", "błąd", "blad", "fehler", "erreur", "fallo", "errore", "erro", "failed")
    if any(tok in s for tok in error_tokens):
        return "error"

    if "pominięte przez użytkownika" in s or "skipped by user" in s:
        return "skipped_by_user"

    warn_tokens = (
        "warn", "ostrzeż", "ostrzez", "warnung", "avertissement", "advertencia", "avviso", "aviso",
        "unverified", "niezweryfikowan", "degraded", "unknown", "nieznan", "zastrzeż",
    )
    if any(tok in s for tok in warn_tokens):
        return "warn"

    skip_tokens = ("skip", "pominięt", "pominiet", "übersprungen", "ignoré", "omitido", "saltato")
    if any(tok in s for tok in skip_tokens):
        return "skipped"

    ok_tokens = (
        "ok", "zakończon", "zakonczon", "completed", "erfolgreich", "terminé", "completado",
        "completato", "concluído", "aktualn", "current",
    )
    if any(tok in s for tok in ok_tokens):
        return "ok"

    return "unconfirmed"


def read_mas_versions(filepath: str | Path) -> dict[str, str]:
    """Parse `mas list` snapshot format: `<id> <name> (<version>)`."""
    versions: dict[str, str] = {}
    path = Path(filepath)
    if not path.is_file():
        return versions
    import re
    pattern = re.compile(r"^\s*(\d+)\s+(.+?)\s+\(([^)]+)\)\s*$")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = pattern.match(line)
        if m:
            name = m.group(2).strip()
            ver = m.group(3).strip()
            versions[name] = ver
    return versions


def read_mas_details(filepath: str | Path) -> dict[str, dict[str, str]]:
    """Parse `mas list` snapshot into name -> {'id': id, 'version': ver}."""
    details: dict[str, dict[str, str]] = {}
    path = Path(filepath)
    if not path.is_file():
        return details
    import re
    pattern = re.compile(r"^\s*(\d+)\s+(.+?)\s+\(([^)]+)\)\s*$")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = pattern.match(line)
        if m:
            app_id = m.group(1).strip()
            name = m.group(2).strip()
            ver = m.group(3).strip()
            details[name] = {"id": app_id, "version": ver}
    return details


def read_kv_versions(filepath: str | Path, sep: str | None = None) -> dict[str, str]:
    """Read whitespace- or delimiter-separated key-value snapshot file."""
    versions: dict[str, str] = {}
    path = Path(filepath)
    if not path.is_file():
        return versions
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if sep:
            parts = line.split(sep, 1)
            if len(parts) == 2:
                versions[parts[0].strip()] = parts[1].strip()
        else:
            parts = line.split()
            if len(parts) >= 2:
                versions[parts[0]] = parts[1]
    return versions


def read_npm_cli_snapshot(filepath: str | Path) -> dict[str, str]:
    """Read npm_cli snapshot file (`name|package|version|bin|path`)."""
    versions: dict[str, str] = {}
    path = Path(filepath)
    if not path.is_file():
        return versions
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split("|")
        if len(parts) >= 3:
            versions[parts[0].strip()] = parts[2].strip()
    return versions


def read_npm_cli_details(filepath: str | Path) -> dict[str, dict[str, str]]:
    """Read npm_cli snapshot file (`name|package|version|bin|path`) with id."""
    details: dict[str, dict[str, str]] = {}
    path = Path(filepath)
    if not path.is_file():
        return details
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split("|")
        if len(parts) >= 3:
            name = parts[0].strip()
            pkg = parts[1].strip()
            ver = parts[2].strip()
            details[name] = {"id": pkg or name, "version": ver}
    return details


def collect_run_items(
    session_dir: str | Path,
    step_results: dict[str, str] | None = None,
    inventory_updated_count: int = 0,
) -> list[dict[str, Any]]:
    """Collect unified per-item records across all update subsystems."""
    sdir = Path(session_dir)
    items: list[dict[str, Any]] = []
    seen_updated_apps: set[str] = set()

    # 1. App Store (only if both before and after snapshots exist)
    mas_before_file = sdir / "mas_before.txt"
    mas_after_file = sdir / "mas_after.txt"
    if mas_before_file.is_file() and mas_after_file.is_file():
        mas_before = read_mas_details(mas_before_file)
        mas_after = read_mas_details(mas_after_file)
        for name, data in mas_after.items():
            new_ver = data.get("version", "")
            old_data = mas_before.get(name)
            old_ver = old_data.get("version") if old_data else None
            app_id = data.get("id") or (old_data.get("id") if old_data else name)
            if old_ver is not None and is_valid_version(old_ver) and is_valid_version(new_ver) and old_ver != new_ver:
                app_key = normalize_app_key(name)
                if app_key not in seen_updated_apps:
                    seen_updated_apps.add(app_key)
                    items.append({
                        "name": name,
                        "id": app_id,
                        "category": "appstore",
                        "old_version": old_ver,
                        "new_version": new_ver,
                        "status": "updated",
                        "details": None,
                    })

    # 2. Homebrew Formulae (only if both snapshots exist)
    brew_form_before_file = sdir / "brew_formulae_before.txt"
    brew_form_after_file = sdir / "brew_formulae_after.txt"
    if brew_form_before_file.is_file() and brew_form_after_file.is_file():
        brew_form_before = read_kv_versions(brew_form_before_file)
        brew_form_after = read_kv_versions(brew_form_after_file)
        for name, new_ver in brew_form_after.items():
            old_ver = brew_form_before.get(name)
            if old_ver is not None and is_valid_version(old_ver) and is_valid_version(new_ver) and old_ver != new_ver:
                app_key = normalize_app_key(name)
                if app_key not in seen_updated_apps:
                    seen_updated_apps.add(app_key)
                    items.append({
                        "name": name,
                        "id": name,
                        "category": "brew_formula",
                        "old_version": old_ver,
                        "new_version": new_ver,
                        "status": "updated",
                        "details": None,
                    })

    # 3. Homebrew Casks (only if both snapshots exist)
    brew_cask_before_file = sdir / "brew_casks_before.txt"
    brew_cask_after_file = sdir / "brew_casks_after.txt"
    if brew_cask_before_file.is_file() and brew_cask_after_file.is_file():
        brew_cask_before = read_kv_versions(brew_cask_before_file)
        brew_cask_after = read_kv_versions(brew_cask_after_file)
        for name, new_ver in brew_cask_after.items():
            old_ver = brew_cask_before.get(name)
            if old_ver is not None and is_valid_version(old_ver) and is_valid_version(new_ver) and old_ver != new_ver:
                app_key = normalize_app_key(name)
                if app_key not in seen_updated_apps:
                    seen_updated_apps.add(app_key)
                    items.append({
                        "name": name,
                        "id": name,
                        "category": "brew_cask",
                        "old_version": old_ver,
                        "new_version": new_ver,
                        "status": "updated",
                        "details": None,
                    })

    # 4. Native CLI + npm (only if both snapshots exist)
    npm_cli_before_file = sdir / "npm_cli_before.txt"
    npm_cli_after_file = sdir / "npm_cli_after.txt"
    if npm_cli_before_file.is_file() and npm_cli_after_file.is_file():
        npm_cli_before = read_npm_cli_details(npm_cli_before_file)
        npm_cli_after = read_npm_cli_details(npm_cli_after_file)
        for name, data in npm_cli_after.items():
            new_ver = data.get("version", "")
            old_data = npm_cli_before.get(name)
            old_ver = old_data.get("version") if old_data else None
            cli_id = data.get("id") or (old_data.get("id") if old_data else name)
            if old_ver is not None and is_valid_version(old_ver) and is_valid_version(new_ver) and old_ver != new_ver:
                app_key = normalize_app_key(name)
                if app_key not in seen_updated_apps:
                    seen_updated_apps.add(app_key)
                    items.append({
                        "name": name,
                        "id": cli_id,
                        "category": "npm_cli",
                        "old_version": old_ver,
                        "new_version": new_ver,
                        "status": "updated",
                        "details": None,
                    })

    # 5. Internet Apps (only if both snapshots exist)
    inet_before_file = sdir / "internet_before.txt"
    inet_after_file = sdir / "internet_after.txt"
    if inet_before_file.is_file() and inet_after_file.is_file():
        inet_before = read_kv_versions(inet_before_file, sep="|")
        inet_after = read_kv_versions(inet_after_file, sep="|")
        for name, new_ver in inet_after.items():
            old_ver = inet_before.get(name)
            if old_ver is not None and is_valid_version(old_ver) and is_valid_version(new_ver) and old_ver != new_ver:
                app_key = normalize_app_key(name)
                if app_key not in seen_updated_apps:
                    seen_updated_apps.add(app_key)
                    items.append({
                        "name": name,
                        "id": name,
                        "category": "internet",
                        "old_version": old_ver,
                        "new_version": new_ver,
                        "status": "updated",
                        "details": None,
                    })

    # 6. macOS System update
    sys_upgrade_path = sdir / "system_upgrade.txt"
    sys_before_path = sdir / "system_before.txt"
    sys_after_path = sdir / "system_after.txt"
    if sys_upgrade_path.is_file():
        txt = sys_upgrade_path.read_text(encoding="utf-8", errors="replace").strip()
        if txt and is_valid_version(txt):
            old_s = None
            new_s = txt
            if "->" in txt:
                p = txt.split("->", 1)
                old_s = p[0].strip()
                new_s = p[1].strip()
            elif "|" in txt:
                p = txt.split("|", 1)
                old_s = p[0].strip()
                new_s = p[1].strip()
            if is_valid_version(new_s) and (old_s is None or (is_valid_version(old_s) and old_s != new_s)):
                app_key = normalize_app_key("macOS")
                if app_key not in seen_updated_apps:
                    seen_updated_apps.add(app_key)
                    items.append({
                        "name": "macOS",
                        "id": "macos",
                        "category": "system",
                        "old_version": old_s,
                        "new_version": new_s,
                        "status": "updated",
                        "details": None,
                    })
    elif sys_before_path.is_file() and sys_after_path.is_file():
        old_sys = sys_before_path.read_text(encoding="utf-8", errors="replace").strip()
        new_sys = sys_after_path.read_text(encoding="utf-8", errors="replace").strip()
        if is_valid_version(old_sys) and is_valid_version(new_sys) and old_sys != new_sys:
            app_key = normalize_app_key("macOS")
            if app_key not in seen_updated_apps:
                seen_updated_apps.add(app_key)
                items.append({
                    "name": "macOS",
                    "id": "macos",
                    "category": "system",
                    "old_version": old_sys,
                    "new_version": new_sys,
                    "status": "updated",
                    "details": None,
                })

    # 7. Pending / Remaining items
    mau_reason = None
    reason_path = sdir / "mau_interrupt_reason.txt"
    if reason_path.is_file():
        mau_reason = reason_path.read_text(encoding="utf-8", errors="replace").strip()

    pending_mau_file = sdir / "pending_mau"
    pending_mau_val = None
    if pending_mau_file.is_file():
        pending_mau_val = pending_mau_file.read_text(encoding="utf-8", errors="replace").strip()

    if pending_mau_val == "unknown":
        items.append({
            "name": "Microsoft AutoUpdate",
            "id": "MAU",
            "category": "internet",
            "old_version": None,
            "new_version": None,
            "status": "unconfirmed",
            "details": mau_reason or "Listing check failed (unknown status)",
        })
    elif pending_mau_val == "0":
        # Verified 0 pending MAU updates. Do not show initial IDs.
        pass
    else:
        # Strictly read mau_remaining.txt, NEVER fall back to mau_pending.txt
        remaining_path = sdir / "mau_remaining.txt"
        if remaining_path.is_file():
            rem_text = remaining_path.read_text(encoding="utf-8", errors="replace").strip()
            if rem_text:
                for pid in rem_text.split():
                    clean_pid = pid.strip()
                    if not clean_pid:
                        continue
                    human_name = MAU_PRODUCT_NAMES.get(clean_pid, clean_pid)
                    display_name = f"{human_name} ({clean_pid})" if clean_pid in MAU_PRODUCT_NAMES else clean_pid
                    items.append({
                        "name": display_name,
                        "id": clean_pid,
                        "category": "internet",
                        "old_version": None,
                        "new_version": None,
                        "status": "pending",
                        "details": mau_reason or "Microsoft AutoUpdate pending",
                    })
        elif pending_mau_val and pending_mau_val.isdigit() and int(pending_mau_val) > 0:
            items.append({
                "name": "Microsoft AutoUpdate",
                "id": "MAU",
                "category": "internet",
                "old_version": None,
                "new_version": None,
                "status": "pending",
                "details": f"{pending_mau_val} updates pending",
            })

    # Homebrew Formulae pending queue
    pbf_file = sdir / "pending_brew_formulae"
    if pbf_file.is_file():
        pbf_val = pbf_file.read_text(encoding="utf-8", errors="replace").strip()
        if pbf_val == "unknown":
            items.append({
                "name": "Homebrew Formulae",
                "id": "brew_formulae",
                "category": "brew_formula",
                "old_version": None,
                "new_version": None,
                "status": "unconfirmed",
                "details": "Formulae check/update unconfirmed",
            })
        elif pbf_val.isdigit() and int(pbf_val) > 0:
            items.append({
                "name": "Homebrew Formulae pending queue",
                "id": "brew_formulae",
                "category": "brew_formula",
                "old_version": None,
                "new_version": None,
                "status": "pending",
                "details": f"{pbf_val} updates pending",
            })

    # Homebrew Casks pending queue
    pbc_file = sdir / "pending_brew_casks"
    if pbc_file.is_file():
        pbc_val = pbc_file.read_text(encoding="utf-8", errors="replace").strip()
        if pbc_val == "unknown":
            items.append({
                "name": "Homebrew Casks",
                "id": "brew_casks",
                "category": "brew_cask",
                "old_version": None,
                "new_version": None,
                "status": "unconfirmed",
                "details": "Casks check/update unconfirmed",
            })
        elif pbc_val.isdigit() and int(pbc_val) > 0:
            items.append({
                "name": "Homebrew Casks pending queue",
                "id": "brew_casks",
                "category": "brew_cask",
                "old_version": None,
                "new_version": None,
                "status": "pending",
                "details": f"{pbc_val} updates pending",
            })

    # App Store pending queue
    pas_file = sdir / "pending_appstore"
    if pas_file.is_file():
        pas_val = pas_file.read_text(encoding="utf-8", errors="replace").strip()
        if pas_val == "unknown":
            items.append({
                "name": "App Store",
                "id": "appstore",
                "category": "appstore",
                "old_version": None,
                "new_version": None,
                "status": "unconfirmed",
                "details": "App Store check/update unconfirmed",
            })
        elif pas_val.isdigit() and int(pas_val) > 0:
            items.append({
                "name": "App Store pending queue",
                "id": "appstore",
                "category": "appstore",
                "old_version": None,
                "new_version": None,
                "status": "pending",
                "details": f"{pas_val} updates pending",
            })

    # macOS System pending updates from system_available.txt
    pending_sys_file = sdir / "pending_system"
    sys_avail_file = sdir / "system_available.txt"
    pending_sys_val = None
    if pending_sys_file.is_file():
        pending_sys_val = pending_sys_file.read_text(encoding="utf-8", errors="replace").strip()

    if pending_sys_val != "0" and sys_avail_file.is_file():
        from system_updates import parse_softwareupdate_list
        raw_sys = sys_avail_file.read_text(encoding="utf-8", errors="replace")
        sys_items = parse_softwareupdate_list(raw_sys)
        for s_it in sys_items:
            items.append({
                "name": s_it.get("title") or s_it.get("label", "macOS update"),
                "id": s_it.get("label", "system"),
                "category": "system",
                "old_version": None,
                "new_version": s_it.get("version") or None,
                "status": "pending",
                "details": f"Label: {s_it.get('label')}" if s_it.get("label") else None,
            })

    # Intel-only apps missing Rosetta
    rosetta_file = sdir / "rosetta_missing_apps.txt"
    if rosetta_file.is_file():
        for line in rosetta_file.read_text(encoding="utf-8", errors="replace").splitlines():
            app_name = line.strip()
            if app_name:
                items.append({
                    "name": app_name,
                    "id": app_name,
                    "category": "internet",
                    "old_version": None,
                    "new_version": None,
                    "status": "pending",
                    "details": "Intel-only; Rosetta missing; EOL macOS 28",
                })

    # Internet apps behind cask oracle
    inet_behind_file = sdir / "internet_behind_apps.txt"
    if inet_behind_file.is_file():
        for line in inet_behind_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) >= 3:
                b_name, b_old, b_new = parts[0].strip(), parts[1].strip(), parts[2].strip()
                items.append({
                    "name": b_name,
                    "id": b_name,
                    "category": "internet",
                    "old_version": b_old or None,
                    "new_version": b_new or None,
                    "status": "pending",
                    "details": f"Behind cask ({b_old} < {b_new})",
                })

    # 8. Unconfirmed or degraded steps from step_results
    if step_results:
        step_labels = {
            "prescan": "Scan new apps",
            "appstore": "App Store",
            "npmcli": "Native CLI + npm",
            "brew": "Homebrew",
            "internet": "Internet apps",
            "postupdate": "Inventory update",
            "system": "macOS System",
        }
        pending_brew_reason = None
        pbr_file = sdir / "pending_brew_reason"
        if pbr_file.is_file():
            pending_brew_reason = pbr_file.read_text(encoding="utf-8", errors="replace").strip()

        xcode_change = None
        xc_file = sdir / "xcode_changed.txt"
        if xc_file.is_file():
            xc_txt = xc_file.read_text(encoding="utf-8", errors="replace").strip()
            if xc_txt.startswith("xcode_changed="):
                xcode_change = xc_txt.split("=", 1)[1].strip()
            elif xc_txt:
                xcode_change = xc_txt

        for step_key, step_val in step_results.items():
            status_code = classify_step_status(step_val)
            if status_code in ("warn", "error", "unconfirmed"):
                details = str(step_val)
                if step_key == "brew" and pending_brew_reason == "xcode_license":
                    if xcode_change:
                        details = f"Xcode license not accepted (Xcode {xcode_change})"
                    else:
                        details = "Xcode license not accepted"
                items.append({
                    "name": f"Step: {step_labels.get(step_key, step_key)}",
                    "id": step_key,
                    "category": step_key,
                    "old_version": None,
                    "new_version": None,
                    "status": "unconfirmed",
                    "details": details,
                })

    return items


def format_terminal_summary(summary: dict[str, Any], lang: str = "en") -> str:
    """Format the 4-section terminal summary string."""
    i18n = SUMMARY_I18N.get(lang, SUMMARY_I18N["en"])
    title_updated = os.environ.get("L_ALL_SUMMARY_UPDATED_TITLE", i18n["updated_title"])
    title_pending = os.environ.get("L_ALL_SUMMARY_PENDING_TITLE", i18n["pending_title"])
    title_unconfirmed = os.environ.get("L_ALL_SUMMARY_UNCONFIRMED_TITLE", i18n["unconfirmed_title"])
    inv_fmt = os.environ.get("L_ALL_SUMMARY_INVENTORY_CHANGES", i18n["inventory_changes"])
    none_str = i18n["none"]

    items = summary.get("items", [])
    updated_items = [it for it in items if it.get("status") == "updated"]
    pending_items = [it for it in items if it.get("status") == "pending"]
    unconfirmed_items = [it for it in items if it.get("status") == "unconfirmed"]
    counts = summary.get("counts", {})
    inventory_count = counts.get("inventory_version_fields_changed", 0)

    lines: list[str] = [
        "────────────────────────────────────────────────────────────",
        f"📌 {title_updated}:",
    ]
    if updated_items:
        for it in updated_items:
            cat = it.get("category", "")
            cat_str = f" ({cat})" if cat else ""
            old_v = it.get("old_version")
            new_v = it.get("new_version")
            if old_v and new_v:
                lines.append(f"   • {it['name']}{cat_str}: {old_v} -> {new_v}")
            elif new_v:
                lines.append(f"   • {it['name']}{cat_str}: {new_v}")
            else:
                lines.append(f"   • {it['name']}{cat_str}")
    else:
        lines.append(f"   • {none_str}")

    lines.append("")
    lines.append(f"⏳ {title_pending}:")
    if pending_items:
        for it in pending_items:
            details = it.get("details")
            det_str = f" — {details}" if details else ""
            lines.append(f"   • {it['name']}{det_str}")
    else:
        lines.append(f"   • {none_str}")

    lines.append("")
    lines.append(f"⚠️  {title_unconfirmed}:")
    if unconfirmed_items:
        for it in unconfirmed_items:
            details = it.get("details")
            det_str = f" — {details}" if details else ""
            lines.append(f"   • {it['name']}{det_str}")
    else:
        lines.append(f"   • {none_str}")

    lines.append("")
    try:
        inv_line = inv_fmt % inventory_count
    except Exception:
        inv_line = f"{inv_fmt}: {inventory_count}"
    lines.append(f"📝 {inv_line}")
    lines.append("────────────────────────────────────────────────────────────")

    return "\n".join(lines)


def migrate_run_summary(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate older run_summary dict (v1, v2, or v3) to schema v4."""
    migrated = dict(data)
    migrated["format_version"] = FORMAT_VERSION
    if "items" not in migrated or not isinstance(migrated["items"], list):
        migrated["items"] = []
    if "verification" not in migrated or not isinstance(migrated["verification"], dict):
        migrated["verification"] = {}
    if "run_status" not in migrated:
        migrated["run_status"] = "completed"
    if "counts" not in migrated or not isinstance(migrated["counts"], dict):
        migrated["counts"] = {}
    else:
        c = dict(migrated["counts"])
        if "inventory_version_fields_changed" not in c and "inventory_fields_changed" in c:
            c["inventory_version_fields_changed"] = c["inventory_fields_changed"]
        migrated["counts"] = c
    if "steps" in migrated and isinstance(migrated["steps"], dict):
        new_steps = {}
        for step_k, step_v in migrated["steps"].items():
            if isinstance(step_v, dict) and "code" in step_v:
                new_steps[step_k] = {
                    "code": str(step_v["code"]),
                    "text": str(step_v.get("text", "")),
                }
            else:
                code = classify_step_status(step_v)
                new_steps[step_k] = {
                    "code": code,
                    "text": str(step_v) if step_v is not None else "",
                }
        migrated["steps"] = new_steps
    return migrated


def determine_exit_class(overall_exit: int, degraded: int) -> str:
    """Classify run outcome into clean (0), warnings (10/degraded), or error (1)."""
    if overall_exit != 0:
        return "error"
    if degraded != 0:
        return "warnings"
    return "clean"


def merge_pending(counts: dict[str, Any], session_dir: str) -> tuple[dict[str, Any], dict[str, str]]:
    """Attach pending-* measurements. Missing/corrupt values stay unknown, not 0."""
    merged = dict(counts)
    verification: dict[str, str] = {}
    for key, filename in PENDING_FILES:
        path = Path(session_dir) / filename
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            merged[key] = None
            verification[key] = "missing"
            continue
        if text == "":
            merged[key] = None
            verification[key] = "empty"
            continue
        if text in {"unknown", "null"}:
            merged[key] = None
            verification[key] = "unknown"
            continue
        try:
            merged[key] = int(text)
            verification[key] = "verified"
        except ValueError:
            merged[key] = None
            verification[key] = "invalid"
    return merged, verification


def build_run_summary(
    start_time: int,
    end_time: int,
    overall_exit: int,
    degraded: int,
    blocking_exit: int,
    step_results: dict[str, Any],
    counts: dict[str, Any] | None = None,
    flags: dict[str, Any] | None = None,
    session_dir: str | None = None,
    verification: dict[str, str] | None = None,
    run_status: str = "completed",
    run_id: str | None = None,
    items: list[dict[str, Any]] | None = None,
    step_codes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Compose the structured run summary dict."""
    duration = max(0, end_time - start_time)
    minutes = duration // 60
    secs = duration % 60

    start_iso = datetime.datetime.fromtimestamp(start_time, tz=datetime.timezone.utc).isoformat()
    end_iso = datetime.datetime.fromtimestamp(end_time, tz=datetime.timezone.utc).isoformat()

    steps_v4: dict[str, dict[str, str]] = {}
    if step_results:
        for k, v in step_results.items():
            if isinstance(v, dict) and "code" in v:
                steps_v4[k] = {
                    "code": str(v["code"]),
                    "text": str(v.get("text", "")),
                }
            else:
                code = None
                if step_codes and k in step_codes:
                    code = step_codes[k]
                if not code or code == "unconfirmed":
                    code = classify_step_status(v)
                steps_v4[k] = {
                    "code": code,
                    "text": str(v) if v is not None else "",
                }

    summary: dict[str, Any] = {
        "format_version": FORMAT_VERSION,
        "run_id": run_id or str(uuid.uuid4()),
        "run_status": run_status,
        "timestamp": start_iso,
        "completed_at": end_iso if run_status == "completed" else None,
        "duration_seconds": duration,
        "duration_formatted": f"{minutes}m {secs}s",
        "exit_code": overall_exit,
        "exit_class": determine_exit_class(overall_exit, degraded),
        "degraded": bool(degraded),
        "blocking_exit": blocking_exit,
        "steps": steps_v4,
        "counts": counts or {},
        "verification": verification or {},
        "flags": flags or {},
        "items": items if items is not None else [],
    }
    if session_dir:
        summary["session_dir"] = session_dir
        summary["session_dir_note"] = "ephemeral; not a durable archive"
    return summary


def write_run_summary(output_path: str | Path, summary_data: dict[str, Any]) -> str:
    """Atomically serialize summary_data as formatted JSON to output_path."""
    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    json_str = json.dumps(summary_data, indent=2, ensure_ascii=False) + "\n"

    tmp_dir = target_path.parent
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target_path.name}.", suffix=".tmp", dir=tmp_dir)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(json_str)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_name, target_path)
        os.chmod(target_path, 0o600)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return str(target_path)
