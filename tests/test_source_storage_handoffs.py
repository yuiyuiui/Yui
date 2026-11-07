"""Cross-stage evidence isolation, bounded downloads and independent source copies."""
import harness_support
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from controller_common import bind
import nl0
import nl0_review_loop
import source_access
import source_cache
import staging_storage


class StorageHandoffs(unittest.TestCase):
    def test_only_declared_source_survives_a_repair_snapshot(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            source=root/'source';dst=root/'review'
            nl0_review_loop.copy_source(harness_support.CORE/'tests/fixtures/closed-addition',source)
            (source/'prior-private-logs').mkdir()
            (source/'prior-private-logs/build.olean').write_bytes(b'disposable')
            (source/'audit-a.json').write_text('outdated')
            nl0_review_loop.copy_source(source,dst)
            self.assertFalse((dst/'prior-private-logs').exists())
            self.assertFalse((dst/'audit-a.json').exists())
            nl0.validate(dst/'nl0.json',dst/'spec.json')
            evidence=next(p for p in dst.rglob('*') if p.is_file() and p.name not in {'spec.json','nl0.json'})
            before=bind(source/evidence.relative_to(dst))
            evidence.write_text('private edits')
            self.assertEqual(bind(before['path']),before)

    def test_shared_download_is_fetched_once_and_eviction_preserves_original_evidence(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);cache=root/'cache';downloads=[]
            first=threading.Event()
            def download(dst,url,*,browser):
                downloads.append(url);first.set()
                doc=dst/'original.html';doc.write_bytes(b'public source')
                text=dst/'body.txt';text.write_text('public source')
                return {'url':url,'status':'READABLE','document':bind(doc),'text':bind(text)}
            def role(name,url):
                return source_cache.fetch(root/name,url,False,cache,download)
            with ThreadPoolExecutor(max_workers=2) as pool:
                a=pool.submit(role,'first','https://example.org/one')
                first.wait(5)
                b=pool.submit(role,'second','https://example.org/one')
                a,b=a.result(),b.result()
            self.assertEqual(len(downloads),1)
            self.assertNotEqual(a['document']['path'],b['document']['path'])
            Path(b['text']['path']).write_text('private modification')
            self.assertEqual(bind(a['text']['path']),a['text'])
            with patch.object(source_cache,'LIMIT',1):
                role('third','https://example.org/two')
            self.assertFalse(list(cache.glob('entry-*')))
            self.assertEqual(bind(a['document']['path']),a['document'])

    def test_bounded_stream_rejects_oversize_truncation_and_disk_pressure(self):
        class Response(BytesIO):
            def __init__(self,data,declared):
                super().__init__(data);self.headers={'Content-Length':declared}
        with tempfile.TemporaryDirectory() as raw,patch.object(source_access,'LIMIT',20):
            self.assertEqual(source_access.read_bytes(Response(b'proof','5'),raw),b'proof')
            for data,length in [(b'x','99'),(b'x','4'),(b'x'*25,None)]:
                with self.subTest(length=length),self.assertRaises(ValueError):
                    source_access.read_bytes(Response(data,length),raw)
            with patch.object(staging_storage,'available',side_effect=[10**12,0]),self.assertRaises(staging_storage.StoragePressure):
                source_access.read_bytes(Response(b'proof',None),raw)
