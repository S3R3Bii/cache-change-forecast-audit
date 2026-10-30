"""Exact small autoregression; all candidate settings are explicit protocol inputs."""

from fractions import Fraction as F


def pack(x):
    x = F(x)
    return dict(numerator=x.numerator, denominator=x.denominator, value=float(x))


def unpack(x):
    return F(x["numerator"], x["denominator"])


def clip(x):
    return max(F(0), min(F(1), x))


def features(counts):
    if len(counts) != 3 or any(
        type(c) is not int or not 0 <= c <= 1000 for c in counts
    ):
        raise ValueError("three completed block miss counts in 0..1000 required")
    return [F(1)] + [F(c, 1000) for c in counts]


def origins(blocks, first, last, trace, scenario="control"):
    if first < 3 or last >= len(blocks):
        raise ValueError("three past complete blocks required")
    return [
        dict(
            trace=trace,
            scenario=scenario,
            block=t,
            lag_counts=[blocks[t - 1], blocks[t - 2], blocks[t - 3]],
            target_count=blocks[t],
        )
        for t in range(first, last + 1)
    ]


def solve(a, b):
    m = [list(row) + [value] for row, value in zip(a, b)]
    n = len(b)
    for col in range(n):
        pivot = next((i for i in range(col, n) if m[i][col]), None)
        if pivot is None:
            raise ValueError("singular system")
        m[col], m[pivot] = m[pivot], m[col]
        divisor = m[col][col]
        m[col] = [x / divisor for x in m[col]]
        for i in range(n):
            if i == col:
                continue
            multiple = m[i][col]
            m[i] = [x - multiple * y for x, y in zip(m[i], m[col])]
    return [row[-1] for row in m]


def fit(rows, penalty):
    if (
        not rows
        or F(penalty) <= 0
        or any(
            type(r["target_count"]) is not int or not 0 <= r["target_count"] <= 1000
            for r in rows
        )
    ):
        raise ValueError(
            "nonempty valid training data and positive ridge penalty required"
        )
    x = [features(r["lag_counts"]) for r in rows]
    y = [F(r["target_count"], 1000) for r in rows]
    a = [
        [
            sum((v[i] * v[j] for v in x), F(0))
            + (F(penalty) if i == j and i > 0 else 0)
            for j in range(4)
        ]
        for i in range(4)
    ]
    b = [sum((v[i] * target for v, target in zip(x, y)), F(0)) for i in range(4)]
    return solve(a, b)


def predict(rows, name, coefficients=None):
    result = []
    for r in rows:
        raw = (
            F(r["lag_counts"][0], 1000)
            if name == "previous-block"
            else sum(
                (a * b for a, b in zip(coefficients, features(r["lag_counts"]))), F(0)
            )
        )
        value = clip(raw)
        result.append(
            dict(
                **r,
                model=name,
                raw_prediction=pack(raw),
                prediction=pack(value),
                clipped=raw != value
            )
        )
    return result


def metrics(rows):
    if not rows:
        raise ValueError("empty denominator")
    by = {}
    for r in rows:
        by.setdefault(r["trace"] + "|" + r["scenario"], []).append(r)

    def single(group):
        errors = [unpack(r["prediction"]) - F(r["target_count"], 1000) for r in group]
        return dict(
            origins=len(group),
            mae=pack(sum(map(abs, errors), F(0)) / len(group)),
            mse=pack(sum((x * x for x in errors), F(0)) / len(group)),
            signed_error=pack(sum(errors, F(0)) / len(group)),
            clipped_origins=sum(r["clipped"] for r in group),
        )

    per = {key: single(value) for key, value in sorted(by.items())}
    micro = single(rows)
    result = dict(
        origins=len(rows),
        groups=len(per),
        per_group=per,
        clipped_origins=micro["clipped_origins"],
    )
    for key in ["mae", "mse", "signed_error"]:
        result["micro_" + key] = micro[key]
        result["macro_" + key] = pack(
            sum((unpack(r[key]) for r in per.values()), F(0)) / len(per)
        )
    return result


def select(search):
    return min(
        search, key=lambda r: (unpack(r["validation"]["macro_mae"]), -F(r["lambda"]))
    )
