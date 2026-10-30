import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from projection import project


def record(clock, key, size, future):
    return (
        clock.to_bytes(4, "little")
        + key.to_bytes(8, "little")
        + size.to_bytes(4, "little")
        + future
    )


class ProjectionTests(unittest.TestCase):
    def test_future_bytes_do_not_affect_projection(self):
        a = record(1, 9, 5, b"\x00" * 8) + record(2, 9, 5, b"\xff" * 8)
        b = a[:16] + b"FUTURE!!" + a[24:40] + b"IGNORED!"
        self.assertEqual(project(a, 2), project(b, 2))

    def test_first_appearance_not_numeric_rank(self):
        raw = b"".join(
            record(i, k, 0, b"\xff" * 8) for i, k in enumerate([90, 1, 90, 2])
        )
        ids, q = project(raw, 4)
        self.assertEqual(ids, [0, 1, 0, 2])
        self.assertEqual(q["zero_size_records"], 4)

    def test_truncated_prefix_rejected(self):
        with self.assertRaises(ValueError):
            project(record(1, 2, 3, b"\x00" * 8)[:-1], 1)

    def test_clock_regression_retained(self):
        raw = record(2, 1, 1, b"\x00" * 8) + record(1, 2, 1, b"\x00" * 8)
        self.assertEqual(project(raw, 2)[1]["clock_regressions"], 1)

    def test_key_byte_order_is_a_bijection(self):
        rows = [record(i, k, 1, b"\x00" * 8) for i, k in enumerate([3, 256, 3, 0])]
        changed = [r[:4] + r[4:12][::-1] + r[12:] for r in rows]
        self.assertEqual(
            project(b"".join(rows), 4)[0], project(b"".join(changed), 4)[0]
        )


if __name__ == "__main__":
    unittest.main()
