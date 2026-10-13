import numpy as np
import pandas as pd
import pytest

from app.services.metrics import MIN_VOL_FOR_SHARPE, compute_fund_metrics, max_drawdown, total_return


def test_total_return():
    assert total_return(pd.Series([100, 110, 120])) == pytest.approx(0.20)


def test_max_drawdown():
    assert max_drawdown(pd.Series([100, 120, 90, 130])) == pytest.approx(-0.25)


def business_series(start, end, start_price, end_price):
    idx = pd.bdate_range(start, end)
    return pd.Series(np.linspace(start_price, end_price, len(idx)), index=idx)


def test_period_returns_on_linear_series():
    s = business_series("2024-10-01", "2026-10-09", 100, 200)
    m = compute_fund_metrics(s, risk_free_rate=0.0)
    assert m.as_of.isoformat() == "2026-10-09"
    assert m.last_price == pytest.approx(200)
    one_year_ago = s.loc[:"2025-10-09"].iloc[-1]
    assert m.ret_1y == pytest.approx(200 / one_year_ago - 1)
    ytd_base = s.loc[:"2025-12-31"].iloc[-1]
    assert m.ret_ytd == pytest.approx(200 / ytd_base - 1)
    assert m.max_drawdown_1y == pytest.approx(0)  # sürekli yükselen seri
    assert m.daily_change > 0


def test_three_year_return():
    s = business_series("2023-01-02", "2026-10-09", 100, 400)
    m = compute_fund_metrics(s)
    three_years_ago = s.loc[:"2023-10-09"].iloc[-1]
    assert m.ret_3y == pytest.approx(400 / three_years_ago - 1)
    # 2 yıllık fonun 3 yıllık getirisi yok
    assert compute_fund_metrics(business_series("2024-10-01", "2026-10-09", 100, 200)).ret_3y is None


def test_no_sharpe_below_volatility_floor():
    # para piyasası benzeri fon: fiyat düzgün artıyor, pazartesileri hafta sonu faizi eklenmiş
    idx = pd.bdate_range("2025-09-01", "2026-10-09")
    daily = np.where(idx.dayofweek == 0, 0.0039, 0.0013)
    s = pd.Series(100 * np.cumprod(1 + daily), index=idx)
    m = compute_fund_metrics(s, risk_free_rate=0.30)
    assert 0 < m.volatility_1y < MIN_VOL_FOR_SHARPE
    assert m.ret_1y > 0.30 and m.sharpe_1y is None  # getiri risksizden yüksek ama Sharpe anlamsız


def test_young_fund_has_no_long_period_returns():
    s = business_series("2026-08-01", "2026-10-09", 1, 1.1)  # 2 aylık fon
    m = compute_fund_metrics(s, risk_free_rate=0.3)
    assert m.ret_1m is not None
    assert m.ret_3m is None and m.ret_1y is None and m.ret_ytd is None and m.ret_3y is None
    assert m.sharpe_1y is None


def test_sharpe_and_volatility():
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2025-09-01", "2026-10-09")
    s = pd.Series(100 * np.cumprod(1 + rng.normal(0.001, 0.01, len(idx))), index=idx)
    m = compute_fund_metrics(s, risk_free_rate=0.10)
    window = s.loc[pd.Timestamp("2026-10-09") - pd.DateOffset(years=1):]
    expected_vol = window.pct_change().dropna().std() * np.sqrt(252)
    assert m.volatility_1y == pytest.approx(expected_vol)
    assert m.sharpe_1y == pytest.approx((m.ret_1y - 0.10) / expected_vol)
    assert m.max_drawdown_1y < 0


def test_empty_and_single_point():
    assert compute_fund_metrics(pd.Series(dtype=float)) is None
    m = compute_fund_metrics(pd.Series([1.5], index=pd.to_datetime(["2026-10-09"])))
    assert m.last_price == 1.5 and m.daily_change is None and m.volatility_1y is None
