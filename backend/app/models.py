"""Veritabanı tabloları.

funds ─┬─< prices                 (fonun günlük fiyat geçmişi)
       ├─< portfolio_allocations  (fonun varlık dağılımı)
       └── fund_metrics           (önceden hesaplanmış metrikler, 1:1)
users ───< risk_profiles          (kullanıcının risk anketi sonuçları)
"""
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Fund(Base):
    """TEFAS'taki her fon için sabit bilgiler."""

    __tablename__ = "funds"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)  # TEFAS fon kodu, ör. "TTE"
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(100), index=True)  # Hisse Senedi, Para Piyasası...
    fund_type: Mapped[str | None] = mapped_column(String(10))  # YAT (yatırım), EMK (emeklilik), BYF
    company: Mapped[str | None] = mapped_column(String(255))  # kurucu portföy yönetim şirketi
    risk_level: Mapped[int | None] = mapped_column(Integer)  # 1 (en düşük) - 7 (en yüksek)
    is_active: Mapped[bool] = mapped_column(default=True)
    # Düzenleyici durum (app/services/fund_status.py): aktif / islem_kapali / islem_kapali_tasfiye.
    # Boşsa aktif sayılır. TEFAS'ın is_active'inden ayrıdır: SPK'nın kapattığı fon TEFAS'ta görünmeye devam edebilir.
    status: Mapped[str | None] = mapped_column(String(30), default="aktif")
    status_note: Mapped[str | None] = mapped_column(String(500))  # kullanıcıya gösterilen açıklama
    status_source: Mapped[str | None] = mapped_column(String(100))  # ör. "SPK Bülteni 2026/60"
    status_url: Mapped[str | None] = mapped_column(String(500))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (CheckConstraint("risk_level BETWEEN 1 AND 7", name="ck_fund_risk_level"),)

    prices: Mapped[list["Price"]] = relationship(back_populates="fund", cascade="all, delete-orphan")
    allocations: Mapped[list["PortfolioAllocation"]] = relationship(
        back_populates="fund", cascade="all, delete-orphan"
    )
    metrics: Mapped["FundMetrics | None"] = relationship(
        back_populates="fund", cascade="all, delete-orphan", uselist=False
    )


class Price(Base):
    """Fonun günlük fiyatı ve büyüklüğü (TEFAS 'Fon Getiri Bilgileri')."""

    __tablename__ = "prices"
    __table_args__ = (UniqueConstraint("fund_code", "date", name="uq_price_fund_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fund_code: Mapped[str] = mapped_column(ForeignKey("funds.code", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    price: Mapped[float] = mapped_column(Float)  # pay fiyatı (TL)
    total_value: Mapped[float | None] = mapped_column(Float)  # portföy büyüklüğü (TL)
    shares_outstanding: Mapped[int | None] = mapped_column(BigInteger)  # tedavüldeki pay sayısı
    investor_count: Mapped[int | None] = mapped_column(Integer)  # yatırımcı (kişi) sayısı

    fund: Mapped[Fund] = relationship(back_populates="prices")


class PortfolioAllocation(Base):
    """Fonun belirli bir tarihteki varlık dağılımı (yüzde)."""

    __tablename__ = "portfolio_allocations"
    __table_args__ = (
        UniqueConstraint("fund_code", "date", "asset_type", name="uq_alloc_fund_date_asset"),
        CheckConstraint("ratio >= 0 AND ratio <= 100", name="ck_alloc_ratio"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fund_code: Mapped[str] = mapped_column(ForeignKey("funds.code", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date)
    asset_type: Mapped[str] = mapped_column(String(100))  # Hisse Senedi, Devlet Tahvili, Altın, Mevduat...
    ratio: Mapped[float] = mapped_column(Float)  # yüzde, 0-100

    fund: Mapped[Fund] = relationship(back_populates="allocations")


class FundMetrics(Base):
    """Her fon için önceden hesaplanmış performans metrikleri.

    Fiyatlar her güncellendiğinde yeniden hesaplanır; API bu tabloyu okur,
    böylece liste sayfası 1000+ fonun metriklerini anında gösterebilir.
    Getiriler ve oranlar ondalık kesirdir (0.25 = %25).
    """

    __tablename__ = "fund_metrics"

    fund_code: Mapped[str] = mapped_column(ForeignKey("funds.code", ondelete="CASCADE"), primary_key=True)
    as_of: Mapped[date] = mapped_column(Date)  # hesaplamada kullanılan son fiyat tarihi
    last_price: Mapped[float] = mapped_column(Float)
    daily_change: Mapped[float | None] = mapped_column(Float)  # bir önceki işlem gününe göre
    ret_1m: Mapped[float | None] = mapped_column(Float, index=True)
    ret_3m: Mapped[float | None] = mapped_column(Float)
    ret_6m: Mapped[float | None] = mapped_column(Float)
    ret_1y: Mapped[float | None] = mapped_column(Float, index=True)
    ret_ytd: Mapped[float | None] = mapped_column(Float)  # yılbaşından bu yana
    ret_3y: Mapped[float | None] = mapped_column(Float)  # toplam (yıllıklandırılmamış)
    volatility_1y: Mapped[float | None] = mapped_column(Float)  # yıllıklandırılmış
    sharpe_1y: Mapped[float | None] = mapped_column(Float, index=True)
    max_drawdown_1y: Mapped[float | None] = mapped_column(Float)  # negatif sayı, ör. -0.12
    data_points: Mapped[int] = mapped_column(Integer)  # son 1 yıldaki fiyat sayısı
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    fund: Mapped[Fund] = relationship(back_populates="metrics")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))  # asla düz şifre saklanmaz
    full_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    risk_profiles: Mapped[list["RiskProfile"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RiskProfile(Base):
    """Risk anketi sonucu. Kullanıcı anketi tekrar doldurursa yeni satır eklenir, en sonuncusu geçerlidir."""

    __tablename__ = "risk_profiles"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_risk_score"),
        CheckConstraint("profile IN ('temkinli', 'dengeli', 'agresif')", name="ck_risk_profile"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    score: Mapped[int] = mapped_column(Integer)  # 0-100 toplam puan
    profile: Mapped[str] = mapped_column(String(20))  # temkinli / dengeli / agresif
    horizon_years: Mapped[int | None] = mapped_column(Integer)  # yatırım vadesi (yıl)
    answers: Mapped[dict] = mapped_column(JSON)  # {"soru_id": "cevap", ...}
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[User] = relationship(back_populates="risk_profiles")


class BacktestWindow(Base):
    """Kayan pencereli geriye dönük test: her seçim ayı, profil ve nitelikli yatırımcı seçeneği için
    örnek portföyün sonraki 12 aylık getirisi ve para piyasası medyanı. Gece güncellemesinden sonra
    yeniden hesaplanır (app/services/recommender.store_rolling)."""

    __tablename__ = "backtest_windows"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile: Mapped[str] = mapped_column(String(20), index=True)
    qualified: Mapped[bool] = mapped_column(default=False)
    start_date: Mapped[date] = mapped_column(Date)  # seçim günü
    end_date: Mapped[date] = mapped_column(Date)
    codes: Mapped[str] = mapped_column(String(200))  # virgülle ayrılmış fon kodları (eşit ağırlık)
    portfolio_return: Mapped[float] = mapped_column(Float)
    benchmark_return: Mapped[float] = mapped_column(Float)
    data_as_of: Mapped[date | None] = mapped_column(Date)  # hesaplamada kullanılan son fiyat tarihi
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

