"""Enflasyon (TÜFE) ve reel getiri.

Veri: TÜİK'in Tüketici Fiyat Endeksi genel endeksi (2025=100), TCMB EVDS web servisinden (EVDS 3). Seri kodu
EVDS meta veri servisinden doğrulandı (13.11.2026): TP.TUKFIY2025.GENEL, veri grubu bie_tukfiy2025, 01.2005'ten
başlar. TÜİK Ocak 2026'da baz yılını 2003=100'den 2025=100'e geçirdi; yeni seri 2005'e kadar zincirlenmiş olarak
yayımlandığı için eski seriyle (TP.GENENDEKS.T1) zincirleme gerekmedi. İki serinin aylık değişimleri en çok
0,0066 puan farklı (yuvarlama).

API anahtarı (settings.evds_api_key) yalnızca HTTP isteğinin "key" başlığında kullanılır; hiçbir hata mesajına,
günlüğe ya da yanıta yazılmaz. Anahtar yoksa ya da internet yoksa son bilinen veriyle çalışılır; hiç veri yoksa
reel getiri "enflasyon verisi yok" olarak gösterilir.

Reel getiri = (1 + nominal getiri) / (1 + enflasyon) - 1, yalnızca 1, 3, 6, 12 ve 36 aylık dönemlerde.
Dönem sonu, açıklanmış son TÜFE ayının son günüdür (ör. Ekim 2026 TÜFE'si açıklandıysa 31.10.2026); dönem başı
k ay önceki ayın son günü. Fon fiyatı o gün ya da öncesindeki son fiyattır (en çok STALE_AFTER_DAYS gün eski).
Enflasyon = TÜFE(son ay) / TÜFE(k ay önce) - 1. TÜFE aylık ortalama fiyat düzeyidir, fon fiyatı ay sonu
değeridir; bu yaygın bir yaklaşımdır (rapor 3.8). Eksik TÜFE ayı ya da eksik fiyat varsa sonuç boştur.
"""
from __future__ import annotations

import logging
from calendar import monthrange
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd
import requests
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CpiMonth, Fund, Price
from app.services.data_quality import drop_one_day_glitches
from app.services.fund_status import STATUS_ACTIVE

log = logging.getLogger(__name__)

SERIES = "TP.TUKFIY2025.GENEL"
BASE_YEAR = "2025=100"
EVDS_URL = "https://evds3.tcmb.gov.tr/igmevdsms-dis/"
FIRST_MONTH = date(2005, 1, 1)
PERIODS = [(1, "1 ay"), (3, "3 ay"), (6, "6 ay"), (12, "1 yıl"), (36, "3 yıl")]
STALE_AFTER_DAYS = 7  # metrics_job ile aynı
RELEASE_DAY = 3  # TÜİK TÜFE'yi genellikle sonraki ayın 3'ünde açıklar (hafta sonu/tatilde kayar)
SOURCE_NOTE = "TÜFE (2025=100): TÜİK. TCMB EVDS aracılığıyla alınmıştır."
NO_DATA = "Enflasyon verisi yok."
TIMEOUT = 30


TR_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def month_label(d: date) -> str:
    return f"{TR_MONTHS[d.month - 1]} {d.year}"


class InflationError(Exception):
    """EVDS'ten veri alınamadı. Mesaj anahtarı içermez."""


# --- EVDS -----------------------------------------------------------------------------------------

def parse_evds(payload: dict, series: str = SERIES) -> list[tuple[date, float]]:
    """EVDS JSON yanıtı -> [(ayın ilk günü, endeks)]. Tarih "2005-1" biçimindedir; boş değerler atlanır."""
    field = series.replace(".", "_")
    out = []
    for item in payload.get("items") or []:
        raw, value = item.get("Tarih"), item.get(field)
        if not raw or value in (None, ""):
            continue
        try:
            y, m = (int(x) for x in str(raw).split("-")[:2])
            out.append((date(y, m, 1), float(value)))
        except (ValueError, TypeError):
            continue
    return sorted(out)


