# MediWatch Intelligence - Progress Checklist
Legend: [x] built AND executed/tested in the build sandbox | [~] written, NOT executed (needs your machine) | [ ] not built

The sandbox had NO network, no Docker, no PostgreSQL. Only Python 3.12 + pandas + scikit-learn + Node were usable.

## [x] Executed and tested (45 tests run, 37 pass, 8 API tests skip because FastAPI is missing there)
Forecast engine, scenario engine, stock ledger rules, CSV injection guard, openFDA normaliser / idempotent
upsert planner / retrying client (fake transport), ML pipeline (leak-safe features, purged chronological split,
models, status gates, safe inference). Python syntax of everything compiles. Frontend files parse (syntax only).

## [~] Written, never run - expect small fixes on first run
- FastAPI app: auth (PBKDF2 + HS256 token, login lockout), roles (admin/analyst/inventory_manager/viewer) enforced server-side,
  shortages search/filter/sort/paginate/export, inventory CRUD + movements (FEFO) + orders + CSV import wizard + export,
  scenarios (preview/save/rename/duplicate/delete), dashboard (DB-derived), FDA refresh + run history, users, audit log,
  model status + predictions (experimental)
- SQLAlchemy models (tables created by create_all at startup)
- API integration tests (backend/tests/test_api.py)
- React frontend: login, dashboard, shortage explorer + detail drawer, inventory (+ detail, movements, orders, scenario save, CSV import),
  scenarios, data & model; dark mode, reduced-motion, page/nav animation, URL filters, skeletons, error/empty states
- Dockerfiles, docker-compose.yml, CI workflow
- Live openFDA calls (field names partly unverified - see docs/data_sources.md)

## [ ] Not built
Alembic migrations (uses create_all), suppliers & delivery history, purchase-order UI beyond simple add, alerts/rules/notifications,
watchlists, risk cases, alternative-supply explorer, PDF reports, historical time machine UI, Ask MediWatch, anomaly detection,
saved views, command palette, organisation multi-tenancy, frontend tests, email notifications.
