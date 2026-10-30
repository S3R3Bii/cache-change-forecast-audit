"""Offline forecast context exercise; no cache mutation, source request or alert."""

import argparse, json
from fractions import Fraction as F
from pathlib import Path
from model import features, unpack, pack, clip

ROOT = Path(__file__).resolve().parents[1]


def review(item, model):
    counts = item.get("previous_misses", [])
    changed = item.get("configuration_changed", False)
    if type(changed) is not bool:
        raise ValueError("configuration_changed must be boolean")
    if len(counts) != 3 or any(x is None for x in counts):
        return dict(
            state="UNKNOWN_MISSING_COMPLETED_HISTORY",
            prediction=None,
            baseline=None,
            context="Three completed 1000-request blocks are required, newest first.",
        )
    vector = features(counts)
    raw = sum((unpack(c) * x for c, x in zip(model["coefficients"], vector)), F(0))
    return dict(
        state="AUTHORED_EXERCISE_ESTIMATE",
        model=model["model_name"],
        prediction=pack(clip(raw)),
        raw_prediction=pack(raw),
        clipped=raw != clip(raw),
        baseline=pack(F(counts[0], 1000)),
        units="miss fraction per 1000-request block in the equal-object LRU simulation",
        configuration_changed=changed,
        recommendation=(
            "Collect post-change history and recheck this configuration-blind forecast against the previous-block baseline."
            if changed
            else "Keep configuration context with the forecast and compare it with the previous-block baseline."
        ),
        limitation="Teaching estimate; no actual cache, production IOPS/latency, capacity recommendation or measured operational benefit.",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("input", type=Path)
    a = p.parse_args()
    model = json.loads((ROOT / "results/development/selected_model.json").read_text())
    print(json.dumps(review(json.loads(a.input.read_text()), model), indent=2))
