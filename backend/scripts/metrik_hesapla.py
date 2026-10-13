"""Tüm fonların metriklerini yeniden hesaplar.

    python -m scripts.metrik_hesapla
"""
import logging

from app.database import Base, SessionLocal, engine
from app.services.metrics_job import recompute_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        r = recompute_all(db)
    rf = f"%{r['risk_free_rate'] * 100:.1f}" if r["risk_free_rate"] is not None else "hesaplanamadı"
    print(f"\n{r['funds']} fonun metrikleri {r['seconds']} sn'de hesaplandı. Risksiz getiri: {rf}")
