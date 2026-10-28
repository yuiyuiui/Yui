"""Read pagination preserves content and does not relax mutation boundaries."""
import harness_support
import unittest
import json

from clean_stage import read_page
from artifact_validation import own_text_lines
from read_views import read_json, MAX_TOOL_BYTES


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

    def test_megabyte_single_line_and_unicode_resume_without_loss(self):
        original='中文🙂\\"'*180000
        start,column=1,0;parts=[]
        while start is not None:
            page=read_page(original,start,start+249,column=column,metadata={'id':'large.json'})
            self.assertLessEqual(len(json.dumps(page,ensure_ascii=False).encode()),MAX_TOOL_BYTES)
            parts.append(page['text'].split(': ',1)[1])
            start,column=page['next_start'],page['next_column']
        self.assertEqual(''.join(parts),original)

    def test_json_pointer_pages_huge_string_and_exposes_container_keys(self):
        value='中文🙂\\"'*180000;document={'P':{'actual/type':value,'other':'small'}}
        page=read_json(document,'/P')
        self.assertEqual(page['view'],'keys');self.assertIn('actual/type',page['keys'])
        offset=0;parts=[]
        while offset is not None:
            page=read_json(document,'/P/actual~1type',offset=offset,metadata={'id':'packet.json'})
            self.assertLessEqual(len(json.dumps(page,ensure_ascii=False).encode()),MAX_TOOL_BYTES)
            parts.append(page['value']);offset=page['next_offset']
        self.assertEqual(''.join(parts),value)

    def test_all_json_keys_can_be_listed_and_scalars_preserve_their_type(self):
        document={str(i):'x'*500 for i in range(600)}
        offset=0;keys=[]
        while offset is not None:
            page=read_json(document,offset=offset,limit=100)
            keys.extend(page['keys']);offset=page['next_offset']
        self.assertEqual(keys,list(document))
        self.assertIs(read_json({'flag':False},'/flag')['value'],False)
        with self.assertRaises(ValueError):read_json(document,'/bad~2escape')


if __name__=='__main__':unittest.main()
