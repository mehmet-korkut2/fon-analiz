# Betikler

Backend klasöründe, `.venv` aktifken çalıştır.

| Komut | Ne yapar |
|---|---|
| `python -m scripts.baglanti_testi` | TEFAS ve döviz kaynaklarına ulaşılabildiğini kontrol eder, örnek veriyi gösterir |
| `python -m scripts.tefas_yukle --limit 10` | İlk 10 fonun listesini ve son 5 yıllık fiyatlarını veritabanına yükler |
| `python -m scripts.tefas_yukle --fon TTE --ay 60` | Tek fonun son 5 yıllık fiyatlarını yükler |
| `python -m scripts.metrik_hesapla` | Tüm fonların getiri, volatilite, Sharpe ve maks. düşüş metriklerini yeniden hesaplar |
| `python -m scripts.veri_kalitesi` | Fiyat serilerinde bir günde %30'dan fazla değişen şüpheli sıçramaları listeler (`--esik`, `--fon`, `--csv`). Veritabanını değiştirmez |
| `python -m scripts.fon_durumu_isaretle` | SPK Bülteni 2026/60 kapsamındaki fonları işaretler (tasfiye / işleme kapalı). Önce TEFAS'taki `tefasDurum`'a bakar; `--deneme` ile sadece raporlar |
| `python -m scripts.oneri_analizi > ../docs/oneri_analizi_cikti.md` | Öneri sistemi analizleri (RA modu, ağırlık duyarlılığı, kayan pencereli test özeti, örnek kişiler, dengeli kota etkisi); markdown çıktı. Veritabanını değiştirmez |
| `python -m scripts.geriye_donuk_test` | Kayan pencereli geriye dönük testi hesaplar (son 3 yılda her ayın ilk işlem günü seçim, 12 ay tutma), `backtest_windows` tablosuna yazar ve özeti basar (~1 dk). Gece güncellemesi de bunu yapar; `--pencere` ile her dönemi listeler |
| `python -m scripts.ml_degerlendir --arima --kaydet` | ML walk-forward değerlendirmesi (referanslar, LightGBM, ARIMA, keşif varyantı); sonucu model performansı sayfası için kaydeder (~4,5 dk). `--kayittan` kayıtlı raporu markdown'a çevirir, `--ayar` hiperparametre ayarını yeniden yapar |
| `python -m scripts.rapor_gorselleri` | Rapor şekillerini veritabanından üretir (`docs/rapor/gorseller/*.png`). Ekran görüntüleri (Şekil 4.x, 5.3) elle alınır |
| `python -m scripts.rapor_olustur` | `docs/rapor/` bölümlerini birleştirip `docs/rapor/cikti/Bitirme_Raporu.docx` ve `.pdf` üretir (kapak, içindekiler, şekiller, tablolar). PDF ve içindekiler için Word gerekir; `--no-pdf` yalnızca docx. Bağımlılıklar: `pip install -r requirements-rapor.txt` |
