# Fon Analiz Platformu: Yol Haritası

Bitirme projesinin yapılacaklar listesi. Biten maddeyi `[ ]` yerine `[x]` yaparak işaretle.

Son güncelleme: 13 Ekim 2026

---

## 1. Hazırlık ve tasarım ✅

- [x] Proje fikri ve tanıtım yazısı
- [x] Geliştirme ortamı (Python, Node.js, Git, VS Code)
- [x] Proje iskeleti: FastAPI backend + React (Vite) frontend
- [x] GitHub reposu
- [x] Sistem mimarisi diyagramı
- [x] Veritabanı şeması (funds, prices, portfolio_allocations, users, risk_profiles)
- [x] Arayüz taslakları (ana sayfa, fon detay, karşılaştırma, risk anketi)

## 2. Veri toplama

- [x] TEFAS istemcisi (2026'daki yeni JSON API)
- [x] Veri yükleme betiği: `python -m scripts.tefas_yukle`
- [x] Fon bilgileri: kod, ad, kategori, risk değeri, işlem durumu
- [x] Günlük otomatik güncelleme (hafta içi 21:00)
- [x] Döviz ve altın: TCMB (resmi) + anlık kaynak, ayrı sayfa
- [x] Çift tıklamayla çalışan başlatma dosyaları (.bat)
- [x] Tüm fonları yükle: `python -m scripts.tefas_yukle --limit 0`
- [ ] Emeklilik (EMK) fonlarını ekle: `python -m scripts.tefas_yukle --tip EMK --limit 0`
- [x] Veri doğrulama: 5 fonun fiyatı TEFAS sitesiyle birebir eşleşti
- [ ] Portföy dağılımı kararı: TEFAS artık bu veriyi vermiyor. Başka kaynak (ör. KAP aylık raporları) bul ya da özelliği çıkar
- [ ] Backend açılışında eksik günleri otomatik tamamla (bilgisayar 21:00'de kapalıysa)
- [ ] Ara değerlendirme: danışmana ilerlemeyi göster

## 3. Backend ve metrikler

- [ ] Getiri hesapları: 1 ay, 3 ay, 6 ay, 1 yıl, 3 yıl, yılbaşından bu yana
- [ ] Volatilite, Sharpe oranı, maksimum düşüş (fonksiyonlar `app/services/metrics.py` içinde hazır, API'ye bağlanacak)
- [ ] Kıyaslama: BIST 100, enflasyon, mevduat; beta
- [ ] `fund_metrics` tablosu: metrikleri her gece önceden hesapla
- [ ] Endpoint: fon detay (`GET /api/funds/{kod}`)
- [ ] Endpoint: fiyat geçmişi (tarih aralığı parametresiyle)
- [ ] Endpoint: karşılaştırma (`GET /api/compare?funds=A,B,C`)
- [ ] Endpoint: sıralamalar (en iyi getiri, en düşük risk, en iyi Sharpe)
- [ ] Fon listesine sayfalama, arama, kategori ve risk filtresi
- [ ] Metrik testleri (bilinen örnek verilerle)
- [ ] Alembic migration'larına geçiş

## 4. Frontend

- [ ] Fon listesi: tablo, filtreler, arama, sıralama, sayfalama
- [ ] Fon detay sayfası: bilgiler, metrik kartları, metrik açıklamaları
- [ ] Fiyat grafiği (Recharts) ve dönem seçici
- [ ] Karşılaştırma sayfası: fon seçimi, 100'den başlayan grafik, metrik tablosu
- [ ] Sıralamalar sayfası
- [ ] Taslaklardaki tasarımı uygula (renkler, yazı tipleri, yerleşim)
- [ ] Yükleme, hata ve boş durum ekranları
- [ ] Mobil uyum
- [ ] Favori fonlar
- [ ] Kullanıcı girişi (opsiyonel, zaman kalırsa)

## 5. Risk profili ve öneri

- [ ] Anket sorularını ve puanlamayı kesinleştir (taslakta 5 soruluk çalışan sürüm var)
- [ ] Endpoint: `POST /api/risk-profile` (puan ve profil: temkinli / dengeli / agresif)
- [ ] Anket ekranı
- [ ] Öneri algoritması: risk değeri + Sharpe + getiri ağırlıklı puan
- [ ] Endpoint: `GET /api/recommendations`
- [ ] Öneri sayfası ve yasal uyarı metni
- [ ] Profile göre örnek portföy ve geçmiş performansı
- [ ] Farklı profillerle test et, ağırlıkları ayarla

## 6. ML tahmin modülü

- [ ] Kaynak araştırması: ARIMA, Prophet, LSTM
- [ ] Veri hazırlığı, zamana göre eğitim/test ayrımı
- [ ] Referans model: hareketli ortalama, naive tahmin (RMSE, MAE)
- [ ] ARIMA veya Prophet
- [ ] LSTM
- [ ] Model karşılaştırma tablosu (rapora girecek)
- [ ] `forecasts` tablosu ve gece toplu tahmin
- [ ] Endpoint: `GET /api/funds/{kod}/forecast`
- [ ] Fon detayında tahmin çizgisi ve güven aralığı
- [ ] "Yatırım tavsiyesi değildir" uyarısı

> Zaman sıkışırsa en kolay sadeleştirilecek kısım bu aşama. Basit bir model de yeterli.

## 7. Test, yayın, rapor, sunum

- [ ] Uçtan uca test, hata düzeltme
- [ ] Veritabanı: Supabase veya Neon (PostgreSQL)
- [ ] Backend: Render
- [ ] Frontend: Vercel
- [ ] Günlük güncellemeyi Render Cron Job veya GitHub Actions'a taşı (ücretsiz Render sunucusu uykuya geçer)
- [ ] Alan adı (GitHub Student Pack ile ücretsiz)
- [ ] Kullanıcı testi: 3–5 kişiye kullandır
- [ ] Rapor: giriş, literatür, yöntem, ML sonuçları, sonuç, kaynakça
- [ ] Sunum slaytları (10–15 slayt)
- [ ] Demo videosu (canlı demo bozulursa diye)
- [ ] Prova ve olası sorular
- [ ] README ve kod düzeni, teslim

---

## Sık kullanılan komutlar

En kolayı: proje klasöründeki .bat dosyalarına çift tıkla (1_backend_baslat, 2_frontend_baslat, 3_tum_fonlari_yukle, 4_backend_terminal).

Elle çalıştırmak istersen, backend (her yeni terminalde önce ilk iki satır):

```powershell
cd C:\Users\MONSTER\Desktop\fon-analiz\backend
.venv\Scripts\activate
uvicorn app.main:app --reload
pytest
python -m scripts.baglanti_testi
python -m scripts.tefas_yukle --limit 10
```

Frontend:

```powershell
cd C:\Users\MONSTER\Desktop\fon-analiz\frontend
npm run dev
```

Kaydetme:

```powershell
cd C:\Users\MONSTER\Desktop\fon-analiz
git add .
git commit -m "Ne yaptığını kısaca yaz"
git push
```

## Bilinen kısıtlar

- TEFAS 2026'da API'sini değiştirdi. Fiyat geçmişi en fazla 5 yıl geriye gidiyor. Portföy dağılımı, yatırımcı sayısı ve fon büyüklüğü artık yayınlanmıyor.
- Anlık döviz verisi gayriresmi bir kaynaktan (Truncgil Finans) geliyor. Resmi kur için TCMB sekmesi var.
- Günlük güncelleme sadece backend açıkken çalışıyor.
