"""Adversarial request/tool-boundary controls; no personal context is dispatched."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
import threading

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

    def test_request_identity_survives_concurrent_normalization(self):
        barrier=threading.Barrier(2);reserve=self.worker.reserve_request_number
        def interleaved():
            number=reserve();barrier.wait(timeout=2);return number
        self.worker.reserve_request_number=interleaved
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.worker.normalize_request(self.payload()),range(2)))
        rows=[json.loads(line) for line in (self.worker.logs/'requests.jsonl').read_text().splitlines()]
        self.assertEqual(sorted(row['request_number'] for row in rows),[1,2])
        self.assertEqual(len(results),2)
        lifecycle=[json.loads(line) for line in (self.worker.logs/'request-lifecycle.jsonl').read_text().splitlines()]
        self.assertEqual({row['request_number'] for row in lifecycle if row['event']=='NORMALIZED'},{1,2})

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
            fixture=Path(__file__).parent/'fixtures/closed-addition'
            value={'spec':json.loads((fixture/'spec.json').read_text()),
                   'graph':json.loads((fixture/'nl0.json').read_text())}
            value['spec']['case_id']=value['graph']['case_id']='EXPLICIT_CASE'
            checked=worker.dispatch('check_artifact',{'artifact_json':json.dumps(value)})
            self.assertTrue(checked['accepted'],checked)
            self.assertEqual(checked['candidate_number'],1)
            own=worker.dispatch('read_draft',{'candidate':1,'pointer':'/spec/conclusion'})
            self.assertEqual(own['value'],value['spec']['conclusion'])
            # Simulate native context compaction. Its opaque summary is still
            # rejected; only actual own-stage draft/check records restore state.
            worker.allowed_user_messages={'EXPLICIT_TASK'};worker.initial_user_message='EXPLICIT_TASK'
            request=self.payload();request['input'].append({'type':'message','role':'user',
                'content':[{'type':'input_text','text':'Another language model started: FOREIGN_SUMMARY_CANARY'}]})
            sent=worker.normalize_request(request)
            self.assertNotIn('FOREIGN_SUMMARY_CANARY',json.dumps(sent))
            checkpoint=json.loads((worker.logs/'requests.jsonl').read_text().splitlines()[-1])['controller_checkpoint']
            self.assertEqual(checkpoint['data']['candidate_number'],1)
            self.assertEqual(checkpoint['data']['last_structurally_valid_candidate'],1)
            self.assertEqual(sent['input'][-1]['content'][0]['text'],checkpoint['text'])
            (worker.logs/'system.txt').write_text(worker.system+'\n')
            (worker.logs/'tools.json').write_text(json.dumps(worker.tools))
            import exposure
            self.assertEqual(exposure.audit_stage(worker.logs)['status'],'TRANSMITTED-EXPOSURE-CHECK-PASSED')
            row=json.loads((worker.logs/'requests.jsonl').read_text())
            row['controller_checkpoint']['sources'][0]['sha256']='0'*64
            (worker.logs/'requests.jsonl').write_text(json.dumps(row)+'\n')
            audit=exposure.audit_stage(worker.logs)
            self.assertIn({'request':1,'check':'own_stage_checkpoint_binding'},audit['errors'])
            self.assertFalse(worker.dispatch('read_draft',{'candidate':2,'pointer':'/spec/conclusion'})['accepted'])
            self.assertFalse(worker.dispatch('read_draft',{'candidate':1,'pointer':'/../../other-stage'})['accepted'])
            submitted=worker.dispatch('submit_artifact',{'artifact_json':'{"accept_candidate":1}'})
            self.assertTrue(submitted['stage_complete'])
            self.assertFalse(worker.dispatch('read_draft',{'candidate':1,'pointer':'/spec/conclusion'})['accepted'])
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

    def test_unfinished_registration_is_nonterminal_progress_not_a_mathematical_gap(self):
        value=self.worker.dispatch('report_obstacle',{'obstacle_json':json.dumps({
            'status':'TASK_INCOMPLETE','location':'source inventory',
            'explanation':'A conventional source application still needs registration.',
            'basis':'Actual draft feedback, not evidence against the theorem.',
            'partial_progress':'The source was found and the draft is retained.'})})
        self.assertTrue(value['progress_recorded'])
        self.assertFalse(value['stage_complete'])
        self.assertIsNone(self.worker.accepted)
        self.assertIn('Continue',value['next_action'])


if __name__ == '__main__':
    unittest.main()
