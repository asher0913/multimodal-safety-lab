import unittest

from multimodal_safety_lab.core import CrossModalDefense, IntentAlignmentDefense, TextOnlyDefense, evaluate, fixture


class SafetyTests(unittest.TestCase):
    def test_cross_modal_catches_split_attack(self):
        split = [sample for sample in fixture() if sample.sample_id.endswith("split")][0]
        self.assertFalse(TextOnlyDefense().predict(split)[0])
        self.assertTrue(CrossModalDefense().predict(split)[0])

    def test_benign_policy_discussion_passes(self):
        benign = [sample for sample in fixture() if sample.sample_id == "b1"][0]
        self.assertFalse(IntentAlignmentDefense().predict(benign)[0])

    def test_evaluator_has_complete_rows(self):
        samples = fixture()
        report = evaluate(CrossModalDefense(), samples)
        self.assertEqual(len(report["rows"]), len(samples))
        self.assertGreaterEqual(report["harmful_catch_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
