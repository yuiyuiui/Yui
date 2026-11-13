"""Unknown native shutdown preserves owned source; confirmed exits permit cleanup."""
import harness_support
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import cleanup
import execution_state
import ir
import jobs
import native_workspace
import pilot_common
from lean_fixtures import norm_plan, LIFT
from run_resources import MARKER


class NativeWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.retained=[]
        for name in ('contract.json','source.json'):
            shutil.copyfile(harness_support.FIXTURES/'lean/examples/case1_norm_sup'/name,self.root/name)
        self.cp=self.root/'contract.json';self.plan=norm_plan(self.cp)

    def tearDown(self):
        # These fault doubles launch no native process. Real native checks in
        # this class have completed handles before the simulated uncertainty.
        for work in self.retained:
            if work.exists():shutil.rmtree(work)
        self.temp.cleanup()

    def unknown(self,file,work,**kwargs):
        self.retained.append(Path(work))
        raise RuntimeError('Native process cleanup could not be confirmed')

    def assert_retained(self,filename):
        self.assertTrue(self.retained)
        work=self.retained[-1]
        self.assertTrue((work/MARKER).is_file())
        self.assertTrue((work/'output'/filename).is_file())
        self.assertIn('import Mathlib',(work/'output'/filename).read_text())
        value=json.loads((work/'native-workspace-retained.json').read_text())
        self.assertFalse(value['cleanup_confirmed'])
        self.assertEqual(value['workspace'],str(work))
        return work

    def test_ir_check_retains_source_and_owner_after_unknown_shutdown(self):
        with patch.object(ir,'run_lean',side_effect=self.unknown):
            with self.assertRaisesRegex(RuntimeError,'cleanup'):
                ir.check(self.cp,self.plan,{'T001':LIFT},only='T001')
        self.assert_retained('Check.lean')

    def test_auxiliary_check_has_the_same_retention_contract(self):
        with patch('helper_modules.context',return_value=None),patch.object(ir,'run_lean',side_effect=self.unknown):
            with self.assertRaisesRegex(RuntimeError,'cleanup'):
                ir.check_auxiliary(self.cp,self.plan,'T001','True','trivial',out=self.root/'auxiliary')
        self.assert_retained('Auxiliary.lean')

    def test_interface_check_retains_its_actual_candidate_program(self):
        contract=ir.contract(self.cp)
        draft={'parameters':contract['parameters'],'premises':contract['premises'],
               'conclusion_type':contract['conclusion']['type'],'representation_notes':'The unchanged reviewed ports.'}
        with patch.object(ir,'run_lean',side_effect=self.unknown):
            with self.assertRaisesRegex(RuntimeError,'cleanup'):ir.check_interface(self.cp,draft)
        self.assert_retained('Interface.lean')

    def test_confirmed_compile_failure_releases_only_its_owned_scratch(self):
        observed=[]
        def failed(file,work,**kwargs):
            observed.append(Path(work))
            native_workspace.record(work,confirmed=True,phase='exited',exit_code=1)
            return {'exit_code':1,'stdout':'Located type mismatch.','stderr':'','wall_seconds':0.1}
        with patch.object(ir,'run_lean',side_effect=failed):
            result=ir.check(self.cp,self.plan,{'T001':LIFT},only='T001')
        self.assertEqual(result['status'],'LEAN-CHECK-FAILED')
        self.assertTrue(observed)
        self.assertTrue(all(not work.exists() for work in observed))

    def test_audit_b_retains_the_actual_assembly_workspace(self):
        import audit_b
        from audit_b_fixtures import prepare_control
        out=prepare_control(self.root/'audit-case')
        def unknown_assembly(c,mapping,formal,destination,work):
            file=work/'output/Assembly.lean';file.write_text(formal)
            return self.unknown(file,work)
        with patch.object(ir,'check',return_value={'exit_code':0}), \
                patch.object(audit_b.assembly,'build',side_effect=unknown_assembly):
            with self.assertRaisesRegex(RuntimeError,'cleanup'):audit_b.build(out)
        self.assert_retained('Assembly.lean')

    def test_interface_type_tool_retains_its_native_input(self):
        import translation_author
        stage=object.__new__(translation_author.InterfaceStage)
        stage.accepted=None;stage.type_probes=0;stage.lean_calls=0;stage.logs=self.root/'type-tool'
        stage.lean_timeout=lambda:360
        with patch.object(ir,'run_lean',side_effect=self.unknown):
            with self.assertRaisesRegex(RuntimeError,'cleanup'):
                stage.dispatch('check_lean_types',{'header':'import Mathlib\n','parameters':[],'types':['True']})
        self.assert_retained('Types.lean')

    def test_shared_module_check_retains_source_until_stop_is_confirmed(self):
        import shared_lemmas
        from lean_fixtures import shared_fixture
        cp,plan=shared_fixture(self.root/'shared-input')
        checked=ir.check(cp,plan,{'T001':LIFT},only='T001')
        store=shared_lemmas.Store(self.root/'store')
        with patch.object(ir,'run_lean',side_effect=self.unknown):
            with self.assertRaisesRegex(RuntimeError,'cleanup'):
                store.admit(cp,plan,'T001',LIFT,checked=checked)
        self.assert_retained('Shared.lean')

    def test_confirmed_cancellation_can_release_scratch(self):
        observed=[]
        def cancelled(file,work,**kwargs):
            observed.append(Path(work));native_workspace.record(work,confirmed=True,phase='exited',exit_code=130)
            raise execution_state.Cancelled('Explicit fixture cancellation after verified exit')
        with patch.object(ir,'run_lean',side_effect=cancelled):
            with self.assertRaises(execution_state.Cancelled):
                ir.check(self.cp,self.plan,{'T001':LIFT},only='T001')
        self.assertTrue(observed)
        self.assertFalse(observed[0].exists())

    def test_real_completed_native_call_with_unconfirmed_cleanup_cannot_release_or_return_success(self):
        original=pilot_common.terminate_owned
        with patch.object(pilot_common,'terminate_owned',return_value=False):
            with self.assertRaisesRegex(RuntimeError,'cleanup') as caught:
                ir.check(self.cp,self.plan,{'T001':LIFT},only='T001')
        work=Path(caught.exception.native_workspace);self.retained.append(work)
        self.assert_retained('Check.lean')
        self.assertFalse(native_workspace.confirmed(work))
        fence=json.loads((work/native_workspace.FENCE).read_text())
        self.assertIs(fence['cleanup_confirmed'],False)
        self.assertEqual(fence['exit_code'],0)

    def test_child_launched_before_identity_failure_remains_known_and_blocks_unsafe_cleanup(self):
        import runtime_config
        selected=runtime_config.use_environment(runtime_config.require_environment())
        selected.__enter__();self.addCleanup(selected.__exit__,None,None,None)
        problem=self.root/'problem.md';problem.write_text('Native launch ownership fixture.')
        job=jobs.prepare(problem,track='nl0',profiles=harness_support.PROFILES,output=self.root/'run')
        run=Path(job['root']);actual=subprocess.Popen;children=[];workspaces=[]
        def launched(command,**kwargs):
            if not isinstance(command,(list,tuple)) or Path(command[0]).name not in {'sandbox-exec','lean'} or not kwargs.get('start_new_session'):
                return actual(command,**kwargs)
            child=actual([sys.executable,'-B','-c','import time; time.sleep(60)'],
                cwd=kwargs['cwd'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
            children.append((child,execution_state.capture_process(child,private_group=True)))
            return child
        try:
            with native_workspace.temporary('native-unknown-child-',logs=run/'check') as work:
                workspaces.append(work);self.retained.append(work)
                (work/'input').mkdir();(work/'output').mkdir();file=work/'output/Check.lean'
                file.write_text('import Mathlib\nexample : True := by trivial\n')
                with patch.object(pilot_common.subprocess,'Popen',side_effect=launched), \
                        patch.object(pilot_common,'capture_process',side_effect=RuntimeError('OS identity query unavailable')):
                    with self.assertRaisesRegex(RuntimeError,'OS identity'):
                        pilot_common.run_lean(file,work,timeout=30)
                fence=native_workspace.read_cleanup(work)
                self.assertFalse(fence['cleanup_confirmed']);self.assertEqual(fence['process']['pid'],children[0][0].pid)
                with patch.object(cleanup,'signal_owned',side_effect=AssertionError('Unknown group must not be signalled')):
                    blocked=cleanup.clean(apply=True,grace=0,outputs=[run])
                self.assertEqual(blocked['status'],'BLOCKED',blocked);self.assertTrue(work.exists())
                # The test owns a separate verified handle. This is not an
                # application inference from its deliberately failed query.
                child,owner=children[0]
                self.assertTrue(execution_state.terminate_owned(child,owner))
                native_workspace.record(work,confirmed=True,phase='test-owned-exit',process=owner,exit_code=child.returncode)
        finally:
            for child,owner in children:
                if child.poll() is None:execution_state.terminate_owned(child,owner)
                for stream in (child.stdout,child.stderr):
                    if stream:stream.close()

    def test_owned_cleanup_reclaims_retention_only_after_exit_and_exact_marker_readback(self):
        problem=self.root/'problem.md';problem.write_text('Synthetic cleanup ownership fixture.')
        job=jobs.prepare(problem,track='nl0',profiles=harness_support.PROFILES,output=self.root/'run')
        run=Path(job['root']);receipt=self.root/'retained.json'
        code=("import sys,json;from pathlib import Path;sys.path.insert(0,"+repr(str(harness_support.CORE/'nl0/scripts'))+");"
              "import native_workspace;work=None\n"
              "try:\n with native_workspace.temporary('native-retention-test-',logs=Path("+repr(str(run/'check'))+")) as current:\n"
              "  work=current;(work/'output').mkdir();(work/'output/Check.lean').write_text('example : True := by trivial\\n');"
              "raise RuntimeError('Native process cleanup could not be confirmed')\n"
              "except RuntimeError:\n Path("+repr(str(receipt))+").write_text(json.dumps({'workspace':str(work)}))\n")
        cp=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,text=True,timeout=30)
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
        work=Path(json.loads(receipt.read_text())['workspace']);self.retained.append(work)
        self.assertTrue(work.is_dir())
        marker=work/MARKER;saved=marker.read_bytes()
        value=json.loads(saved);value['logs']=str(self.root/'foreign')
        marker.write_text(json.dumps(value))
        blocked=cleanup.clean(apply=True,grace=0,outputs=[run])
        self.assertEqual(blocked['status'],'BLOCKED',blocked)
        self.assertTrue(work.exists());marker.write_bytes(saved)
        result=cleanup.clean(apply=True,grace=0,outputs=[run])
        self.assertEqual(result['status'],'CLEANED',result)
        self.assertFalse(work.exists());self.assertTrue(problem.exists())


if __name__=='__main__':unittest.main()
