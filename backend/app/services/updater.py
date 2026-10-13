"""TEFAS verilerini veritabanına yazan ortak mantık.

Hem elle çalıştırılan betik (scripts/tefas_yukle.py) hem de her gün çalışan
zamanlanmış görev (app/scheduler.py) bu fonksiyonları kullanır.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Fund, Price
from app.services import fund_status, metrics_job
from app.services.tefas_client import FundInfo, FundPrice, TefasClient, TefasError

log = logging.getLogger(__name__)

_lock = threading.Lock()  # aynı anda iki güncelleme çalışmasın


@dataclass
class UpdateResult:
    started_at: str
    finished_at: str | None = None
    status: str = "running"  # running / ok / partial / failed / skipped
    funds_total: int = 0
    funds_updated: int = 0
    new_prices: int = 0
    metrics: dict | None = None
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


def run_update(
    fund_type: str = "YAT",
    months: int = 1,
    limit: int = 0,
    only_code: str | None = None,
    client: TefasClient | None = None,
    recompute_metrics: bool = True,
) -> UpdateResult:
    """Fon listesini yeniler ve her fonun son `months` aylık fiyatlarından eksik olanları ekler."""
    global last_result
    result = UpdateResult(started_at=datetime.now().isoformat(timespec="seconds"))

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
                result.status = "failed"
                result.errors.append(str(e))
                return result

            if only_code:
                funds = [f for f in funds if f.code == only_code.upper()]
            elif limit:
                funds = funds[:limit]
            upsert_funds(db, funds)
            result.funds_total = len(funds)
            log.info("%s fon güncellenecek (%s, son %s ay).", len(funds), fund_type, months)

            for i, f in enumerate(funds, 1):
                if not f.is_active:
                    continue
                try:
                    added = save_prices(db, f.code, client.price_history(f.code, months=months))
                except TefasError as e:
                    result.errors.append(f"{f.code}: {e}")
                    log.error("%s atlandı: %s", f.code, e)
                    continue
                result.funds_updated += 1
                result.new_prices += added
                if i % 50 == 0 or i == len(funds):
                    log.info("[%s/%s] işlendi, şimdiye kadar %s yeni fiyat.", i, len(funds), result.new_prices)

            if recompute_metrics:
                try:
                    result.metrics = metrics_job.recompute_all(db)
                except Exception as e:  # metrik hatası fiyat güncellemesini boşa çıkarmasın
                    log.exception("Metrik hesaplama başarısız")
                    result.errors.append(f"metrikler: {e}")

        result.status = "partial" if result.errors else "ok"
        return result
    finally:
        result.finished_at = datetime.now().isoformat(timespec="seconds")
        log.info("Güncelleme bitti: %s", result.to_dict())
        _lock.release()
