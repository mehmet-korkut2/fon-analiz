# 8. Sonuç

## 8.1 Özet

Bu projede TEFAS'taki yatırım fonlarını analiz eden, karşılaştıran ve risk profiline göre eğitim amaçlı öneriler sunan bir web uygulaması geliştirdik.

**Veri ve metrikler.** Uygulama 1.071 yatırım fonunun beş yıllık 866.841 günlük fiyatını TEFAS'ın 2026'da değişen arayüzünden toplar ve her akşam günceller. Getiri, volatilite, Sharpe oranı ve maksimum düşüş metriklerini önceden hesaplar.

**Sayfalar.** Fon listesi, fon detayı (teknik göstergeler dahil), karşılaştırma, sıralamalar, risk anketi ve öneriler, sanal portföy, model performansı ve döviz sayfalarından oluşur.

**Testler.** Uygulamayı 131 otomatik testle ve gerçek tarayıcıda dört turda (açık/koyu tema, masaüstü/telefon) çalışan uçtan uca testle doğruladık.

**Sunum hazırlığı.** Uygulama sunum bilgisayarında tek tıkla açılır ve internet yokken de son verilerle çalışır.

Projenin ana çizgisi, her sonucu bir doğrulamaya bağlamak ve olumsuz sonuçları da göstermektir. SPK kararıyla kapatılan fonlar veriden silinmedi, işaretlendi. Öneri sisteminin geçmişte kıyası çoğunlukla geçemediği gösterildi. Basit bir referansı geçemeyen makine öğrenmesi modelinin tahminleri sitede kullanılmadı.

## 8.2 Katkılar

- **Değişen TEFAS arayüzü için çalışan bir veri hattı.** Belgelenmemiş yeni JSON adreslerinden fon listesi, fiyat geçmişi, güncel büyüklük ve profil bilgisi toplanır. Gece güncellemesi kaçırılan günleri tamamlar. İnternet yoksa sessizce atlanır, bağlantı koparsa durur (Bölüm 2, 7.4).
- **Veriyi değiştirmeden veri kalitesi yönetimi.** SPK kararıyla işleme kapatılan 117 fon iki ayrı durumla işaretlendi. Tek günlük hatalı fiyatlar yalnızca hesapta yok sayıldı; kaynaktan gelen fiyat hiçbir yerde değiştirilmedi (Bölüm 2.7).
- **Sharpe oranındaki takvim etkisinin tespiti.** Para piyasası benzeri fonlarda Sharpe oranının risk değil, hafta sonu faizinin pazartesiye yansıması yüzünden anlamsız büyüdüğünü gösterdik ve gerekçeli bir %5 volatilite eşiği getirdik (Bölüm 3.5).
- **Gerekçeli ve geçmişte sınanmış öneriler.** Her önerinin gerekçesi sayılarla üretilir. Yöntem, yalnızca seçim gününe kadarki veriyle 24 dönemlik kayan pencereli bir testten geçirildi; sonuçlar kıyası geçemediği dönemler de dahil sitede yayımlanır (Bölüm 5.6).
- **Önceden tanımlanmış ölçütle değerlendirilen ML çalışması.** Başarı ölçütü sonuçlar görülmeden tanımlandı. Olumsuz sonuç bütünüyle yayımlandı ve sitede, testte en isabetli çıkan yöntem ölçülmüş kapsama oranıyla gösterildi (Bölüm 6).
- **Veri kaynaklarının kullanım koşullarının sistematik incelenmesi.** Bütün kaynakların koşulları alıntılarla belgelendi. KAP verisi, teknik olarak kullanılabilir olduğu hâlde saklama yasağı nedeniyle kullanılmadı (Bölüm 2.8, 2.9).
- **TEFAS kurallarına yakın bir sanal portföy.** Emirler fonun valörüne ve son işlem saatine göre bekler. İleri fiyat kuralıyla bilinen bir fiyattan işlem yapılamaz (Bölüm 3.6).
- **Tutarlı ve erişilebilir arayüz.** Tek yerde tanımlanan tema ve koyu tema; WCAG AA kontrastı, klavyeyle gezinme ve telefonda yatay taşma olmaması ölçülerek doğrulandı (Bölüm 4.3).

