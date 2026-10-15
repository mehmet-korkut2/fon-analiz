from datetime import date

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import scheduler
from app.database import Base
from app.models import Fund, Price
from app.services import updater
from app.services.tefas_client import FundInfo, FundPrice, FundProfile, FundSnapshot, TefasError


class FakeClient:
    """TEFAS'a gitmeden önceden belirlenmiş veriyi döndürür."""

    def __init__(self, prices, fail=(), info_fail=()):
        self.prices = prices
        self.fail = set(fail)
        self.info_fail = set(info_fail)
        self.kap_calls = []

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

    def snapshot(self, code):
        if code in self.info_fail:
            raise TefasError("zaman aşımı")
        return FundSnapshot(code, 1_000_000.0 * len(self.kap_calls), 100 + len(self.kap_calls), 5000)

    def profile(self, code):
        self.kap_calls.append(code)
        return FundProfile(f"https://www.kap.org.tr/tr/fon-bilgileri/genel/{code.lower()}", 1, 2, "17:45")


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
    monkeypatch.setattr(scheduler.settings, "catch_up_on_startup", False)
    try:
        scheduler.start()
        nxt = scheduler.next_run()
        assert nxt is not None and "T21:00" in nxt
    finally:
        scheduler.stop()


def test_expected_latest_date():
    from datetime import datetime
    # Pazartesi 10:00 -> bir önceki iş günü cuma
    assert scheduler.expected_latest_date(datetime(2026, 10, 12, 10, 0)).isoformat() == "2026-10-09"
    # Pazartesi 22:00 -> aynı gün
    assert scheduler.expected_latest_date(datetime(2026, 10, 12, 22, 0)).isoformat() == "2026-10-12"
    # Pazar -> cuma
    assert scheduler.expected_latest_date(datetime(2026, 10, 11, 23, 0)).isoformat() == "2026-10-09"


def test_update_stores_current_size_and_kap_link_once(db_session):
    prices = {"AAA": [(date(2026, 10, 9), 1.0)], "BBB": [(date(2026, 10, 9), 2.0)]}
    first = FakeClient(prices)
    r = updater.run_update(client=first)
    assert r.info_updated == 2
    assert first.kap_calls == ["AAA", "BBB"]  # KPL işlem görmüyor, istek yok
    with db_session() as db:
        a = db.get(Fund, "AAA")
        assert a.investor_count is not None and a.total_value is not None and a.info_date is not None
        assert a.kap_url.endswith("/aaa")
        assert (a.buy_valor, a.sell_valor, a.cutoff_time) == (1, 2, "17:45") and a.profile_date is not None
        assert db.get(Fund, "KPL").total_value is None

    # ikinci gece: büyüklük yenilenir; profil (KAP, valör) 30 günden yeni, yeniden istenmez
    second = FakeClient(prices)
    second.kap_calls = ["x"]  # değerleri birinci geceden farklı kılmak için
    updater.run_update(client=second)
    assert second.kap_calls == ["x"]
    with db_session() as db:
        assert db.get(Fund, "AAA").investor_count == 101


def test_size_failure_keeps_price_update(db_session):
    r = updater.run_update(client=FakeClient({"AAA": [(date(2026, 10, 9), 1.0)], "BBB": [(date(2026, 10, 9), 2.0)]}, info_fail={"BBB"}))
    assert r.funds_updated == 2 and r.new_prices == 2 and r.info_updated == 1
    assert any(e.startswith("BBB (büyüklük)") for e in r.errors)


def test_update_skipped_quietly_when_offline(db_session):
    client = FakeClient({"AAA": [(date(2026, 10, 9), 1.0)]})
    r = updater.run_update(client=client, online=lambda: False)
    assert r.status == "offline" and r.funds_total == 0 and "İnternet bağlantısı yok" in r.errors[0]
    assert updater.last_result is r
    with db_session() as db:
        assert db.scalar(select(func.count()).select_from(Price)) == 0  # hiçbir şey yazılmadı


def test_update_stops_when_connection_lost(db_session):
    class Dropping(FakeClient):
        def list_funds(self, fund_type):
            return [FundInfo(f"F{i}", f"Fon {i}", "Hisse Senedi", fund_type, 6, True, {}) for i in range(20)]

        def price_history(self, code, months=1):
            self.calls = getattr(self, "calls", 0) + 1
            if code != "F0":
                raise TefasError("bağlantı yok")
            return [FundPrice(code, date(2026, 10, 9), 1.0)]

    client = Dropping({})
    state = {"n": 0}

    def online():  # ilk kontrolde bağlı, sonra kopuk
        state["n"] += 1
        return state["n"] == 1

    r = updater.run_update(client=client, online=online, recompute_metrics=False)
    assert client.calls == 1 + updater.FAILS_BEFORE_CHECK  # 20 fonun hepsi denenmedi
    assert r.new_prices == 1 and r.status == "partial" and updater.LOST_MSG in r.errors
