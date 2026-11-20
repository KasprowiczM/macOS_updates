"""One notification per scheduled run, built from the run's event file.

    python3 run_notification.py text   --events FILE [--lang L] [--exit-code N] [--extra TEXT]
    python3 run_notification.py notify --events FILE [--mode M] [--lang L] [--exit-code N] [--extra TEXT]

``text`` prints JSON {title, subtitle, body, counts, notify}. ``notify`` also
delivers it through ``osascript``; all text travels as argv of an AppleScript
``on run argv`` handler, never interpolated into script source, so app names
with quotes or backslashes are harmless. Modes (env MAC_UPDATE_NOTIFY):
always | needs_you | never; legacy 1/true -> always, 0/false -> never.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STRINGS_FILE = os.path.join(HERE, "..", "..", "i18n", "strings", "notify.json")
LANGS = ("en", "pl", "de", "es", "fr", "it", "pt")
MAX_APPS = 3
MAX_NAME = 40
_CTRL = re.compile(r"[\x00-\x1f\x7f]+")


def load_strings(lang):
    try:
        with open(STRINGS_FILE, encoding="utf-8") as fh:
            table = json.load(fh)
    except (OSError, ValueError):
        table = {}
    merged = dict(table.get("en", {}))
    merged.update(table.get(lang, {}))
    return merged


def detect_lang(env=None, prefs_path=None):
    env = os.environ if env is None else env
    lang = env.get("MAC_UPDATE_LANG") or env.get("MAC_LANG") or ""
    if not lang and prefs_path:
        try:
            with open(prefs_path, encoding="utf-8") as fh:
                for line in fh:
                    key, _, value = line.partition("=")
                    if key.strip() == "MAC_LANG":
                        lang = value.strip()
                        break
        except OSError:
            pass
    if not lang:
        lang = (env.get("LC_ALL") or env.get("LANG") or "")[:2]
    return lang if lang in LANGS else "en"


def normalize_mode(raw, default="needs_you"):
    value = (raw or "").strip().lower()
    if value in ("always", "needs_you", "never"):
        return value
    if value in ("1", "true", "yes", "on"):
        return "always"
    if value in ("0", "false", "no", "off"):
        return "never"
    return default


def read_events(path):
    rows = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        pass
    return rows


def clean(text, limit=MAX_NAME):
    text = _CTRL.sub(" ", str(text)).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def collect(path):
    """Counts and updated names of the last run in the event file."""
    rows = read_events(path)
    start = 0
    for index, row in enumerate(rows):
        if row.get("type") == "run_start":
            start = index
    rows = rows[start:]
    names, final, order, run_result = {}, {}, [], None
    for row in rows:
        kind = row.get("type")
        key = (str(row.get("group")), str(row.get("id")))
        if kind == "item_start" and row.get("name"):
            names[key] = row["name"]
        elif kind == "item_end":
            if key not in final:
                order.append(key)
            final[key] = row.get("result")
        elif kind == "run_end":
            run_result = row.get("result")
    counts = {"updated": 0, "needs_you": 0, "failed": 0}
    updated_names = []
    for key in order:
        result = final[key]
        if result in counts:
            counts[result] += 1
        if result == "updated":
            updated_names.append(names.get(key) or key[1])
    return counts, updated_names, run_result, bool(rows)


def build(events, lang="en", exit_code=0, extra=""):
    s = load_strings(lang)
    counts, updated_names, run_result, have_events = collect(events)
    run_failed = run_result in ("error", "interrupted") or (
        exit_code not in (0, None) and counts["failed"] == 0)
    parts = []
    if counts["needs_you"]:
        parts.append(s["needs_you"].format(n=counts["needs_you"]))
    if counts["updated"]:
        parts.append(s["updated"].format(n=counts["updated"]))
    if counts["failed"]:
        parts.append(s["failed"].format(n=counts["failed"]))
    if run_failed and not counts["failed"]:
        parts.append(s["run_failed"])
    idle = not parts
    if idle:
        parts.append(s["idle"])
    subtitle = " · ".join(parts)
    body_parts = []
    if updated_names:
        shown = [clean(n) for n in updated_names[:MAX_APPS]]
        text = ", ".join(shown)
        if len(updated_names) > MAX_APPS:
            text += " +%d" % (len(updated_names) - MAX_APPS)
        body_parts.append(text)
    if counts["needs_you"]:
        body_parts.append(s["hint_needs"])
    if extra:
        body_parts.append(clean(extra, 200))
    attention = bool(counts["needs_you"] or counts["failed"] or run_failed)
    return {
        "title": s["title"], "subtitle": subtitle, "body": " ".join(body_parts),
        "counts": counts, "idle": idle and not extra, "attention": attention,
    }


def should_notify(mode, built, quiet_idle=True):
    if mode == "never":
        return False
    if mode == "needs_you":
        return built["attention"]
    return not (built["idle"] and quiet_idle)


APPLESCRIPT = (
    "on run argv",
    "display notification (item 1 of argv) with title (item 2 of argv) subtitle (item 3 of argv)",
    "end run",
)


def deliver(built):
    osa = shutil.which("osascript")
    if not osa:
        return False
    cmd = [osa]
    for line in APPLESCRIPT:
        cmd += ["-e", line]
    # "--" ends option parsing, so text starting with "-" stays an argument.
    cmd += ["--", built["body"] or built["subtitle"], built["title"],
            built["subtitle"] if built["body"] else ""]
    try:
        subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=15, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def main(argv):
    parser = argparse.ArgumentParser(prog="run_notification")
    parser.add_argument("action", choices=("text", "notify"))
    parser.add_argument("--events", default="")
    parser.add_argument("--lang", default="")
    parser.add_argument("--prefs", default="")
    parser.add_argument("--mode", default=None)
    parser.add_argument("--exit-code", type=int, default=0)
    parser.add_argument("--extra", default="")
    args = parser.parse_args(argv)
    lang = args.lang if args.lang in LANGS else detect_lang(prefs_path=args.prefs or None)
    built = build(args.events, lang, args.exit_code, args.extra)
    mode = normalize_mode(args.mode if args.mode is not None else os.environ.get("MAC_UPDATE_NOTIFY"))
    quiet = os.environ.get("MAC_UPDATE_NOTIFY_QUIET_IDLE", "1") != "0"
    built["mode"] = mode
    built["notify"] = should_notify(mode, built, quiet)
    if args.action == "text":
        print(json.dumps(built, ensure_ascii=False))
        return 0
    if built["notify"]:
        built["delivered"] = deliver(built)
    print(json.dumps({"notify": built["notify"], "mode": mode}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception:  # a notification must never fail a run
        sys.exit(0)
