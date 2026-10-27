import csv, io
from datetime import date
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.api.common import like, page_params, paged
from backend.app.db.session import get_db
from backend.app.deps import audit, current_user, require_roles
from backend.app.domain.csv_safe import to_csv
from backend.app.domain.ledger import InsufficientStock
from backend.app.models import Batch, InventoryItem, Location, Movement, Order, User
from backend.app.services import apply_stock_movement, item_forecast, stock_total

router = APIRouter(prefix="/api/v1/inventory", tags=["local inventory (your own data)"])
WRITE = require_roles("inventory_manager")
NOTE = "Local stock-out ESTIMATE from your recorded stock and assumptions; not a shortage prediction."


class LocationIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ItemIn(BaseModel):
    location_id: int
    drug_name: str = Field(min_length=1, max_length=300)
    unit: str = Field(default="units", max_length=30)
    avg_daily_consumption: float = Field(default=0, ge=0)
    lead_time_days: float = Field(default=0, ge=0)
    safety_stock_days: float = Field(default=0, ge=0)


class ItemPatch(BaseModel):
    unit: Optional[str] = Field(default=None, max_length=30)
    avg_daily_consumption: Optional[float] = Field(default=None, ge=0)
    lead_time_days: Optional[float] = Field(default=None, ge=0)
    safety_stock_days: Optional[float] = Field(default=None, ge=0)


class MovementIn(BaseModel):
    kind: Literal["receipt", "issue", "adjustment", "transfer_in", "transfer_out"]
    quantity: float
    reason: str = Field(default="", max_length=300)
    expiry: Optional[date] = None
    lot: Optional[str] = Field(default=None, max_length=80)


class OrderIn(BaseModel):
    quantity: float = Field(gt=0)
    expected_date: date
    confirmed: bool = False


def summary(item: InventoryItem) -> dict:
    f = item_forecast(item)
    return {"id": item.id, "drug_name": item.drug_name, "location_id": item.location_id,
            "location": item.location.name, "unit": item.unit, "is_demo": item.is_demo,
            "avg_daily_consumption": item.avg_daily_consumption, "lead_time_days": item.lead_time_days,
            "safety_stock_days": item.safety_stock_days, "total_stock": stock_total(item),
            "forecast": f.to_dict(), "forecast_note": NOTE,
            "label": "DEMO / simulated record" if item.is_demo else "user-entered record"}


