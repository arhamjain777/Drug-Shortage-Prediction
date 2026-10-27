"""Business logic that touches the database. Pure maths lives in backend/app/domain/."""
import logging
from datetime import date, datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.domain.forecast import Batch as FBatch, ForecastInput, Incoming, compute_forecast
from backend.app.domain.ledger import InsufficientStock, Movement as LMove, apply_movement
from backend.app.models import Batch, IngestionRun, InventoryItem, Movement, Order, ShortageRecord
from ingestion.fetch_sources import OpenFDAClient, SourceUnavailable
from ingestion.normalise import plan_upsert

log = logging.getLogger("mediwatch.services")
OUT_KINDS = ("issue", "transfer_out")


def item_forecast_input(item: InventoryItem, as_of: date | None = None) -> ForecastInput:
    as_of = as_of or date.today()
    return ForecastInput(
        as_of=as_of,
        batches=tuple(FBatch(b.quantity, b.expiry) for b in item.batches),
        avg_daily_consumption=item.avg_daily_consumption,
        lead_time_days=item.lead_time_days,
        safety_stock_days=item.safety_stock_days,
        incoming=tuple(Incoming(o.quantity, o.expected_date, o.confirmed) for o in item.orders if not o.received),
    )


def item_forecast(item: InventoryItem, as_of: date | None = None):
    return compute_forecast(item_forecast_input(item, as_of))


def stock_total(item: InventoryItem) -> float:
    return sum(b.quantity for b in item.batches)


def apply_stock_movement(db: Session, item: InventoryItem, kind: str, qty: float, user, reason="",
                         expiry: date | None = None, lot: str | None = None) -> Movement:
    """One transaction: validate -> change batches -> append ledger row. Caller commits."""
    total = stock_total(item)
    mv = LMove(kind, qty, reason, user.email)
    new_total = apply_movement(total, mv)          # raises ValueError / InsufficientStock
    signed = new_total - total
    if signed > 0:
        item.batches.append(Batch(quantity=signed, expiry=expiry, lot=lot))
    else:
        need = -signed
        today = date.today()
        pool = sorted(item.batches, key=lambda b: (b.expiry is None, b.expiry or date.max))
        if kind in OUT_KINDS:   # expired stock can only be written off via adjustment
            pool = [b for b in pool if b.expiry is None or b.expiry > today]
            if sum(b.quantity for b in pool) < need:
                raise InsufficientStock("not enough non-expired stock; expired stock needs an adjustment write-off")
        for b in pool:
            take = min(b.quantity, need)
            b.quantity -= take
            need -= take
            if need <= 1e-9:
                break
        for b in [b for b in item.batches if b.quantity <= 1e-9]:
            item.batches.remove(b)
    row = Movement(item_id=item.id, kind=kind, quantity=qty, balance_after=new_total, reason=reason, user_id=user.id)
    db.add(row)
    return row


def run_refresh(db: Session, user=None, client: OpenFDAClient | None = None) -> IngestionRun:
    """Fetch openFDA, upsert idempotently. A failed fetch NEVER deletes stored data."""
    run = IngestionRun(triggered_by=user.id if user else None)
    db.add(run); db.commit()
    client = client or OpenFDAClient(api_key=settings.openfda_api_key)
    try:
        raw = client.fetch_all()
        existing = dict(db.execute(select(ShortageRecord.source_key, ShortageRecord.content_hash)).all())
        plan = plan_upsert(existing, raw)
        for n in plan.inserts:
            db.add(ShortageRecord(**_to_row(n), first_seen_run_id=run.id))
        by_key = {}
        if plan.updates:
            keys = [n["source_key"] for n in plan.updates]
            by_key = {r.source_key: r for r in db.scalars(select(ShortageRecord).where(ShortageRecord.source_key.in_(keys)))}
        for n in plan.updates:
            for k, v in _to_row(n).items():
                setattr(by_key[n["source_key"]], k, v)
        run.fetched, run.inserted, run.updated = len(raw), len(plan.inserts), len(plan.updates)
        run.unchanged, run.duplicates, run.rejected = plan.unchanged, plan.duplicates, len(plan.rejected)
        run.status = "success"
    except SourceUnavailable as e:
        db.rollback(); db.add(run)
        run.status, run.error = "failed", str(e)
        log.warning("refresh failed: %s", e)
    except Exception:
        db.rollback(); db.add(run)
        run.status, run.error = "failed", "unexpected internal error (see server log)"
        log.exception("refresh crashed")
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
    return run


def _d(s):
    return date.fromisoformat(s) if s else None


def _to_row(n: dict) -> dict:
    return dict(
        source_key=n["source_key"], content_hash=n["content_hash"], generic_name=n["generic_name"],
        company_name=n["company_name"], status=n["status"], availability=n["availability"],
        shortage_reason=n["shortage_reason"], presentation=n["presentation"], dosage_form=n["dosage_form"],
        strength=n["strength"], therapeutic_category=n["therapeutic_category"], related_info=n["related_info"],
        initial_posting_date=_d(n["initial_posting_date"]), update_date=_d(n["update_date"]),
        change_date=_d(n["change_date"]), discontinued_date=_d(n["discontinued_date"]),
        brand_names=n["brand_names"], package_ndc=n["package_ndc"], raw=n["raw"],
        last_seen_at=datetime.now(timezone.utc))
