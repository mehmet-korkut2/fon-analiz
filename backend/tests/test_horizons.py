"""Tahmin karnesi: ufka göre tahmin ve konformal aralık, takvim, gerçekleşen, kayıt (app/ml/horizons.py)."""
from datetime import date

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.ml import horizons as H
from app.ml.evaluation import INTERVAL
from app.ml.features import YEAR, features_at, make_panel
from app.ml.job import migrate_legacy
from app.ml.trading_calendar import add_trading_days, is_trading_day, target_dates
from app.models import SOURCE_BACKFILL, SOURCE_LIVE, ForecastDay, Fund, Price

CODES = {"MM1": ("Para Piyasası", 1, 0.0002, 0.0003), "BR1": ("Borçlanma Araçları", 3, 0.0008, 0.004),
         "BR2": ("Borçlanma Araçları", 4, 0.0007, 0.005), "HS1": ("Hisse Senedi", 6, 0.001, 0.015),
         "HS2": ("Hisse Senedi", 7, 0.0009, 0.02), "YOK": ("Değişken", None, 0.0005, 0.01)}


def make_prices(n=420, seed=3):
    idx = pd.bdate_range("2024-01-01", periods=n)
    rng = np.random.default_rng(seed)
    return pd.DataFrame({c: 10 * np.cumprod(1 + rng.normal(m, s, n)) for c, (_, _, m, s) in CODES.items()}, index=idx)


def meta():
    return pd.DataFrame({"category": [v[0] for v in CODES.values()], "risk_level": [v[1] for v in CODES.values()]},
                        index=list(CODES))


def panel_of(prices):
    return make_panel(prices, meta())


def rows_at(prices, c):
    dp = H.DriftPanel(panel_of(prices))
    cals = {h: H.Calibrator(dp, h) for h in H.HORIZONS}
    return pd.DataFrame(H.forecast_rows(dp, cals, c, SOURCE_LIVE, set())).set_index(["fund_code", "horizon"]).sort_index()


# --- sızıntı ----------------------------------------------------------------------------------------

def test_no_leakage_future_prices_do_not_change_forecast():
    prices = make_prices()
    c = 330
    before = rows_at(prices, c)
    bad = prices.copy()
    bad.iloc[c + 1:] *= np.random.default_rng(9).uniform(0.2, 5, size=bad.iloc[c + 1:].shape)
    bad.iloc[c + 1] = prices.iloc[c - 1]  # t+1'de t-1'e dönüş: t gününü "tek günlük hata" gibi gösterir
    after = rows_at(bad, c)
    cols = ["base_price", "pred_price", "lo_price", "hi_price", "calib_n", "risk_group", "target_date"]
    pd.testing.assert_frame_equal(before[cols], after[cols])


def test_calibration_uses_only_errors_realized_before_forecast_day():
    dp = H.DriftPanel(panel_of(make_prices()))
    h, c = 5, 330
    cal = H.Calibrator(dp, h)
    r = dp.resid(h)
    # elle: başlangıç satırı + h < c olan hatalar (hedef günü c'den önce)
    cols = dp.groups == "5-7"
    manual = r[: c - h, cols]
    manual = manual[~np.isnan(manual)]
    assert len(manual) >= H.MIN_N
    q10, q90, n = cal.at(c)["5-7"]
    assert n == len(manual) and (q10, q90) == pytest.approx(tuple(np.quantile(manual, INTERVAL)))
    # c gününde hedefi c'ye denk gelen hata (satır c - h) dahil değil
    assert len(cal.known("5-7", c)) == len(cal.known("5-7", c - 1)) + int((~np.isnan(r[c - h - 1, cols])).sum())


def test_vectorized_drift_matches_features_at():
    p = panel_of(make_prices())
    dp = H.DriftPanel(p)
    for c in [YEAR, 300, 419]:
        f = features_at(p, p.prices.index[c])
        got = pd.Series(dp.ret12[c], index=dp.codes).dropna()
        assert set(got.index) == set(f.index)
        drift21 = (1 + got) ** (21 / YEAR) - 1
        assert np.allclose(drift21[f.index], f["drift"])


