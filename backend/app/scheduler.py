"""Zamanlanmış görevler.

Varsayılan: hafta içi her gün 21:00'de (İstanbul saati) TEFAS verilerini günceller.
TEFAS günün fiyatlarını akşam saatlerinde yayınladığı için daha erken saat önerilmez.

Not: Sunucu birden fazla işlemle (worker) çalıştırılırsa her işlem kendi zamanlayıcısını
başlatır. Canlıda tek worker kullan veya SCHEDULER_ENABLED=false yapıp görevi ayrı çalıştır.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.services.updater import run_update

log = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def daily_update():
    log.info("Zamanlanmış TEFAS güncellemesi başladı.")
    run_update(fund_type="YAT", months=1)


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
        coalesce=True,  # bilgisayar kapalıyken kaçan çalışmalar tek seferde telafi edilir
        misfire_grace_time=6 * 3600,  # 6 saate kadar geç kalmış çalışmayı yine yap
    )
    _scheduler.start()
    log.info("Zamanlayıcı başladı. Sonraki çalışma: %s", next_run())
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
