"""Source query output preservation; no Lean subprocess or model is needed."""
import harness_support
import importlib.util
import json
import os
import tempfile
import unittest
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from artifact_validation import reserve_probe_directory, signature_probe, run_lean


ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("probe_preservation",ROOT/"nl0/scripts/probe_mathlib.py")
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ProbeEvidencePreservation(unittest.TestCase):
    def test_standalone_query_timeout_returns_actual_partial_output(self):
        with tempfile.TemporaryDirectory() as raw, patch.object(probe,'native_timeout',return_value=.2):
            result=probe.run_probe([sys.executable,'-u','-c',
                'import time;print("query-started",flush=True);time.sleep(30)'],raw)
        self.assertEqual(result.returncode,124)
        self.assertIn('query-started',result.stdout)
        self.assertIn('Lean timeout',result.stderr)

    def test_existing_frozen_receipt_is_not_overwritten_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)
            (out/"library-sources.json").write_text('{"exit_code":0}\n')
            before=(out/"library-sources.json").read_bytes()
            with self.assertRaisesRegex(FileExistsError,"EVIDENCE-EXISTS"):
                probe.prepare_output(out)
            self.assertEqual((out/"library-sources.json").read_bytes(),before)

    def test_explicit_replacement_archives_and_revokes_old_success(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)
            values={"library-sources.json":'{"exit_code":0}\n',"library-probe.log":"old signatures\n","LibraryProbe.lean":"import Mathlib\n","registry.json":"[]\n"}
            for name,text in values.items():(out/name).write_text(text)
            archive=Path(probe.prepare_output(out,replace=True))
            for name,text in values.items():
                self.assertEqual((archive/name).read_text(),text)
                self.assertFalse((out/name).exists())
            self.assertEqual(len(json.loads((archive/"manifest.json").read_text())["files"]),4)

    def test_new_query_output_is_allowed_without_replacement(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"fresh"
            self.assertIsNone(probe.prepare_output(out))
            self.assertTrue(out.is_dir())


class ProbeAllocationTests(unittest.TestCase):
    def test_inherited_and_failed_queries_keep_bytes_while_new_reservation_skips_them(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for number in [1,2,3]:
                path=root/'library'/f'M021-{number:04d}';path.mkdir(parents=True)
                (path/'library-sources.json').write_text('Frozen evidence '+str(number))
            before={p:p.read_bytes() for p in root.rglob('*.json')}
            output=reserve_probe_directory(root,'M021',1)
            self.assertEqual(output.name,'M021-0004')
            self.assertEqual(before,{p:p.read_bytes() for p in before})
            self.assertEqual(list(output.iterdir()),[])

    def test_concurrent_reservations_are_distinct_even_with_identical_counters(self):
        with tempfile.TemporaryDirectory() as d:
            with ThreadPoolExecutor(max_workers=8) as pool:
                outputs=list(pool.map(lambda _:reserve_probe_directory(d,'M021',1),range(16)))
            self.assertEqual(len(set(outputs)),16)
            self.assertTrue(all(p.is_dir() for p in outputs))

    def test_unsafe_occupied_paths_and_unrelated_io_errors_are_not_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);parent=root/'library';parent.mkdir();leaf=parent/'M021-0001'
            leaf.write_text('Unexpected file')
            with self.assertRaisesRegex(OSError,'unsafe occupied'):reserve_probe_directory(root,'M021',1)
            leaf.unlink();leaf.symlink_to(root,target_is_directory=True)
            with self.assertRaisesRegex(OSError,'unsafe occupied'):reserve_probe_directory(root,'M021',1)
            leaf.unlink();parent.rmdir();parent.symlink_to(root,target_is_directory=True)
            with self.assertRaisesRegex(OSError,'symbolic link'):reserve_probe_directory(root,'M021',1)
        with patch.object(Path,'mkdir',side_effect=PermissionError(13,'Denied')):
            with self.assertRaises(PermissionError):reserve_probe_directory('/unused','M021',1)

    def test_returned_receipt_uses_the_actual_new_directory_not_the_counter_hint(self):
        # Synthetic native output tests path routing, not theorem validity.
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);old=root/'library/M021-0001';old.mkdir(parents=True)
            receipt=old/'library-sources.json';receipt.write_text('Immutable old receipt')
            source=root/'Mathlib/Synthetic.lean';source.parent.mkdir();source.write_text('-- Synthetic source fixture\n')
            output='\n'.join(['RESOLVED_NAME:M021:Synthetic.new_query','RESOLVED_MODULE:M021:Mathlib.Synthetic',
                'BEGIN_SIGNATURE:M021','@Synthetic.new_query : True','BEGIN_AXIOMS:M021',
                "'Synthetic.new_query' depends on axioms: []",'END_SOURCE:M021',''])
            lock={'lean':{'version':'synthetic'},'mathlib':{'local_path':str(root),'rev':'f'*40}}
            with patch('runtime_config.require_environment'),patch('artifact_validation.load_lock',return_value=lock), \
                 patch('artifact_validation.run_lean',return_value={
                     'exit_code':0,'stdout':output,'stderr':'','wall_seconds':0}) as native:
                result=signature_probe(root,'M021','Synthetic.new_query',None,1)
            native.assert_called_once()
            self.assertEqual(result['evidence'][0]['path'],'library/M021-0002/library-sources.json')
            self.assertEqual(receipt.read_text(),'Immutable old receipt')
            report=json.loads((root/result['evidence'][0]['path']).read_text())
            self.assertEqual(report['sources']['M021']['declaration'],'Synthetic.new_query')
            self.assertEqual(report['result']['stdout'],output)


class NativeProbeWithoutCatalog(unittest.TestCase):
    def test_former_catalog_example_is_queried_in_the_selected_environment_each_time(self):
        from runtime_config import load_lock
        lock=load_lock()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);obsolete=root/'obsolete';obsolete.mkdir()
            (obsolete/'foundations.json').write_text('Stale data must not affect a native query.')
            with patch.dict(os.environ,{'YUI_LIBRARY_ROOT':str(obsolete)}), \
                 patch('artifact_validation.run_lean',wraps=run_lean) as native:
                first=signature_probe(root/'case','M001','isCompact_singleton',None,1)
                second=signature_probe(root/'case','M001','isCompact_singleton',None,1)
            self.assertEqual(native.call_count,2)
            self.assertNotEqual(first['evidence'],second['evidence'])
            for result in (first,second):
                self.assertNotIn('metadata_reused',result)
                report=json.loads((root/'case'/result['evidence'][0]['path']).read_text())
                self.assertEqual(report['lean_version'],lock['lean']['version'])
                self.assertEqual(report['mathlib_commit'],lock['mathlib']['rev'])
                self.assertEqual(report['result']['exit_code'],0)
                self.assertIn('BEGIN_SIGNATURE:M001',report['result']['stdout'])
                self.assertTrue(report['sources']['M001']['axioms'])
                self.assertTrue((root/'case'/result['evidence'][0]['path']).with_name('library-probe.log').is_file())


if __name__=="__main__":
    unittest.main()
