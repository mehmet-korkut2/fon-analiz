from datetime import date

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Fund, FundMetrics, Price
from app.services.metrics_job import recompute_all


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    idx = pd.bdate_range("2025-01-01", "2026-10-09")
    funds = [
        # kod, ad, kategori, risk, başlangıç, bitiş
        ("HSA", "ÖRNEK HİSSE FONU", "Hisse Senedi", 6, 1.0, 1.8),
        ("HSB", "DİĞER HİSSE FONU", "Hisse Senedi", 7, 1.0, 1.3),
        ("PPA", "ÖRNEK PARA PİYASASI FONU", "Para Piyasası", 1, 1.0, 1.6),
        ("PPB", "İKİNCİ PARA PİYASASI", "Para Piyasası", 1, 1.0, 1.7),
    ]
    with Session() as db:
        for code, name, cat, risk, a, b in funds:
            db.add(Fund(code=code, name=name, category=cat, risk_level=risk, fund_type="YAT"))
            db.add_all(Price(fund_code=code, date=d.date(), price=float(p)) for d, p in zip(idx, np.linspace(a, b, len(idx))))
        db.add(Fund(code="KPL", name="KAPALI FON", category="Hisse Senedi", is_active=False))
        db.commit()
        recompute_all(db)

    def override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_sorted_by_1y_return(client):
    body = client.get("/api/funds").json()
    assert body["total"] == 4  # kapalı fon hariç
    codes = [f["code"] for f in body["items"]]
    assert codes == ["HSA", "PPB", "PPA", "HSB"]
    first = body["items"][0]["metrics"]
    assert first["ret_1y"] > 0 and first["sharpe_1y"] is not None


def test_filters_search_and_paging(client):
    assert [f["code"] for f in client.get("/api/funds?category=Para Piyasası&sort=code&order=asc").json()["items"]] == ["PPA", "PPB"]
    assert client.get("/api/funds?risk_min=6").json()["total"] == 2
    # Türkçe karakterli arama: küçük harfle "piyasa" yazınca "PİYASASI" bulunmalı
    assert client.get("/api/funds?q=piyasa").json()["total"] == 2
    assert client.get("/api/funds?q=hsa").json()["items"][0]["code"] == "HSA"
    page2 = client.get("/api/funds?page=2&page_size=3").json()
    assert len(page2["items"]) == 1 and page2["total"] == 4


def test_categories(client):
    cats = {c["name"]: c["count"] for c in client.get("/api/funds/categories").json()}
    assert cats == {"Hisse Senedi": 2, "Para Piyasası": 2}


def test_detail_with_category_rank(client):
    d = client.get("/api/funds/hsb").json()
    assert d["code"] == "HSB" and d["category_rank_1y"] == 2 and d["category_size"] == 2
    assert client.get("/api/funds/YOK").status_code == 404


def test_price_history(client):
    pts = client.get("/api/funds/HSA/prices?months=1").json()
    assert 19 <= len(pts) <= 24
    assert pts[-1]["date"] == "2026-10-09"


def test_price_history_date_range(client):
    pts = client.get("/api/funds/HSA/prices?start=2026-01-01").json()
    assert pts[0]["date"] == "2026-01-01" and pts[-1]["date"] == "2026-10-09"
    pts = client.get("/api/funds/HSA/prices?start=2026-03-01&end=2026-03-31").json()
    assert pts[0]["date"] == "2026-03-02" and pts[-1]["date"] == "2026-03-31"
    assert client.get("/api/funds/HSA/prices?start=2026-03-31&end=2026-03-01").status_code == 422


def test_risk_free_rate_is_money_market_median(client):
    # Sharpe = (getiri - rf) / volatilite; rf = PPA ve PPB'nin 1 yıllık getirilerinin medyanı
    items = {f["code"]: f["metrics"] for f in client.get("/api/funds?page_size=10").json()["items"]}
    rf = (items["PPA"]["ret_1y"] + items["PPB"]["ret_1y"]) / 2
    hsa = items["HSA"]
    assert hsa["sharpe_1y"] == pytest.approx((hsa["ret_1y"] - rf) / hsa["volatility_1y"])


def test_sample_data_when_empty():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override
    try:
        body = TestClient(app).get("/api/funds").json()
        assert body["sample"] is True and len(body["items"]) == 3
    finally:
        app.dependency_overrides.clear()
