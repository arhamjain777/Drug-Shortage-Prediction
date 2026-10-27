"""Train + evaluate on the stored FDA history. Run: python -m scripts.train_model"""
import json
from sqlalchemy import select
from backend.app import models  # noqa
from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.models import ShortageRecord
from ml.feature_engineering import events_frame
from ml.train import train_and_evaluate

if __name__ == "__main__":
    with SessionLocal() as db:
        recs = [{"generic_name": r.generic_name, "initial_posting_date": r.initial_posting_date.isoformat(),
                 "company_name": r.company_name, "dosage_form": r.dosage_form}
                for r in db.scalars(select(ShortageRecord).where(ShortageRecord.initial_posting_date.is_not(None)))]
    print(f"{len(recs)} records with a posting date")
    print(json.dumps(train_and_evaluate(events_frame(recs), settings.model_dir), indent=2))
