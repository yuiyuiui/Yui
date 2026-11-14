"""v2 accounting and v3 receipt regressions; no model-detection claim is made."""
import harness_support
import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = importlib.util.spec_from_file_location("closed_nl0", ROOT / "nl0/scripts/nl0.py")
nl0 = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(nl0)


class ClosureChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nl0-v2-test-")
        self.base = Path(self.temp.name)
        for p in (ROOT / "tests/fixtures/closed-addition").iterdir():
            if p.is_file():
                shutil.copy2(p, self.base / p.name)
        self.spec = nl0.load(self.base / "spec.json")
        self.graph = nl0.load(self.base / "nl0.json")

    def tearDown(self):
        self.temp.cleanup()

    def write(self):
        (self.base / "spec.json").write_text(json.dumps(self.spec, indent=2) + "\n")
        self.graph["spec_sha256"] = nl0.sha(self.base / "spec.json")
        (self.base / "nl0.json").write_text(json.dumps(self.graph, indent=2) + "\n")

    def data(self, audit=None, inspect=False):
        self.write()
        if audit is not None:
            (self.base / "audit-a.json").write_text(json.dumps(audit, indent=2) + "\n")
        return nl0.validate(self.base / "nl0.json", self.base / "spec.json",
                            self.base / "audit-a.json" if audit is not None else None,
                            allow_unresolved=inspect)

    def template(self):
        return nl0.closure.audit_template(self.data(), nl0.CHECKS, nl0.EXTERNAL_CHECKS,
                                          "nl0.json", "spec.json")

    def shape_only_receipt(self):
        """Synthetic record-shape fixture; it is never saved as a real review."""
        audit = self.template()
        audit["reviewer"]["identity"] = "Synthetic metadata test, not a real auditor"
        audit["reviewer"]["mode"] = "synthetic_unit_fixture"
        audit["reviewer"]["independent"] = True  # Fabricated field for positive validation controls only.

        def fill(value):
            if isinstance(value, dict):
                if "verdict" in value:
                    value["verdict"] = "PASS"
                    value["notes"] = "Synthetic shape assertion only; no mathematical review occurred."
                if "locations" in value:
                    value["locations"] = ["/output/statement"]
                for child in value.values():
                    fill(child)
            elif isinstance(value, list):
                for child in value:
                    fill(child)
        fill(audit)
        for entry in audit["inference_reviews"].values():
            replay = entry["replay"]
            replay.update(mode="fresh_packet_only", carrier="synthetic-test-fixture",
                          read_materials=["packet:" + replay["packet_sha256"]])
        return audit

    def test_complete_nonindependent_receipt_cannot_authorize_translation(self):
        audit=self.shape_only_receipt();audit['reviewer'].update(mode='same_context_self_audit',independent=False)
        result=self.data(audit)[0]
        self.assertTrue(result['audit_record_complete'])
        self.assertFalse(result['audit_receipt_valid']);self.assertFalse(result['current_standard_receipt_valid'])
        self.assertEqual(result['audit_status'],'AUDIT-REVIEW-UNQUALIFIED')
        import translation_author
        with self.assertRaisesRegex(ValueError,'Accepted current Audit A'):
            translation_author.prepare(self.base,self.base,self.base/'blocked-interface')

    def test_complete_example_and_packet_are_structural_only(self):
        data = self.data()
        self.assertEqual(data[0]["status"], "STRUCTURE-PASSED")
        self.assertFalse(data[0]["current_standard_receipt_valid"])
        self.assertFalse(data[0]["mathematics_automatically_verified"])
        packet = nl0.packet(data, "R002")
        self.assertEqual([x["id"] for x in packet["inputs"]], ["N001"])
        for key in ["original_hypotheses", "full_target", "definition_prerequisites", "audit_receipt_valid"]:
            self.assertNotIn(key, packet)
        self.assertNotIn("origin", packet["inputs"][0])
        self.assertNotIn("H001", json.dumps(packet))
        self.assertEqual(packet["packet_sha256"], nl0.closure.digest(packet))

    def test_removed_graph_format_is_rejected(self):
        self.spec['format_version']=1;self.graph['format_version']=1
        with self.assertRaisesRegex(nl0.Invalid,'Only the current NL0 format'):
            self.data()

    def test_missing_producer_and_dependency_cycle_are_rejected(self):
        original=copy.deepcopy(self.graph)
        self.graph['inferences']=[r for r in self.graph['inferences'] if r['id']!='R001']
        with self.assertRaisesRegex(nl0.Invalid,'PRODUCER'):self.data()
        self.graph=original
        self.graph['inferences'][0]['inputs'].append('P')
        self.graph['inferences'][0]['argument'][0]['uses'].append('P')
        with self.assertRaisesRegex(nl0.Invalid,'CYCLE'):self.data()

    def test_numbered_formula_cannot_replace_output_content(self):
        self.graph["propositions"][1]["statement"] = "The identity (8.3) holds."
        with self.assertRaisesRegex(nl0.Invalid, "OPAQUE-REFERENCE"):
            self.data()

    def test_target_or_problem_shortcut_is_not_a_standalone_statement(self):
        original=copy.deepcopy(self.graph)
        for index in range(len(self.graph['propositions'])):
            self.graph=copy.deepcopy(original)
            p=self.graph['propositions'][index]
            p['statement']='The objects are as specified in the target statement.'
            if p['kind']=='hypothesis':self.spec['hypotheses'][0]['statement']=p['statement']
            if p['kind']=='target':self.spec['conclusion']=p['statement']
            with self.assertRaisesRegex(nl0.Invalid,'OPAQUE-REFERENCE'):self.data()
            self.spec=nl0.load(ROOT/'tests/fixtures/closed-addition/spec.json')

    def test_proof_metacommentary_does_not_supply_or_replace_a_statement(self):
        self.graph['inferences'][1]['argument'][1]['text']+=' This proves the target.'
        self.assertEqual(self.data()[0]['status'],'STRUCTURE-PASSED')

    def test_definition_cannot_use_the_problem_as_its_content(self):
        self.spec['definitions']=[dict(id='D001',symbol='d',type='natural number',
            definition='d is as defined in the problem.',depends_on=[],requires=[],binders=[],objects=['a'])]
        with self.assertRaisesRegex(nl0.Invalid,'OPAQUE-REFERENCE'):self.data()

    def test_scope_owner_label_must_name_actual_inference(self):
        local=self.graph['inferences'][1]['locals'][0]
        local['scope']='R001/argument'
        with self.assertRaisesRegex(nl0.Invalid,'LOCAL-SCOPE-OWNER'):self.data()
        local['scope']='Within this inference'
        self.assertEqual(self.data()[0]['status'],'STRUCTURE-PASSED')

    def test_global_overview_reports_unused_original_h_without_inventing_a_use(self):
        self.spec['hypotheses'].append(dict(id='H002',statement='a≠0.',origin='Synthetic original given.'))
        self.graph['propositions'].append(dict(id='H002',kind='hypothesis',statement='a≠0.',
            definitions=[],binders=[],objects=['a','0']))
        data=self.data();view=nl0.global_overview(data)
        self.assertEqual(view['schema'],'yui-global-overview-2')
        self.assertEqual(view['inventory']['unused_original_hypotheses'],['H002'])
        self.assertEqual(view['inventory']['unused_original_hypotheses'],data[0]['unused_original_hypotheses'])
        self.assertNotIn('H002',self.graph['inferences'][1]['inputs'])

    def test_declaration_failure_identifies_actual_record_among_same_start_locals(self):
        r=self.graph['inferences'][1]
        r['locals'].append(dict(symbol='d',type='natural number',scope='R002/argument',
            start='S001',end='S002',kind='definition',declaration='Define d=a.',
            from_inputs=[],from_local=[],objects=['a']))
        r['locals'][0]['objects'].append('d')
        with self.assertRaisesRegex(nl0.Invalid,r'/graph/inferences/1/locals/0') as failure:self.data()
        self.assertIn('declaration[c]',str(failure.exception))
        self.assertIn("missing=['d']",str(failure.exception))

    def test_proposition_id_cannot_replace_statement(self):
        self.graph["propositions"][1]["statement"] = "The conclusion of H001 holds."
        with self.assertRaisesRegex(nl0.Invalid, "OPAQUE-STATEMENT"):
            self.data()

    def test_paper_notation_cannot_supply_an_object(self):
        self.graph["inferences"][1]["argument"][1]["text"] = "Use the notation as defined in the original manuscript."
        with self.assertRaisesRegex(nl0.Invalid, "OPAQUE-REFERENCE"):
            self.data()

    def test_explicitly_used_object_must_be_declared(self):
        self.graph["inferences"][1]["argument"][1]["objects"].append("source_only_vector")
        with self.assertRaisesRegex(nl0.Invalid, "UNDECLARED-OBJECT"):
            self.data()

    def test_bound_input_variable_does_not_become_free(self):
        self.graph["propositions"][1]["binders"] = [{"symbol": "z", "type": "natural number"}]
        self.graph["inferences"][1]["argument"][1]["objects"].append("z")
        with self.assertRaisesRegex(nl0.Invalid, "UNDECLARED-OBJECT"):
            self.data()

    def test_object_cannot_escape_local_scope(self):
        self.graph["inferences"][1]["locals"][0]["end"] = "S001"
        with self.assertRaisesRegex(nl0.Invalid, "UNDECLARED-OBJECT"):
            self.data()

    def test_witness_requires_an_existence_basis(self):
        self.graph["inferences"][1]["locals"][0]["kind"] = "witness"
        with self.assertRaisesRegex(nl0.Invalid, "WITNESS-EXISTENCE"):
            self.data()

    def test_local_introduction_cannot_cite_an_unlisted_fact(self):
        self.graph["inferences"][1]["locals"][0]["declaration"] += " Use H001."
        with self.assertRaisesRegex(nl0.Invalid, "UNDECLARED-FACT"):
            self.data()

    def test_local_fact_must_precede_its_use(self):
        self.graph["inferences"][1]["argument"][0]["uses_local"] = ["F001"]
        with self.assertRaisesRegex(nl0.Invalid, "LOCAL-FACT-ORDER"):
            self.data()

    def test_fact_cannot_leak_a_scoped_object_even_if_consumer_omits_it(self):
        r = self.graph["inferences"][1]
        r["locals"][0]["end"] = "S001"
        r["argument"][1]["objects"].remove("c")
        with self.assertRaisesRegex(nl0.Invalid, "LOCAL-FACT-SCOPE") as rejected:
            self.data()
        self.assertIn('"fact": "F001"',str(rejected.exception))
        self.assertIn('"missing_objects": ["c"]',str(rejected.exception))
        self.assertIn('"produced_at": "S001"',str(rejected.exception))

    def test_local_fact_cannot_escape_its_assumption(self):
        r = self.graph["inferences"][1]
        r["argument"][0]["introduces"] = ["L1"]
        r["argument"][0]["produces"][0]["assumptions"] = ["L1"]
        r["argument"].insert(1, dict(id="S003", text="Discharge L1 into a conditional statement.",
                                     uses=[], uses_local=[], objects=[], produces=[], introduces=[], discharges=["L1"]))
        with self.assertRaisesRegex(nl0.Invalid, "LOCAL-FACT-SCOPE"):
            self.data()

    def test_quantified_local_fact_keeps_its_binder_local(self):
        f = self.graph["inferences"][1]["argument"][0]["produces"][0]
        f.update(statement="For every natural number z, c=a and z=z.", binders=[dict(symbol="z", type="natural number")], objects=["a", "c", "z"])
        self.assertEqual(self.data()[0]["status"], "STRUCTURE-PASSED")

    def test_using_an_unlisted_ancestor_in_prose_fails(self):
        self.graph["inferences"][1]["argument"][1]["text"] += " Also invoke H001."
        with self.assertRaisesRegex(nl0.Invalid, "UNDECLARED-FACT"):
            self.data()

    def test_definition_guard_cannot_smuggle_an_ancestor(self):
        self.spec["definitions"] = [dict(id="D001", symbol="d", type="natural number", definition="d=a.",
                                         depends_on=[], requires=["H001"], binders=[], objects=["a"])]
        self.graph["propositions"][1]["definitions"] = ["D001"]
        with self.assertRaisesRegex(nl0.Invalid, "DIRECT-GUARD"):
            self.data()

    def test_primitive_cannot_shadow_a_global_parameter(self):
        self.spec["logic"]["primitives"].append(dict(symbol="a", type="natural number", meaning="duplicate"))
        with self.assertRaisesRegex(nl0.Invalid, "SHADOW"):
            self.data()

    def test_pending_template_has_no_pass_and_cannot_be_accepted(self):
        audit = self.template()
        verdicts = []
        def collect(value):
            if isinstance(value, dict):
                if "verdict" in value:
                    verdicts.append(value["verdict"])
                for child in value.values():
                    collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)
        collect(audit)
        self.assertEqual(set(verdicts), {"UNVERIFIED"})
        with self.assertRaisesRegex(nl0.Invalid, "AUDIT-FAIL"):
            self.data(audit)
        result = self.data(audit, inspect=True)[0]
        self.assertTrue(result["audit_record_complete"])
        self.assertFalse(result["audit_receipt_valid"])
        self.assertFalse(result["current_standard_receipt_valid"])

    def test_audit_checks_require_individual_notes_evidence_and_locations(self):
        audit = self.shape_only_receipt()
        audit["inference_reviews"]["R002"]["checks"]["statement_closure"] = "PASS"
        with self.assertRaisesRegex(nl0.Invalid, "TYPE"):
            self.data(audit)

    def test_pass_without_a_checked_location_is_rejected(self):
        audit = self.shape_only_receipt()
        audit["inference_reviews"]["R002"]["checks"]["statement_closure"]["locations"] = []
        with self.assertRaisesRegex(nl0.Invalid, "AUDIT-LOCATION"):
            self.data(audit)

    def test_locations_must_resolve_inside_the_packet(self):
        audit = self.shape_only_receipt()
        audit["inference_reviews"]["R002"]["checks"]["statement_closure"]["locations"] = ["/upstream/R001/argument"]
        with self.assertRaisesRegex(nl0.Invalid, "AUDIT-LOCATION"):
            self.data(audit)

    def test_unperformed_replay_cannot_be_pass(self):
        audit = self.shape_only_receipt()
        audit["inference_reviews"]["R002"]["replay"]["mode"] = "unperformed"
        with self.assertRaisesRegex(nl0.Invalid, "REPLAY-BOUNDARY"):
            self.data(audit)

    def test_source_proof_access_invalidates_packet_only_pass(self):
        audit = self.shape_only_receipt()
        audit["inference_reviews"]["R002"]["replay"]["read_materials"].append("source-proof.txt")
        with self.assertRaisesRegex(nl0.Invalid, "REPLAY-BOUNDARY"):
            self.data(audit)

    def test_prior_exposure_cannot_claim_fresh_replay(self):
        audit = self.shape_only_receipt()
        audit["inference_reviews"]["R002"]["replay"]["prior_exposure"] = ["original proof"]
        with self.assertRaisesRegex(nl0.Invalid, "REPLAY-BOUNDARY"):
            self.data(audit)

    def test_replay_is_bound_to_actual_packet_bytes(self):
        audit = self.shape_only_receipt()
        audit["inference_reviews"]["R002"]["replay"]["packet_sha256"] = "0" * 64
        with self.assertRaisesRegex(nl0.Invalid, "STALE-PACKET"):
            self.data(audit)

    def test_receipt_shape_cannot_claim_mathematical_verification(self):
        result = self.data(self.shape_only_receipt())[0]
        self.assertTrue(result["current_standard_receipt_valid"])
        self.assertFalse(result["mathematics_automatically_verified"])

    def test_legacy_receipt_cannot_satisfy_new_contract(self):
        audit = self.template()
        audit["format_version"] = 2
        with self.assertRaisesRegex(nl0.Invalid, "AUDIT-VERSION"):
            self.data(audit)


    def test_cli_audit_template_refuses_overwrite(self):
        self.write()
        out = self.base / "fresh-audit.json"
        cmd = [sys.executable, "-B", str(ROOT / "nl0/scripts/nl0.py"), "audit-template",
               str(self.base / "nl0.json"), "--spec", str(self.base / "spec.json"), "--out", str(out)]
        first = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        before = out.read_bytes()
        second = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual(out.read_bytes(), before)

    def test_uninventoried_semantic_error_is_not_claimed_detected(self):
        # A natural-language parser is deliberately not claimed: a fresh auditor must catch this.
        self.graph["inferences"][1]["argument"][1]["text"] += " The source-only object w has the required property."
        self.assertEqual(self.data()[0]["status"], "STRUCTURE-PASSED")
        self.assertFalse(self.data(self.template(), inspect=True)[0]["audit_receipt_valid"])

    def test_control_preparation_does_not_run_or_predetermine_a_review(self):
        module = importlib.util.spec_from_file_location("review_cases", ROOT / "nl0/scripts/prepare-review-cases.py")
        preparer = importlib.util.module_from_spec(module)
        module.loader.exec_module(preparer)
        destination = self.base / "controls"
        result = preparer.prepare(destination)
        self.assertEqual(result["status"], "NOT_RUN")
        manifest = nl0.load(destination / "owner/expected.json")
        self.assertEqual(manifest["status"], "NOT_RUN")
        for filename in manifest["expected"]:
            p = nl0.load(destination / "reviewer" / filename)
            self.assertNotIn("expected_verdict", p)
            self.assertNotIn("verdict", p)
            self.assertEqual(p["packet_sha256"], nl0.closure.digest(p))
        with self.assertRaises(FileExistsError):
            preparer.prepare(destination)


if __name__ == "__main__":
    unittest.main()
