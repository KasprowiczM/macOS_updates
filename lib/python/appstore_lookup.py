#!/usr/bin/env python3
"""lib/python/appstore_lookup.py — Pure-function helpers for App Store iPad app lookup (T7)."""

from __future__ import annotations

import json
import plistlib
from typing import Any

from vendor_feeds import version_compare


def read_itunes_metadata(plist_bytes: bytes) -> dict[str, str] | None:
    """Parse iTunesMetadata.plist bytes and extract itemId, version, and name.

    Returns a dict with 'itemId' (str), 'bundleShortVersionString' (str),
    and 'itemName' (str), or None on error or missing itemId.
    """
    if not plist_bytes:
        return None
    try:
        data = plistlib.loads(plist_bytes)
        if not isinstance(data, dict):
            return None
        item_id = data.get("itemId")
        if item_id is None:
            return None
        ver = str(data.get("bundleShortVersionString") or data.get("bundleVersion") or "")
        name = str(data.get("itemName") or data.get("bundleDisplayName") or "")
        return {
            "itemId": str(item_id),
            "bundleShortVersionString": ver,
            "itemName": name,
        }
    except Exception:
        return None


def parse_lookup(json_obj: dict | str) -> dict[str, str]:
    """Parse iTunes lookup API response into a mapping of trackId (str) -> version (str)."""
    if isinstance(json_obj, str):
        try:
            json_obj = json.loads(json_obj)
        except Exception:
            return {}
    if not isinstance(json_obj, dict):
        return {}

    results = json_obj.get("results", [])
    if not isinstance(results, list):
        return {}

    mapping: dict[str, str] = {}
    for entry in results:
        if not isinstance(entry, dict):
            continue
        track_id = entry.get("trackId")
        version = entry.get("version")
        if track_id is not None and version is not None:
            mapping[str(track_id)] = str(version)
    return mapping


def pending_ios(installed: list[dict[str, Any]], store: dict[str, str]) -> list[dict[str, Any]]:
    """Return installed iPad apps whose store version is newer than installed version.

    Only includes entries where version_compare(store_ver, installed_ver) == 1.
    """
    pending: list[dict[str, Any]] = []
    for item in installed:
        item_id = str(item.get("itemId", ""))
        inst_ver = str(item.get("version", ""))
        store_ver = store.get(item_id)
        if not store_ver:
            continue
        if version_compare(store_ver, inst_ver) == 1:
            pending.append({
                "name": item.get("name", ""),
                "itemId": item_id,
                "installed": inst_ver,
                "store": store_ver,
                "path": item.get("path", ""),
            })
    return pending