# --- takvim -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("start,n,expected", [
    (date(2026, 11, 13), 1, date(2026, 11, 16)),  # cuma -> pazartesi
    (date(2026, 10, 28), 1, date(2026, 10, 30)),  # 29 Ekim Cumhuriyet Bayramı atlanır
    (date(2026, 5, 25), 1, date(2026, 5, 26)),  # Kurban Bayramı arifesi (yarım gün) işlem günü
    (date(2026, 5, 25), 2, date(2026, 6, 1)),  # bayram (27-30 Mayıs) + hafta sonu
    (date(2026, 12, 31), 1, date(2027, 1, 4)),  # yılbaşı (cuma) + hafta sonu
    (date(2026, 3, 19), 1, date(2026, 3, 23)),  # Ramazan Bayramı 20-22 Mart
    (date(2026, 10, 22), 21, date(2026, 11, 23)),  # 21 işlem günü, arada 29 Ekim
])
def test_add_trading_days_skips_weekends_and_holidays(start, n, expected):
    assert add_trading_days(start, n) == expected


def test_is_trading_day():
    assert is_trading_day(date(2026, 11, 13)) and not is_trading_day(date(2026, 11, 14))
    assert not is_trading_day(date(2026, 4, 23)) and not is_trading_day(date(2026, 7, 15))


def test_target_dates_use_data_then_calendar():
    # verideki günler önce: 2 Kasım beklenmedik şekilde kapalıymış gibi (veride yok)
    known = [date(2026, 10, 30), date(2026, 11, 3)]
    t = target_dates(date(2026, 10, 28), 4, known)
    assert t == [date(2026, 10, 30), date(2026, 11, 3), date(2026, 11, 4), date(2026, 11, 5)]


# --- gerçekleşen ve aralık içi/dışı ----------------------------------------------------------------

def test_realize_in_band_boundaries_and_pending():
    market = pd.DatetimeIndex(["2026-11-10", "2026-11-11", "2026-11-12"])
    df = pd.DataFrame({
        "fund_code": ["A"] * 5, "as_of": [date(2026, 11, 10)] * 4 + [date(2026, 11, 12)],
        "horizon": [1, 2, 2, 2, 1], "pred_price": [10.0, 10.0, 10.0, 10.0, 10.0],
        "lo_price": [9.0, 10.5, 9.0, 9.0, 9.0], "hi_price": [11.0, 11.0, 11.0, 10.0, 11.0]})
    prices = {pd.Timestamp("2026-11-11"): 9.0, pd.Timestamp("2026-11-12"): 10.5}
    r = H.realize(df, market, lambda codes, dates: np.array([prices[pd.Timestamp(d)] for d in dates]))
    assert list(r["realized_price"][:4]) == [9.0, 10.5, 10.5, 10.5]
    assert list(r["in_band"]) == [True, True, True, False, None]  # alt sınırda içeride; üstte dışarıda; bekleniyor
    assert r["error_tl"][0] == pytest.approx(-1.0) and r["error_pct"][1] == pytest.approx(0.05)
    assert pd.isna(r["realized_date"][4]) and np.isnan(r["realized_price"][4])
    s = {x["horizon"]: x for x in H.score(r, ["horizon"])}
    assert s[2]["n"] == 3 and s[2]["coverage"] == pytest.approx(2 / 3) and s[1]["n"] == 1


def test_realized_date_is_hth_trading_day_in_data():
    """Takvimde işlem günü olan ama veride olmayan gün (beklenmedik kapanış) atlanır."""
    market = pd.DatetimeIndex(["2026-10-28", "2026-10-30", "2026-11-03"])  # 2 Kasım yok
    df = pd.DataFrame({"fund_code": ["A"], "as_of": [date(2026, 10, 28)], "horizon": [2], "pred_price": [1.0],
                       "lo_price": [0.9], "hi_price": [1.1]})
    r = H.realize(df, market, lambda c, d: np.array([1.0]))
    assert r["realized_date"][0] == pd.Timestamp("2026-11-03")


# --- ufka göre ayrı kalibrasyon ---------------------------------------------------------------------

def test_each_horizon_calibrated_separately():
    dp = H.DriftPanel(panel_of(make_prices(n=600)))
    c = 599
    widths = {}
    for h in H.HORIZONS:
        q = H.Calibrator(dp, h).at(c)["5-7"]
        r = dp.resid(h)[: c - h, dp.groups == "5-7"]
        r = r[~np.isnan(r)]
        assert q[2] == len(r) and q[0] == pytest.approx(np.quantile(r, INTERVAL[0]))
        widths[h] = q[1] - q[0]
    assert widths[1] < widths[5] < widths[10] < widths[21]  # rastgele yürüyüşte aralık ufukla genişler
    # her ufkun kendi aralığı: 21 günlük aralık 1 günlüğe uygulanmıyor
    rows = rows_at(make_prices(n=600), c).loc["HS1"]
    band = (rows["hi_price"] - rows["lo_price"]) / rows["base_price"]
    assert band[1] < band[21] and band[1] == pytest.approx(widths[1])


