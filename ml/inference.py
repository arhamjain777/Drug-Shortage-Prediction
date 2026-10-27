"""Safe model loading + prediction. If the artefact is missing/corrupt, the result says so."""
from __future__ import annotations
import json, math, os
import joblib, pandas as pd
from ml.feature_engineering import FEATURES


def load_bundle(model_dir: str) -> dict:
    try:
        with open(os.path.join(model_dir, "metadata.json")) as fh:
            meta = json.load(fh)
        if meta.get("status") == "unavailable":
            return {"available": False, "reason": meta.get("reason", "no trained model")}
        model = joblib.load(os.path.join(model_dir, "model.joblib"))
        return {"available": True, "model": model, "meta": meta}
    except (FileNotFoundError, ValueError, OSError, EOFError) as e:
        return {"available": False, "reason": f"model artefact unavailable ({type(e).__name__})"}


def predict(bundle: dict, features: pd.DataFrame, features_as_of: str) -> dict:
    if not bundle.get("available"):
        return {"available": False, "reason": bundle.get("reason"), "predictions": []}
    missing = [c for c in FEATURES if c not in features.columns]
    if missing:
        return {"available": False, "reason": f"missing features: {missing}", "predictions": []}
    X = features[FEATURES]
    bad = X.isna().any(axis=1) | ~X.apply(lambda r: all(math.isfinite(v) for v in r), axis=1)
    ok = features[~bad]
    meta = bundle["meta"]
    probs = bundle["model"].predict_proba(ok[FEATURES])[:, 1] if len(ok) else []
    rows = [{"product_key": k, "score": float(p), "elevated": bool(p >= meta["threshold"]),
             "model_version": meta["version"], "model_status": meta["status"],
             "horizon_days": meta["horizon_days"], "features_as_of": features_as_of,
             "calibrated": False} for k, p in zip(ok["product_key"], probs)]
    return {"available": True, "model_status": meta["status"], "disclaimer": meta["disclaimer"],
            "skipped_invalid_rows": int(bad.sum()), "predictions": rows}
