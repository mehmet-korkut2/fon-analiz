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
- [x] Şüpheli fiyat sıçramaları için karar ver: SPK kararı ile işaretlendi (SPK Bülteni 2026/60, `python -m scripts.fon_durumu_isaretle`)
- [x] Portföy dağılımı kararı: özellik çıkarıldı. KAP raporları teknik olarak sınırda uygun (%73) ama KAP kullanım koşulu veriyi saklamayı yazılı izne bağlıyor; KAP verisi saklanmaz/gösterilmez, fon detayında sadece KAP bağlantısı var (`docs/rapor/02_veri_toplama.md`, 2.8)
- [x] Backend açılışında eksik günleri otomatik tamamla (bilgisayar 21:00'de kapalıysa)
- [ ] Ara değerlendirme: danışmana ilerlemeyi göster

## 3. Backend ve metrikler

- [x] Getiri hesapları: 1 ay, 3 ay, 6 ay, 1 yıl, 3 yıl, yılbaşından bu yana
- [x] Volatilite, Sharpe oranı, maksimum düşüş
- [ ] Kıyaslama: BIST 100, enflasyon, mevduat; beta
- [x] `fund_metrics` tablosu: metrikleri her gece önceden hesapla
- [x] Endpoint: fon detay (`GET /api/funds/{kod}`)
- [x] Endpoint: fiyat geçmişi (tarih aralığı parametresiyle)
- [x] Endpoint: karşılaştırma (`GET /api/compare?funds=A,B,C`)
- [x] Endpoint: sıralamalar (en iyi getiri, en düşük risk, en iyi Sharpe)
- [x] Fon listesine sayfalama, arama, kategori ve risk filtresi
- [x] Metrik testleri (bilinen örnek verilerle)

## 4. Frontend

- [x] Fon listesi: tablo, filtreler, arama, sıralama, sayfalama
- [x] Fon detay sayfası: bilgiler, metrik kartları, metrik açıklamaları
- [x] Fiyat grafiği (Recharts) ve dönem seçici
- [x] Teknik göstergeler: 50/200 günlük hareketli ortalama (açılıp kapatılabilir), 200 günlüğe göre trend etiketi, 52 haftalık aralık (`GET /api/funds/{kod}/technical`, `docs/rapor/04_frontend.md` 4.4)
- [ ] Yönetim ücreti: TEFAS'ta yok (15.10.2026 incelemesi: `fonBilgiGetir`, `fonProfilBilgiGetir` ücret alanı içermiyor); kaynak kararı bekliyor, KAP kullanılmayacak
- [x] Karşılaştırma sayfası: fon seçimi, 100'den başlayan grafik, metrik tablosu
- [x] Sıralamalar sayfası
- [ ] Taslaklardaki tasarımı uygula (renkler, yazı tipleri, yerleşim)
- [x] Yükleme, hata ve boş durum ekranları
- [x] Mobil uyum
- [ ] Favori fonlar
- [ ] Kullanıcı girişi (opsiyonel, zaman kalırsa)

## 5. Risk profili ve öneri ✅

- [x] Anket sorularını ve puanlamayı kesinleştir (7 soru + nitelikli yatırımcı sorusu; ayrıntı `docs/oneri_sistemi.md`)
- [x] Endpoint: `POST /api/risk-profile` (puan ve profil: temkinli / dengeli / agresif)
- [x] Anket ekranı
- [x] Öneri algoritması: risk değeri + Sharpe + getiri ağırlıklı puan
- [x] Endpoint: `GET /api/recommendations`
- [x] Öneri sayfası ve yasal uyarı metni
- [x] Profile göre örnek portföy ve geçmiş performansı (kayan pencereli geriye dönük test: son 3 yılda her ay seçim, 12 ay tutma)
- [x] Farklı profillerle test et, ağırlıkları ayarla (4 örnek kişi ve ağırlık duyarlılık analizi; ağırlıklar bilinçli olarak optimize edilmedi)

## 6. ML tahmin modülü ✅

- [x] Kaynak araştırması: ARIMA, Prophet, LSTM
- [x] Veri hazırlığı, zamana göre eğitim/test ayrımı (walk-forward: ayar 10.2023–09.2024, test 10.2024–09.2026)
- [x] Referans model: hareketli ortalama, naive tahmin (RMSE, MAE) (sıfır, drift, momentum)
- [x] ARIMA veya Prophet (ARIMA, 40 fonluk örnek)
- [x] LSTM: değerlendirildi, kapsam dışı bırakıldı (gerekçe: `docs/rapor/06_ml_tahmin.md`, 6.8)
- [x] Model karşılaştırma tablosu (rapora girecek) (`docs/rapor/06_ml_tahmin.md`; LightGBM drift'i geçemedi)
- [x] `forecasts` tablosu ve gece toplu tahmin
- [x] Endpoint: `GET /api/funds/{kod}/forecast`
- [x] Fon detayında tahmin çizgisi ve güven aralığı (geçmiş eğilime dayalı tahmin + konformal %80 aralık)
- [x] "Yatırım tavsiyesi değildir" uyarısı

> Zaman sıkışırsa en kolay sadeleştirilecek kısım bu aşama. Basit bir model de yeterli.

## 7. Test, yayın, rapor, sunum

- [ ] Uçtan uca test, hata düzeltme
- [ ] Tek tıkla başlatma: backend + frontend + tarayıcı birlikte açılsın
- [ ] İnternetsiz çalışma: döviz için son bilinen veri gösterilsin (sunumda bağlantı olmayabilir)
- [ ] Sunum öncesi veritabanı yedeği ve geri yükleme komutu
- [ ] Kullanıcı testi: 3–5 kişiye kullandır
- [ ] Rapor: giriş, literatür, yöntem, ML sonuçları, sonuç, kaynakça
- [ ] Sunum slaytları (10–15 slayt)
- [ ] Demo videosu (canlı demo bozulursa diye)
- [ ] Prova ve olası sorular
- [ ] README ve kod düzeni, teslim

> Uygulama yayına alınmayacak; sunumda kendi bilgisayarımda çalışacak. Yayınla ilgili maddeler aşağıda "Gelecek çalışmalar"da.

## Gelecek çalışmalar

Bitirme projesi kapsamı dışında bırakılan, yayına alma ve altyapı işleri:

- [ ] Veritabanı: Supabase veya Neon (PostgreSQL)
- [ ] Backend: Render
- [ ] Frontend: Vercel
- [ ] Günlük güncellemeyi Render Cron Job veya GitHub Actions'a taşı (ücretsiz Render sunucusu uykuya geçer)
- [ ] Alan adı (GitHub Student Pack ile ücretsiz)
- [ ] Alembic migration'larına geçiş

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
- Son fiyatı en güncel tarihten 7 günden eski olan fonlar (ör. TLY) "eski verili" sayılır: listede varsayılan olarak gizlenir, kategori sırasına ve risksiz getiri hesabına girmez.
