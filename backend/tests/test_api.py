"""API integration tests (UNVERIFIED in the build sandbox: FastAPI/SQLAlchemy were not installable there).
They auto-skip if dependencies are missing. On your machine: pip install -r backend/requirements.txt, then run."""
import importlib.util, os, tempfile, unittest

HAVE = all(importlib.util.find_spec(m) for m in ("fastapi", "sqlalchemy", "httpx"))
if HAVE:
    _tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
    os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.core.security import hash_password
    from backend.app.db.session import Base, SessionLocal, engine
    from backend.app.models import Location, ShortageRecord, User
    from backend.app import services
    from ingestion.fetch_sources import OpenFDAClient


@unittest.skipUnless(HAVE, "fastapi/sqlalchemy/httpx not installed")
class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
        with SessionLocal() as db:
            for email, role in (("a@t.io", "admin"), ("m@t.io", "inventory_manager"), ("v@t.io", "viewer")):
                db.add(User(email=email, password_hash=hash_password("password-123"), role=role))
            db.add(Location(name="L1"))
            db.add(ShortageRecord(source_key="k1", content_hash="h", generic_name="Amoxicillin", status="Current"))
            db.commit()
        cls.c = TestClient(app)

    def hdr(self, email):
        r = self.c.post("/api/v1/auth/login", json={"email": email, "password": "password-123"})
        self.assertEqual(r.status_code, 200)
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_health_and_auth_required(self):
        self.assertEqual(self.c.get("/health").status_code, 200)
        self.assertEqual(self.c.get("/api/v1/shortages").status_code, 401)

    def test_bad_login(self):
        self.assertEqual(self.c.post("/api/v1/auth/login", json={"email": "a@t.io", "password": "wrong"}).status_code, 401)

    def test_search_shortages(self):
        r = self.c.get("/api/v1/shortages?q=amox", headers=self.hdr("v@t.io"))
        self.assertEqual(r.json()["total"], 1)
        self.assertEqual(self.c.get("/api/v1/shortages?sort=bogus", headers=self.hdr("v@t.io")).status_code, 422)

    def test_viewer_cannot_write_manager_can(self):
        body = {"location_id": 1, "drug_name": "Perm Test", "avg_daily_consumption": 5, "lead_time_days": 3}
        self.assertEqual(self.c.post("/api/v1/inventory", json=body, headers=self.hdr("v@t.io")).status_code, 403)
        self.assertEqual(self.c.post("/api/v1/inventory", json=body, headers=self.hdr("m@t.io")).status_code, 201)

    def test_inventory_flow_and_scenario_isolation(self):
        h = self.hdr("m@t.io")
        item = self.c.post("/api/v1/inventory", headers=h, json={"location_id": 1, "drug_name": "Flow Drug",
                           "avg_daily_consumption": 10, "lead_time_days": 5, "safety_stock_days": 2}).json()
        iid = item["id"]
        r = self.c.post(f"/api/v1/inventory/{iid}/movements", headers=h, json={"kind": "receipt", "quantity": 100})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["forecast"]["days_of_supply"], 10)
        self.assertEqual(self.c.post(f"/api/v1/inventory/{iid}/movements", headers=h, json={"kind": "issue", "quantity": 1000}).status_code, 422)
        self.assertEqual(self.c.post(f"/api/v1/inventory/{iid}/movements", headers=h, json={"kind": "adjustment", "quantity": -5}).status_code, 422)  # needs reason
        s = self.c.post("/api/v1/scenarios", headers=h, json={"item_id": iid, "name": "x", "assumptions": {"demand_change_pct": 100}})
        self.assertEqual(s.status_code, 201)
        self.assertEqual(s.json()["result"]["scenario"]["days_of_supply"], 5)
        d = self.c.get(f"/api/v1/inventory/{iid}", headers=h).json()
        self.assertEqual(d["total_stock"], 100)               # scenario did not change real stock
        self.assertEqual(d["forecast"]["days_of_supply"], 10)

    def test_csv_import_validates_then_commits(self):
        h = self.hdr("m@t.io")
        csv_text = ("location,drug_name,quantity,avg_daily_consumption\nL1,Imp A,50,5\nNOPE,Imp B,5,1\nL1,Imp C,-3,1\n")
        pre = self.c.post("/api/v1/inventory/import", headers=h, json={"csv_text": csv_text}).json()
        self.assertEqual((pre["valid_rows"], pre["rejected_rows"], pre["committed"]), (1, 2, False))
        done = self.c.post("/api/v1/inventory/import", headers=h, json={"csv_text": csv_text, "commit": True}).json()
        self.assertEqual(done["inserted"], 1)

    def test_failed_refresh_keeps_data(self):
        with SessionLocal() as db:
            before = db.query(ShortageRecord).count()
            run = services.run_refresh(db, client=OpenFDAClient(transport=lambda u, t: (503, ""), sleep=lambda s: None, max_retries=1))
            self.assertEqual(run.status, "failed")
            self.assertEqual(db.query(ShortageRecord).count(), before)

    def test_export_csv_neutralises_formulas(self):
        with SessionLocal() as db:
            db.add(ShortageRecord(source_key="k2", content_hash="h", generic_name="=cmd()", status="Current")); db.commit()
        r = self.c.get("/api/v1/shortages/export.csv?q=cmd", headers=self.hdr("v@t.io"))
        self.assertIn("'=cmd()", r.text)

if __name__ == "__main__":
    unittest.main()
