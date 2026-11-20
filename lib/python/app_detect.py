"""Decide how an installed macOS app can be updated, from files only.

Pure static inspection: every detector reads files (plistlib, os) and never
executes anything from the bundle and never touches the network. The only
optional subprocess is ``codesign -dv`` for the Team ID, behind
``with_signature=True`` and an injectable runner, used for Sparkle apps only.

Python 3.9 standard library only.

Public entry points
-------------------
build_context(...)            -> DetectContext   (caskroom map, registry, MAU paths ...)
detect_app(path, ctx, ...)    -> dict            (one detection record)
scan_dirs(dirs, ctx, ...)     -> list of dict
summarize(records)            -> dict            (counts per method/origin/confidence)
app_info_from_record(record)  -> dict            (input for sparkle_auto_install_allowed)
sparkle_auto_install_allowed(app_info, appcast_item, downloaded_info, ...)
                              -> (allowed, reason_code, fallback)

Detector priority (first match wins, evidence kept):
  tested registry > appstore > brew_cask > setapp > adobe/jetbrains_toolbox >
  system > sparkle > electron_updater/squirrel > keystone >
  microsoft_autoupdate > manual.
Setapp, Adobe, JetBrains and system sit above Sparkle on purpose: when another
manager owns the bundle, a leftover Sparkle framework must not make the toolkit
update it behind that manager's back.
"""

from __future__ import annotations

import json
import os
import plistlib
import re
import stat
import subprocess
import unicodedata
from urllib.parse import urlparse

METHODS = (
    "appstore", "brew_cask", "sparkle", "squirrel", "electron_updater",
    "keystone", "microsoft_autoupdate", "setapp", "adobe",
    "jetbrains_toolbox", "system", "browser_app", "vendor_download",
    "app_updater", "manual",
)

# Methods whose update is owned by another manager; the toolkit must not update.
MANAGED_ELSEWHERE = ("setapp", "adobe", "jetbrains_toolbox", "browser_app")

MAX_PLIST = 1024 * 1024
MAX_TEXT = 4096
MAX_SMALL_FILE = 64 * 1024
MAX_TICKET_FILE = 4 * 1024 * 1024
CODESIGN_TIMEOUT = 5

_DEFAULT = object()

DEFAULT_CASKROOMS = ("/opt/homebrew/Caskroom", "/usr/local/Caskroom")
DEFAULT_MAU_PATHS = (
    "/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app",
    "/Applications/Microsoft AutoUpdate.app",
)
DEFAULT_KEYSTONE_DIRS = (
    "~/Library/Google/GoogleSoftwareUpdate",
    "/Library/Google/GoogleSoftwareUpdate",
)

# internet_app_methods.txt method column -> detection method. A tested row
# always yields its mapped method, whatever the bundle shows.
#   vendor_download: the toolkit downloads a verified artifact from the vendor
#   app_updater:     the toolkit triggers the app's own updater
# Any raw method not listed here is a direct-download style row and maps to
# vendor_download; only the literal "manual" stays manual.
REGISTRY_DEFAULT_METHOD = "vendor_download"
REGISTRY_METHOD_MAP = {
    "keystone": "keystone",
    "msupdate": "microsoft_autoupdate",
    "mau_fallback_self_update": "microsoft_autoupdate",
    "brew_cask": "brew_cask",
    "appstore_gui": "appstore",
    "sparkle_appcast": "sparkle",
    "manual": "manual",
    "github_dmg": "vendor_download",
    "mozilla_dmg": "vendor_download",
    "docker_cli": "vendor_download",
    "silent_launch": "app_updater",
    "chromium_updater": "app_updater",
}

# Browser-hosted app wrappers (PWAs): bundle id prefixes and folder names.
BROWSER_APP_PREFIXES = (
    ("com.google.chrome.app.", "Google Chrome"),
    ("com.microsoft.edgemac.app.", "Microsoft Edge"),
    ("com.brave.browser.app.", "Brave Browser"),
)
BROWSER_APP_DIRS = (
    ("chrome apps", "Google Chrome"),
    ("edge apps", "Microsoft Edge"),
    ("brave browser apps", "Brave Browser"),
)
HELPER_NAME_SUFFIXES = ("uninstaller", "url handler", "helper")
HELPER_ID_PREFIXES = ("com.google.drivefs.shortcuts.",)


def _norm(text):
    return unicodedata.normalize("NFC", str(text)).casefold().strip()


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", _norm(text)).strip("-")


def _app_stem(name):
    return name[:-4] if name.lower().endswith(".app") else name


def _default_registry_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(os.path.dirname(here)), "config", "internet_app_methods.txt")


# ---------------------------------------------------------------- context --

class DetectContext(object):
    """Everything a detection needs besides the bundle itself (all injectable)."""

    def __init__(self):
        self.registry = {}          # normalized name -> (display name, method, feed_url)
        self.aliases = {}           # normalized bundle id -> registry name
        self.cask_by_app = {}       # normalized app stem -> [entry]
        self.cask_by_token = {}     # slug token -> entry (listing hint)
        self.mau_paths = []
        self.keystone_dirs = []
        self._keystone_ids = None   # lazily read once
        self._keystone_blobs = None
        self.diagnostics = []


