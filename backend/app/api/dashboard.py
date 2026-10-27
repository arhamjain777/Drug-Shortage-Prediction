from collections import Counter
from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.deps import current_user
from backend.app.models import IngestionRun, InventoryItem, ShortageRecord as S, User
from backend.app.services import item_forecast

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(db: Session = Depends(get_db), _: User = Depends(current_user)):
    """Every number is computed from stored rows. Empty database -> zeros / nulls, never fake values."""
    total = db.scalar(select(func.count(S.id))) or 0
    current = db.scalar(select(func.count(S.id)).where(func.lower(S.status) == "current")) or 0
    recent = db.scalar(select(func.count(S.id)).where(S.update_date >= date.today() - timedelta(days=30))) or 0
    by_status = [{"status": s or "unknown", "count": c} for s, c in db.execute(select(S.status, func.count(S.id)).group_by(S.status))]
    years = Counter(d.year for (d,) in db.execute(select(S.initial_posting_date).where(S.initial_posting_date.is_not(None))))
    items = db.scalars(select(InventoryItem)).all()
    st, exposure = Counter(), Counter()
    for it in items:
        f = item_forecast(it)
        st[f.status] += 1
        exposure[it.location.name] += f.usable_stock
    last_ok = db.scalar(select(IngestionRun).where(IngestionRun.status == "success").order_by(IngestionRun.id.desc()))
    last = db.scalar(select(IngestionRun).order_by(IngestionRun.id.desc()))
    return {
        "reported_shortages": {"total_records": total, "current": current, "updated_last_30_days": recent,
                               "by_status": by_status, "postings_by_year": [{"year": y, "count": c} for y, c in sorted(years.items())],
                               "scope_note": "US FDA data via openFDA"},
        "inventory": {"items": len(items), "below_reorder": st["below_reorder"],
                      "coverage_shorter_than_lead_time": st["coverage_shorter_than_lead"], "stocked_out": st["stocked_out"],
                      "no_demand_data": st["no_demand_data"], "status_counts": dict(st),
                      "exposure_by_location": [{"location": k, "usable_stock_units": v} for k, v in exposure.items()],
                      "demo_items": sum(1 for i in items if i.is_demo)},
        "data_freshness": {"last_successful_refresh": last_ok.finished_at if last_ok else None,
                           "last_run_status": last.status if last else None, "last_run_error": last.error if last else None},
    }
