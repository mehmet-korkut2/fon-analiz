"""Enflasyon ve reel getiri (app/services/inflation.py): hesaplama, dönem hizalaması, eksik ay, internetsiz ve
anahtarsız çalışma, EVDS ayrıştırma, anahtarın sızmaması, hayatta kalma yanılgısına karşı özet, API."""
import logging
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest
import requests
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import CpiMonth, Fund, FundMetrics, Price
from app.services import inflation as I
from app.services import metrics_job
from app.services.fund_status import STATUS_CLOSED

SECRET = "GIZLIANAHT1"  # sahte anahtar: hiçbir çıktıda görünmemeli


def cpi_rows(start=date(2023, 1, 1), end=date(2026, 10, 1), monthly=0.02):
    """Her ay %2 artan sahte TÜFE."""
    out, m, v = [], start, 100.0
    while m <= end:
        out.append((m, round(v, 6)))
        m, v = I.add_months(m, 1), v * (1 + monthly)
    return out


def series(points: dict) -> pd.Series:
    return pd.Series(points, dtype=float).rename(lambda d: pd.Timestamp(d)).sort_index()


# --- EVDS ayrıştırma ve istek -----------------------------------------------------------------------

def test_parse_evds_unpadded_months_and_gaps():
    payload = {"items": [
        {"Tarih": "2026-10", "TP_TUKFIY2025_GENEL": "140.77000000"},
        {"Tarih": "2005-1", "TP_TUKFIY2025_GENEL": "3.59652300", "UNIXTIME": {"$numberLong": "1"}},
        {"Tarih": "2026-11", "TP_TUKFIY2025_GENEL": None},  # henüz açıklanmadı
        {"Tarih": "2026-12", "TP_TUKFIY2025_GENEL": ""},
        {"Tarih": "bozuk", "TP_TUKFIY2025_GENEL": "1"},
    ]}
    assert I.parse_evds(payload) == [(date(2005, 1, 1), 3.596523), (date(2026, 10, 1), 140.77)]
    assert I.parse_evds({}) == []


class FakeResp:
    def __init__(self, status=200, payload=None):
        self.status_code, self._p = status, payload

    def json(self):
        if self._p is None:
            raise ValueError("bozuk")
        return self._p


def test_fetch_sends_key_only_in_header(monkeypatch):
    seen = {}

    def get(url, headers=None, timeout=None):
        seen.update(url=url, headers=headers)
        return FakeResp(200, {"items": [{"Tarih": "2026-9", "TP_TUKFIY2025_GENEL": "137.23"}]})

    monkeypatch.setattr(I.requests, "get", get)
    assert I.fetch(date(2025, 1, 1), SECRET) == [(date(2026, 9, 1), 137.23)]
    assert seen["headers"] == {"key": SECRET} and SECRET not in seen["url"]
    assert "series=TP.TUKFIY2025.GENEL" in seen["url"] and "startDate=01-01-2025" in seen["url"] and "frequency=5" in seen["url"]


@pytest.mark.parametrize("resp,msg", [
    (FakeResp(403), "403"), (FakeResp(500), "HTTP 500"), (FakeResp(200, None), "okunamadı"),
])
def test_fetch_errors_never_contain_key(monkeypatch, resp, msg):
    monkeypatch.setattr(I.requests, "get", lambda *a, **k: resp)
    with pytest.raises(I.InflationError, match=msg) as e:
        I.fetch(date(2025, 1, 1), SECRET)
    assert SECRET not in str(e.value)


