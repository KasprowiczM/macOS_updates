"""Closed recipe dispatch. Catalog data never becomes shell or Python code."""

import copy
import shutil
from artifact_acquisition import acquire_candidate
from recipe_acceptance import (
    validate_recipe_evidence,
    recipe_fingerprint,
    candidate_binding,
)
from user_policy import digest
from vendor_feeds import version_compare
from update_transaction import execute_transaction, TransactionDeferred
from operation_receipts import phase_receipt

# These names select reviewed implementations, not arbitrary import paths.
DIRECT_ADAPTERS = frozenset(("github_dmg", "mozilla_dmg"))


def prepare_recipe_action(recipe, target, operation, environment=None):
    result = dict(
        allowed=False,
        reason_code="recipe_not_accepted",
        reasons=[],
        operation=operation,
        verified=False,
    )
    env = copy.deepcopy(environment or {})
    env["target"] = copy.deepcopy(target)
    checked = validate_recipe_evidence(recipe, operation, env)
    if not checked["allowed"]:
        result["reasons"] = checked["reasons"]
        return result
    from native_update_session import NATIVE_DRIVERS

    native = (
        recipe["update_mechanism"] == "native_updater"
        and recipe["adapter_id"] in NATIVE_DRIVERS
    )
    if not native and (
        recipe["adapter_id"] not in DIRECT_ADAPTERS
        or recipe["update_mechanism"] != "direct_artifact"
    ):
        result["reason_code"] = "adapter_requires_manual_review"
        return result
    if not native and recipe["candidate"]["artifact_type"] != "zip":
        result["reason_code"] = "artifact_format_requires_review"
        return result
    if operation == "update":
        if target.get("presence") != "present" or target.get("freshness") != "fresh":
            result["reason_code"] = "removed_or_incomplete_target"
            return result
        if not native and target.get("running") is not False:
            result["reason_code"] = "running_or_unknown"
            return result
        before = target.get("version") or target.get("short_version")
        if version_compare(recipe["candidate"]["version"], before) not in (
            (0, 1) if native else (1,)
        ):
            # A same-version rebuild needs a product-specific ordering contract.
            result["reason_code"] = "downgrade_or_build_order_unknown"
            return result
    elif operation == "install":
        if native:
            result["reason_code"] = "adapter_requires_manual_review"
            return result
        if target.get("presence") != "absent":
            result["reason_code"] = "target_already_present"
            return result
    else:
        result["reason_code"] = "adapter_requires_manual_review"
        return result
    if native:
        lifecycle = validate_recipe_evidence(recipe, "lifecycle", env)
        if not lifecycle["allowed"]:
            result["reasons"] = lifecycle["reasons"]
            return result
    result.update(
        allowed=True,
        reason_code="allowed",
        recipe=copy.deepcopy(recipe),
        candidate=copy.deepcopy(recipe["candidate"]),
        download_hosts=recipe["download_hosts"][:],
        limits=copy.deepcopy(recipe["limits"]),
        adapter_id=recipe["adapter_id"],
        recipe_revision=recipe["revision"],
        recipe_sha256=recipe_fingerprint(recipe),
        candidate_sha256=candidate_binding(recipe["candidate"]),
        requirements_sha256=digest(recipe["requirement_graph"]),
        evidence_ids=checked["evidence_ids"],
        target=copy.deepcopy(target),
        target_path=target.get("real_path") or target.get("destination"),
    )
    return result


