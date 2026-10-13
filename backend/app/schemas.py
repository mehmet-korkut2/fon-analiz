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
    volatility_1y: float | None = None
    sharpe_1y: float | None = None
    max_drawdown_1y: float | None = None


class FundOut(BaseModel):
    code: str
    name: str
    category: str | None = None
    risk_level: int | None = None
    price: float | None = None
    price_date: date | None = None
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
