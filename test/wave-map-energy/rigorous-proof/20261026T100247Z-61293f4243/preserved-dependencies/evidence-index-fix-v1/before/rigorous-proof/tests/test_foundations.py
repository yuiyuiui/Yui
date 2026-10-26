"""Fixed language metadata is not a source of author-granted theorems."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import foundations


class FixedFoundationTests(unittest.TestCase):
    def test_omitted_metadata_is_bound_without_adding_a_mathematical_verdict(self):
        logic={'classical':True,'rules':['direct']}
        foundations.bind_author(logic)
        foundations.require_canonical(logic)
        self.assertEqual(logic['calculations'],list(foundations.CALCULATIONS))
        self.assertNotIn('verdict',logic)
        self.assertEqual(logic['primitives'],list(foundations.PRIMITIVES.values()))

    def test_an_author_cannot_add_mvt_or_other_theorem_permissions(self):
        for request in [['The mean value theorem is permitted.'],['equality','Fubini'],[{}]]:
            logic={'classical':False,'rules':['direct'],'calculations':request}
            before=deepcopy(logic)
            with self.assertRaisesRegex(ValueError,'FOUNDATION_AUTHORITY'):
                foundations.bind_author(logic)
            self.assertEqual(logic,before)

    def test_project_objects_and_local_capture_cannot_hide_in_primitives(self):
        for symbol in ['u_t','1_Q','ParameterDependentSpace']:
            with self.assertRaisesRegex(ValueError,'FOUNDATION_PRIMITIVE'):
                foundations.bind_author({'primitives':[{'symbol':symbol,'type':'function',
                    'meaning':'A task object depending on a locally chosen Q.'}]})

    def test_standard_selection_binds_exact_meaning_and_rejects_a_conflict(self):
        logic={'primitives':[{'symbol':'0'}]}
        foundations.bind_author(logic)
        self.assertEqual(logic['primitives'],list(foundations.PRIMITIVES.values()))
        bad=deepcopy(logic);bad['primitives'][0]['meaning']='The desired nonzero solution.'
        with self.assertRaisesRegex(ValueError,'conflicts'):foundations.bind_author(bad)

    def test_packet_permissions_are_controller_owned_even_for_legacy_notes(self):
        old={'calculations':['FTC, MVT and compactness are all permitted.'], 'primitives':[]}
        packet=foundations.packet_logic(old)
        self.assertNotIn('FTC',repr(packet))
        self.assertEqual(len(packet['calculations']),len(foundations.CALCULATIONS))
        self.assertIn('FTC',repr(old))
        with self.assertRaises(ValueError):foundations.require_canonical(old)


if __name__=='__main__':unittest.main()
