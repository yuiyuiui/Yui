"""Source query output preservation; no Lean subprocess or model is needed."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("probe_preservation",ROOT/"scripts/probe_mathlib.py")
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ProbeEvidencePreservation(unittest.TestCase):
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


if __name__=="__main__":
    unittest.main()
