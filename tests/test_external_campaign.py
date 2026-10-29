"""External-source staging/coverage controls using an explicitly synthetic text."""
import harness_support

from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import audit_a_campaign as a


class ExternalCampaignTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.case=self.root/'case';shutil.copytree(a.CORE/'tests/fixtures/closed-addition',self.case)
        text=self.case/'primary.txt';text.write_text('SYNTHETIC CONTROL ONLY. This is not an authoritative publication or theorem.\n')
        evidence=[{'path':'primary.txt','sha256':a.bind(text)['sha256']}]
        graph=a.nl0.load(self.case/'nl0.json')
        source={key:'SYNTHETIC control; no real publication claim.' for key in [
            'author','title','version','identifier','locator','notation_map','errata','source_kind','origin',
            'retrieved_at','source_statement','context','qualification','version_check']}
        source.update(statement='For a and b, a=b implies a=b.',hypotheses=['a=b.'],evidence=evidence,primary_evidence=evidence)
        graph['propositions'].insert(1,{'id':'E001','kind':'external','statement':source['statement'],
            'definitions':[],'binders':[],'objects':['a','b'],'source':source})
        r=graph['inferences'][0];r['inputs']=['H001','E001'];r['argument'][0]['uses']=['H001','E001']
        r['argument'][0]['text']='Apply E001 to H001, obtaining a=b; equality symmetry gives b=a.'
        r['applications']=[{'id':'A001','input':'E001','at':'S001','bindings':'Use the global a and b.',
                            'hypothesis_checks':['H001 supplies a=b.']}]
        a.write(self.case/'nl0.json',graph)
        self.out=self.root/'audit';self.plan=a.prepare(self.case,self.root,self.out)

    def tearDown(self):self.tmp.cleanup()

    def row(self,verdict='UNVERIFIED'):
        return {'verdict':verdict,'notes':'Synthetic source is not an authoritative publication.','locations':['/inference/argument']}

    def test_primary_bytes_are_explicit_inputs_without_browser_or_personal_files(self):
        evidence=a.nl0.load(self.out/'global/external-source-evidence.json')['E001']
        doc=evidence['documents'][0]
        self.assertTrue(doc['primary']);self.assertEqual(doc['readback_kind'],'EXACT_UTF8_BYTES')
        self.assertEqual((self.out/'global'/doc['readback']).read_bytes(),(self.case/'primary.txt').read_bytes())
        ids={r['id'] for r in a.nl0.load(self.out/'R001/inputs.json')['inputs']}
        self.assertEqual(ids,{'packet.json'})

    def test_external_citation_criteria_cannot_be_merged_or_skipped_as_pass(self):
        source={**self.row(),'citation_checks':{key:self.row() for key in a.nl0.EXTERNAL_CHECKS}}
        value={'target_review':self.row(),'structure_review':self.row(),'definition_reviews':{},'source_reviews':{'E001':source},'findings':[]}
        a.validate_review(value,self.out/'global',True)
        source['verdict']='PASS'
        with self.assertRaisesRegex(ValueError,'conflicts'):a.validate_review(value,self.out/'global',True)
        source['verdict']='UNVERIFIED';source['citation_checks'].pop('literature_identity')
        with self.assertRaisesRegex(ValueError,'criterion'):a.validate_review(value,self.out/'global',True)

    def test_pdf_readback_uses_fallback_instead_of_treating_ascii_pdf_as_prose(self):
        import source_staging
        pdf=self.case/'primary.pdf';pdf.write_bytes(b'%PDF-1.7\nsynthetic input for a controlled converter')
        evidence={'path':pdf.name,'sha256':a.bind(pdf)['sha256']}
        proposition={'id':'E001','source':{'evidence':[evidence],'primary_evidence':[evidence]}}
        with patch.object(source_staging.shutil,'which',return_value=None),patch('target_selection.text',return_value='Actual converter readback.'):
            staged=source_staging.stage_external(self.case,proposition,self.out)
        document=staged['documents'][0]
        self.assertEqual(document['readback_kind'],'PDF_TEXT_EXTRACTION')
        self.assertEqual(document['converter'],'pypdf')
        self.assertEqual((self.out/document['readback']).read_text(),'Actual converter readback.')

    def test_identical_primary_documents_share_one_bound_readback(self):
        import source_staging
        pdf=self.case/'shared.pdf';pdf.write_bytes(b'%PDF-1.7\nsynthetic source for controlled extraction')
        evidence={'path':pdf.name,'sha256':a.bind(pdf)['sha256']}
        source={'evidence':[evidence],'primary_evidence':[evidence]}
        with patch('target_selection.text',return_value='One actual extraction.') as converter:
            first=source_staging.stage_external(self.case,{'id':'E011','source':source},self.out)
            second=source_staging.stage_external(self.case,{'id':'E012','source':source},self.out)
        self.assertEqual(converter.call_count,1)
        self.assertEqual(first['documents'][0]['readback'],second['documents'][0]['readback'])
        path=self.out/first['documents'][0]['readback'];path.write_text('tampered')
        with self.assertRaisesRegex(ValueError,'readback changed'):
            source_staging.stage_external(self.case,{'id':'E013','source':source},self.out)

    def test_every_external_application_condition_has_its_own_review(self):
        packet=a.nl0.load(self.out/'R001/packet.json')
        app={'input':'E001',**self.row(),'bindings_review':self.row(), 'hypothesis_reviews':[self.row()],
             'conclusion_review':self.row(),'bridges':[]}
        value={'inference':'R001','packet_sha256':packet['packet_sha256'],'verdict':'UNVERIFIED','notes':'Synthetic only.',
               'checks':{key:self.row() for key in a.nl0.CHECKS|a.nl0.closure.CLOSURE_CHECKS},
               'external_applications':{'A001':app},'findings':[]}
        a.validate_review(value,self.out/'R001',False)
        app['hypothesis_reviews']=[]
        with self.assertRaisesRegex(ValueError,'every source hypothesis'):a.validate_review(value,self.out/'R001',False)

    def test_inaccessible_primary_cannot_receive_citation_passes_from_memory(self):
        path=self.out/'global/external-source-evidence.json';access=a.nl0.load(path)
        for row in access['E001']['documents']:row['readback_kind']='UNAVAILABLE'
        a.write(path,access)
        source={**self.row(),'citation_checks':{key:self.row('PASS') for key in a.nl0.EXTERNAL_CHECKS}}
        value={'target_review':self.row(),'structure_review':self.row(),'definition_reviews':{},'source_reviews':{'E001':source},'findings':[]}
        with self.assertRaisesRegex(ValueError,'no usable readback'):a.validate_review(value,self.out/'global',True)
        for key in ['result_location','statement_fidelity','context_completeness']:source['citation_checks'][key]=self.row()
        a.validate_review(value,self.out/'global',True)


if __name__=='__main__':unittest.main()
