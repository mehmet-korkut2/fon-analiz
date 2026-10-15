from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class MetricsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    as_of: date
    last_price: float
    daily_change: float | None = None
    ret_1m: float | None = None
    ret_3m: float | None = None
    ret_6m: float | None = None
    ret_1y: float | None = None
    ret_ytd: float | None = None
    ret_3y: float | None = None
    volatility_1y: float | None = None
    sharpe_1y: float | None = None
    sharpe_note: str | None = None  # Sharpe neden yok (ör. volatilite çok düşük)
    max_drawdown_1y: float | None = None


class FundOut(BaseModel):
    code: str
    name: str
    category: str | None = None
    risk_level: int | None = None
    price: float | None = None
    price_date: date | None = None
    is_stale: bool = False  # son fiyatı genel son tarihten STALE_AFTER_DAYS günden eski
    status: str = "aktif"  # aktif / islem_kapali / islem_kapali_tasfiye
    status_note: str | None = None
    status_source: str | None = None
    status_url: str | None = None
    # TEFAS'ın güncel değeri (geçmişi yok); info_date alındığı gün
    total_value: float | None = None
    investor_count: int | None = None
    info_date: date | None = None
    metrics: MetricsOut | None = None


class FundPage(BaseModel):
    items: list[FundOut]
    total: int
    page: int
    page_size: int
    sample: bool = False  # veritabanı boşken örnek veri döndüğünü belirtir


class CategoryOut(BaseModel):
    name: str
    count: int


class PricePoint(BaseModel):
    date: date
    price: float


class MaPoint(BaseModel):
    date: date
    ma50: float | None = None
    ma200: float | None = None


class Range52w(BaseModel):
    high: float
    high_date: date
    low: float
    low_date: date
    position: float | None = None  # 0 = 52 haftalık dip, 1 = zirve
    full: bool  # fon 52 haftadan yeniyse False
    since: date


class TechnicalSummary(BaseModel):
    as_of: date
    price: float
    ma50: float | None = None
    ma200: float | None = None
    trend: str | None = None  # ustunde / altinda / esit; 200 gün dolmadıysa boş
    range_52w: Range52w


class TechnicalOut(BaseModel):
    summary: TechnicalSummary
    series: list[MaPoint]


class FundDetail(FundOut):
    fund_type: str | None = None
    is_active: bool = True
    kap_url: str | None = None  # TEFAS profilindeki KAP bağlantısı
    buy_valor: int | None = None  # alış / satış valörü (iş günü), son işlem saati: sanal portföy
    sell_valor: int | None = None
    cutoff_time: str | None = None
    category_rank_1y: int | None = None  # kategorisinde 1 yıllık getiriye göre sırası
    category_size: int | None = None


class CompareFund(FundOut):
    period_return: float | None = None  # grafikteki dönemin getirisi


class ComparePoint(BaseModel):
    date: date
    values: dict[str, float | None]  # fon kodu -> base_date'te 100 olacak şekilde ölçeklenmiş fiyat


class CompareOut(BaseModel):
    funds: list[CompareFund]
    base_date: date
    points: list[ComparePoint]


class RankedFund(FundOut):
    rank: int
    value: float  # sıralamada kullanılan metriğin değeri


class RankingList(BaseModel):
    key: str  # return | volatility | sharpe
    metric: str  # ör. ret_1y
    order: str  # desc: büyük olan iyi, asc: küçük olan iyi
    items: list[RankedFund]


class RankingsOut(BaseModel):
    as_of: date | None
    category: str | None
    eligible: int  # sıralamaya giren (güncel verili, açık) fon sayısı
    lists: list[RankingList]


class SurveyOption(BaseModel):
    value: int  # puan (0-4); cevap olarak bu gönderilir
    text: str


class SurveyQuestion(BaseModel):
    id: str
    topic: str
    text: str
    weight: int
    scored: bool
    options: list[SurveyOption]


class ProfileRuleOut(BaseModel):
    profile: str
    label: str
    min_score: int
    risk_range: tuple[int, int]
    max_volatility: float | None
    description: str


class SurveyOut(BaseModel):
    questions: list[SurveyQuestion]
    qualified_question: SurveyQuestion
    max_raw: int
    profiles: list[ProfileRuleOut]


class ProfileIn(BaseModel):
    answers: dict[str, int]  # soru id -> seçilen cevabın puanı (0-4)
    qualified: bool = False


class CapOut(BaseModel):
    rule: str
    max_profile: str
    message: str


class ProfileOut(BaseModel):
    raw: int
    score: int
    profile: str
    label: str
    score_profile: str
    risk_range: tuple[int, int]
    max_volatility: float | None
    description: str
    qualified: bool
    caps: list[CapOut]


class RecommendationItem(FundOut):
    rank: int
    score: float  # 0-1, bileşen yüzdeliklerinin ağırlıklı toplamı
    components: dict[str, float]  # getiri, riske_gore, dusus, tutarlilik (0-1, 1 = en iyi)
    low_volatility: bool  # volatilite %5 altı: riske göre getiri fazla getiriyle ölçüldü
    quota: bool = False  # dengeli profilde riskli fon kotası yüzünden listeye girdi
    reasons: list[str]
    caution: str | None = None


class StatsOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_return: float = Field(serialization_alias="return")
    volatility: float | None
    max_drawdown: float


class PerfPoint(BaseModel):
    date: date
    portfolio: float
    benchmark: float


class PerformanceOut(BaseModel):
    start: date
    end: date
    portfolio: StatsOut
    benchmark: StatsOut
    benchmark_label: str
    benchmark_funds: int
    series: list[PerfPoint]


