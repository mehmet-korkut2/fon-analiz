from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.services.technical import moving_averages, range_52w, summarize, technical


def series(values, start="2025-01-01"):
    return pd.Series(values, index=[d.date() for d in pd.bdate_range(start, periods=len(values))], dtype=float)


def test_moving_average_needs_full_window():
    s = series(np.arange(1, 251))
    ma = moving_averages(s)
    assert ma["ma50"].iloc[:49].isna().all() and ma["ma50"].iloc[49] == pytest.approx(25.5)
    assert ma["ma200"].iloc[:199].isna().all() and ma["ma200"].iloc[199] == pytest.approx(100.5)
    # son gün: 201..250 ve 51..250 ortalaması
    assert ma["ma50"].iloc[-1] == pytest.approx(225.5)
    assert ma["ma200"].iloc[-1] == pytest.approx(150.5)


def test_trend_above_and_below_200_day_average():
    up = summarize(series(np.linspace(1, 2, 300)))
    assert up["trend"] == "ustunde" and up["price"] > up["ma200"]
    down = summarize(series(np.linspace(2, 1, 300)))
    assert down["trend"] == "altinda" and down["price"] < down["ma200"]


def test_trend_empty_when_history_shorter_than_200_days():
    out = summarize(series(np.linspace(1, 2, 120)))
    assert out["ma200"] is None and out["trend"] is None
    assert out["ma50"] is not None


def test_range_52w_uses_only_last_year():
    # ilk yılda 10'a çıkan bir zirve var; 52 haftalık aralığa girmemeli
    values = np.r_[np.full(50, 10.0), np.linspace(2, 4, 300)]
    s = series(values, "2024-01-01")
    r = range_52w(s)
    assert r["high"] == pytest.approx(4.0) and r["full"] is True
    assert r["high_date"] == s.index[-1]
    assert r["since"] > s.index[-1] - timedelta(days=364)
    assert r["position"] == pytest.approx(1.0)


def test_range_52w_position_and_young_fund():
    s = series([2.0, 4.0, 1.0, 3.0])
    r = range_52w(s)
    assert (r["high"], r["low"]) == (4.0, 1.0)
    assert r["position"] == pytest.approx(2 / 3)
    assert r["full"] is False  # 52 haftadan kısa geçmiş
    assert range_52w(series([5.0, 5.0]))["position"] is None  # düz fiyat: konum tanımsız


def test_one_day_glitch_ignored():
    values = np.linspace(1, 1.1, 260)
    values[200] = 5.0  # tek günlük hatalı fiyat, ertesi gün geri dönüyor
    out = technical(list(zip(series(values).index, values)), since=date(2025, 1, 1))
    assert out["summary"]["range_52w"]["high"] < 1.2
    assert all(p["ma50"] is None or p["ma50"] < 1.2 for p in out["series"])


def test_series_starts_at_since_with_warm_averages():
    s = series(np.linspace(1, 2, 400))
    since = s.index[300]
    out = technical(list(s.items()), since)
    assert out["series"][0]["date"] == since and len(out["series"]) == 100
    assert out["series"][0]["ma200"] is not None  # ısınma verisi dönemden önce
    assert technical([], since) is None
