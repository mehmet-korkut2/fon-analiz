"""Favoriler: karne özeti (son 1 günlük tahminlerin aralıkta kalması), sanal portföy pozisyonu, kapatılmış ve
eski verili fon uyarısı, sıralama, kullanıcıya özel olma."""
from datetime import date, datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.ml import horizons as H
from app.models import SOURCE_BACKFILL, SOURCE_LIVE, ForecastDay, Fund, Price, SanalAyar, SanalEmir, User
from app.services import metrics_job
from app.services.fund_status import STATUS_CLOSED

DAYS = pd.bdate_range("2026-09-01", "2026-10-09")


@pytest.fixture
def Session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    S_ = sessionmaker(bind=engine)
    with S_() as db:
        db.add_all([
            Fund(code="HSA", name="HİSSE FONU", category="Hisse Senedi", risk_level=6, fund_type="YAT", buy_valor=1, sell_valor=2),
            Fund(code="PPA", name="PARA PİYASASI", category="Para Piyasası", risk_level=1, fund_type="YAT", buy_valor=0, sell_valor=0),
            Fund(code="KPL", name="KAPATILAN FON", category="Değişken", risk_level=5, fund_type="YAT", status=STATUS_CLOSED,
                 status_note="SPK kararıyla işleme kapatıldı."),
            Fund(code="OLD", name="ESKİ VERİLİ FON", category="Değişken", risk_level=4, fund_type="YAT"),
        ])
        for i, d in enumerate(DAYS):
            db.add_all([Price(fund_code="HSA", date=d.date(), price=10 + i * 0.1),  # her gün +0,1 TL
                        Price(fund_code="PPA", date=d.date(), price=1.0012 ** i),
                        Price(fund_code="KPL", date=d.date(), price=5.0)])
            if d <= pd.Timestamp("2026-09-10"):
                db.add(Price(fund_code="OLD", date=d.date(), price=3.0))
        db.commit()
        metrics_job.recompute_all(db)

    def override():
        with S_() as s:
            yield s

    app.dependency_overrides[get_db] = override
    yield S_
    app.dependency_overrides.clear()


def client():
    c = TestClient(app)
    c.headers["X-Requested-With"] = "XMLHttpRequest"
    return c


def register(c, email):
    r = c.post("/api/auth/kayit", json={"email": email, "password": "uzun-sifre-1", "name": "X"})
    assert r.status_code == 201
    return r.json()["user"]["id"]


def add_forecasts(db, code, rows):
    """rows: (as_of, lo, hi, source) 1 günlük tahminler; tahmin = (lo+hi)/2."""
    for as_of, lo, hi, source in rows:
        db.add(ForecastDay(fund_code=code, as_of=as_of, base_price=1.0, horizon=1, target_date=as_of,
                           pred_price=(lo + hi) / 2, lo_price=lo, hi_price=hi, method=H.METHOD,
                           method_version=H.METHOD_VERSION, source=source, risk_group="5-7"))
    db.commit()


def price(i):
    return 10 + i * 0.1


def test_favorites_enriched_with_forecast_position_and_warnings(Session):
    c = client()
    uid = register(c, "a@ornek.com")
    for code in ["OLD", "KPL", "PPA", "HSA"]:
        assert c.post(f"/api/favoriler/{code}").status_code == 204
    d = [x.date() for x in DAYS]
    n = len(d)
    with Session() as db:
        # HSA: son 3 tahmin günü; gerçekleşen (ertesi günün fiyatı) ilk ikisinde aralıkta, sonuncusunda dışında
        add_forecasts(db, "HSA", [
            (d[n - 4], price(n - 3) - 0.05, price(n - 3) + 0.05, SOURCE_BACKFILL),
            (d[n - 3], price(n - 2) - 0.05, price(n - 2) + 0.05, SOURCE_LIVE),
            (d[n - 2], price(n - 1) + 0.01, price(n - 1) + 0.2, SOURCE_LIVE),  # gerçekleşen alt sınırın altında
            (d[n - 1], 0.0, 99.0, SOURCE_LIVE),  # henüz gerçekleşmedi: sayılmaz
        ])
        # aynı gün hem canlı hem geriye dönük: canlı alınır
        add_forecasts(db, "HSA", [(d[n - 3], 0.0, 0.1, SOURCE_BACKFILL)])
        # sanal portföyde HSA pozisyonu (gerçekleşmiş alış)
        db.add(SanalAyar(user_id=uid, initial_balance=100_000, start_date=d[0]))
        db.add(SanalEmir(user_id=uid, fund_code="HSA", side="alis", status="gerceklesti", created_at=datetime(2026, 9, 1, 10),
                         order_date=d[0], valor=1, target_date=d[1], amount=1_000, exec_date=d[1], exec_price=price(1),
                         exec_units=99, exec_amount=round(99 * price(1), 2)))
        db.commit()

    favs = c.get("/api/favoriler").json()
    assert [f["code"] for f in favs] == ["HSA", "PPA", "KPL", "OLD"]  # en yeni eklenen başta
    by = {f["code"]: f for f in favs}
    h = by["HSA"]
    assert h["metrics"]["last_price"] == pytest.approx(price(n - 1)) and h["metrics"]["daily_change"] is not None
    fc = h["forecast"]
    assert fc["n"] == 3 and fc["in_band"] == 2 and fc["live"] == 2 and fc["last_in_band"] is False
    assert fc["last_as_of"] == str(d[n - 2]) and fc["last_error_pct"] < 0
    p = h["position"]
    assert p["units"] == 99 and p["value"] == pytest.approx(99 * price(n - 1), abs=0.01) and p["pnl"] > 0
    assert h["warning"] is None and by["PPA"]["forecast"] is None and by["PPA"]["position"] is None
    assert "işleme kapatıldı" in by["KPL"]["warning"]
    assert by["OLD"]["is_stale"] and "güncellenmiyor" in by["OLD"]["warning"]

    # başka kullanıcı: ne favori ne pozisyon görür
    b = client()
    register(b, "b@ornek.com")
    assert b.get("/api/favoriler").json() == []
    b.post("/api/favoriler/HSA")
    assert b.get("/api/favoriler").json()[0]["position"] is None


def test_favorites_without_portfolio_do_not_create_one(Session):
    c = client()
    register(c, "a@ornek.com")
    c.post("/api/favoriler/HSA")
    assert c.get("/api/favoriler").json()[0]["position"] is None
    with Session() as db:
        assert db.scalars(select(SanalAyar)).first() is None  # favoriler sayfası portföy açmaz


def test_recent_hits_window(Session):
    d = [x.date() for x in DAYS]
    n = len(d)
    with Session() as db:
        add_forecasts(db, "HSA", [(d[i], price(i + 1) - 0.05, price(i + 1) + 0.05, SOURCE_BACKFILL) for i in range(n - 1)])
        r = H.recent_hits(db, ["HSA", "PPA"], days=10)
    assert set(r) == {"HSA"} and r["HSA"]["n"] == 10 and r["HSA"]["in_band"] == 10 and r["HSA"]["live"] == 0
    assert H.recent_hits(Session(), []) == {}
