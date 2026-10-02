"""Failure handling: insufficient evidence, ambiguity, validation failures."""

def check_insufficient(plan: dict, exec_result: dict, profile: dict):
    if plan.get("intent") == "insufficient":
        return _fail("insufficient_data",
                     "I cannot determine the answer from the available dataset.",
                     "The question references data that is not present in the uploaded file.")
    if not exec_result or exec_result.get("result") is None:
        return _fail("insufficient_data",
                     "I cannot determine the answer from the available dataset.",
                     exec_result.get("error", "No rows remained after filtering."))
    if exec_result.get("row_count_used", 0) == 0:
        return _fail("insufficient_data",
                     "I cannot determine the answer from the available dataset.",
                     "Zero rows matched the question's filters.")
    return None


def check_ambiguous(plan: dict):
    if plan.get("intent") == "ambiguous":
        return _fail("ambiguous_question",
                     "Your question is ambiguous — I need clarification before analyzing.",
                     plan.get("clarification_needed") or "Please specify the metric, dimension, or time period.")
    if plan.get("intent") in ("ranking", "reason", "trend") and not plan.get("metric"):
        return _fail("ambiguous_question",
                     "Your question is ambiguous — I need clarification before analyzing.",
                     "No numeric metric could be identified. Which measure should I analyze?")
    return None


def check_validation(exec_result: dict, profile: dict):
    res = exec_result.get("result") or {}
    val = res.get("headline_value")
    if val is None:
        return None
    if isinstance(val, float) and (val != val):
        return _fail("validation_failure",
                     "The calculated result failed validation and was flagged.",
                     "Computation produced NaN.")
    if isinstance(val, (int, float)) and abs(val) > 1e15:
        return _fail("validation_failure",
                     "The calculated result failed validation and was flagged.",
                     "Value exceeded plausibility bounds.")
    return None


def _fail(kind: str, message: str, detail: str) -> dict:
    return {"kind": kind, "message": message, "detail": detail}