def parse_registry(text):
    """Parse ``Name|method|STATUS_VAR[|feed_url]`` lines into a lookup dict."""
    reg = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            continue
        feed = parts[3] if len(parts) > 3 and parts[3] else None
        for alias in parts[0].split(" / "):
            alias = alias.strip()
            if alias:
                reg.setdefault(_norm(alias), (parts[0], parts[1], feed))
    return reg


def _cask_app_names(cask):
    """App artifact basenames from a cask JSON dict ({"app": [...]} artifacts)."""
    names = []
    arts = cask.get("artifacts") if isinstance(cask, dict) else None
    for art in arts if isinstance(arts, list) else []:
        if not isinstance(art, dict) or "app" not in art:
            continue
        items = art["app"]
        if isinstance(items, (str, dict)):
            items = [items]
        for item in items if isinstance(items, list) else []:
            if isinstance(item, str):
                name = os.path.basename(item)
            elif isinstance(item, dict) and isinstance(item.get("target"), str):
                name = os.path.basename(item["target"])
            else:
                continue
            if name.lower().endswith(".app"):
                names.append(name)
    return names


def _read_small_json(path):
    try:
        with open(path, "rb") as fh:
            data = fh.read(MAX_PLIST + 1)
        if len(data) > MAX_PLIST:
            return None
        return json.loads(data.decode("utf-8"))
    except (OSError, ValueError):
        return None


def _add_cask(ctx, token, app_names, version, source):
    entry = dict(token=token, version=version, source=source)
    for name in app_names:
        bucket = ctx.cask_by_app.setdefault(_norm(_app_stem(name)), [])
        if not any(e["token"] == token for e in bucket):
            bucket.append(entry)


def _load_brew_info(ctx, brew_info):
    if isinstance(brew_info, str):
        try:
            brew_info = json.loads(brew_info)
        except ValueError:
            ctx.diagnostics.append("brew info JSON is not valid JSON")
            return
    casks = brew_info.get("casks") if isinstance(brew_info, dict) else brew_info
    if not isinstance(casks, list):
        ctx.diagnostics.append("brew info JSON has no casks list")
        return
    for cask in casks:
        if not isinstance(cask, dict) or not isinstance(cask.get("token"), str):
            continue
        installed = cask.get("installed")
        version = installed if isinstance(installed, str) else None
        _add_cask(ctx, cask["token"], _cask_app_names(cask), version, "brew_info")


def _load_caskroom(ctx, caskroom):
    try:
        tokens = sorted(e for e in os.listdir(caskroom) if not e.startswith("."))
    except OSError:
        return
    for token in tokens:
        tdir = os.path.join(caskroom, token)
        if not os.path.isdir(tdir):
            continue
        version = None
        names = []
        source = "caskroom_listing"
        try:
            versions = sorted(e for e in os.listdir(tdir) if not e.startswith("."))
        except OSError:
            versions = []
        for ver in versions:
            vdir = os.path.join(tdir, ver)
            try:
                for entry in os.listdir(vdir):
                    if entry.lower().endswith(".app"):
                        names.append(entry)
                        version = ver
            except OSError:
                continue
        if names:
            _add_cask(ctx, token, names, version, "caskroom_listing")
        meta = os.path.join(tdir, ".metadata")
        try:
            vers = sorted(e for e in os.listdir(meta) if not e.startswith("."))
        except OSError:
            vers = []
        for ver in reversed(vers):
            vmeta = os.path.join(meta, ver)
            try:
                stamps = sorted(os.listdir(vmeta))
            except OSError:
                continue
            for stamp in reversed(stamps):
                data = _read_small_json(os.path.join(vmeta, stamp, "Casks", token + ".json"))
                meta_names = _cask_app_names(data) if data else []
                if meta_names:
                    _add_cask(ctx, token, meta_names, ver, "caskroom_metadata")
                    source = "caskroom_metadata"
                    break
            if source == "caskroom_metadata":
                break
        if not names and source == "caskroom_listing":
            # Token known, app names unknown: kept only as a weak name hint.
            ctx.cask_by_token.setdefault(_slug(token), dict(token=token, version=version, source="caskroom_token"))


def load_brew_info_file(path):
    """Read a ``brew info --json=v2 --installed`` capture; None when unreadable."""
    try:
        with open(path, "rb") as fh:
            return json.loads(fh.read().decode("utf-8"))
    except (OSError, ValueError):
        return None


def _default_alias_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(os.path.dirname(here)), "config", "app_aliases.tsv")


