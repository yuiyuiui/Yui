"""Reusable audit-reuse setup; this mixin deliberately defines no test methods."""
from pathlib import Path
import shutil
import tempfile
import harness_support
import audit_a_campaign as a
import audit_reuse as reuse

class AuditReuseFixture:
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.old=self.root/'old';shutil.copytree(a.CORE/'tests/fixtures/closed-addition',self.old)
        self.problem=self.root/'problem';self.problem.mkdir();(self.problem/'problem.md').write_text('Synthetic controller fixture only.')
        self.campaign=self.root/'previous';self.plan=a.prepare(self.old,self.problem,self.campaign)
        for job in self.plan['jobs']:
            directory=self.campaign/job['id'];stage=directory/'stage';stage.mkdir()
            row={'verdict':'PASS','notes':'SYNTHETIC inheritance test judgment, not a mathematical audit.','locations':['/inference/argument']}
            if job['library']:
                raw={'target_review':row,'structure_review':row,'definition_reviews':{},'source_reviews':{},'findings':[]}
                docs={name:reuse.sha(directory/name) for name in ['spec.json','nl0.json']}
            else:
                packet=a.nl0.load(directory/'packet.json')
                raw={'inference':job['id'],'packet_sha256':packet['packet_sha256'],'verdict':'PASS',
                     'notes':row['notes'],'checks':{key:row for key in a.nl0.CHECKS|a.nl0.closure.CLOSURE_CHECKS},'findings':[]}
                docs={'packet.json':reuse.sha(directory/'packet.json')}
            exposure={'status':'TRANSMITTED-EXPOSURE-CHECK-PASSED','actual_model_ids':[__import__('run_pilot').MODEL],'standard_tier_verified':True}
            result={'status':'ACCEPTED','execution_health':'NO_RECORDED_FAULT','usage':{'complete':True},'exposure':exposure}
            for name,value in [('accepted.json',raw),('result.json',result),('exposure-audit.json',exposure),
                               ('execution-manifest.json',{'rule_documents':reuse.rules(),'task_documents':docs})]:a.write(stage/name,value)
        self.new=self.root/'new';shutil.copytree(self.old,self.new)
        self.data=a.nl0.validate(self.new/'nl0.json',self.new/'spec.json')

    def tearDown(self):self.tmp.cleanup()

