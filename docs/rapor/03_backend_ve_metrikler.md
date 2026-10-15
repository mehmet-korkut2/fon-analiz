# 3. Backend ve Metrikler

## 3.1 Amaç

Bu aşamada, toplanan fiyatlardan fonların performans ve risk metriklerini hesaplayan, sonuçları önceden hesaplayıp saklayan ve ön yüze hızlı bir JSON API sunan backend katmanını geliştirdik.

## 3.2 API

FastAPI [1] ile şu uç noktaları sunduk (`app/routers/`):

| Uç nokta | İşlev |
|---|---|
| `GET /api/funds` | Fon listesi: arama (Türkçe büyük harf duyarlı), kategori ve risk süzgeci, metriğe, fon büyüklüğüne ya da yatırımcı sayısına göre sıralama, sayfalama |
| `GET /api/funds/categories` | Kategoriler ve fon sayıları |
| `GET /api/funds/{kod}` | Fon detayı, metrikler, kategori içi sıra, SPK durumu, güncel büyüklük ve yatırımcı sayısı, KAP bağlantısı |
| `GET /api/funds/{kod}/prices` | Fiyat geçmişi (ay sayısı ya da tarih aralığı) |
| `GET /api/funds/{kod}/technical` | 50/200 günlük hareketli ortalama, trend, 52 haftalık aralık (Bölüm 4.4) |
| `GET /api/compare` | 2–4 fonun 100'den başlayan karşılaştırma serileri |
| `GET /api/rankings` | En yüksek getiri, en düşük volatilite, en yüksek Sharpe |
| `GET /api/risk-survey`, `POST /api/risk-profile` | Risk anketi ve profil (Bölüm 5) |
| `GET /api/recommendations`, `…/backtest` | Öneriler, örnek portföy, kayan pencereli test (Bölüm 5) |
| `GET /api/funds/{kod}/forecast`, `GET /api/ml/performance` | Tahmin ve model performansı (Bölüm 6) |
| `GET /api/fx`, `GET /api/status` | Döviz kurları, veri durumu |

Fon adları TEFAS'ta Türkçe büyük harfle tutulduğu ve SQLite'ın büyük-küçük harf eşleştirmesi Türkçe harfleri (İ, I, Ş, Ğ) tanımadığı için arama terimini Türkçe kurallarla büyük harfe çeviren bir yardımcı (`tr_upper`) yazdık.

## 3.3 Metrikler

Bütün oranlar ondalık kesir olarak saklanır (0,25 = %25). Tanımlar (`app/services/metrics.py`):

| Metrik | Tanım |
|---|---|
| Dönem getirisi (1, 3, 6 ay, 1 yıl, 3 yıl) | Son fiyat / dönem başındaki (ya da öncesindeki son) fiyat − 1; dönem başında 7 günden eski fiyat varsa hesaplanmaz |
| Yılbaşından bu yana | Son fiyat / önceki yılın son fiyatı − 1 |
| Volatilite (1 yıl) | Günlük getirilerin standart sapması × √252 |
| Sharpe oranı (1 yıl) [20] | (1 yıllık getiri − risksiz getiri) / 1 yıllık volatilite |
| Maksimum düşüş (1 yıl) | Bir zirveden sonraki en büyük yüzde kayıp |

3 yıllık getiri yıllıklandırılmadan, toplam getiri olarak gösterilir. Metrikler her gece bütün fonlar için yeniden hesaplanıp `fund_metrics` tablosuna yazılır. Bu işlem 1.071 fon için yaklaşık 8,5 saniye sürmektedir. Bu sayede liste sayfası binden fazla fonun metriklerini veritabanından tek sorguyla okuyabilmektedir.

13.10.2026 itibarıyla metriklerin kapsamı:

| Metrik | Hesaplanabilen fon |
|---|---|
| 1 yıllık getiri | 933 |
| 3 yıllık getiri | 583 |
| Volatilite | 1.050 |
| Sharpe oranı | 651 |

Eksik değerler, fonun yeterli geçmişinin olmamasından kaynaklanır. Sharpe için ayrıca Bölüm 3.5'teki eşik devrededir.

**Risksiz getiri.** Sharpe oranı için risksiz getiri olarak para piyasası fonlarının 1 yıllık medyan getirisini kullandık. 13.10.2026 itibarıyla bu değer %46,3'tür. Hesaba yalnızca güncel verili ve SPK kararıyla kapatılmamış para piyasası fonları girer. Sabit bir faiz oranı yerine bu yöntemi seçmemizin nedeni, değerin veriden otomatik güncellenmesi ve yatırımcının fon dünyası içinde gerçekten elde edebileceği "risksiz" getiriyi temsil etmesidir.

## 3.4 Eski verili ve işleme kapatılan fonlar

Son fiyatı en güncel tarihten 7 günden eski olan fonların 1 yıllık getirisi başka bir döneme ait olduğu için diğer fonlarla karşılaştırılamaz. Bu fonlar ve SPK kararıyla işleme kapatılan fonlar (Bölüm 2.7) şunlardan çıkarılır:

