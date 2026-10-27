from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.deps import audit, current_user, require_roles
from backend.app.domain.forecast import ScenarioAssumptions, compare_scenario
from backend.app.models import InventoryItem, Scenario, User
from backend.app.services import item_forecast_input

router = APIRouter(prefix="/api/v1/scenarios", tags=["scenarios (hypothetical)"])
WRITE = require_roles("inventory_manager", "analyst")


class AssumptionsIn(BaseModel):
    demand_change_pct: float = Field(default=0, gt=-100, le=1000)
    stock_change_pct: float = Field(default=0, ge=-100, le=1000)
    lead_time_delay_days: float = Field(default=0, ge=0, le=365)
    safety_stock_days_override: Optional[float] = Field(default=None, ge=0, le=365)
    delay_confirmed_orders_days: int = Field(default=0, ge=0, le=365)
    cancel_confirmed_orders: bool = False
    extra_replenishment_qty: float = Field(default=0, ge=0)
    extra_replenishment_in_days: int = Field(default=0, ge=0, le=365)


class ScenarioIn(BaseModel):
    item_id: int
    name: str = Field(min_length=1, max_length=200)
    assumptions: AssumptionsIn = AssumptionsIn()


class Rename(BaseModel):
    name: str = Field(min_length=1, max_length=200)


def _out(s: Scenario):
    return {"id": s.id, "name": s.name, "item_id": s.item_id, "assumptions": s.assumptions, "result": s.result,
            "created_at": s.created_at, "hypothetical": True,
            "label": "HYPOTHETICAL scenario - not an operational record"}


def _compute(db, item_id, assumptions: dict):
    item = db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(404, "Inventory item not found")
    return compare_scenario(item_forecast_input(item), ScenarioAssumptions(**assumptions))


@router.post("/preview")
def preview(body: ScenarioIn, db: Session = Depends(get_db), _: User = Depends(current_user)):
    """Compute without saving."""
    return _compute(db, body.item_id, body.assumptions.model_dump())


@router.post("", status_code=201)
def save(body: ScenarioIn, db: Session = Depends(get_db), user: User = Depends(WRITE)):
    a = body.assumptions.model_dump()
    s = Scenario(name=body.name, item_id=body.item_id, assumptions=a, result=_json(_compute(db, body.item_id, a)), created_by=user.id)
    db.add(s); audit(db, user, "scenario.create", body.name); db.commit()
    return _out(s)


def _json(d):  # dates -> iso strings already handled by to_dict(); make sure it is JSON-safe
    import json
    return json.loads(json.dumps(d, default=str))


@router.get("")
def list_all(item_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    stmt = select(Scenario).order_by(Scenario.created_at.desc())
    if item_id:
        stmt = stmt.where(Scenario.item_id == item_id)
    return [_out(s) for s in db.scalars(stmt)]


def _get(db, sid):
    s = db.get(Scenario, sid)
    if not s:
        raise HTTPException(404, "Scenario not found")
    return s


@router.get("/{sid}")
def get_one(sid: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return _out(_get(db, sid))


@router.patch("/{sid}")
def rename(sid: int, body: Rename, db: Session = Depends(get_db), user: User = Depends(WRITE)):
    s = _get(db, sid); s.name = body.name; audit(db, user, "scenario.rename", str(sid)); db.commit()
    return _out(s)


@router.post("/{sid}/duplicate", status_code=201)
def duplicate(sid: int, db: Session = Depends(get_db), user: User = Depends(WRITE)):
    o = _get(db, sid)
    c = Scenario(name=f"{o.name} (copy)"[:200], item_id=o.item_id, assumptions=o.assumptions,
                 result=_json(_compute(db, o.item_id, o.assumptions)), created_by=user.id)
    db.add(c); audit(db, user, "scenario.duplicate", str(sid)); db.commit()
    return _out(c)


@router.delete("/{sid}", status_code=204)
def delete(sid: int, db: Session = Depends(get_db), user: User = Depends(WRITE)):
    s = _get(db, sid); db.delete(s); audit(db, user, "scenario.delete", str(sid)); db.commit()
