"""Adversarial request/tool-boundary controls; no personal context is dispatched."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run_pilot as carrier
from clean_stage import ArtifactStage


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.worker = ArtifactStage(self.root/'stage', 'EXPLICIT_TASK', phase='control', library=False)
        self.worker.allowed_user_messages = {'EXPLICIT_TASK'}
        self.worker.initial_user_message = 'EXPLICIT_TASK'

    def tearDown(self):
        import shutil
        shutil.rmtree(self.worker.work)
        self.temp.cleanup()

    def payload(self):
        return {'model': 'gpt-6-luna', 'reasoning': {'effort': 'high'},
                'instructions': 'FOREIGN_INSTRUCTION_CANARY',
                'input': [{'role': 'developer', 'content': [{'type': 'input_text', 'text': 'PRIVATE_SKILL_CANARY'}]},
                          {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'FOREIGN_TASK_CANARY'}]},
                          {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'EXPLICIT_TASK'}]}],
                'tools': [{'type': 'web_search'}], 'service_tier': 'priority',
                'client_metadata': {'memory': 'PRIVATE_MEMORY_CANARY'}}

    def test_only_allowlisted_semantic_payload_survives(self):
        sent = self.worker.normalize_request(self.payload())
        text = json.dumps(sent)
        for token in ['FOREIGN_INSTRUCTION_CANARY', 'PRIVATE_SKILL_CANARY', 'FOREIGN_TASK_CANARY', 'PRIVATE_MEMORY_CANARY', 'web_search']:
            self.assertNotIn(token, text)
        self.assertEqual(sent['instructions'], self.worker.system)
        self.assertEqual(sent['service_tier'], 'default')

    def test_other_model_and_effort_fail_closed(self):
        p = self.payload();p['model'] = 'gpt-5.6-luna'
        with self.assertRaises(ValueError):self.worker.normalize_request(p)
        p = self.payload();p['reasoning']['effort'] = 'medium'
        with self.assertRaises(ValueError):self.worker.normalize_request(p)

    def test_server_conversation_and_fabricated_tool_output_fail(self):
        p = self.payload();p['previous_response_id'] = 'foreign-response'
        with self.assertRaises(PermissionError):self.worker.normalize_request(p)
        p = self.payload();p['input'].append({'type':'function_call_output','call_id':'foreign','output':'{}'})
        with self.assertRaises(PermissionError):self.worker.normalize_request(p)

    def test_rule_tool_cannot_read_fixtures_or_personal_files(self):
        for path in ['tests/fixtures/closed-addition/nl0.json', '../../.codex/memories/MEMORY.md', '/etc/passwd']:
            result = self.worker.dispatch('read_yui', {'path': path, 'start': 1, 'end': 5})
            self.assertFalse(result['accepted'])

    def test_direct_arm_has_no_yui_reader(self):
        direct = ArtifactStage(self.root/'direct', 'EXPLICIT_TASK', phase='control', arm='direct', library=False)
        try:
            self.assertNotIn('read_yui', direct.tool_names)
            self.assertFalse(direct.dispatch('read_yui', {'path':'SKILL.md','start':1,'end':5})['accepted'])
        finally:
            import shutil
            shutil.rmtree(direct.work)

    def test_artifact_phase_label_does_not_disable_live_library_tools(self):
        worker=ArtifactStage(self.root/'library-stage','TASK',phase='initial-proof',library=True)
        try:
            self.assertEqual(worker.phase,'proof')
            self.assertEqual(worker.artifact_phase,'initial-proof')
            result=worker.dispatch('search_mathlib',{'query':'theorem dimH_empty'})
            self.assertEqual(result['exit_code'],0,result)
            self.assertIn('dimH_empty',result['matches'])
            read=worker.dispatch('read_mathlib',{'path':'Mathlib/Topology/MetricSpace/HausdorffDimension.lean',
                                                'start_line':1,'line_count':3})
            self.assertIn('lines',read)
            worker.accepted={'candidate':'done'}
            self.assertFalse(worker.dispatch('search_mathlib',{'query':'dimH_empty'})['accepted'])
        finally:
            import shutil
            shutil.rmtree(worker.work)

    def test_disabled_library_remains_unavailable(self):
        result=self.worker.dispatch('search_mathlib',{'query':'dimH_empty'})
        self.assertFalse(result['accepted'])

    def test_yui_prompt_names_the_entry_and_real_rule_paths(self):
        prompt=self.worker.prompt()
        self.assertIn('path="SKILL.md"',prompt)
        self.assertIn('references/nl0-format.md',prompt)
        self.assertIn('templates/authoring.md',prompt)
        self.assertFalse(list((self.root/'stage/harness-snapshot').rglob('SKILL.md')))

    def test_nl0_prompt_discloses_case_identity_and_all_machine_rules(self):
        import hashlib,nl0
        path=self.root/'problem.txt';path.write_text('EXPLICIT_PROBLEM')
        manifest=self.root/'nl0-inputs.json'
        manifest.write_text(json.dumps({'inputs':[{'id':'problem.txt','path':'problem.txt',
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}]}))
        worker=ArtifactStage(self.root/'nl0','TASK',phase='nl0-authoring',inputs=manifest,
                             kind='nl0',case_id='EXPLICIT_CASE',library=False)
        try:
            prompt=worker.prompt()
            self.assertIn('spec.case_id=graph.case_id="EXPLICIT_CASE"',prompt)
            for rule in nl0.RULES:self.assertIn('"'+rule+'"',prompt)
        finally:
            import shutil
            shutil.rmtree(worker.work)

    def test_task_documents_are_explicit_and_frozen(self):
        import hashlib
        path=self.root/'source.txt';path.write_text('DECLARED_SOURCE')
        manifest=self.root/'inputs.json'
        manifest.write_text(json.dumps({'inputs':[{'id':'source','path':'source.txt',
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}]}))
        worker=ArtifactStage(self.root/'with-input', 'TASK',phase='control',inputs=manifest,library=False)
        try:
            path.write_text('LATER_MUTATION')
            value=worker.dispatch('read_task_input',{'id':'source','start':1,'end':10})
            self.assertIn('DECLARED_SOURCE',value['text'])
            self.assertNotIn('LATER_MUTATION',value['text'])
            self.assertFalse(worker.dispatch('read_task_input',{'id':'other','start':1,'end':10})['accepted'])
        finally:
            import shutil
            shutil.rmtree(worker.work)

    def test_manifest_cannot_import_an_undeclared_external_path(self):
        manifest=self.root/'bad-inputs.json'
        manifest.write_text(json.dumps({'inputs':[{'id':'foreign','path':'../outside','sha256':'wrong'}]}))
        with self.assertRaises(ValueError):
            ArtifactStage(self.root/'bad-stage','TASK',phase='control',inputs=manifest)

    def test_duplicate_json_and_unsupported_gap_status_are_rejected(self):
        self.assertFalse(self.worker.dispatch('submit_artifact',{'artifact_json':'{"x":1,"x":2}'})['accepted'])
        self.assertFalse(self.worker.dispatch('report_obstacle',{'obstacle_json':json.dumps({
            'status':'THEOREM_FALSE','location':'R001','explanation':'took too long',
            'basis':'time','partial_progress':'none'})})['accepted'])

    def test_gap_report_stops_without_claiming_proof_acceptance(self):
        value=self.worker.dispatch('report_obstacle',{'obstacle_json':json.dumps({
            'status':'SUSPECTED_GAP','location':'R001','explanation':'The implication is unestablished.',
            'basis':'The supplied bound does not control the required quantity.',
            'partial_progress':'The earlier inputs remain intact.'})})
        self.assertTrue(value['stage_complete'])
        self.assertFalse(value['mathematical_acceptance'])


if __name__ == '__main__':
    unittest.main()
