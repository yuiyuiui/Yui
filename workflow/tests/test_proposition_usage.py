"""Both NL0 entries deliver actual consumers and unambiguous manuscript locations."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'blocks'))
import foundation_handoff
import proposition_usage


class Usage(unittest.TestCase):
    reference = {'document': 'inputs/paper.md', 'locator': 'Lemma 2.1'}
    theorem = 'Every finite graph has this bound. It is used in Lemma 2.1.'

    def test_direct_outline(self):
        graph = {'propositions': [
            {'id': 'H001', 'statement': self.theorem, 'usage': {'references': [self.reference]}},
            {'id': 'N001', 'statement': 'An intermediate fact.'}, {'id': 'P', 'statement': 'The goal.'}],
            'inferences': [{'id': 'R001', 'inputs': ['H001'], 'output': 'N001'},
                           {'id': 'R002', 'inputs': ['H001', 'N001'], 'output': 'P'}]}
        proposition_usage.bind(graph, {'inputs/paper.md'})
        self.assertEqual(graph['propositions'][0]['usage'],
                         {'inferences': ['R001', 'R002'], 'references': [self.reference]})
        self.assertEqual(graph['propositions'][-1]['usage'], {'inferences': [], 'references': []})
        self.assertEqual(graph['propositions'][0]['statement'], self.theorem)
        proposition_usage.bind(graph, {'inputs/paper.md'}, check=True)

    def test_foundation_allocated_after_review(self):
        registry = {'dependencies': [{'id': 'B107', 'category': 3, 'port': None,
                     'statement': self.theorem, 'usage': {'references': [self.reference]}}],
                    'global_graph': {'propositions': [{'id': 'P', 'statement': 'The goal.'}],
                    'inferences': [{'id': 'R001', 'inputs': [], 'output': 'P', 'basis': ['B107']}]}}
        original = deepcopy(registry)
        graph, labels = foundation_handoff.numbered_seed(registry)
        self.assertEqual(labels, {'B107': 'E107'})
        proposition_usage.bind(graph, {'inputs/paper.md'})
        self.assertEqual(graph['propositions'][-1], {'id': 'E107', 'statement': self.theorem,
                         'usage': {'inferences': ['R001'], 'references': [self.reference]}})
        graph['propositions'][-1]['kind'] = 'external'
        foundation_handoff.attach(registry, graph, labels)
        graph['propositions'][-1]['usage']['references'].clear()
        with self.assertRaisesRegex(ValueError, 'E107.*reviewed document locations of B107'):
            foundation_handoff.by_port(registry, graph)
        self.assertEqual(registry, original)

    def test_usage_neither_creates_edges_nor_resolves_ambiguous_citations(self):
        for bad in [{'inferences': ['R999']},
                    {'references': ['Lemma 2.1']},
                    {'references': [{'document': 'inputs/other.md', 'locator': 'Lemma 2.1'}]},
                    {'references': [{'document': 'inputs/paper.md', 'locator': ' '}]},
                    {'references': [self.reference, self.reference]}]:
            graph = {'propositions': [{'id': 'P', 'usage': bad}], 'inferences': []}
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, 'USAGE.*P'):
                proposition_usage.bind(graph, {'inputs/paper.md'})


if __name__ == '__main__':
    unittest.main()
