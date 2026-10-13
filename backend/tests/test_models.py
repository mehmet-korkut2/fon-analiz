from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Fund, PortfolioAllocation, Price, RiskProfile, User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_fund_with_prices_and_allocations(db):
    fund = Fund(code="TTE", name="Örnek Fon", category="Hisse Senedi", risk_level=6)
    fund.prices.append(Price(date=date(2026, 10, 1), price=1.25, investor_count=1000))
    fund.allocations.append(PortfolioAllocation(date=date(2026, 10, 1), asset_type="Hisse Senedi", ratio=85))
    db.add(fund)
    db.commit()

    saved = db.get(Fund, "TTE")
    assert len(saved.prices) == 1
    assert saved.allocations[0].ratio == 85


def test_duplicate_price_rejected(db):
    db.add(Fund(code="AAA", name="A"))
    db.add_all([Price(fund_code="AAA", date=date(2026, 10, 1), price=1.0),
                Price(fund_code="AAA", date=date(2026, 10, 1), price=1.1)])
    with pytest.raises(IntegrityError):
        db.commit()


def test_user_risk_profile(db):
    user = User(email="test@example.com", password_hash="x")
    user.risk_profiles.append(RiskProfile(score=55, profile="dengeli", answers={"q1": "b"}))
    db.add(user)
    db.commit()
    assert db.get(User, user.id).risk_profiles[0].profile == "dengeli"


def test_invalid_profile_rejected(db):
    user = User(email="x@example.com", password_hash="x")
    user.risk_profiles.append(RiskProfile(score=50, profile="cesur", answers={}))
    db.add(user)
    with pytest.raises(IntegrityError):
        db.commit()


def test_init_db_adds_new_nullable_columns():
    # Eski şemayla oluşturulmuş bir veritabanı: fund_metrics tablosunda ret_3y sütunu yok
    from sqlalchemy import create_engine, inspect, text

    from app.database import init_db

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE fund_metrics (fund_code VARCHAR(10) PRIMARY KEY, as_of DATE NOT NULL, "
                          "last_price FLOAT NOT NULL, data_points INTEGER NOT NULL)"))
        conn.execute(text("INSERT INTO fund_metrics VALUES ('TTE', '2026-10-09', 1.5, 250)"))
    init_db(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("fund_metrics")}
    assert {"ret_3y", "ret_1y", "sharpe_1y"} <= cols
    with engine.connect() as conn:
        assert conn.execute(text("SELECT fund_code, ret_3y FROM fund_metrics")).one() == ("TTE", None)
    init_db(engine)  # ikinci kez çalışınca hata vermez