def parse_aliases(text):
    """Parse ``bundle_id<TAB>registry_name`` lines (``#`` comments allowed)."""
    out = {}
    for raw in text.splitlines():
        line = raw.strip("\r\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].strip() and parts[1].strip():
            out.setdefault(_norm(parts[0]), parts[1].strip())
    return out


def build_context(brew_info=None, registry_path=_DEFAULT, caskroom_dirs=_DEFAULT,
                  mau_paths=_DEFAULT, keystone_dirs=_DEFAULT, alias_path=_DEFAULT):
    """Collect shared lookups once per scan.

    ``brew_info`` is the parsed (or raw string) ``brew info --json=v2
    --installed`` blob. Pass an empty list/None-like value to disable a source:
    ``caskroom_dirs=[]``, ``mau_paths=[]``, ``keystone_dirs=[]``,
    ``registry_path=None``, ``alias_path=None``. Leaving a default means "use
    the real location".
    """
    ctx = DetectContext()
    if alias_path is _DEFAULT:
        alias_path = _default_alias_path()
    if alias_path:
        try:
            with open(alias_path, "r", encoding="utf-8") as fh:
                ctx.aliases = parse_aliases(fh.read())
        except (OSError, UnicodeDecodeError):
            ctx.diagnostics.append("alias table unreadable: " + os.path.basename(str(alias_path)))
    if registry_path is _DEFAULT:
        registry_path = _default_registry_path()
    if registry_path:
        try:
            with open(registry_path, "r", encoding="utf-8") as fh:
                ctx.registry = parse_registry(fh.read())
        except (OSError, UnicodeDecodeError):
            ctx.diagnostics.append("registry unreadable: " + os.path.basename(str(registry_path)))
    if brew_info is not None:
        _load_brew_info(ctx, brew_info)
    roots = DEFAULT_CASKROOMS if caskroom_dirs is _DEFAULT else caskroom_dirs
    for root in roots or ():
        _load_caskroom(ctx, os.path.expanduser(root))
    ctx.mau_paths = [os.path.expanduser(p) for p in (DEFAULT_MAU_PATHS if mau_paths is _DEFAULT else mau_paths) or ()]
    ctx.keystone_dirs = [os.path.expanduser(p) for p in (DEFAULT_KEYSTONE_DIRS if keystone_dirs is _DEFAULT else keystone_dirs) or ()]
    return ctx


def _keystone_has_ticket(ctx, bundle_id):
    """True when a Keystone ticket directory mentions this product id."""
    if not bundle_id:
        return False
    if ctx._keystone_ids is None:
        ids = set()
        blobs = []
        for base in ctx.keystone_dirs:
            try:
                for name in os.listdir(os.path.join(base, "Actives")):
                    ids.add(name)
            except OSError:
                pass
            store = os.path.join(base, "TicketStore")
            try:
                for name in sorted(os.listdir(store))[:50]:
                    full = os.path.join(store, name)
                    if os.path.isfile(full) and not os.path.islink(full):
                        with open(full, "rb") as fh:
                            blobs.append(fh.read(MAX_TICKET_FILE))
            except OSError:
                pass
        ctx._keystone_ids = ids
        ctx._keystone_blobs = blobs
    if bundle_id in ctx._keystone_ids:
        return True
    needle = bundle_id.encode("utf-8", "ignore")
    return any(needle in blob for blob in ctx._keystone_blobs)


# ------------------------------------------------------------ bundle reads --

def _inside(path, root):
    try:
        return os.path.commonpath((path, root)) == root
    except ValueError:
        return False


class _Bundle(object):
    """Cheap, bounded facts about one bundle; nothing is executed."""

    def __init__(self, path):
        self.path = path
        self.stem = _app_stem(os.path.basename(path.rstrip("/")))
        self.diag = []
        self.plist = {}
        try:
            self.real = os.path.realpath(path)
        except (OSError, ValueError):
            self.real = path
        self._read_plist()

    def _plist_candidates(self):
        yield os.path.join(self.real, "Contents", "Info.plist")
        wrapper = os.path.join(self.real, "Wrapper")
        try:
            for entry in sorted(os.listdir(wrapper)):
                if entry.lower().endswith(".app"):
                    yield os.path.join(wrapper, entry, "Info.plist")
        except OSError:
            return

    def _read_plist(self):
        last_error = "Info.plist missing"
        for plist in self._plist_candidates():
            try:
                st = os.lstat(plist)
            except OSError:
                continue
            try:
                if stat.S_ISLNK(st.st_mode) or not _inside(os.path.realpath(plist), self.real):
                    raise OSError("unsafe Info.plist")
                fd = os.open(plist, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
                with os.fdopen(fd, "rb") as fh:
                    if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
                        raise OSError("Info.plist not a regular file")
                    data = fh.read(MAX_PLIST + 1)
                if len(data) > MAX_PLIST:
                    raise ValueError("Info.plist too large")
                info = plistlib.loads(data)
                if not isinstance(info, dict):
                    raise ValueError("Info.plist is not a dictionary")
                self.plist = info
                return
            except (OSError, ValueError, plistlib.InvalidFileException) as exc:
                last_error = "Info.plist unreadable (%s)" % type(exc).__name__
            except Exception as exc:  # expat errors and similar parser failures
                last_error = "Info.plist unreadable (%s)" % type(exc).__name__
        self.diag.append(last_error)

    def s(self, key):
        value = self.plist.get(key)
        return value if isinstance(value, str) and 0 < len(value) <= MAX_TEXT else None

    def marker(self, rel, directory=False):
        full = os.path.join(self.real, rel)
        try:
            st = os.lstat(full)
        except OSError:
            return False
        if stat.S_ISLNK(st.st_mode):
            return False
        return stat.S_ISDIR(st.st_mode) if directory else stat.S_ISREG(st.st_mode)

    def read_small(self, rel):
        full = os.path.join(self.real, rel)
        try:
            if not self.marker(rel):
                return None
            with open(full, "rb") as fh:
                return fh.read(MAX_SMALL_FILE).decode("utf-8", "replace")
        except OSError:
            return None

    def path_parts(self):
        parts = []
        for p in (self.path, self.real):
            parts.extend(_norm(x) for x in p.split(os.sep) if x)
        return parts


def _result(b, method, origin, confidence, evidence, **extra):
    rec = dict(
        id=b.s("CFBundleIdentifier"),
        name=b.stem,
        version=b.s("CFBundleShortVersionString"),
        build=b.s("CFBundleVersion"),
        path=b.path,
        team_id=None,
        method=method,
        method_origin=origin,
        confidence=confidence,
        evidence=list(evidence),
        feed_url=None,
        notes=list(b.diag),
        registry_method=None,
        managed_by=None,
        sparkle=None,
        hidden=False,
    )
    rec.update(extra)
    return rec


# --------------------------------------------------------------- detectors --
# Each detector: (bundle, ctx) -> None or (method, confidence, evidence, extra).

def _registry_lookup(b, ctx):
    """Alias table by bundle id first, then names, then the bundle id itself."""
    bid = b.s("CFBundleIdentifier")
    if bid and _norm(bid) in ctx.aliases:
        target = ctx.aliases[_norm(bid)]
        if _norm(target) in ctx.registry:
            return ctx.registry[_norm(target)], "alias:" + bid
    keys = [b.stem, b.s("CFBundleName"), b.s("CFBundleDisplayName"), b.s("CFBundleIdentifier")]
    for key in keys:
        if key and _norm(key) in ctx.registry:
            return ctx.registry[_norm(key)], key
    return None, None


def _detect_appstore(b, ctx):
    if b.marker("Contents/_MASReceipt/receipt"):
        return "appstore", "high", ["Contents/_MASReceipt/receipt"], {}
    if b.marker("Wrapper/iTunesMetadata.plist"):
        return "appstore", "high", ["Wrapper/iTunesMetadata.plist"], {}
    return None


def _detect_brew_cask(b, ctx):
    key = _norm(b.stem)
    entries = ctx.cask_by_app.get(key)
    if entries:
        entry = sorted(entries, key=lambda e: e["token"])[0]
        notes = []
        if len(entries) > 1:
            notes.append("also matched casks: " + ", ".join(sorted(e["token"] for e in entries)[1:]))
        ver = b.s("CFBundleShortVersionString")
        if entry.get("version") and ver and ver not in entry["version"]:
            notes.append("cask version %s differs from app version %s" % (entry["version"], ver))
        conf = "medium" if entry["source"] == "caskroom_listing" else "high"
        if entry["source"] == "caskroom_listing":
            notes.append("cask matched from Caskroom listing only")
        return "brew_cask", conf, ["cask:%s (%s)" % (entry["token"], entry["source"])], dict(notes=notes)
    hint = ctx.cask_by_token.get(_slug(b.stem))
    if hint:
        return ("brew_cask", "medium", ["cask:%s (token name hint)" % hint["token"]],
                dict(notes=["cask matched by token name only"]))
    return None


def _detect_setapp(b, ctx):
    bid = b.s("CFBundleIdentifier") or ""
    if bid.lower().endswith("-setapp"):
        return "setapp", "high", ["bundle id suffix -setapp"], dict(managed_by="Setapp")
    if "setapp" in b.path_parts():
        return "setapp", "high", ["path under Setapp directory"], dict(managed_by="Setapp")
    return None


def _detect_managed(b, ctx):
    bid = (b.s("CFBundleIdentifier") or "").lower()
    parts = b.path_parts()
    if bid.startswith("com.adobe.") or any(p == "adobe" or p.startswith("adobe ") for p in parts):
        ev = ["bundle id com.adobe.*"] if bid.startswith("com.adobe.") else ["path under Adobe directory"]
        return "adobe", "medium", ev, dict(managed_by="Adobe Creative Cloud")
    real_lower = b.real.lower()
    if "/jetbrains/toolbox/" in real_lower or "jetbrains toolbox" in parts:
        return ("jetbrains_toolbox", "medium", ["path under JetBrains Toolbox"],
                dict(managed_by="JetBrains Toolbox"))
    if bid.startswith("com.jetbrains.") and bid != "com.jetbrains.toolbox":
        return ("jetbrains_toolbox", "low", ["bundle id com.jetbrains.*"],
                dict(managed_by="JetBrains Toolbox",
                     notes=["no Toolbox path evidence; the IDE may use its built-in updater"]))
    return None


def _detect_system(b, ctx):
    if b.real.startswith("/System/") or b.path.startswith("/System/"):
        return "system", "high", ["path under /System"], {}
    if (b.s("CFBundleIdentifier") or "").lower().startswith("com.apple."):
        return "system", "medium", ["bundle id com.apple.*"], {}
    return None


def _detect_sparkle(b, ctx):
    feed = b.s("SUFeedURL")
    ed = b.s("SUPublicEDKey")
    dsa = b.s("SUPublicDSAKeyFile") or b.s("SUPublicDSAKey")
    framework = b.marker("Contents/Frameworks/Sparkle.framework", directory=True)
    if not feed and not framework and not ed:
        return None
    evidence = []
    if feed:
        evidence.append("Info.plist:SUFeedURL")
    if ed:
        evidence.append("Info.plist:SUPublicEDKey")
    if dsa:
        evidence.append("Info.plist:SUPublicDSA")
    if b.plist.get("SUEnableAutomaticChecks") is not None:
        evidence.append("Info.plist:SUEnableAutomaticChecks")
    if framework:
        evidence.append("Contents/Frameworks/Sparkle.framework")
    https = bool(feed) and urlparse(feed).scheme.lower() == "https"
    notes = []
    if feed and ed and https:
        conf = "high"
    elif feed and dsa and not ed:
        conf = "low"
        notes.append("DSA-only Sparkle signing; not eligible for automatic install")
    else:
        conf = "medium"
        if feed and not https:
            notes.append("Sparkle feed is not https")
        if not feed:
            notes.append("no SUFeedURL; feed may be set in code")
    info = dict(
        feed_url=feed,
        public_ed_key_present=bool(ed),
        public_dsa_present=bool(dsa),
        auto_checks=b.plist.get("SUEnableAutomaticChecks") if isinstance(b.plist.get("SUEnableAutomaticChecks"), bool) else None,
        framework=framework,
    )
    return "sparkle", conf, evidence, dict(feed_url=feed, notes=notes, sparkle=info)


_YML_KEYS = ("provider", "url", "owner", "repo", "channel")


def _parse_update_yml(text):
    out = {}
    for line in (text or "").splitlines():
        m = re.match(r"^\s*([A-Za-z]+)\s*:\s*(.+?)\s*$", line)
        if m and m.group(1) in _YML_KEYS:
            out.setdefault(m.group(1), m.group(2).strip("'\""))
    return out


def _detect_electron_squirrel(b, ctx):
    electron = b.marker("Contents/Frameworks/Electron Framework.framework", directory=True)
    yml_text = b.read_small("Contents/Resources/app-update.yml")
    if yml_text is not None:
        cfg = _parse_update_yml(yml_text)
        evidence = ["Contents/Resources/app-update.yml"]
        if cfg.get("provider"):
            evidence.append("app-update.yml:provider=" + cfg["provider"])
        feed = cfg.get("url")
        if not feed and cfg.get("provider") == "github" and cfg.get("owner") and cfg.get("repo"):
            feed = "https://github.com/%s/%s" % (cfg["owner"], cfg["repo"])
        if electron:
            evidence.append("Electron Framework.framework")
        return "electron_updater", "medium", evidence, dict(feed_url=feed)
    if b.marker("Contents/Frameworks/Squirrel.framework", directory=True):
        notes = []
        if electron:
            notes.append("Squirrel.framework ships in every Electron app and may be unused")
        return "squirrel", "medium", ["Contents/Frameworks/Squirrel.framework"], dict(notes=notes)
    return None


def _detect_keystone(b, ctx):
    bid = b.s("CFBundleIdentifier") or ""
    ks_keys = [k for k in ("KSProductID", "KSUpdateURL") if b.s(k)]
    google = bid.lower().startswith("com.google.")
    ticket = google and _keystone_has_ticket(ctx, b.s("KSProductID") or bid)
    if not ks_keys and not ticket:
        return None
    evidence = ["Info.plist:" + k for k in ks_keys]
    if ticket:
        evidence.append("Keystone ticket for " + bid)
    conf = "high" if ticket else "medium"
    return "keystone", conf, evidence, dict(feed_url=b.s("KSUpdateURL"))


def _detect_mau(b, ctx):
    bid = (b.s("CFBundleIdentifier") or "").lower()
    if not bid.startswith("com.microsoft."):
        return None
    present = next((p for p in ctx.mau_paths if os.path.isdir(p)), None)
    if bid == "com.microsoft.autoupdate2":
        return "microsoft_autoupdate", "high", ["bundle id com.microsoft.autoupdate2 (Microsoft AutoUpdate itself)"], {}
    if present is None:
        return None
    return "microsoft_autoupdate", "high", ["bundle id com.microsoft.*", "Microsoft AutoUpdate present"], {}


_DETECTORS = (
    _detect_appstore, _detect_brew_cask, _detect_setapp, _detect_managed,
    _detect_system, _detect_sparkle, _detect_electron_squirrel,
    _detect_keystone, _detect_mau,
)


def _detect_tested(b, ctx, structural):
    """A registry row always wins with its mapped method, confidence high."""
    row, matched = _registry_lookup(b, ctx)
    if not row:
        return None
    display, reg_method, reg_feed = row
    method = REGISTRY_METHOD_MAP.get(reg_method, REGISTRY_DEFAULT_METHOD)
    evidence = ["registry:%s|%s (matched %s)" % (display, reg_method, matched)]
    extra = dict(registry_method=reg_method)
    if reg_method not in REGISTRY_METHOD_MAP:
        extra["notes"] = ["unknown registry method %s treated as vendor_download" % reg_method]
    found = structural()
    if found and found.get("feed_url"):
        extra["feed_url"] = found["feed_url"]
        if found.get("sparkle"):
            extra["sparkle"] = found["sparkle"]
    if reg_feed:
        extra["feed_url"] = reg_feed
    return method, "high", evidence, extra


def _detect_browser_app(b):
    """PWA wrappers created by Chromium browsers; the browser owns them."""
    bid = (b.s("CFBundleIdentifier") or "").lower()
    for prefix, browser in BROWSER_APP_PREFIXES:
        if bid.startswith(prefix):
            return browser, "bundle id " + prefix + "*"
    for part in b.path_parts():
        key = part[:-len(".localized")] if part.endswith(".localized") else part
        for dirname, browser in BROWSER_APP_DIRS:
            if key == dirname:
                return browser, "path under " + dirname.title() + " folder"
    return None


def _helper_by_name(b):
    low = b.stem.casefold()
    for suffix in HELPER_NAME_SUFFIXES:
        if low.endswith(suffix):
            return "name ends with " + suffix
    bid = (b.s("CFBundleIdentifier") or "").lower()
    for prefix in HELPER_ID_PREFIXES:
        if bid.startswith(prefix):
            return "bundle id " + prefix + "*"
    return None


def _is_background_only(b):
    return b.plist.get("LSUIElement") in (True, 1, "1") or b.plist.get("LSBackgroundOnly") in (True, 1, "1")


# --------------------------------------------------------------- signature --

def _default_runner(argv, timeout):
    """Run argv without a shell; returns (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return None, "", "timeout"
    except (OSError, ValueError) as exc:
        return None, "", type(exc).__name__
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


def read_team_id(path, runner=None, timeout=CODESIGN_TIMEOUT):
    """Team ID via ``codesign -dv --verbose=2``; (team_id_or_None, note_or_None)."""
    run = runner or _default_runner
    try:
        code, out, err = run(["/usr/bin/codesign", "-dv", "--verbose=2", path], timeout)
    except Exception as exc:  # an injected runner must never break a scan
        return None, "codesign failed (%s)" % type(exc).__name__
    if code is None:
        return None, "codesign did not complete (%s)" % (err or "unknown")
    text = (out or "") + "\n" + (err or "")
    m = re.search(r"^TeamIdentifier=(\S+)", text, re.M)
    if m and m.group(1) != "not":
        return m.group(1), None
    if code != 0:
        return None, "codesign exit %s" % code
    return None, "no Team ID (unsigned or ad-hoc)"


# ----------------------------------------------------------------- main API --

def detect_app(path, ctx=None, with_signature=False, runner=None):
    """Return one detection record for the bundle at ``path``. Never raises."""
    ctx = ctx if ctx is not None else build_context()
    try:
        b = _Bundle(path)
    except Exception as exc:  # last-resort guard: a scan must survive any bundle
        stub = _Bundle.__new__(_Bundle)
        stub.path, stub.real, stub.plist = path, path, {}
        stub.stem = _app_stem(os.path.basename(path.rstrip("/")))
        stub.diag = ["bundle unreadable (%s)" % type(exc).__name__]
        return _result(stub, "manual", "manual", "low", [])

    cache = []

    def structural():
        if not cache:
            cache.append(_run_chain(b, ctx))
        return cache[0]

    hit = None
    origin = "detected"
    hidden = False
    browser = _detect_browser_app(b)
    if browser:
        hit = ("browser_app", "high", [browser[1]],
               dict(managed_by=browser[0], notes=["browser-hosted app; updated with " + browser[0]]))
        hidden = True
    if hit is None:
        try:
            hit = _detect_tested(b, ctx, structural)
            if hit is not None:
                origin = "tested"
        except Exception as exc:
            b.diag.append("registry lookup failed (%s)" % type(exc).__name__)
    if hit is None:
        helper = _helper_by_name(b)
        if helper:
            hit = ("manual", "low", [helper], dict(notes=["helper"]))
            origin = "manual"
            hidden = True
    if hit is None:
        found = structural()
        if found is not None:
            hit = (found["method"], found["confidence"], found["evidence"], found["extra"])
    if hit is None:
        origin = "manual"
        extra_notes = []
        bid = (b.s("CFBundleIdentifier") or "").lower()
        if bid.startswith("com.microsoft.") and not any(os.path.isdir(p) for p in ctx.mau_paths):
            extra_notes.append("com.microsoft.* but Microsoft AutoUpdate not found")
        evidence_bg = []
        if _is_background_only(b):
            hidden = True
            extra_notes.append("helper")
            evidence_bg.append("Info.plist:LSUIElement/LSBackgroundOnly")
        hit = ("manual", "low", evidence_bg, dict(notes=extra_notes))
    method, conf, evidence, extra = hit
    extra = dict(extra)
    notes = list(b.diag) + list(extra.pop("notes", []))
    rec = _result(b, method, origin, conf, evidence, **extra)
    rec["notes"] = notes
    rec["hidden"] = hidden
    if method in MANAGED_ELSEWHERE:
        rec["notes"].append("managed by %s; the toolkit does not update this app" % (rec["managed_by"] or method))
    if with_signature and method == "sparkle":
        team, note = read_team_id(b.real, runner)
        rec["team_id"] = team
        if note:
            rec["notes"].append(note)
    return rec


def _run_chain(b, ctx):
    for detector in _DETECTORS:
        try:
            hit = detector(b, ctx)
        except Exception as exc:
            b.diag.append("%s failed (%s)" % (getattr(detector, "__name__", "detector").lstrip("_"), type(exc).__name__))
            continue
        if hit:
            method, conf, evidence, extra = hit
            return dict(method=method, confidence=conf, evidence=evidence, extra=extra,
                        feed_url=extra.get("feed_url"), sparkle=extra.get("sparkle"))
    return None


def _iter_bundle_paths(root, diagnostics, max_depth=2):
    """Yield .app paths under root: apps directly inside it and inside up to
    ``max_depth`` levels of plain sub-folders (Utilities, Setapp, Adobe ...).
    Symlinked folders are not followed; .app bundles are never entered."""
    stack = [(root, 0)]
    while stack:
        current, depth = stack.pop(0)
        try:
            with os.scandir(current) as it:
                entries = sorted(it, key=lambda e: e.name)
        except OSError as exc:
            diagnostics.append("cannot read %s (%s)" % (current, type(exc).__name__))
            continue
        for entry in entries:
            if entry.name.startswith("."):
                continue
            try:
                if entry.name.lower().endswith(".app"):
                    if entry.is_dir(follow_symlinks=True):
                        yield entry.path
                elif depth < max_depth and entry.is_dir(follow_symlinks=False):
                    stack.append((entry.path, depth + 1))
            except OSError:
                continue


def scan_dirs(dirs, ctx=None, with_signature=False, runner=None, diagnostics=None):
    """Detect every bundle under ``dirs``; each real bundle is reported once."""
    ctx = ctx if ctx is not None else build_context()
    diags = diagnostics if diagnostics is not None else []
    seen = set()
    records = []
    for root in dirs:
        root = os.path.expanduser(root)
        if not os.path.isdir(root):
            diags.append("not a directory: " + root)
            continue
        for app in _iter_bundle_paths(root, diags):
            try:
                real = os.path.realpath(app)
            except (OSError, ValueError):
                real = app
            if real in seen:
                continue
            seen.add(real)
            records.append(detect_app(app, ctx, with_signature=with_signature, runner=runner))
    return records


def summarize(records):
    """Counts exclude records flagged ``hidden`` (helpers, browser apps); those
    are only counted under ``hidden``."""
    visible = [r for r in records if not r.get("hidden")]
    out = dict(total=len(visible), hidden=len(records) - len(visible), method={}, origin={}, confidence={})
    for rec in visible:
        for field in ("method", "origin", "confidence"):
            key = rec["method_origin"] if field == "origin" else rec[field]
            out[field][key] = out[field].get(key, 0) + 1
    return out


def app_info_from_record(rec):
    """Shape a detection record as ``app_info`` for sparkle_auto_install_allowed."""
    sp = rec.get("sparkle") or {}
    return dict(
        id=rec.get("id"),
        version=rec.get("version"),
        build=rec.get("build"),
        team_id=rec.get("team_id"),
        feed_url=rec.get("feed_url") or sp.get("feed_url"),
        has_public_ed_key=bool(sp.get("public_ed_key_present")),
    )


# ------------------------------------------------- Sparkle verification gate --

FALLBACK_OPEN_APP_UPDATER = "open_app_updater"   # reported as vendor_updater_opened
FALLBACK_MANUAL = "manual"

# reason code -> fallback ("open_app_updater" or "manual"); "ok" -> None
SPARKLE_REASONS = {
    "ok": None,
    "invalid_input": FALLBACK_MANUAL,
    "feed_not_https": FALLBACK_OPEN_APP_UPDATER,
    "enclosure_not_https": FALLBACK_OPEN_APP_UPDATER,
    "enclosure_host_not_allowed": FALLBACK_OPEN_APP_UPDATER,
    "delta_enclosure": FALLBACK_OPEN_APP_UPDATER,
    "pkg_enclosure": FALLBACK_OPEN_APP_UPDATER,
    "app_has_no_ed_key": FALLBACK_OPEN_APP_UPDATER,
    "no_ed_signature": FALLBACK_OPEN_APP_UPDATER,
    "ed_signature_unchecked": FALLBACK_OPEN_APP_UPDATER,
    "ed_signature_invalid": FALLBACK_OPEN_APP_UPDATER,
    "bundle_id_mismatch": FALLBACK_OPEN_APP_UPDATER,
    "installed_unsigned": FALLBACK_OPEN_APP_UPDATER,
    "downloaded_unsigned": FALLBACK_OPEN_APP_UPDATER,
    "team_id_mismatch": FALLBACK_OPEN_APP_UPDATER,   # also log a warning: key rotation or tampering
    "downloaded_version_mismatch": FALLBACK_OPEN_APP_UPDATER,
    "version_not_newer": FALLBACK_MANUAL,            # nothing to install
    "host_version_unknown": FALLBACK_MANUAL,
    "min_system_version_unmet": FALLBACK_MANUAL,     # the vendor updater cannot help either
    "gatekeeper_failed": FALLBACK_OPEN_APP_UPDATER,
    "app_running": FALLBACK_OPEN_APP_UPDATER,        # the toolkit never quits an app
    "destination_not_writable": FALLBACK_OPEN_APP_UPDATER,
}


def compare_versions(a, b):
    """Compare two version strings Sparkle-style: -1, 0 or 1.

    Digit runs compare numerically, letter runs (pre-release tags) sort below a
    missing/numeric component, so 1.0b1 < 1.0 < 1.0.1 and 1.0 == 1.0.0."""
    def key(text):
        out = []
        for tok in re.findall(r"\d+|[A-Za-z]+", str(text)):
            out.append((1, int(tok), "") if tok.isdigit() else (0, 0, tok.lower()))
        return out
    ka, kb = key(a), key(b)
    pad = (1, 0, "")
    n = max(len(ka), len(kb))
    ka += [pad] * (n - len(ka))
    kb += [pad] * (n - len(kb))
    return (ka > kb) - (ka < kb)


def _host(url):
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _has(value):
    return isinstance(value, str) and bool(value.strip())


def sparkle_auto_install_allowed(app_info, appcast_item, downloaded_info,
                                 host_os_version=None, allowed_hosts=()):
    """Pure decision: may the toolkit install this Sparkle update by itself?

    Returns ``(allowed, reason_code, fallback)``. ``fallback`` is None when
    allowed, else ``"open_app_updater"`` (reported as vendor_updater_opened) or
    ``"manual"``; see SPARKLE_REASONS. No crypto, no I/O: signature, codesign
    and Gatekeeper outcomes arrive as parameters.

    app_info (installed app; see app_info_from_record):
        id, version (short), build, team_id, feed_url, has_public_ed_key
    appcast_item (the chosen feed item):
        version (sparkle:version), short_version, ed_signature (str or None),
        enclosure_url, minimum_system_version, is_delta, installer_type
    downloaded_info (the staged download, produced by the caller):
        bundle_id, team_id, version, build, ed_signature_valid (True/False/None
        = result of the EdDSA check over the downloaded bytes with the app's
        SUPublicEDKey), gatekeeper_passed (True/False/None), and optionally
        app_running, dest_writable (checked only when present).
    host_os_version: running macOS version, needed only when the item sets
        minimum_system_version. allowed_hosts: extra hosts the catalog allows
        for the enclosure besides the feed host.
    """
    def deny(code):
        return False, code, SPARKLE_REASONS[code]

    if not (isinstance(app_info, dict) and isinstance(appcast_item, dict) and isinstance(downloaded_info, dict)):
        return deny("invalid_input")
    if not _has(app_info.get("id")) or not (_has(app_info.get("version")) or _has(app_info.get("build"))):
        return deny("invalid_input")
    if not _has(downloaded_info.get("bundle_id")):
        return deny("invalid_input")

    feed = app_info.get("feed_url")
    if not _has(feed) or urlparse(feed).scheme.lower() != "https":
        return deny("feed_not_https")
    enclosure = appcast_item.get("enclosure_url")
    if _has(enclosure):
        if urlparse(enclosure).scheme.lower() != "https":
            return deny("enclosure_not_https")
        ok_hosts = set(h.lower() for h in allowed_hosts) | set([_host(feed)])
        if _host(enclosure) not in ok_hosts:
            return deny("enclosure_host_not_allowed")
    if appcast_item.get("is_delta"):
        return deny("delta_enclosure")
    if (str(appcast_item.get("installer_type") or "").lower() == "pkg"
            or (_has(enclosure) and urlparse(enclosure).path.lower().endswith(".pkg"))):
        return deny("pkg_enclosure")

    if not app_info.get("has_public_ed_key"):
        return deny("app_has_no_ed_key")
    if not _has(appcast_item.get("ed_signature")):
        return deny("no_ed_signature")
    sig = downloaded_info.get("ed_signature_valid")
    if sig is None:
        return deny("ed_signature_unchecked")
    if sig is not True:
        return deny("ed_signature_invalid")

    if downloaded_info.get("bundle_id") != app_info.get("id"):
        return deny("bundle_id_mismatch")
    installed_team, new_team = app_info.get("team_id"), downloaded_info.get("team_id")
    if not _has(installed_team):
        return deny("installed_unsigned")
    if not _has(new_team):
        return deny("downloaded_unsigned")
    if installed_team != new_team:
        return deny("team_id_mismatch")

    short, build = appcast_item.get("short_version"), appcast_item.get("version")
    if _has(downloaded_info.get("version")) and _has(short) and compare_versions(downloaded_info["version"], short) != 0:
        return deny("downloaded_version_mismatch")
    if _has(downloaded_info.get("build")) and _has(build) and compare_versions(downloaded_info["build"], build) != 0:
        return deny("downloaded_version_mismatch")
    cmps = []
    if _has(build) and _has(app_info.get("build")):
        cmps.append(compare_versions(build, app_info["build"]))
    if _has(short) and _has(app_info.get("version")):
        cmps.append(compare_versions(short, app_info["version"]))
    if not cmps:
        return deny("invalid_input")
    if not (all(c >= 0 for c in cmps) and any(c > 0 for c in cmps)):
        return deny("version_not_newer")

    minimum = appcast_item.get("minimum_system_version")
    if _has(minimum):
        if not _has(host_os_version):
            return deny("host_version_unknown")
        if compare_versions(host_os_version, minimum) < 0:
            return deny("min_system_version_unmet")

    gk = downloaded_info.get("gatekeeper_passed")
    if gk is not True:
        return deny("gatekeeper_failed")
    if downloaded_info.get("app_running") is True:
        return deny("app_running")
    if downloaded_info.get("dest_writable") is False:
        return deny("destination_not_writable")
    return True, "ok", None
