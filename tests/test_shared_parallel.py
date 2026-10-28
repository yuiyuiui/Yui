import harness_support
from lean_fixtures import shared_fixture as fixture, LIFT, SUP
import copy
import hashlib
from pathlib import Path
import re
import shutil
import tempfile
import threading
import unittest

HERE = harness_support.LEAN
import ir
import scheduler
import shared_lemmas as shared





class SharedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix='shared-tests-'))
        cls.cpath, cls.plan = fixture(cls.base/'input')
        cls.store = shared.Store(cls.base/'store')
        cls.registration = cls.store.admit(cls.cpath, cls.plan, 'T001', LIFT)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base)

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix='shared-control-'))

    def tearDown(self):
        shutil.rmtree(self.temp)

    def test_complete_signature_and_physical_module(self):
        value = shared.obligation(self.cpath, self.plan, 'T001')
        entry, receipt = self.store.lookup(value)
        self.assertEqual(receipt['status'], 'HIT')
        self.assertIn('(h_H001 : ∀ r, ‖F r‖ = ‖G r‖)', entry['full_type'])
        self.assertIn('DEVELOPMENT_OWNER_REVIEW', str(entry['provenance']))
        module = self.store.root/'Shared'/f"L{entry['key']}.lean"
        self.assertTrue(module.is_file())
        self.assertEqual(ir.digest(module), entry['module_sha256'])
        self.assertEqual(entry['audit_b'], 'NOT_PERFORMED')

    def test_verified_reuse_is_recompiled_and_assembled(self):
        value = shared.obligation(self.cpath, self.plan, 'T001')
        entry, _ = self.store.lookup(value)
        body = shared.reuse_body(entry, value)
        result = ir.check(self.cpath, self.plan, {'T001': body, 'T002': SUP})
        self.assertEqual(result['exit_code'], 0, result['stdout'])

    def test_alpha_renamed_binders_compile_without_rewriting_proof(self):
        cpath, plan = fixture(self.temp/'renamed')
        c = ir.load(cpath)
        def rename(value):
            if isinstance(value, str):
                return re.sub(r'\b(iota|F|G)\b', lambda m: {'iota':'idx','F':'U','G':'V'}[m[0]], value)
            if isinstance(value, list): return [rename(x) for x in value]
            if isinstance(value, dict): return {k:rename(v) for k,v in value.items()}
            return value
        # Route and NL source remain identical; only Lean binders are renamed.
        new_c = rename(c)
        new_c['shared_obligations'][0]['route'] = c['shared_obligations'][0]['route']
        ir.write(cpath, new_c)
        plan = rename(plan)
        plan['contract_sha256'] = ir.digest(cpath)
        value = shared.obligation(cpath, plan, 'T001')
        entry, receipt = self.store.lookup(value)
        self.assertEqual(receipt['status'], 'HIT')
        result = ir.check(cpath, plan, {'T001':shared.reuse_body(entry, value)}, only='T001')
        self.assertEqual(result['exit_code'], 0, result['stdout'])

    def test_changed_header_environment_or_condition_misses(self):
        original = shared.obligation(self.cpath, self.plan, 'T001')
        variants = []
        v = copy.deepcopy(original); v['header'] += '\n-- changed definitions\n'; variants.append(v)
        v = copy.deepcopy(original); v['pins']['mathlib_commit'] = 'changed'; variants.append(v)
        v = copy.deepcopy(original); v['inputs'].append({'id':'H002','binder':'h_H002','type':'False'}); variants.append(v)
        v = copy.deepcopy(original); v['target'] = 'F = G'; variants.append(v)
        for value in variants:
            self.assertEqual(self.store.lookup(value)[1]['status'], 'MISS')

    def test_wrong_representation_misses(self):
        value = shared.obligation(self.cpath, self.plan, 'T001')
        value['representations'] = [{'object':'O001','view':'V999','expression':'F'}]
        self.assertEqual(self.store.lookup(value)[1]['status'], 'MISS')

    def test_module_mutation_invalidates_entry(self):
        shutil.copytree(self.store.root, self.temp/'store')
        store = shared.Store(self.temp/'store')
        value = shared.obligation(self.cpath, self.plan, 'T001')
        key = shared.signature_key(value)
        (store.root/'Shared'/f'L{key}.lean').write_text('changed')
        self.assertEqual(store.lookup(value)[1]['reason'], 'INVALIDATED_ARTIFACT')

    def test_changed_receipt_invalidates_entry(self):
        shutil.copytree(self.store.root, self.temp/'store')
        store = shared.Store(self.temp/'store')
        value = shared.obligation(self.cpath, self.plan, 'T001')
        key = shared.signature_key(value)
        (store.root/'objects'/key/'verification.json').write_text('{}')
        self.assertEqual(store.lookup(value)[1]['reason'], 'INVALIDATED_ARTIFACT')

    def test_failed_or_placeholder_proof_cannot_be_admitted(self):
        for body in ('sorry', 'exact h_H001'):
            with self.assertRaises(ir.Invalid):
                self.store.admit(self.cpath, self.plan, 'T001', body)

    def test_same_key_does_not_overwrite_first_proof(self):
        before = self.store.snapshot()
        receipt = self.store.admit(self.cpath, self.plan, 'T001', LIFT)
        self.assertEqual(receipt['status'], 'ALREADY_PRESENT')
        self.assertEqual(self.store.snapshot(), before)

    def test_fake_check_receipt_cannot_cover_different_proof(self):
        with self.assertRaisesRegex(ir.Invalid, 'verification/proof mismatch'):
            self.store.admit(self.cpath, self.plan, 'T001', LIFT, {
                'status':'LOCAL-PROOF-CHECKED','exit_code':0,'lean_sha256':'changed'})

    def test_forged_receipt_cannot_hide_custom_module_axiom(self):
        cpath, plan = fixture(self.temp/'custom-axiom')
        c = ir.load(cpath)
        c['header'] += '\naxiom injected (iota : Type) (F G : iota → ℂ) (h : ∀ r, ‖F r‖ = ‖G r‖) : ∀ r, ‖F r‖ₑ = ‖G r‖ₑ\n'
        ir.write(cpath, c)
        plan['contract_sha256'] = ir.digest(cpath)
        proof = 'exact injected iota F G h_H001'
        rendered = ir.render(cpath, plan, {'T001':proof}, only='T001')
        forged = {'status':'LOCAL-PROOF-CHECKED','exit_code':0,'axioms':[],
                  'lean_sha256':hashlib.sha256(rendered.encode()).hexdigest(),
                  'contract_sha256':ir.digest(cpath),'wall_seconds':0}
        with self.assertRaisesRegex(ir.Invalid, 'unpermitted shared module axioms'):
            shared.Store(self.temp/'forged-store').admit(cpath, plan, 'T001', proof, forged)


class RepresentationTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix='repr-tests-'))
        self.cpath, self.plan = fixture(self.temp, objects=True)

    def tearDown(self): shutil.rmtree(self.temp)

    def test_views_are_local_and_bridge_is_explicit(self):
        packet = ir.local_packet(self.cpath, self.plan, 'T002')
        self.assertEqual(packet['representations'][0]['view'], 'V002')
        self.assertEqual(packet['bridges'][0]['input'], 'T001')
        self.assertEqual(packet['shared_inputs'][0]['lemma_id'], 'L001')
        self.assertEqual([p['id'] for p in packet['inputs']], ['T001'])
        result = ir.check(self.cpath, self.plan, types_only=True)
        self.assertEqual(result['exit_code'], 0, result['stdout'])

    def test_unlisted_bridge_rejected(self):
        self.plan['steps'][1]['bridges'][0]['input'] = 'H001'
        with self.assertRaisesRegex(ir.Invalid, 'not a direct input'):
            ir.validate(self.cpath, self.plan)

    def test_unknown_view_rejected(self):
        self.plan['steps'][0]['representations'][0]['view'] = 'V999'
        with self.assertRaisesRegex(ir.Invalid, 'unregistered representation'):
            ir.validate(self.cpath, self.plan)

    def test_bad_expression_view_type_fails_lean(self):
        self.plan['steps'][0]['representations'][0]['expression'] = 'F'
        self.assertNotEqual(ir.check(self.cpath, self.plan, types_only=True)['exit_code'], 0)

    def test_unreviewed_or_new_mathematical_export_rejected(self):
        for field, value in [('status','PENDING'), ('classification','new_mathematical_fact')]:
            c = ir.load(self.cpath)
            c['shared_obligations'][0]['review'][field] = value
            ir.write(self.cpath, c)
            with self.assertRaises(ir.Invalid): ir.contract(self.cpath)
            self.cpath, self.plan = fixture(self.temp, objects=True)

    def test_changed_export_interface_rejected(self):
        self.plan['steps'][0]['inputs'] = []
        with self.assertRaisesRegex(ir.Invalid, 'shared interface mismatch'):
            ir.validate(self.cpath, self.plan)


class ParallelTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix='scheduler-tests-'))
        self.cpath, self.plan = fixture(self.temp/'input')

    def tearDown(self): shutil.rmtree(self.temp)

    def test_dependent_bodies_run_concurrently_with_conditional_inputs(self):
        barrier = threading.Barrier(2, timeout=15)
        packets = {}
        def worker(sid, packet):
            packets[sid] = packet
            barrier.wait()
            return {'proof': LIFT if sid == 'T001' else SUP}
        report = scheduler.prove_graph(self.cpath, self.plan, worker, max_workers=2)
        self.assertEqual(report['status'], 'FRAGMENT_ASSEMBLED', report)
        self.assertEqual([x['id'] for x in packets['T002']['inputs']], ['T001'])
        intervals = [(j['started_offset_seconds'], j['finished_offset_seconds']) for j in report['jobs']]
        self.assertLess(max(x[0] for x in intervals), min(x[1] for x in intervals))
        self.assertNotIn('h_T001', report['fresh_verifier']['stdout'].split('depends on axioms')[0])

    def test_warm_cache_skips_producer_and_still_checks_root(self):
        store = shared.Store(self.temp/'store')
        store.admit(self.cpath, self.plan, 'T001', LIFT)
        called = []
        def worker(sid, packet):
            called.append(sid)
            return {'proof':SUP}
        report = scheduler.prove_graph(self.cpath, self.plan, worker, store=store)
        self.assertEqual(report['status'], 'FRAGMENT_ASSEMBLED', report)
        self.assertEqual(called, ['T002'])
        self.assertEqual(report['cache_hits'], 1)

    def test_duplicate_shared_jobs_have_one_producer(self):
        duplicate = copy.deepcopy(self.plan['steps'][0]); duplicate['id'] = 'T003'
        root = self.plan['steps'][1]
        root['inputs'] = ['T001', 'T003']
        self.plan['steps'].insert(1, duplicate)
        calls = []
        def worker(sid, packet):
            calls.append(sid)
            return {'proof':LIFT if sid == 'T001' else SUP}
        report = scheduler.prove_graph(self.cpath, self.plan, worker, store=shared.Store(self.temp/'store'))
        self.assertEqual(report['status'], 'FRAGMENT_ASSEMBLED', report)
        self.assertEqual(report['deduplicated_jobs'], 1)
        self.assertEqual(sorted(calls), ['T001','T002'])

    def test_failed_producer_cannot_leave_its_claim_in_final_theorem(self):
        def worker(sid, packet):
            return {'proof':None if sid == 'T001' else SUP}
        report = scheduler.prove_graph(self.cpath, self.plan, worker)
        self.assertEqual(report['status'], 'GRAPH_UNFINISHED')
        self.assertIsNone(report['assembly'])
        self.assertEqual(set(report['proofs']), {'T002'})

    def test_bad_representation_cannot_launch_workers(self):
        cpath, plan = fixture(self.temp/'invalid-view', objects=True)
        plan['steps'][0]['representations'][0]['expression'] = 'F'
        calls = []
        with self.assertRaisesRegex(ir.Invalid, 'representation expressions failed Lean'):
            scheduler.prove_graph(cpath, plan, lambda sid,packet:calls.append(sid))
        self.assertEqual(calls, [])

    def test_invalid_cache_falls_back_without_erasing_evidence(self):
        store = shared.Store(self.temp/'store')
        store.admit(self.cpath, self.plan, 'T001', LIFT)
        module = next((store.root/'Shared').glob('*.lean'))
        module.write_text('damaged artifact')
        def worker(sid, packet): return {'proof':LIFT if sid == 'T001' else SUP}
        report = scheduler.prove_graph(self.cpath, self.plan, worker, store=store)
        self.assertEqual(report['status'], 'FRAGMENT_ASSEMBLED', report)
        self.assertEqual(module.read_text(), 'damaged artifact')
        self.assertEqual(report['cache_hits'], 0)


if __name__ == '__main__': unittest.main()
