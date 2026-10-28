"""Direct-arm continuation controls use fake CLI/compiler processes only."""
import harness_support
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import direct_runner as runner


class DirectRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.work=Path(self.temp.name)
        (self.work/'prompt.md').write_text('Synthetic test only.')
        self.env=patch.dict(os.environ,{'CODEX_HOME':str(self.work/'empty-auth')});self.env.start()
    def tearDown(self):self.env.stop();self.temp.cleanup()

    def files(self):
        (self.work/'Proof.lean').write_text('theorem theorem_1 : True := by trivial\n')
        (self.work/'correspondence.md').write_text('Synthetic fixture, not a paper proof.')
        (self.work/'result.json').write_text(json.dumps({'status':'complete','root_declaration':'theorem_1',
            'target_label':'Theorem 1','remaining_obligations':[],'blocker':None}))

    def compiled(self,*args,**kwargs):
        return SimpleNamespace(returncode=0,stdout="'theorem_1' does not depend on any axioms\n",stderr='')

    def test_compilation_is_only_a_candidate_not_semantic_acceptance(self):
        self.files();result=runner.verify(self.work,Path('/fake/lean'),self.work,compile_call=self.compiled)
        self.assertTrue(result['ready']);self.assertEqual(result['independent_semantic_acceptance'],'UNVERIFIED')

    def test_incomplete_root_placeholder_or_unproved_axiom_cannot_finish(self):
        self.files()
        for code in ['theorem theorem_1 : True := by sorry','axiom theorem_1 : True']:
            (self.work/'Proof.lean').write_text(code)
            self.assertFalse(runner.verify(self.work,Path('/fake/lean'),self.work,compile_call=self.compiled)['ready'])
        self.files();value=json.loads((self.work/'result.json').read_text());value['remaining_obligations']=['Main result']
        (self.work/'result.json').write_text(json.dumps(value))
        self.assertFalse(runner.verify(self.work,Path('/fake/lean'),self.work,compile_call=self.compiled)['ready'])

    def test_native_compile_error_and_unexpected_trust_dependencies_are_returned(self):
        self.files()
        failed=lambda *a,**k:SimpleNamespace(returncode=1,stdout='type mismatch',stderr='')
        self.assertIn('type mismatch',runner.verify(self.work,Path('/fake/lean'),self.work,compile_call=failed)['diagnostic'])
        unsafe=lambda *a,**k:SimpleNamespace(returncode=0,stdout="'theorem_1' depends on axioms: [extraPremise]",stderr='')
        self.assertFalse(runner.verify(self.work,Path('/fake/lean'),self.work,compile_call=unsafe)['ready'])

    def test_normal_incomplete_turn_continues_the_same_session(self):
        observed=[]
        def turn(binary,work,prompt,session,number,env,cancelled):
            observed.append((session,prompt))
            if number==1:(work/'result.json').write_text('{"status":"in_progress"}')
            else:self.files()
            return 0,'same-session',[{'input_tokens':10,'output_tokens':5}]
        check=lambda work,lean,ml:runner.verify(work,lean,ml,compile_call=self.compiled)
        result=runner.run(self.work,Path('/fake/codex'),Path('/fake/lean'),self.work,turn_call=turn,verify_call=check)
        self.assertEqual(result['status'],'CANDIDATE_READY');self.assertEqual(result['turns'],2)
        self.assertEqual([x[0] for x in observed],[None,'same-session'])
        self.assertIn('unfinished',observed[1][1])
        self.assertFalse((self.work/'.runtime-home/auth.json').exists())

    def test_session_identity_change_is_not_silently_restarted(self):
        def turn(binary,work,prompt,session,number,env,cancelled):return 0,'first' if number==1 else 'other',[]
        result=runner.run(self.work,Path('/fake/codex'),Path('/fake/lean'),self.work,turn_call=turn,
            verify_call=lambda *a:{'ready':False,'reason':'pending'})
        self.assertEqual(result['status'],'EXECUTION_FAULT');self.assertEqual(result['turns'],2)

    def test_malformed_partial_checkpoint_is_repaired_in_the_same_session(self):
        calls=[]
        def turn(binary,work,prompt,session,number,env,cancelled):
            calls.append(session)
            if number==1:(work/'result.json').write_text('{incomplete JSON')
            else:self.files()
            return 0,'same-session',[]
        check=lambda work,lean,ml:runner.verify(work,lean,ml,compile_call=self.compiled)
        result=runner.run(self.work,Path('/fake/codex'),Path('/fake/lean'),self.work,turn_call=turn,verify_call=check)
        self.assertEqual(result['status'],'CANDIDATE_READY');self.assertEqual(calls,[None,'same-session'])

    def test_concrete_missing_input_returns_attention_instead_of_false_completion(self):
        def turn(binary,work,prompt,session,number,env,cancelled):
            (work/'result.json').write_text(json.dumps({'status':'blocked','blocker':{
                'kind':'missing_input','detail':'Original page is absent.','evidence':'input manifest'}}))
            return 0,'same-session',[]
        result=runner.run(self.work,Path('/fake/codex'),Path('/fake/lean'),self.work,turn_call=turn,
            verify_call=lambda *a:{'ready':False,'reason':'pending'})
        self.assertEqual(result['status'],'HUMAN_INPUT_REQUIRED')

    def test_command_preserves_profile_and_resume_uses_exact_id(self):
        first=runner.command('/fake/codex',self.work)
        resumed=runner.command('/fake/codex',self.work,'same-session')
        self.assertEqual(resumed,first[:-1]+['resume','same-session','-'])
        for value in ['gpt-6.1-sol','model_reasoning_effort="high"','service_tier="default"','--ignore-user-config']:
            self.assertIn(value,first)

    def test_cancel_terminates_the_actual_owned_fake_process(self):
        program=self.work/'fake-codex';program.write_text('#!'+sys.executable+'\nimport time\ntime.sleep(20)\n');program.chmod(0o755)
        begin=time.monotonic()
        code,session,usage=runner.turn(program,self.work,'test',None,1,os.environ.copy(),lambda:time.monotonic()-begin>.2)
        self.assertNotEqual(code,0);self.assertLess(time.monotonic()-begin,4)

    def test_cancel_also_terminates_a_running_compiler(self):
        begin=time.monotonic()
        result=runner.compile_process([sys.executable,'-c','import time; time.sleep(20)'],
            cwd=self.work,env=os.environ.copy(),cancelled=lambda:time.monotonic()-begin>.2)
        self.assertNotEqual(result.returncode,0);self.assertLess(time.monotonic()-begin,4)

    def prompt_inputs(self):
        paper=self.work/'selected paper.pdf';paper.write_bytes(b'%PDF-1.7\nsynthetic input')
        lean=self.work/'tools/bin/lean';lean.parent.mkdir(parents=True);lean.write_text('synthetic executable; never called')
        mathlib=self.work/'selected mathlib';mathlib.mkdir()
        return paper,lean,mathlib

    def test_generated_prompt_and_actual_first_turn_use_the_same_selected_paths(self):
        paper,lean,mathlib=self.prompt_inputs();work=self.work/'fresh run';observed=[]
        render=lambda **paths:'Selected inputs: '+json.dumps({k:str(v) for k,v in paths.items()})
        def turn(binary,current,prompt,session,number,env,cancelled):
            observed.append((binary,current,prompt));return 0,'same-session',[]
        original_run=runner.run
        with patch.object(runner,'run',side_effect=lambda *args:original_run(*args,turn_call=turn,
                verify_call=lambda *args:{'ready':True,'status':'CONTROL_ONLY'})),patch('sys.stdout'):
            result=runner.main(default_work=work,prompt_factory=render,default_paper=paper,argv=[
                '--lean',str(lean),'--mathlib',str(mathlib),'--codex',str(self.work/'selected codex')])
        self.assertEqual(result['status'],'CONTROL_ONLY');self.assertEqual(len(observed),1)
        self.assertEqual(observed[0][2],(work/'prompt.md').read_text())
        selected=json.loads(observed[0][2].split(': ',1)[1])
        self.assertEqual(selected,{'paper':str(paper.resolve()),'lean':str(lean.resolve()),'mathlib':str(mathlib.resolve())})
        self.assertEqual(observed[0][0],(self.work/'selected codex').resolve())

    def test_prompt_preparation_rejects_missing_inputs_without_creating_an_output(self):
        paper,lean,mathlib=self.prompt_inputs();work=self.work/'must remain absent'
        for missing in (paper,lean,mathlib):
            paths=[self.work/'missing' if p==missing else p for p in (paper,lean,mathlib)]
            with self.subTest(missing=missing),self.assertRaises(FileNotFoundError):
                runner.prepare_prompt(work,*paths,renderer=lambda **paths:'No launch')
            self.assertFalse(work.exists())

    def test_prompt_preparation_preserves_started_runs_and_conflicting_saved_prompts(self):
        paper,lean,mathlib=self.prompt_inputs();prompt=self.work/'prompt.md';before=prompt.read_bytes()
        with self.assertRaisesRegex(ValueError,'Existing prompt differs'):
            runner.prepare_prompt(self.work,paper,lean,mathlib,renderer=lambda **paths:'Different prompt')
        self.assertEqual(prompt.read_bytes(),before)
        for name in ('execution-status.json','execution-result.json'):
            status=self.work/name;status.write_text('{"status":"RECORDED"}')
            with self.subTest(record=name),self.assertRaisesRegex(ValueError,'Existing run metadata'):
                runner.prepare_prompt(self.work,paper,lean,mathlib,renderer=lambda **paths:prompt.read_text())
            self.assertEqual(status.read_text(),'{"status":"RECORDED"}');self.assertEqual(prompt.read_bytes(),before)
            status.unlink()

    def test_prompt_preparation_survives_relocation_and_tool_overrides(self):
        clone=self.work/'relocated skill root'
        driver=clone/'nl0/scripts/direct_runner.py';driver.parent.mkdir(parents=True)
        shutil.copyfile(runner.__file__,driver)
        default_paper=clone/'supplied paper.pdf';default_paper.write_bytes(b'%PDF-1.7\nsynthetic input')
        program=('import json; from pathlib import Path; from direct_runner import main; '
                 'main(prompt_factory=lambda **paths: "Selected inputs: "+'
                 'json.dumps({k:str(v) for k,v in paths.items()}), '
                 'default_paper=Path('+repr(str(default_paper))+'))')
        selected_paper,lean,mathlib=self.prompt_inputs()
        for mode in ('environment_defaults','explicit_cli'):
            work=self.work/mode;env=os.environ.copy()
            env.update(YUI_LEAN_ROOT=str(lean.parent.parent),YUI_MATHLIB_ROOT=str(mathlib),
                       YUI_CODEX_BINARY=str(self.work/'must-not-be-started'),PYTHONPATH=str(driver.parent))
            command=[sys.executable,'-B','-c',program,'--work',str(work),'--prepare-only']
            if mode=='explicit_cli':
                env.update(YUI_LEAN_ROOT=str(self.work/'invalid-default'),YUI_MATHLIB_ROOT=str(self.work/'invalid-default'))
                command+=['--paper',str(selected_paper),'--lean',str(lean),'--mathlib',str(mathlib)]
            with self.subTest(mode=mode):
                completed=subprocess.run(command,cwd=self.work,env=env,capture_output=True,text=True)
                self.assertEqual(completed.returncode,0,completed.stderr)
                result=json.loads(completed.stdout);self.assertEqual(result['status'],'PROMPT_PREPARED')
                prompt=Path(result['prompt']).read_text()
                paper=selected_paper if mode=='explicit_cli' else default_paper
                selected=json.loads(prompt.split(': ',1)[1])
                self.assertEqual(selected,{'paper':str(paper.resolve()),'lean':str(lean.resolve()),'mathlib':str(mathlib.resolve())})
                self.assertFalse((work/'execution-status.json').exists())


if __name__=='__main__':unittest.main()
