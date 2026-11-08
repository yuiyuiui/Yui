"""The editable graph producer must reject what the global NL0 reader will reject."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import harness_support as support
from basis_fixtures import active_artifact, artifact, dependency, TARGET
from controller_common import bind, manifest, write
import basis
import basis_graph
import frozen_graph
import nl0


class GraphReviewOrder(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.valid = active_artifact(artifact(dependency()))
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        (self.inputs / "problem.md").write_text(TARGET)
        manifest(self.inputs)

    def test_author_can_patch_rejected_prose_without_rewiring_edges(self):
        for pid, text, code in (("H001", "As specified in the target.", "OPAQUE-REFERENCE"),
                                ("N001", "Under H001 the claim follows.", "OPAQUE-STATEMENT"),
                                ("P", "Use H001–H004.", "OPAQUE-STATEMENT"),
                                ("N001", "By Theorem 2.1 we are done.", "OPAQUE-REFERENCE")):
            with self.subTest(pid=pid, text=text):
                validator = basis.BasisContract(self.root, TARGET)
                draft = deepcopy(self.valid)
                idx = next(i for i,p in enumerate(draft["global_graph"]["propositions"]) if p["id"] == pid)
                patch_path = f"/global_graph/propositions/{idx}/statement"
                draft["global_graph"]["propositions"][idx]["statement"] = text
                with patch("basis_native.check") as native:
                    with self.assertRaisesRegex(ValueError, f"{code}: {pid}"):
                        validator(draft)
                    with self.assertRaisesRegex(ValueError, f"{code}: {pid}"):
                        basis_graph.optimize(draft)
                    native.assert_not_called()
                self.assertIsNone(validator.selected)
                self.assertIsNone(validator.last_checked)
                instruction = {"base_candidate":1, "patches":[{"op":"replace","path":patch_path,
                    "value":self.valid["global_graph"]["propositions"][idx]["statement"]}]}
                fixed, _ = validator.save(instruction)
                basis.validate(fixed,TARGET)
                self.assertEqual(fixed, self.valid)
                self.assertTrue(any("H001" in inference["inputs"] for inference in fixed["global_graph"]["inferences"]))

    def test_real_stage_accepts_repaired_node_and_reuses_its_native_check(self):
        import basis_author
        import basis_native
        validator = basis.BasisContract(self.root, TARGET)
        stage = basis_author.BasisStage(self.root/'stage', basis.PROMPT, phase='basis-authoring',
                                       validator=validator, inputs=self.inputs/'inputs.json')
        self.addCleanup(stage.release_resources, 'USER_CANCELLED')
        draft = deepcopy(self.valid)
        idx = next(i for i, p in enumerate(draft['global_graph']['propositions']) if p['id'] == 'N001')
        original = draft['global_graph']['propositions'][idx]['statement']
        draft['global_graph']['propositions'][idx]['statement'] = 'The conclusion under H001.'
        with patch.object(basis_native, 'check', wraps=basis_native.check) as compiler:
            rejected = stage.dispatch('submit_draft', {'artifact':draft})
            self.assertEqual(rejected['feedback_kind'], 'candidate_rejected')
            self.assertIn('N001', rejected['error'])
            self.assertIsNone(stage.accepted)
            compiler.assert_not_called()
            checked = stage.dispatch('check_draft', {'artifact':{'base_candidate':1, 'patches':[
                {'op':'replace','path':f'/global_graph/propositions/{idx}/statement','value':original}]}})
            self.assertTrue(checked['accepted'])
            self.assertFalse(checked['stage_complete'])
            selected = stage.dispatch('submit_draft', {'artifact':{'accept_candidate':2}})
            self.assertTrue(selected['stage_complete'])
            self.assertEqual(compiler.call_count, 1)
        self.assertEqual(stage.accepted['global_graph'], self.valid['global_graph'])

    def test_changed_original_is_rejected_while_the_revision_author_can_edit(self):
        import json
        source = support.TESTS / 'fixtures/closed-addition'
        spec, graph = nl0.load(source/'spec.json'), nl0.load(source/'nl0.json')
        doc = {'prior-global.json':json.dumps({'spec':spec, 'graph':frozen_graph.shape(graph)})}
        owner = frozen_graph.AuthorContract(self.root/'revision', doc, spec['case_id'], frozen_graph.DIRECT)
        modified = deepcopy(spec)
        modified['parameters'][0]['type']='a different domain'
        with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGE_REQUIRES_USER'):
            owner({'spec':modified, **frozen_graph.shape(graph)})
        self.assertIsNone(owner.last_valid_candidate)
        self.assertFalse((owner.directory/'frozen.json').exists())

    def test_checked_receipt_is_editable_until_freeze_and_tampering_is_refused(self):
        import shutil
        base = support.TESTS / "fixtures/closed-addition"
        source = self.root / "global-graphs/0001/stage/case"
        shutil.copytree(base, source)
        graph = nl0.load(source / "nl0.json")
        graph.update(frozen_graph.shape(graph))
        write(source / "nl0.json", graph)
        checked = frozen_graph.checked_receipt(source, frozen_graph.DIRECT)
        self.assertFalse((source / "frozen.json").exists())
        job = {"root":str(self.root)}
        original = (source / "nl0.json").read_bytes()
        with (source / "nl0.json").open("ab") as stream:
            stream.write(b" ")
        with self.assertRaises(ValueError):
            frozen_graph.select(job, checked)
        self.assertFalse((self.root / "global-selection.json").exists())
        (source / "nl0.json").write_bytes(original)
        conflict = source / "frozen.json"
        conflict.write_text("previous version")
        with self.assertRaisesRegex(ValueError, "differs"):
            frozen_graph.select(job, checked)
        self.assertEqual(conflict.read_text(), "previous version")
        self.assertFalse((self.root / "global-selection.json").exists())
        conflict.unlink()
        frozen = frozen_graph.select(job, checked)
        self.assertEqual(checked["sha256"], frozen["sha256"])
        self.assertEqual(frozen, bind(source / "frozen.json"))
        self.assertEqual(frozen_graph.select(job, checked), frozen)
        self.assertEqual(nl0.load(self.root / "global-selection.json"), frozen)
