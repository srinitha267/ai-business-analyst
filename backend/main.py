import os
import shutil
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from engine.ingestion import ingest_file, get_dataset
from engine.schema_profiler import profile
from engine.planner import plan_question
from engine.executor import execute
from engine.explainer import explain
from engine.trace import build_trace
from engine import guards

load_dotenv()

app = FastAPI(title="AI Business Analyst")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROFILES = {}
APPROVALS = {}
RECORDS = {}


class AskRequest(BaseModel):
    dataset_id: str
    question: str


class ApprovalRequest(BaseModel):
    answer_id: str
    decision: str
    note: str | None = None


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1])
    with open(tmp.name, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        meta = ingest_file(tmp.name, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    prof = profile(meta["df"])
    prof["columns"] = meta["columns"]
    PROFILES[meta["dataset_id"]] = prof
    return {
        "dataset_id": meta["dataset_id"],
        "name": meta["name"],
        "rows": meta["rows"],
        "columns": meta["columns"],
        "dtypes": meta["dtypes"],
        "profile": prof,
    }


@app.post("/ask")
async def ask(req: AskRequest):
    try:
        meta = get_dataset(req.dataset_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown dataset_id")
    prof = PROFILES[req.dataset_id]

    plan = plan_question(req.question, prof)

    amb = guards.check_ambiguous(plan)
    if amb:
        return _failure_response(req, meta, plan, amb)

    exec_result = execute(plan, meta["df"])

    ins = guards.check_insufficient(plan, exec_result, prof)
    if ins:
        return _failure_response(req, meta, plan, ins, exec_result)

    val = guards.check_validation(exec_result, prof)
    if val:
        return _failure_response(req, meta, plan, val, exec_result)

    explanation = explain(req.question, plan, exec_result, prof)
    trace = build_trace(meta, req.question, plan, exec_result, explanation, None)

    answer_id = f"{req.dataset_id}:{abs(hash(req.question)) % 10**8}"

    import time as _time
    RECORDS[answer_id] = {
        "answer_id": answer_id,
        "question": req.question,
        "dataset_name": meta["name"],
        "answer": explanation.get("answer"),
        "explanation": explanation.get("explanation"),
        "recommendation": explanation.get("recommendation"),
        "confidence": explanation.get("confidence"),
        "result": exec_result.get("result"),
        "columns_used": exec_result.get("columns_used"),
        "created_at": _time.strftime("%Y-%m-%d %H:%M:%S"),
        "decision": None,
        "note": None,
        "decided_at": None,
    }
    APPROVALS[answer_id] = {"status": "pending", "note": None}

    return {
        "status": "ok",
        "answer_id": answer_id,
        "answer": explanation.get("answer"),
        "explanation": explanation.get("explanation"),
        "recommendation": explanation.get("recommendation"),
        "confidence": explanation.get("confidence"),
        "evidence": {
            "result": exec_result.get("result"),
            "table": exec_result.get("table"),
            "columns_used": exec_result.get("columns_used"),
            "row_count_used": exec_result.get("row_count_used"),
        },
        "chart": exec_result.get("chart_data"),
        "trace": trace,
        "approval": APPROVALS[answer_id],
    }


@app.post("/approve")
async def approve(req: ApprovalRequest):
    if req.answer_id not in APPROVALS:
        raise HTTPException(status_code=404, detail="Unknown answer_id")
    if req.decision not in ("approve", "reject", "request_more"):
        raise HTTPException(status_code=400, detail="Invalid decision")

    import json, time, os
    APPROVALS[req.answer_id] = {"status": req.decision, "note": req.note}

    if req.answer_id in RECORDS:
        RECORDS[req.answer_id]["decision"] = req.decision
        RECORDS[req.answer_id]["note"] = req.note
        RECORDS[req.answer_id]["decided_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    log_path = os.path.join(os.path.dirname(__file__), "approvals_log.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(RECORDS.get(req.answer_id, {
            "answer_id": req.answer_id,
            "decision": req.decision,
            "note": req.note,
            "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })) + "\n")

    return {"answer_id": req.answer_id, "approval": APPROVALS[req.answer_id]}


@app.get("/records")
async def list_records():
    return list(RECORDS.values())


@app.get("/records/approved")
async def list_approved():
    return [r for r in RECORDS.values() if r["decision"] == "approve"]


@app.get("/health")
async def health():
    return {"ok": True}


def _failure_response(req, meta, plan, failure, exec_result=None):
    trace = build_trace(
        meta, req.question, plan,
        exec_result or {"columns_used": [], "result": None},
        None, failure,
    )
    return {
        "status": "insufficient",
        "failure": failure,
        "evidence": {"result": None, "table": [], "columns_used": [], "row_count_used": 0},
        "chart": None,
        "trace": trace,
        "approval": {"status": "blocked", "note": failure["kind"]},
    }