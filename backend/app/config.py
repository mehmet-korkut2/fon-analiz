from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./fon.db"
    frontend_url: str = "http://localhost:5173"

    # Günlük TEFAS güncellemesi
    scheduler_enabled: bool = True
    update_hour: int = 21
    update_minute: int = 0
    timezone: str = "Europe/Istanbul"
    catch_up_on_startup: bool = True  # açılışta veri eskiyse güncellemeyi hemen başlat

    # Sharpe oranı için yıllık risksiz getiri (ör. 0.40 = %40).
    # Boş bırakılırsa para piyasası fonlarının 1 yıllık medyan getirisi kullanılır.
    risk_free_rate: float | None = None

    # TCMB EVDS web servisi (TÜFE için; app/services/inflation.py). Anahtar yalnızca .env'de durur, git'e girmez,
    # hiçbir yerde yazdırılmaz ya da loglanmaz. Boşsa reel getiri bölümü "enflasyon verisi yok" der.
    evds_api_key: str | None = None

    # Kullanıcı oturumu (app/services/auth.py). Uygulama http://localhost'ta çalıştığı için Secure kapalı;
    # HTTPS ile yayına alınırsa COOKIE_SECURE=true yapılmalı.
    session_days: int = 14
    cookie_name: str = "fon_oturum"
    cookie_secure: bool = False

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
