"""Convert a question into a validated plan; never substitute an unknown metric."""
import json
import os
import re
from openai import OpenAI


def _get_client():
    key = os.getenv("OPENAI_API_KEY")
    return OpenAI(api_key=key) if key else None


PLAN_SCHEMA = {
    "intent": "aggregation|comparison|trend|ranking|anomaly|reason|ambiguous|insufficient",
    "metric": "numeric column|null", "aggregation": "sum|mean|count|min|max",
    "group_by": ["column"], "filters": [{"column": "column", "op": "==", "value": "value"}],
    "time_column": "date column|null", "time_bucket": "day|week|month|quarter|year|null",
    "compare_period": "previous_period|previous_year|none", "comparison_values": ["category value"],
    "top_n": "integer|null", "order": "asc|desc|null", "reason_hypothesis": "boolean",
    "clarification_needed": "string|null",
}

SYSTEM_PROMPT = """Plan a business data query as strict JSON. Never calculate or invent values.
Use only supplied columns and observed category values. Select only the measure the
question names. If it does not identify a measure and several are available, return
intent=ambiguous and ask which measure. For a comparison of named category values,
set comparison_values to those exact observed values. For a comparison phrased as
"by <dimension>" (for example, average reach by content type), group by that
dimension and leave comparison_values empty to compare all categories. Respect
average/mean wording by using the mean aggregation. Set intent=insufficient if
the needed data is absent.
Allowed aggregations: sum, mean, count, min, max. Allowed time buckets: day, week,
month, quarter, year. Return every field in the supplied output schema."""


def _schema_for_prompt(profile: dict) -> dict:
    return {key: profile.get(key, default) for key, default in (
        ("columns", []), ("numeric_columns", []), ("date_columns", []),
        ("categorical_columns", []), ("likely_measures", []),
        ("categorical_values", {}), ("semantic_hints", {}),
    )}


def plan_question(question: str, schema_profile: dict) -> dict:
    client = _get_client()
    if client is None:
        return _heuristic_plan(question, schema_profile)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", temperature=0, response_format={"type": "json_object"},
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": json.dumps({
                "question": question, "schema": _schema_for_prompt(schema_profile), "output_schema": PLAN_SCHEMA,
            })}],
        )
        plan = json.loads(response.choices[0].message.content)
        return _validate_plan(_apply_question_defaults(plan, question, schema_profile), schema_profile)
    except Exception:
        # A transient model/API error should fall back to the deterministic planner.
        return _heuristic_plan(question, schema_profile)


def _validate_plan(plan: dict, profile: dict) -> dict:
    valid = set(profile.get("columns", []))
    measures = set(profile.get("likely_measures", profile.get("numeric_columns", [])))
    if plan.get("metric") not in measures:
        plan.update(intent="ambiguous", metric=None,
                    clarification_needed="Which numeric measure should I analyze?")
    plan["group_by"] = [c for c in plan.get("group_by", []) if c in valid]
    plan["filters"] = [f for f in plan.get("filters", []) if f.get("column") in valid and f.get("op") in ("==", "!=", ">", ">=", "<", "<=", "in")]
    if plan.get("time_column") not in profile.get("date_columns", []):
        plan["time_column"] = None
        if plan.get("intent") == "trend":
            plan.update(intent="ambiguous", clarification_needed="No usable date column was found.")
    if plan.get("aggregation") not in ("sum", "mean", "count", "min", "max"):
        plan["aggregation"] = "sum"
    if plan.get("time_bucket") not in (None, "day", "week", "month", "quarter", "year"):
        plan["time_bucket"] = None
    if plan.get("top_n") is not None:
        try:
            plan["top_n"] = max(1, min(100, int(plan["top_n"])))
        except (TypeError, ValueError):
            plan["top_n"] = None
    plan.setdefault("comparison_values", [])
    return plan


DIMENSION_ALIASES = {
    "media_type": ("content type", "media type", "post type", "format"),
    "content_category": ("content category", "category"),
    "day_of_week": ("day of week", "weekday", "day"),
    "performance_bucket_label": ("performance bucket", "performance label"),
}


def _dimension_mentioned(column: str, question: str) -> bool:
    q = question.lower().replace("_", " ")
    normalized = column.lower().replace("_", " ")
    if normalized in q:
        return True
    return any(alias in q for alias in DIMENSION_ALIASES.get(column, ()))


