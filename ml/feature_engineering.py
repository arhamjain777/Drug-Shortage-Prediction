"""Point-in-time feature engineering. The SAME function builds training rows and inference rows,
and it only ever looks at events posted on or before `as_of` (no future information).

Deliberately EXCLUDED: status, update_date, change_date, discontinued_date. openFDA stores only the
*current* value of these, so using them for a past date would leak the future.
"""
from __future__ import annotations
import pandas as pd

FEATURES = ["n_prior_postings", "n_postings_365d", "n_postings_90d", "days_since_last",
            "days_since_first", "n_companies", "is_injectable", "is_oral_solid"]
DAYS_CAP = 3650


def events_frame(normalised_records) -> pd.DataFrame:
    rows = []
    for r in normalised_records:
        if r.get("generic_name") and r.get("initial_posting_date"):
            rows.append({"product_key": r["generic_name"].strip().lower(),
                         "posted": r["initial_posting_date"],
                         "company": r.get("company_name") or "",
                         "dosage_form": (r.get("dosage_form") or "").lower()})
    df = pd.DataFrame(rows, columns=["product_key", "posted", "company", "dosage_form"])
    df["posted"] = pd.to_datetime(df["posted"]).dt.normalize()
    return df


def compute_features(events: pd.DataFrame, as_of) -> pd.DataFrame:
    as_of = pd.Timestamp(as_of).normalize()
    e = events[events["posted"] <= as_of]
    cols = ["product_key"] + FEATURES
    if e.empty:
        return pd.DataFrame(columns=cols)
    g = e.groupby("product_key")
    f = pd.DataFrame({
        "n_prior_postings": g["posted"].nunique(),
        "first": g["posted"].min(), "last": g["posted"].max(),
        "n_companies": g["company"].apply(lambda s: s[s != ""].nunique()),
    })
    for name, days in (("n_postings_365d", 365), ("n_postings_90d", 90)):
        w = e[e["posted"] > as_of - pd.Timedelta(days=days)].groupby("product_key")["posted"].nunique()
        f[name] = w.reindex(f.index).fillna(0).astype(int)
    f["days_since_last"] = (as_of - f["last"]).dt.days.clip(upper=DAYS_CAP)
    f["days_since_first"] = (as_of - f["first"]).dt.days.clip(upper=DAYS_CAP)
    latest = e.sort_values("posted").groupby("product_key")["dosage_form"].last()
    f["is_injectable"] = latest.reindex(f.index).str.contains("inject", na=False).astype(int)
    f["is_oral_solid"] = latest.reindex(f.index).str.contains("tablet|capsule", na=False).astype(int)
    return f.reset_index()[cols]
