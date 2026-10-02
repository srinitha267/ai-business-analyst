"""
Grounded explanation + recommendation.
The LLM receives ONLY computed evidence and may not invent numbers.
"""
import json
import os
from openai import OpenAI

def _get_client():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    return OpenAI(api_key=key)

EXPLAIN_SYSTEM = """You are the EXPLAINER of an AI business analyst engine.
You receive:
 - the user's question
 - a structured plan
 - computed evidence (real numbers from the dataset)
 - the columns used

RULES:
- You MUST NOT invent numbers. Only use numbers present in the evidence.
- You MUST scope the explanation to what the evidence supports.
- If evidence is insufficient to determine a CAUSE, say so explicitly.
- Output STRICT JSON: {"answer": str, "explanation": str, "recommendation": str, "confidence": "high|medium|low"}
- The "answer" is one plain-language sentence with the headline number.
- The "explanation" is 2-4 sentences grounded in the evidence.
- The "recommendation" is one actionable next step for a human reviewer.
"""

def explain(question: str, plan: dict, exec_result: dict, profile: dict) -> dict:
    client = _get_client()
    if client is None:
        return _heuristic_explain(question, plan, exec_result)

    payload = {
        "question": question,
        "plan": plan,
        "evidence": {
            "result": exec_result.get("result"),
            "table": exec_result.get("table"),
            "columns_used": exec_result.get("columns_used"),
            "row_count_used": exec_result.get("row_count_used"),
        },
        "schema_measures": profile.get("likely_measures"),
        "schema_dimensions": profile.get("likely_dimensions"),
    }
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": EXPLAIN_SYSTEM},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )
    return json.loads(resp.choices[0].message.content)


def _heuristic_explain(question: str, plan: dict, exec_result: dict) -> dict:
    """Offline grounded explanation built directly from evidence."""
    res = exec_result.get("result") or {}
    table = exec_result.get("table") or []
    intent = plan.get("intent")

    if intent == "comparison" and len(table) >= 2:
        top, bottom = table[0], table[-1]
        dim = plan.get("group_by", [None])[0]
        top_name, bottom_name = top.get(dim, "Top category"), bottom.get(dim, "Bottom category")
        difference = top["value"] - bottom["value"]
        answer = f"{top_name} has the highest {plan.get('aggregation', 'sum')} {res.get('unit')} at {top['value']:,.2f}; {bottom_name} has the lowest at {bottom['value']:,.2f}."
        explanation = f"The gap is {difference:,.2f} {res.get('unit')}, using {exec_result.get('row_count_used')} matching rows across the compared categories."
        recommendation = "Review the category-level results and confirm the metric definition before acting."

    elif intent == "ranking" and table:
        top = table[0]
        dim = plan.get("group_by", ["dimension"])[0] if plan.get("group_by") else "dimension"
        answer = f"{top.get(dim)} leads with {top['value']:,.2f} in {res.get('unit')}."
        explanation = f"Computed by aggregating {res.get('unit')} over {exec_result.get('row_count_used')} rows, grouped by {dim}."
        recommendation = f"Review the top contributors in {dim} to validate drivers and act."

    elif intent == "trend" and len(table) >= 2:
        first, last = table[0], table[-1]
        pct = res.get("change_pct")
        direction = "increased" if (pct or 0) >= 0 else "decreased"
        answer = (f"{res.get('unit')} {direction} by {abs(pct):.2f}% from "
                  f"{first.get('_period')} to {last.get('_period')}.") if pct is not None else \
                 f"Latest {res.get('unit')}: {last['value']:,.2f}."
        explanation = (f"Period-over-period change computed from {exec_result.get('row_count_used')} rows "
                       f"bucketed by {plan.get('time_bucket')}.")
        recommendation = "Investigate the periods with the largest movement for root cause."

    elif intent == "reason" and len(table) >= 2:
        first, last = table[0], table[-1]
        pct = res.get("change_pct")
        answer = f"{res.get('unit')} moved {pct:+.2f}% between {first.get('_period')} and {last.get('_period')}." if pct is not None else "Change computed."
        explanation = ("The dataset supports the size and direction of the change. "
                       "It does not contain enough evidence to attribute the change to a specific cause.")
        recommendation = "Request more analysis on segment-level drivers before acting."

    else:
        answer = f"Computed value: {res.get('headline_value'):,.2f} ({res.get('unit')})."
        explanation = f"Verified over {exec_result.get('row_count_used')} rows."
        recommendation = "Confirm the metric definition matches the business question."

    return {
        "answer": answer,
        "explanation": explanation,
        "recommendation": recommendation,
        "confidence": "medium",
    }
