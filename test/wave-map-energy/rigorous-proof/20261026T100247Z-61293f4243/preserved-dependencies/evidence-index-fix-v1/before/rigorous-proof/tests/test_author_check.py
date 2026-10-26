"""Actual same-author read/notes binding; never an independent A verdict."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from artifact_validation import NL0Contract
from acceptance import AcceptanceContract,SOURCE


class AuthorCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        fixture=Path(__file__).parent/'fixtures/closed-addition'
        self.value={'spec':json.loads((fixture/'spec.json').read_text()),'graph':json.loads((fixture/'nl0.json').read_text())}
        self.contract=NL0Contract(self.root/'case',{'problem.txt':'For a=b prove a+0=b.'})
        self.contract(self.value)

    def tearDown(self):self.temp.cleanup()

    def notes(self,number=1,**options):
        return self.contract.author_check.record(number,'Compared the complete original a=b hypothesis and a+0=b target.',
            [{'id':p['id'],'note':'The complete formula is derived by its producer.'} for p in self.value['graph']['propositions'] if p['kind'] in {'internal','target'}],
            [{'id':r['id'],'dependency_and_local_assumption_check':'Only the listed equality input is used; no L remains.',
              'source_application_check':'No imported source; only equality and fixed zero law.',
              'declaration_check':'The declared a,b and local c have their actual scopes.'} for r in self.value['graph']['inferences']],
              readiness=options.pop('readiness','no_known_issue'),open_issues=options.pop('open_issues',[]),**options)

    def inspect(self,number=1):
        for r in self.value['graph']['inferences']:self.contract.author_check.packet(number,r['id'])

    def test_conditional_view_does_not_supply_ambient_H_or_ancestor_proof(self):
        view=self.contract.author_check.packet(1,'R002')
        self.assertEqual([p['id'] for p in view['inputs']],['N001'])
        self.assertNotIn('H001',json.dumps(view))
        self.assertNotIn('propositions',view)
        self.assertNotIn('verdict',view)
        self.assertFalse(self.contract.author_check.status(1)['same_author_closing_notes_complete'])

    def test_actual_read_and_exact_note_coverage_required_no_generated_verdict(self):
        with self.assertRaisesRegex(ValueError,'read each'):self.notes()
        for r in self.value['graph']['inferences']:self.contract.author_check.packet(1,r['id'])
        with self.assertRaisesRegex(ValueError,'coverage'):
            self.contract.author_check.record(1,'Actual context comparison.',[],[],readiness='no_known_issue')
        status=self.notes()
        self.assertTrue(status['same_author_closing_notes_complete'])
        self.assertFalse(status['mathematical_acceptance'])
        self.assertTrue(status['author_release_ready'])
        notes=list(self.contract.directory.glob('author-check-*.json'))
        self.assertTrue(notes)
        self.assertFalse(any('"verdict"' in p.read_text() for p in notes))

    def test_next_actions_are_actual_own_tools_without_generated_readiness(self):
        status=self.contract.author_check.status(1)
        self.assertEqual(status['next_actions'][0],{'tool':'read_author_packet',
            'arguments':{'candidate':1,'inference':'R001'}})
        self.inspect()
        status=self.contract.author_check.status(1)
        self.assertEqual(status['next_actions'][0]['tool'],'record_author_checks')
        self.assertFalse(status['author_release_ready'])
        self.notes()
        status=self.contract.author_check.status(1)
        self.assertEqual(status['next_actions'],[{'tool':'submit_draft',
            'arguments':{'artifact':{'accept_candidate':1}}}])
        self.assertFalse(status['mathematical_acceptance'])

    def test_exact_resubmission_retains_notes_but_changed_proof_invalidates_them(self):
        for r in self.value['graph']['inferences']:self.contract.author_check.packet(1,r['id'])
        self.notes();self.contract({'accept_candidate':1})
        self.assertTrue(self.contract.author_check.status(2)['same_author_closing_notes_complete'])
        self.contract({'base_candidate':2,'patches':[{'op':'replace_text','path':'/graph/inferences/0/argument/0/text',
            'old':'Equality symmetry gives b=a.','new':'Symmetry of equality gives b=a.'}]})
        self.assertFalse(self.contract.author_check.status(3)['same_author_closing_notes_complete'])
        status=self.contract.author_check.status(3)
        self.assertEqual(status['remaining_packet_reads'],['R001'])
        self.assertEqual([r['inference'] for r in status['retained_packet_reads']],['R002'])
        self.assertFalse(status['author_release_ready'])

    def test_changed_input_statement_invalidates_the_actual_consumer_view(self):
        self.inspect()
        self.contract({'base_candidate':1,'patches':[{'op':'replace',
            'path':'/graph/propositions/@N001/statement','value':'b=a and b=a.'}]})
        self.assertEqual(self.contract.author_check.status(2)['remaining_packet_reads'],['R001','R002'])

    def test_changed_visible_logic_invalidates_every_actual_view(self):
        self.inspect()
        self.contract({'base_candidate':1,'patches':[{'op':'replace',
            'path':'/spec/logic/classical','value':True}]})
        self.assertEqual(self.contract.author_check.status(2)['remaining_packet_reads'],['R001','R002'])

    def test_same_view_read_evidence_is_immutable_and_tampering_is_rejected(self):
        check=self.contract.author_check
        self.inspect()
        paths=sorted(self.contract.directory.glob('author-packet-read-*.json'))
        before={p:p.read_bytes() for p in paths}
        self.contract({'accept_candidate':1})
        self.inspect(2)
        self.assertEqual({p:p.read_bytes() for p in paths},before)
        self.assertEqual(len(list(self.contract.directory.glob('author-packet-read-*.json'))),2)
        paths[0].write_text('{}')
        with self.assertRaisesRegex(ValueError,'read evidence changed'):check.status(2)

    def test_changed_used_definition_requires_new_view_reads(self):
        import re
        text=(Path(__file__).parents[1]/'templates/guarded-definition-example.md').read_text()
        value=json.loads(re.search(r'```json\n(.*?)\n```',text,re.S).group(1))
        contract=NL0Contract(self.root/'definition-control',{'problem.txt':'Unique witness and its equality to a.'})
        contract(value)
        for r in value['graph']['inferences']:contract.author_check.packet(1,r['id'])
        old=value['spec']['definitions'][0]['definition']
        contract({'base_candidate':1,'patches':[{'op':'replace',
            'path':'/spec/definitions/0/definition','value':old+' This specifies the predicate completely.'}]})
        self.assertEqual(contract.author_check.status(2)['remaining_packet_reads'],['R001','R002'])

    def test_other_stage_and_rejected_candidate_are_inaccessible(self):
        with self.assertRaisesRegex(ValueError,'same author stage'):self.contract.author_check.packet(2,'R001')
        second=NL0Contract(self.root/'other',{'problem.txt':'Different stage.'})
        with self.assertRaises(ValueError):second.author_check.packet(1,'R001')
        bad={'base_candidate':1,'patches':[{'op':'replace','path':'/graph/inferences','value':[]}]}
        with self.assertRaises(ValueError):self.contract(bad)
        with self.assertRaises(ValueError):self.contract.author_check.packet(2,'R001')

    def test_complete_notes_with_known_unresolved_issue_do_not_release(self):
        self.inspect()
        issue={'id':'I001','criterion':'dependency_closure','location':'/graph/inferences/0/argument/0/text',
               'note':'Author flags a possible missing equality step for actual inspection.'}
        status=self.notes(readiness='unresolved',open_issues=[issue])
        self.assertTrue(status['same_author_closing_notes_complete'])
        self.assertFalse(status['author_release_ready'])
        self.assertEqual(status['open_issues'][0]['id'],'I001')
        with self.assertRaisesRegex(ValueError,'known unresolved'):
            self.notes()
        self.assertEqual(list(self.contract.author_check.open_issues),['I001'])

    def test_known_issue_survives_edit_until_located_explicit_resolution(self):
        self.inspect()
        self.notes(readiness='unresolved',open_issues=[{'id':'I001','criterion':'dependency_closure',
            'location':'/graph/inferences/0/argument/0/text','note':'Check the equality derivation before release.'}])
        self.contract({'base_candidate':1,'patches':[{'op':'replace_text',
            'path':'/graph/inferences/0/argument/0/text','old':'Equality symmetry gives b=a.',
            'new':'The input is a=b; symmetry of equality gives b=a.'}]})
        self.inspect(2)
        with self.assertRaisesRegex(ValueError,'known unresolved'):self.notes(2)
        status=self.notes(2,resolutions=[{'id':'I001','location':'/graph/inferences/0/argument/0/text',
            'note':'The corrected sentence explicitly derives b=a from a=b by permitted equality symmetry.'}])
        self.assertTrue(status['author_release_ready'])
        self.assertEqual(status['open_issues'],[])
        self.assertEqual(self.contract.author_check.issue_history[-1]['action'],'author_reported_resolved')

    def test_unperformed_inspection_can_be_saved_but_cannot_release(self):
        status=self.contract.author_check.record(1,'Original target comparison remains unperformed.',[],[],
            readiness='not_checked',open_issues=[])
        self.assertFalse(status['same_author_closing_notes_complete'])
        self.assertFalse(status['author_release_ready'])
        self.assertEqual(status['remaining_packet_reads'],['R001','R002'])

    def test_different_authority_invalidates_readiness_and_own_packet_reads(self):
        self.inspect();self.notes()
        self.contract.author_check.acceptance=AcceptanceContract(SOURCE.read_text().replace(
            'Contract version: `'+self.contract.author_check.acceptance.version+'`.',
            'Contract version: `nl0-audit-a-test`.'))
        status=self.contract.author_check.status(1)
        self.assertFalse(status['author_release_ready'])
        self.assertFalse(status['same_author_closing_notes_complete'])
        self.assertEqual(status['remaining_packet_reads'],['R001','R002'])

    def test_issue_and_resolution_locations_are_actual_candidate_records(self):
        self.inspect()
        with self.assertRaisesRegex(ValueError,'location does not exist'):
            self.notes(readiness='unresolved',open_issues=[{'id':'I001','criterion':'dependency_closure',
                'location':'/graph/inferences/900/text','note':'A located issue is required.'}])
        self.assertEqual(self.contract.author_check.open_issues,{})
        with self.assertRaisesRegex(ValueError,'shared criterion'):
            self.notes(readiness='unresolved',open_issues=[{'id':'I001','criterion':'invented_extra_requirement',
                'location':'/graph','note':'Unknown standards are not accepted.'}])

    def test_neutral_quantified_implication_example_closes_local_antecedent(self):
        path=Path(__file__).parents[1]/'templates/quantified-implication-example.md'
        value=json.loads(path.read_text().split('```json\n',1)[1].split('\n```',1)[0])
        contract=NL0Contract(self.root/'implication',{'problem.txt':'For every real r, r=0 implies r*r=0.'})
        self.assertFalse(contract(value)['mathematical_acceptance'])
        self.assertEqual(value['spec']['hypotheses'],[])
        self.assertEqual(value['graph']['inferences'][0]['argument'][1]['discharges'],['L1'])

    def test_explicit_warm_issues_survive_a_new_author_session(self):
        from author_check import digest
        issue={'id':'I001','criterion':'dependency_closure','location':'/graph/inferences/0/argument/0/text',
            'note':'Synthetic unresolved obligation; not a mathematical verdict.'}
        handoff={'version':'yui-repair-obligations-1','baseline_input':'baseline.json',
            'baseline_content_sha256':digest(self.value),'issues':[issue]}
        documents={'baseline.json':json.dumps(self.value),'repair-obligations.json':json.dumps(handoff)}
        other=NL0Contract(self.root/'warm',documents);other(self.value)
        self.assertIn('I001',other.author_check.open_issues)
        status=other.author_check.status(1)
        self.assertFalse(status['author_release_ready']);self.assertFalse(status['mathematical_acceptance'])
        other({'accept_candidate':1})
        self.assertIn('I001',other.author_check.open_issues)

    def test_warm_handoff_rejects_undeclared_or_changed_baseline(self):
        from author_check import digest
        handoff={'version':'yui-repair-obligations-1','baseline_input':'baseline.json',
            'baseline_content_sha256':digest(self.value),'issues':[]}
        with self.assertRaisesRegex(ValueError,'explicitly declared'):
            NL0Contract(self.root/'undeclared',{'repair-obligations.json':json.dumps(handoff)})
        handoff['baseline_content_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'content hash'):
            NL0Contract(self.root/'changed-baseline',{'baseline.json':json.dumps(self.value),
                'repair-obligations.json':json.dumps(handoff)})


if __name__=='__main__':unittest.main()
