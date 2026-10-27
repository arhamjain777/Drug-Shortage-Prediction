# MediWatch Intelligence
*Anticipate disruption. Protect availability.*

Drug-shortage intelligence + pharmacy inventory forecasting. B.Tech project. Decision-support prototype, **not clinically certified**.

Three concepts are always kept separate (and labelled in the UI):
1. **Reported shortage** - official FDA record (US only, via openFDA; NOT an India feed)
2. **Local stock-out estimate** - arithmetic on *your* recorded stock and assumptions
3. **Model risk score** - experimental ML recurrence score, uncalibrated, shown only if a model exists

> **Honest status:** the core maths, ingestion logic and ML pipeline are unit-tested. The FastAPI backend, React frontend and Docker setup
> were written in an offline sandbox and have **not been run yet**. Expect to fix small issues on first run. See `docs/PROGRESS.md`.

## Run it - Option A: Docker (easiest)
    cp .env.example .env          # then edit: set POSTGRES_PASSWORD and SECRET_KEY
    docker compose up --build
    docker compose exec backend python -m scripts.seed_demo_data      # prints demo passwords once
    docker compose exec backend python -m scripts.refresh_shortages   # real FDA data (needs internet)
Open the app at http://localhost:8080 , API docs at http://localhost:8000/docs

## Run it - Option B: without Docker (SQLite, good for development)
    python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
    pip install -r backend/requirements.txt
    export SECRET_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(48))")   # Windows PowerShell: $env:SECRET_KEY="..."
    python -m scripts.seed_demo_data                       # creates mediwatch.db + demo users (passwords printed once)
    python -m scripts.refresh_shortages                    # optional, needs internet
    uvicorn backend.app.main:app --reload                  # API on :8000
    # second terminal:
    cd frontend && npm install && npm run dev              # app on http://localhost:5173
Without `DATABASE_URL`, the backend uses a local SQLite file. Set `DATABASE_URL=postgresql+psycopg://user:pass@host/db` for PostgreSQL.

## Train the experimental model (after refreshing FDA data)
    python -m scripts.train_model
It reports its own status (`unavailable` / `experimental` / `passed_retrospective_checks`). Check Data & model page. Never treat it as clinically reliable.

## Tests
    python -m unittest discover -s . -t . -v        # 37 always run; 8 API tests run once dependencies are installed
    cd frontend && npm run build                      # type-check + production build

## Demo roles (created by the seed script)
admin@mediwatch.local (all) · manager@mediwatch.local (inventory) · viewer@mediwatch.local (read-only)

## Layout
    backend/app/{api,core,db,domain}   FastAPI routers, config/security, DB session, PURE tested logic (forecast, ledger, csv_safe)
    ingestion/                          openFDA client + normalisation
    ml/                                 features, panel/split, train, inference
    scripts/                            seed, refresh, train
    frontend/                           React + TS + Tailwind + TanStack Query + Motion
    docs/                               progress, data sources, ML method, viva guide

## Known limitations
See `docs/PROGRESS.md` ("Not built"), `docs/data_sources.md`, `docs/ml_methodology.md`.
Security notes: token stored in localStorage (XSS trade-off); login rate-limit is in-memory; use HTTPS and a strong SECRET_KEY in production.
