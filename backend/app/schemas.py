from datetime import date

from pydantic import BaseModel


class FundOut(BaseModel):
    code: str
    name: str
    category: str | None = None
    price: float | None = None
    price_date: date | None = None
