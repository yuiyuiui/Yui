"""Byte-preservation controls; no model or mathematical proof is run."""
import harness_support

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import trace_archive as a


class TraceArchiveTests(unittest.TestCase):
    def test_round_trip_is_exact_and_changed_evidence_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo=Path(temporary);subprocess.run(['git','init','-q',str(repo)],check=True)
            (repo/'.gitignore').write_text('__pycache__/\n')
            root=repo/'paper/rigorous-proof/run';stage=root/'neutral/stage';stage.mkdir(parents=True)
            raw=stage/'requests.jsonl';original=(b'{"neutral_control":true}\n'*1000)+b'last line\n';raw.write_bytes(original)
            (stage/'result.json').write_text('{"status":"UNFINISHED"}\n')
            live=root/'live/stage';live.mkdir(parents=True);(live/'requests.jsonl').write_bytes(original)
            report=a.pack(root,minimum=100)
            self.assertEqual(report['archives'],1);self.assertEqual(raw.read_bytes(),original)
            self.assertEqual(a.pack(root,minimum=100)['archives'],1)
            raw.unlink();a.restore(root/'trace-archives.json');self.assertEqual(raw.read_bytes(),original)
            raw.write_bytes(b'changed; preserve me')
            with self.assertRaisesRegex(ValueError,'Preserve changed'):a.restore(root/'trace-archives.json')
            self.assertEqual(raw.read_bytes(),b'changed; preserve me')

    def test_restore_rejects_an_outside_path_before_reading_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);manifest=root/'trace-archives.json'
            manifest.write_text(json.dumps({'archives':[{'raw':'../../outside','archive':'trace.gz'}]}))
            with self.assertRaisesRegex(ValueError,'escapes'):a.restore(manifest)


if __name__=='__main__':unittest.main()
