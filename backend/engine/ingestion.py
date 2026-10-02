"""Data ingestion: load CSV/Excel into a normalized DataFrame + dataset registry."""
import os
import uuid
import pandas as pd
from typing import Dict

DATASET_STORE: Dict[str, dict] = {}   # dataset_id -> {df, name, columns, dtypes, path}

def ingest_file(path: str, original_name: str) -> dict:
    """Load a file into memory and register it. Returns dataset metadata."""
    ext = os.path.splitext(original_name)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(path)
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    # Normalize column names (trim whitespace)
    df.columns = [str(c).strip() for c in df.columns]

    dataset_id = str(uuid.uuid4())
    meta = {
        "dataset_id": dataset_id,
        "name": original_name,
        "path": path,
        "df": df,
        "rows": int(len(df)),
        "columns": list(df.columns),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
    }
    DATASET_STORE[dataset_id] = meta
    return meta

def get_dataset(dataset_id: str) -> dict:
    if dataset_id not in DATASET_STORE:
        raise KeyError(f"Unknown dataset_id: {dataset_id}")
    return DATASET_STORE[dataset_id]