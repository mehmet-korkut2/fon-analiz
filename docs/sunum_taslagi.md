# Sunum Taslağı (14 slayt)

Süre hedefi: 12–15 dakika anlatım + 4 dakikalık canlı demo (ya da `docs/demo_senaryosu.md`'deki video). Şekil ve tablo numaraları rapora göredir; görseller `docs/rapor/gorseller/` klasöründedir. Slaytlarda az yazı, büyük görsel; sayılar raporla aynı.

---

## 1. Fon Analiz Platformu

- TEFAS yatırım fonları için analiz, karşılaştırma ve eğitim amaçlı öneri
- Bilgisayar Mühendisliği Bitirme Projesi
- Mehmet Korkut · [DOLDUR: danışman, bölüm, tarih]

**Görsel:** Ana sayfa ekran görüntüsü, arka planda soluk (Şekil 4.1).

**Konuşmacı notu:** Türkiye'de bireysel yatırımcıya açık binden fazla yatırım fonu var. Bu projede bu fonları inceleyip karşılaştırmayı ve risk durumuna uygun olanları bulmayı kolaylaştıran bir web uygulaması geliştirdim. Önemli bir not: uygulama yatırım tavsiyesi vermez, eğitim amaçlıdır.

---

## 2. Problem ve amaç

- TEFAS'ta 1.071 yatırım fonu; resmî sayfalarda fiyat ve getiri var, risk karşılaştırması yok
- Kişinin vadesi ve kayıp toleransına uygun fonu seçmek uzmanlık istiyor
- Amaç: karşılaştırma, risk metrikleri, gerekçeli öneriler, ölçülmüş tahmin
- İlke: her sonuç doğrulanır, olumsuz sonuçlar da gösterilir

**Görsel:** Yok ya da TEFAS'ın fon listesi ile bizim fon listemizin yan yana küçük görüntüsü (Şekil 4.2).

**Konuşmacı notu:** Fonların getirisini görmek kolay, ama "bu fon ne kadar dalgalanıyor, kötü bir dönemde ne kadar kaybettiriyor, benim için uygun mu" sorularının cevabı dağınık. Projenin bütününde tek bir ilkeye bağlı kaldım: bir şeyi göstermeden önce doğrulamak ve işe yaramayan sonuçları da saklamamak.

---

## 3. Sistem mimarisi

- Backend: Python, FastAPI, SQLAlchemy, pandas; zamanlanmış gece işi
- Veritabanı: SQLite (tek dosya; yedeklenebilir)
- Ön yüz: React, Vite, Recharts; açık ve koyu tema, telefon uyumlu
- Uzun hesaplar gece önceden yapılır; API milisaniyede yanıt verir

**Görsel:** Şekil 1.1 Sistem mimarisi.

**Konuşmacı notu:** Veri TEFAS, TCMB ve anlık bir döviz kaynağından gelir. Metrikler, geriye dönük test ve tahminler her gece önceden hesaplanıp tablolarda saklanır; bu sayede sayfalar anında açılır. Uygulama yayına alınmadı, sunumda bu bilgisayarda internetsiz de çalışıyor.

---

## 4. Veri: TEFAS'ın 2026 değişikliği

- Eski arayüz kapandı; sitenin yeni JSON adresleri kullanıldı (resmî API yok)
- 1.071 fon, 866.841 günlük fiyat, 13.10.2021 – 14.10.2026
- Fiyat geçmişi en fazla 60 ay; portföy dağılımı artık yayımlanmıyor
- Doğrulama: yeniden çekilen fiyatlar veritabanıyla gün gün karşılaştırıldı, fark 0

**Görsel:** Şekil 2.1 Aylara göre fiyat verisi olan fon sayısı.

**Konuşmacı notu:** Proje başladığında TEFAS veri sunma biçimini değiştirmişti; eski kütüphaneler çalışmıyordu. Sitenin kendi kullandığı adreslerden veri topladım ve doğruluğunu kaynakla tekrar karşılaştırarak kontrol ettim. Grafikte fon sayısının zamanla arttığı görülüyor; yeni fonların geçmişi kısa olduğu için bazı metrikler hesaplanamıyor.

---

## 5. Veri kalitesi: SPK kararı

- 41 fonda 64 büyük sıçrama; 17'si aynı gün (09.10.2026), %95–100 düşüş
- Neden: SPK Bülteni 2026/60, yedi portföy şirketinin fonları işleme kapatıldı
- 117 fon işaretlendi (71 işleme kapalı, 46 tasfiye); veriden silinmedi
- TEFAS'ın "işlemde" alanı bu fonlarda yanlıştı; durum bültenden çıkarıldı

**Görsel:** Şekil 2.2 SPK kararıyla işleme kapatılan şirketlerin fonlarından örnekler.

**Konuşmacı notu:** Para piyasası fonlarının bir günde %99 değer kaybetmesi ekonomik olarak mümkün değil; önce bunun bir veri hatası olduğunu düşündüm. Araştırınca SPK kararını buldum. Bu fonları silmedim, işaretledim: güncel listelerde görünmüyorlar ama geçmiş testlerde duruyorlar, yoksa sonuçlar olduğundan iyi çıkardı.

---

## 6. Metrikler ve pazartesi etkisi

- Getiri, volatilite, Sharpe oranı, maksimum düşüş; her gece 1.071 fon için
- Sharpe 9,35'e kadar çıkıyordu: payda (volatilite) neredeyse sıfır
- Neden: hafta sonu faizi pazartesi fiyatına yansıyor (pazartesi getirisi ≈ 3 kat)
- Çözüm: volatilite %5'in altındaysa Sharpe hesaplanmaz; en yüksek Sharpe 2,10

**Görsel:** Şekil 3.1 Haftanın gününe göre ortalama getiri (ana); köşede Şekil 3.2.

**Konuşmacı notu:** İlk hipotezim fiyatı seyrek güncellenen fonlardı, veride bunu bulamadım. Haftanın günlerine bakınca nedeni gördüm: ölçülen küçük volatilitenin çoğu risk değil, takvim etkisi. %5 eşiği verideki doğal kırılma noktası ve Avrupa risk göstergesinde 3. sınıfın üst sınırı.

---

## 7. Arayüz

- Fon listesi: arama, süzme, metriğe ve büyüklüğe göre sıralama
- Fon detayı: grafik, 50/200 günlük ortalama, 52 haftalık aralık, risk kartları
- Karşılaştırma: 4 fona kadar, 100'den başlayan grafik
- Açık/koyu tema, telefonda yatay taşma yok, WCAG AA kontrast, klavyeyle gezinme

**Görsel:** Şekil 4.3 Fon detay sayfası (büyük) ve Şekil 4.4 Karşılaştırma; köşede Şekil 4.8 (390 px).

**Konuşmacı notu:** Arayüzü canlı demoda göstereceğim; burada yalnızca neler olduğunu özetliyorum. Teknik göstergelerin altında "bunlar geleceği tahmin etmez, testlerimizde basit ortalamadan iyi sonuç vermedi" notu var. Erişilebilirliği ölçerek doğruladım: bütün renk çiftleri WCAG AA kontrastını geçiyor.

---

## 8. Risk anketi ve öneriler

- 9 soru: vade ve kayıp toleransı en ağır; sınırlayıcı kurallar
- Temkinli / dengeli / agresif; TEFAS risk değeri ve volatilite sınırı
- Dört bileşen: fazla getiri, riske göre getiri, düşüş direnci, tutarlılık
- Her önerinin gerekçesi sayılarla yazılır; aynı kategoriden en fazla 2 fon

**Görsel:** Şekil 5.1 Öneriler sayfası; yanında Şekil 5.2 Risk değerine göre medyan getiri.

**Konuşmacı notu:** Bu dönemde düşük riskli fonlar hem daha çok kazandırdı hem hiç düşmedi; grafikte risk 1–2 fonların medyan getirisi %45, risk 7 fonlarınki %15. Bu yüzden dengeli profilin ilk sürümü tamamen para piyasası benzeri fonlardan oluşuyordu. Etiketle uyuşsun diye riskli fon kotası ekledim.

---

## 9. Öneriler geçmişte işe yaradı mı?

- Son 3 yıl, her ay: yalnızca o güne kadarki veriyle seç, 12 ay tut (24 dönem)
- Para piyasası medyanını geçtiği dönem: temkinli 12, dengeli 5, agresif 9 / 24
- Aynı veriyle seçip ölçmek iyimser: "son 1 yıl" kıyası geçiyor
- Kota geçmiş testte sonucu kötüleştirdi (8 → 5 / 24); açıkça yazıldı

**Görsel:** Şekil 5.3 Kayan pencereli test.

**Konuşmacı notu:** Bu slayt projenin en dürüst sonuçlarından biri. Yüksek faiz döneminde risk almak ödüllendirilmedi; öneri sistemi para piyasası fonlarının medyanını çoğunlukla geçemedi. Bunu sitede de kullanıcıya gösteriyorum.

---

## 10. Makine öğrenmesi: basit yöntemi geçemedi

- Hedef: 1 aylık getiri (fiyat değil); walk-forward test, 24 ay, 17.261 tahmin
- Başarı ölçütü sonuçlardan önce tanımlandı
- LightGBM drift'i 4 risk grubunun hiçbirinde geçemedi; ARIMA drift'le aynı
- Sitede ML tahmini yok: etiketli drift tahmini + ölçülmüş %80 aralık

**Görsel:** Tablo 6.1 (Drift ve LightGBM satırları vurgulu) ve Şekil 6.1 Aylık fazla getiri hatası.

**Konuşmacı notu:** Gelecekten bilgi sızdırmayan bir düzenekte, fonun geçmiş ortalamasının sürmesini varsayan basit yöntem en isabetlisi çıktı. LightGBM fonları birbirinden ayırt etmeyi öğrenemedi; sıralama korelasyonu 0,05. Bu yüzden başarısız modelin tahminlerini sitede göstermedim; bütün sonuçlar model performansı sayfasında açık.

---

## 11. Sanal portföy ve "Ya o zaman alsaydım?"

- Hayali parayla alış/satış; emirler TEFAS valörüne ve son işlem saatine göre bekler
- İleri fiyat: bilinen bir fiyattan işlem yapılamaz; alışta tutar bloke
- Para piyasası medyanıyla kıyas, günlük değer grafiği
- Geriye dönük: 4 fona kadar, tarih ve tutar; yıllıklandırılmış getiri

**Görsel:** Şekil 4.6 Sanal portföy ve Şekil 4.7 Ya o zaman alsaydım?

**Konuşmacı notu:** Fon alımının nasıl işlediğini deneyerek öğrenmek için sanal portföy ekledim. TEFAS'taki alan adları ters görünüyordu; hangisinin alış valörü olduğunu yabancı hisse fonlarının bilinen T+1, T+3 valörlerinden çıkardım. Her iki modda "hayali para, yatırım tavsiyesi değil" uyarısı en üstte.

---

## 12. Kaynakların kullanım koşulları

- Her kaynağın koşulu alıntıyla incelendi (TEFAS, TCMB, Truncgil, KAP)
- KAP: "MKK'nın izni olmadan ileride kullanılmak üzere saklanamaz"
- Portföy dağılımı teknik olarak mümkündü (%73) ama yapılmadı
- Yayına alma ya da ticari kullanımda resmî veri ürünleri gerekir

**Görsel:** Tablo 2.2 Veri kaynaklarının kullanım koşulları.

**Konuşmacı notu:** Teknik olarak yapabildiğim bir özelliği, kaynağın kullanım koşulu yasakladığı için yapmadım. Fon detayında KAP verisi yok, yalnızca TEFAS'ın verdiği KAP bağlantısı var. Bu karar yayına alma kararını da etkiledi.

---

## 13. Test ve sunum hazırlığı

- 131 otomatik test (metrikler, API, öneri, ML sızıntısı, sanal portföy, yedek)
- Uçtan uca test: açık/koyu, masaüstü/390 px; internetle 204/204, internetsiz 208/208
- Tek tıkla başlatma, internetsiz çalışma (son bilinen kurlar), yedek ve geri yükleme
- Kullanıcı testi: 6 görev, 5 soruluk anket [DOLDUR: katılımcı sayısı ve sonuç]

**Görsel:** Tablo 7.2 kontrol listesinin özeti ve Şekil 7.1 İnternet yokken döviz sayfası.

**Konuşmacı notu:** Arayüzü elle tıklayarak değil, gerçek tarayıcıda çalışan bir betikle bütün sayfalarda denedim. İnternet kesintisini de canlandırdım; bugün internet olmasa da bu sunum çalışırdı. [DOLDUR: kullanıcı testinden öne çıkan bir gözlem.]

---

## 14. Sonuç ve gelecek çalışmalar

- Katkılar: çalışan veri hattı, veri kalitesi yönetimi, takvim etkisinin tespiti, dürüst test
- Bulgu: kısa vadeli fon getirisi büyük ölçüde öngörülemez; basit yöntem en iyisi
- Kapsam dışı: takas ve haber analizi, RSI/MACD, yönetim ücreti, yayına alma
- Gelecek: BIST 100/enflasyon kıyası, geçmişin biriktirilmesi, başka faiz rejimi

**Görsel:** Yok; kısa bir özet cümlesi ve demo'ya geçiş.

**Konuşmacı notu:** Bu projede en çok, bir sonucu göstermeden önce doğrulamayı ve işe yaramayan bir modeli göstermemeyi öğrendim. Bundan sonraki adım, fonların büyüklüğünü ve risk değerini her gün saklayarak daha zengin bir geçmiş biriktirmek ve sistemi başka bir faiz döneminde sınamak olurdu. Şimdi kısa bir canlı demo göstereceğim. [DOLDUR: kendi kapanış cümlen.]

---

## Demo

`docs/demo_senaryosu.md`'deki akış (4 dk). Canlı demo bozulursa videoya geç. Sorular için `docs/juri_sorulari.md`.