def fetch(start: date, key: str, timeout: int = TIMEOUT) -> list[tuple[date, float]]:
    """EVDS'ten aylık TÜFE (düzey). Anahtar yalnızca başlıkta; hata mesajında yer almaz."""
    url = (f"{EVDS_URL}series={SERIES}&startDate={start:%d-%m-%Y}&endDate=01-01-2999"
           "&type=json&frequency=5&formulas=0")
    try:
        r = requests.get(url, headers={"key": key}, timeout=timeout)
    except requests.RequestException as e:
        raise InflationError(f"EVDS'e ulaşılamadı ({type(e).__name__}).") from None
    if r.status_code == 403:
        raise InflationError("EVDS isteği reddetti (HTTP 403): API anahtarı geçersiz ya da tanımsız.")
    if r.status_code != 200:
        raise InflationError(f"EVDS yanıtı: HTTP {r.status_code}.")
    try:
        return parse_evds(r.json())
    except ValueError:
        raise InflationError("EVDS yanıtı okunamadı.") from None


# --- güncelleme -----------------------------------------------------------------------------------

def add_months(d: date, k: int) -> date:
    y, m = divmod(d.year * 12 + d.month - 1 + k, 12)
    return date(y, m + 1, 1)


def expected_month(today: date) -> date:
    """Bugün itibarıyla açıklanmış olması beklenen son TÜFE ayı (ayın 3'ünden önce bir önceki aydan önceki ay)."""
    first = today.replace(day=1)
    return add_months(first, -1 if today.day >= RELEASE_DAY else -2)


def latest_month(db: Session) -> date | None:
    return db.scalar(select(func.max(CpiMonth.month)))


def store(db: Session, rows: list[tuple[date, float]]) -> int:
    """Ayları ekler ya da günceller; eklenen yeni ay sayısını döner."""
    now = datetime.now()
    existing = {r.month: r for r in db.scalars(select(CpiMonth))}
    added = 0
    for m, v in rows:
        r = existing.get(m)
        if r is None:
            db.add(CpiMonth(month=m, value=v, series_code=SERIES, fetched_at=now))
            added += 1
        elif r.value != v:
            r.value, r.fetched_at = v, now
    db.commit()
    return added


def update(db: Session, key: str | None = None, online: Callable[[], bool] | None = None, today: date | None = None,
           fetcher: Callable[[date, str], list] = fetch, force: bool = False) -> dict:
    """Gece işi ve açılış: beklenen ay yoksa EVDS'ten çeker. Anahtar yoksa, internet yoksa ya da EVDS hata verirse
    hiçbir şey silinmez; son bilinen veriyle devam edilir. Dönen sözlükte anahtar yer almaz."""
    key = settings.evds_api_key if key is None else key
    today = today or date.today()
    last = latest_month(db)
    base = {"last_month": last.isoformat() if last else None}
    if not key or not key.strip():
        return {**base, "status": "anahtar_yok"}
    if not force and last is not None and last >= expected_month(today):
        return {**base, "status": "guncel"}
    if online is not None and not online():
        return {**base, "status": "offline"}
    start = FIRST_MONTH if last is None or force else add_months(last, -12)  # son yılı yeniden al (düzeltme olursa)
    try:
        rows = fetcher(start, key.strip())
    except InflationError as e:
        log.warning("TÜFE güncellenemedi: %s", e)
        return {**base, "status": "hata", "error": str(e)}
    added = store(db, rows)
    last = latest_month(db)
    result = {"status": "ok", "added": added, "last_month": last.isoformat() if last else None}
    log.info("TÜFE güncellendi: %s", result)
    return result


def status(db: Session) -> dict:
    last = latest_month(db)
    fetched = db.scalar(select(func.max(CpiMonth.fetched_at)))
    count = db.scalar(select(func.count()).select_from(CpiMonth))
    return {
        "available": last is not None, "last_month": last, "months": count, "fetched_at": fetched,
        "series": SERIES, "base_year": BASE_YEAR, "source_note": SOURCE_NOTE,
        "key_configured": bool(settings.evds_api_key and settings.evds_api_key.strip()),  # değer değil, yalnızca var/yok
        "expected_month": expected_month(date.today()),
    }


# --- hesap ----------------------------------------------------------------------------------------

def load_cpi(db: Session) -> pd.Series:
    rows = db.execute(select(CpiMonth.month, CpiMonth.value).order_by(CpiMonth.month)).all()
    return pd.Series({m: v for m, v in rows}, dtype=float)


def month_end(m: date) -> date:
    return m.replace(day=monthrange(m.year, m.month)[1])


def real_return(nominal: float | None, inflation: float | None) -> float | None:
    if nominal is None or inflation is None:
        return None
    return (1 + nominal) / (1 + inflation) - 1


