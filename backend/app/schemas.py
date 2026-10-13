from datetime import date

from pydantic import BaseModel, ConfigDict


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


class FundDetail(FundOut):
    fund_type: str | None = None
    is_active: bool = True
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
