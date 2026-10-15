# 7. Test ve Demo

> Bu bölüm iskelettir; 7. aşama tamamlandıkça doldurulacaktır.

## 7.1 Amaç

Bu aşamada uygulamanın uçtan uca doğru çalıştığını göstermeyi, sunumda kendi bilgisayarımızda ve gerekirse internet bağlantısı olmadan güvenilir biçimde çalıştırılmasını sağlamayı ve gerçek kullanıcılardan geri bildirim almayı amaçlıyoruz.

## 7.2 Otomatik testler

Backend'de 125 otomatik test bulunmaktadır (Bölüm 3.7; 15.10.2026). Ön yüz her değişiklikten sonra `npm run lint` ve `npm run build` ile denetlenmiştir.

**Tablo 7.1** Test dosyalarına göre otomatik testler

| Dosya | Kapsam | Test |
|---|---|---|
| `test_funds_api.py` | Fon listesi, detay, fiyat, teknik gösterge, büyüklük API'leri | 23 |
| `test_sanal_portfoy.py` | Sanal portföy ve "Ya o zaman alsaydım?" | 18 |
| `test_recommender.py` | Öneri puanı, portföy, geriye dönük test | 17 |
| `test_sources.py` | TEFAS, TCMB ve anlık kur ayrıştırıcıları | 10 |
| `test_risk_survey.py` | Risk anketi ve profil | 10 |
| `test_ml.py` | ML özellikleri, modeller, değerlendirme | 9 |
| `test_metrics.py` | Getiri, volatilite, Sharpe, maksimum düşüş | 8 |
| `test_updater.py` | Gece güncellemesi, büyüklük ve profil | 7 |
| `test_technical.py` | Hareketli ortalama, trend, 52 haftalık aralık | 7 |
| `test_models.py` | Veritabanı tabloları | 5 |
| `test_data_quality.py` | Tek günlük fiyat sıçramaları | 4 |
| `test_ml_job.py` | Gece tahmin işi | 3 |
| `test_fund_status.py` | SPK kararıyla kapatılan fonlar | 3 |
| `test_api.py` | Sağlık kontrolü | 1 |
| **Toplam** | | **125** |

## 7.3 Uçtan uca test

[DOLDUR: Senaryolar (fon arama → detay → karşılaştırma; anket → öneriler → planlayıcı), kullanılan yöntem ve sonuçlar.]

## 7.4 Yerel çalıştırma ve sunum hazırlığı

Uygulamayı şimdilik yayına almama, sunumda geliştiricinin bilgisayarında çalıştırma kararı aldık. Bu karar doğrultusunda planlanan işler:

- **Tek tıkla başlatma:** backend, frontend ve tarayıcının tek komutla açılması. [DOLDUR]
- **İnternetsiz çalışma:** döviz kurları için son bilinen değerlerin gösterilmesi. [DOLDUR]
- **Veritabanı yedeği ve geri yükleme komutu.** [DOLDUR]

## 7.5 Kullanıcı testi

[DOLDUR: Katılımcı sayısı (hedef 3–5), görevler, gözlemler, alınan geri bildirimler ve yapılan düzeltmeler.]

## 7.6 Demo

[DOLDUR: Sunum akışı, demo videosu bağlantısı, prova notları.]

## 7.7 Karşılaşılan sorunlar ve çözümleri

[DOLDUR]

## 7.8 Kısıtlar

[DOLDUR]
