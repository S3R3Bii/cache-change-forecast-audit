"""Recompute mapped measurements and the actual rendered SVG geometry."""

import hashlib, json, re
from pathlib import Path
from xml.etree import ElementTree as E

ROOT = Path(__file__).resolve().parents[1]
S = "{http://www.w3.org/2000/svg}"


def read(n):
    return json.loads((ROOT / n).read_text())


def vertices(node):
    p = node.find(".//" + S + "path")
    assert p is not None
    values = [
        float(v)
        for v in re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", p.attrib["d"])
    ]
    return list(zip(values[::2], values[1::2]))


def main():
    maps = read("figures/value_map.json")
    d = read("results/development/summary.json")
    search = read("results/development/search.json")
    f = read("results/final/summary.json")
    pred = read("results/final/predictions.json")
    values = coords = hashes = 0
    assert len(maps) == 3
    for m in maps:
        tree = E.parse(ROOT / "figures" / (m["figure"] + ".svg"))
        ids = {n.get("id"): n for n in tree.iter() if n.get("id")}
        areas = []
        for i, a in enumerate(m["axes"]):
            points = vertices(ids["data-area-" + str(i)])
            areas.append(
                (
                    min(x for x, y in points),
                    max(x for x, y in points),
                    min(y for x, y in points),
                    max(y for x, y in points),
                )
            )
        for item in m["items"]:
            axis = m["axes"][item["axis"]]
            xmin, xmax = axis["xlim"]
            ymin, ymax = axis["ylim"]
            kind = item["kind"]
            if kind == "validation":
                name = item["model"]
                v = (
                    d["baseline_validation"]["macro_mae"]["value"]
                    if name == "previous-block"
                    else next(
                        r["validation"]["macro_mae"]["value"]
                        for r in search
                        if r["name"] == name
                    )
                )
                names = ["previous-block"] + [r["name"] for r in search]
                x = names.index(name)
                ymax_expected = (
                    max(
                        [d["baseline_validation"]["macro_mae"]["value"]]
                        + [r["validation"]["macro_mae"]["value"] for r in search]
                    )
                    * 1.3
                )
                assert (
                    axis == dict(xlim=[-0.6, 3.6], ylim=[0, ymax_expected])
                    and item["x"] == x
                    and item["width"] == 0.6
                )
                expected = [(x - 0.3, 0), (x + 0.3, 0), (x + 0.3, v), (x - 0.3, v)]
                assert (
                    item["value"] == v
                    and item["display"] == f"{v:.4f}"
                    and item["display"] in "".join(tree.getroot().itertext())
                )
                values += 1
            elif kind == "final":
                group = item["group"]
                model = item["model"]
                score = (
                    f["models"][model]["changed_primary"]
                    if group == "changed_primary"
                    else f["models"][model]["scenarios"][group]
                )
                v = score["macro_mae"]["value"]
                x = ["control", "shrink", "expand", "changed_primary"].index(group) + (
                    -0.17 if model == "previous-block" else 0.17
                )
                assert (
                    axis == dict(xlim=[-0.6, 3.6], ylim=[0, 0.1])
                    and item["x"] == x
                    and item["width"] == 0.29
                )
                expected = [
                    (x - 0.145, 0),
                    (x + 0.145, 0),
                    (x + 0.145, v),
                    (x - 0.145, v),
                ]
                assert (
                    item["value"] == v
                    and item["display"] == f"{v:.4f}"
                    and item["display"] in "".join(tree.getroot().itertext())
                )
                values += 1
            else:
                assert kind == "trajectory" and axis == dict(
                    xlim=[-0.3, 4.3], ylim=[0, 1]
                )
                trace = item["trace"]
                scenario = item["scenario"]
                view = item["view"]
                ys = []
                for t in range(160, 165):
                    row = next(
                        r
                        for r in pred
                        if r["trace"] == trace
                        and r["scenario"] == scenario
                        and r["block"] == t
                        and r["model"]
                        == ("previous-block" if view == "actual" else view)
                    )
                    ys.append(
                        row["target_count"] / 1000
                        if view == "actual"
                        else row["prediction"]["value"]
                    )
                assert item["x"] == list(range(5)) and item["values"] == ys
                expected = list(zip(range(5), ys))
                values += 5
            left, right, top, bottom = areas[item["axis"]]
            projected = [
                (
                    left + (x - xmin) / (xmax - xmin) * (right - left),
                    bottom - (y - ymin) / (ymax - ymin) * (bottom - top),
                )
                for x, y in expected
            ]
            actual = vertices(ids[item["id"]])
            assert len(actual) == len(projected), (item["id"], actual, projected)
            for (x, y), (a, b) in zip(actual, projected):
                assert abs(x - a) <= 3e-5 and abs(y - b) <= 3e-5, (
                    item["id"],
                    (x, y),
                    (a, b),
                )
                coords += 2
        for name, digest in m["files"].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
            hashes += 1
    result = dict(
        status="PASS_SOURCE_VALUES_AND_ACTUAL_SVG_GEOMETRY",
        figures=3,
        source_values=values,
        svg_coordinates=coords,
        file_hashes=hashes,
    )
    (ROOT / "figures/verification.json").write_bytes(
        (json.dumps(result, indent=2) + "\n").encode()
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
