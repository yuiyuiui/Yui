"""Read pagination preserves content and does not relax mutation boundaries."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from clean_stage import read_page
from artifact_validation import own_text_lines


class ReadPageTests(unittest.TestCase):
    def test_large_read_can_be_reconstructed_without_skips_or_duplicates(self):
        lines=['Line '+str(n) for n in range(1,604)]
        text='\n'.join(lines);start=1;actual=[]
        while start is not None:
            page=read_page(text,start,10000)
            actual.extend(row.split(': ',1)[1] for row in page['text'].splitlines())
            self.assertLessEqual(page['end']-page['start']+1,250)
            start=page['next_start']
        self.assertEqual(actual,lines)

    def test_short_and_empty_documents_have_explicit_end_of_input(self):
        page=read_page('one\ntwo',1,1000)
        self.assertEqual((page['end'],page['total_lines'],page['has_more']),(2,2,False))
        self.assertIsNone(page['next_start'])
        self.assertEqual(read_page('',1,250)['text'],'')

    def test_bad_starts_and_noninteger_ranges_stay_invalid(self):
        for start,end in ((0,5),(3,2),(True,3),(1,False),(4,8)):
            with self.subTest(start=start,end=end),self.assertRaises(ValueError):
                read_page('one\ntwo',start,end)

    def test_own_draft_edit_view_keeps_its_exact_range_policy(self):
        with self.assertRaises(ValueError):own_text_lines('\n'.join(['x']*300),1,300)


if __name__=='__main__':unittest.main()
