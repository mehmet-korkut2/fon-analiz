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
from app.models import Fund, Price
from app.services import recommender as R
from app.services.fund_status import STATUS_LIQUIDATION
from app.services.metrics_job import recompute_all

RF = 0.40


def frame(rows):
    """rows: (code, category, risk, ret_3m, ret_6m, ret_1y, vol, sharpe, mdd)"""
    df = pd.DataFrame(rows, columns=["code", "category", "risk_level", "ret_3m", "ret_6m", "ret_1y", "vol", "sharpe", "mdd"])
    df["name"] = df["code"] + " FONU"
    df["as_of"] = date(2026, 10, 9)
    return df[R.FRAME_COLUMNS]


# Para piyasası benzeri fonlar düşük volatiliteli (Sharpe yok); hisse fonları dalgalı
POOL = frame([
    ("PP1", "Para Piyasası", 1, 0.090, 0.190, 0.46, 0.015, None, 0.000),
    ("PP2", "Para Piyasası", 1, 0.088, 0.185, 0.44, 0.015, None, 0.000),
    ("PP3", "Para Piyasası", 2, 0.085, 0.180, 0.42, 0.016, None, -0.001),
    ("BA1", "Borçlanma Araçları", 2, 0.080, 0.170, 0.41, 0.030, None, -0.010),
    ("DG1", "Değişken", 3, 0.050, 0.150, 0.50, 0.045, None, -0.020),
    ("HS1", "Hisse Senedi", 5, 0.150, 0.300, 0.70, 0.120, 2.50, -0.080),
    ("HS2", "Hisse Senedi", 5, 0.120, 0.250, 0.60, 0.110, 1.82, -0.070),
    ("HS3", "Hisse Senedi", 5, -0.050, 0.050, 0.65, 0.140, 1.79, -0.150),  # 1 yıl iyi ama son 3 ay kötü
    ("HS4", "Hisse Senedi", 6, 0.100, 0.200, 0.55, 0.200, 0.75, -0.200),
    ("SR1", "Serbest", 4, 0.110, 0.220, 0.58, 0.090, 2.00, -0.050),
    ("NUL", "Değişken", None, 0.100, 0.200, 0.60, 0.060, 3.33, -0.010),  # risk değeri boş
])


def test_eligible_profile_filters():
    codes = lambda df: sorted(df["code"])  # noqa: E731
    # temkinli: risk 1-3 ve volatilite <= %5
    assert codes(R.eligible(POOL, "temkinli", False)) == ["BA1", "DG1", "PP1", "PP2", "PP3"]
    # agresif: risk 4-7; serbest fon sadece nitelikli yatırımcıya, risk değeri boş fon hiç
    assert codes(R.eligible(POOL, "agresif", False)) == ["HS1", "HS2", "HS3", "HS4"]
    assert "SR1" in codes(R.eligible(POOL, "agresif", True))
    assert "NUL" not in codes(R.eligible(POOL, "agresif", True))
    # dengeli: risk 2-5 ve volatilite <= %15 (HS4 risk 6, dışarıda)
    assert codes(R.eligible(POOL, "dengeli", False)) == ["BA1", "DG1", "HS1", "HS2", "HS3", "PP3"]


def test_components_are_percentiles_and_weighted():
    s = R.score(R.eligible(POOL, "dengeli", False), "dengeli", RF)
    for c in R.COMPONENTS:
        assert s[c].between(0, 1).all() and s[c].max() == 1
    w = R.WEIGHTS["dengeli"]
    row = s.iloc[0]
    assert row["score"] == pytest.approx(sum(row[c] * w[c] for c in R.COMPONENTS))
    assert all(abs(sum(v.values()) - 1) < 1e-9 for v in R.WEIGHTS.values())


