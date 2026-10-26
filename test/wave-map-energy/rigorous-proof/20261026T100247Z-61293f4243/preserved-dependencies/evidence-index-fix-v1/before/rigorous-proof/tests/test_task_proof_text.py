"""Literal task-line bindings; no mathematical acceptance is produced."""
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from task_proof_text import materialize


class TaskProofTextTests(unittest.TestCase):
    def graph(self,request):
        return {'inferences':[{'argument':[{'text':request}]}]}

    def test_exact_frozen_lines_and_hashes_become_plain_canonical_text(self):
        source='Header.\nFirst identity.\r\nSecond identity.\n'
        graph=self.graph({'from_task':'proof.md','start_line':2,'end_line':3})
        bindings=materialize(graph,{'proof.md':source})
        text='First identity.\r\nSecond identity.\n'
        self.assertEqual(graph['inferences'][0]['argument'][0]['text'],text)
        self.assertEqual(bindings[0]['text_sha256'],hashlib.sha256(text.encode()).hexdigest())
        self.assertEqual(bindings[0]['input_sha256'],hashlib.sha256(source.encode()).hexdigest())
        self.assertNotIn('verdict',bindings[0])

    def test_no_undeclared_file_or_external_input_can_be_read(self):
        for identifier in ['/etc/passwd','../other','old-NL0.json']:
            with self.assertRaisesRegex(ValueError,'same-stage task'):
                materialize(self.graph({'from_task':identifier,'start_line':1,'end_line':1}),{'proof.md':'Proof.'})

    def test_ranges_fields_and_empty_proof_text_are_checked(self):
        for start,end in [(True,1),(0,1),(1,2),(2,1),(1.0,1)]:
            with self.assertRaises(ValueError):
                materialize(self.graph({'from_task':'proof.md','start_line':start,'end_line':end}),{'proof.md':'One line.'})
        with self.assertRaises(ValueError):
            materialize(self.graph({'from_task':'proof.md','start_line':1,'end_line':1,'extra':'instruction'}),{'proof.md':'One line.'})
        with self.assertRaises(ValueError):
            materialize(self.graph({'from_task':'proof.md','start_line':1,'end_line':1}),{'proof.md':'  \n'})

    def test_plain_text_and_nonproof_fields_are_never_automatically_rewritten(self):
        value={'propositions':[{'statement':{'from_task':'proof.md','start_line':1,'end_line':1}}],
               'inferences':[{'argument':[{'text':'Original proof text.'}]}]}
        original=deepcopy(value)
        self.assertEqual(materialize(value,{'proof.md':'Other text.'}),[])
        self.assertEqual(value,original)

    def test_a_bad_later_range_does_not_partially_materialize_the_document(self):
        value={'inferences':[{'argument':[
            {'text':{'from_task':'proof.md','start_line':1,'end_line':1}},
            {'text':{'from_task':'proof.md','start_line':2,'end_line':2}}]}]}
        original=deepcopy(value)
        with self.assertRaises(ValueError):materialize(value,{'proof.md':'One line.'})
        self.assertEqual(value,original)

    def test_source_text_is_copied_as_data_without_execution_or_semantic_repair(self):
        text='A literal $(not_a_command) and an unproved claim.\n'
        graph=self.graph({'from_task':'proof.md','start_line':1,'end_line':1})
        materialize(graph,{'proof.md':text})
        self.assertEqual(graph['inferences'][0]['argument'][0]['text'],text)

    def test_selected_given_is_copied_exactly_and_not_inferred(self):
        request={'from_task':'problem.md','start_line':2,'end_line':2}
        spec={'hypotheses':[{'id':'H001','statement':request,'origin':'problem.md:2'}]}
        graph=self.graph('H001 supplies the given equality.')
        bindings=materialize(graph,{'problem.md':'Given.\na=b.\r\nProve b=a.\n'},spec=spec)
        self.assertEqual(spec['hypotheses'][0]['statement'],'a=b.\r\n')
        self.assertEqual(spec['hypotheses'][0]['origin'],'problem.md:2')
        self.assertEqual(bindings[0]['path'],'/spec/hypotheses/0/statement')
        self.assertNotIn('verdict',bindings[0])

    def test_combined_hypothesis_definition_proof_copy_is_atomic(self):
        request={'from_task':'problem.md','start_line':1,'end_line':1}
        spec={'hypotheses':[{'statement':deepcopy(request)}],
              'definitions':[{'definition':deepcopy(request)}]}
        graph=self.graph(dict(request,end_line=2));original=deepcopy((spec,graph))
        with self.assertRaisesRegex(ValueError,'TASK_TEXT'):
            materialize(graph,{'problem.md':'Only line.\n'},spec=spec)
        self.assertEqual((spec,graph),original)


if __name__=='__main__':unittest.main()