- fon listesinin varsayılan görünümü (bir seçenekle gösterilebilirler),
- kategori fon sayıları ve kategori içi sıra,
- sıralamalar,
- risksiz getiri hesabı.

Bu kurallar API testleriyle doğrulanmıştır.

## 3.5 Karşılaşılan sorun: Sharpe oranı ve pazartesi etkisi

Sıralamalar sayfasında en yüksek Sharpe oranları gerçek dışı görünüyordu:

| Fon | Sharpe oranı |
|---|---|
| NBH | 9,35 |
| PRU | 6,95 |
| KKL | 5,35 |
| LPH | 4,25 |
| HVT | 3,15 |

**İlk hipotez yanlış çıktı.** İlk hipotezimiz, fiyatı seyrek güncellenen fonların yapay olarak düşük volatilite gösterdiğiydi. Bunu sınamak için her fonun son bir yılında fiyatın değişmediği günlerin oranını hesapladık. Sharpe sıralamasının ilk 10'unda bu oran %0'dı. Kapatılmış ve eski verili olanlar dahil 1.067 fonun hiçbirinde de %5'i aşmıyordu. Yani bu veride seyrek güncelleme sorunu yoktu.

**Asıl nedeni grafikler gösterdi.** Bu fonlar kısa vadeli, para piyasası ve borçlanma fon sepeti türünden fonlardı. Fiyatları neredeyse düz bir çizgi biçiminde artıyor, volatiliteleri %1,6–3,6 arasında kalıyordu. Haftanın günlerine göre getirilere baktığımızda belirleyici bulguya ulaştık (Şekil 3.1):

- **PRU'da pazartesi getirisi diğer günlerin yaklaşık üç katıydı:** Pazartesi %0,390, diğer günler %0,128–0,132. Hafta sonunun faizi pazartesi fiyatına yansıyordu.
- **Ölçülen volatilitenin büyük kısmı risk değil, bu takvim etkisiydi.** Getiriyi takvim günü başına çevirdiğimizde PRU'nun volatilitesi %1,77'den %0,20'ye düştü.
- **Sonuç:** Paydası neredeyse sıfır olan Sharpe oranı anlamsız büyüyordu. Örneğin PRU için (58,6 − 46,3) / 1,8 ≈ 6,9.

![Şekil 3.1 Haftanın gününe göre ortalama getiri](gorseller/sekil_3_1_pazartesi.png)

**Çözüm.** Volatilite dağılımına baktık: fonların %10'unun volatilitesi %1,4'ün altında, ilk çeyreğin sınırı %3,1, medyan %13,3. Para piyasası benzeri fonlar ayrı bir küme oluşturuyordu (Şekil 3.2). Farklı eşikleri karşılaştırdık:

- **%3:** Yetersiz. LPH (4,25) ve IRF (2,84) zirvede kalıyordu.
- **%8 ve %10:** İlk 10'u değiştirmiyor, yalnızca daha fazla fonu dışarıda bırakıyordu.
- **%5:** Doğal kırılma noktası.

Bu yüzden **1 yıllık volatilitesi %5'in altındaki fonlarda Sharpe oranını hesaplamamaya** karar verdik. %5, SPK/ESMA risk göstergesi yönteminde 3. risk sınıfının üst sınırıdır [21].

- **Etkisi:** 318 fon Sharpe değeri almıyor. Bunların 164'ü serbest, 49'u katılım, 46'sı para piyasası fonu.
- **Arayüzde:** Bu fonlarda Sharpe yerine "volatilite çok düşük, Sharpe anlamlı değil" notu gösteriliyor.
- **Sonuç:** Eşikten sonra en yüksek Sharpe oranı 2,10'a (AES) indi; ilk 10 gerçek fiyat riski taşıyan fonlardan oluştu.

![Şekil 3.2 Sharpe oranı ve volatilite](gorseller/sekil_3_2_sharpe_vol.png)

## 3.6 Testler

Backend'de toplam 90 otomatik test vardır (`backend/tests/`). Testler şu alanları kapsar:

- **Metrik tanımları:** Bilinen sentetik serilerle.
- **API davranışları:** Süzme, sıralama, sayfalama, Türkçe arama, eski verili ve kapatılmış fonların dışlanması.
- **Diğer kurallar:** Veri kalitesi ve SPK işaretleme.
- **Diğer bölümler:** Öneri sistemi ve makine öğrenmesi modülü (Bölüm 5 ve 6).

Her değişiklikten sonra bütün testler çalıştırıldı.

## 3.7 Kısıtlar

- Fonların BIST 100, enflasyon ve mevduat ile kıyası ve beta katsayısı hesaplanmadı [DOLDUR: yapılırsa güncellenecek].
- Şema değişiklikleri bir migration aracıyla değil, açılışta eksik sütunları ekleyen bir yardımcıyla (`init_db`) yönetilmektedir; Alembic'e geçiş gelecek çalışmalara bırakıldı.
- Metrikler basit getiriler üzerinden hesaplanmaktadır; vergi, giriş-çıkış komisyonu gibi maliyetler hesaba katılmamaktadır (fon yönetim ücreti fiyata yansımıştır).
