"""N0 integrity/version bindings only. Never imports or runs the simulator.

Trust starts at independently retained version AND revision SHA-256 values.
Hash integrity cannot authenticate the human authorization text or prove a Gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import time
from pathlib import Path, PurePosixPath

VERSION_ID = "dynamic_k_v1"
NAMESPACE = "research_versions/dynamic_k_v1"
DIRECTORY_EXCLUSIONS = {
    ".idea": "IDE_METADATA", "__pycache__": "BYTECODE_CACHE",
    ".pytest_cache": "TEST_CACHE", ".mypy_cache": "TYPECHECK_CACHE",
    ".ruff_cache": "LINT_CACHE", ".cache": "CACHE",
    ".hypothesis": "TEST_CACHE", ".venv": "VIRTUAL_ENVIRONMENT",
    "venv": "VIRTUAL_ENVIRONMENT", ".git": "GIT_INTERNAL_METADATA",
}
POLICY = {
    "directory_names": DIRECTORY_EXCLUSIONS,
    "virtual_environment_markers": ["pyvenv.cfg", "conda-meta"],
    "bytecode_suffixes": [".pyc", ".pyo"],
    "lock_name_rules": ["starts_with:~$", "starts_with:.~lock.",
                        "ends_with:.lock", "ends_with:.lck"],
    "new_version_namespace": NAMESPACE, "gitignore_used": False,
    "tmp_research_evidence_included": True,
    "symlink_policy": "REJECT_NO_FOLLOW",
}
LEGACY_CHANGE_ROOTS = ("src/", "tools/")


class IntegrityError(ValueError):
    def __init__(self, reason, details=None):
        super().__init__(reason)
        self.details = details


def require(condition, reason, details=None):
    if not condition:
        raise IntegrityError(reason, details)


def validate_digest(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value),
            "INVALID_SHA256")
    return value


def safe_path(root, relative):
    require(isinstance(relative, str) and relative and "\\" not in relative,
            "NONCANONICAL_RELATIVE_PATH")
    rel = PurePosixPath(relative)
    require(not rel.is_absolute() and str(rel) == relative
            and all(p not in (".", "..") and ":" not in p for p in rel.parts),
            "PATH_OUTSIDE_PROJECT")
    root = Path(root).resolve()
    path = root.joinpath(*rel.parts)
    current = root
    for part in rel.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            attributes = getattr(current.lstat(), "st_file_attributes", 0)
            require(not current.is_symlink() and not (
                attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)),
                "REPARSE_POINT_REJECTED", relative)
    require(path.resolve().is_relative_to(root), "PATH_OUTSIDE_PROJECT")
    return path


def file_info(path):
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) ==
            (after.st_size, after.st_mtime_ns), "FILE_CHANGED_WHILE_READING", str(path))
    return {"byte_count": after.st_size, "sha256": digest.hexdigest()}


def binding(root, relative):
    return {"path": relative, **file_info(safe_path(root, relative))}


def validate_info(info):
    require(isinstance(info, dict) and set(info) == {"byte_count", "sha256"},
            "INVALID_FILE_INFO")
    require(type(info["byte_count"]) is int and info["byte_count"] >= 0,
            "INVALID_BYTE_COUNT")
    validate_digest(info["sha256"])


def validate_binding(root, item):
    require(isinstance(item, dict) and set(item) == {"path", "byte_count", "sha256"},
            "INVALID_FILE_BINDING")
    safe_path(root, item["path"])
    validate_info({k: item[k] for k in ("byte_count", "sha256")})


def read_json(path):
    def unique_pairs(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, "DUPLICATE_JSON_KEY", key)
            out[key] = value
        return out
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)


def read_bound_json(root, item, schema):
    validate_binding(root, item)
    path = safe_path(root, item["path"])
    require(path.is_file(), "BOUND_FILE_MISSING", item["path"])
    expected = {k: item[k] for k in ("byte_count", "sha256")}
    require(file_info(path) == expected, "BOUND_FILE_HASH_MISMATCH", item["path"])
    doc = read_json(path)
    require(doc.get("schema") == schema, "SCHEMA_MISMATCH", item["path"])
    return doc


def inventory(root, *, skip_namespace=False, progress=None):
    """Read raw bytes, including ignored outputs and tmp evidence, without writes."""
    root = Path(root).resolve()
    files = {}
    excluded = []
    def walk(folder, inherited=None):
        for path in sorted(folder.iterdir(), key=lambda p: p.name):
            relative = path.relative_to(root).as_posix()
            safe_path(root, relative)
            if path.is_dir():
                if skip_namespace and relative == NAMESPACE:
                    continue
                reason = inherited or DIRECTORY_EXCLUSIONS.get(path.name)
                if reason is None and ((path / "pyvenv.cfg").is_file()
                                       or (path / "conda-meta").is_dir()):
                    reason = "VIRTUAL_ENVIRONMENT_MARKER"
                walk(path, reason)
            elif path.is_file():
                reason = inherited
                if reason is None and path.suffix.lower() in (".pyc", ".pyo"):
                    reason = "BYTECODE"
                if reason is None and (path.name.startswith(("~$", ".~lock."))
                        or path.name.lower().endswith((".lock", ".lck"))):
                    reason = "TEMPORARY_LOCK_FILE"
                if reason:
                    excluded.append({"path": relative, "reason": reason})
                else:
                    files[relative] = path
            else:
                raise IntegrityError("UNSUPPORTED_FILE_TYPE", relative)
    walk(root)
    before = {key: (p.stat().st_size, p.stat().st_mtime_ns)
              for key, p in files.items()}
    result = {}
    last_progress = time.monotonic()
    for relative, path in sorted(files.items()):
        result[relative] = file_info(path)
        if progress and time.monotonic() - last_progress > 15:
            progress({"hashed_files": len(result),
                      "hashed_bytes": sum(r["byte_count"] for r in result.values())})
            last_progress = time.monotonic()
    reenumerated = {}
    original = files
    original_excluded = list(excluded)
    files = reenumerated
    walk(root)
    require(set(original) == set(reenumerated), "FILE_SET_CHANGED_DURING_CHECK")
    for key, path in original.items():
        require(before[key] == (path.stat().st_size, path.stat().st_mtime_ns),
                "FILE_CHANGED_DURING_CHECK", key)
    return result, original_excluded


def differences(expected, actual):
    added = [{"path": p, **actual[p]} for p in sorted(actual.keys() - expected.keys())]
    deleted = [{"path": p, **expected[p]} for p in sorted(expected.keys() - actual.keys())]
    modified = [{"path": p, "before": expected[p], "after": actual[p]}
                for p in sorted(expected.keys() & actual.keys()) if expected[p] != actual[p]]
    possible_renames = [{"old_path": d["path"], "new_path": a["path"],
                        "sha256": d["sha256"], "classification": "POSSIBLE_RENAME"}
                       for d in deleted for a in added
                       if (d["sha256"], d["byte_count"]) == (a["sha256"], a["byte_count"])]
    return {"added": added, "deleted": deleted, "modified": modified,
            "possible_renames": possible_renames}


def load_expected(root, expected_version_sha256, expected_revision_sha256):
    """Validate anchors/history, then apply declared changes to the old file map."""
    root = Path(root).resolve()
    version_path = NAMESPACE + "/version_record.json"
    validate_digest(expected_version_sha256)
    validate_digest(expected_revision_sha256)
    require(file_info(safe_path(root, version_path))["sha256"] == expected_version_sha256,
            "EXTERNAL_VERSION_ANCHOR_MISMATCH")
    version = read_json(safe_path(root, version_path))
    require(version.get("schema") == "dynamic_k_version_record_v1"
            and version.get("version_id") == VERSION_ID, "VERSION_ID_MISMATCH")
    seal_ref = version["baseline_seal"]
    require(seal_ref["path"].startswith(NAMESPACE + "/baselines/")
            and seal_ref["path"].endswith("/seal.json"), "BASELINE_PATH_MISMATCH")
    seal = read_bound_json(root, seal_ref, "dynamic_k_baseline_seal_v1")
    require(seal.get("status") == "SEALED" and
            set(seal["files"]) == {"files.json", "exclusions.json", "record.json"},
            "INVALID_BASELINE_SEAL")
    base = str(PurePosixPath(seal_ref["path"]).parent)
    def baseline_doc(name, schema):
        return read_bound_json(root, {"path": base + "/" + name,
                                    **seal["files"][name]}, schema)
    manifest = baseline_doc("files.json", "dynamic_k_legacy_file_baseline_v1")
    exclusions = baseline_doc("exclusions.json", "dynamic_k_baseline_exclusions_v1")
    meta = baseline_doc("record.json", "dynamic_k_legacy_baseline_record_v1")
    require(exclusions["policy"] == POLICY and meta["exclusion_policy"] == POLICY,
            "BASELINE_EXCLUSION_POLICY_CHANGED")
    require(manifest["baseline_id"] == meta["baseline_id"] == seal["baseline_id"],
            "BASELINE_ID_MISMATCH")
    require(meta.get("status") == "TWO_PASS_CAPTURE_VERIFIED" and
            meta["verification"]["independent_full_hash_passes"] == 2,
            "BASELINE_CAPTURE_NOT_VERIFIED")
    require(meta["protection_policy"]["explicitly_recorded_legacy_implementation_change_roots"]
            == list(LEGACY_CHANGE_ROOTS), "LEGACY_PROTECTION_POLICY_CHANGED")
    require(meta["protection_policy"].get("immutable_legacy_by_default") is True and
            meta["protection_policy"].get("historical_tests_contracts_manifests_results_not_rewritten") is True,
            "LEGACY_PROTECTION_POLICY_CHANGED")
    expected = dict(manifest["files"])
    for path, info in expected.items():
        safe_path(root, path)
        validate_info(info)
        require(not path.startswith(NAMESPACE + "/"), "BASELINE_CONTAINS_NEW_VERSION")
    require(manifest["file_count"] == len(expected) and
            manifest["total_bytes"] == sum(r["byte_count"] for r in expected.values()),
            "BASELINE_MANIFEST_COUNTS_MISMATCH")
    folders = sorted(safe_path(root, NAMESPACE + "/revisions").iterdir())
    require(bool(folders), "REVISION_HISTORY_MISSING")
    records = []
    paths = []
    prior = None
    reserved = {version_path}
    for index, folder in enumerate(folders, 1):
        require(folder.is_dir() and folder.name == f"{index:04d}",
                "REVISION_SEQUENCE_GAP_OR_UNREGISTERED_ENTRY")
        path = folder.relative_to(root).as_posix() + "/record.json"
        current = binding(root, path)
        record = read_json(safe_path(root, path))
        require(record.get("schema") == "dynamic_k_revision_record_v1" and
                record.get("version_id") == VERSION_ID and
                record.get("revision_id") == f"{index:04d}", "INVALID_REVISION_RECORD")
        require(record.get("parent_record") == prior, "REVISION_PARENT_MISMATCH")
        if index == 1:
            require(current == version["initial_revision"], "GENESIS_REVISION_MISMATCH")
            require(record["bindings"]["contract"] == version["genesis_contract"] and
                    record["bindings"]["configuration"] == version["genesis_configuration"],
                    "GENESIS_SCIENCE_BINDING_MISMATCH")
        require(record["bindings"]["baseline_seal"] == seal_ref,
                "REVISION_BASELINE_BINDING_MISMATCH")
        auth = record.get("authorization", {})
        require(auth.get("actor") == "human_user" and
                isinstance(auth.get("request"), str) and auth["request"].strip(),
                "EXPLICIT_AUTHORIZATION_RECORD_REQUIRED")
        require(isinstance(record.get("reason"), str) and record["reason"].strip(),
                "REVISION_REASON_REQUIRED")
        changes = record["changes"]
        require(set(changes) == {"added", "modified", "deleted"}, "INVALID_CHANGE_LIST")
        seen = set()
        for operation in ("added", "modified", "deleted"):
            require(isinstance(changes[operation], list), "INVALID_CHANGE_LIST")
            for change in changes[operation]:
                path_changed = change["path"]
                safe_path(root, path_changed)
                require(path_changed not in seen, "DUPLICATE_CHANGE_PATH")
                seen.add(path_changed)
                require(path_changed != version_path and not re.fullmatch(
                    re.escape(NAMESPACE) + r"/revisions/[0-9]{4}/record\.json", path_changed),
                    "SELF_REFERENTIAL_OR_HISTORY_REWRITE")
                in_version = path_changed.startswith(NAMESPACE + "/")
                require(in_version or path_changed.startswith(LEGACY_CHANGE_ROOTS),
                        "PROTECTED_LEGACY_PATH_CHANGE", path_changed)
                require(not path_changed.startswith(NAMESPACE + "/baselines/")
                        or (index == 1 and operation == "added"), "BASELINE_REWRITE_REJECTED")
                if operation == "added":
                    validate_binding(root, change)
                    require(path_changed not in expected, "ADDED_PATH_ALREADY_EXISTS")
                    expected[path_changed] = {k: change[k] for k in ("byte_count", "sha256")}
                else:
                    validate_info(change["before"])
                    require(expected.get(path_changed) == change["before"],
                            "REVISION_BEFORE_HASH_MISMATCH", path_changed)
                    if operation == "modified":
                        validate_info(change["after"])
                        expected[path_changed] = change["after"]
                    else:
                        del expected[path_changed]
        for name in ("contract", "configuration"):
            item = record["bindings"][name]
            validate_binding(root, item)
            require(item["path"].startswith(NAMESPACE + "/") and
                    expected.get(item["path"]) == {k: item[k] for k in ("byte_count", "sha256")},
                    "SCIENCE_BINDING_NOT_IN_REVISION")
        prior = current
        paths.append(path)
        records.append(record)
        reserved.add(path)
    require(prior["sha256"] == expected_revision_sha256, "EXTERNAL_REVISION_ANCHOR_MISMATCH")
    return version, manifest, expected, records[-1], prior, reserved


def verify_project(root, expected_version_sha256, expected_revision_sha256, progress=None):
    version, manifest, expected, latest, head, reserved = load_expected(
        root, expected_version_sha256, expected_revision_sha256)
    actual, excluded = inventory(root, progress=progress)
    # Anchor/history files are omitted from the content manifest to avoid
    # self-reference. They must still stay pinned throughout the full scan.
    require(actual.get(NAMESPACE + "/version_record.json", {}).get("sha256")
            == expected_version_sha256, "EXTERNAL_VERSION_ANCHOR_MISMATCH")
    require(actual.get(head["path"]) == {k: head[k] for k in ("byte_count", "sha256")},
            "EXTERNAL_REVISION_ANCHOR_MISMATCH")
    rechecked = load_expected(root, expected_version_sha256, expected_revision_sha256)
    require(rechecked == (version, manifest, expected, latest, head, reserved),
            "VERSION_HISTORY_CHANGED_DURING_CHECK")
    for path in reserved:
        require(file_info(safe_path(root, path)) == actual.get(path),
                "VERSION_HISTORY_CHANGED_DURING_CHECK", path)
    for path in reserved:
        actual.pop(path, None)
    diff = differences(expected, actual)
    require(not any(diff[k] for k in ("added", "modified", "deleted")),
            "UNREGISTERED_FILE_DRIFT", diff)
    return {"status": "PASS", "scope": "N0_FILE_INTEGRITY_AND_VERSION_BINDINGS_ONLY",
            "version_id": VERSION_ID, "revision_id": latest["revision_id"],
            "version_record_sha256": expected_version_sha256,
            "revision_record_sha256": head["sha256"],
            "baseline_seal_sha256": version["baseline_seal"]["sha256"],
            "baseline_file_count": manifest["file_count"],
            "verified_file_count": len(actual), "excluded_file_count": len(excluded),
            "undeclared_changes": diff, "gate_acceptance_claimed": False,
            "scientific_experiments_executed": False}


def validate_experiment(root, record_path, expected_experiment_sha256,
                        expected_version_sha256, expected_revision_sha256):
    """Only validates a proposed/closed experiment record; does not execute it."""
    require(binding(root, record_path)["sha256"] == validate_digest(expected_experiment_sha256),
            "EXPERIMENT_EXTERNAL_ANCHOR_MISMATCH")
    record = read_json(safe_path(root, record_path))
    require(record.get("schema") == "dynamic_k_experiment_record_v1" and
            record.get("version_id") == VERSION_ID and
            isinstance(record.get("run_id"), str) and record["run_id"].strip(),
            "EXPERIMENT_RECORD_INCOMPLETE")
    version, _, _, latest, head, _ = load_expected(
        root, expected_version_sha256, expected_revision_sha256)
    require(record.get("revision_id") == latest["revision_id"] and
            record.get("revision_record") == head, "EXPERIMENT_REVISION_BINDING_MISMATCH")
    require(record.get("baseline_seal") == version["baseline_seal"] and
            record.get("contract") == latest["bindings"]["contract"] and
            record.get("configuration") == latest["bindings"]["configuration"],
            "EXPERIMENT_SCIENCE_BINDING_MISMATCH")
    configuration = read_json(safe_path(root, record["configuration"]["path"]))
    require(binding(root, record["configuration"]["path"]) == record["configuration"] and
            binding(root, record["contract"]["path"]) == record["contract"],
            "EXPERIMENT_SCIENCE_FILE_HASH_MISMATCH")
    require(configuration.get("status") == "FROZEN" and
            configuration.get("formal_experiments_authorized") is True,
            "DRAFT_OR_UNAUTHORIZED_EXPERIMENT_REJECTED")
    authorization = record.get("formal_run_authorization") or {}
    require(authorization.get("actor") == "human_user" and
            authorization.get("scope") == "FORMAL_EXPERIMENT_RUN" and
            isinstance(authorization.get("request"), str) and authorization["request"].strip(),
            "FORMAL_RUN_AUTHORIZATION_RECORD_REQUIRED")
    for parameter in ("T_A_s", "T_s", "tau_res_s", "R_min", "alpha", "D_ref_s", "E_ref_J"):
        require(configuration.get("scientific_parameters", {}).get(parameter) is not None,
                "UNRESOLVED_SCIENTIFIC_PARAMETER", parameter)
    for field in ("source_files", "input_files", "acceptance_evidence"):
        rows = record.get(field)
        require(isinstance(rows, list) and bool(rows), "EXPERIMENT_BINDING_LIST_REQUIRED", field)
        manifest_ref = configuration.get("experiment_binding_manifests", {}).get(field)
        require(manifest_ref is not None, "FROZEN_EXPERIMENT_BINDING_MANIFEST_REQUIRED", field)
        required = read_bound_json(root, manifest_ref, "dynamic_k_experiment_binding_manifest_v1")
        require(rows == required.get("files"), "EXPERIMENT_BINDING_LIST_INCOMPLETE", field)
        seen = set()
        for item in rows:
            validate_binding(root, item)
            require(item["path"] not in seen, "DUPLICATE_EXPERIMENT_BINDING")
            seen.add(item["path"])
            require(binding(root, item["path"]) == item,
                    "EXPERIMENT_FILE_HASH_MISMATCH", item["path"])
    return {"status": "PASS", "scope": "EXPERIMENT_RECORD_BINDINGS_ONLY",
            "run_id": record["run_id"], "experiment_executed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "verify-experiment"))
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--expected-version-sha256", required=True)
    parser.add_argument("--expected-revision-sha256", required=True)
    parser.add_argument("--record")
    parser.add_argument("--expected-experiment-sha256")
    args = parser.parse_args()
    try:
        progress = lambda value: print(json.dumps({"progress": value}), flush=True)
        if args.command == "verify":
            report = verify_project(args.project_root, args.expected_version_sha256,
                                    args.expected_revision_sha256, progress)
        else:
            require(args.record and args.expected_experiment_sha256,
                    "EXPERIMENT_PATH_AND_EXTERNAL_ANCHOR_REQUIRED")
            report = validate_experiment(args.project_root, args.record,
                args.expected_experiment_sha256, args.expected_version_sha256,
                args.expected_revision_sha256)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (IntegrityError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "FAIL", "reason": str(error),
                          "details": getattr(error, "details", None)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
