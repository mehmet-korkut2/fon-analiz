"""Veritabanı tabloları.

funds ─┬─< prices                 (fonun günlük fiyat geçmişi)
       ├─< portfolio_allocations  (fonun varlık dağılımı)
       └── fund_metrics           (önceden hesaplanmış metrikler, 1:1)
users ─┬─< risk_profiles          (kullanıcının risk anketi sonuçları)
       ├─< sessions               (oturumlar; belirtecin özeti)
       ├─< favorites              (favori fonlar)
       ├── sanal_portfoy          (sanal portföy ayarı, 1:1)
       ├─< sanal_emirler, sanal_degerler
login_throttle                    (hatalı giriş sayaçları)
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
    # TEFAS fonBilgiGetir: sadece güncel değer (geçmişi yok), gece güncellemesinde yenilenir.
    # Geçmiş tarihlerin değeri olmadığı için öneri ve geriye dönük testte kullanılmaz.
    total_value: Mapped[float | None] = mapped_column(Float)  # portföy büyüklüğü (TL)
    investor_count: Mapped[int | None] = mapped_column(Integer)
    info_date: Mapped[date | None] = mapped_column(Date)  # büyüklük ve yatırımcı sayısının alındığı gün
    kap_url: Mapped[str | None] = mapped_column(String(500))  # TEFAS profilindeki kapLink (KAP'tan veri çekilmez)
    # TEFAS profili (fonProfilBilgiGetir): sanal portföyde emrin gerçekleşeceği günü belirler
    buy_valor: Mapped[int | None] = mapped_column(Integer)  # alış valörü, iş günü
    sell_valor: Mapped[int | None] = mapped_column(Integer)  # satış valörü, iş günü
    cutoff_time: Mapped[str | None] = mapped_column(String(5))  # son işlem saati ("17:45")
    profile_date: Mapped[date | None] = mapped_column(Date)  # profilin alındığı gün
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
    # Enflasyona göre 1 yıllık reel getiri (app/services/inflation.py): dönem sonu açıklanmış son TÜFE ayının son
    # günü (real_as_of); TÜFE verisi yoksa ya da fonun o günlerde fiyatı yoksa boş.
    real_ret_1y: Mapped[float | None] = mapped_column(Float)
    real_as_of: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    fund: Mapped[Fund] = relationship(back_populates="metrics")


class User(Base):
    """Kullanıcı hesabı (app/services/auth.py). E-posta küçük harfe çevrilerek saklanır."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))  # Argon2id; asla düz şifre saklanmaz
    full_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)

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
    qualified: Mapped[bool | None] = mapped_column()  # nitelikli yatırımcı beyanı
    result: Mapped[dict | None] = mapped_column(JSON)  # POST /api/risk-profile yanıtı (ProfileOut)

    user: Mapped[User] = relationship(back_populates="risk_profiles")


class UserSession(Base):
    """Oturum. Çerezdeki rastgele belirtecin yalnızca SHA-256 özeti saklanır; veritabanı sızsa bile
    oturum ele geçirilemez. Çıkış ve şifre değişikliğinde silinir (app/services/auth.py)."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)


class LoginThrottle(Base):
    """Art arda hatalı giriş sayacı (anahtar: "email:<adres>" ya da "ip:<adres>"). Eşik aşılınca
    locked_until'e kadar giriş denenemez; başarılı giriş e-posta sayacını sıfırlar."""

    __tablename__ = "login_throttle"

    key: Mapped[str] = mapped_column(String(300), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)


