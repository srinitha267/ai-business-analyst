"""Detect useful data types and expose safe schema hints to the planner."""
import pandas as pd

DATE_HINTS = ("date", "month", "day", "year", "time", "period", "quarter", "qtr")
REVENUE_HINTS = ("revenue", "sales", "amount", "total", "price", "spend", "cost", "value", "income")
QTY_HINTS = ("qty", "quantity", "units", "count", "volume")
MEASURE_HINTS = (
    "reach", "impressions", "engagement", "likes", "comments", "shares", "saves",
    "followers", "views", "clicks", "conversions", "rate", "score", "profit", "margin",
)
REGION_HINTS = ("region", "territory", "area", "zone", "country", "state", "city")
PRODUCT_HINTS = ("product", "sku", "item", "category", "segment", "channel")


def _looks_like_date(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    sample = series.dropna().astype(str).head(50)
    if sample.empty:
        return False
    parsed = pd.to_datetime(sample, errors="coerce")
    return parsed.notna().mean() > 0.8


def _name_matches(name: str, hints) -> bool:
    normalized = name.lower().replace("_", " ")
    return any(h in normalized for h in hints)


def profile(df: pd.DataFrame) -> dict:
    """Return schema metadata; numeric IDs are excluded from measure candidates."""
    out = {
        "row_count": int(len(df)), "date_columns": [], "numeric_columns": [],
        "categorical_columns": [], "likely_measures": [], "likely_dimensions": [],
        "categorical_values": {},
        "semantic_hints": {"revenue": None, "quantity": None, "region": None, "product": None},
    }

    for col in df.columns:
        series = df[col]
        is_numeric = pd.api.types.is_numeric_dtype(series)
        is_date = _looks_like_date(series)
        if is_date and not is_numeric:
            out["date_columns"].append(col)
        elif is_numeric:
            out["numeric_columns"].append(col)
            unique_ratio = series.nunique(dropna=True) / max(1, series.notna().sum())
            looks_like_id = (col.lower().endswith("id") or col.lower() in ("id", "index", "row_number")) and unique_ratio > 0.8
            if not looks_like_id:
                # Include unnamed numeric measures too; the planner can then ask
                # the user to choose when a question does not identify one.
                out["likely_measures"].append(col)
            if _name_matches(col, REVENUE_HINTS):
                out["semantic_hints"]["revenue"] = col
            if _name_matches(col, QTY_HINTS):
                out["semantic_hints"]["quantity"] = col
        else:
            unique = series.nunique(dropna=True)
            if 1 < unique <= max(50, int(0.2 * len(df))):
                out["categorical_columns"].append(col)
                out["categorical_values"][col] = series.dropna().astype(str).value_counts().head(100).index.tolist()
            if _name_matches(col, REGION_HINTS):
                out["semantic_hints"]["region"] = col
            if _name_matches(col, PRODUCT_HINTS):
                out["semantic_hints"]["product"] = col

    out["likely_dimensions"] = out["categorical_columns"] + out["date_columns"]
    return out
