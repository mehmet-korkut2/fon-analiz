"""Fiyat serilerinde şüpheli sıçramaları bulur.

Bir fonun fiyatı bir işlem gününden diğerine eşikten (varsayılan %30) fazla değiştiyse
şüpheli sayılır. Fonlarda bu kadar büyük günlük hareket nadirdir; çoğu zaman veri hatası,
pay bölünmesi / birleşmesi ya da fiyat düzeltmesidir.

Her sıçrama için "geri döndü" bilgisi de verilir: ertesi gün fiyat sıçrama öncesine
yakın bir düzeye dönüyorsa (kalan fark, sıçramanın yarısından azsa) bu büyük ihtimalle
tek günlük hatalı bir fiyattır; hem sıçrama hem ertesi günkü dönüş bu şekilde işaretlenir.
Kalıcı sıçramalar gerçek bir olay olabilir, tek tek bakılmalı.
"""
from __future__ import annotations

import pandas as pd

DEFAULT_THRESHOLD = 0.30

COLUMNS = ["code", "prev_date", "prev_price", "date", "price", "change", "next_price", "reverted"]


def find_jumps(prices: pd.DataFrame, threshold: float = DEFAULT_THRESHOLD) -> pd.DataFrame:
    """`prices`: code, date, price sütunlu uzun tablo. Sıçramaları COLUMNS sütunlarıyla döndürür."""
    if prices.empty:
        return pd.DataFrame(columns=COLUMNS)
    df = prices[prices["price"] > 0].sort_values(["code", "date"]).copy()
    g = df.groupby("code", sort=False)
    df["prev_date"] = g["date"].shift(1)
    df["prev_price"] = g["price"].shift(1)
    df["next_price"] = g["price"].shift(-1)
    df["change"] = df["price"] / df["prev_price"] - 1

    jumps = df[df["change"].abs() > threshold].copy()
    after = (jumps["next_price"] / jumps["prev_price"] - 1).abs()
    jumps["reverted"] = jumps["next_price"].notna() & (after < jumps["change"].abs() / 2)
    # Tek günlük hatanın dönüş ayağı da (ertesi günkü ters sıçrama) aynı hataya aittir
    glitch_days = set(zip(jumps.loc[jumps["reverted"], "code"], jumps.loc[jumps["reverted"], "date"]))
    jumps.loc[[(c, d) in glitch_days for c, d in zip(jumps["code"], jumps["prev_date"])], "reverted"] = True
    return jumps[COLUMNS].reset_index(drop=True)


def summarize(jumps: pd.DataFrame, funds_scanned: int) -> dict:
    return {
        "funds_scanned": funds_scanned,
        "funds_with_jumps": int(jumps["code"].nunique()),
        "jumps": len(jumps),
        "reverted": int(jumps["reverted"].sum()),
        "persistent": int((~jumps["reverted"].astype(bool)).sum()),
    }
