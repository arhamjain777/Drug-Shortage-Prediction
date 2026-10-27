import unittest
from datetime import date, timedelta
from backend.app.domain.forecast import (Batch, Incoming, ForecastInput, ScenarioAssumptions,
    compute_forecast, apply_scenario, compare_scenario, usable_stock_fefo)
from backend.app.domain.ledger import Movement, reconcile, InsufficientStock
from backend.app.domain.csv_safe import safe_cell, to_csv

D0 = date(2026, 1, 1)


def inp(**kw):
    base = dict(as_of=D0, batches=(Batch(100),), avg_daily_consumption=10, lead_time_days=5, safety_stock_days=2)
    base.update(kw)
    return ForecastInput(**base)


class ForecastTests(unittest.TestCase):
    def test_core_formulas(self):
        r = compute_forecast(inp())
        self.assertEqual(r.days_of_supply, 10)
        self.assertEqual(r.reorder_point, 70)            # 10 * (5+2)
        self.assertEqual(r.estimated_stockout_date, D0 + timedelta(days=10))
        self.assertEqual(r.status, "adequate")
        self.assertEqual(r.buffer_days_after_lead_time, 5)

    def test_below_reorder_and_replenishment_qty(self):
        r = compute_forecast(inp(batches=(Batch(60),)))
        self.assertEqual(r.status, "below_reorder")
        self.assertEqual(r.quantity_to_reach_reorder_point, 10)

    def test_coverage_shorter_than_lead(self):
        r = compute_forecast(inp(batches=(Batch(30),)))
        self.assertEqual(r.status, "coverage_shorter_than_lead")
        self.assertEqual(r.lead_time_gap_quantity, 20)

    def test_zero_demand_no_division(self):
        r = compute_forecast(inp(avg_daily_consumption=0))
        self.assertEqual(r.status, "no_demand_data")
        self.assertIsNone(r.days_of_supply)
        self.assertIsNone(r.estimated_stockout_date)
        self.assertTrue(r.warnings)

    def test_invalid_inputs_rejected(self):
        with self.assertRaises(ValueError):
            compute_forecast(inp(batches=(Batch(-1),)))
        with self.assertRaises(ValueError):
            compute_forecast(inp(avg_daily_consumption=-2))

    def test_expired_and_expiring_batches(self):
        b = (Batch(50, D0 - timedelta(days=1)), Batch(100, D0 + timedelta(days=5)), Batch(100))
        total, expired, usable = usable_stock_fefo(b, 10, D0)
        self.assertEqual((total, expired), (250, 50))
        # batch2 usable 5d*10=50 (50 wasted), batch3 100 -> 150
        self.assertEqual(usable, 150)
        self.assertEqual(compute_forecast(inp(batches=b)).days_of_supply, 15)

    def test_only_confirmed_incoming_counted(self):
        inc = (Incoming(100, D0 + timedelta(days=5), confirmed=False),)
        r = compute_forecast(inp(incoming=inc))
        self.assertEqual(r.days_of_supply_with_incoming, 10)
        inc = (Incoming(100, D0 + timedelta(days=5), confirmed=True),)
        r = compute_forecast(inp(incoming=inc))
        self.assertEqual(r.days_of_supply_with_incoming, 20)
        self.assertEqual(r.estimated_stockout_date, D0 + timedelta(days=20))

    def test_delivery_after_stockout_does_not_rescue(self):
        inc = (Incoming(1000, D0 + timedelta(days=30), confirmed=True),)
        self.assertEqual(compute_forecast(inp(incoming=inc)).days_of_supply_with_incoming, 10)

    def test_beyond_horizon(self):
        r = compute_forecast(inp(batches=(Batch(100000),)))
        self.assertTrue(r.stockout_beyond_horizon)
        self.assertIsNone(r.estimated_stockout_date)


class ScenarioTests(unittest.TestCase):
    def test_scenario_does_not_mutate_baseline(self):
        base = inp(incoming=(Incoming(50, D0 + timedelta(days=3), True),))
        snapshot = (base.batches, base.avg_daily_consumption, base.incoming)
        out = compare_scenario(base, ScenarioAssumptions(demand_change_pct=50, cancel_confirmed_orders=True))
        self.assertEqual(snapshot, (base.batches, base.avg_daily_consumption, base.incoming))
        self.assertTrue(out["hypothetical"])
        self.assertEqual(out["baseline"]["days_of_supply"], 10)
        self.assertAlmostEqual(out["scenario"]["days_of_supply"], 100 / 15)

    def test_delay_and_extra_replenishment(self):
        base = inp(incoming=(Incoming(100, D0 + timedelta(days=5), True),))
        delayed = compute_forecast(apply_scenario(base, ScenarioAssumptions(delay_confirmed_orders_days=10)))
        self.assertEqual(delayed.days_of_supply_with_incoming, 10)   # arrives day 15, stock-out day 10
        extra = compute_forecast(apply_scenario(inp(), ScenarioAssumptions(extra_replenishment_qty=100, extra_replenishment_in_days=5)))
        self.assertEqual(extra.days_of_supply_with_incoming, 20)

    def test_bad_scenario_rejected(self):
        with self.assertRaises(ValueError):
            apply_scenario(inp(), ScenarioAssumptions(demand_change_pct=-100))


class LedgerTests(unittest.TestCase):
    def test_reconciliation(self):
        ms = [Movement("receipt", 50), Movement("issue", 20), Movement("adjustment", -5, "count", "u1")]
        self.assertEqual(reconcile(10, ms), 35)

    def test_no_negative_stock(self):
        with self.assertRaises(InsufficientStock):
            reconcile(10, [Movement("issue", 11)])

    def test_adjustment_needs_reason_and_user(self):
        with self.assertRaises(ValueError):
            reconcile(10, [Movement("adjustment", 1)])


class CsvTests(unittest.TestCase):
    def test_formula_injection_neutralised(self):
        for bad in ("=1+1", "+cmd", "-2+3", "@SUM(A1)", "\tx"):
            self.assertTrue(safe_cell(bad).startswith("'"))
        self.assertEqual(safe_cell(-5), -5)
        out = to_csv([{"a": "=HYPERLINK()", "b": 3}], ["a", "b"])
        self.assertIn("'=HYPERLINK()", out)

if __name__ == "__main__":
    unittest.main()
