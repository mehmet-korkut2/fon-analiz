# 4. Ön Yüz (Frontend)

## 4.1 Amaç

Bu aşamada, backend'in sunduğu verileri kullanıcıya anlaşılır, karşılaştırılabilir ve gerekçeli biçimde gösteren, telefon ekranında da kullanılabilen bir web arayüzü geliştirdik.

## 4.2 Sayfalar

Ön yüz React 19 [4] ve Vite ile yazılmış tek sayfalık bir uygulamadır; grafikler Recharts [5] ile çizilir.

| Sayfa | İçerik |
|---|---|
| Fonlar | Arama, kategori ve risk süzgeci, metriğe, fon büyüklüğüne ya da yatırımcı sayısına göre sıralama, sayfalama; eski verili ve işleme kapatılan fonları gösterme seçeneği (Şekil 4.1) |
| Fon detayı | Fiyat grafiği ve dönem seçici (1 ay – 5 yıl, yılbaşından bu yana), 50 ve 200 günlük hareketli ortalama, trend etiketi ve 52 haftalık aralık (Bölüm 4.4), fon büyüklüğü ve yatırımcı sayısı (TEFAS'ın güncel değeri), getiri ve risk kartları, kategori sırası, SPK uyarısı, 1 aylık tahmin konisi, yatırım hesaplayıcı ve fonun KAP sayfasına bağlantı (Şekil 4.2; bağlantı TEFAS'tan gelir, KAP verisi saklanmaz, bkz. Bölüm 2.8) |
| Karşılaştır | En fazla 4 fon; 100'den başlayan grafik, logaritmik ölçek seçeneği, satırdaki en iyi değeri vurgulayan metrik tablosu (Şekil 4.3) |
| Sıralamalar | En yüksek getiri (dönem seçilebilir), en düşük volatilite, en yüksek Sharpe; kategori süzgeci |
| Risk anketi | Sorular tek tek, ilerleme çubuğu; sonuç kartı |
| Öneriler | Profil özeti, gerekçeli 10 öneri, örnek portföy, portföy planlayıcı, kayan pencereli test özeti (Bölüm 5) |
| Model | Tahmin modelinin bütün test sonuçları (Bölüm 6) |
| Döviz ve Altın | TCMB ve anlık kaynak sekmeleri |

![Şekil 4.1 Fon listesi](gorseller/sekil_4_1_fon_listesi.png)

![Şekil 4.2 Fon detay sayfası: fiyat grafiği, tahmin konisi ve hesaplayıcı](gorseller/sekil_4_2_fon_detay.png)

![Şekil 4.3 Karşılaştırma sayfası](gorseller/sekil_4_3_karsilastirma.png)

## 4.3 Tasarım kararları

- **Türkçe biçimler:** Sayılar, yüzdeler ve tarihler Türkçe biçimde gösterilir (%12,5; 13.10.2026).
- **Renk paleti:**
  - Karşılaştırma ve model grafiklerinde dört renkli bir kategorik palet kullandık. Paleti renk körlüğü simülasyonunu da içeren bir doğrulama betiğiyle kontrol ettik: komşu renkler arasındaki en küçük fark ΔE 9,1 çıktı (hedef ≥ 8).
  - Sarı ve açık yeşilin beyaz zemin üzerindeki kontrastı düşük olduğu için bu grafiklerde lejant ve aynı verinin tablosu her zaman bulunur.
  - Bir fonun rengi, seçildiği yuvaya bağlıdır; listeden başka bir fon çıkarıldığında diğerlerinin rengi değişmez.
- **Uyarılar:** Her sayfanın altında "yatırım tavsiyesi değildir" uyarısı vardır. Öneri, hesaplayıcı ve planlayıcıda daha belirgin uyarı kutuları kullanılır.
- **Performans:** Grafik kütüphanesi büyük olduğu için grafikli sayfaları yalnızca açıldıklarında yükledik (lazy loading). İlk açılışta indirilen paket 700 kB'tan 297 kB'a indi.
- **Tarayıcıda saklama:** Risk profili ve karşılaştırma listesi tarayıcıda (`localStorage`) saklanır. Gizli pencerede erişilemezse sayfa yine çalışır, yalnızca hatırlamaz.

## 4.4 Teknik göstergeler

Fon detayındaki fiyat grafiğine üç basit teknik gösterge ekledik:

- **50 ve 200 günlük hareketli ortalama:** Son 50 ve 200 işlem gününün basit ortalaması. Grafikte iki ayrı çizgi olarak gösterilir ve kullanıcı her birini ayrı ayrı açıp kapatabilir; varsayılan olarak kapalıdır. Ortalamalar, grafikte seçilen dönemin başında da dolu olsun diye dönem başından 320 gün öncesinden itibaren hesaplanır. Pencere dolmadan (ör. 200 işlem gününden kısa geçmişi olan fonlarda) değer üretilmez.
- **Trend etiketi:** Son fiyat 200 günlük ortalamanın üstündeyse "Fiyat 200 günlük ortalamanın üstünde", altındaysa "altında" yazılır. Etiket yalnızca renkle değil, ok işareti (▲/▼) ve metinle de ayrışır.
- **52 haftalık aralık:** Son 52 haftanın en yüksek ve en düşük fiyatı, tarihleriyle birlikte. Son fiyatın bu aralıktaki yeri bir çubuk üzerinde ve yüzde olarak (%0 en düşük, %100 en yüksek) gösterilir. Fon 52 haftadan yeniyse başlık "… tarihinden beri aralık" olur.

