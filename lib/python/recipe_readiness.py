"""Pure readiness reports and untrusted feedback, with no activation authority.

Inputs are in-memory JSON values. No catalog, journal, process or network is
changed. A report is never an acceptance record or permission to execute.
"""

import datetime
import json
import math
import re

from app_recipes import validate_recipe
from recipe_acceptance import validate_recipe_evidence
from recipe_adapters import DIRECT_ADAPTERS, prepare_recipe_action
from native_update_session import NATIVE_DRIVERS

OPERATIONS = ("update", "install", "lifecycle")
_TOKEN = re.compile(r"[A-Za-z0-9_.:@+-]{1,128}\Z")
_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9_-]{0,127}\Z")
_SHA256 = re.compile(r"[a-f0-9]{64}\Z")


def _token(value):
    return type(value) is str and bool(_TOKEN.fullmatch(value))


def _bounded_json(value, maximum):
    try:
        return len(json.dumps(value, ensure_ascii=True, allow_nan=False)) <= maximum
    except (ValueError, TypeError, RecursionError, OverflowError):
        return False


def _catalog_valid(catalog):
    if (type(catalog) is not dict or not _bounded_json(catalog, 1024 * 1024)
            or set(catalog) != {"schema_version", "metadata", "recipes"}
            or type(catalog["schema_version"]) is not int or catalog["schema_version"] != 2):
        return False
    metadata = catalog["metadata"]
    if (type(metadata) is not dict
            or set(metadata) != {"status", "matrix_ids", "excluded_products"}
            or metadata["status"] != "evidence_required"):
        return False
    for field in ("matrix_ids", "excluded_products"):
        rows = metadata[field]
        if (type(rows) is not list or len(rows) > 512
                or any(type(row) is not str or not row or len(row) > 255 for row in rows)
                or len(set(rows)) != len(rows)):
            return False
    if any(not _IDENTIFIER.fullmatch(row) for row in metadata["matrix_ids"]):
        return False
    recipes = catalog["recipes"]
    if type(recipes) is not list or len(recipes) > 512:
        return False
    ids = set()
    excluded = {item.casefold() for item in metadata["excluded_products"]}
    for recipe in recipes:
        try:
            validate_recipe(recipe)
            if (recipe["id"] in ids or recipe["product"].casefold() in excluded
                    or not set(recipe["matrix_ids"]).issubset(metadata["matrix_ids"])):
                return False
            ids.add(recipe["id"])
        except (ValueError, TypeError, KeyError, RecursionError):
            return False
    return True


def _adapter_gate(recipe, operation):
    if recipe["update_mechanism"] == "native_updater":
        if operation == "install":
            return "adapter_requires_manual_review"
        if recipe["adapter_id"] not in NATIVE_DRIVERS:
            return "native_driver_unaccepted"
    elif (recipe["update_mechanism"] != "direct_artifact"
          or recipe["adapter_id"] not in DIRECT_ADAPTERS):
        return "adapter_requires_manual_review"
    elif recipe["candidate"]["artifact_type"] != "zip":
        return "artifact_format_requires_review"
    if operation == "lifecycle":
        return "lifecycle_not_standalone"
    return None


def assess_catalog_readiness(catalog, environment):
    """Report existing predicates for each operation, without preparing execution.

``environment`` has the same shape as ``validate_recipe_evidence``. Unknown
observations stay unknown; this API never invents candidate/consent bindings.
``runtime_prepare_allowed`` describes the pure preparation predicate only.
Even when it is true, this report grants no authority and contains no action.
"""
    valid = _catalog_valid(catalog)
    result = dict(catalog_valid=valid, activation_allowed=False, read_only=True,
                  reasons=[] if valid else ["catalog_invalid"],
                  missing_recipe_ids=[], missing_recipes=[], recipes=[])
    if not valid:
        return result
    represented = {item for recipe in catalog["recipes"] for item in recipe["matrix_ids"]}
    result["missing_recipe_ids"] = sorted(set(catalog["metadata"]["matrix_ids"]) - represented)
    result["missing_recipes"] = [dict(matrix_id=matrix_id, operations={
        operation: dict(evidence_allowed=False, adapter_available=False,
                        runtime_prepare_allowed=False, reasons=["recipe_missing"], evidence_ids=[])
        for operation in OPERATIONS}) for matrix_id in result["missing_recipe_ids"]]
    environment_valid = type(environment) is dict and _bounded_json(environment, 1024 * 1024)
    for recipe in catalog["recipes"]:
        row = dict(recipe_id=recipe["id"], revision=recipe["revision"],
                   matrix_ids=recipe["matrix_ids"][:], operations={})
        for operation in OPERATIONS:
            checked = (validate_recipe_evidence(recipe, operation, environment) if environment_valid
                       else dict(allowed=False, reasons=["environment_invalid"], evidence_ids=[]))
            reasons = checked["reasons"][:]
            gate = _adapter_gate(recipe, operation)
            if gate:
                reasons.append(gate)
            prepared = False
            if checked["allowed"] and not gate:
                action = prepare_recipe_action(recipe, environment.get("target", {}), operation, environment)
                prepared = action["allowed"]
                if not prepared:
                    reasons.extend(action.get("reasons", []))
                    reasons.append(action["reason_code"])
            row["operations"][operation] = dict(
                evidence_allowed=checked["allowed"], adapter_available=gate is None,
                runtime_prepare_allowed=prepared, reasons=sorted(set(reasons)),
                evidence_ids=checked["evidence_ids"][:])
        result["recipes"].append(row)
    return result


