"""Independent heap LRU, SQLite lag windows, NumPy solve and exact metric checks."""

import argparse, gzip, heapq, json, sqlite3
from fractions import Fraction as F
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def read(n):
    return json.loads((ROOT / n).read_text())


def fraction(x):
    return F(x["numerator"], x["denominator"])


def heap_misses(keys, before, change, after):
    resident = {}
    heap = []
    result = []
    capacity = before

    def trim():
        while len(resident) > capacity:
            stamp, key = heapq.heappop(heap)
            if resident.get(key) == stamp:
                del resident[key]

    for i, key in enumerate(keys):
        if change is not None and i == change:
            capacity = after
            trim()
        miss = int(key not in resident)
        result.append(miss)
        resident[key] = i
        heapq.heappush(heap, (i, key))
        trim()
    return result


def independent_metrics(rows):
    groups = {}
    for r in rows:
        groups.setdefault(r["trace"] + "|" + r["scenario"], []).append(r)

    def one(items):
        errors = [fraction(r["prediction"]) - F(r["target_count"], 1000) for r in items]
        return dict(
            origins=len(items),
            mae=sum(map(abs, errors), F(0)) / len(items),
            mse=sum((x * x for x in errors), F(0)) / len(items),
            signed_error=sum(errors, F(0)) / len(items),
            clipped_origins=sum(r["clipped"] for r in items),
        )

    per = {key: one(items) for key, items in groups.items()}
    whole = one(rows)
    result = dict(
        origins=len(rows),
        groups=len(groups),
        clipped_origins=whole["clipped_origins"],
        per_group=per,
    )
    for k in ["mae", "mse", "signed_error"]:
        result["micro_" + k] = whole[k]
        result["macro_" + k] = sum((p[k] for p in per.values()), F(0)) / len(per)
    return result