def test_fetch_connection_error_hides_details(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError(f"bağlantı yok key={SECRET}")  # alt katman ayrıntıyı sızdırsa bile

    monkeypatch.setattr(I.requests, "get", boom)
    with pytest.raises(I.InflationError) as e:
        I.fetch(date(2025, 1, 1), SECRET)
    assert SECRET not in str(e.value) and e.value.__cause__ is None and e.value.__suppress_context__


# --- güncelleme: anahtar yok, internet yok, hata, güncel --------------------------------------------

@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s


@pytest.mark.parametrize("today,expected", [
    (date(2026, 11, 2), date(2026, 9, 1)),  # Ekim TÜFE'si henüz açıklanmadı (3 Kasım)
    (date(2026, 11, 3), date(2026, 10, 1)),
    (date(2026, 1, 1), date(2025, 11, 1)),  # yıl geçişi
])
def test_expected_month(today, expected):
    assert I.expected_month(today) == expected


def test_update_without_key_or_internet_keeps_data(db, caplog):
    calls = []

    def fetcher(start, key):
        calls.append(start)
        return cpi_rows(end=date(2026, 9, 1))

    assert I.update(db, key="", fetcher=fetcher)["status"] == "anahtar_yok" and calls == []
    assert I.update(db, key=SECRET, fetcher=fetcher, online=lambda: False, today=date(2026, 11, 13))["status"] == "offline"
    assert calls == [] and I.latest_month(db) is None
    caplog.set_level(logging.DEBUG)
    r = I.update(db, key=SECRET, fetcher=fetcher, today=date(2026, 11, 13))
    assert r["status"] == "ok" and r["added"] == len(cpi_rows(end=date(2026, 9, 1))) and calls == [I.FIRST_MONTH]
    # Ekim bekleniyor: internet yokken son bilinen veriyle devam (silinmez)
    n = db.scalar(select(func.count()).select_from(CpiMonth))
    r = I.update(db, key=SECRET, fetcher=fetcher, online=lambda: False, today=date(2026, 11, 13))
    assert r == {"status": "offline", "last_month": "2026-09-01"}
    assert db.scalar(select(func.count()).select_from(CpiMonth)) == n

    def failing(start, key):
        raise I.InflationError("EVDS isteği reddetti (HTTP 403): API anahtarı geçersiz ya da tanımsız.")

    r = I.update(db, key=SECRET, fetcher=failing, today=date(2026, 11, 13))
    assert r["status"] == "hata" and db.scalar(select(func.count()).select_from(CpiMonth)) == n
    # yeni ay gelince yalnızca eklenir; son 12 ay yeniden alınır
    r = I.update(db, key=SECRET, fetcher=lambda s, k: [(I.add_months(date(2026, 10, 1), 0), 999.0)], today=date(2026, 11, 13))
    assert r["status"] == "ok" and r["added"] == 1 and r["last_month"] == "2026-10-01"
    assert I.update(db, key=SECRET, fetcher=fetcher, today=date(2026, 11, 13))["status"] == "guncel"
    assert all(SECRET not in str(x) for x in [r, *[rec.getMessage() for rec in caplog.records]])


def test_status_reports_key_presence_not_value(db, monkeypatch):
    monkeypatch.setattr(I.settings, "evds_api_key", SECRET)
    s = I.status(db)
    assert s["key_configured"] is True and SECRET not in str(s) and s["available"] is False
    monkeypatch.setattr(I.settings, "evds_api_key", None)
    assert I.status(db)["key_configured"] is False


# --- hesap ve hizalama ------------------------------------------------------------------------------

def test_real_return_formula():
    assert I.real_return(0.50, 0.30) == pytest.approx(1.5 / 1.3 - 1)
    assert I.real_return(0.30, 0.30) == pytest.approx(0)  # enflasyon kadar: reel sıfır
    assert I.real_return(-0.10, 0.20) == pytest.approx(0.9 / 1.2 - 1)
    assert I.real_return(None, 0.3) is None and I.real_return(0.1, None) is None


def test_inflation_between_and_missing_month():
    cpi = pd.Series({date(2026, 1, 1): 100.0, date(2026, 2, 1): 110.0, date(2026, 4, 1): 121.0})
    assert I.inflation_between(cpi, date(2026, 1, 1), date(2026, 4, 1)) == pytest.approx(0.21)
    assert I.inflation_between(cpi, date(2026, 3, 1), date(2026, 4, 1)) is None  # Mart eksik


def test_alignment_to_last_cpi_month_end():
    """Son TÜFE ayı Ekim 2026: dönem sonu 31.10.2026 (cumartesi) -> 30.10 cuma fiyatı; 12 ay önce 31.10.2025."""
    cpi = pd.Series(dict(cpi_rows(end=date(2026, 10, 1))))
    idx = pd.bdate_range("2023-01-02", "2026-11-12")
    prices = pd.Series(np.linspace(10, 30, len(idx)), index=idx)
    prices[pd.Timestamp("2026-11-12")] = 1000.0  # TÜFE'den sonraki fiyatlar kullanılmamalı
    out = {p.months: p for p in I.fund_real_returns(prices, cpi)}
    p12 = out[12]
    assert p12.end == date(2026, 10, 31) and p12.start == date(2025, 10, 31)
    assert p12.nominal == pytest.approx(prices["2026-10-30"] / prices["2025-10-31"] - 1)
    assert p12.inflation == pytest.approx(1.02 ** 12 - 1)
    assert p12.real == pytest.approx((1 + p12.nominal) / (1 + p12.inflation) - 1)
    assert out[1].start == date(2026, 9, 30) and out[1].inflation == pytest.approx(0.02)
    assert out[36].start == date(2023, 10, 31) and out[36].real is not None
    assert [p.label for p in out.values()] == ["1 ay", "3 ay", "6 ay", "1 yıl", "3 yıl"]


def test_missing_month_price_or_history_gives_none():
    cpi = pd.Series(dict(cpi_rows(start=date(2025, 1, 1), end=date(2026, 10, 1))))  # 36 ay öncesi yok
    idx = pd.bdate_range("2025-06-02", "2026-10-30")  # fon 2025 ortasında kuruldu
    prices = pd.Series(np.linspace(1, 2, len(idx)), index=idx)
    out = {p.months: p for p in I.fund_real_returns(prices, cpi)}
    assert out[36].inflation is None and out[36].real is None and out[36].beat is None
    assert out[12].nominal is not None  # 31.10.2025'te fiyatı var
    old = prices[prices.index <= "2026-09-15"]  # fiyatı Eylül ortasında kesilmiş: dönem sonu fiyatı yok
    assert all(p.real is None for p in I.fund_real_returns(old, cpi))
    assert I.fund_real_returns(prices, pd.Series(dtype=float)) == []


def test_purchasing_power():
    cpi = pd.Series({date(2026, 1, 1): 100.0, date(2026, 10, 1): 125.0})
    pp = I.purchasing_power(cpi, 10_000, date(2026, 1, 20))
    assert pp["available"] and pp["inflation"] == pytest.approx(0.25) and pp["real_value"] == pytest.approx(8_000)
    later = I.purchasing_power(cpi, 10_000, date(2026, 11, 13))
    assert later["available"] is False and "Kasım 2026" in later["message"]
    assert I.purchasing_power(pd.Series(dtype=float), 1, date(2026, 1, 1))["message"] == I.NO_DATA


# --- veritabanı: metrik, özet, API ------------------------------------------------------------------

@pytest.fixture
def Session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    S = sessionmaker(bind=engine)
    idx = pd.bdate_range("2025-09-01", "2026-11-12")
    t = np.arange(len(idx))
    with S() as db:
        funds = {
            "WIN": ("Hisse Senedi", 6, 1.0 * 1.0012 ** t),  # yılda ~%35: enflasyonu (%26,8) yener
            "LOS": ("Hisse Senedi", 6, 1.0 * 1.0004 ** t),  # ~%10: yenemez
            "MM1": ("Para Piyasası", 1, 1.0 * 1.0011 ** t),
        }
        for code, (cat, risk, p) in funds.items():
            db.add(Fund(code=code, name=f"{code} FONU", category=cat, risk_level=risk, fund_type="YAT"))
            db.add_all(Price(fund_code=code, date=d.date(), price=float(v)) for d, v in zip(idx, p))
        # GON: yılın ortasında fiyatı kesilen ve SPK kararıyla kapatılan fon (-%80): bugün listede yok
        db.add(Fund(code="GON", name="GİDEN FON", category="Hisse Senedi", risk_level=6, fund_type="YAT", status=STATUS_CLOSED))
        gone = idx[idx <= "2026-05-15"]
        db.add_all(Price(fund_code="GON", date=d.date(), price=1.0 if d < pd.Timestamp("2026-05-01") else 0.2) for d in gone)
        db.commit()

    def override():
        with S() as s:
            yield s

    app.dependency_overrides[get_db] = override
    yield S
    app.dependency_overrides.clear()


def load_cpi(S):
    with S() as db:
        I.store(db, cpi_rows(end=date(2026, 10, 1)))
        metrics_job.recompute_all(db)


def test_api_without_cpi_says_no_data(Session):
    with Session() as db:
        metrics_job.recompute_all(db)
        assert all(m.real_ret_1y is None for m in db.scalars(select(FundMetrics)))
    c = TestClient(app)
    r = c.get("/api/funds/WIN/real").json()
    assert r["available"] is False and r["message"] == "Enflasyon verisi yok." and r["periods"] == []
    s = c.get("/api/inflation").json()
    assert s["available"] is False and s["summary"]["available"] is False and s["key_configured"] is False
    assert c.get("/api/funds", params={"beats_inflation": True}).json()["total"] == 0
    assert c.get("/api/funds/YOK/real").status_code == 404


def test_metrics_api_filters_and_sort(Session):
    load_cpi(Session)
    c = TestClient(app)
    with Session() as db:
        m = {x.fund_code: x for x in db.scalars(select(FundMetrics))}
    assert m["WIN"].real_ret_1y > 0 > m["LOS"].real_ret_1y and m["WIN"].real_as_of == date(2026, 10, 31)
    d = c.get("/api/funds/WIN/real").json()
    assert d["available"] and d["last_month"] == "2026-10-01" and d["end"] == "2026-10-31" and "TÜİK" in d["source_note"]
    y = next(p for p in d["periods"] if p["months"] == 12)
    assert y["beat"] is True and y["real"] == pytest.approx(m["WIN"].real_ret_1y)
    assert y["real"] == pytest.approx((1 + y["nominal"]) / (1 + y["inflation"]) - 1)
    beats = c.get("/api/funds", params={"beats_inflation": True}).json()
    expected = {code for code, x in m.items() if x.real_ret_1y is not None and x.real_ret_1y > 0 and code != "GON"}
    assert "WIN" in expected and "LOS" not in expected
    assert {f["code"] for f in beats["items"]} == expected and beats["total"] == len(expected)
    srt = c.get("/api/funds", params={"sort": "real_ret_1y", "order": "desc"}).json()["items"]
    assert srt[0]["code"] == "WIN" and srt[0]["metrics"]["real_ret_1y"] > 0
    rk = c.get("/api/rankings", params={"beats_inflation": True}).json()
    assert all(f["metrics"]["real_ret_1y"] > 0 for lst in rk["lists"] for f in lst["items"])


def test_beat_summary_counts_closed_funds(Session):
    """Hayatta kalma yanılgısı: dönem içinde kapanan fon 'tüm' evrende var, 'aktif' evrende yok."""
    load_cpi(Session)
    with Session() as db:
        s = I.beat_summary(db)
    assert s["start"] == date(2025, 10, 31) and s["end"] == date(2026, 10, 31) and s["exited"] == 1
    assert s["all"]["n"] == 4 and s["active"]["n"] == 3  # GON yalnızca 'tüm'de
    hs = next(c for c in s["categories"] if c["category"] == "Hisse Senedi")
    assert hs["all"] == {"n": 3, "beat": 1, "share": pytest.approx(1 / 3)}
    assert hs["active"] == {"n": 2, "beat": 1, "share": pytest.approx(0.5)}  # kapananı unutunca pay şişer
    body = TestClient(app).get("/api/inflation").json()
    assert body["summary"]["all"]["n"] == 4 and body["last_month"] == "2026-10-01" and body["series"] == "TP.TUKFIY2025.GENEL"


def test_sanal_and_what_if_purchasing_power(Session):
    load_cpi(Session)
    c = TestClient(app)
    w = c.get("/api/sanal-portfoy/geriye", params={"funds": "WIN", "tarih": "2026-01-05", "tutar": 10_000}).json()
    pp = w["funds"][0]["purchasing_power"]
    assert pp["available"] and pp["start_month"] == "2026-01-01" and pp["last_month"] == "2026-10-01"
    assert pp["real_value"] == pytest.approx(w["funds"][0]["value"] / (1.02 ** 9), rel=1e-6)
    c.headers["X-Requested-With"] = "x"
    c.post("/api/auth/kayit", json={"email": "a@ornek.com", "password": "uzun-sifre-1", "name": "A"})
    s = c.get("/api/sanal-portfoy").json()["purchasing_power"]
    assert s["available"] is False and "henüz açıklanmadı" in s["message"]  # portföy bugün başladı


def test_summary_cache_refreshes_when_cpi_changes(Session, monkeypatch):
    load_cpi(Session)
    calls = []
    real = I.beat_summary
    monkeypatch.setattr(I, "beat_summary", lambda db: calls.append(1) or real(db))
    I._summary_cache.clear()
    with Session() as db:
        a = I.beat_summary_cached(db)
        assert I.beat_summary_cached(db) is a and len(calls) == 1  # aynı veri: yeniden hesaplanmaz
        I.store(db, [(date(2026, 11, 1), 999.0)])  # yeni TÜFE ayı
        b = I.beat_summary_cached(db)
    assert len(calls) == 2 and b["last_month"] == date(2026, 11, 1)
