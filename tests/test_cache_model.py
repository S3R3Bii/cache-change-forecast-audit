import sys, unittest
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cache import simulate
from model import fit, predict, features, origins, metrics, select, pack, unpack, clip


class CacheTests(unittest.TestCase):
    def test_cold_and_repeated(self):
        self.assertEqual(simulate([1, 1, 1], 2, block_size=1)[0], [1, 0, 0])

    def test_recency_eviction(self):
        self.assertEqual(simulate([1, 2, 1, 3, 2], 2, block_size=1)[0], [1, 1, 0, 1, 1])

    def test_shrink_preserves_most_recent(self):
        self.assertEqual(
            simulate([1, 2, 3, 3, 1, 3], 3, 3, 1, 1)[0], [1, 1, 1, 0, 1, 1]
        )

    def test_expand_does_not_resurrect(self):
        self.assertEqual(simulate([1, 2, 3, 1], 2, 3, 4, 1)[0], [1, 1, 1, 1])

    def test_equal_capacity_control(self):
        keys = [1, 2, 1, 3, 2, 3]
        self.assertEqual(simulate(keys, 2, block_size=1), simulate(keys, 2, 3, 2, 1))

    def test_block_counts(self):
        self.assertEqual(simulate([1, 1, 2, 2], 1, block_size=2)[1], [1, 1])

    def test_zero_or_boolean_capacity_rejected(self):
        for cap in [0, -1, True]:
            with self.assertRaises(ValueError):
                simulate([1], cap, block_size=1)

    def test_partial_block_rejected(self):
        with self.assertRaises(ValueError):
            simulate([1, 2, 3], 2, block_size=2)

    def test_invalid_resize_rejected(self):
        for at, cap in [(4, 2), (0, 0), (-1, 2)]:
            with self.assertRaises(ValueError):
                simulate([1, 2, 3], 2, at, cap, 1)

    def test_future_requests_do_not_change_prefix_misses(self):
        a = simulate([1, 2, 1, 3, 8, 9], 2, block_size=1)[0]
        b = simulate([1, 2, 1, 3, 1, 1], 2, block_size=1)[0]
        self.assertEqual(a[:4], b[:4])


class ModelTests(unittest.TestCase):
    def test_constant_history_exact_intercept(self):
        rows = [
            dict(
                trace="a",
                scenario="control",
                block=i,
                lag_counts=[500] * 3,
                target_count=500,
            )
            for i in range(6)
        ]
        self.assertEqual(fit(rows, "1"), [F(1, 2), F(0), F(0), F(0)])

    def test_clipping(self):
        self.assertEqual(clip(F(-1)), 0)
        self.assertEqual(clip(F(2)), 1)

    def test_boundary_prior_features(self):
        rows = origins([0, 100, 200, 300, 400], 3, 4, "a")
        self.assertEqual(rows[0]["lag_counts"], [200, 100, 0])
        self.assertEqual(rows[0]["target_count"], 300)

    def test_future_target_not_in_earlier_features(self):
        a = origins([0, 100, 200, 300, 400], 3, 4, "a")
        b = origins([0, 100, 200, 300, 900], 3, 4, "a")
        self.assertEqual(a[0], b[0])

    def test_exact_selection_tie_prefers_larger_penalty(self):
        candidates = [
            dict(lambda_="0.01", validation=dict(macro_mae=pack(F(1, 3)))),
            dict(lambda_="100", validation=dict(macro_mae=pack(F(1, 3)))),
        ]
        for c in candidates:
            c["lambda"] = c.pop("lambda_")
        self.assertEqual(select(candidates)["lambda"], "100")

    def test_feature_validation(self):
        for x in [[1, 2], [True, 2, 3], [1, -1, 3], [1001, 2, 3], [None, 2, 3]]:
            with self.assertRaises(ValueError):
                features(x)

    def test_metrics_exact_signed_and_squared(self):
        rows = [
            dict(
                trace="a",
                scenario="x",
                prediction=pack(F(1, 2)),
                target_count=250,
                clipped=False,
            ),
            dict(
                trace="b",
                scenario="x",
                prediction=pack(F(0)),
                target_count=500,
                clipped=False,
            ),
        ]
        m = metrics(rows)
        self.assertEqual(unpack(m["macro_mae"]), F(3, 8))
        self.assertEqual(unpack(m["macro_mse"]), F(5, 32))
        self.assertEqual(unpack(m["macro_signed_error"]), F(-1, 8))

    def test_empty_training_rejected(self):
        with self.assertRaises(ValueError):
            fit([], "1")


if __name__ == "__main__":
    unittest.main()
