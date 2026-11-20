#!/usr/bin/env python3
"""Read-only scan: how can each installed app be updated?

Usage: detect_apps.py [--dir DIR ...] [--brew-json FILE] [--json] [--system]
                      [--signatures]

Reads bundles only (plist and marker files). Never launches an app, never
touches the network, never calls brew; pass ``--brew-json`` a capture of
``brew info --json=v2 --installed`` to map Homebrew casks to apps.
``--signatures`` additionally runs codesign (Sparkle apps only) for Team IDs.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib", "python"))

import app_detect  # noqa: E402

DEFAULT_DIRS = ("/Applications", "~/Applications")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Detect the update method of installed macOS apps (read-only).")
    ap.add_argument("--dir", action="append", dest="dirs", metavar="DIR",
                    help="app directory to scan (repeatable; default /Applications and ~/Applications)")
    ap.add_argument("--brew-json", metavar="FILE", help="saved output of: brew info --json=v2 --installed")
    ap.add_argument("--json", action="store_true", help="print records and summary as JSON")
    ap.add_argument("--system", action="store_true", help="also scan /System/Applications")
    ap.add_argument("--all", action="store_true", dest="show_hidden",
                    help="list hidden helpers and browser-hosted apps too (they are never counted)")
    ap.add_argument("--signatures", action="store_true", help="read Team IDs with codesign for Sparkle apps")
    args = ap.parse_args(argv)

    brew = None
    if args.brew_json:
        brew = app_detect.load_brew_info_file(args.brew_json)
        if brew is None:
            print("warning: could not read --brew-json file; cask detection falls back to Caskroom listing", file=sys.stderr)
    dirs = list(args.dirs) if args.dirs else list(DEFAULT_DIRS)
    if args.system:
        dirs.append("/System/Applications")

    ctx = app_detect.build_context(brew_info=brew)
    diagnostics = list(ctx.diagnostics)
    records = app_detect.scan_dirs(dirs, ctx, with_signature=args.signatures, diagnostics=diagnostics)
    records.sort(key=lambda r: (r["name"].casefold(), r["path"]))
    summary = app_detect.summarize(records)

    if args.json:
        json.dump(dict(apps=records, summary=summary, diagnostics=diagnostics), sys.stdout,
                  indent=2, ensure_ascii=False, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    shown = records if args.show_hidden else [r for r in records if not r["hidden"]]
    width = min(40, max([4] + [len(r["name"]) for r in shown]))
    print("%-*s  %-14s  %-20s  %-8s  %s" % (width, "NAME", "VERSION", "METHOD", "ORIGIN", "CONFIDENCE"))
    for r in shown:
        print("%-*s  %-14s  %-20s  %-8s  %s" % (
            width, r["name"][:width], (r["version"] or "-")[:14], r["method"],
            r["method_origin"], r["confidence"]))
    print()
    print("%d apps (%d hidden helpers/browser apps not counted)" % (summary["total"], summary["hidden"]))
    for key in ("method", "origin", "confidence"):
        counts = summary[key]
        print("by %s: %s" % (key, ", ".join("%s=%d" % (k, counts[k]) for k in sorted(counts))))
    for line in diagnostics:
        print("note: " + line, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
