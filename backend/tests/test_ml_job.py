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
from app.ml import horizons as H
from app.models import SOURCE_BACKFILL, SOURCE_LIVE, ForecastDay, ForecastSummary, Fund, MlReport, Price


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
        assert r["report_refreshed"] is True and r["forecasts"] == 7 * 21  # kapalı fon hariç, 21 ufuk
        assert r["backfill_days"] == H.BACKFILL_DAYS and r["backfill"] == 7 * 21 * H.BACKFILL_DAYS
        last = max(db.scalars(select(Price.date)))
        live = list(db.scalars(select(ForecastDay).where(ForecastDay.source == SOURCE_LIVE)))
        assert {x.as_of for x in live} == {last} and "KPL" not in {x.fund_code for x in live}
        hs = {x.horizon: x for x in live if x.fund_code == "HS1"}
        assert sorted(hs) == list(range(1, 22)) and all(x.method == "drift-konformal" and x.method_version == "v1" and x.risk_group == "5-7" for x in hs.values())
        assert all(x.lo_price < x.pred_price < x.hi_price for x in hs.values())
        # 21 günlük kayıt tahmin kartıyla aynı
        f = H.latest_forecasts(db, ["HS1"])["HS1"]
        assert f.pred_return == pytest.approx(hs[21].pred_price / hs[21].base_price - 1) and len(f.path) == 21
        rep = job.latest_report(db).payload
        assert {"overall", "groups", "verdicts", "monthly", "importance", "exploration", "horizons"} <= set(rep)
        assert rep["calendar"]["test"][2] == 24
        assert {x["horizon"] for x in rep["horizons"]["rows"]} == set(range(1, 22))
        summ = db.scalars(select(ForecastSummary)).one().payload
        assert summ["counts"][SOURCE_BACKFILL]["days"] == H.BACKFILL_DAYS and summ["counts"][SOURCE_LIVE]["realized"] == 0
        # rapor 28 günden yeni: ikinci çalıştırma raporu yeniden hesaplamaz; kayıtlar silinmez, çoğaltılmaz
        n = db.scalar(select(func.count()).select_from(ForecastDay))
        r2 = job.run(db)
        assert r2["report_refreshed"] is False and db.scalar(select(func.count()).select_from(MlReport)) == 1
        assert r2["forecasts"] == 0 and r2["backfill"] == 0
        assert db.scalar(select(func.count()).select_from(ForecastDay)) == n
        assert db.scalar(select(func.count()).select_from(ForecastSummary)) == 1


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
        assert f["code"] == "HS1" and f["method"] == "drift-konformal" and f["method_version"] == "v1" and f["lo"] < f["pred_return"] < f["hi"]
        assert f["note"].startswith("Bu bir ML tahmini değildir") and f["model_note"].startswith("LightGBM bu risk grubunda")
        assert c.get("/api/funds/KPL/forecast").status_code == 404
        assert f["source"] == "canli" and len(f["path"]) == 21 and f["coverage"] is not None
        assert f["path"][0]["hi"] - f["path"][0]["lo"] < f["path"][-1]["hi"] - f["path"][-1]["lo"]
        p = c.get("/api/ml/performance").json()
        assert p["report"]["horizon"] == 21 and len(p["report"]["verdicts"]) >= 1
        assert p["scorecard"]["counts"]["geriye_donuk"]["days"] == H.BACKFILL_DAYS
        # karne: varsayılan seçim, bütün günleri gerçekleşmiş en yeni tahmin (canlı gün henüz bekleniyor)
        k = c.get("/api/funds/hs1/forecast-scorecard").json()
        assert len(k["days"]) == 30 and k["days"][0]["source"] == "canli" and k["days"][0]["realized"] == 0
        sel = k["selected"]
        full = next(d for d in k["days"] if d["realized"] == 21)
        assert sel["source"] == "geriye_donuk" and sel["as_of"] == full["as_of"] and len(sel["rows"]) == 21
        assert all(r["realized_price"] is not None for r in sel["rows"])
        part = c.get(f"/api/funds/hs1/forecast-scorecard?as_of={k['days'][1]['as_of']}").json()["selected"]
        assert part["rows"][0]["realized_price"] is not None and part["rows"][-1]["realized_price"] is None
        assert k["backfill_note"].startswith("Geriye dönük hesaplanmıştır")
        assert {x["horizon"] for x in k["summary"]} == {1, 2, 5, 10, 21}
        live = c.get(f"/api/funds/hs1/forecast-scorecard?as_of={k['days'][0]['as_of']}").json()["selected"]
        assert live["source"] == "canli" and all(r["realized_price"] is None and r["in_band"] is None for r in live["rows"])
        assert c.get("/api/funds/hs1/forecast-scorecard?as_of=2020-01-01").status_code == 404
        assert c.get("/api/funds/KPL/forecast-scorecard").status_code == 404
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
