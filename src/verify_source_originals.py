"""Separate byte parser reconciles private prefixes with every published ordinal."""

import argparse, gzip, hashlib, json
from pathlib import Path


def main(private):
    import zstandard

    root = Path(__file__).resolve().parents[1]
    plan = json.loads((root / "data/source_plan.json").read_text())
    original = json.loads((private / "receipts.json").read_text())
    public = json.loads((root / "data/source_receipts.json").read_text())
    quality = json.loads((root / "data/qualification_ledger.json").read_text())
    conditions = 0
    for p in plan["traces"]:
        capture = next(x for x in original if x["trace"] == p["trace"])
        receipt = next(x for x in public if x["trace"] == p["trace"])
        source = private / capture["private_body"]
        h = hashlib.sha256()
        with source.open("rb") as f:
            while True:
                chunk = f.read(1048576)
                if not chunk:
                    break
                h.update(chunk)
        assert (
            h.hexdigest() == capture["sha256"] == receipt["sha256"]
            and source.stat().st_size == receipt["bytes"] == p["expected_bytes"]
        )
        conditions += 1
        with source.open("rb") as f, zstandard.ZstdDecompressor().stream_reader(
            f
        ) as reader:
            raw = reader.read(plan["prefix_requests"] * 24)
        assert len(raw) == 4800000
        conditions += 1
        saved = json.loads(
            gzip.decompress(
                (root / "data/keys" / (p["trace"] + ".json.gz")).read_bytes()
            )
        )
        mapping = {}
        clocks = []
        zero = 0
        for index in range(200000):
            offset = index * 24
            # A reversible integer representation independently preserves token equality.
            key = int.from_bytes(raw[offset + 4 : offset + 12], "little")
            if key not in mapping:
                mapping[key] = len(mapping)
            assert saved[index] == mapping[key]
            conditions += 1
            clocks.append(int.from_bytes(raw[offset : offset + 4], "little"))
            zero += int(int.from_bytes(raw[offset + 12 : offset + 16], "little") == 0)
        q = next(x for x in quality if x["trace"] == p["trace"])
        expected = dict(
            records=200000,
            distinct_prefix_ids=len(mapping),
            first_raw_clock=clocks[0],
            last_raw_clock=clocks[-1],
            clock_ties=sum(a == b for a, b in zip(clocks, clocks[1:])),
            clock_regressions=sum(a > b for a, b in zip(clocks, clocks[1:])),
            zero_size_records=zero,
        )
        for k, v in expected.items():
            assert q[k] == v
            (conditions := conditions + 1)
        assert (
            q["future_field_decoded"] is False
            and q["clock_regressions"] == 0
            and len(saved) == 200000
        )
        conditions += 1
    value = dict(
        status="PASS_INDEPENDENT_NATIVE_ORDINAL_PROJECTION",
        conditions=conditions,
        source_objects=6,
        source_bytes=sum(x["bytes"] for x in public),
        projected_requests=1200000,
        source_future_field_decoded=False,
        scope="Every published ordinal and prefix-quality field from exact compressed sources; no full-file semantic validation or final simulation.",
    )
    (root / "data/source_verification.json").write_bytes(
        (json.dumps(value, indent=2) + "\n").encode()
    )
    print(json.dumps(value))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--private", required=True, type=Path)
    main(p.parse_args().private)
