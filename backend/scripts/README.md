# Betikler

Backend klasöründe, `.venv` aktifken çalıştır.

| Komut | Ne yapar |
|---|---|
| `python -m scripts.baglanti_testi` | TEFAS ve döviz kaynaklarına ulaşılabildiğini kontrol eder, örnek veriyi gösterir |
| `python -m scripts.tefas_yukle --limit 10` | İlk 10 fonun listesini ve son 5 yıllık fiyatlarını veritabanına yükler |
| `python -m scripts.tefas_yukle --fon TTE --ay 60` | Tek fonun son 5 yıllık fiyatlarını yükler |
| `python -m scripts.metrik_hesapla` | Tüm fonların getiri, volatilite, Sharpe ve maks. düşüş metriklerini yeniden hesaplar |
