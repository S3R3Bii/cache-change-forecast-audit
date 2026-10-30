"""Bind paper values to checked JSON and verify the primary-loss qualification."""

import ast, hashlib, json
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def read(n):
    return json.loads((ROOT / n).read_text())


def main():
    text = (ROOT / "paper/main.tex").read_text()
    bindings = read("paper_bindings.json")
    pdf = PdfReader(ROOT / "paper/manuscript.pdf")
    assert len(pdf.pages) == 6
    pages = [p.extract_text() or "" for p in pdf.pages]
    assert all(p.strip() for p in pages)
    flat = "\n".join(pages)
    checks = 0
    for name, item in bindings.items():
        path = (ROOT / item["file"]).resolve()
        assert path.is_relative_to(ROOT) and path.suffix == ".json"
        value = json.loads(path.read_text())
        for key in item["pointer"]:
            value = value[key]
        if item["kind"] == "length":
            value = len(value)
        else:
            assert item["kind"] == "value"
        assert item["value"] == value
        checks += 1
        fmt = (
            "integer_grouped"
            if type(value) is int and abs(value) >= 1000
            else "six_decimal" if type(value) is float else "text"
        )
        display = (
            f"{value:,}"
            if fmt == "integer_grouped"
            else f"{value:.6f}" if fmt == "six_decimal" else str(value)
        )
        assert item["format"] == fmt and item["display"] == display
        checks += 1
        assert (
            "\\newcommand{\\" + name + "}{" + display + "}" in text
            and text.count("\\" + name) >= 2
        )
        checks += 1
        assert display in flat
        (checks := checks + 1)
    assert len(bindings) == 70
    checks += 1
    f = read("results/final/summary.json")
    b = f["models"]["previous-block"]
    s = f["models"][f["selected_name"]]
    assert (
        b["changed_primary"]["macro_mae"]["value"]
        < s["changed_primary"]["macro_mae"]["value"]
    )
    checks += 1
    assert (
        b["changed_primary"]["macro_mse"]["value"]
        > s["changed_primary"]["macro_mse"]["value"]
    )
    checks += 1
    assert (
        "mean squared error (MSE) favors the linear model" in text
        and "recommendation below concerns the predeclared MAE objective" in text
    )
    checks += 1
    for scenario in ["control", "shrink", "expand"]:
        for key, row in b["scenarios"][scenario]["per_group"].items():
            assert (
                row["mae"]["value"]
                < s["scenarios"][scenario]["per_group"][key]["mae"]["value"]
            )
            checks += 1
    assert len(read("data/dependency_freeze.json")["files"]) == 47
    checks += 1
    fixtures = sum(
        isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
        for p in (ROOT / "tests").glob("test_*.py")
        for n in ast.walk(ast.parse(p.read_text()))
    )
    assert fixtures == 27 and "Twenty-seven fixture methods" in text
    checks += 1
    source = read("data/source_receipts.json")
    assert len(source) == 6 and all(
        r["status"] == 200 and r["retry_attempt"] is False for r in source
    )
    checks += 1
    assert (
        sum(r["bytes"] for r in source)
        == 126293595
        == read("data/source_verification.json")["source_bytes"]
    )
    checks += 1
    assert all(
        q["records"] == 200000
        and q["clock_regressions"] == 0
        and q["future_field_decoded"] is False
        for q in read("data/qualification_ledger.json")
    )
    checks += 1
    assert (
        read("data/source_plan.json")["source_listing_objects"] == 14
        and "thirteen-trace summary" in text
    )
    checks += 1
    for phrase in [
        "3--119",
        "120--159",
        "160--199",
        "first 200,000 complete 24-byte records",
        "three prior completed miss fractions",
        "0.01,1,100",
        "not $\\lambda n$",
        "no validation refit",
        "no cold restart",
        "not blinded",
        "not peer reviewed",
        "does not resurrect",
        "no asserted calendar-time unit",
    ]:
        candidate = (
            text.lower()
            if phrase in ["no cold restart", "no asserted calendar-time unit"]
            else text
        )
        actual_phrase = (
            "without an asserted calendar-time unit"
            if phrase == "no asserted calendar-time unit"
            else phrase
        )
        assert actual_phrase in candidate, actual_phrase
        checks += 1
    build = read("paper/build_receipt.json")
    assert (
        build["status"] == "PASS_COMPILE_AND_SIX_PAGE_VISUAL_REVIEW"
        and build["pages"] == 6
        and not build["layout_warnings"]
    )
    checks += 1
    for path, digest in build["artifact_sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
        checks += 1
    for p in (ROOT / "paper/images").glob("*.pdf"):
        assert p.read_bytes() == (ROOT / "figures" / p.name).read_bytes()
        checks += 1
    result = dict(
        status="PASS_SOURCE_BOUND_MANUSCRIPT",
        pages=6,
        bound_measurements=len(bindings),
        conditions=checks,
        manuscript_sha256=hashlib.sha256(
            (ROOT / "paper/manuscript.pdf").read_bytes()
        ).hexdigest(),
        page_characters=[len(x) for x in pages],
        primary_MAE_and_opposite_MSE_result_explicit=True,
        rendering="Local Poppler inspection and current-render identity proof; CI checks bound values and artifact identity without compiling TeX.",
    )
    (ROOT / "paper_verification.json").write_bytes(
        (json.dumps(result, indent=2) + "\n").encode()
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
