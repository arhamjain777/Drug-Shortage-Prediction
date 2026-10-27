# Viva guide (starter)
1. **Objective?** Help pharmacies see reported shortages, estimate when *their own* stock runs out, and rank recurrence risk - keeping the three ideas separate.
2. **Three kinds of "risk"?** Reported shortage (a fact from FDA), stock-out forecast (arithmetic on my inventory), predicted risk (ML estimate).
3. **Days of supply?** usable stock / average daily use. **Reorder point** = daily use x (lead time + safety days).
4. **Why FEFO?** Oldest-expiry stock is used first; stock that expires before it can be used is not counted.
5. **Why ignore unconfirmed orders?** A promise is not stock. Counting it hides real risk.
6. **Why not a random train/test split?** Time data: random splitting lets the model "see the future". I split by date and purge overlaps.
7. **What is leakage?** Using information that would not exist at prediction time (e.g., today's shortage status for a past date).
8. **Why PR-AUC/recall, not accuracy?** Shortages are rare; predicting "never" scores high accuracy and is useless.
9. **Is the model reliable?** Only as shown by its metadata status; "experimental" by default. Scores are uncalibrated.
10. **Why doesn't the dataset cover India?** openFDA is US-only; the source layer is designed to accept other countries' sources.
11. **Idempotent ingestion?** Re-running a refresh changes nothing unless the source record changed (hash comparison).
12. **CSV injection?** Cells starting with = + - @ can run as spreadsheet formulas; I prefix them with an apostrophe.
13. **Why pure functions for the forecast?** Easy to test with exact numbers; the API and UI just call them.
14. **What is NOT finished?** See docs/PROGRESS.md - no database, auth or frontend yet. I will say so in the viva.
