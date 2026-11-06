"""Compiler-generated declaration names are not basis registry identifiers."""
import harness_support
from basis_fixtures import artifact,dependency,checked_context
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import basis
import basis_review
import ir


class NativeBasisDependencies(unittest.TestCase):
    def test_exact_names_nested_helpers_cycles_and_import_boundaries(self):
        def row(*deps,imported=False):return {'direct_constants':list(deps),'imported':imported}
        declarations={
            'YuiBasis.B001':row('YuiBasis.B001._simp_1','YuiBasis.B002','Library.theorem'),
            'YuiBasis.B001._simp_1':row('YuiBasis.B001._simp_1._proof_1','YuiBasis.B0010'),
            'YuiBasis.B001._simp_1._proof_1':row('YuiBasis.B003','YuiBasis.B001._simp_1'),
            'Library.theorem':row('YuiBasis.B004',imported=True),
            'YuiBasis.B0010':row(),
            'YuiBasis.B002':row('YuiBasis.B005')}
        names={'YuiBasis.'+key:key for key in ('B001','B002','B003','B004','B005')}
        self.assertEqual(basis_review.native_basis_dependencies('YuiBasis.B001',declarations,names),['B002','B003'])

    def test_helper_edges_invalidate_connected_review_reuse(self):
        items={r['id']:r for r in artifact(dependency('B001'),dependency('B002',2),dependency('B003',2))['dependencies']}
        items['B002']['native_dependencies']=['B001']
        packet={'items':items,'target':'synthetic target'}
        first=basis_review.item_keys(packet)
        changed=deepcopy(packet);changed['items']['B001']['statement']='changed native dependency statement'
        second=basis_review.item_keys(changed)
        self.assertEqual({k for k in first if first[k]!=second[k]},{'B001','B002'})
        changed['items']['B002']['native_dependencies']=['_simp_1']
        with self.assertRaisesRegex(ValueError,'Unknown basis dependency IDs: _simp_1'):
            basis_review.item_keys(changed)

    def test_actual_native_simp_helper_reaches_review_and_receipt_readback(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            typ='∀ a b : ℕ, a + b = b + a'
            value=artifact(dependency('B001',typ=typ,proof='intro a b; exact Nat.add_comm a b'),
                dependency('B002',2,typ=typ,proof='intro a b; simpa only [← YuiBasis.B001]'))
            context=checked_context(root,value)
            native=ir.load(Path(context['native']['path']).parent/'elaborated.json')
            self.assertTrue(any(r['name'].startswith('YuiBasis.B002.') for r in native['dependencies']['declarations']))
            packet=ir.load(root/'review/inputs'/basis_review.PACKET)
            self.assertEqual(packet['items']['B002']['native_dependencies'],['B001'])
            self.assertEqual(set(basis_review.item_keys(packet)),{'B001','B002'})
            self.assertEqual(basis.verify_context(context),value)


if __name__=='__main__':unittest.main()
