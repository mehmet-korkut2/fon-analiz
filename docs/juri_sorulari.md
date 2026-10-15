# Jüri Soruları ve Cevaplar

Sunumda gelebilecek sorular ve kısa, dürüst cevaplar. Sayılar raporla aynıdır; bölüm numaraları rapora göredir. Cevaplar ezberlenmek için değil, içeriği hatırlamak için yazıldı; kendi cümlelerinle söyle.

## Veri

**1. Verileri nereden ve nasıl topladınız?**
TEFAS'tan. TEFAS 2026'da eski arayüzünü kapattı; sitenin kendi kullandığı JSON adreslerinden fon listesini, her fonun 5 yıllık fiyatını, güncel büyüklüğünü ve profilini çekiyoruz. 1.071 yatırım fonu, 866.841 günlük fiyat. Her akşam 21:00'de güncelleniyor, bilgisayar kapalıysa açılışta tamamlanıyor (Bölüm 2.2, 2.3).

**2. Verileri nasıl doğruladınız?**
İki yolla. Elle: 5 fonun fiyatını TEFAS sitesiyle karşılaştırdık, birebir eşleşti. Programla: şüpheli fonların fiyatlarını TEFAS'tan yeniden çekip veritabanıyla gün gün karşılaştırdık; TLY'de 1.239, YCK'da 1.229 günde fark sıfırdı. Bu, gördüğümüz olağan dışı hareketlerin yükleme hatası değil, kaynağın kendisi olduğunu gösterdi (Bölüm 2.6).

**3. TEFAS'ın resmî bir API'si var mı? Bu kullanım yasal mı?**
Resmî API yok; TEFAS bunu sıkça sorulan sorularda açıkça yazıyor. Kullandığımız adresler sitenin kendi adresleri. Kullanım koşullarını inceledik: saklamayı ya da göstermeyi yasaklayan bir hüküm yok, ama açık bir izin de yok. Proje ticari değil ve yayına alınmıyor; yayına alınsaydı Borsa İstanbul'un resmî veri ürünlerine geçmek gerekirdi (Bölüm 2.9).

**4. SPK kararıyla kapatılan fonları neden veriden silmediniz?**
Çünkü o fonlar gerçekten vardı ve geçmişte alınabiliyordu. Silseydik geriye dönük testler, kapanıp batan fonları hiç görmemiş olurdu; sonuçlar olduğundan iyi çıkardı (hayatta kalma yanlılığı). Bu yüzden 117 fonu işaretledik: güncel listelerden, sıralamalardan ve önerilerden çıkıyorlar ama geçmiş testlerde duruyorlar (Bölüm 2.7, 5.6).

**5. Portföy dağılımını neden göstermiyorsunuz?**
TEFAS yayımlamayı bıraktı. KAP'taki raporlardan çıkarmayı denedik; teknik olarak sınırda mümkündü (örneklemin %73'ü). Ama KAP'ın kullanım koşulu, bilgilerin MKK'nın yazılı izni olmadan "ileride kullanılmak üzere saklanamaz" olduğunu söylüyor. Teknik olarak yapabildiğimiz hâlde yapmadık (Bölüm 2.8).

## Metrikler ve öneri

**6. Sharpe oranında neden %5 volatilite eşiği var?**
Para piyasası benzeri fonlarda Sharpe 9'a kadar çıkıyordu. Nedeni risk değil takvimdi: hafta sonunun faizi pazartesi fiyatına yansıyor, ölçülen küçük volatilitenin çoğu bu. Payda neredeyse sıfır olunca oran anlamsız büyüyor. %5, verideki doğal kırılma noktası ve SPK/ESMA risk göstergesinde 3. sınıfın üst sınırı. 318 fon Sharpe almıyor, yerine açıklama gösteriliyor (Bölüm 3.5).