def _timing_key(event):
    if type(event) is not dict:
        raise ValueError("invalid_phase_event")
    fields = ("recipe_id", "recipe_revision", "phase", "comparison_id", "operation",
              "evidence_kind", "evidence_type", "outcome")
    if (any(not _token(event.get(key)) for key in fields + ("run_id", "action_id"))
            or event["recipe_revision"] in ("unknown", "none")
            or not _SHA256.fullmatch(event["comparison_id"])
            or event["operation"] not in OPERATIONS
            or event["evidence_kind"] not in ("fixture", "live", "user_feedback", "unknown")
            or type(event.get("elapsed_ms")) is not int
            or not 0 <= event["elapsed_ms"] <= 2**63 - 1):
        raise ValueError("invalid_phase_comparison")
    for field in ("start", "end"):
        value = event.get(field)
        if type(value) is not str or len(value) > 64:
            raise ValueError("invalid_phase_time")
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("invalid_phase_time")
    return tuple(event[field] for field in fields)


def summarize_phase_timings(receipts):
    """Nearest-rank p50/p95 after five distinct runs in a comparable group.

``comparison_id`` is a caller-supplied SHA256 binding the exact N/N+1 payloads,
OS/arch, machine class, budgets, mode and controlled conditions. Its integrity
is not established by this function. Declared live labels remain unverified.
Duplicate measurements count once. Conflicting samples exclude that run.
"""
    if type(receipts) is not list or len(receipts) > 20000:
        raise ValueError("invalid_receipt_collection")
    result = dict(groups=[], rejected_events=0, duplicate_events=0, conflicting_runs=0,
                  verified_live_evidence=False)
    groups = {}
    for event in receipts:
        try:
            key = _timing_key(event)
        except (ValueError, TypeError, OverflowError):
            result["rejected_events"] += 1
            continue
        samples = groups.setdefault(key, {})
        run = event["run_id"]
        sample = (event["action_id"], event["start"], event["end"], event["elapsed_ms"])
        if run not in samples:
            samples[run] = sample
        elif samples[run] == sample:
            result["duplicate_events"] += 1
        elif samples[run] is not None:
            samples[run] = None
            result["conflicting_runs"] += 1
    for key, samples in sorted(groups.items()):
        values = sorted(sample[3] for sample in samples.values() if sample is not None)
        count = len(values)
        recipe_id, revision, phase, comparison, operation, kind, evidence_type, outcome = key
        result["groups"].append(dict(
            recipe_id=recipe_id, recipe_revision=revision, phase=phase, comparison_id=comparison,
            operation=operation, declared_evidence_kind=kind, evidence_type=evidence_type,
            outcome=outcome, independent_runs=count,
            p50_ms=values[math.ceil(count * .5) - 1] if count >= 5 else None,
            p95_ms=values[math.ceil(count * .95) - 1] if count >= 5 else None,
            reasons=[] if count >= 5 else ["insufficient_independent_runs"]))
    return result


def validate_feedback_report(report):
    """Validate minimal report context without returning or trusting its prose.

The user's redaction declaration is not a secret scanner. Store/share the
original only after human review. Valid feedback cannot serve as acceptance.
"""
    result = dict(valid=False, trusted=False, verified=False, acceptance_eligible=False,
                  classification="unverified_user_feedback", context_complete=False,
                  reasons=[], warnings=[])
    required = {"schema_version", "toolkit_version", "commit", "command", "flags", "os_version",
                "architecture", "locale", "terminal", "exact_error", "redacted"}
    if type(report) is not dict or not _bounded_json(report, 65536):
        result["reasons"] = ["invalid_feedback_report"]
        return result
    result["reasons"].extend("missing_" + key for key in sorted(required - set(report)))
    if set(report) - required:
        result["reasons"].append("unknown_feedback_fields")
    if result["reasons"]:
        return result
    checks = {
        "schema_version": type(report["schema_version"]) is int and report["schema_version"] == 1,
        "toolkit_version": type(report["toolkit_version"]) is str and bool(re.fullmatch(
            r"[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}(?:[-+][A-Za-z0-9.-]{1,64})?", report["toolkit_version"])),
        "commit": type(report["commit"]) is str and bool(re.fullmatch(r"(?:[a-f0-9]{40,64}|unknown)", report["commit"])),
        "command": type(report["command"]) is str and bool(re.fullmatch(
            r"(?:bash )?[a-z][a-z0-9_]{0,63}\.sh", report["command"])),
        "flags": type(report["flags"]) is list and len(report["flags"]) <= 64
                 and all(_token(value) for value in report["flags"]),
        "os_version": type(report["os_version"]) is str and bool(re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,3}){0,2}", report["os_version"])),
        "architecture": type(report["architecture"]) is str and report["architecture"] in ("arm64", "x86_64", "unknown"),
        "locale": type(report["locale"]) is str and bool(re.fullmatch(r"[A-Za-z0-9_.@-]{1,64}", report["locale"])),
        "terminal": type(report["terminal"]) is dict and set(report["terminal"]) == {"is_tty", "name"}
                    and type(report["terminal"].get("is_tty")) is bool and _token(report["terminal"].get("name")),
        "exact_error": type(report["exact_error"]) is str and 0 < len(report["exact_error"]) <= 8192,
        "redacted": report["redacted"] is True,
    }
    result["reasons"] = ["invalid_" + key for key, valid in checks.items() if not valid]
    result["valid"] = not result["reasons"]
    for key in ("commit", "architecture"):
        if report[key] == "unknown":
            result["warnings"].append("unknown_" + key)
    result["context_complete"] = result["valid"] and not result["warnings"]
    return result
