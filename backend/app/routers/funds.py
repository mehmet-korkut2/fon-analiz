from fastapi import APIRouter

from app.schemas import FundOut

router = APIRouter(prefix="/funds", tags=["funds"])

# Geçici örnek veri. TEFAS verisi veritabanına yüklenince buradan sorgulanacak.
SAMPLE_FUNDS = [
    FundOut(code="AAA", name="Örnek Hisse Senedi Fonu", category="Hisse Senedi", price=1.2345),
    FundOut(code="BBB", name="Örnek Para Piyasası Fonu", category="Para Piyasası", price=2.5000),
    FundOut(code="CCC", name="Örnek Altın Fonu", category="Kıymetli Madenler", price=0.8765),
]


@router.get("", response_model=list[FundOut])
def list_funds(category: str | None = None):
    if category:
        return [f for f in SAMPLE_FUNDS if f.category == category]
    return SAMPLE_FUNDS
