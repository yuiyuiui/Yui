"""Adversarial request/tool-boundary controls; no personal context is dispatched."""
import harness_support
import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from unittest.mock import Mock, patch

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
        return {'model': __import__('run_pilot').MODEL, 'reasoning': {'effort': 'high'},
                'instructions': 'FOREIGN_INSTRUCTION_CANARY',
                'input': [{'role': 'developer', 'content': [{'type': 'input_text', 'text': 'PRIVATE_SKILL_CANARY'}]},
                          {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'FOREIGN_TASK_CANARY'}]},
                          {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'EXPLICIT_TASK'}]}],
                'tools': [{'type': 'web_search'}], 'service_tier': 'priority',
                'client_metadata': {'memory': 'PRIVATE_MEMORY_CANARY'}}









    def test_native_config_preserves_large_tool_history_without_model_call(self):
        import io,tomllib
        proc=Mock();proc.stdin=io.StringIO();proc.stdout=[];proc.pid=12345
        self.worker.execution=None
        self.worker.start_relay=Mock(return_value=12345)
        self.worker.rpc=Mock(return_value={})
        with patch.object(carrier,'system_https_proxy',return_value=None), \
                patch.object(carrier.subprocess,'Popen',return_value=proc), \
                patch('runtime_config.auth_home',return_value=self.root/'empty-auth'), \
                patch('run_resources.register_child'):
            self.worker.start_process()
        parsed=tomllib.loads((self.worker.logs/'effective-config.toml').read_text())
        self.assertEqual(parsed['tool_output_token_limit'],262144)
        self.assertEqual(parsed['model'],__import__('run_pilot').MODEL)
        self.assertEqual(parsed['model_reasoning_effort'],'high')
        self.assertEqual(parsed['project_doc_max_bytes'],0)
        self.assertFalse(parsed['features']['memories'])
        self.assertFalse(parsed['features']['shell_tool'])

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

    def test_output_protective_stops_preserve_unfinished_state_and_actual_health(self):
        from output_guard import ModelOutputLimit, ModelOutputStalled
        for i, (error_type, relay_fault) in enumerate([(ModelOutputLimit,False),
                (ModelOutputStalled,False),(ModelOutputLimit,True)]):
            worker=ArtifactStage(self.root/f'output-stop-{i}','Neutral controller test',phase='control',library=False)
            worker.execution=None
            worker.start_process=Mock()
            worker.rpc=Mock(return_value={'thread':{'id':'neutral-thread'}})
            worker.interrupt_active_turn=Mock()
            def stopped(*args):
                worker.started=time.monotonic()
                raise error_type({'request_number':1,'reason':'synthetic controller test'})
            worker.solve_turns=stopped
            if relay_fault:(worker.logs/'relay-errors.jsonl').write_text('{"error":"TLS EOF"}\n')
            with patch.object(worker,'pause_error',side_effect=__import__('execution_state').Cancelled('Synthetic user cancellation')):
                result,accepted=worker._execute()
            self.assertIsNone(accepted)
            self.assertEqual(result['status'],'CANCELLED')
            self.assertEqual(result['paused_outcome']['task_outcome'],'MODEL_OUTPUT_LIMIT' if error_type is ModelOutputLimit else 'MODEL_OUTPUT_STALLED')
            self.assertTrue(result['model_output_stop_confirmed'])
            self.assertFalse(worker.work.exists())
            self.assertFalse(result['measurement_valid'])
            self.assertEqual(result['execution_health'],'FAULT' if relay_fault else 'UNVERIFIED')
            self.assertNotIn('execution_fault',result)
            worker.interrupt_active_turn.assert_called_once()


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

    def test_structured_artifact_tools_do_not_mutate_model_call_arguments(self):
        from copy import deepcopy
        args={'artifact':{'status':'candidate','text':'A formula with "quotes" and a real\nnewline.'}}
        original=deepcopy(args)
        result=self.worker.dispatch('check_draft',args)
        self.assertTrue(result['accepted'])
        self.assertEqual(args,original)
        done=self.worker.dispatch('submit_draft',args)
        self.assertTrue(done['stage_complete'])
        self.assertEqual(self.worker.accepted,original['artifact'])

    def test_yui_prompt_names_the_entry_and_real_rule_paths(self):
        prompt=self.worker.prompt()
        self.assertIn('path="SKILL.md"',prompt)
        self.assertIn('references/nl0-format.md',prompt)
        self.assertIn('templates/authoring.md',prompt)
        self.assertFalse(list((self.root/'stage/harness-snapshot').rglob('SKILL.md')))


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

    def test_obstacle_tool_publishes_exact_direct_fields_and_actionable_rejection(self):
        tool=next(t for t in self.worker.tools if t['name']=='report_obstacle')
        expected={'status','location','explanation','basis','partial_progress'}
        self.assertEqual(set(tool['inputSchema']['properties']),expected)
        self.assertEqual(set(tool['inputSchema']['required']),expected)
        rejected=self.worker.dispatch('report_obstacle',{'claim':'An unstructured allegation.'})
        self.assertFalse(rejected['accepted'])
        self.assertIn('missing=',rejected['error']);self.assertIn('partial_progress',rejected['error'])
        self.assertIsNone(self.worker.accepted)
        value=self.worker.dispatch('report_obstacle',{'status':'SUSPECTED_GAP','location':'R001',
            'explanation':'A required implication has not been established.',
            'basis':'The supplied bound does not yield the needed quantity.',
            'partial_progress':'The actual draft is preserved.'})
        self.assertTrue(value['stage_complete']);self.assertFalse(value['mathematical_acceptance'])

    def test_unfinished_registration_does_not_create_a_report_or_mathematical_gap(self):
        value=self.worker.dispatch('report_obstacle',{'obstacle_json':json.dumps({
            'status':'TASK_INCOMPLETE','location':'source inventory',
            'explanation':'A conventional source application still needs registration.',
            'basis':'Actual draft feedback, not evidence against the theorem.',
            'partial_progress':'The source was found and the draft is retained.'})})
        self.assertFalse(value['accepted'])
        self.assertNotIn('progress_recorded',value)
        self.assertNotIn('next_action',value)
        self.assertIsNone(self.worker.accepted)

    def test_nl0_author_does_not_replace_work_with_incomplete_progress_reports(self):
        import shutil
        directory=self.root/'nl0-loop-control';directory.mkdir()
        path=directory/'problem.txt';path.write_text('Neutral explicit task.')
        import hashlib
        manifest=directory/'inputs.json';manifest.write_text(json.dumps({'inputs':[
            {'id':'problem.txt','path':'problem.txt','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}]}))
        stage=ArtifactStage(self.root/'nl0-report-stage','Neutral author control.',phase='nl0-authoring',
            library=False,kind='nl0',case_id='neutral',inputs=manifest)
        try:
            result=stage.dispatch('report_obstacle',{'obstacle_json':json.dumps({
                'status':'TASK_INCOMPLETE','location':'draft','explanation':'Not finished yet.',
                'basis':'No actual mathematical gap.','partial_progress':'A source was read.'})})
            self.assertFalse(result['accepted'])
            self.assertIn('AUTHOR_ACTION_REQUIRED',result['error'])
            self.assertIsNone(stage.accepted)
        finally:shutil.rmtree(stage.work)



if __name__ == '__main__':
    unittest.main()