## 8.3 Temel bulgular

**TEFAS'ın 2026 arayüz değişikliği.**

- TEFAS'ın eski uç noktaları kapandı. Fiyat geçmişi artık fon fon ve en fazla 60 ay geriye çekilebiliyor.
- Portföy dağılımı yayımlanmıyor. Fon büyüklüğü ve yatırımcı sayısı yalnızca güncel değer olarak alınabiliyor.
- TEFAS'ın işlem durumu alanı, SPK'nın kapattığı 117 fonun hepsi için "işlemde" dönüyordu. Bu nedenle fonların gerçek durumunu bu alandan değil, SPK bülteninden çıkarmak zorunda kaldık.
- Kullandığımız adresler resmî bir API değildir; önceden haber verilmeden değişebilir (Bölüm 2.2).

**SPK kararı ve veri kalitesi.**

- 1.071 fonun 41'inde, bir günde %30'dan büyük toplam 64 sıçrama bulduk. Bunların 4'ü ertesi gün geri dönen tek günlük hatalardı.
- Kalıcı sıçramaların 17'si aynı gün (09.10.2026) gerçekleşmişti. Nedeni SPK'nın 2026/60 sayılı bülteniydi: yedi portföy şirketinin bütün fonları işleme kapatılmış, listelenen fonların tasfiyesine karar verilmişti. Bu fonlardan 71'i "işleme kapalı", 46'sı "tasfiye" olarak işaretlendi.
- Tek günlük hatalar hesaptan çıkarılınca bir fonun 1 yıllık volatilitesi %87,3'ten %21,8'e indi (Bölüm 2.7).

**Pazartesi etkisi.**

