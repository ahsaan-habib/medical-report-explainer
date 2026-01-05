from conftest import REPORT
from medrep import guard, ranges
from medrep.models import Patient, Result
from medrep.parse import parse_rows


def by_test(results):
    return {r.test: r for r in results}


def test_table_rows_parse_exactly():
    results, leftovers = parse_rows(REPORT)
    r = by_test(results)
    assert r["Haemoglobin"].value == 11.2 and (r["Haemoglobin"].ref_low, r["Haemoglobin"].ref_high) == (12.0, 15.5)
    assert (r["Sodium"].ref_low, r["Sodium"].ref_high) == (135.0, 145.0)          # en dash
    assert (r["eGFR"].ref_low, r["eGFR"].ref_high) == (60.0, None)
    assert r["White cell count"].unit == "10^9/L" and r["White cell count"].ref_high == 11.0
    assert (r["Base excess"].ref_low, r["Base excess"].ref_high) == (-2.0, 2.0)
    assert all(x.ref_source == "report" for x in results)
    assert leftovers == ["Ferritin result was 8 ug/L (ref 15-150)", "Collected 2026-01-02"]


def test_ranges_prefer_the_report_then_table_then_unknown():
    printed = Result(test="Haemoglobin", value=11.2, unit="g/dL", ref_low=12.0, ref_high=15.5, ref_source="report")
    table = Result(test="Hb", value=14.0, unit="g/dL")
    unknown = Result(test="Haemoglobin", value=7.0, unit="mmol/L")
    out = ranges.ground([printed, table, unknown], Patient(sex="female", age=40))
    assert out[0].flag == "low" and out[0].ref_source == "report"
    assert out[1].flag == "normal" and out[1].ref_source.startswith("table: Haemoglobin (g/dL, female)")
    assert out[2].flag == "unknown"
    # sex-specific range, sex not given: don't guess
    assert ranges.ground([table], Patient())[0].flag == "unknown"
    # age outside the table's rows
    assert ranges.ground([table], Patient(sex="female", age=5))[0].flag == "unknown"


def test_guard_catches_diagnosis_advice_and_alarm():
    bad = ("Your haemoglobin is low, which suggests you may have anaemia. "
           "Start taking an iron supplement. This is nothing to worry about.")
    labels = " ".join(guard.problems(bad))
    for label in ("states a condition", "diagnostic framing", "names a condition", "treatment advice",
                  "reassurance or alarm"):
        assert label in labels
    assert guard.problems("Haemoglobin measures the oxygen-carrying protein in your blood.") == []


def test_numbers_must_come_from_the_results_and_units_count():
    results = [Result(test="White cell count", value=6.2, unit="10^9/L", ref_low=4.5, ref_high=11.0),
               Result(test="Haemoglobin", value=11.2, unit="g/dL", ref_low=12.0, ref_high=15.5)]
    ok = "White cell count: 6.2 10^9/L, range 4.5–11 10^9/L. Haemoglobin 11.2 g/dL is below 12."
    assert guard.numbers_grounded(ok, results) == []
    assert guard.numbers_grounded("Haemoglobin 11.2, most people are around 14.", results) == [
        "number not in the results (14)"]
    assert guard.numbers_grounded("You are 40.", results, extra=(40,)) == []


def test_negative_values_and_test_descriptions_are_not_flagged():
    results = [Result(test="Base excess", value=-1.0, unit="mmol/L", ref_low=-2.0, ref_high=2.0)]
    assert guard.numbers_grounded("Base excess: -1 mmol/L, range -2 to 2 mmol/L.", results) == []
    assert guard.problems("White cell count measures white blood cells, which fight infection.") == []
    assert guard.problems("You may have an infection.") and guard.problems("This is consistent with infection.")
