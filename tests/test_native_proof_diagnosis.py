"""Actual Codex stdio tool handoff with a deterministic local endpoint, no remote model."""
import harness_support
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import concurrency
import execution_state
import ir
import model_pilot
import proof_diagnosis
from lean_fixtures import shared_fixture, LIFT
from native_fixture import NativeFixture


@unittest.skipUnless(harness_support.native_available(),'Codex executable required')
class NativeProofDiagnosisTests(unittest.TestCase):
    def test_author_waits_for_real_nested_diagnosis_and_continues_same_native_thread(self):
        with tempfile.TemporaryDirectory(prefix='native-proof-diagnosis-') as raw:
            root=Path(raw);cp,plan=shared_fixture(root/'source')
            interface=root/'interface'
            ir.write(interface/'inputs/spec.json',{'target':'Synthetic transport fixture only.'})
            ir.write(interface/'inputs/nl0.json',ir.load(cp.parent/'source.json'))
            diagnosis={'route':'LOCAL_PROOF_REPAIR','explanation':'The failed application used an unknown name.',
                'locations':[{'document':'own-attempts.json','pointer':'/0/actual_attempt/proof'}],
                'repair_advice':'Use the permitted input with the actual conversion lemma.','comparison':None}
            def respond(f,h,n,payload):
                if n==1:code='text(await tools.check_transition('+json.dumps({'proof':'exact missing_name'})+'));'
                elif n==2:code='text(await tools.report_proof_obstruction('+json.dumps({
                    'layer':'unknown','explanation':'Unknown identifier after a failed own check.',
                    'locations':['/target'],'candidates':[{'kind':'proof','candidate':1}]})+'));'
                elif n==3:code='text(await tools.submit_draft('+json.dumps({'artifact':diagnosis})+'));'
                elif n==4:code='text(await tools.submit_transition('+json.dumps({'proof':LIFT})+'));'
                else:raise AssertionError('Unexpected extra request: '+str(n))
                f.code(h,n,code)
            with NativeFixture(root/'native',responder=respond) as f:
                f.stage.release_resources('USER_CANCELLED')
                budget=concurrency.Budget(concurrency.resolve(1),execution=f.recorder,role='proof')
                author=model_pilot.Stage(root/'author',cp,'proof',None,plan,'T001',budget=budget)
                f.stage=author
                def diagnose(s,request,out):
                    with execution_state.activate(f.recorder,'diagnostic-node'):
                        return proof_diagnosis.run_live(s,request,interface,out/'review',budget=budget)
                author.diagnose_obstruction=diagnose
                f.start();f.wait(seconds=45)
                result,accepted=f.outcomes[0]
                self.assertEqual(result['status'],'ACCEPTED',result)
                self.assertEqual(accepted,{'proof':LIFT})
                self.assertEqual(len(f.calls),4)
                self.assertFalse(f.failures);self.assertFalse(f.notifications)
                self.assertEqual(budget.report()['observed_peak_model_stages'],1)
                self.assertEqual(budget.report()['active_model_stages'],0)
                self.assertEqual(len(author.diagnosis_cache),1)
                # Both author requests after the diagnosis share the original carrier.
                events=[json.loads(s) for s in (author.logs/'events.jsonl').read_text().splitlines()]
                starts=[e for e in events if e.get('method')=='thread/started']
                self.assertEqual(len(starts),1)


if __name__=='__main__':unittest.main()
