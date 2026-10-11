from datetime import date

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import scheduler
from app.database import Base
from app.models import Fund, Price
from app.services import updater
from app.services.tefas_client import FundInfo, FundPrice, TefasError


class FakeClient:
    """TEFAS'a gitmeden önceden belirlenmiş veriyi döndürür."""

    def __init__(self, prices, fail=()):
        self.prices = prices
        self.fail = set(fail)

    def list_funds(self, fund_type):
        return [
            FundInfo("AAA", "A Fonu", "Hisse Senedi", fund_type, 6, True, {}),
            FundInfo("BBB", "B Fonu", "Para Piyasası", fund_type, 1, True, {}),
            FundInfo("KPL", "Kapalı Fon", "Değişken", fund_type, 4, False, {}),
        ]

    def price_history(self, code, months=1):
        if code in self.fail:
            raise TefasError("zaman aşımı")
        return [FundPrice(code, d, p) for d, p in self.prices.get(code, [])]


@pytest.fixture
def db_session(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(updater, "SessionLocal", Session)
    return Session


def test_update_inserts_only_new_prices(db_session):
    day1, day2 = date(2026, 10, 8), date(2026, 10, 9)
    first = updater.run_update(client=FakeClient({"AAA": [(day1, 1.0)], "BBB": [(day1, 2.0)]}))
    assert first.status == "ok" and first.new_prices == 2

    # Ertesi gün: day1 tekrar gelir ama yeniden yazılmamalı
    second = updater.run_update(client=FakeClient({"AAA": [(day1, 1.0), (day2, 1.1)], "BBB": [(day1, 2.0), (day2, 2.01)]}))
    assert second.new_prices == 2

    with db_session() as db:
        assert db.scalar(select(func.count()).select_from(Price)) == 4
        assert db.get(Fund, "AAA").risk_level == 6
        assert db.get(Fund, "KPL").is_active is False


def test_update_skips_inactive_and_reports_errors(db_session):
    r = updater.run_update(client=FakeClient({"AAA": [(date(2026, 10, 9), 1.0)]}, fail={"BBB"}))
    assert r.status == "partial"
    assert r.funds_total == 3 and r.funds_updated == 1  # KPL kapalı, BBB hata verdi
    assert r.errors and r.errors[0].startswith("BBB")


def test_update_failed_when_tefas_down(db_session):
    class Down(FakeClient):
        def list_funds(self, fund_type):
            raise TefasError("bağlantı yok")

    r = updater.run_update(client=Down({}))
    assert r.status == "failed"


def test_scheduler_registers_weekday_job(monkeypatch):
    monkeypatch.setattr(scheduler.settings, "scheduler_enabled", True)
    try:
        scheduler.start()
        nxt = scheduler.next_run()
        assert nxt is not None and "T21:00" in nxt
    finally:
        scheduler.stop()
