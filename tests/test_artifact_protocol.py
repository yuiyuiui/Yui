"""Submission contracts, recovery and consumers; all judgments are synthetic."""
from copy import deepcopy
import ast
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import harness_support
import artifact_protocol as p
import audit_a_campaign as audit_a
import basis_review
from clean_stage import ArtifactStage
import interface_review
import audit_b_review
import proof_diagnosis
import basis
import audit_b
import correspondence
import artifact_validation
import payload_protocols
import translation_author
import source_preparation
import background
import dependency_instances
import proof_repair
from basis_fixtures import artifact, dependency
from review_contract import ReviewContract, ReviewProgressGuard, put
from native_fixture import NativeFixture


def row():
    return {'verdict':'UNVERIFIED','notes':'Synthetic protocol fixture, no mathematical acceptance.',
            'locations':['spec.json#/definitions/0']}


def global_case(root, count=17, selective=True):
    root.mkdir(parents=True)
    definitions=[{'id':f'D{i:03d}'} for i in range(1,count+1)]
    (root/'spec.json').write_text(json.dumps({'definitions':definitions}))
    (root/'nl0.json').write_text(json.dumps({'propositions':[]}))
    if selective:
        (root/'review-selection.json').write_text(json.dumps({
            'required_scopes':['structure',*['definition:'+d['id'] for d in definitions]]}))
    return audit_a.review_shape(root,True)


def complete(shape):
    value=deepcopy(shape.base)
    for pointer in shape.required:put(value,pointer,row())
    value['findings']=[]
    value['coverage']={key:'assessed' for key in shape.required}
    return value


class ArtifactProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)

    def tearDown(self):self.tmp.cleanup()

    def contract(self, count=17, selective=True):
        root=self.root/'global';shape=global_case(root,count,selective)
        return ReviewContract.structured(self.root/'saved',shape,
            lambda value:audit_a.validate_review(value,root,True),complete_assessment=True)

    def test_original_class_of_failure_reports_extra_fields_and_preserves_all_eighteen_rows(self):
        c=self.contract()
        for pointer in c.required:c.record(pointer,'assessed',row())
        self.assertEqual(len(c.required),18)
        before=deepcopy(c.progress())
        bad={'from_saved_review':True,'summary':{'verdict':'PASS','notes':'Extra summary','findings':[]}}
        with self.assertRaisesRegex(ValueError,r'/summary: missing=\[\], unexpected=\[.notes., .verdict.\]'):c(bad)
        self.assertEqual(c.progress(),before)
        good={'from_saved_review':True,'summary':{'findings':[]}}
        c(good)
        self.assertEqual(good['structure_review'],row())
        self.assertEqual(set(good),{'structure_review','definition_reviews','source_reviews','findings'})
        audit_a.validate_review(good,self.root/'global',True)

    def test_object_string_check_submit_all_use_the_advertised_contract(self):
        c=self.contract(count=1)
        for name in ['check_draft','submit_draft','check_artifact','submit_artifact']:
            with self.subTest(tool=name):
                stage=ArtifactStage(self.root/name,'Synthetic review.',phase='audit-a-global',library=False,validator=c)
                try:
                    advertised=next(t for t in stage.tools if t['name']=='submit_draft')['inputSchema']['properties']['artifact']
                    good=complete(c.shape);p.validate(good,advertised)
                    bad={**good,'verdict':'PASS','notes':'Extra top-level fields'}
                    with self.assertRaisesRegex(ValueError,'unexpected'):p.validate(bad,advertised)
                    def args(value):return {'artifact':value} if name.endswith('_draft') else {'artifact_json':json.dumps(value)}
                    result=stage.dispatch(name,args(bad))
                    self.assertFalse(result['accepted']);self.assertIn('notes',result['error'])
                    self.assertIn('verdict',result['error']);self.assertIsNone(stage.accepted)
                    result=stage.dispatch(name,args(good))
                    self.assertTrue(result['accepted']);self.assertEqual(result['stage_complete'],name.startswith('submit'))
                    if name.startswith('submit'):audit_a.validate_review(stage.accepted,self.root/'global',True)
                finally:shutil.rmtree(stage.work)

    def test_partial_and_complete_are_distinct_schema_alternatives(self):
        c=self.contract(count=1)
        value={'coverage':{key:'unread' for key in c.required}}
        p.validate(value,c.schema)
        with self.assertRaisesRegex(ValueError,'REVIEW_INCOMPLETE'):c(value)
        false_complete={'coverage':{key:'assessed' for key in c.required}}
        with self.assertRaises(ValueError):p.validate(false_complete,c.schema)
        c(complete(c.shape))

    def test_saved_bad_nested_fields_never_replace_valid_work(self):
        c=self.contract(count=1);pointer=c.required[0];c.record(pointer,'assessed',row())
        before=deepcopy(c.progress())
        for key,value in [('notes',False),('locations','not an array'),('verdict','assessed'),('extra',1)]:
            with self.subTest(field=key),self.assertRaisesRegex(ValueError,pointer):
                c.record(pointer,'assessed',{**row(),key:value})
            self.assertEqual(c.progress(),before)

    def test_checkpoint_tool_rejects_extra_wrapper_fields_using_its_advertised_schema(self):
        c=self.contract(count=1);stage=ArtifactStage(self.root/'checkpoint','Synthetic',phase='audit-a-global',
                                                   library=False,validator=c)
        try:
            args={'pointer':c.required[0],'coverage':'assessed','judgment':row(),'notes':'Wrong level'}
            schema=next(t for t in stage.tools if t['name']=='record_review_item')['inputSchema']
            with self.assertRaisesRegex(ValueError,'unexpected=.*notes'):p.validate(args,schema)
            rejected=stage.dispatch('record_review_item',args)
            self.assertIn('unexpected',rejected['error'])
            self.assertEqual(len(c.progress()['remaining']),len(c.required))
            del args['notes'];stage.dispatch('record_review_item',args)
            self.assertEqual(len(c.progress()['remaining']),len(c.required)-1)
        finally:shutil.rmtree(stage.work)

    def test_full_and_selective_global_fields_come_from_selected_scopes(self):
        for index,(count,selective) in enumerate([(0,True),(1,True),(7,False)]):
            root=self.root/str(index);shape=global_case(root,count,selective)
            value=complete(shape);p.validate(value,shape.schema);value.pop('coverage')
            audit_a.validate_review(value,root,True)
            self.assertEqual('target_review' in value,not selective)
            wrong={**value,'other_scope':row()}
            with self.assertRaisesRegex(ValueError,'other_scope'):audit_a.validate_review(wrong,root,True)

    def test_basis_revision_schema_requires_resolution_only_on_affected_item(self):
        shape=basis_review.review_shape(['B001','B002'],{'basis_id':'B001'})
        value={'verdict':'PASS','notes':'Synthetic','source':'Synthetic','application':'Synthetic',
               'locations':['/items/B001/statement','/items/B001/actual_type']}
        for key,resolution,valid in [('B001',False,False),('B001',True,True),('B002',False,True),('B002',True,False)]:
            args={'pointer':'/items/'+key,'coverage':'assessed','judgment':{**value,**({'resolution':'Answered'} if resolution else {})}}
            with self.subTest(key=key,resolution=resolution):
                if valid:p.validate(args,shape.record_schema())
                else:
                    with self.assertRaises(ValueError):p.validate(args,shape.record_schema())

    def test_interface_and_audit_b_share_whole_row_and_summary_boundaries(self):
        shapes=[interface_review.review_shape(),audit_b_review.review_shape({'required_review_locations':{'P':[],'E001':[]}})]
        for shape in shapes:
            value=complete(shape)
            if shape is shapes[0]:
                for key in shape.required:put(value,key,{**row(),'locations':[{'document':'spec.json','pointer':'/full_target'}]})
            p.validate(value,shape.schema)
            material={k:v for k,v in value.items() if k!='coverage'};shape.validate(material)
            for bad in [{**value,'extra':0},{**value,'findings':{}},{**value,'coverage':{}}]:
                with self.assertRaises(ValueError):p.validate(bad,shape.schema)
            self.assertEqual(set(shape.summary_schema['properties']),{'findings'})

    def test_diagnostic_routes_bind_their_comparison_shape(self):
        base={'explanation':'Synthetic','repair_advice':'Synthetic','locations':[{'document':'spec.json','pointer':'/full_target'}]}
        p.validate({**base,'route':'LOCAL_PROOF_REPAIR','comparison':None},proof_diagnosis.artifact_schema())
        for route in ['SOURCE_REVIEW_REQUIRED','INTERFACE_REPAIR_REQUIRED','INTERNAL_INTERFACE_REPAIR','unknown']:
            with self.subTest(route=route),self.assertRaises(ValueError):
                p.validate({**base,'route':route,'comparison':None},proof_diagnosis.artifact_schema())

    def test_schema_type_checks_are_total_and_do_not_coerce_boolean_integer(self):
        schema=p.obj({'count':{'type':'integer','minimum':1},'name':p.TEXT,'rows':p.array(p.TEXT,minItems=1)})
        good={'count':1,'name':'x','rows':['x']};p.validate(good,schema)
        for key,bad in [('count',True),('count',0),('name',None),('name',' '),('rows',{}),('rows',[])]:
            with self.subTest(key=key,value=bad),self.assertRaisesRegex(ValueError,'/'+key):p.validate({**good,key:bad},schema)

    def test_basis_schema_and_consumer_agree_for_categories_and_nested_errors(self):
        value=artifact(dependency('B001'),dependency('B002',2),dependency('B003',3),dependency('B004',4))
        p.validate(value,basis.artifact_schema());basis.validate(value,value['full_target'])
        for field,bad in [('category',True),('origin',[]),('uses','B001'),('lean',{'type':'True'}),('lean',None)]:
            invalid=deepcopy(value);invalid['dependencies'][0][field]=bad
            for check in [lambda v:p.validate(v,basis.artifact_schema()),lambda v:basis.validate(v,v['full_target'])]:
                with self.subTest(field=field),self.assertRaisesRegex(ValueError,'/dependencies/0/'+field):check(invalid)

    def test_valid_projection_arguments_survive_the_advertised_interface_schema(self):
        step={'id':'T002','statement':'True','inputs':['T001'],'source_steps':['R001'],
            'explanation':'Synthetic projection use','input_instances':{
                'T001':[{'levels':[],'uses':[{'args':[1],'expected':'True'}]}]}}
        p.validate(step,dependency_instances.step_schema())
        dependency_instances.validate(step,{'T001':{'universe_params':[]}})
        for invalid in [0,-1,True,None]:
            value=deepcopy(step);value['input_instances']['T001'][0]['uses'][0]['args']=[invalid]
            with self.subTest(argument=invalid),self.assertRaises(ValueError):p.validate(value,dependency_instances.step_schema())

    def test_background_notes_and_checkpoints_use_the_same_fields(self):
        note={'id':'BG001','kind':'mathematical','at':'/inference/argument/0',
            'fact':'Synthetic fact','justification':'Synthetic check',
            'grounds':[{'location':'/inputs','reason':'Synthetic input'}]}
        packet={'inference':{'argument':[{'text':'Synthetic'}]},'inputs':[]}
        p.validate(note,background.note_schema(native=False));background.validate([note],packet,self.root)
        for bad in [{**note,'extra':1},{**note,'grounds':[]},{**note,'kind':'mathlib'}]:
            for check in [lambda v:p.validate(v,background.note_schema(native=False)),
                          lambda v:background.validate([v],packet,self.root)]:
                with self.subTest(value=bad),self.assertRaises(ValueError):check(bad)

    def test_blocking_findings_advertise_required_evidence_including_nested_quotes(self):
        shape=audit_a.review_shape(self._finding_case(),True)
        schema=shape.summary_schema['properties']['findings']['items']
        good={'verdict':'FAIL','explanation':'Synthetic','locations':['spec.json#/definitions'],
              'quotation':{'location':'spec.json#/definitions','text':'Synthetic'},'owner_note':'Extensible'}
        for marker in [{'verdict':'FAIL'},{'severity':'blocking'},{'severity':'Error'}]:
            value={**{k:v for k,v in good.items() if k!='verdict'},**marker}
            p.validate(value,schema)
            del value['quotation']
            with self.assertRaisesRegex(ValueError,'quotation'):p.validate(value,schema)
        p.validate({'severity':'INFO','note':'Nonblocking context'},schema)
        c=ReviewContract.structured(self.root/'finding-progress',shape,lambda value:None)
        with self.assertRaisesRegex(ValueError,'quotation'):p.validate({'verdict':'FAIL',
            'explanation':'Synthetic','locations':['x']},c.blocker_schema())

    def _finding_case(self):
        directory=self.root/'findings';global_case(directory,count=0)
        return directory

    def test_obstruction_and_type_probe_schemas_expose_the_actual_input_variants(self):
        report={'layer':'unknown','explanation':'Synthetic','locations':['/target'],
                'candidates':[{'kind':'proof','candidate':1}]}
        p.validate(report,proof_repair.obstruction_schema())
        for bad in [{**report,'layer':'local_proof'},{**report,'layer':'source'},
                    {**report,'locations':[]},{**report,'candidates':[{'kind':'proof','candidate':True}]}]:
            with self.subTest(report=bad),self.assertRaises(ValueError):p.validate(bad,proof_repair.obstruction_schema())
        probe={'header':'import Mathlib\n','parameters':[{'name':'n','type':'Nat'}],'types':['n = n']}
        p.validate(probe,translation_author.type_probe_schema())
        probe['parameters'][0]['implicit']=True
        with self.assertRaisesRegex(ValueError,'/parameters/0:.*implicit'):p.validate(probe,translation_author.type_probe_schema())

    def test_edit_and_retained_candidate_protocol_matches_expansion(self):
        value={'spec':{'full_target':'before'},'graph':{}}
        drafts={1:json.dumps(value)}
        submissions=[{'accept_candidate':1},{'base_candidate':1,'patches':[
            {'op':'replace','path':'/spec/full_target','value':'after'}]},
            {'base_input':'input','reset_base':True,'patches':[
            {'op':'replace_text','path':'/spec/full_target','old':'before','new':'after'}]}]
        for submission in submissions:
            p.validate(submission,artifact_validation.submission_schema())
            expanded,_=artifact_validation.expand_submission(submission,{'input':json.dumps(value)},drafts)
            self.assertIn(expanded['spec']['full_target'],['before','after'])
        invalid={'base_candidate':1,'patches':[{'op':'replace','path':'/spec/full_target','text':'wrong field'}]}
        for check in [lambda v:p.validate(v,artifact_validation.submission_schema()),
                      lambda v:artifact_validation.expand_submission(v,{},drafts)]:
            with self.assertRaisesRegex(ValueError,'unexpected=.*text'):check(invalid)

    def test_mapping_schema_and_consumer_reject_the_same_unexpected_fields(self):
        contract={'premises':[]};inventory={'propositions':[{'id':'P','kind':'target'}],'scope':'whole_structured_nl0'}
        value={'version':audit_b.VERSION,'policy':correspondence.POLICY,'source_inventory_sha256':'synthetic',
               'entries':{'P':{'selector':'decl:AuditBExport.P','expected_type':'True',
                    'correspondence':{'mode':'direct','explanation':'Synthetic'}}},'library_terms':{}}
        schema=audit_b.mapping_schema(contract,inventory)
        p.validate(value,schema);audit_b.validate_mapping(contract,inventory,value)
        invalid=deepcopy(value);invalid['entries']['P']['notes']='unexpected'
        for check in [lambda v:p.validate(v,schema),lambda v:audit_b.validate_mapping(contract,inventory,v)]:
            with self.assertRaisesRegex(ValueError,'/entries/P:.*notes'):check(invalid)

    def test_interface_schema_constrains_dynamic_source_ids_and_step_fields(self):
        source={'roots':[{'id':'H001','kind':'hypothesis'},{'id':'M001','kind':'mathlib'}],
                'source_outputs':{'P':'R001'}}
        schema=translation_author.artifact_schema(source)
        value={'header':'import Mathlib\n','parameters':[],'premise_types':{'H001':'True'},
            'conclusion_type':'True','representation':'Synthetic','objects':[],
            'steps':[{'id':'T001','statement':'True','inputs':['H001'],'source_steps':['R001'],'explanation':'Synthetic'}],
            'terminal':'T001','source_outputs':{'P':'T001'},'endpoint_correspondence':{
                'P':{'mode':'direct','explanation':'Synthetic'}}}
        p.validate(value,schema)
        for key,changed in [('premise_types',{'H001':'True','E099':'True'}),('source_outputs',{'N999':'T001'})]:
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'/'+key):p.validate({**value,key:changed},schema)
        wrong=deepcopy(value);wrong['steps'][0]['input_instance']={}
        with self.assertRaisesRegex(ValueError,'/steps/0.*T001.*input_instance'):p.validate(wrong,schema)

    def test_source_no_change_and_extraction_are_separate_variants(self):
        shape=p.choice(p.obj({'status':p.literal('NO_CHANGE'),'reason':p.TEXT}),source_preparation.patch_schema())
        p.validate({'status':'NO_CHANGE','reason':'Synthetic'},shape)
        with self.assertRaisesRegex(ValueError,'reason'):p.validate({'status':'NO_CHANGE'},shape)
        with self.assertRaises(ValueError):p.validate({'status':'NO_CHANGE','reason':'Synthetic','candidates':[]},shape)

    def test_nl0_does_not_advertise_an_obstacle_its_dispatcher_rejects(self):
        nl0=payload_protocols.obstacle_schema('nl0')
        ordinary=payload_protocols.obstacle_schema('json')
        value={key:'Synthetic' for key in ordinary['required']};value['status']='SOURCE_UNAVAILABLE'
        p.validate(value,ordinary)
        with self.assertRaisesRegex(ValueError,'/status'):p.validate(value,nl0)
        value['status']='MISSING_SOURCE_STATEMENT';p.validate(value,nl0)

    def test_changing_guess_fields_cannot_bypass_no_progress_guard(self):
        c=self.contract(count=1);g=ReviewProgressGuard(c)
        for pointer in c.required:c.record(pointer,'assessed',row())
        for index in range(6):
            value={'from_saved_review':True,'summary':{'findings':[],f'guess{index}':1}}
            try:c(value)
            except ValueError as error:g.observe('check_draft',{'artifact':value},{'error':str(error)})
        self.assertEqual(g.blocked['reason'],'REVIEW_NO_PROGRESS')

    def test_production_reviews_cannot_construct_an_untyped_contract(self):
        core=Path(__file__).resolve().parents[1]
        for base in ['nl0/scripts','nl02lean/scripts']:
            for path in (core/base).glob('*.py'):
                tree=ast.parse(path.read_text())
                for node in ast.walk(tree):
                    if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='ReviewContract':
                        self.fail(f'{path.name}:{node.lineno}: use ReviewContract.structured with the authoritative shape')

    def test_native_schema_rejection_correction_and_downstream_validation(self):
        c=self.contract(count=1)
        good=complete(c.shape);bad={**good,'verdict':'PASS','notes':'Misplaced overall fields'}
        seen=[]
        def respond(f,handler,number,payload):
            seen.append(payload)
            artifact=bad if len(seen)==1 else good
            f.code(handler,number,'text(await tools.submit_draft('+json.dumps({'artifact':artifact})+'));')
        with NativeFixture(self.root/'native',responder=respond,validator=c) as f:
            f.start();f.wait(seconds=30)
            self.assertEqual(f.outcomes[0][0]['status'],'ACCEPTED')
            self.assertEqual(len(seen),2);self.assertFalse(f.notifications)
            audit_a.validate_review(f.stage.accepted,self.root/'global',True)
            calls=[json.loads(line) for line in (f.stage.logs/'tools.jsonl').read_text().splitlines()]
            rejected=next(call for call in calls if not call['result'].get('accepted'))
            self.assertIn('unexpected',rejected['result']['error'])
            self.assertIn('notes',rejected['result']['error']);self.assertIn('verdict',rejected['result']['error'])


if __name__=='__main__':unittest.main()
