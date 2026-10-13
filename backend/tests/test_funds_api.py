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
from app.services.fund_status import apply_status_rules
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
    # Fiyatı 1 Eylül'de kesilen "eski verili" fonlar: getirileri yüksek ama listede,
    # sıralamada ve risksiz getiride yer almamalı
    stale_idx = idx[idx <= "2026-09-01"]
    stale = [
        ("HSX", "ESKİ HİSSE FONU", "Hisse Senedi", 7, 1.0, 5.0),
        ("PPX", "ESKİ PARA PİYASASI FONU", "Para Piyasası", 1, 1.0, 3.0),
    ]
    # SPK 2026/60 kapsamındaki fonlar: verisi güncel ve getirisi yüksek ama varsayılan listede,
    # sıralamada ve risksiz getiride yer almamalı. PPK tasfiye listesinde, BAX sadece işleme kapalı.
    closed = [
        ("PPK", "PARDUS PORTFÖY PARA PİYASASI (TL) FON", "Para Piyasası", 1, 1.0, 2.5),
        ("BAX", "BULLS PORTFÖY ALTIN FONU", "Hisse Senedi", 5, 1.0, 3.0),
    ]
    with Session() as db:
        for (code, name, cat, risk, a, b), dates in [(f, idx) for f in funds + closed] + [(f, stale_idx) for f in stale]:
            db.add(Fund(code=code, name=name, category=cat, risk_level=risk, fund_type="YAT"))
            prices = np.linspace(a, b, len(dates))
            if cat == "Hisse Senedi":
                # hisse fonları dalgalansın (günlük ±%1); para piyasası fonları düz çizgi, volatilitesi ~0
                prices = prices * (1 + 0.01 * (-1) ** np.arange(len(dates)))
            db.add_all(Price(fund_code=code, date=d.date(), price=float(p)) for d, p in zip(dates, prices))
        db.add(Fund(code="KPL", name="KAPALI FON", category="Hisse Senedi", is_active=False))
        db.commit()
        apply_status_rules(db)
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


def test_stale_funds_hidden_by_default(client):
    assert "HSX" not in [f["code"] for f in client.get("/api/funds?page_size=50").json()["items"]]
    body = client.get("/api/funds?include_stale=true&page_size=50").json()
    assert body["total"] == 6
    stale = {f["code"]: f["is_stale"] for f in body["items"]}
    assert stale == {"HSA": False, "HSB": False, "PPA": False, "PPB": False, "HSX": True, "PPX": True}
    # eski fon 3 aylık getiride en yüksek olsa da varsayılan sıralamada başa geçmez
    assert client.get("/api/funds?include_stale=true&sort=ret_3m").json()["items"][0]["code"] == "HSX"
    assert client.get("/api/funds?sort=ret_3m").json()["items"][0]["code"] == "HSA"


def test_stale_fund_detail_and_category_rank(client):
    d = client.get("/api/funds/HSX").json()
    assert d["is_stale"] is True and d["price_date"] == "2026-09-01"
    assert d["category_rank_1y"] is None  # eski fon sıralanmaz
    # güncel fonların sırası eski fonu saymaz: HSA, HSX'ten düşük getirili olsa da 1. / 2
    hsa = client.get("/api/funds/HSA").json()
    assert hsa["is_stale"] is False and hsa["category_rank_1y"] == 1 and hsa["category_size"] == 2


def test_risk_free_rate_is_money_market_median(client):
    # Sharpe = (getiri - rf) / volatilite; rf = PPA ve PPB'nin 1 yıllık getirilerinin medyanı
    # (eski verili PPX dahil olsaydı medyan değişirdi)
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


def test_compare_normalized_series(client):
    body = client.get("/api/compare?funds=hsa,PPA&months=12").json()
    assert [f["code"] for f in body["funds"]] == ["HSA", "PPA"]
    first, last = body["points"][0], body["points"][-1]
    assert first["date"] == body["base_date"] and first["values"] == {"HSA": 100.0, "PPA": 100.0}
    assert last["date"] == "2026-10-09"
    # dönem getirisi, metriklerdeki 1 yıllık getiriyle aynı tanım
    for f in body["funds"]:
        assert f["period_return"] == pytest.approx(f["metrics"]["ret_1y"], abs=1e-4)
        assert f["period_return"] == pytest.approx(last["values"][f["code"]] / 100 - 1, abs=1e-4)


def test_compare_ytd_base_is_previous_year_end(client):
    body = client.get("/api/compare?funds=HSA,HSB&start=2025-12-31").json()
    assert body["base_date"] == "2025-12-31"
    hsa = next(f for f in body["funds"] if f["code"] == "HSA")
    assert hsa["period_return"] == pytest.approx(hsa["metrics"]["ret_ytd"], abs=1e-4)


