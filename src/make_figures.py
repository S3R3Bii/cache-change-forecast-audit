"""Show the retained search, simple-baseline win and complete transient groups."""

import hashlib, json, shutil
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "svg.fonttype": "none",
        "path.simplify": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "text.color": "#203d4c",
        "axes.labelcolor": "#203d4c",
        "savefig.facecolor": "white",
    }
)
COLORS = ["#6c7c86", "#b46128", "#245d74"]


def read(n):
    return json.loads((ROOT / n).read_text())


def finish(fig, axes, name, items):
    for i, ax in enumerate(axes):
        ax.patch.set_gid("data-area-" + str(i))
    for item in items:
        item.pop("artist").set_gid(item["id"])
    hashes = {}
    for ext in ["pdf", "svg", "png"]:
        p = ROOT / "figures" / (name + "." + ext)
        fig.savefig(p, dpi=150, metadata={"Date": None} if ext == "svg" else None)
        if ext == "svg":
            p.write_bytes(
                (
                    "\n".join(x.rstrip() for x in p.read_text().splitlines()) + "\n"
                ).encode()
            )
        hashes[p.relative_to(ROOT).as_posix()] = hashlib.sha256(
            p.read_bytes()
        ).hexdigest()
    shutil.copyfile(
        ROOT / "figures" / (name + ".pdf"), ROOT / "paper/images" / (name + ".pdf")
    )
    result = dict(
        figure=name,
        axes=[dict(xlim=list(a.get_xlim()), ylim=list(a.get_ylim())) for a in axes],
        items=items,
        files=hashes,
    )
    plt.close(fig)
    return result


