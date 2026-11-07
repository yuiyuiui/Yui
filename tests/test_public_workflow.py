"""Exercise the public Yui CLI, snapshotted case, native model carrier, real Lean and final cleanup."""
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import harness_support as support
from basis_fixtures import TARGET
import cleanup
import delivery
import frozen_graph
import nl0
from controller_common import bind


class PublicEntryTests(unittest.TestCase):
    def test_three_real_entries_from_cli_through_clean_and_standalone_readback(self):
        for track,goal,mode,scope,ids in [('nl0','conditional','direct','NL0',[]),
                ('full','conditional','direct-external','CONDITIONAL_LEAN',['P','E001']),
                ('full','unconditional','planned-conditional','CONDITIONAL_LEAN',['P','E003']),
                ('full','unconditional','planned-closed','UNCONDITIONAL_LEAN',['P'])]:
            with self.subTest(track=track,goal=goal),tempfile.TemporaryDirectory() as raw:
                base=Path(raw).resolve();problem=base/'document.md';problem.write_text(TARGET)
                out=base/'output'
                argv=['yui','run',str(problem),'--target',TARGET,'--track',track,'--formalization',goal,
                      '--use-config-profiles','--output',str(out),'--max-concurrency','1']
                program=support.TESTS/'tooling/public_entry_control.py'
                if mode=='direct-external':argv+=['--stop-after','nl0']
                command=[sys.executable,'-B',str(program),mode,*argv[1:]]
                with subprocess.Popen(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as child:
                    if mode=='direct-external':
                        import workflow_checkpoint
                        until=time.monotonic()+160
                        checkpoint=out/'stage-checkpoint.json'
                        while not checkpoint.is_file() and child.poll() is None and time.monotonic()<until:
                            time.sleep(.1)
                        if not checkpoint.is_file():
                            child.kill()
                            self.fail('No verified NL0 checkpoint: '+str(child.communicate())[-1800:])
                        row=nl0.load(checkpoint)
                        self.assertEqual(row['stage'],'nl0')
                        self.assertFalse((out/'nl0-to-lean').exists())
                        with self.assertRaisesRegex(ValueError,'current waiting'):
                            workflow_checkpoint.resume(out,'stale-id')
                        cp=subprocess.run([sys.executable,'-B',str(support.CORE/'nl0/scripts/yui.py'),
                            'resume-checkpoint',str(out),'--id',row['id']],capture_output=True,text=True)
                        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
                    stdout,stderr=child.communicate(timeout=360)
                    self.assertEqual(child.returncode,0,(stderr+stdout)[-2500:])
                user=out/'delivery'
                self.assertEqual(delivery.verify(user)['scope'],scope)
                steps=[r['node'].split('/')[-1] for r in nl0.load(out/'protocol/work/state.json')['trace']]
                self.assertEqual(steps.count('outline')+steps.count('basis-outline'),1)
                self.assertEqual(steps.count('detail'),1)
                self.assertEqual(steps.count('close'),int(goal=='unconditional'))
                self.assertEqual([r['id'] for r in nl0.load(user/delivery.STATEMENTS)['entries']],ids)
                if track=='nl0':self.assertEqual(list((user/'formalization').iterdir()),[])
                rec=nl0.load(user/'run.json')
                self.assertTrue(rec['audit_a'])
                self.assertGreater(rec['elapsed_seconds'],0)
                self.assertIsNone(rec['usage']['total'])
                self.assertEqual(rec['remaining_extra_premises'],ids[1:])
                self.assertTrue(all(b['elapsed_seconds'] is not None for b in rec['blocks']))
                if track=='nl0':
                    contents=(user/'nl0/nl0.json').read_bytes()
                    (user/'nl0/nl0.json').write_bytes(contents+b'\n')
                    with self.assertRaises(ValueError):cleanup.clean(outputs=[out],apply=True,grace=0)
                    self.assertTrue((out/'runtime').exists())
                    (user/'nl0/nl0.json').write_bytes(contents)
                    # Exercise the public builder CLI against the real completed case trace.
                    cp=subprocess.run([sys.executable,'-B',str(support.CORE/'workflow/scripts/flow.py'),'start',
                        str(base/'independent-replay'),'audit',json.dumps({'job':bind(out/'job.json')})],
                        text=True,capture_output=True,timeout=30)
                    self.assertEqual(cp.returncode,0,cp.stderr+cp.stdout)
                    self.assertEqual(json.loads(cp.stdout)['status'],'completed')
                (out/'.owned-scratch').write_text('discard')
                self.assertEqual(cleanup.clean(outputs=[out],apply=True,grace=0)['status'],'CLEANED')
                self.assertEqual({p.name for p in out.iterdir()},{'delivery'})
                self.assertTrue(problem.exists())
                releases=list((user/'nl0/review-evidence/execution').glob('*/release.json'))
                self.assertTrue(releases)
                saved=releases[0].read_bytes()
                releases[0].write_text('{}')
                with self.assertRaisesRegex(ValueError,'inventory'):delivery.verify(user)
                releases[0].write_bytes(saved)
                self.assertEqual(delivery.verify(user)['scope'],scope)
                binary=os.environ.get('YUI_TEST_COMPARATOR')
                if binary and scope in delivery.LEAN:
                    self.assertEqual(delivery.compare(user,binary)['status'],'COMPARATOR_PASSED')
                if binary and mode=='planned-closed':
                    package=base/'modified-proof'
                    shutil.copytree(user/'formalization',package)
                    for declaration in ['theorem P : True := True.intro',
                            'theorem P (a b : ℕ) (h : a=b) (extra : False) : a+0=b := extra.elim']:
                        (package/'Solution.lean').write_text('import Mathlib\nnamespace YuiClosed\n'+declaration+'\nend YuiClosed\n')
                        with self.assertRaisesRegex(ValueError,'theorem statement do not match'):
                            delivery.compare_package(package,binary)
                self.assertEqual(cleanup.clean(outputs=[out],apply=True,grace=0)['status'],'CLEANED')


class GlobalBoundaryTests(unittest.TestCase):
    def test_edges_declarations_locals_and_previous_success_remain_separate(self):
        from copy import deepcopy
        source=support.FIXTURES/'closed-addition'
        spec=nl0.load(source/'spec.json')
        graph=nl0.load(source/'nl0.json')
        outline={'spec':spec,'graph':{**graph,**frozen_graph.shape(graph)}}
        frozen_graph.check_frozen(outline,spec,graph)
        mutations=[('prop',lambda s,g:g['propositions'][-1].update(statement='True')),
                   ('edge',lambda s,g:g['inferences'][0].update(inputs=[])),
                   ('target',lambda s,g:s.update(full_target='True')),
                   ('hypotheses',lambda s,g:s.update(hypotheses=[])),
                   ('definitions',lambda s,g:s.update(definitions=[{}])),
                   ('params',lambda s,g:s.update(parameters=[]))]
        for label,change in mutations:
            with self.subTest(label=label),self.assertRaisesRegex(ValueError,'Frozen global'):
                s,g=deepcopy(spec),deepcopy(graph);change(s,g);frozen_graph.check_frozen(outline,s,g)
        graph['inferences'][0]['argument'][0]['text']='A local revision.'
        frozen_graph.check_frozen(outline,spec,graph)

    def test_attachment_claim_does_not_acknowledge_a_missing_file(self):
        import fault_control
        import jobs
        import material_exchange
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw).resolve();problem=root/'original.md';problem.write_text(TARGET)
            job=jobs.prepare(problem,track='nl0',profiles=support.PROFILES,output=root/'run')
            run=Path(job['root']);gate=fault_control.Gate(run/'nl0/local/material',stage='source-material',
                notify=lambda *_:{'status':'QUEUED'})
            material=root/'book.txt';material.write_text('A complete source statement.')
            def respond(_):
                incident=gate.state['incident']
                with self.assertRaisesRegex(ValueError,'supply-material'):
                    fault_control.resume(run,incident)
                self.assertEqual(material_exchange.supply(run,incident)['status'],'WAITING_FOR_ATTACHMENT')
                with self.assertRaisesRegex(ValueError,'actual attached file'):material_exchange.supply(run,incident,root)
                with self.assertRaises(OSError):material_exchange.supply(run,incident,root/'unavailable.pdf')
                self.assertFalse((gate.logs/'error-control'/(incident+'.json')).exists())
                self.assertEqual(material_exchange.supply(run,incident,material)['status'],'ATTACHMENT_RECEIVED')
                material_exchange.supply(run,incident,material)
                other=root/'other.txt';other.write_text('Another book')
                with self.assertRaisesRegex(ValueError,'different'):material_exchange.supply(run,incident,other)
            gate.wait=respond
            state=gate.pause({'code':'workflow_blocked','message':'Provide the cited edition'},checkpoint={'required_material':'Edition A'})
            received=material_exchange.received(gate.logs,state['incident'],state['job_binding'])
            self.assertEqual(received['original']['sha256'],bind(material)['sha256'])
            (gate.logs/'attachments'/state['incident']/received['readback']['name']).write_text('modified')
            with self.assertRaisesRegex(ValueError,'changed'):material_exchange.received(gate.logs,state['incident'],state['job_binding'])

if __name__=='__main__':unittest.main()
