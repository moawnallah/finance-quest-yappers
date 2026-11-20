import copy
import datetime as dt
import json
from pathlib import Path

import pytest
import yaml

from medium import AttemptError, question_view, reveal_view, score
from medium.build import NODES, SERIES, build, write
from medium.parts import Report, score_reasons
from medium.series import SeriesStore, TRANSFORMS, step_dates
from common import load_sources
from medium.task import compile_task, validate

DATA = Path(__file__).resolve().parent.parent
D1 = yaml.safe_load((NODES / "D1.yaml").read_text(encoding="utf-8"))
D1_TASK = {"node": "D1", "level": "medium", **D1["medium"][0]}
TODAY = dt.date(2026, 11, 20)


def store():
    return SeriesStore(SERIES / "series.csv", SERIES / "catalog.yaml")


def compiled(task, s=None):
    s = s or store()
    r = validate(task, s, TODAY, sources=load_sources())
    rec = None if r.errors else compile_task(task, s, r)
    return rec, r


@pytest.fixture(scope="module")
def records():
    return {tid: rec for tid, rec, _, _ in build()}


# ---------------------------------------------------------------- build and views

def test_samples_build_and_match_schema(tmp_path):
    results = build()
    assert results and all(rec for _, rec, _, _ in results), [r.errors for *_, r, _ in results]
    data = json.loads(write(results, tmp_path).read_text(encoding="utf-8"))
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(data, json.loads((DATA / "schemas" / "medium_tasks.schema.json").read_text(encoding="utf-8")))


def test_build_is_deterministic():
    assert [rec for _, rec, _, _ in build()] == [rec for _, rec, _, _ in build()]


def test_question_view_hides_answer_and_identity(records):
    for rec in records.values():
        dumped = json.dumps(question_view(rec)).lower()
        for secret in ("weight", "explain", "outcome", "truth", "\"name\"", "\"cutoff\"", "\"expected\""):
            assert secret not in dumped, (rec["id"], secret)
        assert rec["reveal"]["stimulus"][0]["cutoff"] not in dumped
        assert rec["reveal"]["stimulus"][0]["series"][0]["name"].lower() not in dumped
        points = question_view(rec)["stimulus"][0]["series"][0]["points"]
        assert points[-1]["t"] == 0 and all("d" not in p for p in points)


def test_localization_falls_back_to_english(records):
    rec = copy.deepcopy(records["d1.m1"])
    rec["question"]["brief"] = {"en": "Hello", "pl": "Cześć"}
    assert question_view(rec, "pl")["brief"] == "Cześć"
    assert question_view(rec, "de")["brief"] == "Hello"


def test_outcomes(records):
    assert records["d1.m1"]["reveal"]["outcome"]["direction"] == "down"
    assert records["d1.m1"]["reveal"]["outcome"]["change"] == pytest.approx(-8.0)
    d3 = records["d3.m1"]["reveal"]["outcome"]
    assert d3["direction"] == "up" and d3["unit"] == "pp" and d3["change"] == pytest.approx(0.22)


# ---------------------------------------------------------------- scoring

def test_reasons_formula_matches_spec():
    boxes = [{"id": "a", "weight": 1.0}, {"id": "b", "weight": 0.8}, {"id": "c", "weight": 0.5},
             {"id": "d", "weight": -1.0}, {"id": "e", "weight": 0.0}]
    assert score_reasons(boxes, ["a", "b"]) == 1.0                      # best two
    assert score_reasons(boxes, ["a", "c"]) == pytest.approx(1.5 / 1.8)
    assert score_reasons(boxes, ["a", "d"]) == 0.0                      # clipped
    assert score_reasons(boxes, ["a", "b", "e"]) == pytest.approx(1.8 / 2.3)


def test_day_x_is_graded_on_reasons_only(records):
    rec = records["d1.m1"]
    good = score(rec, "up", ["guidance", "capex", "priced_in"], confidence=5)  # wrong direction, still 1
    assert good["score"] == 1.0 and good["score_estimate"] is None and good["p"] == 1.0
    assert score(rec, "down", ["beat", "hindsight"])["score"] == 0.0


def test_outcome_truth_scores_direction():
    task = copy.deepcopy(D1_TASK)
    task.update(variant="estimate", truth="outcome")
    rec, r = compiled(task)
    assert rec, r.errors
    s = score(rec, "up", ["guidance", "capex", "priced_in"])
    assert s["score_estimate"] == 0.0 and s["score"] == pytest.approx(0.5)


@pytest.mark.parametrize("response, reasons, confidence", [
    ("flat", ["guidance", "capex"], None),            # not an option in D1
    ("down", ["guidance"], None),                     # fewer than pick.min
    ("down", ["guidance", "capex", "beat", "priced_in"], None),
    ("down", ["guidance", "guidance"], None),
    ("down", ["guidance", "nope"], None),
    ("down", ["guidance", "capex"], 6),
])
def test_bad_answers_raise(records, response, reasons, confidence):
    with pytest.raises(AttemptError):
        score(records["d1.m1"], response, reasons, confidence)


# ---------------------------------------------------------------- validation

