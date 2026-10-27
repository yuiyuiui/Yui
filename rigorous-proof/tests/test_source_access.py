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
            with patch.object(access,'fetch',side_effect=fetch) as getter:
                result=access.search(tmp,'synthetic paper title',engine='all')
            self.assertEqual(result['candidates'],['https://arxiv.org/pdf/1234.5678','https://arxiv.org/abs/1234.5678'])
            self.assertEqual([r['status'] for r in result['attempts']],['READABLE','BROWSER_REQUIRED'])
            self.assertIn('arxiv.org',getter.call_args_list[0].args[1])
            self.assertIn('google.com',getter.call_args_list[1].args[1])

    def test_arxiv_is_default_and_a_versioned_id_retains_its_pdf_locator(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(access,'public_url'),patch.object(access.urllib.request,'build_opener') as builder:
            response=builder.return_value.open.return_value.__enter__.return_value
            response.status=200;response.geturl.return_value='https://arxiv.org/abs/1234.5678v2'
            response.read.return_value=b'<a href="/pdf/1234.5678v2">PDF</a>'
            result=access.search(tmp,'1234.5678v2')
            self.assertEqual(result['engine'],'arxiv')
            self.assertEqual(result['candidates'],['https://arxiv.org/pdf/1234.5678v2'])
            self.assertEqual(builder.return_value.open.call_args.args[0].full_url,'https://arxiv.org/abs/1234.5678v2')
            self.assertEqual(builder.return_value.open.call_count,1)

    def test_scihub_requires_a_doi_and_google_candidates_are_not_verdicts(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(access,'public_url'),patch.object(access.urllib.request,'build_opener') as builder:
            response=builder.return_value.open.return_value.__enter__.return_value
            response.status=200;response.geturl.return_value='https://sci-hub.box/10.1234/example'
            response.read.return_value=b'<meta name="citation_pdf_url" content="/storage/original.pdf"><p>doi:10.1234/example.</p>'
            result=access.search(tmp,'https://doi.org/10.1234/example',engine='scihub')
            self.assertEqual(result['candidates'],['https://sci-hub.box/storage/original.pdf'])
            self.assertEqual(result['doi_candidates'],['10.1234/example'])
            self.assertNotIn('verified',result)
            before=builder.return_value.open.call_count
            with self.assertRaisesRegex(ValueError,'actual DOI'):access.search(tmp,'Guessed paper title',engine='scihub')
            self.assertEqual(builder.return_value.open.call_count,before)
        self.assertEqual(access.dois('(10.1234/foo). https://doi.org/10.1234/foo%28bar%29'),
                         ['10.1234/foo','10.1234/foo(bar)'])
        self.assertEqual(access.source_links('https://www.google.com/search?q=paper',
            ['/url?q=https%3A%2F%2Fexample.org%2Fpaper.pdf','https:///']),['https://example.org/paper.pdf'])

    def test_browser_readback_binds_rendered_and_original_bytes_and_caches(self):
        from controller_common import bind
        def capture(directory,url,stem):
            raw=Path(directory)/(stem+'.browser-document');raw.write_bytes(b'<title>Paper</title><object data="/original.pdf"></object>')
            shot=Path(directory)/(stem+'.png');shot.write_bytes(b'synthetic screenshot bytes')
            return {'raw':raw.read_bytes(),'document':bind(raw),'screenshot':bind(shot),'text':'Actual rendered paper page.',
                    'links':['https://example.org/original.pdf'],'status':'READABLE','final_url':url,
                    'normal_verification':True,'browser_runtime':{'test_only':True}}
        with tempfile.TemporaryDirectory() as tmp,patch.object(access,'public_url'),patch('source_browser.capture',side_effect=capture) as browser:
            first=access.read(tmp,'https://example.org/paper',browser=True)
            self.assertEqual(first['origin'],'controller_browser');self.assertTrue(first['normal_verification'])
            self.assertIn('rendered',first['content'])
            self.assertEqual(first['links'],['https://example.org/original.pdf'])
            second=access.read(tmp,'https://example.org/paper',browser=True)
            self.assertEqual(first['record'],second['record']);browser.assert_called_once()
            Path(first['screenshot']['path']).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'changed'):access.read(tmp,'https://example.org/paper',browser=True)

    def test_browser_absence_and_errors_preserve_real_failed_receipts(self):
        for error,status in [(FileNotFoundError('missing runtime'),'BROWSER_UNAVAILABLE'),
                             (ValueError('browser driver error'),'BROWSER_ERROR')]:
            with self.subTest(status=status),tempfile.TemporaryDirectory() as tmp,patch.object(access,'public_url'),\
                 patch('source_browser.capture',side_effect=error):
                result=access.read(tmp,'https://example.org',browser=True)
                self.assertEqual(result['status'],status);self.assertTrue(access.failed_access(result))
                self.assertNotIn('content',result)
                self.assertTrue(Path(result['record']['path']).is_file())

    def test_chinese_challenge_and_google_sorry_are_not_readable_sources(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(access,'public_url'),patch.object(access.urllib.request,'build_opener') as builder:
            response=builder.return_value.open.return_value.__enter__.return_value
            response.status=200;response.geturl.return_value='https://www.google.com/sorry/index'
            response.read.return_value='<p>我们的系统检测到异常流量</p>'.encode()
            result=access.read(tmp,'https://www.google.com/search?q=paper')
            self.assertEqual(result['status'],'HUMAN_ACCESS_REQUIRED');self.assertNotIn('content',result)

    def test_browser_installation_never_ignores_invalid_explicit_override(self):
        import source_browser
        with patch.dict(source_browser.os.environ,{'YUI_SOURCE_BROWSER_NODE':'/does/not/exist'}):
            with self.assertRaisesRegex(FileNotFoundError,'YUI_SOURCE_BROWSER_NODE'):source_browser.installation()

    def test_frozen_runtime_includes_actual_browser_driver(self):
        from controller_common import runtime_bindings,bind
        import source_browser
        self.assertIn(bind(Path(source_browser.__file__).with_suffix('.mjs')),runtime_bindings())

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
                with patch.object(access,'public_url'),patch('source_browser.capture',side_effect=FileNotFoundError('synthetic missing browser')):
                    search=stage.dispatch('search_external_sources',{'query':'10.1234/example','engine':'scihub','browser':True})
                self.assertEqual(search['engine'],'scihub')
                self.assertEqual(search['attempts'][0]['status'],'BROWSER_UNAVAILABLE')
                reference=search['access_records'][0]
                self.assertFalse(Path(reference['path']).is_absolute())
                self.assertEqual(bind(stage.validator.directory/reference['path'])['sha256'],reference['sha256'])
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
