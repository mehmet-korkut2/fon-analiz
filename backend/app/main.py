import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import scheduler
from app.config import settings
from app.database import init_db
from app.deps import csrf_violation
from app.routers import account, auth, compare, funds, fx, inflation, ml, rankings, recommendations, risk, sanal, similarity, status

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
    allow_credentials=True,  # oturum çerezi (frontend Vite proxy'siyle aynı kökenden de çağırır)
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def csrf_guard(request: Request, call_next):
    """Çerezli, durum değiştiren isteklerde X-Requested-With başlığı zorunlu (app/deps.py)."""
    if csrf_violation(request):
        return JSONResponse({"detail": "İstek reddedildi (CSRF koruması)."}, status_code=403)
    return await call_next(request)

app.include_router(funds.router, prefix="/api")
app.include_router(compare.router, prefix="/api")
app.include_router(rankings.router, prefix="/api")
app.include_router(risk.router, prefix="/api")
app.include_router(recommendations.router, prefix="/api")
app.include_router(ml.router, prefix="/api")
app.include_router(fx.router, prefix="/api")
app.include_router(status.router, prefix="/api")
app.include_router(sanal.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(account.router, prefix="/api")
app.include_router(inflation.router, prefix="/api")
app.include_router(similarity.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
