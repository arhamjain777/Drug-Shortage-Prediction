"""Build the (product, as_of) panel and the target, and split chronologically with purging.

TARGET: for a product that already has >=1 posting on/before as_of, label=1 if a NEW posting
appears in (as_of, as_of + horizon]. This is *recurrence* prediction; the model cannot predict a
product's first-ever shortage. A product enters the panel only at its first posting, so negatives
are not selected using knowledge of future shortages.
"""
from __future__ import annotations
import pandas as pd
from ml.feature_engineering import compute_features


def build_panel(events: pd.DataFrame, horizon_days: int = 90, step_days: int = 30, data_end=None) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data_end = pd.Timestamp(data_end if data_end is not None else events["posted"].max()).normalize()
    last_asof = data_end - pd.Timedelta(days=horizon_days)   # outcome window must be fully observed
    start = events["posted"].min()
    if last_asof < start:
        return pd.DataFrame()
    parts = []
    for as_of in pd.date_range(start, last_asof, freq=f"{step_days}D"):
        f = compute_features(events, as_of)
        if f.empty:
            continue
        fut = events[(events["posted"] > as_of) & (events["posted"] <= as_of + pd.Timedelta(days=horizon_days))]
        pos = set(fut["product_key"])
        f["label"] = f["product_key"].isin(pos).astype(int)
        f.insert(0, "as_of", as_of)
        parts.append(f)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def chronological_split(panel: pd.DataFrame, horizon_days: int, fractions=(0.6, 0.2, 0.2)):
    """Split by as_of date (never randomly). Rows whose outcome window reaches into the next
    period are PURGED so labels never peek across split boundaries."""
    dates = sorted(panel["as_of"].unique())
    n = len(dates)
    c1 = dates[max(0, int(n * fractions[0]) - 1)]
    c2 = dates[max(0, int(n * (fractions[0] + fractions[1])) - 1)]
    h = pd.Timedelta(days=horizon_days)
    val_start = panel[panel["as_of"] > c1]["as_of"].min()
    test_start = panel[panel["as_of"] > c2]["as_of"].min()
    train = panel[panel["as_of"] <= c1]
    if pd.notna(val_start):
        train = train[train["as_of"] + h <= val_start]
    val = panel[(panel["as_of"] > c1) & (panel["as_of"] <= c2)]
    if pd.notna(test_start):
        val = val[val["as_of"] + h <= test_start]
    test = panel[panel["as_of"] > c2]
    return train, val, test
