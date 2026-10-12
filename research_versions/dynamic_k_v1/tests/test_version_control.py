"""Isolated N0 controls; no production imports, workloads, or scientific runs."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOL = Path(__file__).resolve().parents[1] / "tools/version_control.py"
spec = importlib.util.spec_from_file_location("dynamic_k_n0_version_control", TOOL)
vc = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = vc
spec.loader.exec_module(vc)


def write_json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(document, sort_keys=True, indent=2) + "\n").encode("utf-8"))


class N0IntegrityControls(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).parent / ".scratch"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, data in {
            "src/engine.py": b"original\r\n",
            "tests/test_old.py": b"historical expectation\n",
            "docs/GATE.md": b"frozen contract\n",
            "configs/current.json": b"{}\n",
            "outputs/history.json": b"{\"failed\":true}\n",
            "tmp/evidence.log": b"evidence\n",
            "data/orbit.bin": b"\x00\xff\x80",
            ".idea/session.xml": b"volatile",
            "src/__pycache__/ignored.pyc": b"volatile",
        }.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        legacy, excluded = vc.inventory(self.root)
        self.legacy = legacy
        self.assertEqual(len(excluded), 2)
        self.ns = self.root / vc.NAMESPACE
        self.baseline_relative = vc.NAMESPACE + "/baselines/test_baseline"
        baseline = self.root / self.baseline_relative
        manifest = {"schema": "dynamic_k_legacy_file_baseline_v1", "baseline_id": "test_baseline",
                    "files": legacy, "file_count": len(legacy),
                    "total_bytes": sum(r["byte_count"] for r in legacy.values())}
        metadata = {"schema": "dynamic_k_legacy_baseline_record_v1", "baseline_id": "test_baseline",
                    "status": "TWO_PASS_CAPTURE_VERIFIED", "exclusion_policy": vc.POLICY,
                    "verification": {"independent_full_hash_passes": 2},
                    "protection_policy": {"explicitly_recorded_legacy_implementation_change_roots": list(vc.LEGACY_CHANGE_ROOTS),
                        "immutable_legacy_by_default": True,
                        "historical_tests_contracts_manifests_results_not_rewritten": True}}
        for name, doc in {
            "files.json": manifest,
            "exclusions.json": {"schema": "dynamic_k_baseline_exclusions_v1", "policy": vc.POLICY,
                                "excluded_files": excluded},
            "record.json": metadata,
        }.items():
            write_json(baseline / name, doc)
        seal = {"schema": "dynamic_k_baseline_seal_v1", "baseline_id": "test_baseline",
                "status": "SEALED", "files": {n: vc.file_info(baseline / n)
                            for n in ("files.json", "exclusions.json", "record.json")}}
        write_json(baseline / "seal.json", seal)
        self.seal = vc.binding(self.root, self.baseline_relative + "/seal.json")
        self.contract_path = vc.NAMESPACE + "/contracts/draft.md"
        self.config_path = vc.NAMESPACE + "/configs/draft.json"
        (self.root / self.contract_path).parent.mkdir(parents=True)
        (self.root / self.contract_path).write_bytes(b"DRAFT\n")
        write_json(self.root / self.config_path, {"status": "DRAFT_NOT_FROZEN"})
        actual, _ = vc.inventory(self.root)
        initial = self.record("0001", None, vc.differences(legacy, actual))
        path = vc.NAMESPACE + "/revisions/0001/record.json"
        write_json(self.root / path, initial)
        self.revision = vc.binding(self.root, path)
        version = {"schema": "dynamic_k_version_record_v1", "version_id": vc.VERSION_ID,
                   "baseline_seal": self.seal, "initial_revision": self.revision,
                   "genesis_contract": initial["bindings"]["contract"],
                   "genesis_configuration": initial["bindings"]["configuration"]}
        write_json(self.ns / "version_record.json", version)
        self.version_sha = vc.file_info(self.ns / "version_record.json")["sha256"]

    def record(self, number, parent, diff):
        return {"schema": "dynamic_k_revision_record_v1", "version_id": vc.VERSION_ID,
                "revision_id": number, "parent_record": parent,
                "reason": "TEST_FIXTURE_ONLY_NOT_A_PRODUCTION_AUTHORIZATION",
                "authorization": {"actor": "human_user", "request": "isolated test fixture"},
                "bindings": {"baseline_seal": self.seal,
                    "contract": vc.binding(self.root, self.contract_path),
                    "configuration": vc.binding(self.root, self.config_path)},
                "changes": {"added": diff["added"], "modified": diff["modified"],
                            "deleted": [{"path": r["path"], "before": {k: r[k] for k in ("byte_count", "sha256")}}
                                        for r in diff["deleted"]]}}

    def check(self):
        return vc.verify_project(self.root, self.version_sha, self.revision["sha256"])

    def prior_expected(self):
        return vc.load_expected(self.root, self.version_sha, self.revision["sha256"])[2]

    def append_fixture_revision(self, before):
        actual, _ = vc.inventory(self.root)
        actual.pop(vc.NAMESPACE + "/version_record.json")
        for path in list(actual):
            if "/revisions/" in path and path.endswith("/record.json"):
                actual.pop(path)
        number = f"{int(self.revision['path'].split('/')[-2]) + 1:04d}"
        record = self.record(number, self.revision, vc.differences(before, actual))
        path = vc.NAMESPACE + f"/revisions/{number}/record.json"
        write_json(self.root / path, record)
        self.revision = vc.binding(self.root, path)
        return record

    def test_unchanged_complete_inventory_passes_and_keeps_ignored_evidence(self):
        self.assertIn("outputs/history.json", self.legacy)
        self.assertIn("tmp/evidence.log", self.legacy)
        self.assertEqual(self.check()["status"], "PASS")
        self.assertEqual(self.check()["excluded_file_count"], 2)

    def test_raw_byte_line_ending_change_detected(self):
        (self.root / "src/engine.py").write_bytes(b"original\n")
        with self.assertRaisesRegex(vc.IntegrityError, "UNREGISTERED_FILE_DRIFT") as error:
            self.check()
        self.assertEqual(error.exception.details["modified"][0]["path"], "src/engine.py")

    def test_deletion_detected(self):
        (self.root / "outputs/history.json").unlink()
        with self.assertRaises(vc.IntegrityError) as error:
            self.check()
        self.assertEqual(error.exception.details["deleted"][0]["path"], "outputs/history.json")

    def test_rename_reported_without_assuming_identity(self):
        (self.root / "src/engine.py").rename(self.root / "src/renamed.py")
        with self.assertRaises(vc.IntegrityError) as error:
            self.check()
        self.assertEqual(len(error.exception.details["possible_renames"]), 1)

    def test_new_legacy_file_detected(self):
        (self.root / "src/unregistered.py").write_bytes(b"extra")
        with self.assertRaisesRegex(vc.IntegrityError, "UNREGISTERED_FILE_DRIFT"):
            self.check()

    def test_new_namespace_file_detected(self):
        (self.ns / "unregistered.json").write_bytes(b"{}")
        with self.assertRaisesRegex(vc.IntegrityError, "UNREGISTERED_FILE_DRIFT"):
            self.check()

    def test_manifest_tamper_rejected(self):
        path = self.root / self.baseline_relative / "files.json"
        data = vc.read_json(path)
        data["files"].pop("src/engine.py")
        write_json(path, data)
        with self.assertRaisesRegex(vc.IntegrityError, "BOUND_FILE_HASH_MISMATCH"):
            self.check()

    def test_seal_tamper_rejected(self):
        path = self.root / self.baseline_relative / "seal.json"
        data = vc.read_json(path)
        data["files"]["files.json"]["sha256"] = "0" * 64
        write_json(path, data)
        with self.assertRaisesRegex(vc.IntegrityError, "BOUND_FILE_HASH_MISMATCH"):
            self.check()

    def test_coordinated_reseal_cannot_replace_external_version_anchor(self):
        path = self.ns / "version_record.json"
        data = vc.read_json(path)
        data["baseline_seal"]["sha256"] = "0" * 64
        write_json(path, data)
        with self.assertRaisesRegex(vc.IntegrityError, "EXTERNAL_VERSION_ANCHOR_MISMATCH"):
            self.check()

    def test_registered_source_change_and_parent_chain_pass(self):
        before = self.prior_expected()
        (self.root / "src/engine.py").write_bytes(b"authorized fixture change\n")
        self.append_fixture_revision(before)
        self.assertEqual(self.check()["revision_id"], "0002")

    def test_historical_test_change_rejected_even_if_registered(self):
        before = self.prior_expected()
        (self.root / "tests/test_old.py").write_bytes(b"rewritten expectation")
        self.append_fixture_revision(before)
        with self.assertRaisesRegex(vc.IntegrityError, "PROTECTED_LEGACY_PATH_CHANGE"):
            self.check()

    def test_revision_parent_tamper_rejected(self):
        before = self.prior_expected()
        (self.ns / "new.txt").write_bytes(b"new")
        self.append_fixture_revision(before)
        path = self.root / self.revision["path"]
        record = vc.read_json(path)
        record["parent_record"]["sha256"] = "0" * 64
        write_json(path, record)
        self.revision = vc.binding(self.root, self.revision["path"])
        with self.assertRaisesRegex(vc.IntegrityError, "REVISION_PARENT_MISMATCH"):
            self.check()

    def test_revision_tail_deletion_detected_by_external_latest_anchor(self):
        before = self.prior_expected()
        self.append_fixture_revision(before)
        (self.root / self.revision["path"]).unlink()
        (self.root / self.revision["path"]).parent.rmdir()
        with self.assertRaisesRegex(vc.IntegrityError, "EXTERNAL_REVISION_ANCHOR_MISMATCH"):
            self.check()

    def test_declared_before_hash_cannot_be_forged(self):
        before = self.prior_expected()
        (self.root / "src/engine.py").write_bytes(b"changed")
        self.append_fixture_revision(before)
        path = self.root / self.revision["path"]
        record = vc.read_json(path)
        record["changes"]["modified"][0]["before"]["sha256"] = "0" * 64
        write_json(path, record)
        self.revision = vc.binding(self.root, self.revision["path"])
        with self.assertRaisesRegex(vc.IntegrityError, "REVISION_BEFORE_HASH_MISMATCH"):
            self.check()

    def test_path_escape_and_windows_absolute_paths_rejected(self):
        for path in ("../outside", "D:/outside", "/outside", "src\\engine.py", "src/./engine.py"):
            with self.subTest(path=path), self.assertRaises(vc.IntegrityError):
                vc.safe_path(self.root, path)

    def test_duplicate_json_key_rejected(self):
        path = self.ns / "duplicate.json"
        path.write_bytes(b'{"files":{},"files":{}}')
        with self.assertRaisesRegex(vc.IntegrityError, "DUPLICATE_JSON_KEY"):
            vc.read_json(path)

    def test_file_set_change_during_scan_rejected(self):
        original = vc.file_info
        made = []
        def changed(path):
            info = original(path)
            if not made:
                (self.root / "appeared.txt").write_bytes(b"during scan")
                made.append(True)
            return info
        with patch.object(vc, "file_info", changed):
            with self.assertRaisesRegex(vc.IntegrityError, "FILE_SET_CHANGED_DURING_CHECK"):
                vc.inventory(self.root)

    def test_read_failure_is_not_partial_success(self):
        with patch.object(vc, "file_info", side_effect=PermissionError("unreadable fixture")):
            with self.assertRaises(PermissionError):
                vc.inventory(self.root)

    def test_version_anchor_changed_between_history_load_and_scan_rejected(self):
        original = vc.inventory
        def changed(root, **kwargs):
            path = self.ns / "version_record.json"
            document = vc.read_json(path)
            document["unexpected_mutation"] = True
            write_json(path, document)
            return original(root, **kwargs)
        with patch.object(vc, "inventory", changed):
            with self.assertRaisesRegex(vc.IntegrityError, "EXTERNAL_VERSION_ANCHOR_MISMATCH"):
                self.check()

    def test_revision_changed_after_scan_rejected(self):
        original = vc.inventory
        def changed(root, **kwargs):
            result = original(root, **kwargs)
            path = self.root / self.revision["path"]
            document = vc.read_json(path)
            document["unexpected_mutation"] = True
            write_json(path, document)
            return result
        with patch.object(vc, "inventory", changed):
            with self.assertRaisesRegex(vc.IntegrityError, "GENESIS_REVISION_MISMATCH"):
                self.check()

    def test_empty_experiment_template_rejected(self):
        path = vc.NAMESPACE + "/experiments/template.json"
        write_json(self.root / path, {"schema": "dynamic_k_experiment_record_v1",
                    "version_id": vc.VERSION_ID, "run_id": None})
        with self.assertRaisesRegex(vc.IntegrityError, "EXPERIMENT_RECORD_INCOMPLETE"):
            vc.validate_experiment(self.root, path, vc.binding(self.root, path)["sha256"],
                                   self.version_sha, self.revision["sha256"])

    def test_draft_configuration_cannot_approve_experiment(self):
        path = vc.NAMESPACE + "/experiments/fixture.json"
        latest = vc.read_json(self.root / self.revision["path"])
        record = {"schema": "dynamic_k_experiment_record_v1", "version_id": vc.VERSION_ID,
                  "run_id": "TEST_ONLY", "revision_id": "0001", "revision_record": self.revision,
                  "baseline_seal": self.seal, "contract": latest["bindings"]["contract"],
                  "configuration": latest["bindings"]["configuration"]}
        write_json(self.root / path, record)
        with self.assertRaisesRegex(vc.IntegrityError, "DRAFT_OR_UNAUTHORIZED_EXPERIMENT_REJECTED"):
            vc.validate_experiment(self.root, path, vc.binding(self.root, path)["sha256"],
                                   self.version_sha, self.revision["sha256"])


if __name__ == "__main__":
    unittest.main()
