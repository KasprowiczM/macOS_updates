#!/usr/bin/env python3
"""lib/python/system_updates.py — Pure-function helpers for softwareupdate parsing and classification."""

from __future__ import annotations

import re
from typing import Any


def parse_softwareupdate_list(text: str) -> list[dict[str, Any]]:
    """Parse output of `softwareupdate -l` into a list of update dictionaries.

    Returns:
        list of dict with keys:
            label (str): Update identifier passed to `softwareupdate -i`
            title (str): Human-readable update name
            version (str): Update version string
            size_kib (int): Download size in KiB
            recommended (bool): Whether update is marked Recommended: YES
            restart (bool): Whether update requires a reboot
    """
    items: list[dict[str, Any]] = []
    if not text or "No new software available" in text:
        return items

    # Split by item headers: lines starting with '* '
    lines = text.splitlines()
    current_label: str | None = None
    current_block: list[str] = []

    def flush_item(label: str, block_lines: list[str]) -> None:
        block_text = "\n".join(block_lines)
        title = label
        version = ""
        size_kib = 0
        recommended = False
        restart = False

        m_title = re.search(r"Title:\s*([^,\n]+)", block_text)
        if m_title:
            title = m_title.group(1).strip()

        m_ver = re.search(r"Version:\s*([^,\n]+)", block_text)
        if m_ver:
            version = m_ver.group(1).strip()

        m_size = re.search(r"Size:\s*(\d+)\s*K(?:i)?B", block_text, re.IGNORECASE)
        if m_size:
            size_kib = int(m_size.group(1))

        m_rec = re.search(r"Recommended:\s*([^,\n]+)", block_text, re.IGNORECASE)
        if m_rec and m_rec.group(1).strip().upper() == "YES":
            recommended = True

        m_act = re.search(r"Action:\s*([^,\n]+)", block_text, re.IGNORECASE)
        if (m_act and "restart" in m_act.group(1).lower()) or re.search(r"\brestart\b", block_text, re.IGNORECASE):
            restart = True

        items.append({
            "label": label,
            "title": title,
            "version": version,
            "size_kib": size_kib,
            "recommended": recommended,
            "restart": restart,
        })

    for line in lines:
        m_label = re.match(r"^\*\s*(?:Label:\s*)?(\S.*)$", line)
        if m_label:
            if current_label is not None:
                flush_item(current_label, current_block)
            current_label = m_label.group(1).strip()
            current_block = []
        elif current_label is not None:
            current_block.append(line)

    if current_label is not None:
        flush_item(current_label, current_block)

    return items


def classify_updates(
    items: list[dict[str, Any]], current_version: str
) -> dict[str, list[dict[str, Any]]]:
    """Classify updates into same_major, major, and other based on current macOS version.

    Args:
        items: List of update dicts from parse_softwareupdate_list
        current_version: Current macOS version string (e.g. "26.6.2" or "27.0")

    Returns:
        dict with keys:
            same_major: Updates to the current macOS major release (e.g. 26.7 on 26.6.2)
            major: Upgrades to a newer macOS major release (e.g. macOS 27 on 26.6.2)
            other: Standalone apps/security payloads (Safari, XProtect, etc.)
    """
    classified: dict[str, list[dict[str, Any]]] = {
        "same_major": [],
        "major": [],
        "other": [],
    }

    try:
        cur_major = int(str(current_version).split(".")[0])
    except (ValueError, IndexError):
        cur_major = 0

    for it in items:
        title = it.get("title", "")
        label = it.get("label", "")
        version = it.get("version", "").strip()

        # Is this a macOS operating system upgrade/update?
        # Typically begins with 'macOS' or 'OS X'
        is_os = bool(re.match(r"^(?:macOS|OS X)\b", title, re.IGNORECASE) or re.match(r"^(?:macOS|OS X)\b", label, re.IGNORECASE))

        if not is_os:
            classified["other"].append(it)
            continue

        # Extract major version of this OS update
        # Version may be "26.7" or "27" or in Title "macOS 27"
        item_major = None
        if version:
            v_part = version.split(".")[0].strip()
            if v_part.isdigit():
                item_major = int(v_part)

        if item_major is None:
            # Try to extract from title (e.g. "macOS 27")
            m = re.search(r"macOS\s+(?:Tahoe\s+)?(\d+)", title, re.IGNORECASE)
            if m:
                item_major = int(m.group(1))

        if item_major is not None and cur_major > 0:
            if item_major > cur_major:
                classified["major"].append(it)
            elif item_major == cur_major:
                classified["same_major"].append(it)
            else:
                # Point update or older
                classified["same_major"].append(it)
        else:
            classified["same_major"].append(it)

    return classified