def verify(phase):
    plan = read("data/source_plan.json")
    simulations = read("results/" + phase + "/simulation.json")
    checked = 0
    request_values = 0

    def check(condition, label):
        nonlocal checked
        checked += 1
        if not condition:
            raise AssertionError(label)

    con = sqlite3.connect(":memory:")
    con.execute(
        "create table blocks(trace text,scenario text,b integer,n integer,primary key(trace,scenario,b))"
    )
    expected_groups = {
        (p["trace"], scenario)
        for p in plan["traces"]
        if p["phase"] == phase
        for scenario in (["control"] if phase == "development" else plan["scenarios"])
    }
    check(
        {(s["trace"], s["scenario"]) for s in simulations} == expected_groups
        and len(simulations) == len(expected_groups),
        "all simulation groups",
    )
    for sim in simulations:
        keys = json.loads(
            gzip.decompress(
                (ROOT / "data/keys" / (sim["trace"] + ".json.gz")).read_bytes()
            )
        )
        check(
            len(keys) == 200000 and all(type(k) is int and k >= 0 for k in keys),
            "ordinal stream",
        )
        after = 512 if phase == "development" else plan["scenarios"][sim["scenario"]]
        independent = heap_misses(
            keys, 512, None if phase == "development" else 160000, after
        )
        saved = json.loads(
            gzip.decompress(
                (
                    ROOT
                    / "results"
                    / phase
                    / "request_misses"
                    / (sim["trace"] + "-" + sim["scenario"] + ".json.gz")
                ).read_bytes()
            )
        )
        check(len(saved) == len(independent), "request denominator")
        for observed, expected in zip(saved, independent):
            check(
                type(observed) is int and observed == expected,
                "heap/OrderedDict request equality",
            )
            request_values += 1
        blocks = [sum(independent[i : i + 1000]) for i in range(0, 200000, 1000)]
        check(
            len(sim["block_misses"]) == 200
            and sim["capacity_before"] == 512
            and sim["capacity_after"] == after,
            "simulation metadata",
        )
        for i, (observed, expected) in enumerate(zip(sim["block_misses"], blocks)):
            check(observed == expected, "independent block counts")
            con.execute(
                "insert into blocks values(?,?,?,?)",
                (sim["trace"], sim["scenario"], i, expected),
            )
        if phase == "final":
            control = next(
                x
                for x in simulations
                if x["trace"] == sim["trace"] and x["scenario"] == "control"
            )
            check(
                sim["block_misses"][:160] == control["block_misses"][:160],
                "shared pre-change state",
            )

    def sql_origins(first, last):
        query = """with lags as (
        select trace,scenario,b,n,
        lag(n,1) over(partition by trace,scenario order by b) l1,
        lag(n,2) over(partition by trace,scenario order by b) l2,
        lag(n,3) over(partition by trace,scenario order by b) l3
        from blocks) select trace,scenario,b,n,l1,l2,l3 from lags where b between ? and ?"""
        return {
            (t, s, b): dict(
                trace=t, scenario=s, block=b, target_count=n, lag_counts=[l1, l2, l3]
            )
            for t, s, b, n, l1, l2, l3 in con.execute(query, (first, last))
        }

    expected_current = (
        sql_origins(120, 159) if phase == "development" else sql_origins(160, 199)
    )
    for name, expected in (
        [
            ("training_origins", sql_origins(3, 119)),
            ("validation_origins", expected_current),
        ]
        if phase == "development"
        else [("origins", expected_current)]
    ):
        saved = read("results/" + phase + "/" + name + ".json")
        check(len(saved) == len(expected), "origin denominator")
        for r in saved:
            check(
                r == expected[(r["trace"], r["scenario"], r["block"])],
                "SQLite feature/target/boundary",
            )
    training = read("results/development/training_origins.json")
    check(len(training) == 351, "fixed train count")
    x = np.array(
        [[1] + [v / 1000 for v in r["lag_counts"]] for r in training], dtype=np.float64
    )
    y = np.array([r["target_count"] / 1000 for r in training])
    search = read("results/development/search.json")
    models = {}
    selection = []

    def metric_matches(actual, expected):
        for key, value in expected.items():
            if key == "per_group":
                check(set(actual[key]) == set(value), "all metric groups")
                for group, item in value.items():
                    metric_matches(actual[key][group], item)
            elif isinstance(value, F):
                check(
                    fraction(actual[key]) == value
                    and actual[key]["value"] == float(value),
                    "exact metric identity",
                )
            else:
                check(actual[key] == value, "metric count")

    for candidate in search:
        penalty = float(candidate["lambda"])
        matrix = x.T @ x + np.diag([0, penalty, penalty, penalty])
        numeric = np.linalg.solve(matrix, x.T @ y)
        exact = [fraction(c) for c in candidate["coefficients"]]
        check(
            len(exact) == 4
            and max(abs(float(a) - b) for a, b in zip(exact, numeric)) <= 1e-8,
            "independent NumPy coefficients",
        )
        for c in candidate["coefficients"]:
            check(c["value"] == float(fraction(c)), "coefficient display")
        models[candidate["name"]] = (exact, numeric)
        selection.append(
            (
                fraction(candidate["validation"]["macro_mae"]),
                -F(candidate["lambda"]),
                candidate,
            )
        )
    chosen = min(selection, key=lambda z: z[:2])[2]
    selected = read("results/development/selected_model.json")
    check(
        selected["model_name"] == chosen["name"]
        and selected["lambda"] == chosen["lambda"]
        and selected["coefficients"] == chosen["coefficients"],
        "exact selection",
    )
    check(
        selected["training_origins"] == 351
        and selected["validation_origins"] == 120
        and selected["no_validation_refit"] is True,
        "fit provenance",
    )
    predictions = read("results/" + phase + "/predictions.json")
    expected_models = {"previous-block"} | (
        {r["name"] for r in search}
        if phase == "development"
        else {selected["model_name"]}
    )
    check(
        len(predictions) == len(expected_current) * len(expected_models),
        "prediction denominator",
    )
    seen = set()
    numeric_predictions = {}
    for p in predictions:
        key = (p["trace"], p["scenario"], p["block"])
        origin = expected_current[key]
        check(
            p["lag_counts"] == origin["lag_counts"]
            and p["target_count"] == origin["target_count"],
            "prediction feature/label identity",
        )
        unique = key + (p["model"],)
        check(
            unique not in seen and p["model"] in expected_models,
            "unique complete prediction",
        )
        seen.add(unique)
        if p["model"] == "previous-block":
            raw = F(origin["lag_counts"][0], 1000)
            numeric = float(raw)
        else:
            exact, beta = models[p["model"]]
            vec = [F(1)] + [F(v, 1000) for v in origin["lag_counts"]]
            raw = sum((a * b for a, b in zip(exact, vec)), F(0))
            numeric = float(np.dot([float(v) for v in vec], beta))
        value = min(F(1), max(F(0), raw))
        check(
            fraction(p["raw_prediction"]) == raw
            and p["raw_prediction"]["value"] == float(raw),
            "raw rational prediction",
        )
        check(
            fraction(p["prediction"]) == value
            and p["prediction"]["value"] == float(value)
            and p["clipped"] == (value != raw),
            "clipped rational prediction",
        )
        check(
            abs(float(raw) - numeric) <= 1e-9
            and abs(float(value) - min(1, max(0, numeric))) <= 1e-9,
            "independent numeric prediction",
        )
        numeric_predictions[unique] = min(1, max(0, numeric))
    summary = read("results/" + phase + "/summary.json")

    def validated_metric(actual, rows):
        metric_matches(actual, independent_metrics(rows))
        errors = {}
        for row in rows:
            key = (row["trace"], row["scenario"], row["block"], row["model"])
            errors.setdefault(row["trace"] + "|" + row["scenario"], []).append(
                numeric_predictions[key] - row["target_count"] / 1000
            )
        arrays = [np.asarray(e, dtype=np.float64) for e in errors.values()]
        whole = np.concatenate(arrays)
        for suffix, operation in [
            ("mae", lambda e: np.mean(np.abs(e))),
            ("mse", lambda e: np.mean(e * e)),
            ("signed_error", lambda e: np.mean(e)),
        ]:
            micro = float(operation(whole))
            macro = float(np.mean([operation(e) for e in arrays]))
            check(
                abs(actual["micro_" + suffix]["value"] - micro) <= 1e-10
                and abs(actual["macro_" + suffix]["value"] - macro) <= 1e-10,
                "independent NumPy metric",
            )

    if phase == "development":
        for candidate in search:
            rows = [r for r in predictions if r["model"] == candidate["name"]]
            validated_metric(candidate["validation"], rows)
        validated_metric(
            summary["baseline_validation"],
            [r for r in predictions if r["model"] == "previous-block"],
        )
        validated_metric(
            summary["selected_validation"],
            [r for r in predictions if r["model"] == chosen["name"]],
        )
        check(
            summary["selected_name"] == chosen["name"]
            and summary["training_origins"] == 351
            and summary["validation_origins"] == 120
            and summary["candidates"] == 3,
            "development summary",
        )
    else:
        for model in expected_models:
            rows = [r for r in predictions if r["model"] == model]
            observed = summary["models"][model]
            for scenario in plan["scenarios"]:
                validated_metric(
                    observed["scenarios"][scenario],
                    [r for r in rows if r["scenario"] == scenario],
                )
            validated_metric(
                observed["changed_primary"],
                [r for r in rows if r["scenario"] != "control"],
            )
            validated_metric(
                observed["changed_first_five"],
                [r for r in rows if r["scenario"] != "control" and r["block"] < 165],
            )
        expected_delta = fraction(
            summary["models"][chosen["name"]]["changed_primary"]["macro_mae"]
        ) - fraction(
            summary["models"]["previous-block"]["changed_primary"]["macro_mae"]
        )
        check(
            fraction(summary["selected_minus_baseline_changed_macro_mae"])
            == expected_delta,
            "primary paired difference",
        )
        for sim in simulations:
            key = sim["trace"] + "|" + sim["scenario"]
            mean = F(sum(sim["block_misses"][160:200]), 40000)
            control = next(
                x
                for x in simulations
                if x["trace"] == sim["trace"] and x["scenario"] == "control"
            )
            delta = mean - F(sum(control["block_misses"][160:200]), 40000)
            check(
                fraction(summary["target_mean_miss_fractions"][key]) == mean
                and fraction(summary["target_mean_difference_from_control"][key])
                == delta,
                "paired simulated target means",
            )
        for trace in {r["trace"] for r in predictions}:
            starts = [
                r for r in predictions if r["trace"] == trace and r["block"] == 160
            ]
            check(
                len({tuple(r["lag_counts"]) for r in starts}) == 1,
                "identical first post-change features, no capacity input",
            )
        check(
            summary["origins_per_model"] == 360
            and summary["changed_primary_origins_per_model"] == 240
            and summary["first_five_changed_origins_per_model"] == 30,
            "final count boundaries",
        )
    return dict(
        status="PASS_INDEPENDENT_HEAP_SQLITE_NUMPY_FRACTION",
        phase=phase,
        conditions=checked,
        request_miss_values_checked=request_values,
        simulation_groups=len(simulations),
        predictions=len(predictions),
        coefficient_absolute_tolerance=1e-8,
        prediction_absolute_tolerance=1e-9,
        metric_absolute_tolerance=1e-10,
        exact_rational_metrics=True,
        source_network_requests=0,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("phase", choices=["development", "final"])
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    value = verify(a.phase)
    if a.output:
        a.output.write_bytes((json.dumps(value, indent=2) + "\n").encode())
    print(json.dumps(value))
