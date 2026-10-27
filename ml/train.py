"""Explicit training job (never runs inside an API request).
Usage: python -m ml.train --events events.json --out models/ [--horizon 90]
`events.json` is a list of NORMALISED records exported by the ingestion step."""
from __future__ import annotations
import argparse, hashlib, json, os, platform
import joblib, numpy as np, pandas as pd, sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from ml.data_preparation import build_panel, chronological_split
from ml.feature_engineering import FEATURES, events_frame

SEED = 42
DISCLAIMER = ("Retrospective recurrence-risk estimate from public FDA posting history. Not a calibrated "
              "probability, not validated for operational or clinical decisions.")


def compute_metrics(y_true, score, threshold) -> dict:
    y_true, score = np.asarray(y_true), np.asarray(score)
    pred = (score >= threshold).astype(int)
    both = len(set(y_true.tolist())) == 2
    return {
        "n": int(len(y_true)), "n_positive": int(y_true.sum()),
        "base_rate": float(y_true.mean()) if len(y_true) else None,
        "threshold": float(threshold),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "pr_auc": float(average_precision_score(y_true, score)) if both else None,
        "roc_auc": float(roc_auc_score(y_true, score)) if both else None,
        "brier": float(brier_score_loss(y_true, np.clip(score, 0, 1))),
    }


def _best_threshold(y, s) -> float:
    best, bt = -1.0, 0.5
    for t in np.unique(np.round(s, 4)):
        p = (s >= t).astype(int)
        tp = int(((p == 1) & (y == 1)).sum()); fp = int(((p == 1) & (y == 0)).sum()); fn = int(((p == 0) & (y == 1)).sum())
        f1 = 2 * tp / (2 * tp + fp + fn) if tp else 0.0
        if f1 > best:
            best, bt = f1, float(t)
    return bt


def _has_both(df): return df["label"].nunique() == 2


def train_and_evaluate(events: pd.DataFrame, out_dir: str, horizon_days: int = 90, step_days: int = 30,
                       min_test_positives: int = 30, min_rows: int = 200, min_products: int = 50) -> dict:
    panel = build_panel(events, horizon_days, step_days)
    base = {"horizon_days": horizon_days, "seed": SEED, "features": FEATURES, "disclaimer": DISCLAIMER}
    if panel.empty or len(panel) < min_rows or panel["product_key"].nunique() < min_products:
        n_prod = 0 if panel.empty else panel["product_key"].nunique()
        return {**base, "status": "unavailable",
                "reason": f"insufficient data ({len(panel)} rows / {n_prod} products; need >= {min_rows} / {min_products})"}
    train, val, test = chronological_split(panel, horizon_days)
    if not (_has_both(train) and len(val) and _has_both(val) and len(test) and _has_both(test)):
        return {**base, "status": "unavailable", "reason": "a chronological split lacks both classes"}

    Xtr, ytr = train[FEATURES], train["label"]
    models = {
        "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=SEED)),
        "hist_gradient_boosting": HistGradientBoostingClassifier(random_state=SEED, max_depth=3, max_iter=100),
    }
    val_ap, fitted = {}, {}
    for name, m in models.items():
        m.fit(Xtr, ytr)
        fitted[name] = m
        val_ap[name] = float(average_precision_score(val["label"], m.predict_proba(val[FEATURES])[:, 1]))
    best = max(val_ap, key=val_ap.get)
    model = fitted[best]
    thr = _best_threshold(val["label"].to_numpy(), model.predict_proba(val[FEATURES])[:, 1])
    ts = model.predict_proba(test[FEATURES])[:, 1]
    test_m = compute_metrics(test["label"], ts, thr)
    # transparent heuristic baseline: rank by postings in the last 365 days (a ranking, NOT a probability)
    heur = test["n_postings_365d"].to_numpy(dtype=float)
    heur_ap = float(average_precision_score(test["label"], heur))

    gates = {
        "enough_test_positives": test_m["n_positive"] >= min_test_positives,
        "beats_base_rate_1_5x": bool(test_m["pr_auc"] is not None and test_m["pr_auc"] >= 1.5 * test_m["base_rate"]),
        "beats_heuristic_baseline": bool(test_m["pr_auc"] is not None and test_m["pr_auc"] > heur_ap),
    }
    status = "passed_retrospective_checks" if all(gates.values()) else "experimental"
    span = lambda d: [str(d["as_of"].min().date()), str(d["as_of"].max().date())]
    meta = {**base, "status": status, "gates": gates, "selected_model": best, "validation_pr_auc": val_ap,
            "threshold": thr, "test_metrics": test_m, "heuristic_baseline_test_pr_auc": heur_ap,
            "periods": {"train": span(train), "validation": span(val), "test": span(test)},
            "class_balance": {k: {"rows": int(len(d)), "positives": int(d["label"].sum())}
                              for k, d in (("train", train), ("validation", val), ("test", test))},
            "library_versions": {"sklearn": sklearn.__version__, "pandas": pd.__version__, "python": platform.python_version()}}
    meta["version"] = "m-" + hashlib.sha1(json.dumps({k: meta[k] for k in ("periods", "seed", "selected_model", "horizon_days")}, sort_keys=True).encode()).hexdigest()[:8]
    os.makedirs(out_dir, exist_ok=True)
    joblib.dump(model, os.path.join(out_dir, "model.joblib"))
    with open(os.path.join(out_dir, "metadata.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", required=True); ap.add_argument("--out", default="models")
    ap.add_argument("--horizon", type=int, default=90)
    a = ap.parse_args()
    with open(a.events) as fh:
        ev = events_frame(json.load(fh))
    print(json.dumps(train_and_evaluate(ev, a.out, a.horizon), indent=2))
