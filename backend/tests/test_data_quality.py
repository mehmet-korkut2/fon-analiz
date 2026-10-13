from datetime import date, timedelta

import pandas as pd

from app.services.data_quality import drop_one_day_glitches, find_jumps, summarize
from app.services.metrics import compute_fund_metrics
from app.services.metrics_job import fund_series


def series(code, prices):
    start = date(2026, 1, 5)
    return pd.DataFrame({"code": code, "date": [start + timedelta(days=i) for i in range(len(prices))], "price": prices})


def test_finds_one_day_glitch_and_persistent_jump():
    prices = pd.concat([
        series("HTA", [1.0, 1.01, 10.1, 1.02, 1.03]),  # tek günlük hatalı fiyat (x10, ertesi gün geri)
        series("BOL", [100.0, 101.0, 1.01, 1.02, 1.03]),  # kalıcı düşüş (ör. pay bölünmesi)
        series("NOR", [1.0, 1.1, 1.25, 1.2, 1.3]),  # büyük ama eşik altı hareketler
    ])
    j = find_jumps(prices)
    # HTA'da iki sıçrama var (çıkış ve dönüş); ikisi de aynı tek günlük hataya ait
    assert list(j["code"]) == ["BOL", "HTA", "HTA"]
    hta = j[j["code"] == "HTA"]
    assert list(hta["date"]) == [date(2026, 1, 7), date(2026, 1, 8)] and hta["change"].iloc[0] > 8
    assert hta["reverted"].tolist() == [True, True]
    bol = j[j["code"] == "BOL"].iloc[0]
    assert bol["change"] < -0.9 and bool(bol["reverted"]) is False
    assert summarize(j, 3) == {"funds_scanned": 3, "funds_with_jumps": 2, "jumps": 3, "reverted": 2, "persistent": 1}


def test_threshold_and_empty():
    prices = series("NOR", [1.0, 1.1, 1.25, 1.2, 1.3])
    assert find_jumps(prices).empty
    assert len(find_jumps(prices, threshold=0.12)) == 1
    assert find_jumps(prices.iloc[0:0]).empty


def test_drop_one_day_glitches_keeps_real_moves():
    s = pd.Series([1.0, 1.01, 10.1, 1.02, 1.03, 0.5, 0.51])  # 2. gün hata, 5. gün kalıcı düşüş
    cleaned = drop_one_day_glitches(s)
    assert list(cleaned.index) == [0, 1, 3, 4, 5, 6]
    # son gün ertesi günü olmadığı için hiçbir zaman çıkarılmaz
    assert list(drop_one_day_glitches(pd.Series([1.0, 1.0, 5.0])).index) == [0, 1, 2]


def test_metrics_ignore_one_day_glitch():
    idx = pd.bdate_range("2025-01-01", "2026-10-09")
    clean = pd.Series([1.0 + 0.001 * i for i in range(len(idx))], index=idx)
    glitchy = clean.copy()
    glitchy.iloc[-30] *= 3  # YCK/BFS gibi tek günlük sıçrama
    g = pd.DataFrame({"date": idx, "price": glitchy.values})
    with_glitch = compute_fund_metrics(glitchy, risk_free_rate=0.0)
    ignored = compute_fund_metrics(fund_series(g), risk_free_rate=0.0)
    expected = compute_fund_metrics(clean.drop(clean.index[-30]), risk_free_rate=0.0)
    assert with_glitch.volatility_1y > 5 * expected.volatility_1y
    assert ignored.volatility_1y == expected.volatility_1y
    assert ignored.max_drawdown_1y == expected.max_drawdown_1y == 0
    assert ignored.data_points == with_glitch.data_points - 1  # veri silinmedi, sadece hesapta yok sayıldı
