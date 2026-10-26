"""Real pinned-source checks with synthetic review judgments, not proof audits."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

CORE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(CORE/'scripts'),str(CORE/'translation/scripts'),str(CORE/'tests')]
import audit_a_campaign as campaign
import audit_reuse as reuse
import background
import test_audit_reuse as fixtures
from artifact_validation import signature_probe


class EvidenceIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.probes=tempfile.TemporaryDirectory(prefix='yui-index-probes-')
        for identifier,declaration in [('M901','Continuous.add'),('M902','Continuous.mul')]:
            signature_probe(Path(cls.probes.name),identifier,declaration,None,1)

    @classmethod
    def tearDownClass(cls):cls.probes.cleanup()
    def setUp(self):fixtures.AuditReuseTests.setUp(self)
    def tearDown(self):fixtures.AuditReuseTests.tearDown(self)

    def add_notes(self,order=('A','B','B','C')):
        stage=self.campaign/'R001/stage';sources={}
        for letter,identifier in [('A','M901'),('B','M902'),('C','M901')]:
            source=background.source_from_probe(Path(self.probes.name),identifier)
            original=Path(self.probes.name)/source['evidence'][0]['path']
            target=stage/'library'/('source-'+letter+'.json');target.parent.mkdir(exist_ok=True)
            shutil.copyfile(original,target)
            source['evidence']=[{'path':str(target.relative_to(stage)),'sha256':reuse.sha(target)}]
            sources[letter]=source
        raw=campaign.nl0.load(stage/'accepted.json')
        raw['background_notes']=[{'id':'BG'+str(i+1).zfill(3),'kind':'mathlib',
            'at':'/inference/argument/0/text','fact':'Synthetic evidence-index control only.',
            'grounds':[{'location':'/inputs','reason':'Synthetic context-location control.'}],
            'justification':'Synthetic receipt fixture; no mathematical audit is claimed.',
            'source':deepcopy(sources[letter])} for i,letter in enumerate(order)]
        campaign.write(stage/'accepted.json',raw)
        return reuse.select(self.data,[self.campaign])['packet:R001'],sources

    def legacy_bad(self,binding,sources):
        record,_=reuse.read_binding(self.new,binding)
        record['background_sources'][sources['B']['evidence'][0]['path']]=record['background_sources'][sources['C']['evidence'][0]['path']]
        path=self.new/'review-evidence/reuse'/(reuse.hashed(record)+'.json')
        campaign.write(path,record)
        return {'path':str(path.relative_to(self.new)),'sha256':reuse.sha(path)}

    def test_repeated_sources_keep_correct_identity_and_unique_allocation(self):
        for order in [('A','B','B','C'),('B','B','B','A','C','A'),('A','B','C','B','C')]:
            hit,sources=self.add_notes(order)
            binding=reuse.materialize(hit,self.new);record,_=reuse.read_binding(self.new,binding)
            self.assertEqual(len(record['background_sources']),3)
            for source in sources.values():
                ev=source['evidence'][0];key=record['background_sources'][ev['path']]
                self.assertEqual(record['previous'][key]['sha256'],ev['sha256'])
            reuse.validate(self.new,binding,self.data,'packet:R001')

    def test_legacy_index_repairs_without_changing_old_files_or_judgments(self):
        hit,sources=self.add_notes();good=reuse.materialize(hit,self.new);bad=self.legacy_bad(good,sources)
        original=(self.new/bad['path']).read_bytes();record,paths=reuse.read_binding(self.new,bad)
        old_raw=paths['raw'].read_bytes()
        with self.assertRaises(reuse.EvidenceIndexError):reuse.validate(self.new,bad,self.data,'packet:R001')
        fixed,report=reuse.repair_evidence_index(self.new,bad,self.data,'packet:R001')
        self.assertEqual((self.new/bad['path']).read_bytes(),original)
        self.assertEqual(reuse.read_binding(self.new,fixed)[1]['raw'].read_bytes(),old_raw)
        self.assertEqual(report['new_model_calls'],0);self.assertEqual(report['new_native_checks'],0)
        self.assertFalse(report['mathematical_content_changed'])
        reuse.validate(self.new,fixed,self.data,'packet:R001')

    def test_missing_or_tampered_source_is_not_repaired_from_unbound_files(self):
        hit,sources=self.add_notes();bad=self.legacy_bad(reuse.materialize(hit,self.new),sources)
        record,paths=reuse.read_binding(self.new,bad);digest=sources['B']['evidence'][0]['sha256']
        correct=next(k for k,v in record['previous'].items() if k.startswith('background_') and v['sha256']==digest)
        paths[correct].write_text('{}')
        with self.assertRaisesRegex(ValueError,'Stale'):
            reuse.repair_evidence_index(self.new,bad,self.data,'packet:R001')

    def test_source_context_change_is_not_treated_as_an_index_repair(self):
        hit,sources=self.add_notes();bad=self.legacy_bad(reuse.materialize(hit,self.new),sources)
        changed=deepcopy(self.data);changed[2]['parameters'][0]['type']='a different mathematical domain'
        with self.assertRaisesRegex(ValueError,'context changed'):
            reuse.repair_evidence_index(self.new,bad,changed,'packet:R001')

    def test_actual_collection_recovers_bad_index_without_model_execution(self):
        hit,sources=self.add_notes();out=self.root/'recovery-campaign'
        (self.new/'audit-a.json').unlink(missing_ok=True)  # Discard only the synthetic fixture's old receipt.
        plan=campaign.prepare(self.new,self.problem,out,reuse_from=[self.campaign])
        bad=self.legacy_bad(plan['inherited']['packet:R001'],sources)
        plan['inherited']['packet:R001']=bad;campaign.write(out/'campaign.json',plan)
        with patch.object(campaign,'ArtifactStage') as model:
            result=campaign.collect(out,None)
        model.assert_not_called()
        self.assertTrue(result['full_acceptance']);self.assertEqual(len(result['bookkeeping_repairs']),1)
        self.assertTrue((self.new/bad['path']).exists())
        receipt=campaign.nl0.load(self.new/'audit-a.json')
        inherited=receipt['inference_reviews']['R001']['inheritance']
        self.assertNotEqual(inherited,bad)
        self.assertIn(bad,receipt['inference_reviews']['R001']['evidence'])
        campaign.nl0.validate(self.new/'nl0.json',self.new/'spec.json',self.new/'audit-a.json')
        import source_preparation
        _,files=source_preparation.read_source(self.new/'nl0.json',self.new/'spec.json',self.new/'audit-a.json')
        portable=self.root/'portable';portable.mkdir()
        for source in files:
            target=portable/source.relative_to(self.new.resolve());target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,target)
        campaign.nl0.validate(portable/'nl0.json',portable/'spec.json',portable/'audit-a.json')


if __name__=='__main__':unittest.main()