def test_low_vol_funds_ra_pool_depends_on_profile():
    pool = R.eligible(POOL, "dengeli", False)
    # dengeli ("tum"): düşük volatiliteli fonun RA'sı, fazla getirisinin tüm havuzdaki yüzdeliği
    tum = R.score(pool, "dengeli", RF).set_index("code")
    assert tum.loc["PP3", "riske_gore"] == tum.loc["PP3", "getiri"]
    # aynı havuz "ayri" modda: düşük volatiliteli fonlar sadece kendi aralarında karşılaştırılır,
    # en yüksek fazla getirili olan (DG1) 1 alır; hisse fonlarının Sharpe yüzdeliği değişmez
    ayri = R.score(pool, "dengeli", RF, ra_mode="ayri").set_index("code")
    assert ayri.loc["DG1", "riske_gore"] == 1
    assert ayri.loc["HS1", "riske_gore"] == tum.loc["HS1", "riske_gore"] == 1
    assert R.RA_MODE == {"temkinli": "ayri", "dengeli": "tum", "agresif": "tum"}


def test_temkinli_does_not_penalize_money_market_funds():
    s = R.score(R.eligible(POOL, "temkinli", False), "temkinli", RF).set_index("code")
    # Sharpe'ı olmayan para piyasası fonu en yüksek fazla getiriyle kendi havuzunda zirvede
    assert s.loc["DG1", "riske_gore"] == 1 and s.loc["PP1", "riske_gore"] > s.loc["BA1", "riske_gore"]
    assert s.index[0] in ("PP1", "DG1")


def test_consistency_penalizes_recent_weakness():
    s = R.score(R.eligible(POOL, "agresif", False), "agresif", RF).set_index("code")
    # HS3'ün 1 yıllık getirisi HS2'den yüksek ama son 3 ayı negatif
    assert s.loc["HS3", "getiri"] > s.loc["HS2", "getiri"]
    assert s.loc["HS3", "tutarlilik"] < s.loc["HS2", "tutarlilik"]
    assert s.loc["HS3", "worst_period"] == "3 ay"


def test_category_limit_and_portfolio_pick():
    scored = R.score(R.eligible(POOL, "agresif", True), "agresif", RF)
    picked = R.diversify(scored, limit=10)
    assert picked["category"].value_counts().max() <= 2
    assert len(picked[picked["category"] == "Hisse Senedi"]) == 2
    port = R.portfolio_pick(picked, 2)
    assert port["category"].nunique() == 2  # önce farklı kategoriler


def test_dengeli_risky_quota():
    pool = R.eligible(POOL, "dengeli", False)
    scored = R.score(pool, "dengeli", RF)
    assert sorted(pool.loc[R.is_risky(pool), "code"]) == ["HS1", "HS2", "HS3"]
    # kota: ilk 3'ün en az 2'si riskli (risk değeri 4+ ve volatilite %5+) gruptan
    picked = R.diversify(scored, limit=3, min_risky=2)
    assert R.is_risky(picked).sum() >= 2 and len(picked) == 3
    assert list(picked["score"]) == sorted(picked["score"], reverse=True)
    port = R.portfolio_pick(picked, 2, min_risky=2)
    assert R.is_risky(port).all()
    # recommend_from: kota yüzünden girenler işaretli ve gerekçesi yazıyor
    rec = R.recommend_from(POOL, date(2026, 10, 9), "dengeli", False, limit=3, rf=RF)
    assert R.is_risky(rec.items).sum() >= 2 and R.is_risky(rec.portfolio).sum() >= 2
    for code in rec.items.loc[rec.items["quota"], "code"]:
        assert "çeşitlendirme" in rec.reasons[code][0][-1]
    # temkinli ve agresif profillerde kota yok
    assert set(R.RISKY_QUOTA) == {"dengeli"}
    assert not R.recommend_from(POOL, None, "agresif", False, rf=RF).items["quota"].any()