def test_compare_stale_fund_line_stops(client):
    body = client.get("/api/compare?funds=HSA,HSX&months=3").json()
    hsx = next(f for f in body["funds"] if f["code"] == "HSX")
    assert hsx["is_stale"] is True
    after = [p for p in body["points"] if p["date"] > "2026-09-01"]
    assert after and all(p["values"]["HSX"] is None and p["values"]["HSA"] is not None for p in after)


def test_compare_validation(client):
    assert client.get("/api/compare?funds=HSA").status_code == 422
    assert client.get("/api/compare?funds=HSA,hsa").status_code == 422  # aynı fon iki kez
    assert client.get("/api/compare?funds=HSA,HSB,PPA,PPB,HSX").status_code == 422
    r = client.get("/api/compare?funds=HSA,YOK")
    assert r.status_code == 404 and "YOK" in r.json()["detail"]


def test_rankings_exclude_stale_funds(client):
    body = client.get("/api/rankings").json()
    assert body["eligible"] == 4 and body["as_of"] == "2026-10-09"
    lists = {l["key"]: l for l in body["lists"]}
    ret = lists["return"]
    assert ret["metric"] == "ret_1y" and [f["code"] for f in ret["items"]] == ["HSA", "PPB", "PPA", "HSB"]
    assert [f["rank"] for f in ret["items"]] == [1, 2, 3, 4]
    assert ret["items"][0]["value"] == ret["items"][0]["metrics"]["ret_1y"]
    # eski verili HSX ve PPX hiçbir listede yok
    assert all(f["code"] not in ("HSX", "PPX") for l in body["lists"] for f in l["items"])
    vols = [f["value"] for f in lists["volatility"]["items"]]
    assert vols == sorted(vols)
    sharpes = [f["value"] for f in lists["sharpe"]["items"]]
    assert sharpes == sorted(sharpes, reverse=True)


def test_rankings_category_period_and_limit(client):
    body = client.get("/api/rankings?category=Hisse Senedi&period=ret_3m&limit=1").json()
    assert body["eligible"] == 2 and body["category"] == "Hisse Senedi"
    ret = body["lists"][0]
    assert ret["metric"] == "ret_3m" and len(ret["items"]) == 1 and ret["items"][0]["category"] == "Hisse Senedi"
    assert client.get("/api/rankings?period=volatility_1y").status_code == 422


def test_spk_closed_funds_hidden_by_default(client):
    codes = [f["code"] for f in client.get("/api/funds?page_size=50").json()["items"]]
    assert "PPK" not in codes and "BAX" not in codes
    body = client.get("/api/funds?include_closed=true&page_size=50").json()
    status = {f["code"]: f["status"] for f in body["items"]}
    assert status["PPK"] == "islem_kapali_tasfiye" and status["BAX"] == "islem_kapali" and status["HSA"] == "aktif"
    # kategori sayıları ve sıralamalar da kapalı fonları saymaz
    cats = {c["name"]: c["count"] for c in client.get("/api/funds/categories").json()}
    assert cats == {"Hisse Senedi": 2, "Para Piyasası": 2}
    rankings = client.get("/api/rankings").json()
    assert rankings["eligible"] == 4
    assert all(f["code"] not in ("PPK", "BAX") for l in rankings["lists"] for f in l["items"])


def test_spk_closed_fund_detail_note_and_rank(client):
    d = client.get("/api/funds/PPK").json()
    assert d["status"] == "islem_kapali_tasfiye"
    assert d["status_note"] == "SPK'nın 17.09.2026 tarihli kararıyla işleme kapatılmış ve tasfiye sürecindedir."
    assert d["status_source"] == "SPK Bülteni 2026/60" and d["status_url"].startswith("https://spk.gov.tr/")
    assert d["category_rank_1y"] is None
    bax = client.get("/api/funds/BAX").json()
    assert bax["status"] == "islem_kapali" and "tasfiye" not in bax["status_note"]
    # aktif fonun kategori sırasına kapalı fon (BAX, Hisse Senedi) girmez
    assert client.get("/api/funds/HSA").json()["category_size"] == 2


def test_no_sharpe_for_near_riskless_funds(client):
    items = {f["code"]: f["metrics"] for f in client.get("/api/funds?page_size=10").json()["items"]}
    # para piyasası fonlarının fiyatı düz çizgi: volatilite %5'in altında, Sharpe yok ve nedeni yazıyor
    for code in ("PPA", "PPB"):
        assert items[code]["volatility_1y"] < 0.05
        assert items[code]["sharpe_1y"] is None and "Sharpe anlamlı değil" in items[code]["sharpe_note"]
    assert items["HSA"]["volatility_1y"] > 0.05 and items["HSA"]["sharpe_1y"] is not None
    assert items["HSA"]["sharpe_note"] is None
    # Sharpe sıralamasına sadece Sharpe'ı olan fonlar girer
    sharpe = next(l for l in client.get("/api/rankings").json()["lists"] if l["key"] == "sharpe")
    assert [f["code"] for f in sharpe["items"]] == ["HSA", "HSB"]

