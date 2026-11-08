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
    def test_public_package_matches_accepted_maintenance_baseline(self):
        command=str(support.CORE/'workflow/scripts/flow.py')
        result=subprocess.run([sys.executable,'-B',command,'audit','--require-baseline'],text=True,capture_output=True,timeout=90)
        audit=json.loads(result.stdout)
        self.assertTrue(audit['passed'],audit.get('checks'))
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(audit['tests']['generated_coverage']['entries'],3)
        self.assertFalse(any(audit['tests']['missing'].values()))
    def test_builder_entry_runs_a_fresh_prepared_case_exactly_once(self):
        import jobs
        with tempfile.TemporaryDirectory() as raw:
            base=Path(raw).resolve()
            problem=base/'proof.md'
            problem.write_text(TARGET)
            job=jobs.prepare(problem,track='nl0',profiles=support.PROFILES,output=base/'case',max_concurrency=1)
            run=Path(job['root'])
            bridge=support.TESTS/'tooling/public_entry_control.py'
            cmd=[sys.executable,'-B',str(bridge),'standalone-flow','start',str(base/'outer'),'audit',
                 json.dumps({'job':bind(run/'job.json')})]
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
            self.assertEqual(result.returncode,0,(result.stdout+result.stderr)[-1800:])
            self.assertEqual(json.loads(result.stdout)['status'],'completed')
            self.assertEqual(delivery.verify(run/'delivery')['scope'],'NL0')
            self.assertEqual(len(list(run.glob('global-graphs/*/stage/accepted.json'))),1)

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
                self.assertEqual(steps.count('freeze-global'),1)
                producer='basis-outline' if goal=='unconditional' else 'outline'
                self.assertLess(steps.index(producer),steps.index('freeze-global'))
                self.assertLess(steps.index('freeze-global'),steps.index('detail'))
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
                saved_report=(user/'run.json').read_bytes()
                wrong_exit='nl02lean' if rec['exit']=='b2lean' else 'b2lean'
                wrong_goal='conditional' if goal=='unconditional' else 'unconditional'
                for changes in ({'exit':wrong_exit},{'case_status':'QUEUED'},
                                {'requested_goal':wrong_goal,'entry':'2basis' if wrong_goal=='unconditional' else 'nl0'},
                                {'audit_b':'AUDIT-B-CONDITIONAL'}):
                    with self.subTest(scope=scope,changes=changes),self.assertRaises(ValueError):
                        (user/'run.json').write_text(json.dumps({**rec,**changes}))
                        delivery.verify(user)
                if scope=='NL0':
                    changed={**rec,'actual_result':'NL0_SOURCE_QUALIFIED','case_status':'DRAFT-AUDIT-CONDITIONAL'}
                    (user/'run.json').write_text(json.dumps(changed))
                    with self.assertRaisesRegex(ValueError,'source review'):delivery.verify(user)
                (user/'run.json').write_bytes(saved_report)
                binary=os.environ.get('YUI_TEST_COMPARATOR')
                if binary and scope in delivery.LEAN:
                    self.assertEqual(delivery.compare(user,binary)['status'],'COMPARATOR_PASSED')
                if mode=='planned-closed':
                    check=base/'wrong-selector'
                    shutil.copytree(user,check)
                    config=nl0.load(check/'formalization/config.json')
                    config['theorem_names']=[]
                    (check/'formalization/config.json').write_text(json.dumps(config))
                    report=nl0.load(check/'run.json')
                    report['files']=delivery.files(check)
                    (check/'run.json').write_text(json.dumps(report))
                    with self.assertRaisesRegex(ValueError,'published theorem'):delivery.verify(check)
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

    def test_explicit_clean_can_retry_a_previously_packaged_interruption(self):
        import execution_state
        import jobs
        with tempfile.TemporaryDirectory() as raw:
            base=Path(raw).resolve()
            source=base/'original.md'
            source.write_text(TARGET)
            job=jobs.prepare(source,track='nl0',profiles=support.PROFILES,output=base/'case')
            run=Path(job['root'])
            with subprocess.Popen([sys.executable,'-c','import time;time.sleep(15)']) as process:
                owner=execution_state.identity(process.pid)
                process.terminate()
            state={'schema_version':'yui-execution-1','controller':owner,'phase':'NL0_GLOBAL_FREEZE',
                'usage':{},'processes':{},'elapsed_seconds':3,'started_at_utc':'2026-01-01T00:00:00+00:00',
                'updated_at_utc':'2026-01-01T00:00:03+00:00'}
            execution_state.atomic(run/'execution-status.json',state)
            execution_state.atomic(run/'case-result.json',{'result':{'status':'CANCELLED','error':'external cancellation'}})
            anchor=delivery.partial(job)
            self.assertEqual(delivery.partial(job),anchor)
            self.assertEqual(cleanup.clean(outputs=[run],apply=True,grace=0)['status'],'CLEANED')
            self.assertEqual(delivery.verify(run/'delivery',anchor=anchor)['scope'],'INTERRUPTED')
            report=nl0.load(run/'delivery/run.json')
            self.assertEqual(report['exit'],'nl0')
            self.assertEqual(report['elapsed_seconds'],3)
            self.assertIsNone(report['usage']['total'])
            self.assertTrue(source.exists())

    def test_located_findings_return_to_the_owner_of_the_field(self):
        for pointer,basis_owner,direct_owner in [
            ('/spec/definitions/0','global','global'),('/graph/propositions/2/statement','basis','global'),
            ('/graph/propositions/1/source/reference','global','global'),('/graph/inferences/0/inputs/1','basis','global'),
            ('/graph/inferences/0/output','basis','global'),('/graph/inferences','basis','global'),
            ('/graph/inferences/0/definitions/0','global','global'),('/graph/inferences/0/argument/2','local','local')]:
            issue={'location':pointer,'criterion':'structure'}
            self.assertEqual(frozen_graph.issue_owner(issue,frozen_graph.BASIS),basis_owner)
            self.assertEqual(frozen_graph.issue_owner(issue,frozen_graph.DIRECT),direct_owner)

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
