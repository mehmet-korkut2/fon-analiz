"""TEFAS işlem günü takvimi: hafta sonu ve Türkiye resmî tatilleri (dinî bayramlar dahil) hariç her gün.

Arife günleri (yarım gün) işlem günüdür; TEFAS o günlerde de fiyat yayınlıyor. Takvim 14.10.2021 -
22.10.2026 arasındaki bütün fiyat günleriyle birebir karşılaştırıldı: fark yok (docs/ml_tahmin.md).

Tahminin hedef günü iki yoldan bulunur (`target_dates`):
- Fiyat verisinde t'den sonra en az h işlem günü varsa: verideki h'inci işlem günü (gerçekleşen).
- Yoksa: verideki son günden sonra takvimle ileri sayılır (henüz gelmemiş günler).
Böylece beklenmedik bir kapanış olursa (takvimde olmayan) gerçekleşen tarih veriden düzelir.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

import holidays


@lru_cache(maxsize=32)
def _holidays(year: int) -> frozenset[date]:
    return frozenset(holidays.Turkey(years=year).keys())


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in _holidays(d.year)


def add_trading_days(d: date, n: int) -> date:
    """d'den sonraki n'inci işlem günü (d'nin kendisi sayılmaz)."""
    for _ in range(n):
        d += timedelta(days=1)
        while not is_trading_day(d):
            d += timedelta(days=1)
    return d


def target_dates(as_of: date, horizon: int, known_days: list[date]) -> list[date]:
    """as_of'tan sonraki 1..horizon'uncu işlem günleri. `known_days`: fiyat verisindeki işlem günleri
    (artan sırada). Veride olanlar veriden, sonrası takvimden."""
    after = [d for d in known_days if d > as_of][:horizon]
    out = list(after)
    last = after[-1] if after else as_of
    while len(out) < horizon:
        last = add_trading_days(last, 1)
        out.append(last)
    return out