def test_reasons_and_caution():
    s = R.score(R.eligible(POOL, "agresif", False), "agresif", RF).set_index("code", drop=False)
    reasons, caution = R.explain(s.loc["HS1"], "agresif", RF)
    assert len(reasons) == 3 and "agresif profilin aralığında (4-7)" in reasons[-1]
    assert any("Sharpe oranı 2,50" in r for r in reasons)
    _, caution = R.explain(s.loc["HS4"], "agresif", RF)
    assert caution and caution.startswith("Dikkat:")
    t = R.score(R.eligible(POOL, "temkinli", False), "temkinli", RF).set_index("code", drop=False)
    reasons, _ = R.explain(t.loc["PP1"], "temkinli", RF)
    assert any("neredeyse hiç dalgalanmıyor" in r or "risksiz getirinin" in r for r in reasons)


def test_recommend_from_empty_pool():
    rec = R.recommend_from(POOL.iloc[0:0], None, "dengeli", False)
    assert rec.items.empty and rec.pool_size == 0


# --- Veritabanıyla: performans ve geriye dönük test ----------------------------

@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    idx = pd.bdate_range("2024-06-03", "2026-10-09")
    n = len(idx)
    t = np.arange(n)
    wiggle = 1 + 0.01 * (-1) ** t
    split = idx.get_indexer([pd.Timestamp("2025-10-09")], method="pad")[0]  # seçim günü (12 ay önce)
    series = {
        # kod: (kategori, risk, fiyatlar)
        "MM1": ("Para Piyasası", 1, 1.0 * 1.0016 ** t),
        "MM2": ("Para Piyasası", 1, 1.0 * 1.0015 ** t),
        "MM3": ("Para Piyasası", 1, 1.0 * 1.0014 ** t),
        "EQA": ("Hisse Senedi", 6, (1.0 * 1.0022 ** t) * wiggle),
        "EQB": ("Hisse Senedi", 6, (1.0 * 1.0018 ** t) * wiggle),
        "VAR": ("Değişken", 5, (1.0 * 1.0020 ** t) * (1 + 0.008 * (-1) ** t)),
    }
    # BAD: seçim gününe kadar en iyi fon, sonra çöküyor ve bugün SPK kararıyla kapalı
    bad = np.where(t <= split, 1.0026 ** t, 1.0026 ** split * 0.5) * wiggle
    series["BAD"] = ("Değişken", 5, bad)
    with Session() as db:
        for code, (cat, risk, prices) in series.items():
            db.add(Fund(code=code, name=f"{code} FONU", category=cat, risk_level=risk, fund_type="YAT",
                        status=STATUS_LIQUIDATION if code == "BAD" else "aktif"))
            db.add_all(Price(fund_code=code, date=d.date(), price=float(p)) for d, p in zip(idx, prices))
        db.commit()
        recompute_all(db)
    R._frame_cache.clear()
    with Session() as s:
        yield s, Session


def test_equal_weight_buy_and_hold(db_session):
    db, _ = db_session
    perf = R.performance(db, ["MM1", "EQA"], date(2025, 10, 9), date(2026, 10, 9), ["MM1", "MM2", "MM3"])
    s = perf.series
    assert s["portfolio"].iloc[0] == pytest.approx(100) and s["benchmark"].iloc[0] == pytest.approx(100)
    # eşit ağırlıklı al-tut = fonların dönem getirilerinin ortalaması
    assert perf.portfolio["return"] == pytest.approx(np.mean(list(perf.funds.values())))
    assert perf.benchmark_funds == 3
    # kıyas = para piyasası fonlarının (100'den başlayan) serilerinin medyanı
    mm = R.performance(db, ["MM1", "MM2", "MM3"], date(2025, 10, 9), date(2026, 10, 9), ["MM1", "MM2", "MM3"])
    assert perf.benchmark["return"] == pytest.approx(np.median(list(mm.funds.values())))
    assert mm.funds["MM1"] > mm.funds["MM2"] > mm.funds["MM3"]


def test_current_recommendations_exclude_closed_fund(db_session):
    db, _ = db_session
    rec = R.recommend(db, "agresif", False)
    assert "BAD" not in set(rec.items["code"])


