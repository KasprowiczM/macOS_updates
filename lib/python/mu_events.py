"""Append-only JSON-lines event channel for user interfaces.

Usage (normally through lib/events.sh):
    python3 mu_events.py emit FILE TYPE [key=value | key:=json] ...
    python3 mu_events.py group-end FILE GROUP RESULT SECONDS [CHECKED]

``group_end`` carries an optional ``checked`` count (things looked at, when only
some got an item row), taken from CHECKED or the latest ``group_checked`` event
of the group; it is left out when neither exists.

Every event is one JSON object on its own line with at least ``ts`` (UTC,
ISO 8601, milliseconds) and ``type``. ``MAC_UPDATE_RUN_ID`` is attached as
``run_id`` when set, so several runs may share a file. The module never
writes to stdout; a failure to write is silent by design (the event channel
must never change or break an update run).
"""

import datetime
import json
import os
import sys

# "available" is a preview (dry-run) result: the item would be updated.
ITEM_RESULTS = ("updated", "available", "current", "needs_you", "failed", "skipped")
SESSION_ITEMS = "item_events.jsonl"
MAX_VALUE = 4096


def _now():
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (now.microsecond // 1000)


def _clean(value):
    if isinstance(value, str):
        return value[:MAX_VALUE]
    if isinstance(value, list):
        return [_clean(v) for v in value[:500]]
    if isinstance(value, dict):
        return {str(k)[:128]: _clean(v) for k, v in list(value.items())[:100]}
    return value


def parse_fields(args):
    """``k=v`` is a string; ``k:=v`` is JSON (numbers, arrays, null)."""
    fields = {}
    for arg in args:
        if "=" not in arg:
            continue
        key, value = arg.split("=", 1)
        if key.endswith(":"):
            key = key[:-1]
            try:
                value = json.loads(value)
            except ValueError:
                pass
        key = key.strip()
        if not key or key in ("ts", "type") or not key.replace("_", "").isalnum():
            continue
        fields[key] = _clean(value)
    return fields


def build_event(event_type, fields, run_id=None):
    event = {"ts": _now(), "type": str(event_type)[:64]}
    if run_id:
        event["run_id"] = str(run_id)[:128]
    for key, value in fields.items():
        event.setdefault(key, value)
    return event


def append_event(path, event):
    line = (json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def read_events(path):
    rows = []
    try:
        with open(path, encoding="utf-8", errors="replace") as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        pass
    return rows


def group_counts(path, group, run_id=None):
    """Latest item_end per item id for one group (and run, when known)."""
    final = {}
    for row in read_events(path):
        if row.get("type") != "item_end" or row.get("group") != group:
            continue
        if run_id and row.get("run_id") not in (None, run_id):
            continue
        final[str(row.get("id"))] = row.get("result")
    counts = {key: 0 for key in ITEM_RESULTS}
    for result in final.values():
        if result in counts:
            counts[result] += 1
    return counts


def group_checked(path, group, run_id=None):
    """Latest ``group_checked`` count for one group (and run), or None."""
    found = None
    for row in read_events(path):
        if row.get("type") != "group_checked" or row.get("group") != group:
            continue
        if run_id and row.get("run_id") not in (None, run_id):
            continue
        value = row.get("checked")
        if type(value) is int and value >= 0:
            found = value
    return found


def main(argv):
    try:
        if len(argv) >= 3 and argv[0] == "emit":
            path, event_type = argv[1], argv[2]
            event = build_event(event_type, parse_fields(argv[3:]), os.environ.get("MAC_UPDATE_RUN_ID"))
            if event_type == "item_end" and not event.get("name"):
                event.pop("name", None)
            if path:
                append_event(path, event)
            session = os.environ.get("MAC_UPDATE_SESSION_DIR")
            if event_type in ("item_start", "item_end") and session and os.path.isdir(session):
                append_event(os.path.join(session, SESSION_ITEMS), event)
            return 0
        if len(argv) in (5, 6) and argv[0] == "group-end":
            path, group, result, seconds = argv[1:5]
            run_id = os.environ.get("MAC_UPDATE_RUN_ID")
            counts = group_counts(path, group, run_id)
            try:
                secs = int(seconds)
            except ValueError:
                secs = None
            fields = dict(group=group, result=result, updated=counts["updated"],
                          available=counts["available"], current=counts["current"], needs_you=counts["needs_you"],
                          failed=counts["failed"], skipped=counts["skipped"], seconds=secs)
            checked = None
            if len(argv) == 6:
                try:
                    checked = max(0, int(argv[5]))
                except ValueError:
                    checked = None
            if checked is None:
                checked = group_checked(path, group, run_id)
            if checked is not None:
                fields["checked"] = checked
            append_event(path, build_event("group_end", fields, run_id))
            return 0
    except (OSError, ValueError, TypeError):
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
