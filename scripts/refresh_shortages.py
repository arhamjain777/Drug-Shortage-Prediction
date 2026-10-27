"""Fetch official FDA shortage records. Run: python -m scripts.refresh_shortages"""
from backend.app import models  # noqa
from backend.app.db.session import Base, SessionLocal, engine
from backend.app.services import run_refresh

if __name__ == "__main__":
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        r = run_refresh(db)
        print(f"status={r.status} fetched={r.fetched} inserted={r.inserted} updated={r.updated} "
              f"unchanged={r.unchanged} duplicates={r.duplicates} rejected={r.rejected} error={r.error}")
