"""TEFAS (tefas.gov.tr) istemcisi.

2026'da TEFAS eski BindHistoryInfo uç noktalarını kapattı ve fon başına çalışan
yeni bir JSON API'ye geçti:

- /api/funds/fonGetiriBazliBilgiGetir : fon listesi (getiri tablosu)
- /api/funds/fonFiyatBilgiGetir       : tek fonun fiyat geçmişi
- /api/funds/fonBilgiGetir            : tek fonun güncel büyüklüğü ve yatırımcı sayısı (geçmişi yok)
- /api/funds/fonProfilBilgiGetir      : tek fonun profili (ISIN, valör, son işlem saati, komisyon, KAP bağlantısı)

Valör alanları: fonGeriAlisValor yatırımcının ALIŞ, fonSatisValor SATIŞ valörüdür (iş günü).
Adlar ters görünse de değerler piyasa uygulamasıyla uyumlu: yabancı hisse fonlarında
fonGeriAlisValor=1, fonSatisValor=3 (alım T+1, satım T+3); para piyasası fonlarında 0 / 0.

Yeni API'nin kısıtları:
- Fiyat geçmişi fon fon çekilir (toplu tarih sorgusu yok).
- Geriye dönük süre sadece 1, 3, 6, 12, 36 veya 60 ay olabilir (en fazla 5 yıl).
- Portföy dağılımı ve yönetim ücreti yayınlanmıyor. Fon büyüklüğü ve yatırımcı sayısı yalnızca
  güncel değer olarak (fon başına bir istekle) alınabiliyor; geçmiş tarihlerin değeri yok.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://www.tefas.gov.tr"
LIST_ENDPOINT = "/api/funds/fonGetiriBazliBilgiGetir"
PRICE_ENDPOINT = "/api/funds/fonFiyatBilgiGetir"
INFO_ENDPOINT = "/api/funds/fonBilgiGetir"
PROFILE_ENDPOINT = "/api/funds/fonProfilBilgiGetir"
# kapLink yalnızca KAP'ın fon sayfasıysa saklanır (bağlantı arayüzde açılıyor)
KAP_LINK_PREFIX = "https://www.kap.org.tr/"
VALID_PERIODS = (1, 3, 6, 12, 36, 60)
FUND_TYPES = ("YAT", "EMK", "BYF")  # yatırım, emeklilik, borsa yatırım fonu

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Origin": BASE_URL,
    "Referer": BASE_URL + "/",
}


class TefasError(Exception):
    pass


def internet_available(timeout: float = 3.0) -> bool:
    """TEFAS'a ulaşılabiliyor mu (internet yokken güncellemeyi hızlıca atlamak için).

    Herhangi bir HTTP yanıtı (bot koruması dahil) yeterli; proxy ayarları da dikkate alınır.
    """
    try:
        requests.head(BASE_URL, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=timeout, allow_redirects=False)
        return True
    except requests.RequestException:
        return False


@dataclass
class FundInfo:
    code: str
    name: str | None
    category: str | None
    fund_type: str
    risk_level: int | None
    is_active: bool
    raw: dict  # TEFAS'ın döndürdüğü tüm alanlar (getiri1a, getiri1y... dahil)


@dataclass
class FundPrice:
    code: str
    date: date
    price: float


@dataclass
class FundSnapshot:
    """fonBilgiGetir: fonun o anki büyüklüğü ve yatırımcı sayısı."""

    code: str
    total_value: float | None  # portföy büyüklüğü (TL)
    investor_count: int | None
    shares_outstanding: int | None


def snap_period(months: int) -> int:
    """İstenen ay sayısını TEFAS'ın kabul ettiği en yakın büyük periyoda yuvarlar."""
    for p in VALID_PERIODS:
        if p >= months:
            return p
    return VALID_PERIODS[-1]


def _parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    s = str(value).strip()
    try:
        return date.fromisoformat(s[:10])  # "2026-10-09" veya "2026-10-09T00:00:00"
    except ValueError:
        pass
    try:
        return datetime.strptime(s[:10], "%d.%m.%Y").date()  # "09.10.2026"
    except ValueError:
        return None


def _to_float(value) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:  # "1.234,56" veya "1234.56"
        s = str(value).strip()
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        return float(s)
    except ValueError:
        return None


def clean_category(value: str | None) -> str | None:
    """'Kıymetli Madenler Şemsiye Fonu' -> 'Kıymetli Madenler'"""
    if not value:
        return None
    s = value.strip()
    for suffix in (" Şemsiye Fonu", " Şemsiye Fon", " Fonu"):
        if s.endswith(suffix):
            return s[: -len(suffix)].strip()
    return s


def _risk(value) -> int | None:
    try:
        r = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return r if 1 <= r <= 7 else None


def parse_fund_list(rows: list[dict], fund_type: str) -> list[FundInfo]:
    funds = []
    for r in rows:
        code = r.get("fonKodu")
        if not code:
            continue
        funds.append(
            FundInfo(
                code=code.strip().upper(),
                name=(r.get("fonUnvan") or "").strip() or None,
                category=clean_category(r.get("fonTurAciklama")),
                fund_type=fund_type,
                risk_level=_risk(r.get("riskDegeri")),
                is_active=r.get("tefasDurum") is not False,
                raw=r,
            )
        )
    return funds


