from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import funds, fx

Base.metadata.create_all(bind=engine)  # İleride Alembic migration'ları ile değiştirilecek

app = FastAPI(title="Fon Analiz API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(funds.router, prefix="/api")
app.include_router(fx.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