@pytest.mark.parametrize("mutate, message", [
    (lambda t: t.update(id="x1.m1"), "must look like d1.m<n>"),
    (lambda t: t.update(id="d1.e1"), "must look like d1.m<n>"),
    (lambda t: t.update(sources=["nope"]), "unknown source"),
    (lambda t: t["reveal"].update(show=["everything"]), "reveal.show"),
    (lambda t: t.update(variant="day_x", truth="outcome"), "truth none"),
    (lambda t: t["stimulus"][0].update(kind="offer"), "not implemented"),
    (lambda t: t["response"].update(kind="number"), "not implemented"),
    (lambda t: t["stimulus"][0]["series"][0].update(series_id="nope"), "unknown series_id"),
    (lambda t: t["stimulus"][0]["series"][0].update(transform="rolling_5"), "transform"),
    (lambda t: t["stimulus"][0]["series"][0].pop("label"), "needs a `label`"),
    (lambda t: t["reasons"]["boxes"][0].update(weight=2), "from -1 to 1"),
    (lambda t: [b.update(weight=0) for b in t["reasons"]["boxes"]], "positive weight"),
    (lambda t: t["reasons"].update(pick={"min": 3, "max": 2}), "reasons.pick"),
    (lambda t: t.update(brief="Synthetic listed company (fictional) reports today."), "hidden name"),
    (lambda t: t.update(brief="The stock would later fall."), "hindsight"),
    (lambda t: t.update(valid_until="2020-01-01"), "in the past"),
    (lambda t: t["response"].update(expected="up"), "fact-check"),
])
def test_validation_errors(mutate, message):
    task = copy.deepcopy(D1_TASK)
    mutate(task)
    rec, r = compiled(task)
    assert rec is None and any(message in e for e in r.errors), r.errors


def test_hindsight_ok_allows_a_fact_known_on_day_x():
    # A day-X brief may state a crash that had already happened; the author marks the field.
    task = copy.deepcopy(D1_TASK)
    task["brief"] = "Markets crashed last week. The company reports today."
    rec, r = compiled(task)
    assert rec is None and any("hindsight" in e for e in r.errors)
    task["hindsight_ok"] = ["brief"]
    rec, r = compiled(task)
    assert rec, r.errors


def test_negative_boxes_may_be_hindsight():
    task = copy.deepcopy(D1_TASK)
    task["reasons"]["boxes"][-1]["text"] = "The stock eventually crashed"
    rec, r = compiled(task)
    assert rec, r.errors


# ---------------------------------------------------------------- real series from the table

def table_store(tmp_path, display=True):
    dates = step_dates(dt.date(2024, 3, 8), "daily", 80, 30)
    rows = "".join(f"real_x,{d.isoformat()},{100 + i},TestSource,CC BY 4.0\n" for i, d in enumerate(dates))
    (tmp_path / "series.csv").write_text("series_id,date,value,source,licence\n" + rows)
    (tmp_path / "catalog.yaml").write_text(yaml.safe_dump({"real_x": {
        "name": "Real X", "unit": "PLN", "frequency": "daily", "source": "TestSource",
        "licence": "CC BY 4.0", "display": display}}))
    return SeriesStore(tmp_path / "series.csv", tmp_path / "catalog.yaml")


def real_task(cutoff="2024-03-09"):
    task = copy.deepcopy(D1_TASK)
    task["stimulus"][0].update(cutoff=cutoff, hide=[])
    task["stimulus"][0]["series"] = [{"series_id": "real_x", "transform": "level"}]
    task["response"].update(options=["up", "down", "flat"], flat_band=0.5, expected="up")
    return task


def test_table_series_with_weekend_cutoff(tmp_path):
    rec, r = compiled(real_task(), table_store(tmp_path))  # 2024-03-09 is a Saturday
    assert rec, r.errors
    assert any("using 2024-03-08" in w for w in r.warnings)
    chart = question_view(rec)["stimulus"][0]
    assert chart["x_unit"] == "date" and chart["series"][0]["points"][-1]["d"] == "2024-03-08"
    assert chart["attribution"] == [{"source": "TestSource", "licence": "CC BY 4.0"}] and not chart["synthetic"]
    assert reveal_view(rec)["outcome"] == {"direction": "up", "change": 5.0, "unit": "PLN", "flat_band": 0.5, "steps": 5}


def test_series_without_display_licence_is_rejected(tmp_path):
    rec, r = compiled(real_task(), table_store(tmp_path, display=False))
    assert rec is None and any("may not be displayed" in e for e in r.errors)


def test_level_series_with_flat_needs_flat_band(tmp_path):
    task = real_task()
    del task["response"]["flat_band"]
    rec, r = compiled(task, table_store(tmp_path))
    assert rec is None and any("flat_band is required" in e for e in r.errors)


def test_transforms():
    dates = [dt.date(2023, m, 1) for m in range(1, 13)] + [dt.date(2024, m, 1) for m in range(1, 4)]
    values = [100.0] * 12 + [110.0, 105.0, 100.0]
    assert TRANSFORMS["index100"](dates, values, 12)[0] == pytest.approx(100 / 110 * 100)
    yoy = TRANSFORMS["yoy"](dates, values, 0)
    assert yoy[:12] == [None] * 12 and yoy[12] == pytest.approx(10.0) and yoy[14] == pytest.approx(0.0)


def test_reveal_show_defaults_to_everything(records):
    assert set(records["d1.m1"]["reveal"]["show"]) == {"truth", "outcome", "per_box_explain", "sources"}
