"""Döviz ve altın kurları.

İki kaynak:
- "tcmb":  TCMB gösterge kurları (resmi). Günde bir kez, iş günleri ~15:30'da yayınlanır.
- "canli": Truncgil Finans (ücretsiz, gayriresmi). Gün içinde birkaç dakikada bir güncellenir;
           döviz, altın, gümüş, BIST100, Brent gibi verileri de içerir.

Sonuçlar bellekte önbelleğe alınır, böylece her ziyaretçi isteği kaynağa gitmez. Her kaynağın son
başarılı yanıtı ayrıca veritabanına yazılır (fx_snapshots). İnternet yokken ya da kaynak yanıt
vermezken bu son bilinen kurlar "stale" işaretiyle ve alındıkları zamanla döner; sunumda internet
olmasa da döviz sayfası boş kalmaz.
"""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from datetime import datetime

import requests
from sqlalchemy.orm import Session

from app.models import FxSnapshot

TCMB_URL = "https://www.tcmb.gov.tr/kurlar/today.xml"
CANLI_URL = "https://finans.truncgil.com/v4/today.json"
CACHE_TTL = {"tcmb": 15 * 60, "canli": 60}  # saniye
TIMEOUT = 15
HEADERS = {"User-Agent": "Mozilla/5.0 (fon-analiz bitirme projesi)"}

SOURCE_NAMES = {
    "tcmb": "TCMB gösterge kurları",
    "canli": "Truncgil Finans (anlık, gayriresmi)",
}

# Truncgil sadece kod verir; sık kullanılanlara Türkçe ad ekliyoruz.
NAMES = {
    "USD": "ABD Doları", "EUR": "Euro", "GBP": "İngiliz Sterlini", "CHF": "İsviçre Frangı",
    "CAD": "Kanada Doları", "RUB": "Rus Rublesi", "AED": "BAE Dirhemi", "AUD": "Avustralya Doları",
    "DKK": "Danimarka Kronu", "SEK": "İsveç Kronu", "NOK": "Norveç Kronu", "JPY": "Japon Yeni",
    "KWD": "Kuveyt Dinarı", "SAR": "Suudi Arabistan Riyali", "CNY": "Çin Yuanı", "AZN": "Azerbaycan Manatı",
    "QAR": "Katar Riyali", "KRW": "Güney Kore Wonu", "PKR": "Pakistan Rupisi", "RON": "Rumen Leyi",
    "BGN": "Bulgar Levası", "PLN": "Polonya Zlotisi", "HUF": "Macar Forinti", "CZK": "Çek Korunası",
    "INR": "Hindistan Rupisi", "ILS": "İsrail Şekeli", "GEL": "Gürcistan Larisi", "KZT": "Kazak Tengesi",
    "GRA": "Gram Altın", "HAS": "Has Altın", "ONS": "Ons Altın ($)", "CEYREKALTIN": "Çeyrek Altın",
    "YARIMALTIN": "Yarım Altın", "TAMALTIN": "Tam Altın", "CUMHURIYETALTINI": "Cumhuriyet Altını",
    "ATAALTIN": "Ata Altın", "14AYARALTIN": "14 Ayar Altın", "18AYARALTIN": "18 Ayar Altın",
    "YIA": "22 Ayar Bilezik", "GUMUS": "Gram Gümüş", "GPL": "Gram Platin", "PAL": "Gram Paladyum",
    "XU100": "BIST 100", "BRENT": "Brent Petrol ($)", "DBITCOIN": "Bitcoin ($)",
}

GROUPS = {"Currency": "doviz", "Gold": "altin"}  # diğer her şey "diger"

_cache: dict[str, tuple[float, dict]] = {}


class FxError(Exception):
    pass


def _num(value) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace("%", "").replace("$", "")
    if "," in s and "." in s:  # 1.234,56
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:  # 49,1432
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_tcmb(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    rates = []
    for c in root.findall("Currency"):
        code = c.get("Kod") or c.get("CurrencyCode")
        buying = _num(c.findtext("ForexBuying"))
        selling = _num(c.findtext("ForexSelling"))
        if not code or buying is None:
            continue
        rates.append({
            "code": code,
            "name": (c.findtext("Isim") or code).strip().title(),
            "group": "doviz",
            "unit": int(_num(c.findtext("Unit")) or 1),
            "buying": buying,
            "selling": selling,
            "banknote_buying": _num(c.findtext("BanknoteBuying")),
            "banknote_selling": _num(c.findtext("BanknoteSelling")),
            "change": None,  # TCMB günlük değişim yayınlamaz
        })
    return {"updated_at": root.get("Tarih"), "rates": rates}


def parse_canli(data: dict) -> dict:
    rates = []
    for code, v in data.items():
        if not isinstance(v, dict):
            continue
        buying, selling = _num(v.get("Buying")), _num(v.get("Selling"))
        if buying is None and selling is None:
            continue
        rates.append({
            "code": code,
            "name": NAMES.get(code) or (v.get("Name") or code).title(),
            "group": GROUPS.get(v.get("Type"), "diger"),
            "unit": 1,
            "buying": buying,
            "selling": selling,
            "change": _num(v.get("Change")),  # yüzde
        })
    return {"updated_at": data.get("Update_Date"), "rates": rates}


def _fetch(source: str) -> dict:
    url = TCMB_URL if source == "tcmb" else CANLI_URL
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return parse_tcmb(r.text) if source == "tcmb" else parse_canli(r.json())
    except (requests.RequestException, ValueError, ET.ParseError) as e:
        raise FxError(f"{SOURCE_NAMES[source]} alınamadı: {e}") from e


def _save(db: Session, source: str, result: dict) -> None:
    snap = db.get(FxSnapshot, source)
    if snap is None:
        snap = FxSnapshot(source=source)
        db.add(snap)
    snap.payload, snap.fetched_at = result, datetime.fromisoformat(result["fetched_at"])
    db.commit()


def last_known(db: Session | None, source: str) -> dict | None:
    snap = db.get(FxSnapshot, source) if db is not None else None
    return snap.payload if snap else None


def get_rates(source: str = "canli", use_cache: bool = True, db: Session | None = None) -> dict:
    """Kurlar. Kaynağa ulaşılamazsa önce bellekteki, yoksa veritabanındaki son başarılı yanıt
    (stale=True; fetched_at alındığı zaman) döner; ikisi de yoksa FxError."""
    if source not in SOURCE_NAMES:
        raise ValueError(f"Bilinmeyen kaynak: {source}")
    now = time.time()
    cached = _cache.get(source)
    if use_cache and cached and now - cached[0] < CACHE_TTL[source]:
        return cached[1]
    try:
        result = _fetch(source)
    except FxError as e:
        old = cached[1] if cached else last_known(db, source)
        if old:  # kaynak düştüyse ya da internet yoksa son bilinen kurlar
            return {**old, "stale": True, "error": str(e)}
        raise
    result.update(source=source, source_name=SOURCE_NAMES[source], fetched_at=datetime.now().isoformat(timespec="seconds"), stale=False)
    _cache[source] = (now, result)
    if db is not None:
        _save(db, source, result)
    return result
