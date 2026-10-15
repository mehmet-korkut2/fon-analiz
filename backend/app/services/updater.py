"""TEFAS verilerini veritabanına yazan ortak mantık.

Hem elle çalıştırılan betik (scripts/tefas_yukle.py) hem de her gün çalışan
zamanlanmış görev (app/scheduler.py) bu fonksiyonları kullanır.
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Fund, Price
from app.services import fund_status, metrics_job, recommender, sanal_portfoy
from app.services.tefas_client import FundInfo, FundPrice, TefasClient, TefasError, internet_available

log = logging.getLogger(__name__)

OFFLINE_MSG = "İnternet bağlantısı yok; TEFAS güncellemesi atlandı. Site son verilerle çalışmaya devam eder."
LOST_MSG = "İnternet bağlantısı kesildi; güncelleme yarıda bırakıldı, alınan veriler kaydedildi."
FAILS_BEFORE_CHECK = 3  # art arda bu kadar hata olursa bağlantı yeniden kontrol edilir

_lock = threading.Lock()  # aynı anda iki güncelleme çalışmasın


@dataclass
class UpdateResult:
    started_at: str
    finished_at: str | None = None
    status: str = "running"  # running / ok / partial / failed / skipped / offline
    funds_total: int = 0
    funds_updated: int = 0
    new_prices: int = 0
    info_updated: int = 0  # büyüklüğü/yatırımcı sayısı yenilenen fon
    metrics: dict | None = None
    ml: dict | None = None
    sanal: dict | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        d["errors"] = d["errors"][:20]
        return d


last_result: UpdateResult | None = None


def upsert_funds(db: Session, funds: list[FundInfo]) -> None:
    for f in funds:
        fund = db.get(Fund, f.code)
        if fund is None:
            fund = Fund(code=f.code)
            db.add(fund)
        fund.name = f.name or fund.name or f.code
        fund.category = f.category or fund.category
        fund.fund_type = f.fund_type
        fund.risk_level = f.risk_level or fund.risk_level
        fund.is_active = f.is_active
    db.flush()
    fund_status.apply_status_rules(db, commit=False)  # yeni eklenen fonlar da SPK kararlarına göre işaretlensin
    db.commit()


def save_prices(db: Session, code: str, prices: list[FundPrice]) -> int:
    if not prices:
        return 0
    since = prices[0].date
    existing = set(db.scalars(select(Price.date).where(Price.fund_code == code, Price.date >= since)))
    new = [Price(fund_code=code, date=p.date, price=p.price) for p in prices if p.date not in existing]
    db.add_all(new)
    db.commit()
    return len(new)


PROFILE_REFRESH_DAYS = 30  # valör ve KAP bağlantısı nadiren değişir


def update_info(db: Session, client: TefasClient, code: str, today: date | None = None) -> bool:
    """Fonun güncel büyüklüğünü ve yatırımcı sayısını (her seferinde), profilini (KAP bağlantısı,
    valör, son işlem saati; hiç alınmadıysa ya da 30 günden eskiyse) yazar.

    TEFAS bu değerlerin geçmişini vermiyor; sadece son alınan değer saklanır. İstekler
    TefasClient'ın bekleme süresine tabidir. Başarısız olursa eski değer korunur.
    """
    fund = db.get(Fund, code)
    if fund is None:
        return False
    today = today or date.today()
    snap = client.snapshot(code)
    if snap is not None:
        fund.total_value = snap.total_value
        fund.investor_count = snap.investor_count
        fund.info_date = today
    if fund.profile_date is None or (today - fund.profile_date).days >= PROFILE_REFRESH_DAYS:
        prof = client.profile(code)
        if prof is not None:
            fund.kap_url = prof.kap_url or fund.kap_url
            fund.buy_valor, fund.sell_valor, fund.cutoff_time = prof.buy_valor, prof.sell_valor, prof.cutoff
            fund.profile_date = today
    db.commit()
    return snap is not None


def run_update(
    fund_type: str = "YAT",
    months: int = 1,
    limit: int = 0,
    only_code: str | None = None,
    client: TefasClient | None = None,
    recompute_metrics: bool = True,
    fetch_info: bool = True,
    online: Callable[[], bool] | None = None,
) -> UpdateResult:
    """Fon listesini yeniler ve her fonun son `months` aylık fiyatlarından eksik olanları ekler.

    İnternet yoksa (online() False) hiçbir şey yapmadan "offline" döner; güncelleme sırasında bağlantı
    koparsa kalan fonlar için saatlerce yeniden denemek yerine durur. online verilmezse, gerçek
    TEFAS istemcisiyle çalışırken internet_available kullanılır (testlerde sahte istemciyle kontrol yok).
    """
    global last_result
    result = UpdateResult(started_at=datetime.now().isoformat(timespec="seconds"))
    if online is None and client is None:
        online = internet_available
    if online is not None and not online():
        result.status, result.finished_at = "offline", result.started_at
        result.errors.append(OFFLINE_MSG)
        last_result = result
        log.info(OFFLINE_MSG)
        return result

    if not _lock.acquire(blocking=False):
        result.status = "skipped"
        result.errors.append("Başka bir güncelleme zaten çalışıyor.")
        result.finished_at = result.started_at
        return result

    last_result = result
    client = client or TefasClient()
    try:
        with SessionLocal() as db:
            try:
                funds = client.list_funds(fund_type)
            except TefasError as e:
                offline = online is not None and not online()
                result.status = "offline" if offline else "failed"
                result.errors.append(OFFLINE_MSG if offline else str(e))
                return result

            if only_code:
                funds = [f for f in funds if f.code == only_code.upper()]
            elif limit:
                funds = funds[:limit]
            upsert_funds(db, funds)
            result.funds_total = len(funds)
            log.info("%s fon güncellenecek (%s, son %s ay).", len(funds), fund_type, months)

            fails = 0
            for i, f in enumerate(funds, 1):
                if not f.is_active:
                    continue
                try:
                    added = save_prices(db, f.code, client.price_history(f.code, months=months))
                    fails = 0
                except TefasError as e:
                    result.errors.append(f"{f.code}: {e}")
                    log.error("%s atlandı: %s", f.code, e)
                    fails += 1
                    if fails >= FAILS_BEFORE_CHECK and online is not None and not online():
                        result.errors.append(LOST_MSG)
                        log.warning(LOST_MSG)
                        break
                    continue
                result.funds_updated += 1
                result.new_prices += added
                if fetch_info:
                    try:
                        result.info_updated += update_info(db, client, f.code)
                    except TefasError as e:  # büyüklük alınamazsa fiyat güncellemesi yine sayılır
                        result.errors.append(f"{f.code} (büyüklük): {e}")
                if i % 50 == 0 or i == len(funds):
                    log.info("[%s/%s] işlendi, şimdiye kadar %s yeni fiyat.", i, len(funds), result.new_prices)

            if recompute_metrics:
                try:
                    result.metrics = metrics_job.recompute_all(db)
                except Exception as e:  # metrik hatası fiyat güncellemesini boşa çıkarmasın
                    log.exception("Metrik hesaplama başarısız")
                    result.errors.append(f"metrikler: {e}")
                try:
                    result.sanal = sanal_portfoy.process(db)  # bekleyen sanal emirler ve portföy değeri
                except Exception as e:
                    log.exception("Sanal portföy güncellemesi başarısız")
                    result.errors.append(f"sanal portföy: {e}")
                try:
                    n = recommender.store_rolling(db)  # ~1 dk; öneri sayfasındaki geriye dönük test
                    log.info("Kayan pencereli geriye dönük test: %s pencere", n)
                except Exception as e:
                    log.exception("Geriye dönük test başarısız")
                    result.errors.append(f"geriye dönük test: {e}")
                try:
                    from app.ml import job as ml_job  # lightgbm yüklemesi sadece burada

                    result.ml = ml_job.run(db)  # ~15 sn; ayda bir ~2 dk (değerlendirme raporu)
                except Exception as e:
                    log.exception("ML işi başarısız")
                    result.errors.append(f"ML: {e}")

        result.status = "partial" if result.errors else "ok"
        return result
    finally:
        result.finished_at = datetime.now().isoformat(timespec="seconds")
        log.info("Güncelleme bitti: %s", result.to_dict())
        _lock.release()