class Favorite(Base):
    """Kullanıcının favori fonları."""

    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "fund_code", name="uq_favorite"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    fund_code: Mapped[str] = mapped_column(ForeignKey("funds.code", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


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



SOURCE_LIVE = "canli"  # tahmin gününün gece işinde, o günkü veriyle kaydedildi
SOURCE_BACKFILL = "geriye_donuk"  # sonradan, yalnızca o tarihe kadarki veriyle hesaplandı


class ForecastDay(Base):
    """Gün gün tahmin (tahmin karnesi): her tahmin günü x fon x ufuk (1..21 işlem günü) için drift
    tahmini ve ufka göre kalibre edilmiş konformal %80 aralık (app/ml/horizons.py). Kayıtlar silinmez.
    Gerçekleşen fiyat burada tutulmaz, `prices`'tan okunur. Fiyatlar TL (fon birim fiyatı)."""

    __tablename__ = "forecast_days"
    __table_args__ = (UniqueConstraint("fund_code", "as_of", "horizon", "source", name="uq_forecast_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # fon sorgusu (fund_code, as_of) bu benzersiz indeksin önekini kullanır; ayrı fund_code indeksi gerekmez
    fund_code: Mapped[str] = mapped_column(ForeignKey("funds.code", ondelete="CASCADE"))
    as_of: Mapped[date] = mapped_column(Date, index=True)  # tahmin günü (o günün fiyatı biliniyor)
    base_price: Mapped[float] = mapped_column(Float)  # tahmin günündeki fiyat
    horizon: Mapped[int] = mapped_column(Integer)  # işlem günü, 1..21
    target_date: Mapped[date] = mapped_column(Date)  # takvimle hesaplanan hedef gün
    pred_price: Mapped[float] = mapped_column(Float)
    lo_price: Mapped[float] = mapped_column(Float)  # %10 dilimi
    hi_price: Mapped[float] = mapped_column(Float)  # %90 dilimi
    method: Mapped[str] = mapped_column(String(30))  # yöntem adı: drift-konformal
    # yöntemin sürümü (app/ml/horizons.METHOD_VERSIONS). Kayıt yapıldığı sürümle kalır; yöntem değişince
    # eski kayıtlar yeniden hesaplanmaz.
    method_version: Mapped[str] = mapped_column(String(12))
    source: Mapped[str] = mapped_column(String(12))  # canli | geriye_donuk
    risk_group: Mapped[str] = mapped_column(String(12))
    calib_n: Mapped[int | None] = mapped_column(Integer)  # aralığın kurulduğu geçmiş hata sayısı
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ForecastSummary(Base):
    """Tahmin karnesinin bütün fonlar üzerinden özeti (ufuk x risk grubu x kaynak); her gece yeniden
    hesaplanır, model performansı sayfası buradan okur. Yalnızca son satır kullanılır."""

    __tablename__ = "forecast_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    data_as_of: Mapped[date] = mapped_column(Date)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MlReport(Base):
    """ML walk-forward değerlendirme raporu (app/ml/report.build_report çıktısı, JSON)."""

    __tablename__ = "ml_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    data_as_of: Mapped[date] = mapped_column(Date)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SimilarityRun(Base):
    """Benzer fonlar / kümeleme hesabı (app/ml/similarity.py, ayda bir). payload: yöntem, k, silhouette eğrisi,
    kategorilerle örtüşme (ARI), kararlılık, küme adları ve özetleri."""

    __tablename__ = "similarity_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    data_as_of: Mapped[date] = mapped_column(Date)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FundCluster(Base):
    """Fonun kümesi (yalnızca son hesabın satırları tutulur)."""

    __tablename__ = "fund_clusters"

    run_id: Mapped[int] = mapped_column(ForeignKey("similarity_runs.id", ondelete="CASCADE"), primary_key=True)
    fund_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    cluster: Mapped[int] = mapped_column(Integer)
    silhouette: Mapped[float | None] = mapped_column(Float)


class FundNeighbor(Base):
    """Fona en çok benzeyen fonlar (haftalık getiri korelasyonu; yalnızca son hesabın satırları tutulur)."""

    __tablename__ = "fund_neighbors"

    run_id: Mapped[int] = mapped_column(ForeignKey("similarity_runs.id", ondelete="CASCADE"), primary_key=True)
    fund_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    rank: Mapped[int] = mapped_column(Integer, primary_key=True)
    neighbor_code: Mapped[str] = mapped_column(String(10))
    corr: Mapped[float] = mapped_column(Float)


# --- Sanal portföy (kullanıcıya özel, hayali para; app/services/sanal_portfoy.py) -----------------

class SanalAyar(Base):
    """Sanal portföyün başlangıç bakiyesi ve başlangıç günü (kullanıcı başına bir satır). user_id boşsa
    kullanıcı girişi öncesinden kalan portföydür; ilk açılan hesaba aktarılır (app/services/auth.py)."""

    __tablename__ = "sanal_portfoy"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    initial_balance: Mapped[float] = mapped_column(Float)
    start_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SanalEmir(Base):
    """Sanal alış/satış emri. Nakit ve pozisyonlar bu kayıtlardan hesaplanır (ayrı bakiye tutulmaz)."""

    __tablename__ = "sanal_emirler"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    fund_code: Mapped[str] = mapped_column(ForeignKey("funds.code"), index=True)
    side: Mapped[str] = mapped_column(String(5))  # alis / satis
    status: Mapped[str] = mapped_column(String(12), index=True)  # bekliyor / gerceklesti / iptal
    created_at: Mapped[datetime] = mapped_column(DateTime)
    order_date: Mapped[date] = mapped_column(Date)  # emrin sayıldığı iş günü (saat sonrası: ertesi iş günü)
    valor: Mapped[int] = mapped_column(Integer)
    valor_known: Mapped[bool] = mapped_column(default=True)  # False: TEFAS'ta valör yok, ertesi iş günü
    target_date: Mapped[date] = mapped_column(Date)  # bu gün (ya da sonraki ilk işlem günü) fiyatından gerçekleşir
    amount: Mapped[float | None] = mapped_column(Float)  # alış: istenen tutar (TL, emir verilince ayrılır)
    units: Mapped[int | None] = mapped_column(Integer)  # satış: istenen pay adedi
    exec_date: Mapped[date | None] = mapped_column(Date)
    exec_price: Mapped[float | None] = mapped_column(Float)
    exec_units: Mapped[int | None] = mapped_column(Integer)
    exec_amount: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(String(300))


class SanalDeger(Base):
    """Sanal portföyün günlük değeri; gece güncellemesinden ve her emirden sonra yeniden hesaplanır."""

    __tablename__ = "sanal_degerler"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    cash: Mapped[float] = mapped_column(Float)
    holdings: Mapped[float] = mapped_column(Float)
    total: Mapped[float] = mapped_column(Float)
    benchmark: Mapped[float | None] = mapped_column(Float)  # aynı para para piyasası medyanında olsaydı


class CpiMonth(Base):
    """Aylık TÜFE genel endeksi (TÜİK; TCMB EVDS web servisinden, app/services/inflation.py). Ay, ayın ilk günüyle
    tutulur. Kaynak koşulu: kaynak gösterilerek kullanılabilir ve yayımlanabilir (rapor 2.9 ve 3.8)."""

    __tablename__ = "cpi_monthly"

    month: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[float] = mapped_column(Float)
    series_code: Mapped[str] = mapped_column(String(40))  # TP.TUKFIY2025.GENEL
    fetched_at: Mapped[datetime] = mapped_column(DateTime)


class FxSnapshot(Base):
    """Döviz kaynağının (tcmb / canli) son başarılı yanıtı: internet yokken son bilinen kurlar gösterilir."""

    __tablename__ = "fx_snapshots"

    source: Mapped[str] = mapped_column(String(10), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime)
