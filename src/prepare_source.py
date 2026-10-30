"""Create fixed ordinal prefixes from exact complete private source objects."""

import argparse, gzip, hashlib, json
from pathlib import Path
from projection import decode_prefix, project


def save(p, v):
    p.write_bytes((json.dumps(v, indent=2) + "\n").encode())


def main(private):
    root = Path(__file__).resolve().parents[1]
    plan = json.loads((root / "data/source_plan.json").read_text())
    receipts = json.loads((private / "receipts.json").read_text())
    assert len(receipts) == 6 and all(r["status"] == 200 for r in receipts)
    (root / "data/keys").mkdir(exist_ok=False)
    quality = []
    public = []
    for p in plan["traces"]:
        r = next(r for r in receipts if r["trace"] == p["trace"])
        path = private / r["private_body"]
        assert (
            len(path.read_bytes()) == p["expected_bytes"]
            and hashlib.sha256(path.read_bytes()).hexdigest() == r["sha256"]
        )
        raw = decode_prefix(path, plan["prefix_requests"])
        ids, q = project(raw, plan["prefix_requests"])
        q.update(
            trace=p["trace"],
            phase=p["phase"],
            decoded_prefix_bytes=len(raw),
            full_compressed_sha256=r["sha256"],
            state="PASS_PREFIX" if not q["clock_regressions"] else "FAIL_CLOCK_ORDER",
        )
        quality.append(q)
        save(root / "data/qualification_ledger.json", quality)
        assert q["state"] == "PASS_PREFIX", "Captured prefix clock order gate"
        text = (json.dumps(ids, separators=(",", ":")) + "\n").encode()
        target = root / "data/keys" / (p["trace"] + ".json.gz")
        target.write_bytes(gzip.compress(text, mtime=0))
        public.append({k: v for k, v in r.items() if k != "private_body"})
    save(root / "data/source_receipts.json", public)
    print(
        json.dumps(
            dict(
                status="PASS_ORDINAL_PREFIX_PROJECTION",
                traces=len(quality),
                projected_requests=sum(q["records"] for q in quality),
                quality=quality,
            )
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--private", required=True, type=Path)
    main(p.parse_args().private)