def inflation_between(cpi: pd.Series, start_month: date, end_month: date) -> float | None:
    """TÜFE(son ay) / TÜFE(başlangıç ayı) - 1; ay eksikse None."""
    if start_month not in cpi.index or end_month not in cpi.index:
        return None
    return float(cpi[end_month] / cpi[start_month] - 1)


def price_at(prices: pd.Series, d: date, max_age: int = STALE_AFTER_DAYS) -> float | None:
    """d günü ya da öncesindeki son fiyat (en çok max_age gün eski); yoksa None. prices: tarih indeksli, sıralı."""
    upto = prices[prices.index <= pd.Timestamp(d)]
    if upto.empty or (pd.Timestamp(d) - upto.index[-1]).days > max_age:
        return None
    return float(upto.iloc[-1])


@dataclass
class PeriodReal:
    months: int
    label: str
    start: date  # dönem başı (k ay önceki ayın son günü)
    end: date  # dönem sonu (son TÜFE ayının son günü)
    nominal: float | None
    inflation: float | None
    real: float | None

    @property
    def beat(self) -> bool | None:
        return None if self.real is None else self.real > 0


def fund_real_returns(prices: pd.Series, cpi: pd.Series) -> list[PeriodReal]:
    """Bir fon için bütün dönemler. prices: tarih indeksli fiyat serisi (tek günlük hatalar çıkarılmış)."""
    if cpi.empty:
        return []
    last = cpi.index[-1]
    end = month_end(last)
    p_end = price_at(prices, end)
    out = []
    for k, label in PERIODS:
        sm = add_months(last, -k)
        start = month_end(sm)
        p_start = price_at(prices, start)
        nominal = p_end / p_start - 1 if p_end is not None and p_start is not None else None
        infl = inflation_between(cpi, sm, last)
        out.append(PeriodReal(k, label, start, end, nominal, infl, real_return(nominal, infl)))
    return out


def fund_prices(db: Session, code: str, since: date) -> pd.Series:
    rows = db.execute(select(Price.date, Price.price).where(Price.fund_code == code, Price.date >= since)
                      .order_by(Price.date)).all()
    if not rows:
        return pd.Series(dtype=float)
    s = pd.Series([p for _, p in rows], index=pd.to_datetime([d for d, _ in rows]), dtype=float)
    return drop_one_day_glitches(s)


def fund_real(db: Session, code: str) -> dict:
    """Fon detayı: bütün dönemler (API)."""
    cpi = load_cpi(db)
    if cpi.empty:
        return {"available": False, "message": NO_DATA}
    last = cpi.index[-1]
    since = month_end(add_months(last, -max(k for k, _ in PERIODS))) - timedelta(days=STALE_AFTER_DAYS + 7)
    periods = fund_real_returns(fund_prices(db, code, since), cpi)
    return {"available": True, "last_month": last, "end": month_end(last), "source_note": SOURCE_NOTE,
            "base_year": BASE_YEAR, "periods": periods}


def period_table(db: Session, months: int, cpi: pd.Series | None = None) -> tuple[pd.DataFrame, dict]:
    """Bütün fonların k aylık nominal getirisi, son TÜFE ayına hizalı. Hayatta kalma yanılgısına karşı, dönem
    başında fiyatı olan her fon yer alır: dönem içinde fiyatı kesilen (kapanan, işleme kapatılan) fonun dönem sonu
    değeri son fiyatıdır (exited=True). Dönen sözlük: ay, tarih ve enflasyon."""
    cpi = load_cpi(db) if cpi is None else cpi
    if cpi.empty:
        return pd.DataFrame(), {}
    last = cpi.index[-1]
    sm = add_months(last, -months)
    start, end = month_end(sm), month_end(last)
    infl = inflation_between(cpi, sm, last)
    meta = {"months": months, "start": start, "end": end, "last_month": last, "inflation": infl}
    if infl is None:
        return pd.DataFrame(), meta
    rows = db.execute(select(Price.fund_code, Price.date, Price.price).where(
        Price.date >= start - timedelta(days=STALE_AFTER_DAYS), Price.date <= end)).all()
    if not rows:
        return pd.DataFrame(), meta
    df = pd.DataFrame(rows, columns=["code", "date", "price"])
    df["date"] = pd.to_datetime(df["date"])
    funds = {f.code: f for f in db.scalars(select(Fund))}
    out = []
    for code, g in df.groupby("code"):
        s = drop_one_day_glitches(g.sort_values("date").set_index("date")["price"])
        p0 = price_at(s, start)
        if p0 is None:
            continue  # dönem başında fiyatı yok (henüz kurulmamış ya da çoktan kesilmiş)
        p1 = price_at(s, end)
        exited = p1 is None
        if exited:
            p1 = float(s.iloc[-1])  # dönem içinde fiyatı kesildi: son fiyatından çıkmış sayılır
        f = funds.get(code)
        nominal = p1 / p0 - 1
        out.append({"code": code, "category": (f.category if f else None) or "Bilinmiyor",
                    "status": (f.status if f else None) or STATUS_ACTIVE, "is_active": bool(f.is_active) if f else False,
                    "exited": exited, "nominal": nominal, "real": real_return(nominal, infl)})
    return pd.DataFrame(out), meta