def test_small_group_falls_back_to_all_groups():
    dp = H.DriftPanel(panel_of(make_prices()))
    c = 330
    # "bilinmiyor" grubunda tek fon var: 50 hatayı ancak ~50 gün sonra doldurur; erken bir günde tümüne düşer
    early = YEAR + 20
    cal = H.Calibrator(dp, 1)
    assert len(cal.known("bilinmiyor", early)) < H.MIN_N
    assert cal.at(early)["bilinmiyor"][2] == len(cal.known(H.ALL, early))
    assert cal.at(c)["bilinmiyor"][2] == len(cal.known("bilinmiyor", c))


def test_evaluate_reports_every_horizon_and_group():
    dp = H.DriftPanel(panel_of(make_prices(n=600)))
    ev = H.evaluate(dp, dp.dates[450], dp.dates[-1])
    hs = {(r["horizon"], r["group"]): r for r in ev["rows"]}
    assert {h for h, _ in hs} == set(H.HORIZONS) and (1, H.ALL) in hs
    assert all(0 <= r["coverage"] <= 1 and r["mae_pct"] >= 0 for r in ev["rows"])
    assert hs[(21, H.ALL)]["mae_pct"] > hs[(1, H.ALL)]["mae_pct"]
    assert hs[(1, H.ALL)]["n"] > hs[(21, H.ALL)]["n"]  # son 20 günün 21 günlük hedefi henüz gelmedi


# --- kayıt: canlı ve geriye dönük -------------------------------------------------------------------

@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        prices = make_prices()
        for code, (cat, risk, _, _) in CODES.items():
            s.add(Fund(code=code, name=code, category=cat, risk_level=risk,
                       status="islem_kapali" if code == "BR2" else "aktif"))
            s.add_all(Price(fund_code=code, date=d.date(), price=float(v)) for d, v in prices[code].items())
        s.commit()
        yield s


def test_store_live_and_backfill_never_overwrite(db):
    dp = H.DriftPanel(panel_of(make_prices()))
    # elle eklenmiş bir canlı gün (geriye dönük pencerenin içinde): üzerine yazılmamalı
    c = len(dp.dates) - 10
    live_rows = H.forecast_rows(dp, {h: H.Calibrator(dp, h) for h in H.HORIZONS}, c, SOURCE_LIVE, set())
    for r in live_rows:
        r["pred_price"] = 123.0  # işaret
    from sqlalchemy import insert
    db.execute(insert(ForecastDay), live_rows)
    db.commit()
    res = H.store(db, dp, backfill_days=15)
    assert res["backfill_days"] == 14  # 15 günden biri canlı
    d = dp.dates[c].date()
    assert set(db.scalars(select(ForecastDay.source).where(ForecastDay.as_of == d))) == {SOURCE_LIVE}
    assert set(db.scalars(select(ForecastDay.pred_price).where(ForecastDay.as_of == d))) == {123.0}
    assert "BR2" not in set(db.scalars(select(ForecastDay.fund_code).where(ForecastDay.source == SOURCE_BACKFILL)))  # kapalı fon
    last = dp.dates[-1].date()
    assert set(db.scalars(select(ForecastDay.source).where(ForecastDay.as_of == last))) == {SOURCE_LIVE}
    n = db.scalar(select(func.count()).select_from(ForecastDay))
    assert H.store(db, dp, backfill_days=15) == {"live": 0, "backfill": 0, "backfill_days": 0}
    assert db.scalar(select(func.count()).select_from(ForecastDay)) == n
    # sonraki gün veri gelince: önceki "son gün" canlı kalır, yeni gün canlı eklenir
    dp2 = H.DriftPanel(panel_of(make_prices(n=421)))
    assert H.store(db, dp2, backfill_days=15)["live"] > 0
    assert db.scalar(select(func.count()).select_from(ForecastDay).where(
        ForecastDay.as_of == last, ForecastDay.source == SOURCE_BACKFILL)) == 0


