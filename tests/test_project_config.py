"""Exercise project settings through public preparation and the real stage selectors."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import harness_support
import basis
import b2lean
import entrypoint
import jobs
import project_config
import runtime_config


class ProjectConfigTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.parser = argparse.ArgumentParser()
        entrypoint.parsers(self.parser.add_subparsers(dest='command'))

    def invoke(self, *args):
        return entrypoint.dispatch(self.parser.parse_args(list(map(str,args))))

    def project(self, name):
        path = self.root/name
        path.mkdir()
        (path/'proof.md').write_text('A supplied proof.\n')
        receipt = self.invoke('init-config',path)
        self.assertEqual(Path(receipt['path']),path/project_config.NAME)
        return path,receipt['configuration']

    def test_edit_before_first_run_and_independent_batch_settings(self):
        left,config = self.project('left')
        right,other = self.project('right')
        config['model']['reasoning_effort']='xhigh'
        config['stages']['audit-a']={'reasoning_effort':'max'}
        config['max_concurrency']=3
        other['model']['reasoning_effort']='low'
        for path,settings in [(left,config),(right,other)]:
            (path/project_config.NAME).write_text(json.dumps(settings))
        result=self.invoke('prepare',left/'proof.md',right/'proof.md','--track','nl0',
                           '--target','For every natural number n we have n = n.')
        self.assertIsNone(result['profiles'])
        first,second=[json.loads((Path(run)/'job.json').read_bytes()) for run in result['runs']]
        self.assertEqual([row['stages'] for row in result['project_settings']],[config['stages'],other['stages']])
        self.assertNotIn(project_config.NAME,[row['id'] for row in first['documents']])
        self.assertEqual([x['profiles']['nl0']['reasoning_effort'] for x in (first,second)],['xhigh','low'])
        self.assertEqual(first['max_concurrency'],3)
        self.assertEqual(json.loads(project_config.for_run(first).read_bytes()),config)
        (left/project_config.NAME).write_text('{"new project edit":true}')
        jobs.validate(first)
        with project_config.use(project_config.for_run(first)):
            self.assertEqual(runtime_config.model_profile('audit-a-global')['reasoning_effort'],'max')
        project_config.for_run(first).write_text('{}')
        with self.assertRaisesRegex(ValueError,'changed'):jobs.validate(first)

    def test_nested_input_explicit_override_and_existing_file_bytes(self):
        path,config=self.project('nested')
        config['timeouts']['case_seconds']=79
        config['lean']['max_heartbeats']=8723
        original=json.dumps(config,indent=4)+'\n'
        (path/project_config.NAME).write_text(original)
        sub=path/'source';sub.mkdir();proof=sub/'proof.md';proof.write_text('Proof text.')
        self.assertEqual(project_config.directory_for(proof),path)
        result=self.invoke('prepare',proof,'--project-dir',path,'--track','nl0',
                           '--target','Every integer n is equal to itself.','--nl0-effort','medium')
        job=json.loads((Path(result['runs'][0])/'job.json').read_bytes())
        self.assertFalse((sub/project_config.NAME).exists())
        self.assertEqual((path/project_config.NAME).read_text(),original)
        self.assertEqual(job['time_budget_seconds'],79)
        with project_config.use(project_config.for_run(job)):
            self.assertEqual(runtime_config.model_profile('nl0-authoring')['reasoning_effort'],'medium')
            self.assertEqual(runtime_config.native_heartbeats(),8723)

    def test_phase_overrides_only_apply_inside_their_real_execution_stage(self):
        path,config=self.project('stages')
        expected=dict(zip(project_config.STAGES,['max','medium','low','high','xhigh','ultra']))
        config['stages']={k:{'reasoning_effort':v} for k,v in expected.items()}
        file=path/project_config.NAME;file.write_text(json.dumps(config))
        effort=lambda role:runtime_config.model_profile(role)['reasoning_effort']
        def observe(stage):
            def read(*args,**kwargs):
                with ThreadPoolExecutor(1) as workers:
                    self.assertEqual(workers.submit(copy_context().run,effort,'proof').result(),expected[stage])
                raise StopIteration
            return read
        with project_config.use(file):
            self.assertEqual({stage:effort(stage) for stage in project_config.STAGES},expected)
            for stage,role in [('nl0','nl0-authoring'),('audit-a','audit-a-packet-replay'),
                               ('nl02lean','proof'),('audit-b','audit-b-semantic-review')]:
                self.assertEqual(effort(role),expected[stage])
            with patch('role_sessions.Sessions',side_effect=observe('2basis')),self.assertRaises(StopIteration):
                basis.run({'root':str(path)},None,None)
            with patch.object(b2lean.workflow,'bound',side_effect=observe('b2lean')),self.assertRaises(StopIteration):
                b2lean.finish(path,path/'out',context={},intermediate={})
            self.assertEqual(effort('proof'),expected['nl02lean'])

    def test_concurrent_creation_reuses_one_complete_file_and_rejects_unknown_stages(self):
        with ThreadPoolExecutor(6) as pool:
            files=list(pool.map(lambda _:project_config.open_project(self.root,profiles=harness_support.PROFILES),range(12)))
        self.assertTrue(all(item==files[0] for item in files))
        file=self.root/project_config.NAME
        config=files[0];config['stages']['typo']={}
        file.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError,'stage'):self.invoke('init-config',self.root)
        self.assertEqual(json.loads(file.read_bytes()),config)
        self.assertEqual(list(self.root.iterdir()),[file])
        config['stages']={'audit-a':{'reasoning_effort':[]}}
        file.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError,'reasoning effort'):self.invoke('init-config',self.root)
