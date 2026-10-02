"""Execute validated query plans against the uploaded DataFrame."""
import pandas as pd


def execute(plan: dict, df: pd.DataFrame) -> dict:
    work = df.copy()
    metric = plan.get("metric")
    agg = plan.get("aggregation") or "sum"
    group_by = plan.get("group_by") or []
    time_col = plan.get("time_column")
    bucket = plan.get("time_bucket")
    filters = plan.get("filters") or []
    comparison_values = plan.get("comparison_values") or []
    intent = plan.get("intent")

    used = list(dict.fromkeys(([metric] if metric else []) + group_by + ([time_col] if time_col else []) + [f.get("column") for f in filters]))
    for filt in filters:
        col, op, value = filt.get("column"), filt.get("op"), filt.get("value")
        if col not in work.columns:
            return _empty("A filter references a missing column.", used)
        if op == "==":
            work = work[work[col] == value]
        elif op == "!=":
            work = work[work[col] != value]
        elif op in (">", ">=", "<", "<="):
            left = pd.to_numeric(work[col], errors="coerce")
            right = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
            if pd.isna(right):
                return _empty("A numeric filter value could not be parsed.", used)
            work = work.loc[{">": left > right, ">=": left >= right, "<": left < right, "<=": left <= right}[op]]
        elif op == "in":
            work = work[work[col].isin(value if isinstance(value, list) else [value])]
        else:
            return _empty("Unsupported filter operator.", used)

    if metric and metric not in work.columns:
        return _empty("The requested measure is not in the dataset.", used)
    if any(col not in work.columns for col in group_by):
        return _empty("A grouping column is not in the dataset.", used)
    if metric:
        work[metric] = pd.to_numeric(work[metric], errors="coerce")
        work = work.dropna(subset=[metric])

    if time_col and bucket:
        if time_col not in work.columns:
            return _empty("The requested date column is not in the dataset.", used)
        parsed = pd.to_datetime(work[time_col], errors="coerce")
        work = work.loc[parsed.notna()].copy()
        parsed = parsed.loc[parsed.notna()]
        if bucket == "month":
            work["_period"] = parsed.dt.to_period("M").astype(str)
        elif bucket == "quarter":
            work["_period"] = parsed.dt.to_period("Q").astype(str)
        elif bucket == "week":
            work["_period"] = parsed.dt.to_period("W").astype(str)
        elif bucket == "year":
            work["_period"] = parsed.dt.to_period("Y").astype(str)
        else:
            work["_period"] = parsed.dt.strftime("%Y-%m-%d")

    if comparison_values:
        if len(group_by) != 1:
            return _empty("A comparison needs exactly one category column.", used)
        work = work[work[group_by[0]].astype(str).isin([str(v) for v in comparison_values])]
        if work[group_by[0]].nunique() < 2:
            return _empty("Both comparison categories must have matching rows.", used)

    group_cols = (["_period"] if "_period" in work.columns else []) + group_by
    if group_cols:
        if not metric:
            return _empty("A numeric measure is required for grouped analysis.", used)
        if agg not in ("sum", "mean", "count", "min", "max"):
            return _empty("Unsupported aggregation.", used)
        grouped = work.groupby(group_cols, dropna=False)[metric].agg(agg).reset_index(name="value")
        grouped["value"] = pd.to_numeric(grouped["value"], errors="coerce")
        grouped = grouped.dropna(subset=["value"])

        # Trends must be chronological. Ranking is sorted by metric instead.
        if intent in ("trend", "reason") and "_period" in grouped.columns:
            grouped = grouped.sort_values(["_period"] + group_by, kind="stable")
        else:
            grouped = grouped.sort_values("value", ascending=(plan.get("order") == "asc"), kind="stable")
        if intent == "ranking" and plan.get("top_n"):
            grouped = grouped.head(int(plan["top_n"]))
        table = _clean_records(grouped.to_dict(orient="records"))
        chart = {"type": "line" if intent == "trend" else "bar",
                 "x": "_period" if "_period" in grouped.columns else (group_by[0] if group_by else "index"),
                 "y": "value", "points": table}

        if intent in ("trend", "reason") and not group_by and len(table) >= 2:
            first, last = table[0], table[-1]
            percent = ((last["value"] - first["value"]) / abs(first["value"]) * 100) if first["value"] else None
            result = {"headline_value": last["value"], "headline_label": last["_period"],
                      "start_value": first["value"], "start_label": first["_period"],
                      "change_pct": round(percent, 2) if percent is not None else None, "unit": metric}
        elif intent == "ranking" and table:
            result = {"headline_value": table[0]["value"], "headline_label": table[0].get(group_by[0]), "unit": metric}
        elif intent == "comparison" and table:
            result = {"headline_value": table[0]["value"], "headline_label": table[0].get(group_by[0]),
                      "comparison_values": comparison_values, "unit": metric}
        elif len(table) == 1:
            result = {"headline_value": table[0]["value"], "unit": metric}
        else:
            result = {"headline_value": None, "unit": metric}
    elif metric:
        values = work[metric].dropna()
        if values.empty:
            return _empty("No valid numeric values remain for this measure.", used)
        value = values.agg(agg)
        result = {"headline_value": _number(value), "unit": metric}
        table = [{"metric": metric, "value": _number(value)}]
        chart = {"type": "bar", "x": "metric", "y": "value", "points": table}
    else:
        result = {"headline_value": int(len(work)), "unit": "rows"}
        table = [{"rows": int(len(work))}]
        chart = {"type": "bar", "x": "rows", "y": "rows", "points": table}

    return {"result": result, "table": table, "chart_data": chart,
            "columns_used": used, "row_count_used": int(len(work))}


def _number(value):
    number = float(value)
    return int(number) if number.is_integer() else number


def _clean_records(rows):
    cleaned = []
    for row in rows:
        cleaned.append({key: (_number(value) if isinstance(value, (int, float)) else value)
                        for key, value in row.items()})
    return cleaned


def _empty(reason, used):
    return {"result": None, "table": [], "chart_data": None, "columns_used": used,
            "row_count_used": 0, "error": reason}
