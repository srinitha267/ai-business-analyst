"""Evaluate planner choices and compare computed outputs with a pandas reference."""
import json
import math
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.ingestion import ingest_file
from engine.schema_profiler import profile
from engine.planner import plan_question
from engine.executor import execute
from engine import guards

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "sample_sales.csv")
EVAL = os.path.join(os.path.dirname(__file__), "eval_set.json")


def _reference_table(plan, df):
    """Independent reference aggregation for this eval set's supported queries."""
    metric, agg = plan.get("metric"), plan.get("aggregation") or "sum"
    if not metric or metric not in df.columns:
        return None
    work = df.copy()
    work[metric] = pd.to_numeric(work[metric], errors="coerce")
    work = work.dropna(subset=[metric])
    dimension = (plan.get("group_by") or [None])[0]
    if plan.get("comparison_values") and dimension:
        work = work[work[dimension].astype(str).isin([str(v) for v in plan["comparison_values"]])]
    time_col, bucket = plan.get("time_column"), plan.get("time_bucket")
    if time_col and bucket:
        dates = pd.to_datetime(work[time_col], errors="coerce")
        work = work.loc[dates.notna()].copy()
        dates = dates.loc[dates.notna()]
        freq = {"month": "M", "quarter": "Q", "year": "Y", "week": "W"}.get(bucket)
        work["_period"] = dates.dt.to_period(freq).astype(str) if freq else dates.dt.strftime("%Y-%m-%d")
    group_cols = (["_period"] if "_period" in work.columns else []) + (plan.get("group_by") or [])
    if not group_cols:
        return [{"metric": metric, "value": float(work[metric].agg(agg))}]
    result = work.groupby(group_cols, dropna=False)[metric].agg(agg).reset_index(name="value")
    if plan.get("intent") in ("trend", "reason") and "_period" in result.columns:
        result = result.sort_values(["_period"] + (plan.get("group_by") or []), kind="stable")
    else:
        result = result.sort_values("value", ascending=(plan.get("order") == "asc"), kind="stable")
    if plan.get("intent") == "ranking" and plan.get("top_n"):
        result = result.head(int(plan["top_n"]))
    return result.to_dict(orient="records")


def _same_table(actual, expected, tolerance=1e-8):
    if actual is None or expected is None or len(actual) != len(expected):
        return False
    for got, want in zip(actual, expected):
        if got.keys() != want.keys():
            return False
        for key in want:
            left, right = got[key], want[key]
            if isinstance(right, (int, float)):
                if not isinstance(left, (int, float)) or not math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance):
                    return False
            elif str(left) != str(right):
                return False
    return True


def run():
    meta = ingest_file(DATA, "sample_sales.csv")
    prof = profile(meta["df"])
    prof["columns"] = meta["columns"]
    with open(EVAL, encoding="utf-8") as stream:
        questions = json.load(stream)

    rows = []
    for item in questions:
        plan = plan_question(item["question"], prof)
        expected = item["expected"]
        failure = guards.check_ambiguous(plan)
        if failure:
            ok = expected.get("failure") == failure["kind"]
            rows.append((item["id"], "PASS" if ok else "FAIL", failure["kind"]))
            continue

        actual = execute(plan, meta["df"])
        failure = guards.check_insufficient(plan, actual, prof) or guards.check_validation(actual, prof)
        if failure:
            ok = expected.get("failure") == failure["kind"]
            rows.append((item["id"], "PASS" if ok else "FAIL", failure["kind"]))
            continue

        ok = True
        if expected.get("metric") and plan.get("metric") != expected["metric"]:
            ok = False
        if expected.get("dimension") and expected["dimension"] not in plan.get("group_by", []):
            ok = False
        if expected.get("time_bucket") and plan.get("time_bucket") != expected["time_bucket"]:
            ok = False
        if expected.get("top") and plan.get("top_n") != expected["top"]:
            ok = False
        reference = _reference_table(plan, meta["df"])
        numeric_ok = _same_table(actual.get("table"), reference)
        ok = ok and numeric_ok
        detail = "plan and reference values match" if ok else f"plan={plan}; numeric_match={numeric_ok}"
        rows.append((item["id"], "PASS" if ok else "FAIL", detail))

    print(f"\n{'ID':6} {'RESULT':6} DETAIL")
    print("-" * 100)
    for row in rows:
        print(f"{row[0]:6} {row[1]:6} {row[2]}")
    passed = sum(result == "PASS" for _, result, _ in rows)
    print("-" * 100)
    print(f"PASSED: {passed}/{len(rows)}  FAILED: {len(rows) - passed}/{len(rows)}")
    return passed, len(rows)


if __name__ == "__main__":
    run()
