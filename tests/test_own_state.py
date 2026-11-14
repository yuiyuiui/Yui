"""Synthetic controller provenance checks, never a model/mathematical pass."""
import harness_support
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from clean_stage import ArtifactStage
import own_state
import exposure
from native_carrier import MODEL
from unittest.mock import patch


class OwnStateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'problem.md').write_text('Synthetic given a=b; prove a+0=b.\n')
        manifest={'inputs':[{'id':'problem.md','path':'problem.md',
            'sha256':hashlib.sha256((self.root/'problem.md').read_bytes()).hexdigest()}]}
        (self.root/'inputs.json').write_text(json.dumps(manifest))
        fixture=Path(__file__).parent/'fixtures/closed-addition'
        self.value={'spec':json.loads((fixture/'spec.json').read_text()),
                    'graph':json.loads((fixture/'nl0.json').read_text())}
        self.worker=ArtifactStage(self.root/'stage','Synthetic controller fixture only.',
            phase='nl0-authoring',kind='nl0',inputs=self.root/'inputs.json')
        (self.worker.logs/'system.txt').write_text(self.worker.system+'\n')
        (self.worker.logs/'tools.json').write_text(json.dumps(self.worker.tools))

    def tearDown(self):
        shutil.rmtree(self.worker.work,ignore_errors=True);self.temp.cleanup()

    def draft(self):
        result=self.worker.dispatch('check_draft',{'artifact':deepcopy(self.value)})
        self.assertTrue(result['accepted']);return result['candidate_number']

    def test_author_keeps_native_queries_without_a_personal_catalog_tool_or_snapshot(self):
        self.assertIn('probe_library',self.worker.tool_names)
        self.assertNotIn('find_library_sources',self.worker.tool_names)
        manifest=json.loads((self.worker.logs/'execution-manifest.json').read_text())
        self.assertNotIn('library_catalog',manifest)
        self.assertFalse((self.worker.logs/'harness-snapshot/library').exists())
        result=self.worker.dispatch('find_library_sources',{'query':'compact'})
        self.assertFalse(result['accepted'])
        self.assertEqual(self.worker.lean_calls,0)

    def test_native_tool_io_failure_is_logged_as_execution_not_mathematical_feedback(self):
        for error in [OSError(5,'Synthetic I/O failure'),PermissionError(13,'Synthetic denied write')]:
            with patch('artifact_validation.signature_probe',side_effect=error):
                with self.assertRaises(type(error)):
                    self.worker.dispatch('probe_library',{'id':'M021','declaration':'Synthetic.source'})
            row=json.loads((self.worker.logs/'tools.jsonl').read_text().splitlines()[-1])
            self.assertEqual(row['tool'],'probe_library')
            self.assertEqual(row['result']['feedback_kind'],'tool_execution_fault')
            self.assertFalse(row['result']['accepted']);self.assertFalse(row['result']['retryable'])
            self.assertEqual(self.worker.tool_execution_fault['error_type'],type(error).__name__)

    def test_bad_source_selector_returns_feedback_and_keeps_the_author_active(self):
        result=self.worker.dispatch('probe_library',{'id':'invalid','declaration':'Synthetic.source'})
        self.assertFalse(result['accepted'])
        self.assertEqual(result['feedback_kind'],'candidate_rejected')
        self.assertIsNone(self.worker.accepted)
        self.assertFalse(hasattr(self.worker,'tool_execution_fault'))

    def test_actual_tool_failure_reaches_stage_and_case_results_without_a_model(self):
        import full_workflow
        from execution_health import StageFailure
        def failing_start():
            self.worker.dispatch('probe_library',{'id':'M021','declaration':'Synthetic.source'})
        with patch('artifact_validation.signature_probe',side_effect=OSError(5,'Synthetic storage failure')), \
             patch.object(self.worker,'start_process',side_effect=failing_start), \
             patch.object(self.worker,'pause_error',side_effect=__import__('execution_state').Cancelled('Synthetic user cancellation')):
            result,_=self.worker._execute()
        self.assertEqual(result['paused_outcome']['stop_reason'],'LOCAL_TOOL_EXECUTION_FAULT')
        self.assertEqual(result['tool_execution_fault']['tool'],'probe_library')
        self.assertIsNone(result['api_calls']);self.assertEqual(result['lean_calls'],0)
        with self.assertRaises(__import__('execution_state').Cancelled):
            full_workflow.nl0_artifact_for_audit(self.worker.logs.parent)

    def sent(self):
        value=self.worker.controller_checkpoint()
        self.latest_checkpoint=value
        return {'controller_checkpoint':value,'sent_payload':None}

    def checkpoint_errors(self):
        checkpoint=self.latest_checkpoint;records={};errors=[]
        for row in checkpoint['sources']:
            p=self.worker.logs/row['path']
            if not p.is_file() or __import__('hashlib').sha256(p.read_bytes()).hexdigest()!=row['sha256']:
                errors.append('changed source')
            elif p.suffix=='.json':records[row['path']]=json.loads(p.read_text())
        manifest=json.loads((self.worker.logs/'execution-manifest.json').read_text())
        tools=[json.loads(l) for l in (self.worker.logs/'tools.jsonl').read_text().splitlines()]
        actual={(r['tool'],own_state.digest(r['result'])):r['result'] for r in tools}
        if not own_state.verify(self.worker.logs,checkpoint['data'],records,actual,manifest):errors.append('invalid own-state binding')
        return {'errors':errors}

    def test_reset_checkpoint_has_only_real_displayed_progress_and_excludes_summary(self):
        number=self.draft();self.worker.dispatch('read_author_packet',{'candidate':number,'inference':'R001'})
        request=self.sent();state=request['controller_checkpoint']['data']['own_state']
        self.assertEqual(state['progress']['candidate'],number)
        self.assertEqual(state['progress']['remaining_packet_reads'],['R002'])
        self.assertFalse(state['progress']['author_release_ready'])
        self.assertTrue(state['progress_matches_current_candidate'])
        self.assertNotIn('FOREIGN_UNBOUND_SUMMARY',json.dumps(request['sent_payload']))
        self.assertEqual(self.checkpoint_errors()['errors'],[])

    def test_rejected_edit_preserves_latest_draft_and_labels_old_progress_stale(self):
        number=self.draft()
        result=self.worker.dispatch('check_draft',{'artifact':{'base_candidate':number,'patches':[
            {'op':'add','path':'/graph/inferences/0/argument/0/objects/-','value':'not_declared'}]}})
        self.assertFalse(result['accepted'])
        request=self.sent();data=request['controller_checkpoint']['data'];state=data['own_state']
        self.assertEqual(data['candidate_number'],number+1)
        self.assertEqual(state['progress']['candidate'],number)
        self.assertFalse(state['progress_matches_current_candidate'])
        self.assertEqual(self.checkpoint_errors()['errors'],[])

    def test_forged_progress_or_changed_snapshot_is_rejected(self):
        self.draft();request=self.sent();data=request['controller_checkpoint']['data']
        path=self.worker.logs/'case'/('own-state-'+own_state.digest(data['own_state'])+'.json')
        original=path.read_text();value=json.loads(original)
        value['progress']['author_release_ready']=True;path.write_text(json.dumps(value))
        self.assertTrue(self.checkpoint_errors()['errors'])
        path.write_text(original)
        # An apparently re-hashed snapshot still has to match an actual tool result.
        changed=deepcopy(data);changed['own_state']['progress']['author_release_ready']=True
        records={f"case/own-state-{own_state.digest(changed['own_state'])}.json":changed['own_state']}
        manifest=json.loads((self.worker.logs/'execution-manifest.json').read_text())
        tools=[json.loads(l) for l in (self.worker.logs/'tools.jsonl').read_text().splitlines()]
        actual={(r['tool'],own_state.digest(r['result'])):r['result'] for r in tools}
        self.assertFalse(own_state.verify(self.worker.logs,changed,records,actual,manifest))

    def test_immutable_earlier_checkpoint_remains_valid_after_later_progress(self):
        number=self.draft();first=self.sent()['controller_checkpoint']
        self.worker.dispatch('read_author_packet',{'candidate':number,'inference':'R001'})
        second=self.sent()['controller_checkpoint']
        self.assertNotEqual(first['data']['own_state'],second['data']['own_state'])
        self.assertEqual(self.checkpoint_errors()['errors'],[])

    def test_source_index_is_same_stage_native_metadata_not_a_new_premise(self):
        self.draft();case=self.worker.validator.directory
        directory=case/'library/M001-0001';directory.mkdir(parents=True)
        manifest=json.loads((self.worker.logs/'execution-manifest.json').read_text())
        pin=manifest['resolved_environment']['mathlib']['rev']
        # This synthetic metadata is used only to exercise provenance parsing.
        report={'probe_version':1,'exit_code':0,'mathlib_commit':pin,'sources':{'M001':{
            'declaration':'Nat.add_comm','module':'Mathlib.Algebra.Ring.Nat',
            'declaration_kind':'theorem'}}}
        path=directory/'library-sources.json';path.write_text(json.dumps(report))
        request=self.sent();state=request['controller_checkpoint']['data']['own_state']
        self.assertEqual(state['source_probe_index'][0]['declaration'],'Nat.add_comm')
        self.assertIs(state['mathematical_acceptance'],False)
        self.assertEqual(self.checkpoint_errors()['errors'],[])
        report['mathlib_commit']='wrong pin';path.write_text(json.dumps(report))
        self.assertTrue(self.checkpoint_errors()['errors'])
        with self.assertRaisesRegex(ValueError,'pin differs'):self.worker.controller_checkpoint()

    def test_policy_downgrade_and_foreign_source_paths_are_rejected(self):
        self.draft();request=self.sent();checkpoint=request['controller_checkpoint']
        checkpoint['data']['checkpoint_version']=1
        # Readback also checks the actual transmitted text/body binding.
        self.assertTrue(self.checkpoint_errors()['errors'])

    def test_an_external_probe_path_cannot_enter_an_own_snapshot(self):
        self.draft();request=self.sent();data=request['controller_checkpoint']['data']
        changed=deepcopy(data);state=changed['own_state']
        state['source_probe_index']=[{'id':'M001','declaration':'Nat.add_comm','module':'Mathlib.Data.Nat.Basic',
            'evidence':{'path':'../foreign.json','sha256':'0'*64}}]
        state['source_probe_total']=1
        records={'case/own-state-'+own_state.digest(state)+'.json':state,'../foreign.json':{'exit_code':0}}
        tools=[json.loads(l) for l in (self.worker.logs/'tools.jsonl').read_text().splitlines()]
        actual={(r['tool'],own_state.digest(r['result'])):r['result'] for r in tools}
        manifest=json.loads((self.worker.logs/'execution-manifest.json').read_text())
        self.assertFalse(own_state.verify(self.worker.logs,changed,records,actual,manifest))

    def bound_source(self):
        case=self.worker.validator.directory
        pin=json.loads((self.worker.logs/'execution-manifest.json').read_text())['resolved_environment']['mathlib']['rev']
        original=case/'library/M001-0001/library-sources.json';original.parent.mkdir(parents=True)
        row={'declaration':'Nat.add_comm','module':'Mathlib.Algebra.Ring.Nat','declaration_kind':'theorem'}
        report={'probe_version':1,'exit_code':0,'mathlib_commit':pin,'sources':{'M001':row}}
        original.write_text(json.dumps(report));sha=hashlib.sha256(original.read_bytes()).hexdigest()
        alias=case/f'library/bound-M002-{sha[:16]}/library-sources.json';alias.parent.mkdir()
        report['sources']={'M002':deepcopy(row)}
        report['metadata_reuse']={'previous_bound_source_id':'M001',
            'stage_evidence_path':str(original.relative_to(case)),'stage_evidence_sha256':sha}
        alias.write_text(json.dumps(report))
        return pin,original,alias

    def test_bound_native_alias_is_accepted_with_its_exact_same_stage_origin(self):
        self.draft();pin,original,alias=self.bound_source()
        request=self.sent();index=request['controller_checkpoint']['data']['own_state']['source_probe_index']
        self.assertEqual({x['id'] for x in index},{'M001','M002'})
        self.assertEqual(self.checkpoint_errors()['errors'],[])
        row=json.loads(alias.read_text());row['sources']['M002']['declaration']='Nat.mul_comm'
        alias.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError,'identity/content'):
            own_state.source_report(self.worker.logs,str(alias.relative_to(self.worker.logs)),pin)

    def test_bound_alias_cannot_escape_or_silently_change_its_origin(self):
        self.draft();pin,original,alias=self.bound_source()
        original.write_text(original.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'origin hash differs'):
            own_state.source_report(self.worker.logs,str(alias.relative_to(self.worker.logs)),pin)
        row=json.loads(alias.read_text());row['metadata_reuse']['stage_evidence_path']='../foreign/library-sources.json'
        alias.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError,'unsupported same-stage'):
            own_state.source_report(self.worker.logs,str(alias.relative_to(self.worker.logs)),pin)

    def test_failed_native_probe_is_not_exposed_as_a_successful_source(self):
        self.draft();pin,original,alias=self.bound_source();alias.unlink()
        row=json.loads(original.read_text());row['exit_code']=1;original.write_text(json.dumps(row))
        self.assertEqual(own_state.source_index(self.worker),( [], 0 ))


if __name__=='__main__':unittest.main()
