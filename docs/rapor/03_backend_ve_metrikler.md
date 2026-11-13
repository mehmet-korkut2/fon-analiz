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
| `GET /api/sanal-portfoy`, `POST …/emir`, `DELETE …/emir/{id}`, `POST …/sifirla` | Sanal portföy: özet, alış/satış emri, bekleyen emri iptal, sıfırlama (Bölüm 3.6) |
| `GET /api/sanal-portfoy/geriye` | "Ya o zaman alsaydım?": en fazla 4 fon, tarih ve tutar (Bölüm 3.6) |
| `GET /api/fx`, `GET /api/status` | Döviz kurları, veri durumu |

Fon adları TEFAS'ta Türkçe büyük harfle tutulduğu ve SQLite'ın büyük-küçük harf eşleştirmesi Türkçe harfleri (İ, I, Ş, Ğ) tanımadığı için arama terimini Türkçe kurallarla büyük harfe çeviren bir yardımcı (`tr_upper`) yazdık.

## 3.3 Metrikler

Bütün oranlar ondalık kesir olarak saklanır (0,25 = %25). Tanımlar (`app/services/metrics.py`):

| Metrik | Tanım |
|---|---|
| Dönem getirisi (1, 3, 6 ay, 1 yıl, 3 yıl) | Son fiyat / dönem başındaki (ya da öncesindeki son) fiyat − 1; dönem başında 7 günden eski fiyat varsa hesaplanmaz |
| Yılbaşından bu yana | Son fiyat / önceki yılın son fiyatı − 1 |
| Volatilite (1 yıl) | Günlük getirilerin standart sapması × √252 |
| Sharpe oranı (1 yıl) [23] | (1 yıllık getiri − risksiz getiri) / 1 yıllık volatilite |
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

Bu yüzden **1 yıllık volatilitesi %5'in altındaki fonlarda Sharpe oranını hesaplamamaya** karar verdik. %5, SPK/ESMA risk göstergesi yönteminde 3. risk sınıfının üst sınırıdır [24].

- **Etkisi:** 318 fon Sharpe değeri almıyor. Bunların 164'ü serbest, 49'u katılım, 46'sı para piyasası fonu.
- **Arayüzde:** Bu fonlarda Sharpe yerine "volatilite çok düşük, Sharpe anlamlı değil" notu gösteriliyor.
- **Sonuç:** Eşikten sonra en yüksek Sharpe oranı 2,10'a (AES) indi; ilk 10 gerçek fiyat riski taşıyan fonlardan oluştu.

![Şekil 3.2 Sharpe oranı ve volatilite](gorseller/sekil_3_2_sharpe_vol.png)

## 3.6 Sanal portföy

Kullanıcının hayali parayla fon alıp satarak deneme yapabildiği bir simülasyon ekledik (`app/services/sanal_portfoy.py`). Gerçek alım satım yapılmaz. Her kullanıcının kendi portföyü vardır ve yerel veritabanında saklanır (giriş gerekir; Bölüm 3.7). Üç tablo kullanılır: `sanal_portfoy` (başlangıç bakiyesi ve günü), `sanal_emirler` (bütün emirler) ve `sanal_degerler` (günlük portföy değeri). Tablolar açılışta `init_db()` ile oluşturulur.

**Defter yaklaşımı.** Nakit, pozisyonlar ve maliyet ayrıca saklanmaz; her seferinde emir kayıtlarından yeniden hesaplanır. Böylece bakiye ile işlemler arasında tutarsızlık oluşamaz. Maliyet ortalama maliyet yöntemiyle izlenir: kısmi satışta satılan payların maliyeti ortalama maliyetten düşülür, aradaki fark "gerçekleşen kâr/zarar" olur.

**TEFAS kurallarına yakın işlem.** Emirler hemen gerçekleşmez, bekleyen emir olarak kaydedilir:

