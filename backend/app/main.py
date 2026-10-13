import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import scheduler
from app.config import settings
from app.database import init_db
from app.routers import compare, funds, fx, rankings, recommendations, risk, status

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

init_db()  # İleride Alembic migration'ları ile değiştirilecek


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="Fon Analiz API", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(funds.router, prefix="/api")
app.include_router(compare.router, prefix="/api")
app.include_router(rankings.router, prefix="/api")
app.include_router(risk.router, prefix="/api")
app.include_router(recommendations.router, prefix="/api")
app.include_router(fx.router, prefix="/api")
app.include_router(status.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
