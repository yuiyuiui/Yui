"""Catalog retrieval/import controls use synthetic metadata, never user library data."""
import harness_support
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import library_catalog as c


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.catalog=self.root/'library';self.catalog.mkdir()
        self.source=self.root/'mathlib/Mathlib/Tests/Catalog.lean'
        self.source.parent.mkdir(parents=True);self.source.write_text('-- synthetic test fixture, not a proof\n')
        self.lock={'lean':{'version':'fixture'},'mathlib':{'rev':'fixture','local_path':str(self.root/'mathlib')}}
        self.env=patch.dict(os.environ,{'YUI_LIBRARY_ROOT':str(self.catalog)});self.env.start()
        self.runtime=patch.object(c,'load_lock',return_value=self.lock);self.runtime.start()
        def row(name):
            return {'declaration':name,'module':'Mathlib.Tests.Catalog','declaration_kind':'theorem',
                    'signature':'@'+name+' : True','axioms':'synthetic fixture',
                    'source_path':'Mathlib/Tests/Catalog.lean',
                    'source_sha256':hashlib.sha256(self.source.read_bytes()).hexdigest(),
                    'mathlib_commit':'fixture'}
        self.report={'probe_version':1,'exit_code':0,'lean_version':'fixture','mathlib_commit':'fixture',
                     'sources':{'M001':row('Catalog.alpha'),'M002':row('Catalog.beta')},
                     'result':{'exit_code':0,'wall_seconds':1}}
        self.receipt=self.root/'library-sources.json'
        self.receipt.write_text(json.dumps(self.report))

    def tearDown(self):
        self.runtime.stop();self.env.stop();self.temp.cleanup()

    def populate(self):
        c.add(self.receipt,'M001',['integral','finite','sum'])
        c.add(self.receipt,'M002',['module','dimension'])

    def test_exact_and_keyword_discovery_preserve_native_metadata(self):
        self.populate()
        rows=c.lookup('Catalog.alpha')['sources']
        self.assertEqual([r['declaration'] for r in rows],['Catalog.alpha'])
        self.assertEqual(rows[0]['match_kind'],'exact_declaration')
        self.assertEqual(rows[0]['signature'],'@Catalog.alpha : True')
        self.assertEqual(c.lookup('the integral of a finite sum')['sources'][0]['declaration'],'Catalog.alpha')
        self.assertEqual(c.lookup('module dimension')['sources'][0]['declaration'],'Catalog.beta')

    def test_unmatched_terms_do_not_invent_sources_and_order_is_stable(self):
        self.populate()
        self.assertEqual(c.lookup('quokka-xylophone-unmatched')['sources'],[])
        entries=c.load()['entries']
        a=c.ranked(entries,'integral dimension');b=c.ranked(list(reversed(entries)),'integral dimension')
        self.assertEqual([r[0]['declaration'] for r in a],[r[0]['declaration'] for r in b])

    def test_absent_optional_catalog_allows_native_probe_fallback(self):
        self.assertEqual(c.lookup('Catalog.alpha')['sources'],[])
        self.assertIsNone(c.cached_probe('M003','Catalog.alpha',None,self.lock))
        self.assertEqual(c.catalog_files(),[])
        self.assertEqual(c.binding()['files'],[])

    def test_default_is_inside_installed_skill_and_environment_can_override(self):
        with patch.object(c,'CORE',self.root/'installed/renamed skill root'):
            with patch.dict(os.environ):
                os.environ.pop('YUI_LIBRARY_ROOT',None)
                self.assertEqual(c.catalog_path(),self.root/'installed/renamed skill root/library/foundations.json')
            self.assertEqual(c.catalog_path(),self.catalog/'foundations.json')

    def test_importing_two_ids_from_one_receipt_preserves_bytes_and_mapping(self):
        self.populate()
        entries=c.load()['entries']
        self.assertEqual(len(entries),2)
        self.assertEqual({entry['source_id'] for entry in entries},{'M001','M002'})
        self.assertEqual(len(list((self.catalog/'evidence').glob('*.json'))),1)
        self.assertEqual(c.evidence_path(entries[0]).read_bytes(),self.receipt.read_bytes())
        for entry in entries:
            self.assertEqual(c.verified(entry)[0]['declaration'],entry['declaration'])

    def test_repeat_import_merges_tags_without_overwriting_evidence(self):
        self.populate();before={p:p.read_bytes() for p in (self.catalog/'evidence').glob('*')}
        self.assertEqual(c.add(self.receipt,'M001',['integral'])['status'],'ALREADY_PRESENT')
        self.assertEqual(c.add(self.receipt,'M001',['linearity'])['status'],'TAGS_UPDATED')
        self.assertEqual(len(c.load()['entries']),2)
        self.assertIn('linearity',c.load()['entries'][0]['tags'])
        self.assertEqual(before,{p:p.read_bytes() for p in before})

    def test_bad_probe_or_wrong_pin_is_not_imported(self):
        for field,value in [('exit_code',1),('mathlib_commit','wrong')]:
            report={**self.report,field:value};self.receipt.write_text(json.dumps(report))
            with self.assertRaises(ValueError):c.add(self.receipt,'M001',['integral'])
            self.assertFalse(c.catalog_path().exists())

    def test_conflicting_metadata_requires_explicit_review(self):
        self.populate();before=c.catalog_path().read_bytes()
        self.report['sources']['M001']['signature']='@Catalog.alpha : False'
        self.receipt.write_text(json.dumps(self.report))
        with self.assertRaisesRegex(ValueError,'differs'):c.add(self.receipt,'M001',['integral'])
        self.assertEqual(c.catalog_path().read_bytes(),before)
        self.assertFalse((self.catalog/'.maintenance.lock').exists())

    def test_changed_evidence_or_source_blocks_reuse(self):
        self.populate();entry=c.load()['entries'][0]
        evidence=c.evidence_path(entry);original=evidence.read_bytes()
        evidence.write_bytes(original+b'\n')
        with self.assertRaisesRegex(ValueError,'evidence changed'):c.lookup('Catalog.alpha')
        evidence.write_bytes(original);self.source.write_text('-- modified source\n')
        with self.assertRaisesRegex(ValueError,'identity changed'):c.lookup('Catalog.alpha')

    def test_unindexed_notes_are_not_frozen_and_evidence_cannot_escape(self):
        self.populate();(self.catalog/'README.md').write_text('Private maintenance note')
        (self.catalog/'unindexed.json').write_text('{"private":true}')
        self.assertEqual(len(c.catalog_files()),2)
        entry=c.load()['entries'][0];entry['evidence']['path']='../outside.json'
        with self.assertRaisesRegex(ValueError,'escapes'):c.verified(entry)

    def test_stage_uses_its_own_snapshot_after_catalog_maintenance(self):
        from clean_stage import ArtifactStage
        self.populate();worker=ArtifactStage(self.root/'stage','EXPLICIT_TASK',phase='control',library=False)
        try:
            snapshot=worker.logs/'harness-snapshot/library'
            self.assertTrue((snapshot/'foundations.json').is_file())
            manifest=json.loads((worker.logs/'execution-manifest.json').read_text())
            self.assertEqual(manifest['library_catalog'],c.binding())
            c.catalog_path().write_text('{"version":1,"entries":[]}')
            self.assertEqual(c.lookup('Catalog.alpha')['sources'],[])
            with c.use_library(snapshot):
                self.assertEqual(c.lookup('Catalog.alpha')['sources'][0]['declaration'],'Catalog.alpha')
        finally:
            shutil.rmtree(worker.work)

    def test_snapshot_preserves_a_catalog_relative_evidence_alias(self):
        from clean_stage import ArtifactStage
        self.populate();value=c.load();original=c.evidence_path(value['entries'][0])
        alias=self.catalog/'evidence/alias.json';alias.symlink_to(original.name)
        for entry in value['entries']:entry['evidence']['path']='evidence/alias.json'
        c.write_catalog(value)
        worker=ArtifactStage(self.root/'alias-stage','EXPLICIT_TASK',phase='control',library=False)
        try:
            snapshot=worker.logs/'harness-snapshot/library'
            self.assertTrue((snapshot/'evidence/alias.json').is_file())
            with c.use_library(snapshot):
                self.assertEqual(c.lookup('Catalog.alpha')['sources'][0]['declaration'],'Catalog.alpha')
        finally:
            shutil.rmtree(worker.work)


if __name__=='__main__':unittest.main()