1. *Emir günü.* Hafta sonu ya da fonun son işlem saatinden (TEFAS profilindeki `sonIsSaat`, ör. 17:45; para piyasası fonlarında 13:30) sonra verilen emir ertesi iş günü verilmiş sayılır.
2. *Valör.* Emir gününe fonun valörü kadar iş günü eklenir ve emir o günün fiyatından gerçekleşir. O gün tatilse (fiyat yoksa) sonraki ilk işlem gününün fiyatı kullanılır. Valör bilgisi olmayan fonlarda ertesi iş günü fiyatı kullanılır ve bu, emrin notunda yazar.
3. *İleri fiyat.* Hedef günün fiyatı emir verildiği anda zaten biliniyorsa (veritabanındaysa) emir bir sonraki iş gününe kayar. Böylece bilinen bir fiyattan işlem yapılamaz. Bu, gerçek fon işlemlerindeki "ileri fiyatlama" ilkesine karşılık gelir.
4. *Nakit ve pay.* Alış emrinde tutar emir verilince ayrılır (bloke); kullanılabilir nakitten fazla alış emri verilemez. Pay adedi tam sayıdır; tutarın 1 paya yetmeyen kısmı nakitte kalır. Satışta pay adedi girilir. Bekleyen satış emrindeki paylar yeniden satılamaz; satış tutarı nakde valör gününde geçer.
5. *Kısıtlar.* SPK kararıyla işleme kapatılan, TEFAS'ta işlem görmeyen ve eski verili (son fiyatı 7 günden eski) fonlar alınamaz. Komisyon, stopaj ve TEFAS'taki tutar/adet sınırları uygulanmaz.

Bekleyen emirler her gece güncellemeden sonra, ilgili günün fiyatı geldiğinde gerçekleşir. Aynı adımda portföyün başlangıç gününden son fiyat gününe kadar günlük değeri yeniden hesaplanır (`process()`). Fiyatlar metriklerdeki gibi tek günlük hatalardan arındırılır; veritabanındaki fiyat değiştirilmez.

**Valör alanlarının anlamı.** TEFAS profilinde iki alan vardır: `fonSatisValor` ve `fonGeriAlisValor`. Adlarına bakınca ilkinin yatırımcının alışı olduğu düşünülebilir. Ancak değerler bunun tersini gösterir. Yabancı hisse fonlarında (ör. GUH, AES) `fonGeriAlisValor` 1, `fonSatisValor` 3'tür; Türkiye'de bu fonlarda alım T+1, satım T+3 valörlüdür. Yurt içi hisse fonlarında değerler 1 ve 2'dir (alım T+1, satım T+2); para piyasası fonlarında ikisi de 0'dır. Bu nedenle alış valörü olarak `fonGeriAlisValor`'ü, satış valörü olarak `fonSatisValor`'ü kullandık. 15.10.2026'da 1.071 fonun profilini aldık: 1.065 fonun alış valörü vardır (142 fonda T+0, 923 fonda T+1); 6 fonda valör boştur ve bu fonlarda ertesi iş günü kuralı uygulanır. Satış valörlerinin dağılımı: T+0: 142, T+1: 159, T+2: 584, T+3: 177, T+4: 2 fon; 7 fonda boş. Profil 30 günde bir yenilenir.

