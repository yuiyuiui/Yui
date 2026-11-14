"""Review recovery and bounded stop with a real native client and a local provider."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

import harness_support
import basis_review
from clean_stage import ArtifactStage
import fault_control
from execution_state import Cancelled, CaseDeadlineExceeded
from native_fixture import NativeFixture
from review_contract import ReviewContract, ReviewProgressGuard
from native_carrier import NativeEventTimeout, NativeCarrier


def contract(root):
    packet={'items':{'B001':{'statement':'fixture','actual_type':'True'}}}
    def validate(value):
        return basis_review.validate_rows(value,['B001'],packet=packet)
    return ReviewContract.structured(root,basis_review.review_shape(['B001']),validate,
        row_validator=lambda p,r:basis_review.validate_judgment('B001',r,packet=packet))


def draft():
    return {'items':{'B001':{'verdict':'UNVERIFIED','notes':'Synthetic fixture.',
            'source':'Input','application':'Compare the bound proposition.',
            'locations':['/items/B001/statement','/items/B001/actual_type']}},
            'coverage':{'/items/B001':'assessed'}}


class ReviewProgressTests(unittest.TestCase):
    def test_unchanged_valid_preview_across_all_encodings_stops_without_acceptance(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            stage=ArtifactStage(root/'stage','Test review.',phase='review',library=False,validator=contract(root/'review'))
            self.addCleanup(shutil.rmtree,stage.work)
            saved={'from_saved_review':True,'summary':{}}
            for tool,args in [('check_draft',{'artifact':draft()}),
                              ('check_artifact',{'artifact_json':json.dumps(draft())}),
                              ('check_draft',{'artifact':saved})]:
                reply=stage.dispatch(tool,args)
                self.assertTrue(reply['accepted'])
                self.assertFalse(reply['stage_complete'])
                self.assertEqual(reply['review_feedback']['state'],'preview_valid')
                self.assertIn('submit_draft',reply['review_feedback']['next_action'])
            self.assertFalse(stage.review_guard.failures)
            self.assertIsNone(stage.accepted)
            self.assertEqual(stage.review_guard.blocked['reason'],'REVIEW_NO_PROGRESS')
            stage.review_guard.resume()
            progress=stage.dispatch('read_review_progress',{})
            self.assertEqual(progress['review_feedback'],reply['review_feedback'])
            self.assertEqual(progress['remaining'],[])
            self.assertTrue(stage.dispatch('submit_artifact',{'artifact_json':json.dumps(saved)})['stage_complete'])
            self.assertEqual(stage.accepted['items'],draft()['items'])

    def test_saved_note_replacement_resets_rejections_and_same_note_retries_are_bounded(self):
        with tempfile.TemporaryDirectory() as raw:
            c=contract(Path(raw));g=ReviewProgressGuard(c)
            saved={'artifact':{'from_saved_review':True,'summary':{}}}
            for n in range(8):
                note={'id':'BG001','fact':str(n)}
                c.base['background_notes']=[note]
                reply=g.observe('record_background_note',note,{'recorded':note['id']})
                self.assertEqual(reply['state'],'checkpoint_saved')
                for _ in range(2):g.observe('submit_draft',saved,{'error':'unfinished'})
                self.assertIsNone(g.blocked)
            for _ in range(3):
                g.observe('record_background_note',note,{'recorded':note['id']})
            self.assertEqual(g.blocked['last_validation']['state'],'checkpoint_saved')

    def test_same_schema_location_in_different_singleton_probes_is_not_one_defect(self):
        with tempfile.TemporaryDirectory() as raw:
            guard=ReviewProgressGuard(contract(Path(raw)))
            error='/observations/0/facts/0: expected string, got integer'
            for i in range(8):
                args={'artifact':{'observations':[{'id':f'note-{i}','facts':[i]}]}}
                guard.observe('check_draft',args,{'error':error})
            self.assertIsNone(guard.blocked)
            for i in range(8,13):
                args={'artifact':{'observations':[{'id':'note-7','facts':[i]}]}}
                guard.observe('check_draft',args,{'error':error})
            self.assertIn('Six attempts',guard.blocked['message'])

    def test_corrected_preview_in_the_same_native_batch_can_continue_and_submit(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            bad=draft();bad['items']['B001']['extra']='misplaced'
            def respond(f,handler,n,payload):
                if n==1:
                    code=('const good='+json.dumps({'artifact':draft()})+'; text(await tools.check_draft(good)); '
                          'const bad='+json.dumps({'artifact':bad})+'; '
                          'for(let i=0;i<3;i++) await Promise.allSettled([tools.check_draft(bad)]); '
                          'text(await tools.check_draft(good));')
                else:
                    code='text(await tools.submit_draft('+json.dumps({'artifact':draft()})+'));'
                f.code(handler,n,code)
            with NativeFixture(root/'native',validator=contract(root/'review'),responder=respond) as f:
                f.start();f.wait(seconds=15)
                self.assertEqual(f.outcomes[0][0]['status'],'ACCEPTED')
                self.assertEqual(f.stage.continuation_count,0)
                self.assertEqual(len(f.calls),2)
                self.assertFalse(f.notifications)
                tools=[json.loads(s)['result'] for s in (f.stage.logs/'tools.jsonl').read_text().splitlines()]
                self.assertIn('pause_reason',tools[3]['review_feedback'])
                self.assertEqual(tools[4]['review_feedback']['state'],'preview_valid')
                self.assertTrue(tools[5]['stage_complete'])

    def test_drain_waits_for_matching_outer_or_direct_results_and_honors_stop_conditions(self):
        with tempfile.TemporaryDirectory() as raw:
            t=NativeCarrier.__new__(NativeCarrier);t.logs=Path(raw);t.active_turn_id='active';t.thread_id='thread'
            t.send=Mock(return_value=99)
            guard=ReviewProgressGuard(contract(t.logs/'review'));guard.stop('Synthetic stall')
            trigger={'method':'item/tool/call','params':{'turnId':'active','callId':'inner'}}
            def output(call_id,kind='custom_tool_call_output',turn='active'):
                return {'method':'rawResponseItem/completed','params':{'turnId':turn,'item':{'type':kind,'call_id':call_id}}}
            for outer in [True,False]:
                t.native_code_calls={'first':{'turn_id':'active'},'second':{'turn_id':'active'},
                    'done':{'turn_id':'active','output_received':True},'old':{'turn_id':'old'}} if outer else {}
                events=iter([trigger,output('done'),output('first',turn='old'),output('first'),
                             output('second') if outer else output('inner','function_call_output')])
                def receive(predicate,deadline):
                    return next(e for e in events if predicate(e))
                t.receive_until=receive
                self.assertEqual(t.wait_work_turn(guard,None)['params']['item']['call_id'],'second' if outer else 'inner')
            with patch('native_carrier.REVIEW_FEEDBACK_DRAIN_SECONDS',0):
                for exc in (CaseDeadlineExceeded('budget'),Cancelled('cancel'),TimeoutError('local tool failed')):
                    t.receive_until=Mock(side_effect=[trigger,exc])
                    with self.assertRaises(type(exc)):t.wait_work_turn(guard,time.monotonic()+20)
                t.receive_until=Mock(side_effect=[trigger,NativeEventTimeout()])
                with self.assertRaises(NativeEventTimeout):t.wait_work_turn(guard,time.monotonic())
                t.receive_until=Mock(side_effect=[trigger,NativeEventTimeout()])
                self.assertEqual(t.wait_work_turn(guard,None),trigger)
            self.assertIn('review_feedback_drain_timeout',(t.logs/'controller.jsonl').read_text())

    def test_saved_envelope_uses_new_rows_and_malformed_update_is_transactional(self):
        with tempfile.TemporaryDirectory() as raw:
            c=contract(Path(raw)); g=ReviewProgressGuard(c)
            wrapper={'artifact':{'from_saved_review':True,'summary':{}}}
            for _ in range(2):
                g.observe('submit_draft',wrapper,{'error':'unfinished'})
                g.completed_turn()
            row=draft()['items']['B001']
            original=deepcopy(row)
            c.record('/items/B001','assessed',row)
            g.observe('record_review_item',{}, {'recorded':'/items/B001','remaining':[]})
            self.assertIsNone(g.blocked)
            for key,bad in [('source',' '),('locations',['/items/B001/no']),('verdict','bad'),
                            ('statement_location','/items/B001/statement')]:
                with self.subTest(key=key),self.assertRaises(ValueError):
                    c.record('/items/B001','assessed',{**row,key:bad})
                self.assertEqual(c.items['/items/B001']['judgment'],original)
            with self.assertRaises(ValueError):
                c({'items':draft()['items'],'coverage':draft()['coverage'],'extra':1})
            c(wrapper['artifact'])
            self.assertEqual(wrapper['artifact']['items']['B001'],original)

    def test_alternation_cosmetic_keys_and_empty_turns_are_bounded(self):
        with tempfile.TemporaryDirectory() as raw:
            c=contract(Path(raw));g=ReviewProgressGuard(c)
            for n in range(5):
                d={'artifact':{'a':n%2,'b':2} if n%3 else {'b':2,'a':n%2}}
                g.observe('submit_draft',d,{'error':'bad type'})
            self.assertEqual(g.blocked['reason'],'REVIEW_NO_PROGRESS')
            g.reset()
            for n in range(6):
                g.observe('check_draft',{'artifact':{'field':n}},
                          {'error':f'/items/B001: missing=[], unexpected=[guess{n}].'})
            self.assertIsNotNone(g.blocked)
            g.reset()
            for n in range(20):
                g.observe('read_task_input',{'offset':n},{'text':'next page'})
                g.completed_turn()
            self.assertIsNone(g.blocked)
            g.observe('check_draft',{}, {'error':'missing item'})
            g.completed_turn()
            for n in range(6):
                g.observe('read_task_input',{'start':n}, {'text':'different page'})
                g.completed_turn()
            self.assertIsNone(g.blocked)
            for _ in range(3):
                g.observe('read_review_progress',{}, {'remaining':['B001']})
                g.completed_turn()
            self.assertEqual(g.empty_turns,3)
            self.assertIsNotNone(g.blocked)

    def test_native_burst_pauses_once_and_same_role_can_correct_or_cancel(self):
        for recover in [True,False]:
            with self.subTest(recover=recover),tempfile.TemporaryDirectory() as raw:
                root=Path(raw)
                bad=draft();bad['items']['B001']['statement_location']='redundant'
                corrected=False
                recovery_step=0
                def respond(f,handler,n,payload):
                    nonlocal recovery_step
                    if corrected:recovery_step+=1
                    if recovery_step==1:
                        f.code(handler,n,'text(await tools.read_review_progress({}));')
                    elif recovery_step==2:
                        args={'pointer':'/items/B001','coverage':'assessed','judgment':draft()['items']['B001']}
                        f.code(handler,n,'text(await tools.record_review_item('+json.dumps(args)+'));')
                    elif not corrected and recover:
                        f.code(handler,n,'const args='+json.dumps({'artifact':bad})+'; '
                               'text(await Promise.allSettled(Array.from({length:4}, () => tools.submit_draft(args))));')
                    elif not corrected:
                        f.tool(handler,n,'submit_draft',bad)
                    else:
                        value={'from_saved_review':True,'summary':{}}
                        f.code(handler,n,'text(await tools.submit_draft('+json.dumps({'artifact':value})+'));')
                with NativeFixture(root/'carrier',responder=respond,validator=contract(root/'review')) as f:
                    f.start()
                    path=f.stage.logs/'error-state.json'
                    f.wait(lambda:f.notifications and path.exists() and
                           json.loads(path.read_text())['state']=='PAUSED_ERROR',seconds=25)
                    state=json.loads(path.read_text());calls=len(f.calls)
                    self.assertEqual(state['error']['reason'],'REVIEW_NO_PROGRESS')
                    self.assertIn('statement_location',state['error']['last_validation']['message'])
                    self.assertTrue(state['resumable'])
                    # The native client can open its next HTTP request while its
                    # previous output acknowledgment is crossing stdio. That
                    # in-flight request cannot dispatch new work after the stop.
                    requests=1 if recover else 3
                    self.assertIn(calls,(requests,requests+1))
                    attempts=[json.loads(s) for s in (f.stage.logs/'tools.jsonl').read_text().splitlines()]
                    self.assertEqual([x['tool'] for x in attempts],['submit_draft']*(4 if recover else 3))
                    starts=[json.loads(s) for s in (f.stage.logs/'client.jsonl').read_text().splitlines()]
                    self.assertEqual(sum(s.get('method')=='turn/start' for s in starts),1)
                    self.assertEqual(len(f.notifications),1)
                    self.assertIn('statement_location',f.notifications[0])
                    self.assertNotIn('review_feedback_drain_timeout',(f.stage.logs/'controller.jsonl').read_text())
                    time.sleep(.15)
                    self.assertEqual(len(f.calls),calls)
                    if recover:
                        events=[json.loads(s) for s in (f.stage.logs/'events.jsonl').read_text().splitlines()]
                        batch=next(e['params']['item']['output'] for e in events
                                   if e.get('method')=='rawResponseItem/completed'
                                   and e['params']['item'].get('type')=='custom_tool_call_output'
                                   and e['params']['item'].get('call_id')=='call-1')
                        self.assertEqual(json.dumps(batch).count('validation_error'),4)
                        self.assertIn('pause_reason',json.dumps(batch))
                        corrected=True
                        thread=f.stage.thread_id
                        fault_control.resume(f.stage.logs,state['incident']);f.wait(seconds=25)
                        self.assertEqual(f.stage.thread_id,thread)
                        rows=[json.loads(s) for s in (f.stage.logs/'tools.jsonl').read_text().splitlines()]
                        progress=next(row['result'] for row in rows if row['tool']=='read_review_progress')
                        self.assertEqual(progress['review_feedback'],state['error']['last_validation'])
                        self.assertIn('read_review_progress',f.stage.continuation_prompt)
                        self.assertEqual(f.outcomes[0][0]['exposure']['errors'],[])
                        self.assertEqual(f.stage.accepted['items']['B001']['verdict'],'UNVERIFIED')
                    else:
                        (f.stage.logs/'cancel-request.json').write_text('{}')
                        f.wait(seconds=20)
                        self.assertEqual(f.outcomes[0][0]['status'],'CANCELLED')
                    self.assertEqual(len(f.notifications),1)


    def test_empty_completed_native_turns_after_a_rejection_pause_before_next_start(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);t=NativeCarrier.__new__(NativeCarrier)
            t.request_lock=threading.Lock();t.native_turn_generation=0;t.request_turns={}
            t.logs=root;t.timeout=None;t.allowed_user_messages=set()
            t.thread_id='retained';t.accepted=None;t.turn_results=[];t.continuation_count=0
            t.last_response_success=None;t.rpc=Mock(return_value={'turn':{'id':'turn'}})
            t.review_guard=ReviewProgressGuard(contract(root/'review'))
            def receive(predicate, deadline):
                if t.api_calls==1:t.review_guard.observe('submit_draft',{}, {'error':'bad B001'})
                if t.api_calls>4:t.accepted={'corrected':True}
                return {'method':'turn/completed','params':{'turn':{'id':'turn','status':'completed'}}}
            t.receive_until=receive
            paused=[]
            t.pause_error=lambda err:paused.append((t.api_calls,err['reason']))
            t.solve_turns('Synthetic review')
            self.assertEqual(paused,[(4,'REVIEW_NO_PROGRESS')])
            self.assertEqual(t.api_calls,5)
