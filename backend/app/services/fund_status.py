"""Fonların düzenleyici durumu (işleme kapatılma, tasfiye).

TEFAS'ın işlem durumu (is_active) dışında, SPK kararlarıyla işleme kapatılan fonlar
`funds.status` alanıyla işaretlenir. Bu fonlar varsayılan listede, sıralamalarda ve risksiz
getiri hesabında yer almaz; fiyat verileri olduğu gibi kalır.

SPK Bülteni 2026/60 (17.09.2026) iki ayrı karar içerir:
- 7 portföy şirketinin TEFAS'ta işlem gören TÜM fonları alım satıma kapatıldı -> STATUS_CLOSED
- Bültende unvanları sayılan fonların ayrıca tasfiyesine karar verildi -> STATUS_LIQUIDATION
"""
from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Fund
from app.text import tr_upper

STATUS_ACTIVE = "aktif"
STATUS_CLOSED = "islem_kapali"
STATUS_LIQUIDATION = "islem_kapali_tasfiye"

SPK_2026_60_DATE = "17.09.2026"
SPK_2026_60_SOURCE = "SPK Bülteni 2026/60"
SPK_2026_60_URL = "https://spk.gov.tr/data/6aab8e7b8f95db07100fd7b4/2026-60.pdf"
NOTES = {
    STATUS_LIQUIDATION: f"SPK'nın {SPK_2026_60_DATE} tarihli kararıyla işleme kapatılmış ve tasfiye sürecindedir.",
    STATUS_CLOSED: f"SPK'nın {SPK_2026_60_DATE} tarihli kararıyla TEFAS'ta işleme kapatılmıştır.",
}

LIQUIDATION_LIST = Path(__file__).resolve().parent.parent / "data" / "spk_2026_60_tasfiye.txt"

# Şirket -> fon adının başındaki unvan. Bültende "A1 Portföy" geçiyor, TEFAS'taki fon adları
# "A1 CAPİTAL PORTFÖY" ile başlıyor; ikisi de eşleşsin.
COMPANY_PREFIXES = {
    "Tera": ("TERA PORTFÖY",),
    "Pusula": ("PUSULA PORTFÖY",),
    "Hedef": ("HEDEF PORTFÖY",),
    "Atlas": ("ATLAS PORTFÖY",),
    "A1 Capital": ("A1 CAPİTAL PORTFÖY", "A1 PORTFÖY"),
    "Pardus": ("PARDUS PORTFÖY",),
    "Bulls": ("BULLS PORTFÖY",),
}


def _norm(s: str) -> str:
    # "CAPİTAL" / "CAPITAL" farkı eşleşmeyi bozmasın
    return " ".join(tr_upper(s).replace("İ", "I").split())


_PREFIXES = [(company, _norm(p)) for company, ps in COMPANY_PREFIXES.items() for p in ps]


def match_company(name: str | None) -> str | None:
    """Fon adı 7 şirketten birinin unvanıyla başlıyorsa şirketin kısa adını döndürür."""
    if not name:
        return None
    n = _norm(name)
    return next((company for company, p in _PREFIXES if n.startswith(p)), None)


def name_key(name: str) -> str:
    """Unvan karşılaştırması için sadeleştirilmiş ad.

    Kaynaklar arasında değişen yazım farklarını yok sayar: büyük/küçük harf, noktalama,
    "Fon" / "Fonu" ve "(Hisse Senedi Yoğun)" / "(Hisse Senedi Yoğun Fon)".
    "(TL)" gibi anlam taşıyabilecek kısımlar korunur; emin olunamayan fon tasfiye sayılmaz.
    """
    n = _norm(name)
    n = re.sub(r"\(HISSE SENEDI YOĞUN( FON)?\)", "", n)
    n = re.sub(r"\bFONU\b", "FON", n)
    return " ".join(re.sub(r"[^\w]", " ", n).split())


@lru_cache(maxsize=1)
def liquidation_keys() -> frozenset[str]:
    lines = LIQUIDATION_LIST.read_text(encoding="utf-8").splitlines()
    return frozenset(name_key(line) for line in lines if line.strip() and not line.startswith("#"))


def classify(name: str | None) -> str:
    if not match_company(name):
        return STATUS_ACTIVE
    return STATUS_LIQUIDATION if name_key(name) in liquidation_keys() else STATUS_CLOSED


def apply_status_rules(db: Session, commit: bool = True) -> Counter:
    """Tüm fonların durumunu kurallara göre yeniden yazar; (şirket, durum) sayılarını döndürür."""
    counts: Counter = Counter()
    for fund in db.scalars(select(Fund)):
        status = classify(fund.name)
        if status == STATUS_ACTIVE:
            fund.status, fund.status_note, fund.status_source, fund.status_url = STATUS_ACTIVE, None, None, None
            continue
        fund.status, fund.status_note = status, NOTES[status]
        fund.status_source, fund.status_url = SPK_2026_60_SOURCE, SPK_2026_60_URL
        counts[(match_company(fund.name), status)] += 1
    if commit:
        db.commit()
    return counts


def is_tradable():
    """İşleme kapatılmamış fonlar için SQL koşulu (status boşsa aktif sayılır)."""
    return or_(Fund.status.is_(None), Fund.status == STATUS_ACTIVE)
