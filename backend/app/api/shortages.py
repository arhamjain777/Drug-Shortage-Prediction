from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from backend.app.api.common import like, page_params, paged
from backend.app.db.session import get_db
from backend.app.deps import current_user
from backend.app.domain.csv_safe import to_csv
from backend.app.models import ShortageRecord as S, User

router = APIRouter(prefix="/api/v1/shortages", tags=["reported shortages (FDA, US)"])
SORTS = {"update_date": S.update_date, "initial_posting_date": S.initial_posting_date,
         "generic_name": S.generic_name, "status": S.status}
SOURCE_NOTE = "Source: US FDA via openFDA. Reported shortage records; not a shortage feed for India."


def _query(q, status, dosage_form, company):
    stmt = select(S)
    if q:
        stmt = stmt.where(or_(S.generic_name.ilike(like(q), escape="\\"), S.company_name.ilike(like(q), escape="\\"),
                              S.presentation.ilike(like(q), escape="\\")))
    if status:
        stmt = stmt.where(S.status == status)
    if dosage_form:
        stmt = stmt.where(S.dosage_form == dosage_form)
    if company:
        stmt = stmt.where(S.company_name.ilike(like(company), escape="\\"))
    return stmt


def _row(r: S, full=False):
    d = {"id": r.id, "generic_name": r.generic_name, "company_name": r.company_name, "status": r.status,
         "availability": r.availability, "dosage_form": r.dosage_form, "presentation": r.presentation,
         "strength": r.strength, "initial_posting_date": r.initial_posting_date, "update_date": r.update_date,
         "source": "openFDA drug shortages", "last_seen_at": r.last_seen_at}
    if full:
        d.update(shortage_reason=r.shortage_reason, related_info=r.related_info, brand_names=r.brand_names,
                 therapeutic_category=r.therapeutic_category, package_ndc=r.package_ndc, change_date=r.change_date,
                 discontinued_date=r.discontinued_date, source_key=r.source_key, raw=r.raw, note=SOURCE_NOTE)
    return d


@router.get("")
def list_shortages(q: str | None = None, status: str | None = None, dosage_form: str | None = None,
                   company: str | None = None, sort: str = "update_date", order: str = Query("desc", pattern="^(asc|desc)$"),
                   pg=Depends(page_params), db: Session = Depends(get_db), _: User = Depends(current_user)):
    page, size = pg
    if sort not in SORTS:
        raise HTTPException(422, f"sort must be one of {sorted(SORTS)}")
    base = _query(q, status, dosage_form, company)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    col = SORTS[sort]
    rows = db.scalars(base.order_by(col.desc().nulls_last() if order == "desc" else col.asc().nulls_last(), S.id)
                      .offset((page - 1) * size).limit(size)).all()
    out = paged([_row(r) for r in rows], total, page, size)
    out["note"] = SOURCE_NOTE
    return out


@router.get("/facets")
def facets(db: Session = Depends(get_db), _: User = Depends(current_user)):
    def distinct(col):
        return [v for (v,) in db.execute(select(col).where(col.is_not(None)).group_by(col).order_by(col)).all()]
    return {"statuses": distinct(S.status), "dosage_forms": distinct(S.dosage_form)}


@router.get("/export.csv")
def export_csv(q: str | None = None, status: str | None = None, dosage_form: str | None = None,
               company: str | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = db.scalars(_query(q, status, dosage_form, company).order_by(S.id).limit(50000)).all()
    cols = ["id", "generic_name", "company_name", "status", "availability", "dosage_form", "presentation",
            "initial_posting_date", "update_date", "source"]
    data = to_csv([_row(r) for r in rows], cols)
    return Response(data, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=reported_shortages.csv"})


@router.get("/{rid}")
def get_shortage(rid: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    r = db.get(S, rid)
    if not r:
        raise HTTPException(404, "Shortage record not found")
    return _row(r, full=True)
