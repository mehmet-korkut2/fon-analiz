import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Fund
from app.services.fund_status import (
    SPK_2026_60_URL,
    STATUS_ACTIVE,
    STATUS_CLOSED,
    STATUS_LIQUIDATION,
    apply_status_rules,
    classify,
    liquidation_keys,
    match_company,
)


def test_company_match_by_name_prefix():
    assert match_company("TERA PORTFÖY BİRİNCİ SERBEST FON") == "Tera"
    # TEFAS'ta "CAPİTAL", başka kaynaklarda "CAPITAL" ya da bültendeki gibi "A1 Portföy"
    assert match_company("A1 CAPİTAL PORTFÖY PARA PİYASASI (TL) FONU") == "A1 Capital"
    assert match_company("A1 Capital Portföy Altın Fonu") == "A1 Capital"
    assert match_company("A1 PORTFÖY HİSSE SENEDİ FONU") == "A1 Capital"
    assert match_company("İŞ PORTFÖY BIST TEKNOLOJİ FONU") is None
    # şirket adı unvanın başında değilse eşleşmez (Hedef'in "Atlas" adlı fonu Hedef'tir)
    assert match_company("HEDEF PORTFÖY ATLAS İSTATİSTİKSEL ARBİTRAJ HİSSE SENEDİ SERBEST FON") == "Hedef"
    assert match_company(None) is None


def test_liquidation_list_vs_only_closed():
    assert len(liquidation_keys()) == 130
    # tasfiye listesinde: yazım farkları (Fon/Fonu, (TL)/(Tl), büyük/küçük harf) önemli değil
    assert classify("TERA PORTFÖY BİRİNCİ SERBEST FON") == STATUS_LIQUIDATION
    assert classify("PARDUS PORTFÖY İKİNCİ HİSSE SENEDİ (TL) FONU (HİSSE SENEDİ YOĞUN FON)") == STATUS_LIQUIDATION
    assert classify("BULLS PORTFÖY PARA PİYASASI (TL) FONU") == STATUS_LIQUIDATION
    # şirketin listede olmayan fonu: sadece işleme kapalı
    assert classify("TERA PORTFÖY BİRİNCİ BORÇLANMA ARAÇLARI (TL) FONU") == STATUS_CLOSED
    # "Hisse Senedi Fonu" ile "Hisse Senedi Serbest Fon" farklı fonlar
    assert classify("PARDUS PORTFÖY BİRİNCİ HİSSE SENEDİ (TL) FONU (HİSSE SENEDİ YOĞUN FON)") == STATUS_CLOSED
    assert classify("İŞ PORTFÖY BIST TEKNOLOJİ FONU") == STATUS_ACTIVE


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s


def test_apply_status_rules_marks_and_unmarks(db):
    db.add_all([
        Fund(code="TLY", name="TERA PORTFÖY BİRİNCİ SERBEST FON"),
        Fund(code="TRJ", name="TERA PORTFÖY BİRİNCİ BORÇLANMA ARAÇLARI (TL) FONU"),
        Fund(code="TTE", name="İŞ PORTFÖY BIST TEKNOLOJİ FONU", status=STATUS_CLOSED, status_note="eski not"),
    ])
    db.commit()
    counts = apply_status_rules(db)
    assert counts == {("Tera", STATUS_LIQUIDATION): 1, ("Tera", STATUS_CLOSED): 1}
    tly, trj, tte = db.get(Fund, "TLY"), db.get(Fund, "TRJ"), db.get(Fund, "TTE")
    assert tly.status == STATUS_LIQUIDATION and "tasfiye sürecindedir" in tly.status_note
    assert tly.status_source == "SPK Bülteni 2026/60" and tly.status_url == SPK_2026_60_URL
    assert trj.status == STATUS_CLOSED and "tasfiye" not in trj.status_note
    # kurallara uymayan eski işaret temizlenir
    assert tte.status == STATUS_ACTIVE and tte.status_note is None
    assert apply_status_rules(db) == counts  # tekrar çalıştırmak aynı sonucu verir
