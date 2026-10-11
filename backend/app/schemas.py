from pydantic import BaseModel


class FundOut(BaseModel):
    code: str
    name: str
    category: str | None = None
    price: float
