"""Metadata-only fixtures: these tests do not authenticate a mathematical source."""
import harness_support
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = importlib.util.spec_from_file_location("external_nl0", ROOT / "nl0/scripts/nl0.py")
nl0 = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(nl0)


class ExternalAuditRecords(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="external-audit-fixture-")
        self.base = Path(self.temp.name)
        primary = self.base / "fixture.txt"
        primary.write_text("SYNTHETIC UNIT FIXTURE. This is not a publication or a mathematical proof.\n")
        self.evidence = [{"path": "fixture.txt", "sha256": nl0.sha(primary)}]
        self.spec = dict(format_version=1, case_id="metadata-only-fixture",
                         full_target="Synthetic fixture target.", conclusion="Synthetic fixture target.",
                         parameters=[], hypotheses=[], definitions=[],
                         logic=dict(classical=True, rules=["direct"], calculations=["Fixture only."]),
                         pins=dict(lean_version="4.32.2", mathlib_commit="fixture", mathlib_root="fixture"),
                         inputs=copy.deepcopy(self.evidence))
        source = {k: "SYNTHETIC fixture; no real source claim." for k in (
            "author", "title", "version", "identifier", "locator", "notation_map", "errata",
            "source_kind", "origin", "retrieved_at", "source_statement", "context",
            "qualification", "version_check")}
        source.update(statement="Synthetic source premise.", evidence=copy.deepcopy(self.evidence),
                      primary_evidence=copy.deepcopy(self.evidence), hypotheses=["Fixture condition one.", "Fixture condition two."])
        self.graph = dict(format_version=1, case_id=self.spec["case_id"], spec_sha256="pending",
                          propositions=[dict(id="E001", kind="external", statement=source["statement"],
                                             definitions=[], source=source),
                                        dict(id="P", kind="target", statement=self.spec["conclusion"], definitions=[])],
                          inferences=[dict(id="R001", inputs=["E001"], output="P", definitions=[], rules=["direct"],
                                           locals=[], argument=[dict(text="Synthetic argument only.", uses=["E001"], introduces=[], discharges=[])],
                                           applications=[dict(id="A001", input="E001", bindings="Synthetic binding.",
                                                              hypothesis_checks=["Fixture check one.", "Fixture check two."])])])
        source_review = self.review()
        source_review["citation_checks"] = {k: self.review() for k in nl0.EXTERNAL_CHECKS}
        inference_review = self.review()
        inference_review.update(checks={k: "PASS" for k in nl0.LEGACY_CHECKS},
                                external_applications={"A001": self.application_review()})
        self.audit = dict(format_version=2, graph_sha256="pending", spec_sha256="pending",
                          reviewer=dict(identity="synthetic unit fixture", mode="same_context_self_audit", independent=False,
                                        disclosure="Metadata testing only; no actual source or proof audited."),
                          target_review=self.review(), definition_reviews={}, source_reviews={"E001": source_review},
                          inference_reviews={"R001": inference_review})
        self.rebind()

    def tearDown(self):
        self.temp.cleanup()

    def review(self):
        return dict(verdict="PASS", notes="Synthetic record shape only; this is not mathematical evidence.",
                    evidence=copy.deepcopy(self.evidence))

    def application_review(self):
        return dict(input="E001", **self.review(), bindings_review=self.review(),
                    hypothesis_reviews=[self.review(), self.review()], conclusion_review=self.review(), bridges=[])

    def write(self):
        for name, obj in [("spec.json", self.spec), ("nl0.json", self.graph), ("audit-a.json", self.audit)]:
            (self.base / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")

    def rebind(self):
        self.write()
        self.graph["spec_sha256"] = nl0.sha(self.base / "spec.json")
        self.write()
        self.audit["spec_sha256"] = nl0.sha(self.base / "spec.json")
        self.audit["graph_sha256"] = nl0.sha(self.base / "nl0.json")

    def check(self, *, audit=True, inspect=False):
        self.write()
        return nl0.validate(self.base / "nl0.json", self.base / "spec.json",
                            self.base / "audit-a.json" if audit else None, allow_unresolved=inspect, legacy=True)

    def test_complete_record_never_claims_automatic_mathematical_verification(self):
        result = self.check()[0]
        self.assertFalse(result["audit_receipt_valid"])
        self.assertFalse(result["mathematics_automatically_verified"])

    def test_current_contract_preserves_all_pending_external_obligations(self):
        # Synthetic shape fixture, not a real publication or source verification.
        self.spec["format_version"] = self.graph["format_version"] = 2
        self.spec["logic"]["primitives"] = []
        for p in self.graph["propositions"]:
            p.update(binders=[], objects=[])
        for r in self.graph["inferences"]:
            for i, paragraph in enumerate(r["argument"], 1):
                paragraph.update(id=f"S{i:03d}", objects=[], uses_local=[], produces=[])
            for app in r["applications"]:
                app["at"] = "S001"
        self.rebind()
        data = nl0.validate(self.base / "nl0.json", self.base / "spec.json")
        pending = nl0.closure.audit_template(data, nl0.CHECKS, nl0.EXTERNAL_CHECKS, "nl0.json", "spec.json")
        self.assertEqual(set(pending["source_reviews"]["E001"]["citation_checks"]), nl0.EXTERNAL_CHECKS)
        self.assertEqual(len(pending["inference_reviews"]["R001"]["external_applications"]["A001"]["hypothesis_reviews"]), 2)
        (self.base / "pending.json").write_text(json.dumps(pending))
        inspected = nl0.validate(self.base / "nl0.json", self.base / "spec.json", self.base / "pending.json", allow_unresolved=True)[0]
        self.assertFalse(inspected["current_standard_receipt_valid"])
        self.assertTrue(any("citation_checks" in item["review"] for item in inspected["unresolved_reviews"]))
        app = self.graph["inferences"][0]["applications"][0]
        app["hypothesis_checks"][0] += " Use N999."
        self.rebind()
        with self.assertRaisesRegex(nl0.Invalid, "UNDECLARED-FACT"):
            nl0.validate(self.base / "nl0.json", self.base / "spec.json")
        app["hypothesis_checks"][0] = "Fixture check one."
        app["at"] = "S999"
        self.rebind()
        with self.assertRaisesRegex(nl0.Invalid, "APPLICATION-STEP"):
            nl0.validate(self.base / "nl0.json", self.base / "spec.json")

    def test_each_citation_check_is_required(self):
        for key in nl0.EXTERNAL_CHECKS:
            with self.subTest(key=key):
                removed = self.audit["source_reviews"]["E001"]["citation_checks"].pop(key)
                with self.assertRaisesRegex(nl0.Invalid, "FIELDS"):
                    self.check()
                self.audit["source_reviews"]["E001"]["citation_checks"][key] = removed

    def test_source_check_has_its_own_evidence(self):
        self.audit["source_reviews"]["E001"]["citation_checks"]["result_location"]["evidence"] = []
        with self.assertRaisesRegex(nl0.Invalid, "EVIDENCE"):
            self.check()

    def test_legacy_audit_cannot_certify_external_graph(self):
        self.audit["format_version"] = 1
        with self.assertRaisesRegex(nl0.Invalid, "AUDIT-VERSION"):
            self.check()

    def test_primary_evidence_is_required(self):
        self.graph["propositions"][0]["source"]["primary_evidence"] = []
        with self.assertRaisesRegex(nl0.Invalid, "EVIDENCE"):
            self.check(audit=False)

    def test_primary_evidence_must_be_bound_to_source(self):
        other = self.base / "other.txt"
        other.write_text("different synthetic fixture")
        self.graph["propositions"][0]["source"]["primary_evidence"] = [{"path": "other.txt", "sha256": nl0.sha(other)}]
        with self.assertRaisesRegex(nl0.Invalid, "SOURCE-EVIDENCE"):
            self.check(audit=False)

    def test_external_application_requires_actual_use_id(self):
        del self.graph["inferences"][0]["applications"][0]["id"]
        with self.assertRaisesRegex(nl0.Invalid, "APPLICATION-ID"):
            self.check(audit=False)

    def test_repeated_source_use_has_separate_review(self):
        second = copy.deepcopy(self.graph["inferences"][0]["applications"][0])
        second.update(id="A002", bindings="A second synthetic binding.")
        self.graph["inferences"][0]["applications"].append(second)
        self.rebind()
        with self.assertRaisesRegex(nl0.Invalid, "AUDIT-APPLICATION-COVERAGE"):
            self.check()
        self.audit["inference_reviews"]["R001"]["external_applications"]["A002"] = self.application_review()
        self.assertFalse(self.check()[0]["audit_receipt_valid"])

    def test_duplicate_actual_use_id_is_rejected(self):
        self.graph["inferences"][0]["applications"].append(copy.deepcopy(self.graph["inferences"][0]["applications"][0]))
        with self.assertRaisesRegex(nl0.Invalid, "APPLICATION"):
            self.check(audit=False)

    def test_each_hypothesis_needs_a_separate_review(self):
        self.audit["inference_reviews"]["R001"]["external_applications"]["A001"]["hypothesis_reviews"].pop()
        with self.assertRaisesRegex(nl0.Invalid, "AUDIT-HYPOTHESIS-COVERAGE"):
            self.check()

    def test_application_cannot_be_reviewed_against_another_source(self):
        self.audit["inference_reviews"]["R001"]["external_applications"]["A001"]["input"] = "E002"
        with self.assertRaisesRegex(nl0.Invalid, "AUDIT-APPLICATION-SOURCE"):
            self.check()

    def test_bridge_must_be_an_available_proved_internal_node(self):
        self.audit["inference_reviews"]["R001"]["external_applications"]["A001"]["bridges"] = ["P"]
        with self.assertRaisesRegex(nl0.Invalid, "AUDIT-BRIDGE"):
            self.check()

    def test_failed_source_blocks_acceptance_despite_blanket_parent_pass(self):
        self.audit["source_reviews"]["E001"]["citation_checks"]["statement_fidelity"]["verdict"] = "FAIL"
        with self.assertRaisesRegex(nl0.Invalid, "AUDIT-FAIL"):
            self.check()

    def test_inspection_preserves_unverified_source_without_acceptance(self):
        self.audit["source_reviews"]["E001"]["citation_checks"]["result_location"]["verdict"] = "UNVERIFIED"
        result = self.check(inspect=True)[0]
        self.assertTrue(result["audit_record_complete"])
        self.assertFalse(result["audit_receipt_valid"])
        self.assertEqual(result["audit_status"], "AUDIT-REVIEW-UNQUALIFIED")
        self.assertEqual(result["unresolved_reviews"][0]["verdict"], "UNVERIFIED")

    def test_failed_application_blocks_acceptance(self):
        self.audit["inference_reviews"]["R001"]["external_applications"]["A001"]["hypothesis_reviews"][0]["verdict"] = "FAIL"
        with self.assertRaisesRegex(nl0.Invalid, "AUDIT-FAIL"):
            self.check()

    def test_inspection_still_requires_complete_records(self):
        del self.audit["source_reviews"]["E001"]["citation_checks"]["literature_identity"]
        with self.assertRaisesRegex(nl0.Invalid, "FIELDS"):
            self.check(inspect=True)

    def test_unknown_verdict_is_not_an_unverified_review(self):
        self.audit["target_review"]["verdict"] = "PROBABLY PASS"
        with self.assertRaisesRegex(nl0.Invalid, "AUDIT-VERDICT"):
            self.check(inspect=True)

    def test_changing_source_invalidates_previous_receipt(self):
        self.graph["propositions"][0]["source"]["source_statement"] += " Changed condition."
        with self.assertRaisesRegex(nl0.Invalid, "STALE-AUDIT"):
            self.check()


if __name__ == "__main__":
    unittest.main(verbosity=2)
