import sys, unittest
from pathlib import Path
from fractions import Fraction as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from review_cli import review
from model import pack


class ExerciseTests(unittest.TestCase):
    def model(self):
        return dict(
            model_name="authored-test",
            coefficients=[pack(F(1, 4)), pack(F(1, 2)), pack(0), pack(0)],
        )

    def test_authored_estimate_and_baseline(self):
        r = review(dict(previous_misses=[400, 500, 300]), self.model())
        self.assertEqual(r["prediction"], pack(F(9, 20)))
        self.assertEqual(r["baseline"], pack(F(2, 5)))

    def test_configuration_context_is_explicit(self):
        r = review(
            dict(previous_misses=[400, 500, 300], configuration_changed=True),
            self.model(),
        )
        self.assertTrue(r["configuration_changed"])
        self.assertIn("post-change", r["recommendation"])

    def test_missing_history_is_unknown(self):
        self.assertIsNone(
            review(dict(previous_misses=[400, None, 300]), self.model())["prediction"]
        )

    def test_invalid_count_not_a_measurement(self):
        with self.assertRaises(ValueError):
            review(dict(previous_misses=[True, 1, 2]), self.model())


if __name__ == "__main__":
    unittest.main()
