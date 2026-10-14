# 2. Veri Toplama

## 2.1 Amaç

Bu aşamanın amacı, TEFAS'taki yatırım fonlarının bilgilerini ve beş yıllık günlük fiyat geçmişini güvenilir biçimde toplamak, her gün kendiliğinden güncellemek ve verinin doğruluğunu kaynağa karşı doğrulamaktır.

## 2.2 TEFAS'ın 2026 arayüz değişikliği

TEFAS [7] 2026'da veri sunma biçimini değiştirdi. Eski HTML/form tabanlı uç noktalar yerine sitenin kendi kullandığı iki JSON uç noktası üzerinden çalıştık (`app/services/tefas_client.py`):

- `/api/funds/fonGetiriBazliBilgiGetir`: fon listesi; kod, unvan, kategori, risk değeri ve işlem durumu.
- `/api/funds/fonFiyatBilgiGetir`: bir fonun fiyat geçmişi.

Değişikliğin bizi doğrudan etkileyen sonuçları:

- **Kaldırılan alanlar:** Portföy dağılımı, yatırımcı sayısı ve fon büyüklüğü artık yayımlanmıyor. Veritabanında bu alanlar boş kalabiliyor; varlık dağılımı özelliği şimdilik uygulanmadı (Bölüm 2.8).
- **Sınırlı fiyat geçmişi:** En fazla 60 ay geriye gidiyor ve dönem parametresi yalnızca 1, 3, 6, 12, 36 ve 60 ay olabiliyor. İstemci, istenen süreyi bunlardan en yakın büyüğüne yuvarlıyor.
- **Resmî olmayan erişim:** Uç noktalar resmî ve belgelenmiş bir API değil, sitenin kullandığı adresler. Siteyi yormamak için istekler arasında 0,5 saniye bekliyor, hata durumunda üç kez ve artan aralıklarla yeniden deniyoruz.

## 2.3 Veri yükleme ve günlük güncelleme

**İlk yükleme.** `scripts/tefas_yukle` betiği fon listesini ve her fonun son beş yıllık fiyatlarını yükler. Aynı fiyat iki kez yazılmaz, yalnızca eksik tarihler eklenir. Bütün fonların ilk yüklemesi yaklaşık 15 dakika sürmektedir.

**Günlük güncelleme.** `app/scheduler.py` hafta içi her gün saat 21:00'de (İstanbul) son bir ayın fiyatlarını çeker. Ardından sırasıyla şunları çalıştırır:

- metriklerin yeniden hesaplanması (Bölüm 3),
- SPK kararlarına göre fon durumlarının işaretlenmesi,
- kayan pencereli geriye dönük test (Bölüm 5),
- tahmin işi (Bölüm 6).

TEFAS günün fiyatlarını akşam yayımladığı için daha erken bir saat seçmedik.

**Kaçırılan günler.** Bilgisayar 21:00'de kapalıysa güncelleme kaçar. Bu nedenle backend her açılışta verinin beklenen son tarihe ulaşıp ulaşmadığına bakar ve gerekirse güncellemeyi hemen başlatır.

## 2.4 Veri kapsamı

![Şekil 2.1 Aylara göre fiyat verisi olan fon sayısı](gorseller/sekil_2_1_fon_sayisi.png)

| | |
|---|---|
| Fon (yatırım fonu, YAT) | 1.071 |
| Günlük fiyat kaydı | 866.841 |
| Tarih aralığı | 13.10.2021 – 14.10.2026 |
| Kategori | 9 |
| TEFAS risk değeri boş olan fon | 118 |

Emeklilik (EMK) ve borsa yatırım fonları (BYF) TEFAS listesinde yer alıyor; 3 tür birlikte 1.419 fon. Ancak proje kapsamında yalnızca yatırım fonlarını yükledik. Fon sayısı zamanla artmaktadır (Şekil 2.1); yeni fonların geçmişi kısa olduğundan bir yıllık metrikler yalnızca en az bir yıllık verisi olan fonlar için hesaplanabilmektedir.

## 2.5 Döviz ve altın kurları

Döviz ve altın sayfası için iki kaynak kullandık:

- **TCMB'nin günlük gösterge kurları (`today.xml`) [8]:** Resmî kaynak.
- **Truncgil Finans [9]:** Gün içi anlık kurlar. Resmî olmayan bir kaynak olduğu için arayüzde ayrı bir sekmede, kaynağı belirtilerek gösterilmektedir.

## 2.6 Veri doğrulama

Toplanan verinin doğruluğunu iki yolla kontrol ettik:

- **Elle kontrol:** 5 fonun fiyatlarını TEFAS sitesiyle karşılaştırdık; hepsi birebir eşleşti. [DOLDUR: kontrol edilen 5 fonun kodları ve tarihleri.]
- **Programla kontrol:** Şüpheli görünen fonların fiyatlarını TEFAS'tan yeniden çekip veritabanıyla gün gün karşılaştırdık. Bütün kontrollerde fark sıfır çıktı:

| Fon | Karşılaştırılan gün | Fark |
|---|---|---|
| TLY | 1.239 | 0 |
| YCK | 1.229 | 0 |
| DLZ | 477 | 0 |
| KHA, AC4, BPZ | 22 (son 1 ay) | 0 |

