# ML methodology (honest version)
**Task:** recurrence risk. For a product with >=1 prior FDA posting, will a NEW posting appear within H days (default 90)?
It cannot predict a product's first-ever shortage.

**Why this design:** a list of current shortages has no negatives. Using only products that eventually had shortages as "monitored" would leak the future. So a product enters the panel at its first posting, and negatives are later dates with no new posting.

**Leakage controls (all unit-tested):** features use only postings <= as_of; `status`/`update_date`/`discontinued_date` are excluded because openFDA stores only their *current* value; outcome windows must be fully observed; train/val/test are chronological with purging of rows whose outcome window crosses a boundary; no random splits.

**Models:** heuristic baseline (postings in last 365 d), Logistic Regression, HistGradientBoosting. Chosen on validation PR-AUC; threshold maximises validation F1; test set touched once.

**Status gates:** `unavailable` (too little data) -> `experimental` -> `passed_retrospective_checks` (>=30 test positives, PR-AUC >= 1.5x base rate, beats heuristic). Even the top status means "retrospective only", never "clinically reliable". Scores are labelled **uncalibrated**.

**Known biases:** only FDA-reported shortages; reporting practice changes over time; the same drug has many presentations; the first-posting date is not the shortage start date.

**Numbers:** none are reported here. The tests use SYNTHETIC data purely to prove the pipeline mechanics. Train on real ingested data to get real metrics.
