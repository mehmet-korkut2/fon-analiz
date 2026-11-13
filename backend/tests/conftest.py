"""Testler gerçek veritabanına (backend/fon.db) dokunmasın.

app.main içe aktarılırken init_db() çalışır ve eksik tabloları oluşturur; testler app.main'i içe aktardığı için
bu, gerçek fon.db'de tablo oluşturuyordu (ör. son sütunu eklenmeden önce oluşan forecast_days). Uygulama
modülleri içe aktarılmadan önce veritabanı geçici bir dosyaya yönlendirilir; zamanlayıcı da kapatılır.
Ortam değişkenleri .env dosyasından önce gelir (pydantic-settings).
"""
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="fon_test_"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["CATCH_UP_ON_STARTUP"] = "false"
os.environ["EVDS_API_KEY"] = ""  # testler gerçek EVDS anahtarını kullanmaz, internete çıkmaz


def pytest_sessionstart(session):
    from app.config import settings

    assert "fon.db" not in settings.database_url, "testler gerçek veritabanını kullanmamalı"
