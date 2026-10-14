import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.ml import job
from app.models import Forecast, Fund, MlReport, Price


@pytest.fixture
def Session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    S = sessionmaker(bind=engine)
    idx = pd.bdate_range("2022-01-03", "2026-10-09")
    rng = np.random.default_rng(1)
    n = len(idx)
    funds = {
        "MM1": ("Para Piyasası", 1, 1.0015 ** np.arange(n)),
        "MM2": ("Para Piyasası", 1, 1.0014 ** np.arange(n)),
        "MM3": ("Para Piyasası", 2, 1.0016 ** np.arange(n)),
        "BR1": ("Borçlanma Araçları", 3, np.cumprod(1 + rng.normal(0.0012, 0.003, n))),
        "HS1": ("Hisse Senedi", 6, np.cumprod(1 + rng.normal(0.001, 0.015, n))),
        "HS2": ("Hisse Senedi", 7, np.cumprod(1 + rng.normal(0.0008, 0.02, n))),
        "DG1": ("Değişken", 5, np.cumprod(1 + rng.normal(0.001, 0.01, n))),
        "KPL": ("Hisse Senedi", 6, np.cumprod(1 + rng.normal(0.001, 0.015, n))),  # SPK kararıyla kapalı
    }
    with S() as db:
        for code, (cat, risk, p) in funds.items():
            db.add(Fund(code=code, name=f"{code} FONU", category=cat, risk_level=risk,
                        status="islem_kapali" if code == "KPL" else "aktif"))
            db.add_all(Price(fund_code=code, date=d.date(), price=float(v)) for d, v in zip(idx, p))
        db.commit()
    return S


def test_job_stores_forecasts_and_report(Session):
    with Session() as db:
        r = job.run(db)
        assert r["report_refreshed"] is True and r["forecasts"] == 7  # kapalı fon hariç
        f = {x.fund_code: x for x in db.scalars(select(Forecast))}
        assert "KPL" not in f
        hs = f["HS1"]
        assert hs.method == "drift" and hs.lo < hs.pred_return < hs.hi and hs.risk_group == "5-7"
        rep = job.latest_report(db).payload
        iv = rep["drift_interval"]["5-7"]
        assert hs.lo == pytest.approx(hs.pred_return + iv["q10"]) and hs.coverage == iv["coverage"]
        assert {"overall", "groups", "verdicts", "monthly", "importance", "exploration"} <= set(rep)
        assert rep["calendar"]["test"][2] == 24
        # rapor 28 günden yeni: ikinci çalıştırma raporu yeniden hesaplamaz, tahminleri yeniler
        r2 = job.run(db)
        assert r2["report_refreshed"] is False and db.scalar(select(func.count()).select_from(MlReport)) == 1
        assert db.scalar(select(func.count()).select_from(Forecast)) == 7


def test_forecast_and_performance_api(Session):
    def override():
        with Session() as s:
            yield s

    app.dependency_overrides[get_db] = override
    try:
        c = TestClient(app)
        assert c.get("/api/ml/performance").status_code == 404  # henüz rapor yok
        with Session() as db:
            job.run(db)
        f = c.get("/api/funds/hs1/forecast").json()
        assert f["code"] == "HS1" and f["method"] == "drift" and f["lo"] < f["pred_return"] < f["hi"]
        assert f["note"].startswith("Bu bir ML tahmini değildir") and f["model_note"].startswith("LightGBM bu risk grubunda")
        assert c.get("/api/funds/KPL/forecast").status_code == 404
        p = c.get("/api/ml/performance").json()
        assert p["report"]["horizon"] == 21 and len(p["report"]["verdicts"]) >= 1
    finally:
        app.dependency_overrides.clear()


def test_job_skips_without_history():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        db.add(Fund(code="AAA", name="AAA", category="Hisse Senedi", risk_level=5))
        db.add(Price(fund_code="AAA", date=pd.Timestamp("2026-10-09").date(), price=1.0))
        db.commit()
        assert job.run(db) == {"skipped": "yeterli geçmiş veri yok"}
