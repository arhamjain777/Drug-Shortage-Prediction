"""Create the first admin + DEMO inventory (all marked is_demo). Run: python -m scripts.seed_demo_data
Passwords come from env vars, or are generated and printed once. Nothing secret is stored in code."""
import os, secrets
from datetime import date, timedelta
from sqlalchemy import select
from backend.app import models  # noqa
from backend.app.core.security import hash_password
from backend.app.db.session import Base, SessionLocal, engine
from backend.app.models import Location, User
from backend.app.services import apply_stock_movement
from backend.app.models import InventoryItem, Order

DEMO = [  # (drug, unit, daily, lead, safety, qty, expiry offset days or None)
    ("DEMO Amoxicillin 500 mg capsule", "capsules", 40, 7, 3, 180, 200),
    ("DEMO Ceftriaxone 1 g injection", "vials", 12, 10, 4, 60, 120),
    ("DEMO Paracetamol 500 mg tablet", "tablets", 300, 5, 2, 9000, None),
    ("DEMO Insulin glargine pen", "pens", 6, 14, 5, 40, 90),
]


def user(db, email, role, env):
    pw = os.getenv(env) or secrets.token_urlsafe(12)
    if not db.scalar(select(User).where(User.email == email)):
        db.add(User(email=email, full_name=role.replace("_", " ").title(), password_hash=hash_password(pw), role=role))
        print(f"created {email} ({role}) password: {pw if not os.getenv(env) else '[from ' + env + ']'}")


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        user(db, "admin@mediwatch.local", "admin", "SEED_ADMIN_PASSWORD")
        user(db, "manager@mediwatch.local", "inventory_manager", "SEED_MANAGER_PASSWORD")
        user(db, "viewer@mediwatch.local", "viewer", "SEED_VIEWER_PASSWORD")
        db.commit()
        admin = db.scalar(select(User).where(User.email == "admin@mediwatch.local"))
        loc = db.scalar(select(Location).where(Location.name == "DEMO Main Pharmacy"))
        if not loc:
            loc = Location(name="DEMO Main Pharmacy", is_demo=True); db.add(loc); db.commit()
        for name, unit, daily, lead, safety, qty, exp in DEMO:
            if db.scalar(select(InventoryItem).where(InventoryItem.location_id == loc.id, InventoryItem.drug_name == name)):
                continue
            it = InventoryItem(location_id=loc.id, drug_name=name, unit=unit, avg_daily_consumption=daily,
                               lead_time_days=lead, safety_stock_days=safety, is_demo=True)
            db.add(it); db.flush()
            apply_stock_movement(db, it, "receipt", qty, admin, "DEMO seed", date.today() + timedelta(days=exp) if exp else None)
            if name.startswith("DEMO Ceftriaxone"):
                db.add(Order(item_id=it.id, quantity=100, expected_date=date.today() + timedelta(days=6), confirmed=True))
        db.commit()
    print("demo data ready (all inventory rows are SIMULATED).")


if __name__ == "__main__":
    main()