def _to_int(value) -> int | None:
    f = _to_float(value)
    return None if f is None or f < 0 else int(round(f))


def parse_snapshot(rows: list[dict], code: str) -> FundSnapshot | None:
    if not rows:
        return None
    r = rows[0]
    total = _to_float(r.get("portBuyukluk"))
    return FundSnapshot(
        code=(r.get("fonKodu") or code).strip().upper(),
        total_value=total if total is not None and total >= 0 else None,
        investor_count=_to_int(r.get("yatirimciSayi")),
        shares_outstanding=_to_int(r.get("payAdet")),
    )


def parse_kap_link(rows: list[dict]) -> str | None:
    link = (rows[0].get("kapLink") or "").strip() if rows else ""
    return link if link.startswith(KAP_LINK_PREFIX) and len(link) <= 500 else None


def _valor(value) -> int | None:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return None
    return v if 0 <= v <= 10 else None


def _hhmm(value) -> str | None:
    s = str(value or "").strip()
    try:
        h, m = (int(x) for x in s.split(":")[:2])
    except ValueError:
        return None
    return f"{h:02d}:{m:02d}" if 0 <= h < 24 and 0 <= m < 60 else None


@dataclass
class FundProfile:
    """fonProfilBilgiGetir'den saklananlar."""

    kap_url: str | None
    buy_valor: int | None  # fonGeriAlisValor: alış valörü (iş günü)
    sell_valor: int | None  # fonSatisValor: satış valörü (iş günü)
    cutoff: str | None  # sonIsSaat: bu saatten sonraki emir ertesi iş günü sayılır ("17:45")


def parse_profile(rows: list[dict]) -> FundProfile | None:
    if not rows:
        return None
    r = rows[0]
    return FundProfile(
        kap_url=parse_kap_link(rows),
        buy_valor=_valor(r.get("fonGeriAlisValor")),
        sell_valor=_valor(r.get("fonSatisValor")),
        cutoff=_hhmm(r.get("sonIsSaat")),
    )


def parse_prices(rows: list[dict], code: str) -> list[FundPrice]:
    prices = []
    for r in rows:
        d = _parse_date(r.get("tarih"))
        p = _to_float(r.get("fiyat"))
        if d is None or p is None or p <= 0:
            continue  # bozuk veya boş satırları atla
        prices.append(FundPrice(code=(r.get("fonKodu") or code).upper(), date=d, price=p))
    prices.sort(key=lambda x: x.date)
    return prices


class TefasClient:
    def __init__(self, delay: float = 0.5, retries: int = 3, timeout: int = 30):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.delay = delay  # istekler arası bekleme: siteyi yormamak için
        self.retries = retries
        self.timeout = timeout

    def _post(self, endpoint: str, payload: dict) -> list[dict]:
        last_error = None
        for attempt in range(1, self.retries + 1):
            try:
                r = self.session.post(BASE_URL + endpoint, json=payload, timeout=self.timeout)
                r.raise_for_status()
                body = r.json()
                time.sleep(self.delay)
                return body.get("resultList") or []
            except (requests.RequestException, ValueError) as e:
                last_error = e
                wait = 2**attempt
                log.warning("TEFAS isteği başarısız (%s/%s): %s. %ss sonra tekrar.", attempt, self.retries, e, wait)
                time.sleep(wait)
        raise TefasError(f"TEFAS'a ulaşılamadı: {last_error}")

    def list_funds(self, fund_type: str = "YAT") -> list[FundInfo]:
        assert fund_type in FUND_TYPES
        payload = {
            "dil": "TR", "fonTipi": fund_type, "kurucuKodu": None, "sfonTurKod": None,
            "fonTurAciklama": None, "islem": 1, "fonTurKod": None, "fonGrubu": None,
            "donemGetiri1a": "1", "donemGetiri3a": "1", "donemGetiri6a": "1",
            "donemGetiri1y": "1", "donemGetiriyb": "1", "donemGetiri3y": "1",
            "donemGetiri5y": "1", "basTarih": None, "bitTarih": None,
            "calismaTipi": 2, "getiriOrani": "1",
        }
        return parse_fund_list(self._post(LIST_ENDPOINT, payload), fund_type)

    def price_history(self, code: str, months: int = 12) -> list[FundPrice]:
        payload = {"fonKodu": code.upper(), "dil": "TR", "periyod": snap_period(months)}
        return parse_prices(self._post(PRICE_ENDPOINT, payload), code)

    def snapshot(self, code: str) -> FundSnapshot | None:
        return parse_snapshot(self._post(INFO_ENDPOINT, {"fonKodu": code.upper(), "dil": "TR"}), code)

    def profile(self, code: str) -> FundProfile | None:
        return parse_profile(self._post(PROFILE_ENDPOINT, {"fonKodu": code.upper(), "dil": "TR"}))