- Sıralamada en yüksek Sharpe oranları 9,35'e kadar çıkıyordu. İlk hipotezimiz olan seyrek fiyat güncellemesi veride bulunmadı.
- Asıl neden takvimdi. Bir fonda pazartesi getirisi diğer günlerin yaklaşık üç katıydı (%0,390'a karşı %0,128–0,132). Getiri takvim günü başına çevrilince volatilitesi %1,77'den %0,20'ye düştü.
- %5 volatilite eşiğiyle 318 fon Sharpe değeri almadı ve en yüksek Sharpe 2,10'a indi (Bölüm 3.5).

**Öneri sisteminin kayan pencereli testi.**

- Son üç yılda her ay yalnızca o güne kadarki veriyle seçilip 12 ay tutulan örnek portföyler, para piyasası fonlarının medyanını 24 dönemin temkinli profilde 12'sinde, dengelide 5'inde, agresifte 9'unda geçti. Dönemlerin kıyas ortalaması %55,3 idi.
- Aynı dönemin verisiyle seçilen "son 1 yıl" sonucu ise kıyası geçiyordu (ör. dengeli %47,5'e karşı %46,3). Yani aynı veriyle seçip aynı veriyle ölçmek iyimser bir tablo çiziyor.
- Dengeli profil için koyduğumuz riskli fon kotası geçmiş testte sonucu kötüleştirdi (kotasız 8 / 24). Kotayı profil tutarlılığı gerekçesiyle tuttuk ve bunu açıkça yazdık (Bölüm 5.5, 5.6).

**Makine öğrenmesinin drift'i geçememesi.**

- 24 aylık walk-forward testte (17.261 tahmin) fazla getiri hatası fonun geçmiş ortalama getirisinin sürmesini varsayan drift'te %3,65, LightGBM'de %3,88 çıktı. Ay içi sıralama korelasyonu drift'te 0,155, LightGBM'de 0,054 oldu.
- LightGBM, önceden tanımlanan ölçütü dört risk grubunun hiçbirinde karşılayamadı.
- Fon bazında ARIMA drift'ten ayırt edilemedi (40 fonda %2,32'ye karşı %2,33). Bu, bir aylık fon getirilerinde öğrenilebilir yapının çok zayıf olduğunu gösteriyor.
- Drift'in konformal %80 aralığı test döneminde %75–77 kapsadı (Bölüm 6.6).

**Kaynakların kullanım koşulları ve KAP kararı.**

- KAP'ın portföy dağılım raporlarından veri çıkarmak teknik olarak sınırda mümkündü: örneklemin %73'ü üç kalıba indirgendi. Ancak KAP'ın kullanım koşulu bilgilerin MKK'nın yazılı izni olmadan "ileride kullanılmak üzere saklanamaz" olduğunu söylüyor. Bu nedenle KAP verisini hiç kullanmadık; fon detayında yalnızca TEFAS'ın verdiği KAP bağlantısı var.
- TEFAS ve Truncgil kullanımımızı yasaklayan bir hüküm bulmadık, ama açık bir izin de yok. Yayına alma ya da ticari kullanım hâlinde resmî veri ürünleri ve yazılı izin gerekecektir (Bölüm 2.8, 2.9).

## 8.4 Kısıtlar

Bölümlerdeki kısıtları üç başlıkta topluyoruz:

**Veri.**

- TEFAS erişimi resmî olmayan adreslere dayanır.
- Fiyat geçmişi beş yılla sınırlıdır ve tek bir yüksek faiz dönemini kapsar.
- Fonların geçmişteki risk değeri, kategorisi, büyüklüğü ve yatırımcı sayısı bilinmez; geçmiş tarihli hesaplarda güncel değerler kullanıldı ya da bu bilgiler hiç kullanılmadı.
- SPK kararları elle izlenir.
- Yalnızca yatırım fonları (YAT) yüklendi; emeklilik ve borsa yatırım fonları kapsam dışıdır.

**Yöntem.**

- Kayan pencereli test ve ML testi aynı tek faiz rejimini kapsar ve 24 dönemden oluşur. Dönemler örtüştüğü için bağımsız değildir; küçük farklar istatistiksel olarak ayırt edilemez.
- Öneri ağırlıkları uzman görüşüne dayanır, optimize edilmedi.
- Metriklerde ve sanal portföyde komisyon, stopaj ve alım-satım masrafı yoktur.
- Fonlar BIST 100, enflasyon ve mevduatla kıyaslanmadı; beta hesaplanmadı. [DOLDUR: kıyaslama yapılırsa bu madde güncellenecek.]

**Uygulama.**

- Tek kullanıcılıdır ve yereldir; kullanıcı girişi ve favoriler yoktur.
- Şema değişiklikleri bir migration aracıyla yönetilmez.
- İnternetsiz çalışma proxy ile canlandırılarak denendi.
- Ekran okuyucuyla deneme yapılmadı.
- Kullanıcı testi henüz yapılmadı (Bölüm 7.5).

## 8.5 Kapsam dışı bırakılanlar ve gerekçeleri

**Tablo 8.1** Kapsam dışı bırakılan özellikler

| Konu | Neden kapsam dışı | Ne olursa yapılabilir |
|---|---|---|
| Takas analizi | Takas (aracı kurum dağılımı) verisi borsada işlem gören paylar içindir; TEFAS'ta işlem gören yatırım fonları için karşılığı yoktur. Bir fonun içindeki hisselerin takas verisini kullanmak için fonun portföy içeriğini bilmek gerekirdi; portföy dağılımı da elimizde yok (Bölüm 2.8). Takas verisi ayrıca ücretsiz ve açık bir kaynaktan alınamıyor. [DOLDUR: takas verisinin lisans ve dağıtım koşulu kaynakla doğrulanacak.] | Lisanslı veri ve fon portföy içerikleri bulunursa borsa yatırım fonları için denenebilir |
| RSI, MACD gibi teknik göstergeler | Test ettiğimiz fiyat temelli özellikler (momentum, 1 yıllık zirveye uzaklık) bir aylık getiriyi drift'ten iyi tahmin etmedi (Bölüm 6.6). Test edilmemiş göstergeleri çoğaltmak kullanıcıda sinyal varmış izlenimi yaratabilirdi. Yalnızca geçmişi özetleyen 50/200 günlük ortalama ve 52 haftalık aralığı, "geleceği tahmin etmez" notuyla ekledik (Bölüm 4.4) | Göstergeler önce walk-forward düzeneğinde sınanır, işe yararsa gösterilir |
| Haber ve duygu analizi | Fon ve şirket haberlerinin başlıca kaynağı KAP'tır ve KAP verisi saklanamaz (Bölüm 2.8). Haber sitelerinin içeriği telif kapsamındadır. Türkçe finans metinleri için etiketli veri yoktur. Fiyat temelli sinyallerin bile drift'i geçemediği bir ufukta haberden ek fayda beklemek için gerekçe bulamadık | Lisanslı bir haber akışı ve etiketli veriyle ayrı bir araştırma olarak yapılabilir |
| Yönetim ücreti | TEFAS'ın sayfalarında ve uç noktalarında yok; resmî olarak izahnamede ve KAP'ta yayımlanır (Bölüm 2.9). Getiri hesaplarını etkilemez, çünkü ücret fiyata yansımıştır | MKK'nın izniyle ya da portföy şirketlerinin sitelerinin koşulları incelenerek |
| Portföy dağılımı | TEFAS yayımlamıyor; KAP raporları teknik olarak sınırda çıkarılabiliyor ama saklanmaları kullanım koşuluna aykırı (Bölüm 2.8) | MKK'nın yazılı izni alınırsa üç rapor kalıbı için ayrıştırıcı yazılabilir |
| Yayına alma | TEFAS dışarıya API sunmuyor; yayında Borsa İstanbul veri ürünleri gerekebilir (Bölüm 2.9). Ücretsiz sunucularda gece işi uyku nedeniyle güvenilir çalışmaz. Bitirme projesinin amacı için yerel sunum yeterli | Resmî veri lisansı, PostgreSQL ve zamanlanmış görev servisiyle |
| LSTM | Veri miktarı ve sinyalin zayıflığı; önceden belirlenen karar kuralı gereği LightGBM başarısız olunca denenmedi (Bölüm 6.8) | Daha uzun veri ve ek bilgi kaynaklarıyla |
| Kullanıcı girişi ve favoriler | Tek kullanıcılı yerel sunum için gerekmedi; kişisel veri işleme yükü getirirdi | Yayına alınırsa |

## 8.6 Gelecek çalışmalar

- **Kıyaslama:** Fonların BIST 100, enflasyon ve mevduat getirisiyle kıyası ve beta katsayısı.
- **Geçmişin biriktirilmesi:** Fon büyüklüğü, yatırımcı sayısı, risk değeri ve kategorinin her gün saklanması. Yeterli geçmiş oluşunca bu bilgiler geriye dönük testte sınanabilir (Bölüm 5.8).
- **Diğer fon türleri:** Emeklilik (EMK) ve borsa yatırım fonlarının (BYF) eklenmesi.
- **Farklı piyasa koşulları:** Öneri sisteminin ve ML'nin başka bir faiz rejimini kapsayan veriyle yeniden sınanması; LSTM'in bu durumda yeniden değerlendirilmesi (Bölüm 6.8).
- **Yayına alma:** PostgreSQL, backend ve ön yüz için barındırma, gece işinin zamanlanmış görev servisine taşınması, alan adı, Alembic'e geçiş. TEFAS verisi için resmî kaynak (Borsa İstanbul veri yayın ürünleri) (Bölüm 2.9).
- **İzne bağlı veriler:** MKK'nın yazılı izniyle KAP portföy dağılım raporlarından varlık dağılımı ve fonların yönetim ücreti (Bölüm 2.8, 2.9).
- **Kullanıcı özellikleri:** Kullanıcı girişi, favori fonlar, birden fazla sanal portföy, sanal portföyde komisyon ve stopaj.
- **Erişilebilirlik:** Ekran okuyucuyla deneme ve sayfada tema seçimi.

## 8.7 Kişisel değerlendirme

[DOLDUR: Projeden öğrendiklerin, zorlandığın yerler, yeniden yapsan neyi farklı yapacağın, yapay zekâ araçlarıyla çalışma deneyimin. Bu bölüm senin sesinle yazılmalı.]
