"""Preprocessing dispatch boundaries with controlled executors, not actual reviews."""
import harness_support
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

CORE=Path(__file__).resolve().parents[1]
import source_refactor as r


class SourceRefactorDriverTests(unittest.TestCase):
    def test_a_new_proof_queue_resets_prior_completion_in_the_same_case(self):
        import scheduler
        import ir
        import execution_state
        import concurrency
        from source_fixtures import case,interface
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);graph,spec,_=case(root/'source');cp,pp,*_=interface(graph,spec,root/'typed')
            recorder=execution_state.Recorder(root/'record','neutral',concurrency.resolve(1))
            recorder.task('T002',state='LOCAL_CHECKED',role='proof',attempt_id='previous-attempt')
            def worker(sid,packet):
                if sid=='T001':
                    self.assertEqual(recorder.state['tasks']['T002']['state'],'PENDING')
                    self.assertNotEqual(recorder.state['tasks']['T002']['attempt_id'],'previous-attempt')
                return {'proof':'exact h_H001'}
            try:
                with patch.object(scheduler.ir,'check',return_value={'exit_code':0}):
                    result=scheduler.prove_graph(cp,ir.load(pp),worker,max_workers=1,out=root/'queue',execution=recorder)
                self.assertEqual(result['status'],'FRAGMENT_ASSEMBLED')
            finally:recorder.close('SYNTHETIC_RECORDING_CONTROL_ONLY')

    def test_model_extraction_identifier_cannot_escape_the_owned_directory(self):
        import copy
        from runtime_config import load_lock
        from source_fixtures import case
        with tempfile.TemporaryDirectory() as tmp:
            graph,_,patch=case(Path(tmp)/'source')
            data=json.loads(patch.read_text());data['candidates'][0]['id']='../../escape'
            with self.assertRaisesRegex(ValueError,'unsafe candidate id'):
                r.source.apply_patch(json.loads(graph.read_text()),data)

    def test_no_change_keeps_exact_authority_and_does_not_start_producer_or_cut_review(self):
        authority={'graph':'explicit-graph','spec':'explicit-spec','audit_a':'explicit-receipt'}
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'preparation'
            data=[{'current_standard_receipt_valid':True,'background_notes':{'R001':[{'fact':'large body omitted'}]}},{'source':'graph'},{'source':'spec'}]
            class ControlledStage:
                def __init__(self,logs,prompt,**kwargs):self.logs=logs;self.validator=kwargs['validator']
                def execute(self):
                    self.logs.mkdir();value={'status':'NO_CHANGE','reason':'No eligible repeated derivation.'}
                    self.validator(value);(self.logs/'accepted.json').write_text(json.dumps(value));(self.logs/'result.json').write_text('{}')
            with patch.object(r.source,'read_source',return_value=(data,[])), \
                 patch.object(r.source,'inventory',return_value={'background_supplement':{'large':'body'}}), \
                 patch.object(r,'ArtifactStage',ControlledStage),patch.object(r,'require_review_execution'), \
                 patch.object(r,'producer_reviews') as producers,patch.object(r,'cut_reviews') as cuts:
                result=r.run(authority,out,None)
            self.assertEqual(result,authority);producers.assert_not_called();cuts.assert_not_called()
            inventory=json.loads((out/'inputs/inventory.json').read_text())
            self.assertNotIn('background_supplement',inventory)
            self.assertEqual(inventory['consumers_with_background_notes'],['R001'])

    def test_unaccepted_source_cannot_begin_discovery(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(r.source,'read_source',return_value=([{'current_standard_receipt_valid':False}],[])), \
             patch.object(r,'ArtifactStage') as stage:
            with self.assertRaises(ValueError):r.run({'graph':'g','spec':'s'},Path(tmp)/'prep',None)
        stage.assert_not_called()


if __name__=='__main__':unittest.main()