Göstergeler backend'de hesaplanır (`app/services/technical.py`, `GET /api/funds/{kod}/technical`). Metriklerde olduğu gibi, tek gün sıçrayıp ertesi gün geri dönen hatalı fiyatlar hesaptan önce çıkarılır (Bölüm 3); fiyat verisi değiştirilmez. Trend ve 52 haftalık aralık grafikte seçilen dönemden bağımsızdır, her zaman son fiyat gününe göre hesaplanır.

14.10.2026 verisiyle fiyatı güncel ve işlemde olan 954 fonun 624'ünde fiyat 200 günlük ortalamanın üstünde, 260'ında altındadır; 70 fonun 200 günlük ortalama için yeterli geçmişi yoktur. En az 52 haftalık geçmişi olan 842 fonda son fiyatın aralıktaki yerinin medyanı %89'dur ve 412 fon aralığın üst %10'luk kısmındadır. Bu, fon fiyatlarının yüksek enflasyon ortamında çoğunlukla yükselme eğiliminde olmasıyla uyumludur; "zirveye yakın" olmak tek başına bir sinyal değildir.

Göstergelerin altında şu not yer alır: "Teknik göstergeler geçmiş fiyat hareketini özetler. Testlerimizde momentum ve 52 haftalık zirveye uzaklık gibi göstergeler gelecekteki getiriyi tahmin etmede basit ortalamadan daha iyi sonuç vermedi; hareketli ortalamalar ayrıca test edilmedi." Not, Bölüm 6'daki değerlendirmeye dayanır ve test edilenle edilmeyeni ayırır. Geçmiş getiri (momentum; 1, 3, 6 ve 12 aylık) ve 1 yıllık zirveye uzaklık, LightGBM modelinin özellikleri arasındaydı; ayrıca momentum tek başına bir referans yöntem olarak denendi. İkisi de fonun geçmiş ortalama getirisinin sürmesi varsayımını (drift) hiçbir risk grubunda geçemedi. 50 ve 200 günlük hareketli ortalamalar ise modelde ayrı bir özellik olarak denenmedi; bu yüzden onlar için bir başarı iddiasında bulunmuyoruz ve notta bunu açıkça belirtiyoruz. RSI ve MACD gibi daha karmaşık göstergeleri eklemedik: test etmediğimiz göstergeleri çoğaltmak kullanıcıya sinyal varmış izlenimi verebilir.

Grafik renkleri: 50 günlük ortalama turuncu (#c24a1a) düz çizgi, 200 günlük ortalama mor (#a83e8c) noktalı çizgidir. Fiyat (yeşil) ve tahmin (mavi) çizgileriyle birlikte dört renk, Bölüm 4.3'teki doğrulama betiğinden geçti (renk körlüğü simülasyonunda en küçük fark ΔE 6,5; bu nedenle 200 günlük ortalama ayrıca noktalı çizilir ve her çizginin lejantı vardır).

## 4.5 Mobil uyum

Arayüzü telefon genişliklerinde (360 ve 390 px) tarayıcının geliştirici protokolüyle açıp her sayfada yatay taşma olup olmadığını ölçtük; bütün sayfalarda sayfa genişliği ekran genişliğine eşittir. Geniş tablolar kendi kutuları içinde yatay kaydırılır.

![Şekil 4.4 Fon detay sayfası, 390 px genişlik](gorseller/sekil_4_4_mobil.png)

## 4.6 Karşılaşılan sorunlar ve çözümleri

| Sorun | Neden | Çözüm |
|---|---|---|
| Karşılaştırma sayfası 390 px'te 1.074 px genişliğe taşıyordu | Ekran okuyucu için gizlenen metinler (`.sr-only`, `position: absolute`) konumunu sayfaya göre alıp kaydırılabilir tablonun dışına çıkıyordu | Tablo kabına `position: relative` verildi; taşma ölçümle sıfırlandı |
| Telefon genişliğinde menü bağlantıları kelime kelime bölünüyordu | Bağlantıların satır kırma davranışı | Bağlantılar bölünmeden alt satıra geçecek şekilde düzenlendi |
| Grafik ekseninde aynı ay iki kez yazılıyordu ("Ara 25 Ara 25") | Kütüphanenin otomatik tik seçimi | Tikler her ayın ilk işlem gününden elle seçildi |
| Tahmin konisi grafikte görünmüyordu | Recharts 2, React Fragment içindeki serileri tanımıyor | Her seri ayrı koşulla eklendi |
| "%76'ini", "9'inde" gibi yanlış Türkçe ekler | Ekler sayıya göre değişiyor (%76'sını, 9'unda) | Metinler ek gerektirmeyen biçime çevrildi ("içerme oranı: %76", "9 / 24") |
| Büyük rakamlarda virgül etrafında boşluk | Eşit genişlikli yazı tipi | Büyük değerlerde normal yazı tipi + eşit genişlikli rakamlar |

## 4.7 Kısıtlar

- Kullanıcı girişi ve favori fonlar uygulanmadı; profil ve karşılaştırma listesi tarayıcıya bağlıdır.
- Koyu tema yoktur.
- Ana sayfa yalnızca veri durumunu gösteren basit bir sayfadır. [DOLDUR: sunum öncesi ana sayfa düzenlenirse güncellenecek.]
- "Taslaklardaki tasarımı uygula" maddesi henüz tamamlanmadı [DOLDUR].
