import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'evaluate_cognition.py'
spec = importlib.util.spec_from_file_location('evaluate_cognition_test', SCRIPT)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


class CognitiveBenchmarkTests(unittest.TestCase):
    def test_splits_are_disjoint(self):
        self.assertEqual(benchmark.validate_splits(), {'train': 15, 'val': 8, 'test': 15})

    def test_grading_and_missing_are_not_fabricated(self):
        first = benchmark.load_cases('test')[0]
        self.assertTrue(benchmark.grade(first, 'Resultado verificado: **3**.'))
        self.assertFalse(benchmark.grade(first, 'Resultado verificado: **4**.'))
        partial = benchmark.score_responses('test', [{'id': first['id'], 'answer': '3'}])
        self.assertEqual(partial['evaluated'], 1)
        self.assertEqual(partial['missing'], 14)
        self.assertEqual(partial['accuracy'], 1)
        self.assertIsNone(partial['median_provider_tokens_per_second'])
        self.assertIsNone(partial['memory'])


if __name__ == '__main__':
    unittest.main()