@router.get("/locations")
def locations(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [{"id": l.id, "name": l.name, "is_demo": l.is_demo} for l in db.scalars(select(Location).order_by(Location.name))]


@router.post("/locations", status_code=201)
def add_location(body: LocationIn, db: Session = Depends(get_db), user: User = Depends(WRITE)):
    if db.scalar(select(Location).where(Location.name == body.name.strip())):
        raise HTTPException(409, "Location already exists")
    loc = Location(name=body.name.strip()); db.add(loc); audit(db, user, "location.create", loc.name); db.commit()
    return {"id": loc.id, "name": loc.name}


@router.get("")
def list_items(q: str | None = None, location_id: int | None = None, status: str | None = None,
               pg=Depends(page_params), db: Session = Depends(get_db), _: User = Depends(current_user)):
    page, size = pg
    stmt = select(InventoryItem)
    if q:
        stmt = stmt.where(InventoryItem.drug_name.ilike(like(q), escape="\\"))
    if location_id:
        stmt = stmt.where(InventoryItem.location_id == location_id)
    rows = [summary(i) for i in db.scalars(stmt.order_by(InventoryItem.drug_name)).all()]
    if status:
        rows = [r for r in rows if r["forecast"]["status"] == status]
    total = len(rows)
    return paged(rows[(page - 1) * size: page * size], total, page, size)


@router.post("", status_code=201)
def create_item(body: ItemIn, db: Session = Depends(get_db), user: User = Depends(WRITE)):
    if not db.get(Location, body.location_id):
        raise HTTPException(422, "Unknown location_id")
    if db.scalar(select(InventoryItem).where(InventoryItem.location_id == body.location_id,
                                             InventoryItem.drug_name == body.drug_name.strip())):
        raise HTTPException(409, "This drug already exists at this location")
    item = InventoryItem(**{**body.model_dump(), "drug_name": body.drug_name.strip()})
    db.add(item); db.flush(); audit(db, user, "inventory.create", f"{item.drug_name}@{item.location_id}"); db.commit()
    db.refresh(item)
    return summary(item)


@router.get("/template.csv")
def template():
    return Response("location,drug_name,unit,avg_daily_consumption,lead_time_days,safety_stock_days,quantity,expiry,lot\n"
                    "Main Pharmacy,Example Drug 500 mg tablet,tablets,20,7,3,500,2027-06-30,LOT123\n",
                    media_type="text/csv", headers={"Content-Disposition": "attachment; filename=inventory_template.csv"})


@router.get("/export.csv")
def export(location_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    stmt = select(InventoryItem)
    if location_id:
        stmt = stmt.where(InventoryItem.location_id == location_id)
    rows = []
    for i in db.scalars(stmt.order_by(InventoryItem.id)):
        s = summary(i); f = s["forecast"]
        rows.append({"location": s["location"], "drug_name": s["drug_name"], "unit": s["unit"], "total_stock": s["total_stock"],
                     "usable_stock": f["usable_stock"], "avg_daily_consumption": s["avg_daily_consumption"],
                     "days_of_supply": f["days_of_supply"], "reorder_point": f["reorder_point"],
                     "estimated_stockout_date": f["estimated_stockout_date"], "status": f["status"], "label": s["label"]})
    cols = list(rows[0].keys()) if rows else ["location", "drug_name"]
    return Response(to_csv(rows, cols), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=inventory_export.csv"})


class ImportIn(BaseModel):
    csv_text: str = Field(max_length=2_000_000)
    commit: bool = False


@router.post("/import")
def import_csv(body: ImportIn, db: Session = Depends(get_db), user: User = Depends(WRITE)):
    """Two-step import: commit=false validates and previews; commit=true saves accepted rows in ONE transaction."""
    reader = csv.DictReader(io.StringIO(body.csv_text))
    need = {"location", "drug_name", "quantity"}
    if not reader.fieldnames or not need <= set(reader.fieldnames):
        raise HTTPException(422, f"CSV must contain columns: {sorted(need)}")
    locs = {l.name: l for l in db.scalars(select(Location))}
    seen, good, errors = set(), [], []
    for n, r in enumerate(reader, start=2):
        if n > 5001:
            errors.append({"row": n, "error": "row limit (5000) exceeded"}); break
        try:
            name, loc = (r.get("drug_name") or "").strip(), (r.get("location") or "").strip()
            if not name:
                raise ValueError("drug_name is required")
            if loc not in locs:
                raise ValueError(f"unknown location '{loc}' (create it first)")
            num = lambda k, d="0": float((r.get(k) or d).strip())
            row = dict(loc=locs[loc], name=name, unit=(r.get("unit") or "units").strip(), daily=num("avg_daily_consumption"),
                       lead=num("lead_time_days"), safety=num("safety_stock_days"), qty=num("quantity"),
                       expiry=date.fromisoformat(r["expiry"].strip()) if (r.get("expiry") or "").strip() else None,
                       lot=(r.get("lot") or "").strip() or None)
            if min(row["daily"], row["lead"], row["safety"], row["qty"]) < 0:
                raise ValueError("numbers must be >= 0")
            if (loc, name) in seen:
                raise ValueError("duplicate row within file")
            if db.scalar(select(InventoryItem.id).where(InventoryItem.location_id == row["loc"].id, InventoryItem.drug_name == name)):
                raise ValueError("already exists (skipped)")
            seen.add((loc, name)); good.append(row)
        except ValueError as e:
            errors.append({"row": n, "error": str(e)})
    result = {"valid_rows": len(good), "rejected_rows": len(errors), "errors": errors[:200],
              "preview": [{"location": g["loc"].name, "drug_name": g["name"], "quantity": g["qty"]} for g in good[:10]],
              "committed": False, "inserted": 0}
    if body.commit and good:
        for g in good:
            item = InventoryItem(location_id=g["loc"].id, drug_name=g["name"], unit=g["unit"], avg_daily_consumption=g["daily"],
                                 lead_time_days=g["lead"], safety_stock_days=g["safety"])
            db.add(item); db.flush()
            if g["qty"] > 0:
                apply_stock_movement(db, item, "receipt", g["qty"], user, "CSV import", g["expiry"], g["lot"])
        audit(db, user, "inventory.import", f"{len(good)} rows"); db.commit()
        result.update(committed=True, inserted=len(good))
    return result


def _get(db, item_id) -> InventoryItem:
    item = db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(404, "Inventory item not found")
    return item


@router.get("/{item_id}")
def detail(item_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    item = _get(db, item_id)
    d = summary(item)
    d["batches"] = [{"id": b.id, "quantity": b.quantity, "expiry": b.expiry, "lot": b.lot} for b in item.batches]
    d["orders"] = [{"id": o.id, "quantity": o.quantity, "expected_date": o.expected_date, "confirmed": o.confirmed, "received": o.received} for o in item.orders]
    d["movements"] = [{"id": m.id, "kind": m.kind, "quantity": m.quantity, "balance_after": m.balance_after,
                       "reason": m.reason, "user_id": m.user_id, "at": m.at} for m in reversed(item.movements[-100:])]
    return d


@router.patch("/{item_id}")
def patch(item_id: int, body: ItemPatch, db: Session = Depends(get_db), user: User = Depends(WRITE)):
    item = _get(db, item_id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(item, k, v)
    audit(db, user, "inventory.update", f"item {item_id}"); db.commit()
    return summary(item)


@router.post("/{item_id}/movements", status_code=201)
def movement(item_id: int, body: MovementIn, db: Session = Depends(get_db), user: User = Depends(WRITE)):
    item = _get(db, item_id)
    try:
        m = apply_stock_movement(db, item, body.kind, body.quantity, user, body.reason, body.expiry, body.lot)
        audit(db, user, f"stock.{body.kind}", f"item {item_id} qty {body.quantity}")
        db.commit()
    except (InsufficientStock, ValueError) as e:
        db.rollback()
        raise HTTPException(422, str(e))
    return {"movement_id": m.id, "balance_after": m.balance_after, "forecast": item_forecast(_get(db, item_id)).to_dict()}


@router.post("/{item_id}/orders", status_code=201)
def add_order(item_id: int, body: OrderIn, db: Session = Depends(get_db), user: User = Depends(WRITE)):
    item = _get(db, item_id)
    db.add(Order(item_id=item.id, **body.model_dump())); audit(db, user, "order.create", f"item {item_id}"); db.commit()
    return {"forecast": item_forecast(_get(db, item_id)).to_dict()}
