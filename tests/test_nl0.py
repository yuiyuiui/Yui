"""Behavioral regression tests on the actual Koch graph and corrupted copies."""
import harness_support
import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "tests/fixtures/legacy/bench_case_6"
MODULE_SPEC = importlib.util.spec_from_file_location("nl0", ROOT / "nl0/scripts/nl0.py")
nl0 = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(nl0)


class NL0Checks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="structured-nl0-")
        self.base = Path(self.temp.name)
        for folder in ["evidence", "input"]:
            shutil.copytree(CASE / folder, self.base / folder)
        shutil.copy2(CASE / "AUDIT-A.md", self.base / "AUDIT-A.md")
        self.spec = nl0.load(CASE / "spec.json")
        self.graph = nl0.load(CASE / "nl0.json")
        self.audit = nl0.load(CASE / "audit-a.json")
        from runtime_config import require_environment
        selected=require_environment()
        if self.spec['pins']['mathlib_root']!=selected['mathlib']['local_path']:
            # Relocate only this derived test copy; archived evidence stays unchanged.
            self.spec['pins']['mathlib_root']=selected['mathlib']['local_path']
            self.rebind()

    def tearDown(self):
        self.temp.cleanup()

    def write(self):
        for name, value in [("spec.json", self.spec), ("nl0.json", self.graph), ("audit-a.json", self.audit)]:
            (self.base / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

    def check(self, audit=False):
        self.write()
        return nl0.validate(self.base / "nl0.json", self.base / "spec.json",
                            self.base / "audit-a.json" if audit else None, legacy=True)

    def step(self, key):
        return next(x for x in self.graph["inferences"] if x["id"] == key)

    def rebind(self):
        self.write()
        self.graph["spec_sha256"] = nl0.sha(self.base / "spec.json")
        self.write()
        self.audit["graph_sha256"] = nl0.sha(self.base / "nl0.json")
        self.audit["spec_sha256"] = nl0.sha(self.base / "spec.json")

    def test_actual_smoke_and_audit(self):
        result = self.check(True)[0]
        self.assertFalse(result["audit_receipt_valid"])
        self.assertFalse(result["mathematics_automatically_verified"])
        self.assertEqual(result["kinds"]["hypothesis"], 2)

    def test_array_order_is_not_a_proof_dependency(self):
        self.graph["propositions"].reverse()
        self.graph["inferences"].reverse()
        self.assertEqual(self.check()[0]["status"], "LEGACY-STRUCTURE-PASSED")

    def test_packet_expands_definition_guards_and_matches_authority(self):
        data = self.check(True)
        packet = nl0.packet(data, "R015")
        self.assertEqual({p["id"] for p in packet["definition_prerequisites"]}, {"N007"})
        self.assertEqual(packet["graph_sha256"], nl0.sha(self.base / "nl0.json"))
        self.assertFalse(packet["audit_receipt_valid"])

    def test_packet_without_audit_does_not_claim_audited_inputs(self):
        packet = nl0.packet(self.check(), "R015")
        self.assertFalse(packet["audit_receipt_valid"])

    def test_failed_rerun_cannot_leave_previous_pass_as_latest(self):
        module_spec = importlib.util.spec_from_file_location("smoke_runner", CASE / "run_smoke.py")
        runner = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(runner)
        runner.CASE = self.base
        runner.ROOT = ROOT
        runner.RESULTS = self.base / "results"
        runner.RESULTS.mkdir()
        (runner.RESULTS / "summary.json").write_text('{"status":"FUNCTIONAL-SMOKE-PASSED"}\n')
        self.graph["propositions"][-1]["statement"] = "错误的目标替换。"
        self.write()
        self.assertEqual(runner.main(), 1)
        latest = nl0.load(runner.RESULTS / "summary.json")
        self.assertEqual(latest["status"], "FAILED")
        self.assertEqual(latest["failed_stage"], "graph-check")
        archived = list((self.base / "history/smoke-runs").glob("*.json"))
        self.assertEqual(len(archived), 1)
        self.assertEqual(nl0.load(archived[0])["status"], "FUNCTIONAL-SMOKE-PASSED")

    def test_unknown_input(self):
        self.step("R019")["inputs"].append("N999")
        with self.assertRaisesRegex(nl0.Invalid, "INPUT"):
            self.check()

    def test_duplicate_node(self):
        self.graph["propositions"].append(copy.deepcopy(self.graph["propositions"][0]))
        with self.assertRaisesRegex(nl0.Invalid, "DUPLICATE"):
            self.check()

    def test_unproved_internal_node(self):
        self.graph["inferences"] = [x for x in self.graph["inferences"] if x["id"] != "R012"]
        with self.assertRaisesRegex(nl0.Invalid, "PRODUCER"):
            self.check()

    def test_two_producers(self):
        duplicate = copy.deepcopy(self.step("R012"))
        duplicate["id"] = "R999"
        self.graph["inferences"].append(duplicate)
        with self.assertRaisesRegex(nl0.Invalid, "PRODUCER"):
            self.check()

    def test_cycle(self):
        step = self.step("R012")
        step["inputs"].append("P")
        step["argument"][0]["uses"].append("P")
        with self.assertRaisesRegex(nl0.Invalid, "CYCLE"):
            self.check()

    def test_hypothesis_cannot_be_added_during_proof(self):
        self.graph["propositions"].append(dict(id="H003", kind="hypothesis", statement="目标成立。", definitions=[]))
        with self.assertRaisesRegex(nl0.Invalid, "HYPOTHESIS"):
            self.check()

    def test_every_original_hypothesis_is_an_initial_node(self):
        self.graph["propositions"] = [x for x in self.graph["propositions"] if x["id"] != "H002"]
        with self.assertRaisesRegex(nl0.Invalid, "HYPOTHESIS"):
            self.check()

    def test_no_temporary_assumption_root(self):
        self.graph["propositions"].append(dict(id="L001", kind="local_assumption", statement="可微。", definitions=[]))
        with self.assertRaisesRegex(nl0.Invalid, "ID"):
            self.check()

    def test_global_notation_unique(self):
        self.spec["definitions"][1]["symbol"] = "U"
        self.rebind()
        with self.assertRaisesRegex(nl0.Invalid, "GLOBAL-NAME"):
            self.check()

    def test_local_notation_cannot_shadow_global(self):
        self.step("R015")["locals"][0]["symbol"] = "K"
        with self.assertRaisesRegex(nl0.Invalid, "SHADOW"):
            self.check()

    def test_same_dummy_name_can_have_distinct_scopes(self):
        self.step("R015")["locals"].append(dict(symbol="n", type="ℕ", scope="R015/unrelated_sum"))
        self.assertEqual(self.check()[0]["status"], "LEGACY-STRUCTURE-PASSED")

    def test_definition_cannot_prove_its_own_existence(self):
        node = next(x for x in self.graph["propositions"] if x["id"] == "N007")
        node["definitions"].append("D010")
        with self.assertRaisesRegex(nl0.Invalid, "DEFINITION-PREREQUISITE"):
            self.check()

    def test_definition_cycle(self):
        self.spec["definitions"][0]["depends_on"] = ["D005"]
        self.rebind()
        with self.assertRaisesRegex(nl0.Invalid, "DEFINITION-CYCLE"):
            self.check()

    def test_explicit_input_and_citation_must_agree(self):
        self.step("R015")["argument"][1]["uses"].append("M018")
        with self.assertRaisesRegex(nl0.Invalid, "CITATION"):
            self.check()

    def test_missing_application_hypothesis(self):
        self.step("R014")["applications"][0]["hypothesis_checks"].pop()
        with self.assertRaisesRegex(nl0.Invalid, "APPLICATION"):
            self.check()

    def test_unclosed_local_assumption(self):
        self.step("R015")["argument"][-1]["discharges"] = []
        with self.assertRaisesRegex(nl0.Invalid, "LOCAL-ASSUMPTION"):
            self.check()

    def test_weakening_target_fails_frozen_contract(self):
        self.graph["propositions"][-1]["statement"] = "几乎处处不可微。"
        with self.assertRaisesRegex(nl0.Invalid, "TARGET"):
            self.check()

    def test_changed_proof_invalidates_old_audit(self):
        self.step("R015")["argument"][-1]["text"] += " 新增一句。"
        with self.assertRaisesRegex(nl0.Invalid, "STALE-AUDIT"):
            self.check(True)

    def test_partial_audit_cannot_pass(self):
        del self.audit["inference_reviews"]["R012"]
        with self.assertRaisesRegex(nl0.Invalid, "AUDIT-COVERAGE"):
            self.check(True)

    def test_self_audit_cannot_claim_independence(self):
        self.audit["reviewer"]["independent"] = True
        with self.assertRaisesRegex(nl0.Invalid, "REVIEWER"):
            self.check(True)

    def test_changed_evidence_rejected(self):
        (self.base / "evidence/library-probe.log").write_text("tampered\n")
        with self.assertRaisesRegex(nl0.Invalid, "EVIDENCE-HASH"):
            self.check()

    def test_library_name_cannot_reuse_another_signature(self):
        node = next(x for x in self.graph["propositions"] if x["id"] == "M014")
        node["source"]["declaration"] = "Imaginary.not_a_mathlib_theorem"
        with self.assertRaisesRegex(nl0.Invalid, "SOURCE-SIGNATURE"):
            self.check()

    def test_library_module_must_match_source(self):
        node = next(x for x in self.graph["propositions"] if x["id"] == "M014")
        node["source"]["module"] = "Mathlib.Unrelated.Module"
        with self.assertRaisesRegex(nl0.Invalid, "SOURCE-MODULE"):
            self.check()

    def test_semantic_wrong_quantifier_is_not_automatically_proved(self):
        step = self.step("R015")
        step["argument"][-1]["text"] = "对每个 n 取 C_n=(4ℓ)^n，再令 C=C_n，故得到同一个 C 对所有 n 有效。关闭 L1。"
        self.assertEqual(self.check()[0]["status"], "LEGACY-STRUCTURE-PASSED")
        self.rebind()
        review = self.audit["inference_reviews"]["R015"]
        review["verdict"] = "FAIL"
        review["checks"]["argument"] = "FAIL"
        review["checks"]["output"] = "FAIL"
        review["notes"] = "∀n∃C_n 不能推出 ∃C∀n；因此该论证不能给统一上界。"
        with self.assertRaisesRegex(nl0.Invalid, "AUDIT-FAIL"):
            self.check(True)

    def test_semantic_hidden_triangle_requires_auditor(self):
        step = self.step("R015")
        step["inputs"].remove("M019")
        step["applications"] = []
        for paragraph in step["argument"]:
            paragraph["uses"] = [x for x in paragraph["uses"] if x != "M019"]
            paragraph["text"] = paragraph["text"].replace("M019", "未登记的三角不等式")
        self.graph["propositions"] = [x for x in self.graph["propositions"] if x["id"] != "M019"]
        del self.audit["source_reviews"]["M019"]
        self.assertEqual(self.check()[0]["status"], "LEGACY-STRUCTURE-PASSED")
        self.rebind()
        review = self.audit["inference_reviews"]["R015"]
        review["verdict"] = "FAIL"
        review["checks"]["dependency_accounting"] = "FAIL"
        review["notes"] = "论证实际使用了三角不等式，必须登记 M019 或提供内部证明。"
        with self.assertRaisesRegex(nl0.Invalid, "AUDIT-FAIL"):
            self.check(True)

    def test_semantic_invalid_assumption_discharge_requires_auditor(self):
        self.step("R017")["argument"][-1]["text"] = "因为已经在 L1 中假设可微，关闭 L1 后无条件保留可微本身，并把这当作 N017。"
        self.assertEqual(self.check()[0]["status"], "LEGACY-STRUCTURE-PASSED")
        self.rebind()
        review = self.audit["inference_reviews"]["R017"]
        review["verdict"] = "FAIL"
        review["checks"]["scope"] = "FAIL"
        review["checks"]["output"] = "FAIL"
        review["notes"] = "删除 L1 的记录不能无条件保留假设；实际陈述也与 N017 的否定命题相反。"
        with self.assertRaisesRegex(nl0.Invalid, "AUDIT-FAIL"):
            self.check(True)

    def test_duplicate_json_key_fails_before_validation(self):
        path = self.base / "duplicate.json"
        path.write_text('{"id":"N001","id":"H001"}')
        with self.assertRaisesRegex(nl0.Invalid, "Duplicate JSON key"):
            nl0.load(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
