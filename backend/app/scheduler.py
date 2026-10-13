"""Zamanlanmış görevler.

Varsayılan: hafta içi her gün 21:00'de (İstanbul saati) TEFAS verilerini günceller,
ardından tüm fonların metriklerini yeniden hesaplar. TEFAS günün fiyatlarını akşam
saatlerinde yayınladığı için daha erken saat önerilmez.

Bilgisayar 21:00'de kapalı veya uykudaysa güncelleme kaçar. Bu yüzden backend her
açıldığında verinin güncel olup olmadığına bakar; eskiyse güncellemeyi hemen başlatır.

Not: Sunucu birden fazla işlemle (worker) çalıştırılırsa her işlem kendi zamanlayıcısını
başlatır. Canlıda tek worker kullan veya SCHEDULER_ENABLED=false yapıp görevi ayrı çalıştır.
"""
import logging
import threading
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import func, select

from app.config import settings
from app.database import SessionLocal
from app.models import FundMetrics, Price
from app.services import metrics_job
from app.services.updater import run_update

log = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def daily_update():
    log.info("Zamanlanmış TEFAS güncellemesi başladı.")
    run_update(fund_type="YAT", months=1)


def expected_latest_date(now: datetime) -> date:
    """Şu an itibarıyla veritabanında olması gereken en yeni fiyat tarihi.

    Güncelleme saatinden sonra bugünün (iş günüyse) fiyatı beklenir,
    öncesinde bir önceki iş gününün fiyatı.
    """
    d = now.date()
    if (now.hour, now.minute) < (settings.update_hour, settings.update_minute):
        d -= timedelta(days=1)
    while d.weekday() >= 5:  # cumartesi, pazar
        d -= timedelta(days=1)
    return d


def catch_up():
    """Açılışta: veri eskiyse güncelle, metrik tablosu boşsa hesapla."""
    with SessionLocal() as db:
        latest = db.scalar(select(func.max(Price.date)))
        has_metrics = db.scalar(select(func.count()).select_from(FundMetrics)) > 0
    if latest is None:
        log.info("Veritabanında fiyat yok. İlk yükleme için: python -m scripts.tefas_yukle --limit 0 --ay 60")
        return
    expected = expected_latest_date(datetime.now(ZoneInfo(settings.timezone)))
    if latest < expected:
        log.info("Veri eski (son fiyat %s, beklenen %s). Güncelleme başlatılıyor.", latest, expected)
        run_update(fund_type="YAT", months=1)
    elif not has_metrics:
        log.info("Metrik tablosu boş, hesaplanıyor.")
        with SessionLocal() as db:
            metrics_job.recompute_all(db)


def start() -> BackgroundScheduler | None:
    global _scheduler
    if not settings.scheduler_enabled or _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone=settings.timezone)
    _scheduler.add_job(
        daily_update,
        CronTrigger(day_of_week="mon-fri", hour=settings.update_hour, minute=settings.update_minute, timezone=settings.timezone),
        id="tefas_daily",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=6 * 3600,
    )
    _scheduler.start()
    log.info("Zamanlayıcı başladı. Sonraki çalışma: %s", next_run())
    if settings.catch_up_on_startup:
        threading.Thread(target=catch_up, name="catch-up", daemon=True).start()
    return _scheduler


def stop():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def next_run() -> str | None:
    if _scheduler is None:
        return None
    job = _scheduler.get_job("tefas_daily")
    return job.next_run_time.isoformat(timespec="minutes") if job and job.next_run_time else None
