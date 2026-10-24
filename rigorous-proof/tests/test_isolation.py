"""Adversarial request/tool-boundary controls; no personal context is dispatched."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from unittest.mock import Mock, patch

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
        return {'model': __import__('run_pilot').MODEL, 'reasoning': {'effort': 'high'},
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

    def test_large_own_tool_output_is_preserved_and_clipped_json_is_rejected(self):
        value={'actual_own_packet':'A displayed mathematical sentence. '*2200}
        self.worker.tool_history['large-own-call']=value
        payload=self.payload()
        payload['input'].append({'type':'function_call_output','call_id':'large-own-call',
            'output':json.dumps(value)})
        sent=self.worker.normalize_request(payload)
        self.assertEqual(json.loads(sent['input'][-1]['output']),value)
        payload['input'][-1]['output']=json.dumps(value)[:23524]+'...truncated...'
        with self.assertRaises(json.JSONDecodeError):self.worker.normalize_request(payload)

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
            result,accepted=worker._execute()
            self.assertIsNone(accepted)
            self.assertEqual(result['status'],'UNFINISHED')
            self.assertEqual(result['task_outcome'],'MODEL_OUTPUT_LIMIT' if error_type is ModelOutputLimit else 'MODEL_OUTPUT_STALLED')
            self.assertTrue(result['model_output_stop_confirmed'])
            self.assertTrue(result['temporary_workspace_removed'])
            self.assertFalse(result['measurement_valid'])
            self.assertEqual(result['execution_health'],'FAULT' if relay_fault else 'UNVERIFIED')
            self.assertNotIn('execution_fault',result)
            worker.interrupt_active_turn.assert_called_once()

    def test_nl0_bootstrap_template_is_frozen_yui_material_and_absent_from_direct_arm(self):
        import shutil,hashlib
        problem=self.root/'neutral.txt';problem.write_text('Neutral input-boundary control, not a proof result.')
        manifest=self.root/'neutral-inputs.json'
        manifest.write_text(json.dumps({'inputs':[{'id':'problem.txt','path':problem.name,
            'sha256':hashlib.sha256(problem.read_bytes()).hexdigest()}]}))
        yui=ArtifactStage(self.root/'yui-author','TASK',phase='nl0-authoring',kind='nl0',case_id='neutral',inputs=manifest,library=False)
        direct=ArtifactStage(self.root/'direct-author','TASK',phase='nl0-authoring',kind='nl0',case_id='neutral',arm='direct',inputs=manifest,library=False)
        reviewer=ArtifactStage(self.root/'reviewer','TASK',phase='audit-a-packet-replay',library=False)
        try:
            template=(Path(__file__).parents[1]/'templates/authoring.md').read_text()
            self.assertIn(template,yui.prompt())
            self.assertNotIn(template,direct.prompt())
            self.assertNotIn('read_yui',direct.tool_names)
            authority=yui.acceptance_authority
            self.assertEqual(authority.metadata(),reviewer.acceptance_authority.metadata())
            self.assertIn(authority.instructions(),yui.system)
            self.assertIn(authority.instructions(),reviewer.system)
            self.assertNotIn(authority.instructions(),direct.system)
            self.assertIsNone(direct.acceptance_authority)
            # Actually transmit the normalized instruction set, then tamper
            # only with its archived authority. Independent readback catches it.
            yui.allowed_user_messages={'EXPLICIT_TASK'};yui.initial_user_message='EXPLICIT_TASK'
            yui.normalize_request(self.payload())
            (yui.logs/'system.txt').write_text(yui.system+'\n')
            (yui.logs/'tools.json').write_text(json.dumps(yui.tools))
            import exposure
            self.assertEqual(exposure.audit_stage(yui.logs)['status'],'TRANSMITTED-EXPOSURE-CHECK-PASSED')
            record=yui.logs/'execution-manifest.json';saved=record.read_text();metadata=json.loads(saved)
            metadata.pop('acceptance_contract');record.write_text(json.dumps(metadata))
            self.assertIn({'check':'shared_acceptance_authority_missing'},exposure.audit_stage(yui.logs)['errors'])
            record.write_text(saved)
            archived=yui.logs/'harness-snapshot/references/audit-a.md'
            archived.write_text(archived.read_text()+'\nSynthetic archival tamper.\n')
            self.assertIn({'check':'shared_acceptance_authority_binding'},exposure.audit_stage(yui.logs)['errors'])
        finally:
            shutil.rmtree(yui.work);shutil.rmtree(direct.work);shutil.rmtree(reviewer.work)

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
            self.assertIn('Conditional packet replay has a different input boundary',worker.system)
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
            selected=worker.dispatch('read_draft',{'candidate':1,'pointer':'/graph/inferences/@R001/argument/@S001/text'})
            self.assertEqual(selected['value'],value['graph']['inferences'][0]['argument'][0]['text'])
            lines=worker.dispatch('read_draft',{'candidate':1,
                'pointer':'/graph/inferences/@R001/argument/@S001/text','start_line':1,'end_line':1})
            self.assertEqual(lines['lines'][0]['line'],1)
            self.assertEqual(len(lines['text_sha256']),64)
            self.assertFalse(worker.dispatch('read_draft',{'candidate':2,
                'pointer':'/spec/conclusion','start_line':1,'end_line':1})['accepted'])
            self.assertFalse(worker.dispatch('read_draft',{'candidate':1,
                'pointer':'/spec','start_line':1,'end_line':1})['accepted'])
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
            self.assertFalse(submitted['stage_complete'])
            self.assertIsNone(worker.accepted)
            number=submitted['candidate_number']
            for r in value['graph']['inferences']:
                self.assertIn('inference',worker.dispatch('read_author_packet',{'candidate':number,'inference':r['id']}))
            closing={'candidate':number,
                'readiness':'no_known_issue','open_issues':[],
                'original_context_note':'Compared explicit a=b and a+0=b with the frozen neutral problem.',
                'output_notes':[{'id':'N001','note':'Equality symmetry proves b=a.'},{'id':'P','note':'The zero law and equality prove a+0=b.'}],
                'inference_notes':[{'id':r['id'],'dependency_and_local_assumption_check':'Only direct equality input is used.',
                    'source_application_check':'No imported theorem.',
                    'declaration_check':'Parameters/local c are in scope.'} for r in value['graph']['inferences']]}
            unfinished=dict(closing,readiness='unresolved',open_issues=[{'id':'I001',
                'criterion':'dependency_closure','location':'/graph/inferences/0/argument/0/text',
                'note':'The author has not yet checked whether symmetry supplies this step.'}])
            noted=worker.dispatch('record_author_checks',unfinished)
            self.assertTrue(noted['same_author_closing_notes_complete'],noted)
            self.assertFalse(noted['author_release_ready'])
            rejected=worker.dispatch('submit_draft',{'artifact':{'accept_candidate':number}})
            self.assertFalse(rejected['stage_complete'])
            self.assertIsNone(worker.accepted)
            closing['resolutions']=[{'id':'I001','location':'/graph/inferences/0/argument/0/text',
                'note':'Withdrawn after reading the actual input a=b and the displayed equality symmetry derivation b=a.'}]
            recorded=worker.dispatch('record_author_checks',closing)
            self.assertTrue(recorded['same_author_closing_notes_complete'],recorded)
            self.assertTrue(recorded['author_release_ready'],recorded)
            submitted=worker.dispatch('submit_draft',{'artifact':{'accept_candidate':number}})
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

    def test_nl0_output_detail_is_high_and_independently_checked_against_its_manifest(self):
        import hashlib,shutil
        from exposure import audit_stage
        directory=self.root/'verbosity-input';directory.mkdir();p=directory/'problem.txt';p.write_text('Neutral profile control.')
        manifest=directory/'inputs.json';manifest.write_text(json.dumps({'inputs':[
            {'id':'problem.txt','path':'problem.txt','sha256':hashlib.sha256(p.read_bytes()).hexdigest()}]}))
        stage=ArtifactStage(self.root/'verbosity-stage','Neutral profile control.',phase='nl0-authoring',
            kind='nl0',library=False,case_id='neutral',inputs=manifest)
        try:
            stage.allowed_user_messages={'EXPLICIT_TASK'};stage.initial_user_message='EXPLICIT_TASK'
            sent=stage.normalize_request(self.payload())
            self.assertEqual(sent['text'],{'verbosity':'high'})
            self.assertEqual(self.worker.normalize_request(self.payload())['text'],{'verbosity':'low'})
            (stage.logs/'system.txt').write_text(stage.system+'\n')
            (stage.logs/'tools.json').write_text(json.dumps(stage.tools))
            self.assertEqual(audit_stage(stage.logs)['errors'],[])  # Synthetic transmission, no model judgment.
            file=stage.logs/'execution-manifest.json';value=json.loads(file.read_text());value['output_verbosity']='low';file.write_text(json.dumps(value))
            self.assertIn('exact_output_verbosity',{row['check'] for row in audit_stage(stage.logs)['errors']})
        finally:shutil.rmtree(stage.work)


if __name__ == '__main__':
    unittest.main()
