"""A carrier change at an actual local graph return, with native closure."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import harness_support as support
from basis_fixtures import TARGET
from controller_common import bind, write
from lean_library_fixtures import library
from local_setup_fixtures import configuration
import execution_state
import graph_continuation
import jobs
import local_config
import runtime_config
import setup_checks
import target_selection


@unittest.skipUnless(support.native_available(), 'Needs the installed local Codex carrier')
class GraphContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scratch = tempfile.TemporaryDirectory()
        cls.addClassCleanup(scratch.cleanup)
        cls.root = Path(scratch.name).resolve()
        cls.old = cls.root/'original'
        cls.env = runtime_config.require_environment()
        tools = runtime_config.host_tools()
        cls.ready = configuration(cls.root/'setup')
        cls.ready.update(mode='lean', lean_environment=cls.env,
                         host={'codex':tools['codex'], 'python':str(Path(sys.executable)),
                               'ripgrep':bind(tools['tools']['ripgrep']['binary_path']),
                               'auth_home':str(cls.root/'setup/auth')})
        cls.ready['checks'].update({name:setup_checks.record(cls.root/'setup',name,{'fixture':'offline'})
                                    for name in local_config.rules.LEAN_CHECKS})
        old_ready = deepcopy(cls.ready)
        previous_manifest = cls.root/'previous-native-manifest.json'
        previous_manifest.write_text('{"version":"previous fixture build"}\n')
        old_ready['host']['codex']['package_manifest']=bind(previous_manifest)
        proof = cls.root/'problem.md'
        proof.write_text(TARGET)
        external = cls.root/'external'
        specification = library(external)
        material = external/'source/FixtureLib/Leaf.lean'
        with local_config.use(old_ready):
            cls.old_job = jobs.prepare(proof,track='full',formalization='unconditional',profiles=support.PROFILES,
                target=target_selection.resolve(proof,requested=TARGET),materials=[material],
                lean_libraries=[specification],output=cls.old,max_concurrency=1,time_budget_seconds=1800)
        result = cls.run_case(cls.old, stop=True)
        state = json.loads((cls.old/'protocol/work/state.json').read_text())
        if not (result.returncode==1 and state['node']=='nl0-local/revise-graph'):
            native_errors = [p.read_text()[-1000:] for p in cls.old.glob('2basis/*/stage/transport-stderr.log')]
            raise AssertionError((result.returncode,state['node'],native_errors,(result.stdout+result.stderr)[-5000:]))
        cls.returned = json.loads((cls.old/'case-result.json').read_text())['result']
        if cls.returned['status']!='CANCELLED':
            raise AssertionError(cls.returned)
        previous_manifest.write_text('{"version":"updated fixture build"}\n')
        proof.unlink()
        material.unlink()

    @staticmethod
    def run_case(root, *, stop=False):
        driver = support.TESTS/'tooling/basis_path_control.py'
        mode = 'planned-closed+graph-continuation+refine-after-audit'
        if stop:
            mode += '+stop-before-revision'
        job = json.loads((root/'job.json').read_text())
        env = {**os.environ,'YUI_FROZEN_LOCAL_CONFIG':json.dumps(job['local_configuration'])}
        return subprocess.run([sys.executable,'-B',str(driver),str(root/'job.json'),mode],
                              capture_output=True,text=True,timeout=480,env=env)

    def cli(self, *argv):
        script = support.CORE/'nl0/scripts/yui.py'
        env = {**os.environ,'YUI_FROZEN_LOCAL_CONFIG':json.dumps(self.ready)}
        return subprocess.run([sys.executable,'-B',str(script),*map(str,argv)], env=env,
                              capture_output=True,text=True,timeout=120)

    def test_changed_immutable_science_rejects_continuation(self):
        context = json.loads((self.old/'active-inputs/proof-context.json').read_text())
        paths = {
            'frozen input': self.old/'inputs/problem.md',
            'frozen target': self.old/'inputs/target-selection.json',
            'reviewed basis receipt': Path(context['semantic_review']['path']),
        }
        for label,path in paths.items():
            with self.subTest(label=label):
                old = path.read_bytes()
                try:
                    path.write_bytes(old.replace(b'a+0',b'a+1',1) if b'a+0' in old else old+b' ')
                    out = self.root/'rejected'
                    result = self.cli('continue-graph',self.old,'--output',out,'--prepare-only')
                    self.assertEqual(result.returncode,1,result.stdout+result.stderr)
                    self.assertIn(path.name,result.stdout+result.stderr)
                    self.assertFalse(out.exists())
                finally:
                    path.write_bytes(old)

    def test_live_predecessor_rejected_before_output_is_created(self):
        path = self.old/'execution-status.json'
        original = path.read_bytes()
        status = json.loads(original)
        status['controller'] = {**execution_state.identity(os.getpid()), 'state':'RUNNING'}
        try:
            write(path,status)
            out = self.root/'while-live'
            result = self.cli('continue-graph',self.old,'--output',out,'--prepare-only')
            self.assertEqual(result.returncode,1,result.stdout+result.stderr)
            self.assertIn('Confirm exit',result.stdout)
            self.assertFalse(out.exists())
        finally:
            path.write_bytes(original)

    def test_repeated_stage_keeps_the_original_session_release(self):
        from graph_continuation_evidence import Evidence
        from run_resources import safe_stage_workspace

        with tempfile.TemporaryDirectory(dir=self.root) as scratch:
            source = Path(scratch)/'old'
            target = Path(scratch)/'new'
            owner = source/'2basis/0001/review/stage'
            later = source/'2basis/0002/review/stage'
            retention = {'status':'OWNED_RETAINED','workspace':str(source/'removed-workspace'),
                         'logs':str(owner),'owner':{},'marker_sha256':'0'*64}
            prior_submission = source/'2basis/0001/review/stage/accepted.json'
            write(prior_submission,{})
            session = {'previous_submission':bind(prior_submission)}
            for stage in (owner,later):
                write(stage/'result.json',{'temporary_workspace_removed':False,
                    'workspace_retention':retention,'stage_log_path':str(stage),'role_session':session})
            write(owner/'resources/release.json',{'authorization':'ROLE_COMPLETED',
                'workspace_retention':retention,'result_sha256':bind(owner/'result.json')['sha256'],
                'cleanup_confirmed':True})
            original = json.loads((later/'result.json').read_bytes())
            self.assertTrue(safe_stage_workspace(original))
            result = Evidence(source,target,self.env).stage_result(later/'result.json')
            source.rename(source.with_name('moved'))
            migrated = json.loads(Path(result['path']).read_bytes())
            self.assertEqual(migrated['workspace_retention']['logs'],str(target/owner.relative_to(source)))
            self.assertEqual(migrated['role_session'],session)
            self.assertTrue(safe_stage_workspace(migrated))

    def test_working_graph_carries_and_rebinds_its_native_source_evidence(self):
        from graph_continuation_evidence import Evidence

        with tempfile.TemporaryDirectory(dir=self.root) as scratch:
            source = Path(scratch)/'old'
            target = Path(scratch)/'new'
            relative = Path('global-graphs/0001/stage/case')
            probe = Path('library/basis-M001/library-sources.json')
            context_file = Path('active-inputs/proof-context.json')
            before,after = ({'basis':str(root/'2basis/0001')} for root in (source,target))
            write(source/context_file,before)
            write(target/context_file,after)
            write(source/relative/probe,{'probe_version':1,'inheritance':{'context':before}})
            write(source/relative/'citation.txt','Frozen external text')
            rows = {name:{'path':str(path),'sha256':bind(source/relative/path)['sha256']}
                    for name,path in [('mathlib',probe),('external',Path('citation.txt'))]}
            graph = {'propositions':[{'kind':kind,'source':{'evidence':[row]}} for kind,row in rows.items()]}
            Evidence(source,target,self.env).working_sources(source/relative,graph,
                (bind(source/context_file),bind(target/context_file)))
            source.rename(source.with_name('moved'))
            record = json.loads((target/relative/probe).read_bytes())
            self.assertEqual(record['inheritance']['context'],after)
            for row in rows.values():
                self.assertEqual(row['sha256'],bind(target/relative/row['path'])['sha256'])

    def test_new_carrier_and_original_run_removed_before_real_delivery(self):
        with self.assertRaisesRegex(ValueError,'Bound Codex native component changed'):
            jobs.validate(self.old_job)
        out = self.root/'successor'
        result = self.cli('continue-graph',self.old,'--output',out,'--prepare-only')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        new = json.loads((out/'job.json').read_text())
        checkpoint = graph_continuation.descriptor(new)
        selected=Path(checkpoint['global']['path'])
        self.assertEqual(selected.parents[2].name,'0001-edges')
        graph=json.loads(Path(json.loads(selected.read_text())['graph']['path']).read_text())
        self.assertIn('E001',graph['inferences'][0]['inputs'])
        self.assertEqual(new['lean_environment'],self.old_job['lean_environment'])
        self.assertEqual(new['max_concurrency'],self.old_job['max_concurrency'])
        self.assertEqual(new['native_components'],self.ready['host']['codex'])
        old_status = json.loads((self.old/'execution-status.json').read_text())
        self.assertEqual(checkpoint['deadline'],old_status['time_budget']['deadline_at_utc'])
        self.assertLess(new['time_budget_seconds'],self.old_job['time_budget_seconds'])
        native_run = self.root/'offline-archive'
        self.old.rename(native_run)
        try:
            jobs.validate(new)
            result = self.run_case(out)
            self.assertEqual(result.returncode,0,(result.stdout+result.stderr)[-8000:])
            self.assertFalse(self.old.exists())
            self.assertFalse(any((out/'2basis').glob('**/route.json')))
            findings = json.loads((out/'nl0/local-0002/inputs/global-findings.json').read_text())
            self.assertEqual([row['id'] for row in findings['local_proofs']],['R001'])
            self.assertEqual(findings['blockers'][0]['subject'],'H001')
            new_status = json.loads((out/'execution-status.json').read_text())
            self.assertEqual(new_status['time_budget']['deadline_at_utc'],checkpoint['deadline'])
            trace = json.loads((out/'protocol/work/state.json').read_text())['trace']
            self.assertEqual(trace[0]['node'],'continue-graph')
            self.assertTrue({'translate','close','publish'} <= {row['node'] for row in trace})
            import nl0
            coarse_record=nl0.load(out/'handoffs/audited-coarse-0002.json')
            coarse=Path(coarse_record['files']['audit_a']['path'])
            self.assertEqual(set(nl0.load(coarse)['inference_reviews']),{'R001','R002'})
            author=out/'nl0/refine-0002-0001/stage'
            self.assertLess(coarse.stat().st_mtime_ns,(author/'execution-manifest.json').stat().st_mtime_ns)
            natural=out/'delivery/nl0'
            fine=nl0.load(natural/'audit-a.json')
            self.assertEqual(set(fine['inference_reviews']),{'R001','R002','R003'})
            self.assertIn('inheritance',fine['inference_reviews']['R001'])
            for rid in ('R002','R003'):
                self.assertEqual(fine['inference_reviews'][rid]['verdict'],'PASS')
            with self.assertRaisesRegex(ValueError,'STALE-AUDIT'):
                nl0.validate(natural/'nl0.json',natural/'spec.json',coarse)
            fine['inference_reviews'].pop('R003')
            work=natural/'missing-fine-review.json'
            try:
                write(work,fine)
                with self.assertRaises(ValueError):
                    nl0.validate(natural/'nl0.json',natural/'spec.json',work)
            finally:
                work.unlink()
            delivered = self.root/'readback'
            shutil.copytree(out/'delivery', delivered)
            final = self.cli('verify-delivery',delivered)
            self.assertEqual(final.returncode,0,final.stdout+final.stderr)
            self.assertEqual(json.loads(final.stdout)['scope'],'UNCONDITIONAL_LEAN')
            self.assertTrue((delivered/'formalization/lean-libraries/FixtureLib/source/FixtureLib/Leaf.lean').is_file())
            report = json.loads((delivered/'run.json').read_text())
            self.assertEqual(report['entry'],'2basis')
            self.assertEqual(report['recovery']['resumed_at'],'revise_graph')
            self.assertEqual(report['recovery']['origin']['run_id'],self.old_job['run_id'])
            previous,current = (report['recovery']['carrier'][key] for key in ('previous','current'))
            self.assertEqual(previous['sha256'],current['sha256'])
            self.assertNotEqual(previous['package_manifest_sha256'],current['package_manifest_sha256'])
        finally:
            native_run.rename(self.old)
