"""Exercise private proof publication, replay and use through the real Lean parent."""
import builtins
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import symtable
import tempfile
import unittest
from unittest.mock import patch

import harness_support as support
import concurrency
import ir
import local_helpers
import model_pilot
import private_handoff as handoff
import proof_obligations as obligations
from controller_common import write


class HandoffStaticTests(unittest.TestCase):
    def test_private_delivery_has_no_unbound_global_reads(self):
        def undefined(source, filename):
            tree=symtable.symtable(source,filename,'exec')
            defined={s.get_name() for s in tree.get_symbols() if s.is_imported() or s.is_assigned() or s.is_namespace()}
            defined.update(dir(builtins));defined.update(('__file__','__name__'))
            tables=[tree];missing=set()
            while tables:
                table=tables.pop()
                missing.update(s.get_name() for s in table.get_symbols()
                               if s.is_referenced() and s.is_global() and s.get_name() not in defined)
                tables.extend(table.get_children())
            return missing
        self.assertEqual(undefined('def prepare():\n    source = 1\ndef deliver():\n    return source\n','incident'),{'source'})
        for path in (support.LEAN/'scripts/proof_obligations.py',support.LEAN/'scripts/private_handoff.py',
                     support.CORE/'workflow/blocks/private_proof_handoff.py'):
            with self.subTest(file=path.name):
                self.assertEqual(undefined(path.read_text(),str(path)),set())


