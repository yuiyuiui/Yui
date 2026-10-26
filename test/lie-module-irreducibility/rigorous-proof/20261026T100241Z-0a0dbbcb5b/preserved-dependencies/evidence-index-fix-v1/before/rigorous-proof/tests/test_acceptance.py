"""Shared author/audit coverage and authority binding, without model calls."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import acceptance
import nl0


class AcceptanceTests(unittest.TestCase):
    def test_executable_review_sets_come_from_one_authority(self):
        contract=acceptance.current()
        self.assertEqual(nl0.CHECKS,contract.check_ids('inference'))
        self.assertEqual(nl0.closure.CLOSURE_CHECKS,contract.check_ids('closure')|{'packet_replay'})
        self.assertNotIn('packet_replay',contract.rows)
        grouped=contract.author_groups()
        self.assertEqual(set().union(*(set(v) for v in grouped.values())),set(contract.rows))
        self.assertEqual(grouped['output_notes'],['output','statement_closure'])
        self.assertIn('Conditional packet replay has a different input boundary',contract.section)
        self.assertIn('these statements are conditional premises',contract.section)

    def test_actual_requirement_change_changes_binding_without_changing_coverage(self):
        before=acceptance.current()
        after=acceptance.AcceptanceContract(acceptance.SOURCE.read_text().replace(
            'No theorem needs to be re-proved','An adequate permitted theorem need not be re-proved'))
        self.assertEqual(set(before.rows),set(after.rows))
        self.assertNotEqual(before.section_sha256,after.section_sha256)
        self.assertNotEqual(before.metadata(),after.metadata())

    def test_missing_or_duplicate_authority_and_unknown_groups_are_rejected(self):
        text=acceptance.SOURCE.read_text()
        for broken in [text.replace(acceptance.BEGIN,''),text+acceptance.BEGIN,
                       text.replace('| `target` | package |','| `target` | unknown |')]:
            with self.assertRaises(ValueError):acceptance.AcceptanceContract(broken)
        line=next(line for line in text.splitlines() if line.startswith('| `target`'))
        with self.assertRaisesRegex(ValueError,'duplicate'):
            acceptance.AcceptanceContract(text.replace(line,line+'\n'+line))


if __name__=='__main__':unittest.main()