def real_1y_by_fund(db: Session) -> tuple[dict[str, float], date | None]:
    """Metrik tablosu için: dönem sonunda fiyatı güncel olan fonların 1 yıllık reel getirisi."""
    df, meta = period_table(db, 12)
    if df.empty:
        return {}, meta.get("end")
    cur = df[~df["exited"]]
    return dict(zip(cur["code"], cur["real"])), meta["end"]


_summary_cache: dict = {}


def _summary_key(db: Session) -> tuple:
    return (db.scalar(select(func.max(Price.date))), latest_month(db), db.scalar(select(func.max(CpiMonth.fetched_at))),
            db.scalar(select(func.count()).select_from(Fund).where(Fund.status.is_not(None), Fund.status != STATUS_ACTIVE)),
            db.scalar(select(func.count()).select_from(Fund)))


def beat_summary_cached(db: Session) -> dict:
    """beat_summary ~3 sn sürer (bütün fonların 1 yıllık fiyatları); sonuç yalnızca son fiyat günü, TÜFE ya da fon
    durumları değişince yeniden hesaplanır. Gece metrik hesabından ve açılıştan sonra ısıtılır."""
    key = _summary_key(db)
    if _summary_cache.get("key") != key:
        _summary_cache.update(key=key, value=beat_summary(db))
    return _summary_cache["value"]


def beat_summary(db: Session) -> dict:
    """Ana sayfa: son 12 ayda enflasyonu yenen fonların payı, kategoriye göre. İki evren:
    - tum: dönem başında fiyatı olan her fon (dönem içinde kapanan / SPK kararıyla işleme kapatılan dahil; hayatta
      kalma yanılgısı yok). Ekranda gösterilen bu.
    - aktif: yalnızca bugün işlem gören ve verisi güncel fonlar (karşılaştırma için)."""
    df, meta = period_table(db, 12)
    if df.empty:
        return {"available": False, "message": NO_DATA, **meta}
    active = df[(~df["exited"]) & (df["status"] == STATUS_ACTIVE) & df["is_active"]]

    def share(d: pd.DataFrame) -> dict:
        return {"n": int(len(d)), "beat": int((d["real"] > 0).sum()),
                "share": float((d["real"] > 0).mean()) if len(d) else None}

    cats = []
    for cat, g in df.groupby("category"):
        a = active[active["category"] == cat]
        cats.append({"category": cat, "all": share(g), "active": share(a)})
    cats.sort(key=lambda c: -c["all"]["n"])
    return {"available": True, **meta, "source_note": SOURCE_NOTE, "all": share(df), "active": share(active),
            "exited": int(df["exited"].sum()), "categories": cats}


def purchasing_power(cpi: pd.Series, value: float, start: date) -> dict:
    """Paranın alım gücü: bugünkü değer, başlangıç ayının fiyatlarıyla. Enflasyon başlangıç ayından son açıklanmış
    TÜFE ayına kadardır; başlangıç ayının TÜFE'si henüz açıklanmadıysa hesaplanamaz."""
    if cpi.empty:
        return {"available": False, "message": NO_DATA}
    last = cpi.index[-1]
    sm = start.replace(day=1)
    if sm > last:
        return {"available": False, "last_month": last, "start_month": sm,
                "message": f"{month_label(sm)} enflasyonu henüz açıklanmadı; alım gücü o ayın TÜFE'si açıklanınca hesaplanır."}
    infl = inflation_between(cpi, sm, last)
    if infl is None:
        return {"available": False, "message": NO_DATA}
    return {"available": True, "start_month": sm, "last_month": last, "inflation": infl,
            "real_value": value / (1 + infl)}