class PrivateHandoffTests(unittest.TestCase):
    def setUp(self):
        storage=tempfile.TemporaryDirectory();self.addCleanup(storage.cleanup)
        self.root=Path(storage.name).resolve()
        self.budget=concurrency.Budget(concurrency.resolve(1))
        self.task={'identity':'child01','header':'import Mathlib\n','parameters':[],'premises':[],
                   'target':'True','statement':'Truth.','route':'Use True.intro.'}
        parent=handoff.read_request(handoff.issue(self.root/'context',**self.task))
        self.stage=model_pilot.Stage(self.root/'parent',parent.contract,'proof',None,parent.plan,'T001',budget=self.budget)
        self.addCleanup(shutil.rmtree,self.stage.work,True)

    def issue(self, **changes):
        options={**self.task,**changes}
        return handoff.issue(self.stage.logs/'private-proofs',**options,parent_node=self.stage.step,
                             parent_context=local_helpers.context(self.stage.cpath,self.stage.plan,self.stage.step))

    def author(self,stage):
        self.addCleanup(shutil.rmtree,stage.work,True)
        aux=stage.dispatch('check_auxiliary',{'statement':'True','proof':'exact True.intro'})
        self.assertTrue(aux['accepted'],aux)
        accepted=stage.dispatch('submit_transition',{'proof':'exact '+aux['helper']['application']})
        self.assertTrue(accepted['stage_complete'],accepted)
        report={'status':'ACCEPTED'}
        write(stage.logs/'result.json',report);write(stage.logs/'accepted.json',stage.accepted)
        return report,stage.accepted

    def test_publication_and_parent_registration_resume_without_duplicate_work(self):
        request=self.issue()
        original=handoff.publish
        class PowerLoss(BaseException):pass
        def stop_at(filename):
            def publish(path,value):
                if path.name==filename:raise PowerLoss()
                return original(path,value)
            return publish
        with patch.object(model_pilot.Stage,'execute',autospec=True,side_effect=self.author) as author, \
             patch('execution_health.require_review_execution'),patch.object(obligations,'complete_private'):
            for failed_file in ('proof.json','check.json','result-001.json'):
                with patch.object(handoff,'publish',side_effect=stop_at(failed_file)),self.assertRaises(PowerLoss):
                    obligations.deliver(request,self.budget)
            with patch.object(ir,'check',side_effect=AssertionError('already checked')),ThreadPoolExecutor(2) as pool:
                results=list(pool.map(lambda _i:obligations.deliver(request,self.budget),range(2)))
            self.assertEqual(author.call_count,1)
        result=results[0];self.assertEqual(results,[result,result])
        row,files=handoff.wire.read_result(result,request)
        self.assertEqual(row['status'],'checked')
        self.assertTrue(ir.load(files['proof'])['proof']['helpers'])
        with patch.object(handoff,'publish',side_effect=stop_at('checked.json')),self.assertRaises(PowerLoss):
            obligations.receive(self.stage,result)
        self.stage.local_helpers=[]  # Reopen the parent's persisted registry.
        with patch.object(self.stage,'dispatch',side_effect=AssertionError('duplicate parent check')):
            once=obligations.receive(self.stage,result)
            self.assertEqual(once,obligations.receive(self.stage,result))
        self.assertEqual(len(self.stage.local_helpers),1)
        receipt=ir.load(request.parent/'checked.json')
        self.assertEqual(receipt['helper'],once['helper']['name'])
        self.assertTrue(handoff.wire.resolve(request.parent,receipt['parent_check'],'parent_check').is_file())
        final=self.stage.dispatch('submit_transition',{'proof':'exact '+once['helper']['application']})
        self.assertTrue(final['stage_complete'],final)
        other=self.issue(identity='other')
        with self.assertRaisesRegex(ValueError,'request'):
            obligations.receive(self.stage,result,expected_request=other)
        with patch.object(self.stage,'step','T999'),self.assertRaisesRegex(ValueError,'parent'):
            obligations.receive(self.stage,result)
        actual=ir.load(files['check'])
        actual['native']['selected_environment']['lean_version']='foreign'
        write(files['check'],actual);row['files']['check']=handoff.wire.reference(request.parent,files['check']);write(result,row)
        with self.assertRaisesRegex(ValueError,'native check'):
            obligations.receive(self.stage,result)

    def test_ill_typed_request_returns_located_repair_before_author_start(self):
        request=self.issue(target='UnknownPrivateProposition')
        with patch.object(obligations,'start_worker',side_effect=AssertionError('ill-typed declaration')), \
             patch.object(ir,'check',wraps=ir.check) as native,ThreadPoolExecutor(2) as pool:
            result,repeated=pool.map(lambda _i:obligations.deliver(request,self.budget),range(2))
            self.assertEqual(result,repeated)
            self.assertEqual(native.call_count,1)
        received=obligations.receive(self.stage,result)
        self.assertEqual(received['status'],'needs_parent_repair')
        self.assertIn('UnknownPrivateProposition',received['required_change'])
        self.assertIn('contract',received['location'])
        self.assertEqual(self.stage.local_helpers,[])

    def test_failed_publication_keeps_numbered_error_and_reuses_native_proof(self):
        request=self.issue()
        publish=obligations.publish_result
        def fail_once(req,number,status,files):
            if status=='checked':raise OSError('synthetic publication failure')
            return publish(req,number,status,files)
        with patch.object(model_pilot.Stage,'execute',autospec=True,side_effect=self.author), \
             patch('execution_health.require_review_execution'),patch.object(obligations,'publish_result',side_effect=fail_once):
            first=obligations.deliver(request,self.budget)
        before=first.read_bytes()
        record,error=handoff.read_result(request,first)
        self.assertEqual(record['status'],'execution_error');self.assertIn('check.json',error['records'])
        with patch.object(obligations,'start_worker',side_effect=AssertionError('duplicate author')), \
             patch.object(ir,'check',side_effect=AssertionError('duplicate native check')):
            second=obligations.deliver(request,self.budget)
        self.assertEqual(first.read_bytes(),before)
        self.assertEqual(second.name,'result-002.json')
        self.assertEqual(handoff.read_result(request,second)[0]['status'],'checked')

    def test_unfinished_and_located_diagnosis_have_separate_persisted_outcomes(self):
        request=self.issue()
        def stop(stage):
            self.addCleanup(shutil.rmtree,stage.work,True)
            row={'status':'UNFINISHED','stop_reason':'DEADLINE'}
            write(stage.logs/'result.json',row);return row,None
        def repair(stage):
            self.addCleanup(shutil.rmtree,stage.work,True)
            report={'locations':['/source_steps/0'],'explanation':'Supply the missing implication.'}
            write(stage.logs/'proof-repair-request.json',report)
            row={'status':'REPAIR_REQUESTED','repair_request':report}
            write(stage.logs/'result.json',row);return row,None
        with patch.object(model_pilot.Stage,'execute',stop):
            first=obligations.deliver(request,self.budget)
        with patch.object(model_pilot.Stage,'execute',repair),patch('execution_health.record_qualification',return_value={'record_context_qualified':True}):
            second=obligations.deliver(request,self.budget)
        self.assertEqual(obligations.receive(self.stage,first)['reason'],'DEADLINE')
        detail=obligations.receive(self.stage,second)
        self.assertEqual((detail['status'],detail['location']),('needs_parent_repair','/source_steps/0'))
        self.assertEqual(self.stage.local_helpers,[])

    def test_legacy_checked_body_is_a_candidate_for_a_new_native_check(self):
        base=self.stage.logs/'private-proofs'
        task={('type' if k=='target' else k):v for k,v in self.task.items()}
        old={**task,'pins':handoff.environment()['mathlib_commit'],'evidence':[]}
        directory=base/local_helpers.digest(old);attempt=directory/'attempt-old'
        source=attempt/'source.json';complete=attempt/'complete.json'
        write(source,old);body='exact True.intro'
        write(complete,{'exit_code':0,'proof_sha256':local_helpers.digest(body)})
        from controller_common import bind
        write(directory/'checked.json',{'source':bind(source),'result':bind(complete),'proof':body})
        request=self.issue()
        with patch.object(obligations,'start_worker',side_effect=AssertionError('legacy body available')), \
             patch.object(ir,'check',wraps=ir.check) as checks:
            result=obligations.deliver(request,self.budget)
        self.assertEqual(checks.call_count,2)
        self.assertEqual(handoff.read_result(request,result)[1],body)

    def test_explicit_continuation_restores_an_unpublished_check_in_the_same_case(self):
        write(self.root/'.yui-run.json',{'root':str(self.root),'run_id':'test-owned-case'})
        item={'statement':'True','explanation':'Use True.intro.'}
        request=self.issue(identity=local_helpers.digest(item)[:16],statement=item['explanation'])
        publish=obligations.publish_result
        class PowerLoss(BaseException):pass
        def interrupt(req,number,status,files):
            if status=='checked':raise PowerLoss()
            return publish(req,number,status,files)
        with patch.object(model_pilot.Stage,'execute',autospec=True,side_effect=self.author), \
             patch('execution_health.require_review_execution'),patch.object(obligations,'publish_result',side_effect=interrupt), \
             self.assertRaises(PowerLoss):
            obligations.deliver(request,self.budget)
        current=model_pilot.Stage(self.root/'continued',self.stage.cpath,'proof',None,self.stage.plan,'T001',budget=self.budget)
        self.addCleanup(shutil.rmtree,current.work,True)
        current.previous_private_stage=self.stage.logs
        with patch.object(obligations,'start_worker',side_effect=AssertionError('proof already completed')), \
             patch.object(ir,'check',side_effect=AssertionError('child already checked')):
            accepted=current.dispatch('prove_independent_helpers',{'obligations':[item]})
        self.assertTrue(accepted['accepted'],accepted)
        final=current.dispatch('submit_transition',{'proof':'exact '+accepted['helpers'][0]['helper']['application']})
        self.assertTrue(final['stage_complete'],final)
        self.assertFalse((request.parent/'result-001.json').exists())

    def test_old_check_interrupted_before_its_delivery_receipt_can_be_reissued(self):
        base=self.stage.logs/'private-proofs'
        task={('type' if k=='target' else k):v for k,v in self.task.items()}
        old={**task,'pins':handoff.environment()['mathlib_commit'],'evidence':[]}
        attempt=base/local_helpers.digest(old)/'attempt-retained'
        source=attempt/'source.json';write(source,old)
        contract={**ir.contract(self.stage.cpath),'source':handoff.wire.reference(attempt,source)}
        write(attempt/'contract.json',contract)
        body='exact True.intro'
        write(attempt/'worker/accepted.json',{'proof':body})
        write(attempt/'complete.json',{'exit_code':0,'proof_sha256':local_helpers.digest(body)})
        request=self.issue()
        with patch.object(obligations,'start_worker',side_effect=AssertionError('old proof was saved')):
            manifest=obligations.deliver(request,self.budget)
        self.assertEqual(handoff.read_result(request,manifest)[1],body)
        self.assertFalse((attempt.parent/'checked.json').exists())