**Kıyas.** Portföyün değeri, aynı başlangıç bakiyesinin portföyün başladığı gün para piyasası fonlarına (her gün, 100'den başlayan serilerin medyanı) yatırılmış olmasıyla kıyaslanır. Yöntem öneri sistemindeki kıyasla aynıdır (Bölüm 5).

**"Ya o zaman alsaydım?"** Geriye dönük modda kullanıcı en fazla 4 fon, bir tarih ve bir tutar seçer. Her fon, o tarihteki ya da sonraki ilk işlem günündeki fiyattan alınmış sayılır ve son fiyat gününe kadar tutulur. Bu modda pay kesirli kabul edilir, çünkü amaç fonları aynı tutarla karşılaştırmaktır. Sonuçta bugünkü değer, kâr/zarar (TL ve %), yıllıklandırılmış getiri ve aynı dönemde para piyasası medyanının getirisi gösterilir. Para piyasası kıyası her fon için o fonun kendi alış ve son fiyat günleri arasında hesaplanır; böylece seçilen tarihte henüz var olmayan ya da sonradan kapatılan bir fon da doğru dönemle kıyaslanır. Yıllıklandırma yalnızca yaklaşık 1 yıl (360 gün) ve daha uzun dönemlerde yapılır; daha kısa bir dönemi yıllığa çevirmek, tek bir iyi ayı yıllık %100'lerin üstünde göstererek yanıltıcı olurdu. SPK kararıyla kapatılan fonlar bu modda seçilebilir (geçmişte alınabiliyorlardı), ama sonuçta durumları belirtilir.

## 3.7 Kullanıcı girişi ve güvenlik

Sanal portföy, kaydedilmiş risk profili ve favori fonlar kullanıcıya özeldir; bunlar için hesap gerekir (13.11.2026). Fon listesi, fon detayı, tahmin karnesi, karşılaştırma, sıralamalar, risk anketi, öneriler, model performansı, döviz ve "Ya o zaman alsaydım?" hesaplayıcısı girişsiz kullanılabilir. Uç noktalar: `POST /api/auth/kayit`, `giris`, `cikis`, `sifre`, `DELETE /api/auth/hesap`, `GET /api/auth/ben`; kullanıcıya özel veriler için `GET/POST/DELETE /api/profilim` ve `/api/favoriler` (favori listesi her fon için metrikleri, kapatılmış/eski verili uyarısını, son tahminlerin aralıkta kalma özetini ve kullanıcının sanal portföyündeki pozisyonu da döndürür; Bölüm 4.6). Kod: `app/services/auth.py`, `app/deps.py`, `app/routers/auth.py`, `app/routers/account.py`.

**Şifre saklama.** Şifreler Argon2id ile özetlenir (`argon2-cffi`; zaman maliyeti 3, bellek 64 MiB, paralellik 4, 16 baytlık rastgele tuz; RFC 9106'nın önerdiği düşük bellekli ayar [25]). Bir özet ve bir doğrulama bu bilgisayarda yaklaşık 50 ms sürer. Argon2id'yi bcrypt'e tercih ettik: OWASP'ın şifre saklama rehberinde ilk sırada önerilen algoritmadır ve kullandığımız parametreler rehberdeki en düşük değerlerin üstündedir [26]; bellek zorlamalı olduğu için GPU ile toplu deneme yapmayı pahalılaştırır ve bcrypt'in 72 baytlık şifre sınırı yoktur. Düz şifre hiçbir tabloda ve günlükte bulunmaz; bunu bir test, veritabanının tamamını metne döküp şifreyi arayarak doğrular. Şifre kuralı en az 8, en çok 128 karakterdir. Üst sınır, çok uzun şifrelerle özet hesabını yavaşlatma girişimine karşıdır.

**Oturum: HttpOnly çerez, JWT değil.** Girişte 256 bitlik rastgele bir belirteç üretilir ve `HttpOnly`, `SameSite=Lax`, `Path=/api` özellikli bir çereze yazılır (14 gün). Veritabanında belirtecin kendisi değil, SHA-256 özeti saklanır; veritabanı ele geçirilse bile oturumlar kullanılamaz. JWT yerine sunucu tarafı oturumu seçmemizin nedenleri:

- *Geri alınabilirlik.* Çıkışta, şifre değişikliğinde ve hesap silinince oturum sunucuda silinir ve hemen geçersiz olur. JWT ise süresi dolana kadar geçerli kalır; iptal için yine sunucuda bir liste tutmak gerekir.
- *JavaScript erişimi.* HttpOnly çerez sayfadaki koddan okunamaz; bir XSS açığında belirteç çalınamaz. JWT'yi `localStorage`'da tutmak bu riski taşır.
- *Mimari.* Uygulama tek sunuculu ve aynı kökenlidir (frontend API'ye Vite proxy'si üzerinden erişir). JWT'nin asıl avantajı olan, birden fazla sunucuda veritabanına sormadan doğrulama burada gerekmez.

Girişte her zaman yeni belirteç verilir (oturum sabitlemeye karşı). Şifre değiştirilince diğer bütün oturumlar kapanır, mevcut oturum yeni belirteçle sürer. `Secure` bayrağı ayarla açılır (`COOKIE_SECURE`); uygulama `http://localhost`'ta çalıştığı için varsayılan olarak kapalıdır, HTTPS ile yayına alınırsa açılmalıdır.

**CSRF.** Çerez `SameSite=Lax` olduğundan başka bir siteden gönderilen POST isteklerine eklenmez. Buna ek olarak, oturum çerezi taşıyan ve durum değiştiren (POST, PUT, PATCH, DELETE) isteklerde `X-Requested-With` başlığı zorunludur. Başka bir sitedeki form bu başlığı ekleyemez; `fetch` ile eklenmeye çalışılırsa tarayıcı CORS ön kontrolü yapar ve izin verilen tek köken frontend'dir.

**Kaba kuvvet.** Hatalı girişler e-posta ve IP başına sayılır (`login_throttle` tablosu; uygulama yeniden başlasa da korunur). Aynı e-postaya art arda 5, aynı IP'den 20 hatalı denemeden sonra 30 saniye bekleme başlar; her yeni hata süreyi ikiye katlar (en çok 15 dakika). Beklemede doğru şifre de reddedilir ve yanıt `429` ile kalan süreyi (`Retry-After`) bildirir. Başarılı giriş e-posta sayacını sıfırlar; son hatadan 15 dakika sonra sayaç kendiliğinden sıfırlanır.

**Bilgi sızdırmama.** Yanlış şifre ile kayıtlı olmayan e-posta aynı mesajı alır ("E-posta ya da şifre hatalı."). Kayıtlı olmayan e-postada da sahte bir özet doğrulanır; yanıt süresinden e-postanın kayıtlı olup olmadığı anlaşılamaz. Başka bir kullanıcının emrini iptal etmeye çalışan 403 değil 404 alır; emrin varlığı da belli olmaz. Kayıt ekranında "bu e-posta kayıtlı" uyarısı ise kaçınılmazdır, çünkü e-posta doğrulaması yoktur.

**Kullanıcıya özel veri.** Sanal portföy tablolarına `user_id` eklendi ve bütün sorgular oturumdaki kullanıcıya göre süzülür. Gece güncellemesi her kullanıcının portföyünü ayrı işler. `sanal_degerler`'in birincil anahtarı (tarih) yerine (kullanıcı, tarih) oldu. SQLite birincil anahtarı değiştirmeye izin vermediği için bu tablo kaldırılıp yeniden kuruldu; tablo emirlerden türetildiği için veri kaybı olmaz. Kullanıcı girişinden önceki sanal portföy, açılan **ilk hesaba** aktarılır. Uçtan uca testin geçici hesapları RFC 2606'ya göre gerçek olamayacak `.example` uzantılı adresler kullanır ve bu aktarımı devralmaz. Risk profili girişli kullanıcıda `risk_profiles` tablosuna kaydedilir (geçmiş tutulur, en sonuncusu geçerlidir). Girişsiz kullanıcının profili yalnızca o oturumda tutulur; giriş yapınca hesaba aktarılır. "Hesabımı sil" şifre onayıyla hesabı ve bütün kişisel verileri (profil, sanal portföy, favoriler, oturumlar) siler.

**Tablo 3.1** Tehditler ve önlemler

| Tehdit | Önlem |
|---|---|
| Veritabanı sızıntısında şifrelerin çözülmesi | Argon2id, kullanıcıya özel tuz; düz şifre saklanmaz |
| Veritabanı sızıntısında oturumların ele geçirilmesi | Belirteç değil, SHA-256 özeti saklanır |
| XSS ile oturum çalınması | HttpOnly çerez; belirteç JavaScript'e hiç verilmez |
| CSRF | SameSite=Lax + çerezli yazma isteklerinde zorunlu `X-Requested-With` başlığı |
| Kaba kuvvet / şifre deneme | E-posta ve IP başına artan bekleme (30 sn → 15 dk), 429 |
| Kullanıcı adı (e-posta) keşfi | Tek hata mesajı; kayıtlı olmayan e-postada da sahte doğrulama |
| Oturum sabitleme | Girişte ve şifre değişikliğinde yeni belirteç |
| Çalınan cihazdaki oturum | Şifre değişince diğer oturumlar kapanır; 14 günlük süre |
| Başka kullanıcının verisine erişim (IDOR) | Bütün sorgular oturumdaki kullanıcıya göre süzülür; yabancı kayda 404 |
| Açık yönlendirme (`/giris?sonra=...`) | Yalnızca site içi yollar kabul edilir |

**Testler.** `tests/test_auth.py` (33 test): kayıt, giriş, yanlış şifre ve bilinmeyen e-postanın aynı yanıtı alması, art arda hatalı girişte bekleme ve sürenin ikiye katlanması, IP sınırı, çıkış sonrası eski belirtecin geçersizliği, süresi dolan oturum, giriş gerektiren 10 uç noktada girişsiz 401, herkese açık sayfaların girişsiz çalışması, CSRF başlığı, iki kullanıcının birbirinin portföyünü, emrini, favorisini ve profilini görememesi, şifre değişince diğer oturumların kapanması, giriş öncesi portföyün yalnızca ilk hesaba aktarılması, hesap silme. Kullanıcı süzgeci kasıtlı olarak kaldırıldığında veri ayrımı testinin kaldığını da denedik.

**Yerel şifre sıfırlama.** E-posta gönderen bir servis kurmadan, şifresini unutan kullanıcı için bilgisayardan çalışan bir komut ekledik: `python -m scripts.sifre_sifirla --eposta <adres>`. Yeni şifre ekrana yazılmadan iki kez sorulur (`getpass`); komut satırında, ortam değişkeninde ya da günlükte yer almaz. Şifre kuralı uygulanır, kullanıcının bütün açık oturumları kapatılır (başka cihazlarda giriş yapmış olsa da yeniden giriş yapması gerekir) ve hatalı giriş beklemesi sıfırlanır. Mevcut şifre sorulmaz; komutu yalnızca bu bilgisayardaki veritabanına erişebilen kişi çalıştırabildiği için bu, uygulamanın yerel çalışma biçimiyle uyumludur. `python -m scripts.hesaplar` hesapları listeler: yalnızca e-posta, ad ve oluşturma tarihi; şifre özeti sorguya hiç alınmaz. 9 test: eski şifrenin geçmemesi ve yeninin geçmesi, tarayıcıdaki oturumun kapanması, beklemenin sıfırlanması, kısa/uzun ve uyuşmayan şifrede şifrenin değişmemesi, kayıtlı olmayan e-postada şifre sorulmaması, yeni şifrenin ekrana basılmaması, hesap listesinde şifre bilgisi bulunmaması. Bu testlerden biri, şifre değiştikten sonra betiğin kapanmış veritabanı oturumuna erişip başarı mesajını yazamadan çöktüğü bir hatayı yakaladı; hata düzeltildi.

**Kısıtlar.** E-posta doğrulaması yoktur. Şifre sıfırlama kullanıcının kendisi tarafından yapılamaz; şifresini unutan kullanıcı, uygulamanın çalıştığı bilgisayarda yukarıdaki komutu çalıştırması için bilgisayarın sahibine başvurmalıdır (e-postayla sıfırlama, yayına alınırsa gerekir). İki aşamalı doğrulama yoktur. Kayıt ekranı bir e-postanın kayıtlı olduğunu söyler. Uygulama HTTPS olmadan yerelde çalıştığından çerezin `Secure` bayrağı kapalıdır.

## 3.8 Enflasyona göre reel getiri

Yüksek enflasyon ortamında bir fonun nominal getirisi tek başına yanıltıcıdır: fiyatı %30 artan bir fon, aynı dönemde fiyatlar genel düzeyi %30 arttıysa alım gücünü korumuştur, artırmamıştır. Bu nedenle her fon için enflasyona göre reel getiriyi hesapladık (13.11.2026). Kod: `app/services/inflation.py`.

**Veri ve seri.** TÜFE'yi TCMB EVDS web servisinden aylık olarak alıyoruz (kullanım koşulları Bölüm 2.9). TÜİK, Ocak 2026'dan itibaren TÜFE'nin baz yılını 2003=100'den 2025=100'e geçirdi [27]. Bu yüzden 2003=100 serisi EVDS'te arşive alınmış; yeni seri kodunu EVDS'in meta veri servisinden doğruladık: `TP.TUKFIY2025.GENEL` (veri grubu `bie_tukfiy2025`, "Genel Endeks", 01.2005–10.2026, kaynak TÜİK). Yeni seri 2005'e kadar geriye zincirlenmiş olarak yayımlandığı için eski seriyle ayrıca zincirleme yapmamız gerekmedi; fiyat verimiz 2021'den başlamaktadır. Yeni serinin geçmişinin tutarlılığını, 2003=100 tabanlı ve hâlâ güncellenen `TP.GENENDEKS.T1` serisiyle karşılaştırarak denetledik: 262 ayda iki serinin aylık değişimleri arasındaki en büyük fark 0,0066 puan, ortalama fark 0,0001 puandır (yuvarlama); Ekim 2025–Ekim 2026 enflasyonu iki seride de %29,77'dir. Reel getiri iki ayın oranını kullandığı için baz yılı sonucu etkilemez.

**Açıklanma ve güncelleme.** TÜİK TÜFE'yi genellikle sonraki ayın 3'ünde saat 10:00'da açıklar; hafta sonu ve tatillerde tarih kayar (2026'da Aralık verisi 5 Ocak'ta, Nisan verisi 4 Mayıs'ta açıklandı). Bir ayın verisi bu nedenle ay bittikten 3–5 gün sonra gelir; herhangi bir günde elimizdeki son TÜFE ayı en az 3, en çok yaklaşık 35 gün geridedir. Gece güncellemesi, beklenen ay veritabanında yoksa EVDS'ten son 12 ayı yeniden alır (olası düzeltmeler için) ve metriklerden önce çalışır. API anahtarı tanımlı değilse, internet yoksa ya da EVDS hata verirse hiçbir şey silinmez, son bilinen veriyle devam edilir; hiç veri yoksa arayüz "Enflasyon verisi yok" der. İlk yükleme `python -m scripts.tufe_yukle` ile yapılır (262 ay).

**Hesap ve dönem hizalaması.** Reel getiri = (1 + nominal getiri) / (1 + enflasyon) − 1. Yalnızca 1, 3, 6, 12 ve 36 aylık dönemlerde hesaplanır; aydan kısa dönemler için aylık TÜFE anlamlı değildir. Dönem sonu, açıklanmış son TÜFE ayının son günüdür (13.11.2026'da Ekim 2026 → 31.10.2026); dönem başı k ay önceki ayın son günüdür. Fon fiyatı o gün ya da öncesindeki son işlem gününün fiyatıdır (hafta sonuna denk gelen ay sonunda cuma fiyatı); en çok 7 gün eski olabilir. Enflasyon = TÜFE(son ay) / TÜFE(k ay önceki ay) − 1. Hangi aya kadar hesaplandığı ekranda yazar. Bu hizalama nedeniyle reel getiri tablosundaki nominal getiri, bugüne kadarki getiriden farklı olabilir (ör. TTE'nin bugüne kadarki 1 yıllık getirisi +%2,8, 31.10.2026'ya hizalı getirisi −%2,7). TÜFE ayın ortalama fiyat düzeyidir, fon fiyatı ise ay sonu değeridir; bu yaygın bir yaklaşımdır ve aylık dönemlerde küçük bir zamanlama farkı yaratır. Eksik TÜFE ayında ya da fonun dönem başında veya sonunda fiyatı yoksa sonuç boş kalır; tahmin edilmez.

**Platformda.** Fon detayında her dönem için nominal getiri, enflasyon ve reel getiri yan yana ve "✓ Enflasyonu yendi / ✗ Yenemedi" etiketiyle gösterilir. Fon listesinde "1 yıl reel" sütunu (sıralanabilir) ve "Yalnızca enflasyonu yenenler (1 yıl)" filtresi, sıralamalarda her fonun reel getirisi, "1 yıl reel" dönemi ve aynı filtre vardır. Sanal portföyde ve "Ya o zaman alsaydım?"da paranın alım gücü gösterilir: bugünkü değer / (1 + başlangıç ayından son TÜFE ayına enflasyon). Başlangıç ayının TÜFE'si henüz açıklanmadıysa alım gücü "henüz açıklanmadı" notuyla boş kalır.

**Ana sayfa özeti ve hayatta kalma yanılgısı.** Ana sayfada son 12 ayda enflasyonu yenen fonların payı kategoriye göre gösterilir. Yalnızca bugün aktif olan fonları saymak, dönem içinde kapanan ya da SPK kararıyla işleme kapatılan (çoğu sert değer kaybetmiş) fonları dışarıda bırakıp sonucu iyimser gösterebilir. Bu yüzden dönem başında fiyatı olan her fonu saydık; dönem içinde fiyatı kesilen fonun dönem sonu değeri son fiyatıdır. Karşılaştırma için yalnızca bugün aktif olanlarla hesaplanan pay da ekranda yazar.

**Tablo 3.2** Son 12 ayda (31.10.2025–31.10.2026, TÜFE %29,77) enflasyonu yenen fonların payı

| Kategori | Tüm fonlar (dönem başında fiyatı olan) | Yalnızca bugün aktif olanlar |
|---|---|---|
| **Tümü** | **%36,6 (348 / 950)** | %37,5 (319 / 851) |
| Serbest | %32,6 (356) | %34,8 (302) |
| Hisse Senedi | %8,3 (168) | %6,0 (151) |
| Değişken | %43,7 (135) | %42,6 (129) |
| Fon Sepeti | %34,2 (79) | %33,8 (77) |
| Katılım | %57,9 (76) | %59,7 (72) |
| Borçlanma Araçları | %70,0 (60) | %69,1 (55) |
| Para Piyasası | %91,3 (46) | %100,0 (39) |
| Kıymetli Madenler | %0,0 (23) | %0,0 (19) |
| Karma | %57,1 (7) | %57,1 (7) |

İki evren arasındaki 99 fonun 6'sının fiyatı dönem içinde kesilmiş, 93'ü SPK kararıyla işleme kapatılmış ama fiyatı yayımlanmaya devam etmiştir. Genel fark 0,9 puandır; kategori bazında fark büyüyebilir: para piyasası fonlarında yalnızca aktif fonlar sayılsaydı oran %100 görünürdü, kapatılanlarla birlikte %91,3'tür.

**Öneri sistemi.** Öneri puanlaması değiştirilmedi; reel getiri yalnızca gerekçe metnine eklendi ("… sonuna kadar son 1 yılda enflasyonu yendi: reel getirisi …"). Puanlamayı değiştirmek, geriye dönük testteki seçimleri (Bölüm 5) bugünkü sonuçlarla kıyaslanamaz hâle getirirdi. Bir test, TÜFE eklenip reel getiri hesaplandıktan sonra önerilerin, örnek portföyün ve geriye dönük test sonuçlarının birebir aynı kaldığını doğrular.

**Testler.** `tests/test_inflation.py` (21 test): EVDS yanıtının ayrıştırılması ("2005-1" gibi sıfırsız aylar, boş değerler), anahtarın yalnızca başlıkta gönderilmesi ve hiçbir hata mesajında, sonuçta ya da günlükte yer almaması, anahtar yokken, internet yokken ve EVDS hata verirken verinin korunması, beklenen ay hesabı (ayın 3'ü ve yıl geçişi), formül, dönem hizalaması (hafta sonuna denk gelen ay sonu, TÜFE'den sonraki fiyatların kullanılmaması), eksik ay ve eksik fiyat, alım gücü, liste ve sıralama filtreleri, hayatta kalma yanılgısına karşı özet, özet önbelleği. Ayrıca öneri değişmezliği testi (`test_recommender.py`). Uçtan uca teste ana sayfa özeti, liste ve sıralama filtreleri, fon detayındaki tablo ve alım gücü adımları eklendi.

**Kısıtlar.** TÜFE ayın ortalama fiyat düzeyidir, fon fiyatı ay sonu değeridir. Son TÜFE ayı en çok yaklaşık 35 gün geride kaldığı için reel getiri bugüne kadarki getiriyle aynı dönemi kapsamaz. Vergi ve komisyon hesaba katılmaz. Enflasyon, bireyin kendi harcama sepetini değil, TÜİK'in genel sepetini yansıtır.

## 3.9 Testler

Backend'de toplam 223 otomatik test vardır (`backend/tests/`; dosyalara göre dağılım Tablo 7.1'de). Testler şu alanları kapsar:

- **Metrik tanımları:** Bilinen sentetik serilerle.
- **API davranışları:** Süzme, sıralama, sayfalama, Türkçe arama, eski verili ve kapatılmış fonların dışlanması.
- **Diğer kurallar:** Veri kalitesi ve SPK işaretleme; teknik göstergeler; fon büyüklüğünün öneriye katılmaması.
- **Veri toplama ve çalışma ortamı:** TEFAS ve döviz yanıtlarının ayrıştırılması, gece güncellemesi, internet yokken güncellemenin atlanması ve son bilinen kurlar, yedek ve geri yükleme.
- **Sanal portföy:** Emir günü ve son işlem saati, valör ve hafta sonu, ileri fiyat, tatil gününde sonraki fiyat, valör bilgisi olmayan fon, nakit yetersizliği (bekleyen alışlar dahil), kısmi ve tam satış ile ortalama maliyet, bekleyen satıştaki payların yeniden satılamaması, iptal, sıfırlama, kapatılmış ve eski verili fon, günlük değer ve para piyasası kıyası, "Ya o zaman alsaydım?" hesabı ve yıllıklandırma sınırı (18 test).
- **Enflasyon ve reel getiri:** Bölüm 3.8 (21 test ve öneri değişmezliği testi).
- **Kullanıcı girişi ve güvenlik:** Bölüm 3.7 (33 test; yerel şifre sıfırlama ve hesap listesi komutları 9 test).
- **Diğer bölümler:** Öneri sistemi ve makine öğrenmesi modülü (Bölüm 5 ve 6).

Her değişiklikten sonra bütün testler çalıştırıldı.

## 3.10 Kısıtlar

- Fonların BIST 100 ve mevduat ile kıyası ve beta katsayısı hesaplanmadı (enflasyona göre reel getiri Bölüm 3.8'de); bu kıyaslama kapsam dışı bırakıldı ve gelecek çalışmalar arasındadır (Bölüm 8.6).
- Şema değişiklikleri bir migration aracıyla değil, açılışta eksik sütunları ekleyen bir yardımcıyla (`init_db`) yönetilmektedir; Alembic'e geçiş gelecek çalışmalara bırakıldı.
- Sanal portföy bilgisayardaki veritabanında saklanır (kullanıcı başına bir portföy); komisyon, stopaj ve TEFAS'ın tutar/adet sınırları uygulanmaz. Valör günü hesabında yalnızca hafta sonları atlanır; tatile denk gelen hedef günde sonraki ilk işlem gününün fiyatı kullanılır.
- Metrikler basit getiriler üzerinden hesaplanmaktadır; vergi, giriş-çıkış komisyonu gibi maliyetler hesaba katılmamaktadır (fon yönetim ücreti fiyata yansımıştır).
