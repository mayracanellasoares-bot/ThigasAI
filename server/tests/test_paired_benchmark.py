import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from compare_cognition import compare


class PairedBenchmarkTests(unittest.TestCase):
    def test_only_matching_real_responses_are_compared(self):
        before = {"te-math-01": {"id": "te-math-01", "answer": "4",
                                 "usage": {"prompt_tokens": 5, "completion_tokens": 4},
                                 "elapsed_seconds": 2}}
        after = {"te-math-01": {"id": "te-math-01", "answer": "3",
                                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
                                "elapsed_seconds": 1}}
        report = compare("test", before, after)
        self.assertEqual(report["paired_usable_cases"], 1)
        self.assertTrue(report["incomplete"])
        self.assertEqual(report["old"]["correct"], 0)
        self.assertEqual(report["new"]["correct"], 1)
        self.assertEqual(report["accuracy_delta_percentage_points"], 100)
        self.assertEqual(report["new"]["completion_tokens_reported_total"], 3)

    def test_missing_answers_do_not_become_zero_accuracy(self):
        report = compare("test", {}, {})
        self.assertEqual(report["paired_usable_cases"], 0)
        self.assertIsNone(report["old"]["accuracy_on_paired_cases"])
        self.assertIsNone(report["accuracy_delta_percentage_points"])
        self.assertIsNone(report["new"]["prompt_tokens_reported_total"])


if __name__ == "__main__":
    unittest.main()
