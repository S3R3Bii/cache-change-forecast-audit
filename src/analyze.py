"""One development selection followed by protected final-volume simulations."""

import argparse, gzip, json, time
from datetime import datetime, timezone
from fractions import Fraction as F
from pathlib import Path
from cache import simulate
from model import fit, origins, predict, metrics, pack, unpack, select

ROOT = Path(__file__).resolve().parents[1]


def read(n):
    return json.loads((ROOT / n).read_text())


def save(p, v):
    p.write_bytes((json.dumps(v, indent=2, allow_nan=False) + "\n").encode())


def zipped(p, v):
    p.write_bytes(
        gzip.compress((json.dumps(v, separators=(",", ":")) + "\n").encode(), mtime=0)
    )


def main(phase, output=None):
    if phase == "final":
        from freeze_proof import verify

        verify(ROOT)
    plan = read("data/source_plan.json")
    target = Path(output) if output else ROOT / "results" / phase
    target.mkdir(parents=True, exist_ok=True)
    (target / "request_misses").mkdir(exist_ok=True)
    began = time.perf_counter()
    simulations = []
    training = []
    validation = []
    final = []
    for p in plan["traces"]:
        if p["phase"] != phase:
            continue
        ids = json.loads(
            gzip.decompress(
                (ROOT / "data/keys" / (p["trace"] + ".json.gz")).read_bytes()
            )
        )
        assert len(ids) == plan["prefix_requests"]
        for scenario, capacity in (
            dict(control=512) if phase == "development" else plan["scenarios"]
        ).items():
            misses, blocks = simulate(
                ids,
                plan["baseline_capacity"],
                (
                    None
                    if phase == "development"
                    else plan["final_first_block"] * plan["block_requests"]
                ),
                None if phase == "development" else capacity,
                plan["block_requests"],
            )
            zipped(
                target / "request_misses" / (p["trace"] + "-" + scenario + ".json.gz"),
                misses,
            )
            simulations.append(
                dict(
                    trace=p["trace"],
                    scenario=scenario,
                    requests=len(ids),
                    capacity_before=512,
                    capacity_after=capacity,
                    change_before_block=None if phase == "development" else 160,
                    block_misses=blocks,
                )
            )
            if phase == "development":
                training += origins(blocks, 3, 119, p["trace"])
                validation += origins(blocks, 120, 159, p["trace"])
            else:
                final += origins(blocks, 160, 199, p["trace"], scenario)
    save(target / "simulation.json", simulations)
    runtimes = []
    if phase == "development":
        assert len(training) == 351 and len(validation) == 120
        predictions = predict(validation, "previous-block")
        search = []
        for penalty in plan["lambdas"]:
            start = time.perf_counter()
            coefficients = fit(training, penalty)
            name = "ridge-" + penalty
            pred = predict(validation, name, coefficients)
            score = metrics(pred)
            runtimes.append(
                dict(model=name, fit_and_validation_seconds=time.perf_counter() - start)
            )
            search.append(
                dict(
                    name=name,
                    lambda_=penalty,
                    coefficients=[pack(c) for c in coefficients],
                    validation=score,
                )
            )
            search[-1]["lambda"] = search[-1].pop("lambda_")
            predictions += pred
        chosen = select(search)
        selected = dict(
            model_name=chosen["name"],
            lambda_=chosen["lambda"],
            coefficients=chosen["coefficients"],
            training_origins=351,
            validation_origins=120,
            selection_validation_macro_mae=chosen["validation"]["macro_mae"],
            no_validation_refit=True,
        )
        selected["lambda"] = selected.pop("lambda_")
        summary = dict(
            training_origins=351,
            validation_origins=120,
            selected_name=chosen["name"],
            baseline_validation=metrics(
                [p for p in predictions if p["model"] == "previous-block"]
            ),
            selected_validation=chosen["validation"],
            candidates=len(search),
        )
        for n, v in [
            ("training_origins", training),
            ("validation_origins", validation),
            ("search", search),
            ("selected_model", selected),
            ("predictions", predictions),
            ("summary", summary),
        ]:
            save(target / (n + ".json"), v)
    else:
        selected = read("results/development/selected_model.json")
        coefficients = [unpack(c) for c in selected["coefficients"]]
        predictions = predict(final, "previous-block") + predict(
            final, selected["model_name"], coefficients
        )
        assert len(final) == 360 and len(predictions) == 720
        models = {}
        for name in ["previous-block", selected["model_name"]]:
            rows = [p for p in predictions if p["model"] == name]
            models[name] = dict(
                scenarios={
                    s: metrics([r for r in rows if r["scenario"] == s])
                    for s in plan["scenarios"]
                },
                changed_primary=metrics(
                    [r for r in rows if r["scenario"] != "control"]
                ),
                changed_first_five=metrics(
                    [r for r in rows if r["scenario"] != "control" and r["block"] < 165]
                ),
            )
        means = {
            r["trace"]
            + "|"
            + r["scenario"]: pack(F(sum(r["block_misses"][160:200]), 40000))
            for r in simulations
        }
        differences = {
            key: pack(unpack(value) - unpack(means[key.split("|")[0] + "|control"]))
            for key, value in means.items()
        }
        summary = dict(
            selected_name=selected["model_name"],
            origins_per_model=360,
            predictions=720,
            changed_primary_origins_per_model=240,
            first_five_changed_origins_per_model=30,
            models=models,
            selected_minus_baseline_changed_macro_mae=pack(
                unpack(models[selected["model_name"]]["changed_primary"]["macro_mae"])
                - unpack(models["previous-block"]["changed_primary"]["macro_mae"])
            ),
            target_mean_miss_fractions=means,
            target_mean_difference_from_control=differences,
        )
        save(target / "origins.json", final)
        save(target / "predictions.json", predictions)
        save(target / "summary.json", summary)
    save(
        target / "execution.json",
        dict(
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            phase=phase,
            elapsed_seconds=time.perf_counter() - began,
            candidate_runtimes=runtimes,
            interpretation="New execution provenance; not deterministic replay bytes or production performance.",
        ),
    )
    print(
        json.dumps(
            dict(
                phase=phase,
                selected_name=summary["selected_name"],
                summary=(
                    summary["selected_validation"]["macro_mae"]
                    if phase == "development"
                    else summary["selected_minus_baseline_changed_macro_mae"]
                ),
            )
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("phase", choices=["development", "final"])
    p.add_argument("--output")
    a = p.parse_args()
    main(a.phase, a.output)
