"""Audit trail builder: 7-step trace per the PPT."""
import time
from typing import Any

def build_trace(dataset_meta: dict, question: str, plan: dict, exec_result: dict, explanation: dict, guard_failure: dict | None) -> dict:
    steps = [
        {"step": 1, "name": "Question", "value": question},
        {"step": 2, "name": "Dataset", "value": dataset_meta.get("name"),
         "detail": f"{dataset_meta.get('rows')} rows × {len(dataset_meta.get('columns', []))} cols"},
        {"step": 3, "name": "Columns used", "value": exec_result.get("columns_used", [])},
        {"step": 4, "name": "Calculation / query", "value": _plan_summary(plan)},
        {"step": 5, "name": "Result", "value": exec_result.get("result")},
        {"step": 6, "name": "Explanation", "value": explanation.get("explanation") if explanation else None},
        {"step": 7, "name": "Recommendation", "value": explanation.get("recommendation") if explanation else None},
    ]
    if guard_failure:
        steps.append({"step": 8, "name": "Failure handling",
                      "value": guard_failure.get("kind"),
                      "detail": guard_failure.get("detail")})
    return {
        "steps": steps,
        "generated_at": time.time(),
        "plan_raw": plan,
    }


def _plan_summary(plan: dict) -> str:
    return (f"{plan.get('aggregation', 'count')}({plan.get('metric') or 'rows'}) "
            f"grouped by {plan.get('group_by') or plan.get('time_column') or 'none'} "
            f"order={plan.get('order')} top_n={plan.get('top_n')}")