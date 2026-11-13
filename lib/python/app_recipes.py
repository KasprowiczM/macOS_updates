"""Bounded, declarative recipe and legacy capability catalog readers."""

import json
import re

_MAX_BYTES = 1024 * 1024
_ADAPTERS = frozenset(
    (
        "keystone",
        "github_dmg",
        "mozilla_dmg",
        "silent_launch",
        "msupdate",
        "mau_fallback_self_update",
        "docker_cli",
        "brew_cask",
        "appstore_gui",
        "manual",
        "sparkle_appcast",
        "chromium_updater",
    )
)
_FIELDS = frozenset(
    (
        "id",
        "adapter_id",
        "bundle_ids",
        "team_ids",
        "channels",
        "architectures",
        "minimum_os",
        "download_hosts",
        "allowed_artifacts",
    )
)
_LISTS = _FIELDS - {"id", "adapter_id", "minimum_os"}


def _read(path):
    with open(path, "rb") as handle:
        data = handle.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        raise ValueError("catalog exceeds size limit")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid UTF-8") from exc


def load_recipes(path):
    try:
        data = json.loads(_read(path), object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid recipe JSON") from exc
    if (
        not isinstance(data, dict)
        or set(data) != {"schema_version", "recipes"}
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or not isinstance(data["recipes"], list)
    ):
        raise ValueError("invalid recipe catalog")
    ids = set()
    for recipe in data["recipes"]:
        if not isinstance(recipe, dict) or set(recipe) != _FIELDS:
            raise ValueError("invalid recipe fields")
        if (
            not isinstance(recipe["id"], str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,127}", recipe["id"])
            or recipe["id"] in ids
        ):
            raise ValueError("invalid or duplicate recipe id")
        ids.add(recipe["id"])
        if (
            not isinstance(recipe["adapter_id"], str)
            or recipe["adapter_id"] not in _ADAPTERS
        ):
            raise ValueError("unknown adapter")
        for field in _LISTS:
            value = recipe[field]
            if (
                not isinstance(value, list)
                or len(value) > 128
                or any(not isinstance(x, str) or not x or len(x) > 255 for x in value)
                or len(value) != len(set(value))
            ):
                raise ValueError("invalid recipe list: " + field)
        if recipe["minimum_os"] is not None and (
            not isinstance(recipe["minimum_os"], str)
            or not re.fullmatch(r"\d+(?:\.\d+){0,2}", recipe["minimum_os"])
        ):
            raise ValueError("invalid minimum OS")
        if any(x not in ("stable", "beta", "testflight") for x in recipe["channels"]):
            raise ValueError("invalid channel")
        if any(x not in ("arm64", "x86_64") for x in recipe["architectures"]):
            raise ValueError("invalid architecture")
        if any(
            not re.fullmatch(r"[A-Za-z0-9.-]+", x) or ".." in x
            for x in recipe["download_hosts"]
        ):
            raise ValueError("invalid download host")
        if any(
            x not in ("dmg", "pkg", "zip", "app") for x in recipe["allowed_artifacts"]
        ):
            raise ValueError("invalid artifact")
    return data


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def load_legacy_capabilities(path):
    """Read adapter availability only; names never establish local ownership."""
    result = []
    for line in _read(path).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("|")
        if len(fields) not in (3, 4) or not fields[0] or fields[1] not in _ADAPTERS:
            raise ValueError("invalid legacy adapter row")
        result.append({"name": fields[0], "adapter_id": fields[1]})
    return result
