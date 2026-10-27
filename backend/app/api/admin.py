import logging
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.core.security import hash_password
from backend.app.db.session import get_db
from backend.app.deps import audit, current_user, require_roles
from backend.app.models import AuditLog, IngestionRun, ShortageRecord, User
from backend.app.services import run_refresh

router = APIRouter(prefix="/api/v1", tags=["admin & model"])
log = logging.getLogger("mediwatch.admin")


class UserIn(BaseModel):
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    full_name: str = Field(default="", max_length=120)
    password: str = Field(min_length=10, max_length=200)
    role: Literal["admin", "analyst", "inventory_manager", "viewer"] = "viewer"


def _run(r: IngestionRun):
    return {"id": r.id, "status": r.status, "started_at": r.started_at, "finished_at": r.finished_at, "fetched": r.fetched,
            "inserted": r.inserted, "updated": r.updated, "unchanged": r.unchanged, "duplicates": r.duplicates,
            "rejected": r.rejected, "error": r.error}


@router.post("/admin/refresh")
def refresh(db: Session = Depends(get_db), user: User = Depends(require_roles("analyst"))):
    audit(db, user, "source.refresh"); db.commit()
    return _run(run_refresh(db, user))


@router.get("/admin/ingestion-runs")
def runs(db: Session = Depends(get_db), _: User = Depends(require_roles("analyst"))):
    return [_run(r) for r in db.scalars(select(IngestionRun).order_by(IngestionRun.id.desc()).limit(50))]


@router.get("/admin/users")
def users(db: Session = Depends(get_db), _: User = Depends(require_roles())):
    return [{"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role, "is_active": u.is_active} for u in db.scalars(select(User))]


@router.post("/admin/users", status_code=201)
def create_user(body: UserIn, db: Session = Depends(get_db), admin: User = Depends(require_roles())):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "Email already registered")
    u = User(email=body.email.lower(), full_name=body.full_name, password_hash=hash_password(body.password), role=body.role)
    db.add(u); audit(db, admin, "user.create", f"{u.email} as {u.role}"); db.commit()
    return {"id": u.id, "email": u.email, "role": u.role}


@router.get("/admin/audit")
def audit_log(db: Session = Depends(get_db), _: User = Depends(require_roles())):
    return [{"at": a.at, "user_id": a.user_id, "action": a.action, "detail": a.detail}
            for a in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(200))]


# ---- shortage-risk model (experimental) ----
@router.get("/model/status")
def model_status(_: User = Depends(current_user)):
    from ml.inference import load_bundle
    b = load_bundle(settings.model_dir)
    if not b["available"]:
        return {"available": False, "reason": b["reason"],
                "how_to_train": "Refresh FDA data, then run: python -m scripts.train_model"}
    m = b["meta"]
    return {"available": True, "version": m["version"], "status": m["status"], "horizon_days": m["horizon_days"],
            "periods": m["periods"], "class_balance": m["class_balance"], "test_metrics": m["test_metrics"],
            "gates": m["gates"], "disclaimer": m["disclaimer"]}


@router.get("/predictions")
def predictions(limit: int = 50, db: Session = Depends(get_db), _: User = Depends(require_roles("analyst", "inventory_manager", "viewer"))):
    """Model-generated recurrence-risk SCORES (uncalibrated). Not a reported shortage, not a stock forecast."""
    from datetime import date
    from ml.feature_engineering import compute_features, events_frame
    from ml.inference import load_bundle, predict
    b = load_bundle(settings.model_dir)
    if not b["available"]:
        return {"available": False, "reason": b["reason"], "predictions": []}
    recs = [{"generic_name": r.generic_name, "initial_posting_date": r.initial_posting_date.isoformat(),
             "company_name": r.company_name, "dosage_form": r.dosage_form}
            for r in db.scalars(select(ShortageRecord).where(ShortageRecord.initial_posting_date.is_not(None)))]
    feats = compute_features(events_frame(recs), date.today())
    out = predict(b, feats, date.today().isoformat())
    out["predictions"] = sorted(out["predictions"], key=lambda r: -r["score"])[:max(1, min(limit, 500))]
    return out
