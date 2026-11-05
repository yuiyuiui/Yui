"""Actual case children, native loopback clients and real Lean, with scripted judgments only."""
import harness_support
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from basis_fixtures import TARGET
import execution_state
import fault_control
import ir
import jobs
import queue_controller
import target_selection


class BasisCaseBatchTests(unittest.TestCase):
    def batch(self, root, modes, prepared=None):
        selected=list(prepared or []);children=[]
        for index, mode in enumerate(modes if prepared is None else []):
            problem=root/f'case-{index}-{mode}'/'proof.md'
            problem.parent.mkdir();problem.write_text(TARGET)
            selected.append(jobs.prepare(problem,track='full',formalization='unconditional',
                profiles=harness_support.PROFILES,max_concurrency=1,time_budget_seconds=240,
                policy='first-pass' if mode=='first-pass' else 'normal',
                target=target_selection.resolve(problem,requested=TARGET)))
        routes={j['root']:mode for j,mode in zip(selected,modes)}
        def launch(job,out):
            with (out/'control.log').open('w') as log:
                child=subprocess.Popen([sys.executable,'-B',str(harness_support.TESTS/'tooling/basis_path_control.py'),
                    str(job),routes[str(out)]],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            children.append((child,execution_state.capture_process(child,private_group=True)))
            return child
        class UnexpectedPause(BaseException):pass
        def unexpected(gate,error,**kw):
            raise UnexpectedPause(f"{error}\n{(gate.root/'control.log').read_text()[-4000:]}")
        try:
            with patch.object(queue_controller,'launch_case',launch), patch.object(fault_control.Gate,'pause',unexpected):
                try: results=queue_controller.serve(selected,case_concurrency=1)
                except UnexpectedPause as error:self.fail(str(error))
            for (child,_),job in zip(children,selected):
                if child.returncode==2:self.fail('Fixture failure: '+(Path(job['root'])/'control.log').read_text()[:6000])
            self.assertEqual(len(children),len(selected))
            return [(Path(j['root']),results[j['id']]) for j in selected]
        finally:
            for child, owner in children:
                if child.poll() is None:execution_state.terminate_owned(child,owner)
                child.wait(timeout=10)

    def test_class4_stop_releases_the_batch_slot_and_preserves_the_decision(self):
        with tempfile.TemporaryDirectory() as raw:
            import case_outcomes
            from controller_common import bind,write
            cases=self.batch(Path(raw),['stop','stop'])
            for run,result in cases:
                self.assertEqual(result['status'],'STOPPED_BY_USER')
                self.assertFalse(result['completion']['acceptance_target_satisfied'])
                self.assertFalse((run/'nl0').exists())
                self.assertTrue(ir.load(run/'batch-result.json')['children_exited'])
                self.assertFalse((run/'logs/batch-errors/error-state.json').exists())
                self.assertTrue(case_outcomes.terminal(run,result))
                event=ir.load(result['user_decision']['path'])
                self.assertEqual(event['checkpoint']['semantic_review'],bind(run/'2basis/0001/review/report.json'))
                self.assertEqual([r['port'] for r in event['error']['reviewed_premises']],['E001'])
                self.assertFalse(case_outcomes.terminal(run,{'status':'STOPPED_BY_USER'}))
            (first,outcome),(other,_)=cases
            self.assertFalse(case_outcomes.terminal(other,outcome))
            path=Path(outcome['user_decision']['path'])
            saved=ir.load(path);changed={**saved,'incident':'0'*32}
            write(path,changed)
            self.assertFalse(case_outcomes.terminal(first,{**outcome,'user_decision':bind(path)}))
            write(path,saved)
            control=path.parent.parent/'error-control'/path.name
            write(control,{**ir.load(control),'action':'continue'})
            self.assertFalse(case_outcomes.terminal(first,outcome))

    def test_review_repair_and_all_positive_routes_reach_the_final_export(self):
        for mode in ('continue','accept-conditional','mismatch','evidence-repair'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as raw:
                [(run,result)]=self.batch(Path(raw),[mode])
                conditional=mode=='accept-conditional'
                self.assertEqual(result['status'],'WORKFLOW-CONDITIONAL' if conditional else 'WORKFLOW-PASSED')
                self.assertEqual(result['completion']['acceptance_target_satisfied'],not conditional)
                self.assertEqual(result['closure']['remaining_premises'],['E001','H001'] if conditional else ['H001'])
                import b2lean
                b2lean.validate_receipt(run/'b2lean')
                if mode=='evidence-repair':
                    import json
                    tools=(run/'2basis/0001/stage/tools.jsonl').read_text().splitlines()
                    replies=[e['result'] for line in tools if (e:=json.loads(line))['tool']=='submit_draft']
                    self.assertIn('misspelled.pdf',replies[0]['error'])
                    self.assertTrue(replies[-1]['stage_complete'])
                authors=sorted((run/'2basis').glob('*/stage/result.json'))
                reviewers=sorted((run/'2basis').glob('*/review/stage/result.json'))
                self.assertEqual(len(authors),2 if mode in {'continue','mismatch'} else 1)
                self.assertEqual(len(reviewers),len(authors))
                author_ids={ir.load(p)['native_thread_id'] for p in authors}
                reviewer_ids={ir.load(p)['native_thread_id'] for p in reviewers}
                self.assertEqual(len(author_ids),1)
                self.assertEqual(len(reviewer_ids),1)
                self.assertTrue(author_ids.isdisjoint(reviewer_ids))
                self.assertTrue(ir.load(run/'batch-result.json')['children_exited'])

    def test_located_late_defect_pauses_then_explicit_CLI_revises_and_rechecks(self):
        import json
        import basis_defect
        from controller_common import bind
        with tempfile.TemporaryDirectory() as raw:
            [(old,outcome)]=self.batch(Path(raw),['late'])
            self.assertEqual(outcome['status'],'CANCELLED')
            error=outcome['retained_error']
            self.assertEqual(error['status'],basis_defect.STATUS)
            self.assertFalse((old/'b2lean').exists())
            self.assertEqual(len(list((old/'nl0-to-lean').glob('*/interface-review'))),1)
            stage=Path(error['basis_defect']['path']).parent
            events=[json.loads(line) for line in (stage/'tools.jsonl').read_text().splitlines()]
            reports=[e for e in events if e['tool']==basis_defect.TOOL]
            self.assertEqual([e['result']['accepted'] for e in reports],[False,True])
            before=bind(old/'case-result.json')
            cli=harness_support.CORE/'nl0/scripts/yui.py'
            cp=subprocess.run([sys.executable,'-B',str(cli),'resume',str(old),'--repair-basis','--prepare-only'],
                              check=True,capture_output=True,text=True)
            new=Path(json.loads(cp.stdout)['runs'][0])
            job=jobs.validate(ir.load(new/'job.json'))
            self.assertLess(job['time_budget_seconds'],ir.load(old/'job.json')['time_budget_seconds'])
            self.assertFalse((new/'execution-status.json').exists())
            [(new,result)]=self.batch(Path(raw),['revised'],[job])
            self.assertEqual(result['status'],'WORKFLOW-PASSED')
            self.assertEqual(bind(old/'case-result.json'),before)
            self.assertEqual(ir.load(new/'2basis/0001/inputs/prior-basis.json'),ir.load(job['resume']['basis']['path']))
            self.assertEqual(ir.load(new/'2basis/0001/inputs/repair-findings.json')['B001'],reports[-1]['arguments'])
            self.assertTrue(list((new/'audit-a').glob('*/global/stage/result.json')))
            self.assertLessEqual(ir.load(new/'execution-status.json')['time_budget']['deadline_at_utc'],
                                 ir.load(old/'execution-status.json')['time_budget']['deadline_at_utc'])
            import b2lean
            b2lean.validate_receipt(new/'b2lean')

    def test_cancellations_deadline_and_first_pass_never_release_downstream(self):
        for mode in ('cancel-native','cancel-review','deadline-decision','first-pass'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as raw:
                [(run,result)]=self.batch(Path(raw),[mode])
                self.assertEqual(result['status'],'CANCELLED')
                self.assertFalse((run/'nl0').exists())
                self.assertFalse((run/'active-inputs').exists())
                self.assertFalse(result['completion']['acceptance_target_satisfied'])
                if mode=='deadline-decision':
                    self.assertEqual(result['retained_error']['stop_reason'],'CASE_DEADLINE')
                    event=next((run/'2basis/0001/decision/error-incidents').glob('*.json'))
                    self.assertEqual(ir.load(event)['state'],'EXPIRED')
                    with self.assertRaises(ValueError):fault_control.final_decision(run,event.stem,'continue')
                if mode=='first-pass':
                    self.assertEqual(result['retained_error']['status'],'BASIS_SEMANTIC_NONPASS')
                    self.assertFalse((run/'2basis/0002').exists())

    def test_live_local_proof_diagnosis_hands_a_basis_defect_back_to_the_case(self):
        with tempfile.TemporaryDirectory() as raw:
            [(run,result)]=self.batch(Path(raw),['late-proof'])
            self.assertEqual(result['retained_error']['status'],'BASIS_REVISION_REQUIRED')
            report=Path(result['retained_error']['basis_defect']['path'])
            self.assertIn('diagnosis-requests',report.parts)
            self.assertEqual(ir.load(report)['finding']['basis_id'],'B001')
            self.assertTrue(list((run/'nl0-to-lean').glob('*/workflow/proof-run/workers/T001/result.json')))
            self.assertFalse((run/'b2lean').exists())
            import basis_defect
            job=jobs.validate(basis_defect.prepare(run))
            self.assertIsNotNone(job['resume']['prior_proof_run'])
            [(new,revised)]=self.batch(Path(raw),['revised'],[job])
            self.assertEqual(revised['status'],'WORKFLOW-PASSED')
            recheck=next((new/'nl0-to-lean').glob('*/workflow/proof-run/reused/T001/origin.json'))
            self.assertEqual(ir.load(recheck)['previous_run'],job['resume']['prior_proof_run'])
            current=recheck.parents[2]
            self.assertFalse((current/'workers/T001').exists())
            self.assertTrue((current/'workers/T002/result.json').is_file())
            t1=next(j for j in ir.load(current/'report.json')['jobs'] if j['step']=='T001')
            self.assertEqual(t1['verification']['exit_code'],0)
            self.assertFalse(t1['worker']['model_worker_called'])
