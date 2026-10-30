"""Recompute saved-data simulations and forecasts in a fresh external directory."""

import argparse, gzip, hashlib, json, platform, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(output):
    output = output.resolve()
    assert (
        not output.is_relative_to(ROOT) and not output.exists()
    ), "Use a fresh external output"
    output.mkdir(parents=True)
    names = [
        "data/source_plan.json",
        "data/source_receipts.json",
        "data/qualification_ledger.json",
        "data/source_verification.json",
    ] + [
        p.relative_to(ROOT).as_posix()
        for p in sorted((ROOT / "data/keys").glob("*.json.gz"))
    ]
    before = {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in names}

    def run(*a):
        subprocess.run([sys.executable, *a], cwd=ROOT, check=True)

    run("-m", "unittest", "discover", "-s", "tests", "-v")
    run("src/freeze_proof.py")
    exact = tolerant = 0

    def compare(a, b, where):
        nonlocal exact, tolerant
        if type(a) is float:
            assert isinstance(b, (float, int)) and abs(a - b) <= 1e-12, where
            tolerant += 1
        elif isinstance(a, dict):
            assert set(a) == set(b), where
            for k in a:
                compare(a[k], b[k], where + "/" + k)
        elif isinstance(a, list):
            assert len(a) == len(b), where
            for i, (x, y) in enumerate(zip(a, b)):
                compare(x, y, where + "/" + str(i))
        else:
            assert type(a) == type(b) and a == b, where
            exact += 1

    from verify_results import verify

    for phase in ["development", "final"]:
        target = output / phase
        run("src/analyze.py", phase, "--output", str(target))
        originals = ROOT / "results" / phase
        expected = [
            p.relative_to(originals)
            for p in originals.rglob("*")
            if p.is_file() and p.name != "execution.json"
        ]
        for relative in expected:
            a = (originals / relative).read_bytes()
            b = (target / relative).read_bytes()
            if str(relative).endswith(".gz"):
                a = gzip.decompress(a)
                b = gzip.decompress(b)
            compare(json.loads(a), json.loads(b), phase + "/" + str(relative))
        proof = verify(phase)
        (output / (phase + "-independent.json")).write_bytes(
            (json.dumps(proof, indent=2) + "\n").encode()
        )
    from review_cli import review

    model = json.loads((ROOT / "results/development/selected_model.json").read_text())
    examples = {}
    for p in sorted((ROOT / "examples").glob("*.json")):
        if p.name.endswith(".expected.json"):
            continue
        v = review(json.loads(p.read_text()), model)
        compare(json.loads(p.with_suffix(".expected.json").read_text()), v, p.name)
        examples[p.name] = v["state"]
    after = {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in names}
    assert before == after
    value = dict(
        status="PASS_OFFLINE_REPLAY",
        python=platform.python_version(),
        exact_fields=exact,
        tolerant_fields=tolerant,
        float_replay_absolute_tolerance=1e-12,
        source_files_unchanged=len(names),
        source_sha256=after,
        fixtures=27,
        examples=examples,
        source_network_requests=0,
        compressed_outputs_compared_as_logical_JSON=True,
        original_execution_runtime_receipts_unchanged=True,
    )
    (output / "replay_receipt.json").write_bytes(
        (json.dumps(value, indent=2) + "\n").encode()
    )
    print(json.dumps(value))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, type=Path)
    main(p.parse_args().output)