class PortfolioFund(BaseModel):
    code: str
    name: str
    category: str | None
    weight: float
    period_return: float | None = None  # performans dönemindeki getirisi
    pred_return: float | None = None  # 1 aylık drift tahmini (forecasts tablosu)
    lo: float | None = None  # %80 aralık
    hi: float | None = None


class PortfolioForecast(BaseModel):
    """Portföyün 1 aylık beklenen getirisi (fonların drift tahminlerinin ağırlıklı ortalaması) ve %80 aralık."""
    expected_return: float
    lo: float
    hi: float
    horizon_days: int
    interval_method: str  # aralığın nasıl hesaplandığı (kullanıcıya gösterilir)


class RecommendationsOut(BaseModel):
    profile: str
    label: str
    qualified: bool
    as_of: date | None
    risk_free_rate: float | None
    pool_size: int
    risk_range: tuple[int, int]
    max_volatility: float | None
    weights: dict[str, float]
    ra_mode: str
    category_limit: int
    items: list[RecommendationItem]
    portfolio: list[PortfolioFund]
    performance: PerformanceOut | None
    portfolio_forecast: PortfolioForecast | None = None


class BacktestWindowOut(BaseModel):
    start: date  # seçim günü
    end: date
    codes: list[str]
    portfolio_return: float
    benchmark_return: float
    excess: float  # portföy - para piyasası medyanı


class BacktestSummary(BaseModel):
    windows: int
    beats: int  # para piyasası medyanını geçtiği dönem sayısı
    mean_excess: float
    median_excess: float
    mean_portfolio: float
    mean_benchmark: float
    best: BacktestWindowOut
    worst: BacktestWindowOut


class BacktestOut(BaseModel):
    """Kayan pencereli geriye dönük test: son 3 yılda her ayın ilk işlem günü seçim, 12 ay tutma."""
    profile: str
    qualified: bool
    years: int
    horizon_months: int
    data_as_of: date | None
    summary: BacktestSummary | None  # tablo boşsa (henüz hesaplanmadıysa) None
    windows: list[BacktestWindowOut]


class ForecastOut(BaseModel):
    code: str
    as_of: date
    horizon_days: int
    method: str  # drift
    method_label: str
    pred_return: float
    lo: float  # %80 aralığın alt ucu
    hi: float
    risk_group: str
    risk_group_label: str
    coverage: float | None  # aralığın test dönemindeki kapsama oranı (bu risk grubunda)
    note: str  # "Bu bir ML tahmini değildir; ..."
    model_note: str | None = None  # LightGBM'in bu risk grubundaki sonucu


class MlPerformanceOut(BaseModel):
    created_at: str
    data_as_of: date
    report: dict  # app/ml/report.build_report çıktısı


# --- Sanal portföy -----------------------------------------------------------------

class SanalOrderIn(BaseModel):
    code: str
    side: str = Field(pattern="^(alis|satis)$")
    amount: float | None = None  # alış: TL
    units: int | None = None  # satış: pay adedi


class SanalResetIn(BaseModel):
    initial_balance: float


class SanalOrderOut(BaseModel):
    id: int
    code: str
    name: str
    side: str
    status: str
    created_at: datetime
    order_date: date
    valor: int
    valor_known: bool
    target_date: date
    amount: float | None = None
    units: int | None = None
    exec_date: date | None = None
    exec_price: float | None = None
    exec_units: int | None = None
    exec_amount: float | None = None
    note: str | None = None


class SanalPositionOut(BaseModel):
    code: str
    name: str
    category: str | None = None
    risk_level: int | None = None
    status: str
    units: int
    avg_cost: float | None = None
    cost: float
    price: float | None = None
    price_date: date | None = None
    value: float
    pnl: float | None = None
    pnl_pct: float | None = None
    realized: float
    sellable: int
    sell_valor: int | None = None


class SanalValueOut(BaseModel):
    date: date
    total: float
    cash: float
    holdings: float
    benchmark: float | None = None


class SanalOut(BaseModel):
    initial_balance: float
    start_date: date
    as_of: date | None = None
    total: float
    cash: float  # bloke dahil nakit
    reserved: float  # bekleyen alışlar için ayrılan
    available: float
    holdings: float
    pnl: float
    pnl_pct: float | None = None
    realized: float
    benchmark: float | None = None  # aynı para para piyasası medyanında olsaydı
    benchmark_pct: float | None = None
    positions: list[SanalPositionOut]
    pending: list[SanalOrderOut]
    history: list[SanalOrderOut]
    values: list[SanalValueOut]


class WhatIfFund(BaseModel):
    code: str
    name: str
    error: str | None = None
    category: str | None = None
    risk_level: int | None = None
    status: str | None = None
    status_note: str | None = None
    buy_date: date | None = None
    buy_price: float | None = None
    units: float | None = None
    last_date: date | None = None
    last_price: float | None = None
    value: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None
    days: int | None = None
    annualized: float | None = None  # 360 günden kısa dönemde boş
    mm_value: float | None = None
    mm_pct: float | None = None
    mm_annualized: float | None = None
    late_start: bool = False  # fonun ilk fiyatı seçilen tarihten çok sonra


class WhatIfOut(BaseModel):
    date: date
    amount: float
    as_of: date
    funds: list[WhatIfFund]
    mm_pct: float | None = None
    mm_value: float | None = None
    mm_start: date | None = None
    series: list[dict]  # {date, KOD: değer, ..., mm: değer}
