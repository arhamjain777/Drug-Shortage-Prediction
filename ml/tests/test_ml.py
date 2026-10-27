import json, os, tempfile, unittest
import numpy as np, pandas as pd
from ml.feature_engineering import compute_features, FEATURES
from ml.data_preparation import build_panel, chronological_split
from ml.train import train_and_evaluate, compute_metrics
from ml.inference import load_bundle, predict


def synthetic_events(n_products=150, seed=0):
    """SYNTHETIC test data only (never real shortages, never reported as results)."""
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_products):
        rate = rng.choice([0.002, 0.01, 0.03])        # per-day posting rate differs per product
        d = pd.Timestamp("2018-01-01") + pd.Timedelta(days=int(rng.integers(0, 300)))
        while d < pd.Timestamp("2024-12-31"):
            rows.append({"product_key": f"p{p}", "posted": d, "company": f"c{rng.integers(0,3)}",
                         "dosage_form": "injection" if p % 2 else "tablet"})
            d += pd.Timedelta(days=int(rng.exponential(1 / rate)) + 1)
    return pd.DataFrame(rows)


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.ev = pd.DataFrame({"product_key": ["a", "a", "b"],
            "posted": pd.to_datetime(["2023-01-10", "2023-06-01", "2023-03-01"]),
            "company": ["x", "y", ""], "dosage_form": ["tablet", "tablet", "injection"]})

    def test_no_future_leakage(self):
        as_of = "2023-04-01"
        before = compute_features(self.ev, as_of)
        future = pd.concat([self.ev, pd.DataFrame({"product_key": ["a", "c"],
            "posted": pd.to_datetime(["2023-09-01", "2023-10-01"]), "company": ["z", "z"], "dosage_form": ["tablet"] * 2})])
        after = compute_features(future, as_of)
        pd.testing.assert_frame_equal(before.reset_index(drop=True), after.reset_index(drop=True))
        self.assertNotIn("c", set(after["product_key"]))

    def test_values(self):
        f = compute_features(self.ev, "2023-07-01").set_index("product_key")
        self.assertEqual(f.loc["a", "n_prior_postings"], 2)
        self.assertEqual(f.loc["a", "days_since_last"], 30)
        self.assertEqual(f.loc["a", "n_postings_90d"], 1)
        self.assertEqual(f.loc["b", "is_injectable"], 1)
        self.assertEqual(f.loc["a", "n_companies"], 2)


class PanelTests(unittest.TestCase):
    def test_label_definition(self):
        ev = pd.DataFrame({"product_key": ["a", "a", "a"],
            "posted": pd.to_datetime(["2023-01-01", "2023-02-15", "2023-12-01"]), "company": [""] * 3, "dosage_form": [""] * 3})
        p = build_panel(ev, horizon_days=90, step_days=30, data_end="2023-12-01")
        first = p[p["as_of"] == pd.Timestamp("2023-01-01")].iloc[0]
        self.assertEqual(first["label"], 1)        # 2023-02-15 falls inside (Jan 1, Apr 1]
        mid = p[p["as_of"] == pd.Timestamp("2023-04-01")].iloc[0] if (p["as_of"] == pd.Timestamp("2023-04-01")).any() else None
        late = p[p["as_of"] > pd.Timestamp("2023-03-01")]
        self.assertTrue((late[late["as_of"] + pd.Timedelta(days=90) < pd.Timestamp("2023-12-01")]["label"] == 0).all())
        self.assertLessEqual(p["as_of"].max(), pd.Timestamp("2023-12-01") - pd.Timedelta(days=90))  # no censored outcomes

    def test_chronological_split_is_ordered_and_purged(self):
        panel = build_panel(synthetic_events(), 90, 30)
        tr, va, te = chronological_split(panel, 90)
        self.assertLess(tr["as_of"].max() + pd.Timedelta(days=90), va["as_of"].min() + pd.Timedelta(days=1))
        self.assertLessEqual(va["as_of"].max() + pd.Timedelta(days=90), te["as_of"].min())
        self.assertLess(va["as_of"].min(), te["as_of"].min())
        keys = lambda d: set(zip(d["as_of"], d["product_key"]))
        self.assertFalse(keys(tr) & keys(va) or keys(va) & keys(te) or keys(tr) & keys(te))


class TrainTests(unittest.TestCase):
    def test_pipeline_end_to_end_and_roundtrip(self):
        ev = synthetic_events()
        with tempfile.TemporaryDirectory() as d:
            meta = train_and_evaluate(ev, d)
            self.assertIn(meta["status"], ("experimental", "passed_retrospective_checks"))
            for k in ("periods", "class_balance", "test_metrics", "features", "threshold", "version", "seed"):
                self.assertIn(k, meta)
            self.assertTrue(os.path.exists(os.path.join(d, "model.joblib")))
            b = load_bundle(d)
            feats = compute_features(ev, "2024-06-01")
            out = predict(b, feats, "2024-06-01")
            self.assertTrue(out["available"])
            self.assertTrue(all(0 <= r["score"] <= 1 and r["calibrated"] is False for r in out["predictions"]))
            out2 = predict(load_bundle(d), feats, "2024-06-01")
            self.assertEqual([r["score"] for r in out["predictions"]], [r["score"] for r in out2["predictions"]])  # deterministic
            bad = feats.copy(); bad.loc[0, "days_since_last"] = np.nan
            self.assertEqual(predict(b, bad, "x")["skipped_invalid_rows"], 1)
            self.assertFalse(predict(b, feats.drop(columns=["n_companies"]), "x")["available"])

    def test_inadequate_data_is_unavailable_and_writes_nothing(self):
        ev = synthetic_events(n_products=3)
        with tempfile.TemporaryDirectory() as d:
            meta = train_and_evaluate(ev, d)
            self.assertEqual(meta["status"], "unavailable")
            self.assertEqual(os.listdir(d), [])
            self.assertFalse(predict(load_bundle(d), pd.DataFrame(), "x")["available"])

    def test_missing_model_dir_handled(self):
        self.assertFalse(load_bundle("/nonexistent")["available"])


class MetricTests(unittest.TestCase):
    def test_majority_class_predictor_exposed(self):
        y = [0] * 95 + [1] * 5
        m = compute_metrics(y, [0.0] * 100, 0.5)
        self.assertEqual(m["recall"], 0.0)
        self.assertEqual(m["base_rate"], 0.05)       # 95% "accuracy" would hide this
    def test_known_values(self):
        m = compute_metrics([1, 1, 0, 0], [0.9, 0.4, 0.6, 0.1], 0.5)
        self.assertAlmostEqual(m["precision"], 0.5); self.assertAlmostEqual(m["recall"], 0.5)

if __name__ == "__main__":
    unittest.main()
