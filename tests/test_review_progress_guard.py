"""Review recovery and bounded stop with a real native client and a local provider."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock

import harness_support
import basis_review
import fault_control
from native_fixture import NativeFixture
from review_contract import ReviewContract, ReviewProgressGuard
from run_pilot import Trial


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
                saved=False
                def respond(f,handler,n,payload):
                    nonlocal saved
                    if corrected and not saved:
                        saved=True
                        args={'pointer':'/items/B001','coverage':'assessed','judgment':draft()['items']['B001']}
                        f.code(handler,n,'text(await tools.record_review_item('+json.dumps(args)+'));')
                    else:
                        value={'from_saved_review':True,'summary':{}} if corrected else bad
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
                    self.assertEqual(calls,3)
                    self.assertEqual(len(f.notifications),1)
                    self.assertIn('statement_location',f.notifications[0])
                    time.sleep(.15)
                    self.assertEqual(len(f.calls),calls)
                    if recover:
                        corrected=True
                        thread=f.stage.thread_id
                        fault_control.resume(f.stage.logs,state['incident']);f.wait(seconds=25)
                        self.assertEqual(f.stage.thread_id,thread)
                        self.assertEqual(f.stage.accepted['items']['B001']['verdict'],'UNVERIFIED')
                    else:
                        (f.stage.logs/'cancel-request.json').write_text('{}')
                        f.wait(seconds=20)
                        self.assertEqual(f.outcomes[0][0]['status'],'CANCELLED')
                    self.assertEqual(len(f.notifications),1)


    def test_empty_completed_native_turns_after_a_rejection_pause_before_next_start(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);t=Trial.__new__(Trial)
            t.request_lock=threading.Lock();t.native_turn_generation=0;t.request_turns={}
            t.logs=root;t.timeout=None;t.strict=True;t.allowed_user_messages=set()
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