def main():
    (ROOT / "paper/images").mkdir(parents=True, exist_ok=True)
    d = read("results/development/summary.json")
    search = read("results/development/search.json")
    f = read("results/final/summary.json")
    pred = read("results/final/predictions.json")
    selected = f["selected_name"]
    maps = []
    fig, ax = plt.subplots(figsize=(8.8, 4.6))
    fig.subplots_adjust(left=0.11, right=0.97, bottom=0.23, top=0.76)
    items = []
    values = [("previous-block", d["baseline_validation"]["macro_mae"]["value"])] + [
        (r["name"], r["validation"]["macro_mae"]["value"]) for r in search
    ]
    ymax = max(v for n, v in values) * 1.3
    for j, (name, value) in enumerate(values):
        artist = ax.bar(
            j,
            value,
            0.60,
            color=COLORS[0] if j == 0 else COLORS[2] if name == selected else COLORS[1],
        )[0]
        display = f"{value:.4f}"
        ax.text(j, value + ymax * 0.035, display, ha="center", fontsize=10)
        items.append(
            dict(
                artist=artist,
                id="validation-" + str(j),
                kind="validation",
                axis=0,
                model=name,
                x=j,
                width=0.60,
                value=value,
                display=display,
            )
        )
    ax.set(
        xticks=range(4),
        xticklabels=["Previous block"] + ["Ridge λ=" + r["lambda"] for r in search],
        xlim=(-0.6, 3.6),
        ylim=(0, ymax),
        ylabel="Validation macro MAE (miss-fraction units)",
        xlabel="Fixed candidate grid; smallest validation MAE selects λ=0.01",
    )
    ax.yaxis.grid(alpha=0.16)
    ax.set_axisbelow(True)
    fig.suptitle(
        "Development favored the previous-block baseline",
        x=0.11,
        y=0.97,
        ha="left",
        fontsize=15,
        weight="bold",
    )
    fig.text(
        0.11,
        0.87,
        "120 validation origins from three development volumes; 512 equal-object slots throughout.",
        fontsize=10,
    )
    maps.append(finish(fig, [ax], "validation_search", items))
    fig, ax = plt.subplots(figsize=(8.8, 4.9))
    fig.subplots_adjust(left=0.11, right=0.97, bottom=0.26, top=0.70)
    items = []
    groups = ["control", "shrink", "expand", "changed_primary"]
    for j, group in enumerate(groups):
        for i, model in enumerate(["previous-block", selected]):
            m = (
                f["models"][model]["changed_primary"]
                if group == "changed_primary"
                else f["models"][model]["scenarios"][group]
            )
            value = m["macro_mae"]["value"]
            x = j + [-0.17, 0.17][i]
            artist = ax.bar(
                x,
                value,
                0.29,
                color=COLORS[0] if i == 0 else COLORS[2],
                label=(
                    "Previous block"
                    if i == 0 and j == 0
                    else "Frozen linear model" if i == 1 and j == 0 else None
                ),
            )[0]
            display = f"{value:.4f}"
            ax.text(x, value + 0.003, display, ha="center", fontsize=8)
            items.append(
                dict(
                    artist=artist,
                    id="final-" + group + "-" + str(i),
                    kind="final",
                    axis=0,
                    model=model,
                    group=group,
                    x=x,
                    width=0.29,
                    value=value,
                    display=display,
                )
            )
    ax.set(
        xticks=range(4),
        xticklabels=["512 unchanged", "512 → 128", "512 → 2,048", "Changed combined"],
        xlim=(-0.6, 3.6),
        ylim=(0, 0.1),
        ylabel="Final macro MAE (miss-fraction units)",
    )
    ax.legend(frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, 1.21))
    ax.yaxis.grid(alpha=0.16)
    ax.set_axisbelow(True)
    fig.suptitle(
        "The simple baseline keeps lower MAE after capacity changes",
        x=0.11,
        y=0.97,
        ha="left",
        fontsize=15,
        weight="bold",
    )
    fig.text(
        0.11,
        0.87,
        "Three other volumes × 40 final blocks per scenario. No final refit or reselection.",
        fontsize=10,
    )
    fig.text(
        0.11,
        0.08,
        "Combined repeats the two changed scenarios; it is not an additional independent sample.",
        fontsize=9,
    )
    maps.append(finish(fig, [ax], "final_scenarios", items))
    traces = [
        p["trace"]
        for p in read("data/source_plan.json")["traces"]
        if p["phase"] == "final"
    ]
    fig, grid = plt.subplots(3, 2, figsize=(8.8, 7.2))
    axes = list(grid.flat)
    fig.subplots_adjust(
        left=0.10, right=0.97, bottom=0.13, top=0.77, hspace=0.55, wspace=0.25
    )
    items = []
    for row, trace in enumerate(traces):
        for col, scenario in enumerate(["shrink", "expand"]):
            index = row * 2 + col
            ax = axes[index]
            observed = [
                r
                for r in pred
                if r["trace"] == trace
                and r["scenario"] == scenario
                and r["model"] == "previous-block"
                and r["block"] < 165
            ]
            observed = sorted(observed, key=lambda r: r["block"])
            for j, view in enumerate(["actual", "previous-block", selected]):
                values = (
                    [r["target_count"] / 1000 for r in observed]
                    if view == "actual"
                    else [
                        next(
                            r["prediction"]["value"]
                            for r in pred
                            if r["trace"] == trace
                            and r["scenario"] == scenario
                            and r["model"] == view
                            and r["block"] == t
                        )
                        for t in range(160, 165)
                    ]
                )
                artist = ax.plot(
                    range(5),
                    values,
                    color=[COLORS[1], COLORS[0], COLORS[2]][j],
                    marker=["o", "s", "^"][j],
                    ms=3,
                    lw=1.2,
                    ls=["-", "--", ":"][j],
                    label=["Simulated actual", "Previous block", "Frozen linear model"][
                        j
                    ],
                )[0]
                items.append(
                    dict(
                        artist=artist,
                        id="transient-" + str(index) + "-" + str(j),
                        kind="trajectory",
                        axis=index,
                        trace=trace,
                        scenario=scenario,
                        view=view,
                        x=list(range(5)),
                        values=values,
                    )
                )
            ax.set(
                xlim=(-0.3, 4.3),
                ylim=(0, 1),
                xticks=range(5),
                title=trace + " · " + scenario,
            )
            ax.grid(alpha=0.13)
            ax.set_axisbelow(True)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        frameon=False,
        ncol=3,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.87),
    )
    fig.suptitle(
        "The first five blocks after the authored change",
        x=0.10,
        y=0.97,
        ha="left",
        fontsize=15,
        weight="bold",
    )
    fig.text(
        0.10,
        0.91,
        "All six changed volume/scenario groups; equal request counts do not imply equal elapsed time.",
        fontsize=9,
    )
    fig.supxlabel("Blocks since change (0 is source block 160)", y=0.055, fontsize=10)
    fig.supylabel("Miss fraction per 1,000-request block", x=0.015, fontsize=10)
    maps.append(finish(fig, axes, "change_transients", items))
    (ROOT / "figures/value_map.json").write_bytes(
        (json.dumps(maps, indent=2) + "\n").encode()
    )
    print(
        json.dumps(
            dict(
                figures=3,
                source_values=sum(
                    len(i["values"]) if i["kind"] == "trajectory" else 1
                    for m in maps
                    for i in m["items"]
                ),
            )
        )
    )


if __name__ == "__main__":
    main()