def _apply_question_defaults(plan: dict, question: str, profile: dict) -> dict:
    q = question.lower()
    if any(word in q for word in ("average", "mean", "on average")):
        plan["aggregation"] = "mean"
    if plan.get("intent") == "comparison":
        dimensions = profile.get("categorical_columns", [])
        mentioned = [column for column in dimensions if _dimension_mentioned(column, question)]
        if len(mentioned) == 1:
            plan["group_by"] = [mentioned[0]]
            # A comparison by a dimension means compare every category unless
            # the user explicitly named category values in the question.
            hits = [str(value) for column in dimensions
                    for value in profile.get("categorical_values", {}).get(column, [])
                    if str(value).lower() in q]
            if len(set(hits)) < 2:
                plan["comparison_values"] = []
    return plan


def _heuristic_plan(question: str, profile: dict) -> dict:
    q = question.lower().replace("_", " ")
    measures = profile.get("likely_measures", profile.get("numeric_columns", []))
    # Match an explicitly named column/measure. Never silently pick the first
    # column when multiple plausible measures exist.
    matches = [m for m in measures if m.lower().replace("_", " ") in q]
    if not matches:
        hint = profile.get("semantic_hints", {}).get("revenue")
        if hint and any(word in q for word in ("revenue", "sales", "income")):
            matches = [hint]
        hint = profile.get("semantic_hints", {}).get("quantity")
        if hint and any(word in q for word in ("units", "quantity", "volume")):
            matches = [hint]

    intent = "aggregation"
    if any(word in q for word in ("trend", "over time", "monthly", "by month", "quarterly", "yearly")):
        intent = "trend"
    if any(word in q for word in ("highest", "top", "most", "best", "largest", "ranking")):
        intent = "ranking"
    if any(word in q for word in ("why did", "decrease", "decreased", "decline", "drop", "increase", "increased", "grew")):
        intent = "reason"
    if any(word in q for word in ("compare", " versus ", " vs ")):
        intent = "comparison"
    if any(word in q for word in ("anomaly", "outlier", "unusual", "spike")):
        intent = "anomaly"

    metric = matches[0] if len(set(matches)) == 1 else None
    if metric is None and len(measures) == 1:
        metric = measures[0]
    plan = {
        "intent": intent, "metric": metric, "aggregation": "sum", "group_by": [],
        "filters": [], "time_column": None, "time_bucket": None,
        "compare_period": "previous_period" if intent == "reason" else "none",
        "comparison_values": [], "top_n": None, "order": "desc",
        "reason_hypothesis": intent == "reason",
    }

    date_columns = profile.get("date_columns", [])
    if intent in ("trend", "reason"):
        plan["time_column"] = date_columns[0] if date_columns else None
        plan["time_bucket"] = "quarter" if "quarter" in q else "year" if "year" in q else "month"

    # Find explicitly named dimensions and values observed in the dataset.
    dimensions = profile.get("categorical_columns", [])
    for column in sorted(dimensions, key=len, reverse=True):
        if _dimension_mentioned(column, question):
            plan["group_by"] = [column]
            break
    if intent == "ranking" and not plan["group_by"]:
        hint = profile.get("semantic_hints", {})
        candidate = hint.get("region") or hint.get("product")
        if candidate in dimensions:
            plan["group_by"] = [candidate]

    if intent == "comparison":
        value_hits = []
        for column in dimensions:
            for value in profile.get("categorical_values", {}).get(column, []):
                if str(value).lower() in q:
                    value_hits.append((column, str(value)))
        by_column = {}
        for column, value in value_hits:
            by_column.setdefault(column, []).append(value)
        candidates = [(column, vals) for column, vals in by_column.items() if len(set(vals)) >= 2]
        if len(candidates) == 1:
            plan["group_by"] = [candidates[0][0]]
            plan["comparison_values"] = list(dict.fromkeys(candidates[0][1]))
        elif plan["group_by"]:
            # "Compare metric by dimension" requests all categories in that
            # dimension; two explicit category values are not required.
            plan["comparison_values"] = []
        else:
            plan.update(intent="ambiguous", clarification_needed="Which two observed categories should I compare?")

    if any(word in q for word in ("average", "mean", "on average")):
        plan["aggregation"] = "mean"

    if intent == "ranking":
        found = re.search(r"\btop\s+(\d+)", q)
        plan["top_n"] = max(1, min(100, int(found.group(1)))) if found else 1
    if metric is None and intent not in ("ambiguous", "insufficient"):
        plan.update(intent="ambiguous", clarification_needed="Which numeric measure should I analyze?")
    if intent in ("trend", "reason") and not date_columns:
        plan.update(intent="ambiguous", clarification_needed="This question needs a date column, but none was detected.")
    return plan
