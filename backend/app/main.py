import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.api import admin, auth, dashboard, inventory, scenarios, shortages
from backend.app.core.config import settings
from backend.app.db.session import Base, engine
from backend.app import models  # noqa: F401  (registers tables)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("mediwatch")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience. For production use Alembic migrations (see docs/PROGRESS.md - not yet written).
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="MediWatch Intelligence API", version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
for r in (auth, shortages, inventory, scenarios, dashboard, admin):
    app.include_router(r.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)    # details go to the log, never to the client
    return JSONResponse({"detail": "Internal server error"}, status_code=500)
