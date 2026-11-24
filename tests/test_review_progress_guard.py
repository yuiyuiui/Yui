"""Review recovery and bounded stop with a real native client and a local provider."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock

import harness_support
import basis_review
from clean_stage import ArtifactStage
import fault_control
from native_fixture import NativeFixture
from review_contract import ReviewContract, ReviewProgressGuard
from native_carrier import NativeCarrier


def contract(root):
    packet={'items':{'B001':{'statement':'fixture','actual_type':'True','category':2,
                             'compatibility':'adapted','handoff':{'declaration':'YuiBasis.B001'}}}}
    def validate(value):
        return basis_review.validate_rows(value,['B001'],packet=packet)
    return ReviewContract.structured(root,basis_review.review_shape(['B001']),validate,
        row_validator=lambda p,r:basis_review.validate_judgment('B001',r,packet=packet))


def draft():
    return {'items':{'B001':{'verdict':'UNVERIFIED','notes':'Synthetic fixture.',
            'source':'Input','application':'Compare the bound proposition.',
            'classification':'Adapted foundation, category 2.','handoff':'Use the prepared YuiBasis.B001.',
            'locations':['/items/B001/'+field for field in ('statement','actual_type','category','compatibility','handoff')]}},
            'coverage':{'/items/B001':'assessed'}}


class ReviewProgressTests(unittest.TestCase):
    def test_native_interruption_restores_only_same_review_parts_and_still_requires_parent_judgment(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);hold=threading.Event()
            partial={'pointer':'/items/B001','part':'source statement','coverage':'assessed',
                'judgment':{'verdict':'UNVERIFIED','notes':'Synthetic saved source subjudgment.',
                            'locations':['/items/B001/statement']}}
            unfinished={'from_saved_review':True,'summary':{}}
            def interrupted(f,handler,n,payload):
                if n==1:
                    f.code(handler,n,'text(await tools.record_review_item('+json.dumps(partial)+'));'
                        +'text(await tools.submit_draft('+json.dumps({'artifact':unfinished})+'));')
                else:
                    hold.wait(5)
                    f.code(handler,n,'text(await tools.read_review_progress({}));')
            with NativeFixture(root/'first',validator=contract(root/'review'),responder=interrupted) as first:
                first.start();first.wait(lambda:len(first.calls)>=2 and first.stage.validator.part_sequence==1,seconds=15)
                self.assertIsNone(first.stage.accepted)
                self.assertEqual(first.stage.validator.progress()['remaining'],['/items/B001'])
                __import__('execution_state').request_cancel(first.recorder.root);hold.set()
                first.wait(seconds=10)
                self.assertEqual(first.outcomes[0][0]['status'],'CANCELLED')
            first.recorder.done.set()
            restored=contract(root/'review')
            def resumed(f,handler,n,payload):
                code='text(await tools.read_review_progress('+json.dumps({'pointer':partial['pointer'],'part':partial['part']})+'));'
                code+='text(await tools.submit_draft('+json.dumps({'artifact':unfinished})+'));'
                code+='text(await tools.record_review_item('+json.dumps({'pointer':'/items/B001','coverage':'assessed',
                    'judgment':draft()['items']['B001']})+'));'
                code+='text(await tools.submit_draft('+json.dumps({'artifact':unfinished})+'));'
                f.code(handler,n,code)
            with NativeFixture(root/'resumed',validator=restored,responder=resumed) as second:
                self.assertEqual(restored.progress()['part_count'],1)
                self.assertEqual(restored.progress()['remaining'],['/items/B001'])
                second.start();second.wait(seconds=15)
                self.assertEqual(second.outcomes[0][0]['status'],'ACCEPTED')
                self.assertEqual(second.stage.accepted['items']['B001']['verdict'],'UNVERIFIED')
                log=[json.loads(line) for line in (second.stage.logs/'tools.jsonl').read_text().splitlines()]
                self.assertEqual(log[0]['result']['item']['judgment'],partial['judgment'])
                self.assertFalse(log[1]['result']['accepted'])
                self.assertTrue(log[-1]['result']['stage_complete'])
            second.recorder.done.set()

    def test_repeated_valid_preview_across_all_encodings_stays_open_for_submission(self):
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
            self.assertIsNone(stage.accepted)
            self.assertIsNone(stage.review_guard.blocked)
            progress=stage.dispatch('read_review_progress',{})
            self.assertEqual(progress['review_feedback'],reply['review_feedback'])
            self.assertEqual(progress['remaining'],[])
            self.assertTrue(stage.dispatch('submit_artifact',{'artifact_json':json.dumps(saved)})['stage_complete'])
            self.assertEqual(stage.accepted['items'],draft()['items'])

    def test_saved_note_replacement_is_progress_and_a_repeat_only_reads_the_checkpoint(self):
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
            self.assertIsNone(g.blocked)
            self.assertEqual(g.current_feedback()['remaining'],['/items/B001'])

    def test_many_format_corrections_in_the_same_review_return_the_current_missing_items(self):
        with tempfile.TemporaryDirectory() as raw:
            guard=ReviewProgressGuard(contract(Path(raw)))
            for i in range(9):
                args={'artifact':{'observations':[{'id':'note','facts':[i]}]}}
                feedback=guard.observe('check_draft',args,{'error':'/observations/0/facts/0: expected string'})
                guard.completed_turn()
                self.assertEqual(feedback['remaining'],['/items/B001'])
                self.assertIn('Correct',feedback['next_action'])
                self.assertIsNone(guard.blocked)

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
                self.assertNotIn('pause_reason',tools[3]['review_feedback'])
                self.assertEqual(tools[4]['review_feedback']['state'],'preview_valid')
                self.assertTrue(tools[5]['stage_complete'])

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

    def test_novel_evidence_resets_the_wait_and_repeated_progress_reads_do_not(self):
        with tempfile.TemporaryDirectory() as raw:
            c=contract(Path(raw));g=ReviewProgressGuard(c)
            for n in range(10):
                g.observe('read_task_input',{'offset':n},{'text':'next page'})
                g.completed_turn()
            self.assertIsNone(g.blocked)
            g.completed_turn()
            self.assertIsNone(g.blocked)
            g.observe('read_task_input',{'offset':10},{'text':'next page'})
            g.completed_turn()
            for expected in (False,True):
                reply=g.observe('read_review_progress',{}, {'remaining':['/items/B001']})
                self.assertEqual(reply['remaining'],['/items/B001'])
                g.completed_turn()
                self.assertEqual(bool(g.blocked),expected)

    def test_native_review_waits_after_unchanged_completed_turns_and_can_resume_or_cancel(self):
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
                    elif not corrected and n%2==0:
                        f.message(handler,n,'The same draft remains incomplete.')
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
                    self.assertEqual(calls,6)
                    attempts=[json.loads(s) for s in (f.stage.logs/'tools.jsonl').read_text().splitlines()]
                    self.assertEqual([x['tool'] for x in attempts],['submit_draft']*(12 if recover else 3))
                    self.assertTrue(all('/items/B001' in x['result']['review_feedback']['remaining'] for x in attempts))
                    starts=[json.loads(s) for s in (f.stage.logs/'client.jsonl').read_text().splitlines()]
                    inputs=[row['params']['input'][0]['text'] for row in starts if row.get('method')=='turn/start']
                    self.assertEqual(len(inputs),3)
                    self.assertIn('read_review_progress',inputs[-1])
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
                        self.assertNotIn('pause_reason',json.dumps(batch))
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
                if t.api_calls>=4:t.accepted={'corrected':True}
                return {'method':'turn/completed','params':{'turn':{'id':'turn','status':'completed'}}}
            t.receive_until=receive
            paused=[]
            t.pause_error=lambda err:paused.append((t.api_calls,err['reason']))
            t.solve_turns('Synthetic review')
            self.assertEqual(paused,[(3,'REVIEW_NO_PROGRESS')])
            self.assertEqual(t.api_calls,4)