def test_backtest_selects_with_past_data_only(db_session):
    db, _ = db_session
    bt = R.backtest(db, "agresif", False)
    assert bt.selection_date == date(2025, 10, 9)
    # 12 ay önce BAD en iyi görünüyordu ve o gün kapatılmamıştı: seçilmesi gerekir (geleceği bilmeden)
    assert "BAD" in set(bt.recommendation.items["code"])
    assert "BAD" in set(bt.recommendation.portfolio["code"])
    # ve sonraki 12 aydaki çöküşü portföyün performansına yansır
    assert bt.performance.funds["BAD"] < -0.4
    assert bt.performance.start == date(2025, 10, 9) and bt.performance.end == date(2026, 10, 9)


def test_api_recommendations(db_session):
    _, Session = db_session

    def override():
        with Session() as s:
            yield s

    app.dependency_overrides[get_db] = override
    try:
        c = TestClient(app)
        body = c.get("/api/recommendations", params={"profile": "agresif"}).json()
        assert body["risk_range"] == [4, 7] and body["ra_mode"] == "tum" and body["category_limit"] == 2
        assert body["items"][0]["rank"] == 1 and set(body["items"][0]["components"]) == set(R.COMPONENTS)
        assert body["items"][0]["reasons"] and body["performance"]["portfolio"]["return"] is not None
        assert sum(p["weight"] for p in body["portfolio"]) == pytest.approx(1)
        # kayan pencere tablosu boşken özet yok
        bt = c.get("/api/recommendations/backtest", params={"profile": "agresif"}).json()
        assert bt["summary"] is None and bt["windows"] == [] and bt["years"] == 3
        with Session() as s:
            assert R.store_rolling(s) > 0
        bt = c.get("/api/recommendations/backtest", params={"profile": "agresif"}).json()
        s = bt["summary"]
        assert s["windows"] == len(bt["windows"]) > 0
        assert s["beats"] == sum(w["excess"] > 0 for w in bt["windows"])
        assert s["worst"]["excess"] <= s["median_excess"] <= s["best"]["excess"]
        assert c.get("/api/recommendations", params={"profile": "yok"}).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_selection_dates_are_month_starts_with_full_horizon(db_session):
    db, _ = db_session
    dates = R.selection_dates(db)
    # veri 2024-06-03'te başlıyor, son fiyat 2026-10-09: seçim 2024-06 ... 2025-10 (12 ay sonrası var)
    assert dates[0] == date(2024, 6, 3) and dates[-1] == date(2025, 10, 1)
    assert len(dates) == 17 and all(d.day <= 7 for d in dates)
    assert len({(d.year, d.month) for d in dates}) == len(dates)


def test_rolling_backtest_windows(db_session):
    db, _ = db_session
    ws = R.rolling_backtest(db, profiles=("agresif",), qualified_options=(False,))
    # ilk aylarda 1 yıllık geçmiş yok, aday çıkmaz; pencereler 1 yıllık veri biriktikten sonra başlar
    assert ws and ws[0].start >= date(2025, 6, 1)
    for w in ws:
        assert w.end == (pd.Timestamp(w.start) + pd.DateOffset(months=12)).date()
        assert w.excess == pytest.approx(w.portfolio_return - w.benchmark_return)
    # BAD seçim günlerinde en iyi görünüyordu, sonradan çöktü: seçildiği pencerelerde portföyü aşağı çeker
    bad = [w for w in ws if "BAD" in w.codes]
    assert bad and all(w.excess < 0 for w in bad if w.start <= date(2025, 10, 1))
    s = R.summarize_windows(ws)
    assert s["windows"] == len(ws) and s["best"].excess >= s["worst"].excess


def test_store_and_load_rolling(db_session):
    db, _ = db_session
    n = R.store_rolling(db)
    loaded = [w for p in R.PROFILES_ALL for q in (False, True) for w in R.load_windows(db, p, q)]
    assert n == len(loaded) > 0
    assert R.store_rolling(db) == n  # yeniden hesaplama öncekileri siler, çoğaltmaz
