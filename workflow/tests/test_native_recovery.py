"""Independent reconnect cases: preserve actual returns, ownership and bounded work."""
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest

SPEC=spec_from_file_location('reconnect_under_test',Path(__file__).resolve().parents[1]/'blocks/native_recovery.py')
rules=module_from_spec(SPEC);SPEC.loader.exec_module(rules)


class Recovery(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.owner=SimpleNamespace(logs=self.root,thread_id='owner-thread',execution_task='middle-worker',
            recovery_calls={},model_calls={},tool_history={})
        self.continuation='Continue the unchanged task.'
        self.receipt=self.root/'native-client.json'
        self.receipt.write_text(json.dumps({'allowed_user_message_sha256':[rules.digest(self.continuation)]}))

    def begin(self,call='batch-1',tool='investigate_basis_frontier',args=None):
        args={'obligations':[{'id':'B001','statement':'Synthetic first problem.'}]} if args is None else args
        params={'threadId':self.owner.thread_id,'turnId':'interrupted-turn',
                'callId':call,'tool':tool,'arguments':args}
        self.owner.model_calls[call]={'name':tool,'arguments':rules.text(args)}
        rules.begin_call(self.owner,params)
        with (self.root/'events.jsonl').open('a') as f:
            f.write(json.dumps({'method':'item/tool/call','params':params})+'\n')
        return params

    def complete(self,call='batch-1',result=None):
        result={'proposals':[{'id':'B001','route':'Synthetic returned route.'}]} if result is None else result
        self.owner.tool_history[call]=json.loads(rules.text(result))
        rules.complete_call(self.owner,call,rules.text(result))
        origin=self.owner.model_calls[call]
        with (self.root/'tools.jsonl').open('a') as f:
            f.write(json.dumps({'tool':origin['name'],'arguments':json.loads(origin['arguments']),'result':result})+'\n')
        with (self.root/'request-lifecycle.jsonl').open('a') as f:
            f.write(json.dumps({'event':'TOOL_RESULT_SAVED','call_id':call,'tool':origin['name'],
                'arguments_sha256':rules.digest(origin['arguments']),
                'result_sha256':rules.digest(rules.text(result)),'delivery_confirmed':False})+'\n')
        return result

    def read(self,kind='result',call='batch-1',**kwargs):
        return rules.read(self.owner,{'kind':kind,'call_id':call,
            'sha256':self.owner.recovery_calls[call][kind+'_sha256'],**kwargs})

    def test_finished_children_return_an_exact_read_entry_to_the_recovering_owner(self):
        self.begin();expected=self.complete()
        message=rules.recover(self.owner,self.continuation)
        self.assertIn('batch-1',message);self.assertIn('read_recovery_state',message)
        self.assertNotIn('Synthetic returned route.',message)
        self.assertEqual(json.loads(self.read()['text']),expected)
        self.assertIs(rules.snapshot(self.owner)['mathematical_acceptance'],False)
        self.assertTrue(rules.verify_inputs(self.root,json.loads(self.receipt.read_text())))

    def test_worker_owner_sees_only_direct_children_and_preserves_running_and_failed_states(self):
        self.owner.execution=SimpleNamespace(lock=threading.RLock(),state={'tasks':{
            'running':{'id':'running','parent_task':'middle-worker','state':'RUNNING','role':'proof'},
            'failed':{'id':'failed','parent_task':'middle-worker','state':'FAILED','role':'proof'},
            'sibling':{'id':'sibling','parent_task':'root-owner','state':'FINISHED','secret':'private'},
            'grandchild':{'id':'grandchild','parent_task':'running','state':'FINISHED'}}})
        self.begin()
        message=rules.recover(self.owner,self.continuation)
        state=rules.read(self.owner,{'kind':'index'})
        self.assertEqual({r['id']:r['state'] for r in state['children']},{'running':'RUNNING','failed':'FAILED'})
        self.assertNotIn('grandchild',message);self.assertNotIn('private',message)
        self.assertEqual(state['calls'][0]['state'],'RUNNING')
        self.assertFalse(rules.read(self.owner,{'kind':'result','call_id':'batch-1','sha256':'a'*64})['accepted'])

    def test_empty_recovery_continues_without_creating_a_snapshot(self):
        self.assertEqual(rules.recover(self.owner,self.continuation),self.continuation)
        self.assertFalse((self.root/'recovery').exists())

    def test_own_draft_without_a_new_tool_return_still_has_a_bound_recovery_input(self):
        self.owner.validator=SimpleNamespace(attempt=2)
        self.assertIn('"attempt": 2',rules.recover(self.owner,self.continuation))
        self.assertTrue(rules.verify_inputs(self.root,json.loads(self.receipt.read_text())))

    def test_a_symlink_cannot_redirect_the_owned_progress_record(self):
        self.begin();self.complete()
        with tempfile.TemporaryDirectory() as elsewhere:
            (self.root/'recovery').symlink_to(elsewhere,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'escapes its owner'):
                rules.recover(self.owner,self.continuation)
            self.assertEqual(list(Path(elsewhere).iterdir()),[])

    def test_repeated_flaps_and_heartbeats_reuse_one_index_without_reading_large_bodies(self):
        self.begin();self.complete(result={'proof':'大'*1000000})
        first=rules.recover(self.owner,self.continuation)
        class Unreadable(dict):
            def __getitem__(self,key):raise AssertionError('Recovery reread a full result')
        saved=self.owner.tool_history;self.owner.tool_history=Unreadable(saved)
        self.owner.execution=SimpleNamespace(lock=threading.RLock(),state={'tasks':{},'heartbeat':'changed'})
        for _ in range(10):self.assertEqual(rules.recover(self.owner,self.continuation),first)
        files=list((self.root/'recovery').glob('*.json'))
        self.assertEqual(len(files),1);self.assertLess(files[0].stat().st_size,2500)
        self.owner.tool_history=saved
        self.assertEqual(self.read(limit=100)['total_characters'],len(rules.text(saved['batch-1'])))

    def test_all_calls_remain_readable_after_bounded_index_pages(self):
        for i in range(40):self.begin(call=str(i));self.complete(call=str(i),result={'result':i})
        reminder=rules.snapshot(self.owner)
        self.assertEqual(len(reminder['calls']),16);self.assertEqual(reminder['call_total'],40)
        seen=[]
        for offset in (0,16,32):
            seen.extend(r['call_id'] for r in rules.read(self.owner,{'kind':'index','offset':offset})['calls'])
        self.assertEqual(seen,[str(i) for i in range(40)])
        self.assertEqual(json.loads(self.read(call='0')['text']),{'result':0})

    def test_paging_preserves_exact_unicode_and_argument_identity(self):
        args={'statement':'Synthetic statement α → β.'}
        self.begin(args=args);expected=self.complete(result={'route':'多行\n'*20})
        for kind,value in [('arguments',args),('result',expected)]:
            pieces=[];offset=0
            while offset is not None:
                page=self.read(kind,offset=offset,limit=9);pieces.append(page['text']);offset=page['next_offset']
            self.assertEqual(json.loads(''.join(pieces)),value)

    def test_bad_hash_foreign_call_paths_and_page_bounds_cannot_read_results(self):
        self.begin();self.complete()
        good={'kind':'result','call_id':'batch-1','sha256':self.owner.recovery_calls['batch-1']['result_sha256']}
        for changes in ({'call_id':'foreign'},{'sha256':'f'*64},{'path':'/private/secret'},
                {'offset':-1},{'offset':True},{'limit':0},{'limit':12001},{'offset':99999}):
            with self.subTest(changes=changes):
                self.assertFalse(rules.read(self.owner,{**good,**changes})['accepted'])
        self.owner.tool_history['batch-1']['proposals'][0]['route']='Changed'
        self.assertFalse(rules.read(self.owner,good)['accepted'])

    def test_failed_return_and_saved_progress_do_not_become_acceptance(self):
        self.owner.validator=SimpleNamespace(attempt=3,last_checked=2,last_valid_candidate=1)
        self.begin();expected=self.complete(result={'error':'A child failed.','accepted':False})
        state=rules.snapshot(self.owner)
        self.assertEqual(state['own_progress'],{'attempt':3,'last_checked':2,'last_valid_candidate':1})
        self.assertEqual(json.loads(self.read()['text']),expected)
        self.assertIs(state['mathematical_acceptance'],False)

    def test_changed_request_is_kept_distinct_and_recovery_reads_do_not_expand_the_index(self):
        self.begin(call='first',args={'id':'B001','statement':'One precise statement.'});self.complete(call='first')
        self.begin(call='second',args={'id':'B001','statement':'A different precise statement.'});self.complete(call='second')
        rows=rules.snapshot(self.owner)['calls']
        self.assertNotEqual(rows[0]['arguments_sha256'],rows[1]['arguments_sha256'])
        rules.begin_call(self.owner,{'tool':rules.TOOL,'callId':'read-1'})
        self.assertEqual(rules.snapshot(self.owner)['call_total'],2)

    def test_snapshot_tampering_and_fabricated_result_are_rejected_by_input_readback(self):
        self.begin();self.complete();rules.recover(self.owner,self.continuation)
        receipt=json.loads(self.receipt.read_text());entry=receipt['recovery_inputs'][0]
        path=self.root/entry['path'];original=path.read_text()
        path.write_text(original+' ')
        self.assertFalse(rules.verify_inputs(self.root,receipt));path.write_text(original)
        state=json.loads(original);state['calls'][0]['result_sha256']='b'*64
        content=rules.text(state);sha=rules.digest(content)
        new='recovery/progress-'+sha+'.json';(self.root/new).write_text(content)
        fake_message=rules.digest(rules.message(self.continuation,state))
        receipt['allowed_user_message_sha256'].append(fake_message)
        receipt['recovery_inputs']=[{'path':new,'sha256':sha,'continuation':self.continuation,'message_sha256':fake_message}]
        self.assertFalse(rules.verify_inputs(self.root,receipt))

    def test_same_arguments_do_not_authorize_swapping_two_actual_call_results(self):
        self.begin(call='first');self.complete(call='first',result={'route':'First return.'})
        self.begin(call='second');self.complete(call='second',result={'route':'Second return.'})
        rules.recover(self.owner,self.continuation)
        receipt=json.loads(self.receipt.read_text());entry=receipt['recovery_inputs'][0]
        state=json.loads((self.root/entry['path']).read_text())
        state['calls'][0]['result_sha256']=state['calls'][1]['result_sha256']
        content=rules.text(state);sha=rules.digest(content)
        relative='recovery/progress-'+sha+'.json';(self.root/relative).write_text(content)
        key=rules.digest(rules.message(self.continuation,state))
        receipt['allowed_user_message_sha256'].append(key)
        receipt['recovery_inputs']=[{'path':relative,'sha256':sha,'continuation':self.continuation,'message_sha256':key}]
        self.assertFalse(rules.verify_inputs(self.root,receipt))


if __name__=='__main__':unittest.main()
