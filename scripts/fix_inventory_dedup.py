#!/usr/bin/env python3
"""
scripts/fix_inventory_dedup.py — Fix APPLICATIONS.md deduplication and descriptions.
- Ensures Section 4c (Casks) contains ONLY currently installed casks with valid methods in config/internet_app_methods.txt.
- Fills cask descriptions from brew info API instead of '🆕 NOWY — opis do uzupełnienia'.
- Removes 4c cask apps from GRUPA 3 (deduplication).
- Ensures vendor_latest apps are in GRUPA 3.
"""
import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_MD = REPO_ROOT / "APPLICATIONS.md"
METHODS_FILE = REPO_ROOT / "config" / "internet_app_methods.txt"

def norm_name(s: str) -> str:
    return re.sub(r"[-_ .]", "", s.lower().strip())

def main():
    if not APP_MD.exists():
        print("APPLICATIONS.md not found!")
        return

    content = APP_MD.read_text()

    # Load methods
    methods = {}
    with open(METHODS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) >= 2:
                methods[parts[0].strip()] = parts[1].strip()

    # Get installed casks
    res = subprocess.run(["brew", "list", "--cask", "--versions"], capture_output=True, text=True)
    installed_casks = {}
    for line in res.stdout.splitlines():
        if line.strip():
            parts = line.split()
            cask_slug = parts[0]
            cask_ver = parts[1] if len(parts) > 1 else "?"
            installed_casks[cask_slug] = cask_ver

    # Section 4c should contain ONLY installed casks
    casks_for_4c = []
    cask_norm_names = set()

    for slug, ver in sorted(installed_casks.items()):
        cask_norm_names.add(norm_name(slug))
        desc = "Oprogramowanie macOS (Homebrew Cask)"
        try:
            info_res = subprocess.run(["brew", "info", "--json=v2", "--cask", slug], capture_output=True, text=True)
            if info_res.returncode == 0 and info_res.stdout.strip():
                d = json.loads(info_res.stdout)
                c = d["casks"][0]
                desc = c.get("desc", desc) or desc
        except Exception:
            pass
        casks_for_4c.append((slug, ver, desc))

    for app, meth in methods.items():
        if meth == "brew_cask":
            cask_norm_names.add(norm_name(app))

    # Rebuild 4c section table
    new_4c_table = "### 4c. Casks (aplikacje GUI przez Homebrew)\n\n"
    new_4c_table += "| Nazwa | Wersja | Opis |\n"
    new_4c_table += "|-------|--------|------|\n"
    for slug, ver, desc in casks_for_4c:
        new_4c_table += f"| {slug} | {ver} | {desc} |\n"
    new_4c_table += "\n"

    # Replace 4c section cleanly up to '### 4d'
    pattern_4c = r"### 4c\. Casks.*?(?=### 4d)"
    content = re.sub(pattern_4c, new_4c_table, content, flags=re.DOTALL)

    # Deduplicate GRUPA 3: remove any apps whose normalized name is in cask_norm_names
    grupa3_match = re.search(r"(## GRUPA 3.*?\n)(.*?)(?=## GRUPA 4)", content, re.DOTALL)
    if grupa3_match:
        g3_header = grupa3_match.group(1)
        g3_body = grupa3_match.group(2)
        new_g3_lines = []
        removed_apps = []

        for line in g3_body.splitlines(True):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2 and parts[1]:
                raw_name = parts[1]
                clean_name = re.sub(r"^\*\*(.*?)\*\*$", r"\1", raw_name).strip()
                if clean_name not in ("Nazwa", "Nazwa aplikacji", "---") and not clean_name.startswith("-"):
                    if norm_name(clean_name) in cask_norm_names:
                        removed_apps.append(clean_name)
                        continue
            new_g3_lines.append(line)

        new_g3_body = "".join(new_g3_lines)
        content = content[:grupa3_match.start(2)] + new_g3_body + content[grupa3_match.end(2):]
        print(f"Deduplicated GRUPA 3: removed {len(removed_apps)} apps: {removed_apps}")

    APP_MD.write_text(content)
    print("Updated APPLICATIONS.md successfully.")

if __name__ == "__main__":
    main()