Bu kontroller, aşağıda anlatılan olağan dışı fiyat hareketlerinin yükleme hatasından değil, kaynağın kendisinden geldiğini göstermiştir.

## 2.7 Veri kalitesi: sıçramalar ve SPK kararı

**Şüpheli sıçramalar.** `scripts/veri_kalitesi` betiği, bir işlem gününden diğerine fiyatı %30'dan fazla değişen günleri listeler. Ertesi gün eski düzeye dönen sıçramaları "tek günlük hata" olarak ayırır. 1.071 fonun 41'inde toplam 64 sıçrama bulduk:

- **Tek günlük hata:** 4 sıçrama (YCK ve BFS fonlarında birer giriş-dönüş çifti).
- **Kalıcı sıçrama:** 60.

Kararımız, **fiyat verisini değiştirmemek** oldu. Tek günlük hatalı fiyatlar yalnızca metrik hesabında yok sayılmaktadır (`data_quality.drop_one_day_glitches`). Örneğin BFS fonunda bu temizlik, 1 yıllık volatiliteyi %87,3'ten %21,8'e, maksimum düşüşü −%35,8'den −%18,3'e indirmiştir.

**SPK kararı.** Kalıcı sıçramaların 17'si aynı gün, 09.10.2026'da gerçekleşmişti: Pardus, A1 Capital ve Bulls Portföy fonları %95–100 değer kaybetmişti. Bunların arasında, ekonomik olarak bu kadar değer kaybedemeyecek para piyasası fonları da vardı. Araştırmamız sonucunda nedeni belirledik: SPK'nın 17.09.2026 tarihli 2026/60 sayılı bülteniyle [10] Tera, Pusula, Hedef, Atlas, A1, Pardus ve Bulls Portföy'ün TEFAS'taki bütün fonları alım satıma kapatılmış ve bültende unvanı sayılan fonların tasfiyesine karar verilmişti [11], [12].

![Şekil 2.2 SPK kararıyla işleme kapatılan şirketlerin fonlarından örnekler](gorseller/sekil_2_2_spk_fonlari.png)

Bu karar üzerine şunları yaptık:

- **İki kararı ayrı ele aldık.** Haberlerde kararın tamamı "işleme kapatma ve tasfiye" olarak özetleniyordu. Oysa bülten metnine göre işleme kapatma bütün fonları, tasfiye ise yalnızca listelenen fonları kapsıyor. Bu yüzden iki ayrı durum tanımladık:
  - `islem_kapali`: Veritabanındaki 71 fon.
  - `islem_kapali_tasfiye`: Tasfiye listesinde unvanı geçen 46 fon.
- **Eşleştirmeyi doğruladık.** Fonları unvanlarına göre işaretleyen `scripts/fon_durumu_isaretle` betiğini yazdık. 09.10.2026'da düşen 17 fonun hepsi tasfiye listesinde çıktı; bu, eşleştirmenin doğruluğunu destekledi. Unvanı listedekinden yalnızca "(TL)" ekiyle ayrılan bir fonu (KSA) emin olamadığımız için yalnızca "işleme kapalı" saydık.
- **TEFAS'ın durum alanı kullanılamadı.** TEFAS'ın fon listesindeki işlem durumu alanı (`tefasDurum`), bu 117 fonun hepsi için "işlemde" dönüyordu. Yani durumu TEFAS'tan otomatik olarak alamıyoruz; işaretleme unvana göre yapılıyor.
- **Etkisi:** İşaretli fonlar listede varsayılan olarak gizlenir; sıralamalara, risksiz getiri hesabına ve önerilere girmez. Detay sayfalarında SPK bültenine bağlantılı bir uyarı gösterilir.

**Eski verili fonlar.** Son fiyatı en güncel tarihten 7 günden eski olan fonlar (13.10.2026 itibarıyla 8 fon, ör. TLY) "eski verili" sayılır ve aynı şekilde varsayılan görünümlerden çıkarılır.

## 2.8 Portföy dağılımı ve KAP

TEFAS'ın portföy dağılımını yayımlamayı bırakması nedeniyle fonların varlık dağılımını gösteren özellik uygulanamadı. Alternatif kaynak olarak Kamuyu Aydınlatma Platformu'ndaki (KAP) aylık portföy dağılım raporlarının kullanılabilirliği değerlendirilmektedir. [DOLDUR: KAP fizibilite sonucu ve KAP bildirimleri entegrasyonu; erişimin resmî olmayan yoldan yapıldığı ve kısıtları.]

## 2.9 Kısıtlar

- TEFAS ve Truncgil erişimi resmî ve belgelenmiş bir API'ye değil, sitelerin kullandığı adreslere dayanır; bu adresler önceden haber verilmeden değişebilir.
- Fiyat geçmişi beş yılla sınırlıdır.
- Fonların kategori ve risk değerinin geçmişteki hâlleri saklanmamaktadır; yalnızca güncel değerler bilinmektedir.
- SPK kararları elle izlenmekte ve işlenmektedir.