def test_fund_scorecard_separates_sources_and_pending(db):
    dp = H.DriftPanel(panel_of(make_prices()))
    H.store(db, dp, backfill_days=40)
    card = H.fund_scorecard(db, "HS1")
    assert len(card["days"]) == 30 and card["days"][0]["source"] == SOURCE_LIVE
    sel = card["selected"]
    full = next(d for d in card["days"] if d["realized"] == d["horizons"] == 21)
    assert sel["source"] == SOURCE_BACKFILL and sel["as_of"] == full["as_of"]  # varsayılan: tamamı gerçekleşmiş en yeni
    rows = H.fund_scorecard(db, "HS1", card["days"][1]["as_of"])["selected"]["rows"]
    assert rows[0]["realized_price"] is not None and rows[0]["in_band"] in (True, False)
    assert rows[1]["realized_price"] is None and rows[1]["in_band"] is None  # 1 günlük olan geldi, gerisi bekleniyor
    assert {s["source"] for s in card["summary"]} == {SOURCE_BACKFILL}  # canlı tahminlerin hiçbiri gerçekleşmedi
    s1 = next(s for s in card["summary"] if s["horizon"] == 1)
    assert s1["label"] == "1 gün" and s1["n"] == 40


def test_migrate_legacy_forecasts_table(db):
    db.execute(text("CREATE TABLE forecasts (id INTEGER PRIMARY KEY, fund_code VARCHAR(10), as_of DATE, horizon_days INTEGER, "
                    "method VARCHAR(20), pred_return FLOAT, lo FLOAT, hi FLOAT, risk_group VARCHAR(12), coverage FLOAT, "
                    "created_at DATETIME)"))
    d = db.scalars(select(Price.date).order_by(Price.date.desc())).first()
    db.execute(text("INSERT INTO forecasts (fund_code, as_of, horizon_days, method, pred_return, lo, hi, risk_group, coverage, created_at) "
                    "VALUES ('HS1', :d, 21, 'drift', 0.02, -0.05, 0.08, '5-7', 0.75, '2026-10-22 21:37:32')"), {"d": d})
    db.commit()
    assert migrate_legacy(db) == 1
    row = db.scalars(select(ForecastDay)).one()
    base = db.scalar(select(Price.price).where(Price.fund_code == "HS1", Price.date == d))
    assert row.source == SOURCE_LIVE and row.horizon == 21 and row.pred_price == pytest.approx(base * 1.02)
    assert (row.method, row.method_version) == ("drift-konformal", "v0")  # eski yöntem kendi sürümüyle
    assert row.lo_price == pytest.approx(base * 0.95) and row.target_date == add_trading_days(d, 21)
    assert migrate_legacy(db) == 0  # tablo kaldırıldı


def test_method_version_change_keeps_old_records(db, monkeypatch):
    dp = H.DriftPanel(panel_of(make_prices()))
    H.store(db, dp, backfill_days=5)
    before = {(r.fund_code, r.as_of, r.horizon, r.source): (r.method_version, r.pred_price, r.lo_price)
              for r in db.scalars(select(ForecastDay))}
    assert {v for v, _, _ in before.values()} == {"v1"}
    # yöntem değişti (v2): dolu günler yeniden hesaplanmaz, eski kayıtlar v1 kalır
    monkeypatch.setattr(H, "METHOD_VERSION", "v2")
    assert H.store(db, dp, backfill_days=5) == {"live": 0, "backfill": 0, "backfill_days": 0}
    after = {(r.fund_code, r.as_of, r.horizon, r.source): (r.method_version, r.pred_price, r.lo_price)
             for r in db.scalars(select(ForecastDay))}
    assert after == before
    # yeni gün yeni sürümle
    dp2 = H.DriftPanel(panel_of(make_prices(n=421)))
    H.store(db, dp2, backfill_days=5)
    new_day = dp2.dates[-1].date()
    assert set(db.scalars(select(ForecastDay.method_version).where(ForecastDay.as_of == new_day))) == {"v2"}
    # özetler sürüme göre ayrı
    summ = H.summarize_all(db, dp2)
    assert {r["method_version"] for r in summ["rows"]} <= {"v1", "v2"} and "v1" in summ["versions"]
    card = H.fund_scorecard(db, "HS1")
    assert card["days"][0]["method_version"] == "v2" and card["days"][1]["method_version"] == "v1"