def execute_recipe_action(action, observer, journal):
    """Execute an accepted direct update under caller-held locks and fresh guard.

    observer supplies current(), authorize(), observe_bundle() and transaction_action.
    Installation goes through InstallPlan's separate exclusive install executor.
    The observer is code owned by the caller, never loaded from recipe data.
    """
    result = dict(
        verified=False,
        status="deferred_by_user",
        reason_code="recipe_not_accepted",
        mutation_started=False,
    )
    staged = None
    progress = {}
    try:
        if (
            action.get("allowed") is True
            and action.get("recipe", {}).get("update_mechanism") == "native_updater"
        ):
            from native_update_session import run_native_session

            if (
                recipe_fingerprint(action["recipe"]) != action["recipe_sha256"]
                or candidate_binding(action["candidate"]) != action["candidate_sha256"]
                or action["candidate"] != action["recipe"]["candidate"]
                or action.get("operation") != "update"
                or observer.authorize() is not True
            ):
                return result
            native_action = dict(
                observer.transaction_action,
                candidate=action["candidate"],
                recipe_revision=str(action["recipe_revision"]),
            )
            result["mutation_started"] = True
            native_result = run_native_session(
                native_action,
                action["adapter_id"],
                authorize=observer.native_authorize,
                state_dir=observer.state_dir,
                receipt_dir=observer.receipt_dir,
                lease=observer.lease,
            )
            return dict(native_result, lease_managed=True)
        if (
            action.get("allowed") is not True
            or action.get("operation") != "update"
            or action.get("adapter_id") not in DIRECT_ADAPTERS
            or recipe_fingerprint(action["recipe"]) != action["recipe_sha256"]
            or candidate_binding(action["candidate"]) != action["candidate_sha256"]
            or action["candidate"] != action["recipe"]["candidate"]
        ):
            return result
        if observer.authorize() is not True:
            result["reason_code"] = "authorization_deferred"
            return result
        phase_args = dict(
            run_id=observer.transaction_action.get("plan_id", "unknown"),
            action_id=observer.transaction_action.get("action_id", "unknown"),
            recipe_revision=str(action["recipe_revision"]),
        )
        receipt_dir = getattr(observer, "receipt_dir", None) or journal
        with phase_receipt(receipt_dir, phase="acquisition", **phase_args) as event:
            staged = acquire_candidate(
                action, journal, observer=observer.observe_bundle
            )
            event.update(
                outcome="candidate_verified", evidence_type="signature_verification"
            )
        if observer.authorize() is not True:
            result["reason_code"] = "authorization_deferred"
            return result
        transaction_action = copy.deepcopy(observer.transaction_action)
        if (
            transaction_action.get("target_path") != action["target_path"]
            or transaction_action.get("action_scope") != "direct_update"
        ):
            result["reason_code"] = "scope_mismatch"
            return result
        transaction_action["recipe_candidate"] = copy.deepcopy(action["candidate"])
        with phase_receipt(receipt_dir, phase="replacement", **phase_args) as event:
            receipt = execute_transaction(
                transaction_action,
                staged["bundle_path"],
                journal,
                observer.current,
                observer.authorize,
                observer.observe_bundle,
                allowed_roots=getattr(observer, "allowed_roots", None),
                progress=progress,
            )
            event.update(
                outcome="replacement_verified",
                evidence_type="installed_version_observation",
            )
        actual = observer.observe_bundle(action["target_path"])
        candidate = action["candidate"]
        if (
            actual.get("good") is not True
            or actual.get("receipt_present") is not False
            or any(
                actual.get(k) != candidate.get(k)
                for k in ("version", "build", "bundle_id", "team_id")
            )
        ):
            return dict(
                verified=False,
                status="recovery_required",
                reason_code="update_unverified",
                mutation_started=True,
                recovery_required=True,
                journal_path=receipt.get("journal_path"),
            )
        return dict(
            verified=True,
            status="updated_verified",
            reason_code="updated_verified",
            after=actual["version"],
            after_build=actual["build"],
            evidence_type="installed_version_observation",
            evidence_freshness="fresh",
            mutation_started=True,
            journal_path=receipt.get("journal_path"),
        )
    except (OSError, ValueError, KeyError, TypeError, TransactionDeferred) as error:
        # Do not expose paths, remote URLs or arbitrary exception messages.
        result["reason_code"] = "recipe_execution_deferred"
        result["error_type"] = type(error).__name__
        result["mutation_started"] = bool(
            result["mutation_started"]
            or progress.get("target_mutation_started")
            or progress.get("copy_started")
            and not progress.get("copy_completed")
        )
        if result["mutation_started"]:
            result.update(status="recovery_required", recovery_required=True)
        return result
    finally:
        if staged:
            shutil.rmtree(staged["staging_path"])
