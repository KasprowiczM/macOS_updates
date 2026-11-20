"""Validation for private, source-aware inventory snapshots."""

import uuid
import datetime
import os


def _timestamp(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.utcoffset() == datetime.timedelta(0)
    except ValueError:
        return False


def _optional_string(value):
    return value is None or isinstance(value, str)


def validate_snapshot(value):
    if not isinstance(value, dict) or (
        type(value.get("schema_version")) is not int or value.get("schema_version") != 1
    ):
        raise ValueError("invalid snapshot schema")
    for key in ("snapshot_id", "profile_id"):
        try:
            uuid.UUID(value[key])
        except (KeyError, TypeError, ValueError, AttributeError):
            raise ValueError("invalid " + key)
    if (
        not isinstance(value.get("generation"), int)
        or isinstance(value["generation"], bool)
        or value["generation"] < 0
    ):
        raise ValueError("invalid generation")
    if not _timestamp(value.get("created_at")) or not isinstance(
        value.get("sources"), dict
    ):
        raise ValueError("invalid snapshot metadata")
    if value.get("previous_snapshot_id") is not None:
        try:
            uuid.UUID(value["previous_snapshot_id"])
        except (TypeError, ValueError, AttributeError):
            raise ValueError("invalid previous snapshot")
    if not value["created_at"] or not isinstance(
        value.get("previous_snapshot_id"), (str, type(None))
    ):
        raise ValueError("invalid snapshot metadata")
    ids = set()
    for source in value["sources"].values():
        if (
            not isinstance(source, dict)
            or (
                type(source.get("schema_version")) is not int
                or source.get("schema_version") != 1
            )
            or source.get("status") not in ("ok", "unavailable", "error", "partial")
            or not isinstance(source.get("items"), list)
            or not isinstance(source.get("covered_roots"), list)
            or not isinstance(source.get("complete"), bool)
            or not _timestamp(source.get("observed_at"))
            or any(not isinstance(x, str) for x in source["covered_roots"])
            or not all(isinstance(x, dict) for x in source["items"])
            or not isinstance(source.get("reason_code"), (str, type(None)))
            or (source["status"] != "ok" and source["complete"])
        ):
            raise ValueError("invalid source")
    for group, key in (("instances", "instance_id"), ("packages", "package_id")):
        if not isinstance(value.get(group), list):
            raise ValueError("invalid " + group)
        for record in value[group]:
            if not isinstance(record, dict):
                raise ValueError("invalid record")
            try:
                uuid.UUID(record[key])
            except (KeyError, TypeError, ValueError, AttributeError):
                raise ValueError("invalid record id")
            if record[key] in ids:
                raise ValueError("duplicate record id")
            ids.add(record[key])
            if not all(
                isinstance(e.get("kind"), str) and e["kind"]
                for e in record.get("evidence", [])
                if isinstance(e, dict)
            ):
                raise ValueError("invalid evidence")
            if (
                record.get("presence") not in ("present", "absent", "unobserved")
                or record.get("freshness") not in ("fresh", "stale")
                or not isinstance(record.get("evidence"), list)
                or any(
                    not isinstance(e, dict) or not isinstance(e.get("kind"), str)
                    for e in record["evidence"]
                )
            ):
                raise ValueError("invalid record state")
            if not _timestamp(record.get("observed_at")) or record.get(
                "channel"
            ) not in ("stable", "beta", "testflight", "unknown"):
                raise ValueError("invalid record metadata")
            for e in record["evidence"]:
                if "source_complete" in e and type(e["source_complete"]) is not bool:
                    raise ValueError("invalid source completeness")
                for k, v in e.items():
                    if (
                        k
                        in (
                            "kind",
                            "path",
                            "artifact_path",
                            "prefix",
                            "token",
                            "bundle_id",
                            "team_id",
                            "store_id",
                            "source_key",
                            "source_status",
                            "manifest_path",
                            "name",
                            "installed_receipt",
                        )
                        and not _optional_string(v)
                        and not (k == "store_id" and type(v) is int)
                    ):
                        raise ValueError("invalid evidence field")
            if group == "instances" and (
                not isinstance(record.get("path"), str)
                or not isinstance(record.get("real_path"), str)
                or record.get("scope") not in ("user", "system", "optional_root")
                or not all(
                    k in record
                    for k in (
                        "bundle_id",
                        "team_id",
                        "name",
                        "short_version",
                        "build_version",
                        "architectures",
                        "minimum_os",
                        "parent_instance_id",
                    )
                )
            ):
                raise ValueError("invalid instance")
            if group == "instances" and (
                not os.path.isabs(record["path"])
                or not os.path.isabs(record["real_path"])
                or any(
                    not _optional_string(record[k])
                    for k in (
                        "bundle_id",
                        "team_id",
                        "name",
                        "short_version",
                        "build_version",
                        "minimum_os",
                        "parent_instance_id",
                    )
                )
                or not (
                    record["architectures"] is None
                    or isinstance(record["architectures"], list)
                    and all(isinstance(x, str) for x in record["architectures"])
                )
            ):
                raise ValueError("invalid instance fields")
            if group == "packages" and (
                not isinstance(record.get("manager"), str)
                or not isinstance(record.get("prefix"), str)
                or not all(
                    k in record
                    for k in (
                        "version",
                        "installed_receipt",
                        "explicitly_installed",
                        "related_instance_ids",
                        "source_identity",
                    )
                )
                or not isinstance(record.get("related_instance_ids"), list)
            ):
                raise ValueError("invalid package")
            if group == "packages" and (
                not os.path.isabs(record["prefix"])
                or any(
                    not _optional_string(record[k])
                    for k in ("version", "installed_receipt", "source_identity")
                )
                or (
                    record["explicitly_installed"] is not None
                    and type(record["explicitly_installed"]) is not bool
                )
                or any(not isinstance(x, str) for x in record["related_instance_ids"])
            ):
                raise ValueError("invalid package fields")
    return value
