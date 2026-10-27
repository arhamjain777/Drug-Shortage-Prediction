"""Inventory forecasting engine (pure, deterministic, no I/O).

Every function here is an ESTIMATE based on the stated assumptions:
constant average daily demand, FEFO consumption, and only *confirmed*
incoming orders. Nothing here is a prediction of shortage events.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Optional

SIM_HORIZON_DAYS = 365  # stock-out dates beyond this are reported as "beyond horizon"


@dataclass(frozen=True)
class Batch:
    quantity: float
    expiry: Optional[date] = None  # None = no expiry recorded


@dataclass(frozen=True)
class Incoming:
    quantity: float
    expected_date: date
    confirmed: bool = False  # unconfirmed orders are NEVER counted as supply


@dataclass(frozen=True)
class ForecastInput:
    as_of: date
    batches: tuple
    avg_daily_consumption: float
    lead_time_days: float
    safety_stock_days: float = 0.0
    incoming: tuple = ()


@dataclass(frozen=True)
class ForecastResult:
    status: str  # no_demand_data | stocked_out | coverage_shorter_than_lead | below_reorder | adequate
    total_recorded_stock: float
    expired_stock: float
    usable_stock: float
    confirmed_incoming_counted: float
    days_of_supply: Optional[float]
    days_of_supply_with_incoming: Optional[float]
    estimated_stockout_date: Optional[date]
    stockout_beyond_horizon: bool
    reorder_point: float
    inventory_position: float
    quantity_to_reach_reorder_point: float
    lead_time_gap_quantity: float
    lead_time_coverage_ratio: Optional[float]
    buffer_days_after_lead_time: Optional[float]
    warnings: tuple

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["estimated_stockout_date"] = (
            self.estimated_stockout_date.isoformat() if self.estimated_stockout_date else None
        )
        d["warnings"] = list(self.warnings)
        return d


def validate_input(inp: ForecastInput) -> list:
    """Hard errors raise ValueError; soft issues are returned as warnings."""
    for b in inp.batches:
        if b.quantity < 0 or not math.isfinite(b.quantity):
            raise ValueError("batch quantity must be a finite number >= 0")
    for name in ("avg_daily_consumption", "lead_time_days", "safety_stock_days"):
        v = getattr(inp, name)
        if v < 0 or not math.isfinite(v):
            raise ValueError(f"{name} must be a finite number >= 0")
    for i in inp.incoming:
        if i.quantity < 0 or not math.isfinite(i.quantity):
            raise ValueError("incoming quantity must be a finite number >= 0")
    w = []
    if inp.avg_daily_consumption == 0:
        w.append("Average daily consumption is 0 or missing: days of supply cannot be estimated.")
    if inp.lead_time_days == 0:
        w.append("Supplier lead time is 0: coverage ratios are not meaningful.")
    return w


def usable_stock_fefo(batches, daily: float, as_of: date):
    """Return (total, expired, usable).

    Batches are consumed first-expiry-first-out at `daily` units/day. Units that
    would expire before demand reaches them are not counted as usable.
    A batch whose expiry date <= as_of is treated as already expired.
    """
    total = sum(b.quantity for b in batches)
    expired = sum(b.quantity for b in batches if b.expiry is not None and b.expiry <= as_of)
    live = [b for b in batches if b.expiry is None or b.expiry > as_of]
    if daily <= 0:
        return total, expired, sum(b.quantity for b in live)
    live.sort(key=lambda b: (b.expiry is None, b.expiry or date.max))
    t = 0.0  # days of demand already served
    usable = 0.0
    for b in live:
        if b.expiry is None:
            usable += b.quantity
            t += b.quantity / daily
            continue
        avail_days = (b.expiry - as_of).days - t
        use_days = min(b.quantity / daily, max(0.0, avail_days))
        usable += use_days * daily
        t += use_days
    return total, expired, usable


def _runout_days(usable: float, daily: float, deliveries) -> float:
    """Days until stock hits zero, given deliveries [(day_offset, qty)] sorted by day."""
    t, stock = 0.0, usable
    for d, q in deliveries:
        runout = t + stock / daily
        if runout < d:
            return runout
        stock = stock - daily * (d - t) + q
        t = float(d)
    return t + stock / daily


def compute_forecast(inp: ForecastInput) -> ForecastResult:
    warnings = validate_input(inp)
    daily = inp.avg_daily_consumption
    total, expired, usable = usable_stock_fefo(inp.batches, daily, inp.as_of)
    if expired > 0:
        warnings.append(f"{expired:g} units are expired and excluded from usable stock.")
    if usable < total - expired - 1e-9:
        warnings.append("Some stock is projected to expire before it can be consumed at current demand.")

    counted, deliveries = 0.0, []
    for i in inp.incoming:
        off = (i.expected_date - inp.as_of).days
        if not i.confirmed:
            warnings.append("Unconfirmed incoming order ignored (not treated as guaranteed supply).")
        elif off <= 0:
            warnings.append("Confirmed order with expected date on/before forecast date is overdue; excluded.")
        else:
            deliveries.append((off, i.quantity))
            counted += i.quantity
    deliveries.sort()

    rop = daily * (inp.lead_time_days + inp.safety_stock_days)
    position = usable + counted
    to_rop = max(0.0, rop - position)
    within_lead = sum(q for d, q in deliveries if d <= inp.lead_time_days)
    gap = max(0.0, daily * inp.lead_time_days - (usable + within_lead))

    if daily <= 0:
        return ForecastResult("no_demand_data", total, expired, usable, counted, None, None, None,
                              False, rop, position, to_rop, gap, None, None, tuple(warnings))

    dos = usable / daily
    dos_inc = _runout_days(usable, daily, deliveries)
    beyond = dos_inc > SIM_HORIZON_DAYS
    stockout = None if beyond else inp.as_of + timedelta(days=math.floor(dos_inc))
    ratio = dos_inc / inp.lead_time_days if inp.lead_time_days > 0 else None
    buffer_days = dos_inc - inp.lead_time_days

    if usable <= 0:
        status = "stocked_out"
    elif dos_inc < inp.lead_time_days:
        status = "coverage_shorter_than_lead"
    elif position < rop:
        status = "below_reorder"
    else:
        status = "adequate"
    return ForecastResult(status, total, expired, usable, counted, dos, dos_inc, stockout, beyond,
                          rop, position, to_rop, gap, ratio, buffer_days, tuple(warnings))


# ---------------- Scenario laboratory ----------------
@dataclass(frozen=True)
class ScenarioAssumptions:
    demand_change_pct: float = 0.0
    stock_change_pct: float = 0.0
    lead_time_delay_days: float = 0.0
    safety_stock_days_override: Optional[float] = None
    delay_confirmed_orders_days: int = 0
    cancel_confirmed_orders: bool = False
    extra_replenishment_qty: float = 0.0
    extra_replenishment_in_days: int = 0


def apply_scenario(inp: ForecastInput, a: ScenarioAssumptions) -> ForecastInput:
    """Return a NEW input; the original (frozen) object is never modified."""
    if a.demand_change_pct <= -100 or a.stock_change_pct < -100:
        raise ValueError("percentage change out of range")
    if a.extra_replenishment_qty < 0:
        raise ValueError("extra replenishment must be >= 0")
    k = 1 + a.stock_change_pct / 100
    batches = tuple(replace(b, quantity=b.quantity * k) for b in inp.batches)
    incoming = []
    for i in inp.incoming:
        if i.confirmed and a.cancel_confirmed_orders:
            continue
        if i.confirmed:
            i = replace(i, expected_date=i.expected_date + timedelta(days=a.delay_confirmed_orders_days))
        incoming.append(i)
    if a.extra_replenishment_qty > 0:
        incoming.append(Incoming(a.extra_replenishment_qty,
                                 inp.as_of + timedelta(days=a.extra_replenishment_in_days), True))
    return replace(
        inp, batches=batches, incoming=tuple(incoming),
        avg_daily_consumption=inp.avg_daily_consumption * (1 + a.demand_change_pct / 100),
        lead_time_days=inp.lead_time_days + a.lead_time_delay_days,
        safety_stock_days=inp.safety_stock_days if a.safety_stock_days_override is None
        else a.safety_stock_days_override)


def compare_scenario(inp: ForecastInput, a: ScenarioAssumptions) -> dict:
    base, scen = compute_forecast(inp), compute_forecast(apply_scenario(inp, a))

    def delta(x, y):
        return None if x is None or y is None else y - x
    return {
        "hypothetical": True,
        "baseline": base.to_dict(), "scenario": scen.to_dict(),
        "delta": {
            "days_of_supply_with_incoming": delta(base.days_of_supply_with_incoming, scen.days_of_supply_with_incoming),
            "reorder_point": scen.reorder_point - base.reorder_point,
            "lead_time_gap_quantity": scen.lead_time_gap_quantity - base.lead_time_gap_quantity,
            "buffer_days_after_lead_time": delta(base.buffer_days_after_lead_time, scen.buffer_days_after_lead_time),
        },
    }
