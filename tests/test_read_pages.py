"""Read pagination preserves content and does not relax mutation boundaries."""
import harness_support
import unittest
import json

from clean_stage import read_page
from artifact_validation import own_text_lines
from read_views import read_json, read_batch, MAX_TOOL_BYTES


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

    def test_batch_reads_declared_fragments_with_individual_coordinates(self):
        documents={'packet.json':json.dumps({'input':False,'output':'exact'}),
                   'source.txt':'first\nsecond\nthird'}
        page=read_batch(documents,[{'id':'packet.json','pointer':'/input'},
                                   {'id':'source.txt','start':2,'end':3}])
        self.assertIs(page['results'][0]['value'],False)
        self.assertEqual(page['results'][1]['text'],'2: second\n3: third')
        self.assertFalse(page['has_more'])

    def test_large_batch_has_lossless_fragment_and_request_continuations(self):
        original='中文🙂\\"'*16000
        documents={'packet.json':json.dumps({'proof':original}), 'small.txt':'actual next document'}
        page=read_batch(documents,[{'id':'packet.json','pointer':'/proof'},
                                  {'id':'small.txt','start':1,'end':1}])
        self.assertLessEqual(len(json.dumps(page,ensure_ascii=False).encode()),MAX_TOOL_BYTES)
        self.assertEqual(page['next_request'],1)
        self.assertTrue(page['results'][0]['has_more'])
        parts=[page['results'][0]['value']];offset=page['results'][0]['next_offset']
        while offset is not None:
            value=read_batch(documents,[{'id':'packet.json','pointer':'/proof','offset':offset}])['results'][0]
            parts.append(value['value']);offset=value['next_offset']
        self.assertEqual(''.join(parts),original)
        last=read_batch(documents,[{'id':'small.txt','start':1,'end':1}])
        self.assertIn('actual next document',last['results'][0]['text'])

    def test_batch_cannot_read_undeclared_inputs_or_hide_invalid_coordinates(self):
        documents={'safe.txt':'one','safe.json':'{"x":1}'}
        for requests in [[],[{'id':'safe.txt','start':1,'end':1}]*9,
                         [{'id':'../private.txt','start':1,'end':1}],
                         [{'id':'safe.json','pointer':'/x','start':1,'end':1}],
                         [{'id':'safe.txt','start':0,'end':1}]]:
            with self.subTest(requests=requests),self.assertRaises(ValueError):
                read_batch(documents,requests)


if __name__=='__main__':unittest.main()
