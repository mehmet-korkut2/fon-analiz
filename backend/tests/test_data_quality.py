from datetime import date, timedelta

import pandas as pd

from app.services.data_quality import find_jumps, summarize


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