**7. Risksiz getiri olarak neyi kullandınız?**
Para piyasası fonlarının 1 yıllık medyan getirisini (13.10.2026'da %46,3). Sabit bir faiz yerine bunu seçtik, çünkü kendiliğinden güncelleniyor ve yatırımcının fon dünyasında gerçekten elde edebileceği "risksiz" getiriyi temsil ediyor (Bölüm 3.3).

**8. Öneri sistemi nasıl çalışıyor? Ağırlıkları nasıl belirlediniz?**
9 soruluk anket kullanıcıyı temkinli, dengeli ya da agresif profile koyuyor. Profile uygun fonlar dört bileşenle puanlanıyor: fazla getiri, riske göre getiri, düşüş direnci, tutarlılık. Ağırlıklar uzman görüşü; bilerek optimize etmedik, çünkü az dönemle "en iyi sonucu veren" ağırlığı aramak aşırı uyum olurdu. Ağırlıkları ±0,10 oynatınca ilk 10'un ne kadar değiştiğini ölçtük (Bölüm 5.3, 5.4).

**9. Öneri sisteminiz geçmişte işe yaradı mı?**
Çoğunlukla hayır, ve bunu sitede gösteriyoruz. Son üç yılda her ay yalnızca o güne kadarki veriyle seçilip 12 ay tutulan portföyler, para piyasası medyanını 24 dönemin temkinlide 12'sinde, dengelide 5'inde, agresifte 9'unda geçti. Bu dönem yüksek faiz dönemiydi; risk almak ödüllendirilmedi. Aynı veriyle seçip aynı veriyle ölçtüğümüzde ise kıyası geçiyordu; bu farkı göstermek için kayan pencereli testi yaptık (Bölüm 5.6).

**10. Dengeli profilde riskli fon kotası sonucu kötüleştirdiyse neden tuttunuz?**
Çünkü gerekçemiz getiri değil, tutarlılık. Kota olmadan "dengeli" listenin tamamı para piyasası benzeri fonlardan oluşuyordu; bu, etiketle çelişiyordu. Kotanın geçmiş testte sonucu kötüleştirdiğini (8/24 yerine 5/24) raporda açıkça yazdık (Bölüm 5.5).

## Makine öğrenmesi

**11. ML modeliniz neden başarısız?**
Çünkü bir aylık fon getirisinde öğrenilebilir sinyal çok zayıf. LightGBM fonları birbirinden ayırt etmeyi öğrenemedi (sıralama korelasyonu 0,054; drift'te 0,155). En önemli özellikleri bütün fonlar için aynı olan faiz düzeyi özellikleriydi. ARIMA da basit drift'ten ayırt edilemedi. Bu sonuç, kısa vadeli getirilerin büyük ölçüde öngörülemez olduğu yönündeki genel bilgiyle tutarlı (Bölüm 6.6).

**12. Başarısız bir modeli projede tutmanın anlamı ne?**
Başarı ölçütünü sonuçları görmeden tanımladık ve modeli gelecekten bilgi sızdırmayan bir testle değerlendirdik. Olumsuz sonuç da bir bulgu. Asıl katkı, modelin kurulması değil, dürüstçe test edilmesi ve sonuca göre karar verilmesi: sitede ML tahmini yok; testte en iyi çıkan drift, açık bir etiketle ve ölçülmüş kapsama oranlı bir aralıkla gösteriliyor (Bölüm 6.9, 6.11).

**13. Neden derin öğrenme (LSTM) kullanmadınız?**
Dört nedenle. Veri az: fon başına en fazla 47 aylık gözlem. Tablo biçimli, orta büyüklükteki verilerde ağaç modelleri genellikle derin öğrenmeye eşit ya da üstün. LightGBM bile sinyal bulamadı; daha esnek bir model zayıf sinyalde gürültüyü öğrenir. Ve önceden kural koymuştuk: LSTM'e ancak LightGBM anlamlı sonuç verirse geçilecekti (Bölüm 6.8).

**14. Gelecekten bilgi sızmadığından nasıl emin oldunuz?**
Her test ayında model yalnızca hedef penceresi o günden önce biten gözlemlerle yeniden eğitildi. Özellikler yalnızca tahmin günü ve öncesinin fiyatlarından hesaplandı. Hiperparametreler test döneminden önceki ayrı bir dönemde seçildi. Sonradan kapatılan fonlar da teste dahil. Bu kuralların her biri birim testleriyle doğrulanıyor (Bölüm 6.5).

## Uygulama

**15. Sanal portföyde valörü nasıl modellediniz?**
TEFAS'ın fon profilindeki valör ve son işlem saatini kullanıyoruz. Saat sonrası ya da hafta sonu verilen emir ertesi iş günü sayılıyor. Emir, valör kadar iş günü sonraki günün fiyatından gerçekleşiyor; o gün tatilse sonraki ilk işlem gününden. Ayrıca "ileri fiyat" kuralı var: o günün fiyatı emir anında zaten biliniyorsa emir bir gün kayıyor, bilinen fiyattan alım yapılamıyor. Alışta tutar bloke ediliyor, pay adedi tam sayı. TEFAS'taki alan adları ters görünüyor; hangisinin alış olduğunu yabancı hisse fonlarının bilinen T+1 / T+3 valörlerinden çıkardık (Bölüm 3.6).

**16. Sistemi nasıl test ettiniz?**
Backend'de 131 otomatik test var: metrik tanımları, API kuralları, öneri, ML'de sızıntı önlemleri, sanal portföyün valör ve nakit kuralları, internetsiz çalışma, yedek. Arayüzü gerçek tarayıcıda tıklayıp yazan bir betikle açık/koyu temada, masaüstü ve telefon genişliğinde denedik: internetle 204/204, internetsiz 208/208 adım geçti, konsol hatası ve dış istek yok (Bölüm 7.2, 7.3).

**17. Sunumda internet olmazsa ne olur?**
Uygulama çalışır. Fon verisi yereldeki veritabanında, yazı tipleri projeye gömülü. Döviz sayfası son bilinen kurları "en son X tarihinde güncellendi" notuyla gösterir. Gece güncellemesi internet yoksa birkaç saniyede atlanır. Bunu internet kesintisini canlandırarak denedik (Bölüm 7.4).

## Etik ve yöntem

**18. Bu bir yatırım tavsiyesi mi?**
Hayır. Yatırım danışmanlığı SPK lisansı gerektirir; bu bir bitirme projesi ve eğitim aracı. Her sayfada uyarı var; öneri, hesaplayıcı ve sanal portföyde daha belirgin uyarı kutuları var. Önerilerin geçmişte çoğunlukla kıyası geçemediğini de kullanıcıya gösteriyoruz.

**19. Yapay zekâ araçlarını nasıl kullandınız?**
Anthropic'in Claude Code aracını kullandık. Kodun büyük bölümü, analiz betikleri ve raporun ilk taslakları bizim yönlendirmemizle onunla yazıldı. Kararları biz verdik: hedef değişkenin getiri olması, SPK fonlarının silinmemesi, Sharpe eşiği, başarısız modelin gösterilmemesi, KAP verisinin kullanılmaması gibi. Her değişiklikten sonra testleri çalıştırdık, veri iddialarını kaynağa karşı doğruladık, raporun sayılarını veritabanından aldık. Yapay zekânın yaptığı hatalar da commit geçmişinde kayıtlı (Bölüm 1.3). [DOLDUR: kendi deneyimini bir cümleyle ekle; ne zaman işini kolaylaştırdı, ne zaman düzeltmen gerekti.]

**20. Projenin en büyük kısıtı ne? Yeniden yapsanız neyi farklı yapardınız?**
En büyük kısıt veri: 5 yıllık fiyat geçmişi tek bir yüksek faiz dönemini kapsıyor, bu yüzden hem öneri testi hem ML testi başka piyasa koşullarına genellenemez. Fonların geçmişteki risk değeri ve büyüklüğü de bilinmiyor. Yeniden yapsaydık bu bilgileri ilk günden itibaren her gün saklamaya başlardık. [DOLDUR: kendi cevabını ekle.]
