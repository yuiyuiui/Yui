"""Exact installs, safe reuse and owned partial recovery; no network/download."""
import harness_support
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import lean_environment as environments


class ScientificInstallation(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.root=self.base/'installation'
        self.elan=self.base/'elan';self.elan.write_text('Synthetic tool');self.elan.chmod(0o700)
        self.request={'version':1,'lean_version':'4.99.0','mathlib_ref':'v4.99.0'}
        self.selected={'fixture':'verified by the controlled resolver'}

    def partial(self):
        self.root.mkdir();(self.root/'.yui-install.json').write_text(json.dumps(self.request))
        library=self.root/'mathlib';library.mkdir();(library/'.git').mkdir()
        (library/'lean-toolchain').write_text('leanprover/lean4:v4.99.0\n')
        (library/'lake-manifest.json').write_text('{"packages":[]}')
        lean=self.base/'.elan/toolchains/leanprover--lean4---v4.99.0';lean.mkdir(parents=True)
        return library

    def test_verified_existing_pair_never_reinstalls_or_downloads_metadata(self):
        self.root.mkdir()
        with patch.object(environments,'resolve',return_value=self.selected) as resolve, \
             patch('urllib.request.urlopen') as network,patch.object(environments.subprocess,'run') as commands:
            self.assertEqual(environments.install(mathlib_ref='v4.99.0',directory=self.root),self.selected)
        network.assert_not_called();commands.assert_not_called()
        self.assertEqual(resolve.call_args.kwargs['mathlib_ref'],'v4.99.0')

    def test_conflicting_unowned_directory_is_preserved(self):
        self.root.mkdir();file=self.root/'user.txt';file.write_text('Preserve')
        with patch.object(environments,'resolve',side_effect=environments.SelectionRequired()), \
             patch.object(environments.subprocess,'run') as commands:
            with self.assertRaisesRegex(ValueError,'Preserve'):
                environments.install(lean_version='4.99.0',mathlib_ref='v4.99.0',directory=self.root)
        commands.assert_not_called();self.assertEqual(file.read_text(),'Preserve')
        self.assertEqual(list(self.root.iterdir()),[file])

    def test_owned_partial_reuses_clone_and_runs_only_locked_cache_command(self):
        library=self.partial();before=(library/'lake-manifest.json').read_bytes()
        with patch.object(Path,'home',return_value=self.base), \
             patch.object(environments.shutil,'which',return_value=str(self.elan)), \
             patch.object(environments,'_git',return_value='v4.99.0'), \
             patch.object(environments,'_elan_lean',return_value=self.base/'.elan/toolchains/leanprover--lean4---v4.99.0'), \
             patch.object(environments.subprocess,'check_output',return_value='Lean (version 4.99.0, fixture)'), \
             patch.object(environments,'resolve',side_effect=[environments.SelectionRequired(),self.selected]), \
             patch.object(environments.subprocess,'run') as commands:
            result=environments.install(lean_version='4.99.0',mathlib_ref='v4.99.0',directory=self.root)
        self.assertEqual(result,self.selected)
        calls=[row.args[0] for row in commands.call_args_list]
        self.assertFalse(any('clone' in row or 'update' in row for row in calls))
        self.assertTrue(any(row[-3:]==['exe','cache','get'] for row in calls))
        self.assertFalse(any('toolchain' in row for row in calls))
        self.assertEqual((library/'lake-manifest.json').read_bytes(),before)

    def test_failed_cache_retains_owned_inputs_for_a_repeat(self):
        self.partial()
        def command(argv,**kwargs):
            if argv[-3:]==['exe','cache','get']:
                raise subprocess.CalledProcessError(1,argv)
        with patch.object(Path,'home',return_value=self.base), \
             patch.object(environments.shutil,'which',return_value=str(self.elan)), \
             patch.object(environments,'_git',return_value='v4.99.0'), \
             patch.object(environments,'_elan_lean',return_value=self.base/'.elan/toolchains/leanprover--lean4---v4.99.0'), \
             patch.object(environments.subprocess,'check_output',return_value='Lean (version 4.99.0, fixture)'), \
             patch.object(environments,'resolve',side_effect=environments.SelectionRequired()), \
             patch.object(environments.subprocess,'run',side_effect=command):
            with self.assertRaises(subprocess.CalledProcessError):
                environments.install(lean_version='4.99.0',mathlib_ref='v4.99.0',directory=self.root)
        self.assertEqual(json.loads((self.root/'.yui-install.json').read_text()),self.request)
        self.assertTrue((self.root/'mathlib/.git').is_dir())

    def test_elan_query_uses_the_requested_toolchain_and_custom_home(self):
        binary=self.base/'custom elan home/toolchain/bin/lean';binary.parent.mkdir(parents=True)
        binary.write_text('Synthetic compiler path')
        with patch.dict('os.environ',{'ELAN_HOME':str(self.base/'custom elan home')}), \
             patch.object(environments.subprocess,'check_output',side_effect=[
                 'leanprover/lean4:v4.99.0\n',str(binary)+'\n']) as query:
            self.assertEqual(environments._elan_lean(str(self.elan),'leanprover/lean4:v4.99.0'),binary.parent.parent)
        self.assertEqual(query.call_args.kwargs['env']['ELAN_TOOLCHAIN'],'leanprover/lean4:v4.99.0')
        self.assertEqual(query.call_args.kwargs['env']['ELAN_HOME'],str(self.base/'custom elan home'))

    def test_missing_toolchain_query_never_invokes_the_auto_installing_which_command(self):
        with patch.object(environments.subprocess,'check_output',return_value='no installed toolchains\n') as query:
            self.assertIsNone(environments._elan_lean(str(self.elan),'leanprover/lean4:v4.99.0'))
        self.assertEqual(query.call_count,1)
        self.assertEqual(query.call_args.args[0],[str(self.elan),'toolchain','list'])

    def test_missing_lean_is_installed_once_before_cache_recovery(self):
        self.partial();lean=self.base/'.elan/toolchains/leanprover--lean4---v4.99.0'
        with patch.object(Path,'home',return_value=self.base), \
             patch.object(environments.shutil,'which',return_value=str(self.elan)), \
             patch.object(environments,'_git',return_value='v4.99.0'), \
             patch.object(environments,'_elan_lean',side_effect=[None,lean]), \
             patch.object(environments.subprocess,'check_output',return_value='Lean (version 4.99.0, fixture)'), \
             patch.object(environments,'resolve',side_effect=[environments.SelectionRequired(),self.selected]), \
             patch.object(environments.subprocess,'run') as commands:
            environments.install(lean_version='4.99.0',mathlib_ref='v4.99.0',directory=self.root)
        installs=[row.args[0] for row in commands.call_args_list if 'toolchain' in row.args[0]]
        self.assertEqual(installs,[[str(self.elan),'toolchain','install','leanprover/lean4:v4.99.0']])

    def test_lean_version_is_derived_from_mathlib_not_assumed_equal_to_its_tag(self):
        with patch.object(Path,'home',return_value=self.base), \
             patch.object(environments,'resolve',side_effect=environments.SelectionRequired()), \
             patch('urllib.request.urlopen',return_value=io.BytesIO(b'leanprover/lean4:v4.99.1\n')), \
             patch.object(environments.shutil,'which',return_value=None):
            with self.assertRaises(environments.SelectionRequired):
                environments.install(mathlib_ref='v4.99.0',directory=self.root)
        self.assertEqual(json.loads((self.root/'.yui-install.json').read_text())['lean_version'],'4.99.1')

    def test_redirected_ownership_marker_is_rejected(self):
        self.root.mkdir();outside=self.base/'outside.json';outside.write_text(json.dumps(self.request))
        (self.root/'.yui-install.json').symlink_to(outside)
        with self.assertRaisesRegex(ValueError,'ownership'):
            environments.install(lean_version='4.99.0',mathlib_ref='v4.99.0',directory=self.root)


if __name__=='__main__':unittest.main()
