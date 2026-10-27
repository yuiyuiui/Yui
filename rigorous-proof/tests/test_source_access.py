"""Read-only source transport failures are explicit, not source-verification passes."""
import harness_support
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch
import source_access as access
import shutil


class SourceAccessTests(unittest.TestCase):
    def test_private_addresses_and_embedded_credentials_are_rejected(self):
        for url in ['http://example.org','https://user:pass@example.org','https://example.org:8000']:
            with self.assertRaises(ValueError):access.public_url(url)
        with patch.object(access.socket,'getaddrinfo',return_value=[(0,0,0,'',('127.0.0.1',443))]):
            with self.assertRaisesRegex(ValueError,'Private'):access.public_url('https://example.org')

    def test_http_error_is_recorded_without_claiming_a_readable_source(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(access,'public_url'),patch.object(access.urllib.request,'build_opener') as builder:
            builder.return_value.open.side_effect=urllib.error.HTTPError('https://example.org',403,'Forbidden',{},None)
            result=access.fetch(tmp,'https://example.org')
            self.assertEqual(result['status'],'HTTP_ERROR');self.assertEqual(result['http_status'],403)
            self.assertNotIn('content',result);self.assertTrue(Path(result['record']['path']).is_file())

    def test_mixed_dns_uses_public_addresses_only(self):
        addresses=[(0,0,0,'',('2001::1',443)),(0,0,0,'',('8.8.8.8',443))]
        with patch.object(access.socket,'getaddrinfo',return_value=addresses),patch.object(access.socket,'create_connection') as connect:
            access.public_url('https://example.org')
            access.public_connection(('example.org',443))
            connect.assert_called_once_with(('8.8.8.8',443),30,None)

    def test_human_verification_page_is_not_used_as_primary_text(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(access,'public_url'),patch.object(access.urllib.request,'build_opener') as builder:
            response=builder.return_value.open.return_value.__enter__.return_value
            response.geturl.return_value='https://example.org';response.status=200
            for body,status in [(b'<p>Verify you are human</p>','HUMAN_ACCESS_REQUIRED'),
                                (b'<a href="/httpservice/retry/enablejs">Enable JavaScript</a>','BROWSER_REQUIRED')]:
                response.read.return_value=body
                result=access.read(tmp,'https://example.org')
                self.assertEqual(result['status'],status);self.assertNotIn('content',result)

    def test_readable_source_reuses_bound_bytes_and_rejects_cache_tampering(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(access,'public_url'),patch.object(access.urllib.request,'build_opener') as builder:
            response=builder.return_value.open.return_value.__enter__.return_value
            response.read.return_value=b'<p>Complete primary text.</p>'
            response.geturl.return_value='https://example.org';response.status=200
            first=access.read(tmp,'https://example.org',limit=8)
            second=access.read(tmp,'https://example.org',offset=8,limit=8)
            self.assertEqual(first['status'],'READABLE');self.assertEqual(first['record'],second['record'])
            self.assertTrue(first['has_more']);self.assertNotEqual(first['content'],second['content'])
            self.assertEqual(builder.return_value.open.call_count,1)
            Path(first['text']['path']).write_text('tampered')
            with self.assertRaisesRegex(ValueError,'changed'):access.read(tmp,'https://example.org')

    def test_search_retains_google_failure_and_other_engine_locators(self):
        with tempfile.TemporaryDirectory() as tmp:
            html=Path(tmp)/'search.html'
            html.write_text('<a href="https://arxiv.org/abs/1234.5678">Paper</a><a href="https:///">Broken</a>')
            def fetch(directory,url):
                return {'status':'BROWSER_REQUIRED' if 'google.com' in url else 'READABLE',
                        'document':{'path':str(html)},'record':{'path':'test-search-record','sha256':'synthetic'}}
            with patch.object(access,'fetch',side_effect=fetch):result=access.search(tmp,'synthetic paper title')
            self.assertEqual(result['candidates'],['https://arxiv.org/abs/1234.5678'])
            self.assertEqual([r['status'] for r in result['attempts']],['BROWSER_REQUIRED','READABLE'])

    def test_author_read_tool_returns_usable_case_relative_evidence(self):
        from clean_stage import ArtifactStage
        from controller_common import bind
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'problem.txt';source.write_text('Synthetic supplied theorem.')
            manifest=root/'inputs.json';manifest.write_text(json.dumps({'inputs':[
                {'id':'problem.txt','path':'problem.txt','sha256':bind(source)['sha256']}]}))
            stage=ArtifactStage(root/'stage','Synthetic control.',phase='nl0-authoring',kind='nl0',inputs=manifest)
            try:
                with patch.object(access,'public_url'),patch.object(access.urllib.request,'build_opener') as builder:
                    response=builder.return_value.open.return_value.__enter__.return_value
                    response.read.return_value=b'<p>Complete source statement.</p>'
                    response.geturl.return_value='https://example.org';response.status=200
                    result=stage.dispatch('read_external_source',{'url':'https://example.org'})
                self.assertEqual(result['status'],'READABLE')
                self.assertEqual(len(result['evidence']),3)
                self.assertEqual(len(result['primary_evidence_candidates']),2)
                for row in result['evidence']:
                    self.assertFalse(Path(row['path']).is_absolute())
                    self.assertEqual(bind(stage.validator.directory/row['path'])['sha256'],row['sha256'])
            finally:shutil.rmtree(stage.work)

    def test_corrupt_pdf_retains_download_and_records_failed_extraction(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(access,'public_url'),patch.object(access.urllib.request,'build_opener') as builder:
            response=builder.return_value.open.return_value.__enter__.return_value
            response.read.return_value=b'%PDF-1.7\ninvalid';response.geturl.return_value='https://example.org/paper.pdf';response.status=200
            with patch('target_selection.text',side_effect=ValueError('broken document')):
                result=access.read(tmp,'https://example.org/paper.pdf')
            self.assertEqual(result['status'],'UNAVAILABLE')
            self.assertTrue(Path(result['document']['path']).is_file())
            self.assertIn('broken document',result['reason'])


if __name__=='__main__':unittest.main()
