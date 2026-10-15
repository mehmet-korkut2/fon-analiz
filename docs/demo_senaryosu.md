# Demo Videosu Senaryosu (4 dakika)

Canlı demo bozulursa gösterilecek video. Her adımda önce **ekranda** ne olacağı, sonra **söylenecek** 1–2 cümle var. Süreler toplam 4:00'e göre ayarlandı; konuşma hızı dakikada yaklaşık 130 kelime.

## Kayıttan önce

- [ ] `python -m scripts.yedekle --not demo-oncesi` ile yedek al.
- [ ] `FonAnaliz_Baslat.bat` ile aç; tarayıcı tam ekran, yakınlaştırma %100, açık tema.
- [ ] Sanal portföy boş olsun (Ayarlar → Portföyü sıfırla). Risk anketi doldurulmamış olsun (gizli pencere ya da tarayıcı verisini temizle).
- [ ] "Ya o zaman alsaydım?" için TTE ve AES fonları hazır; tarih 2 yıl önce.
- [ ] Bildirimleri kapat; ekran kaydı 1920×1080, mikrofon testi.
- [ ] Tek parça kaydet. Takılırsan o adımı baştan al, montajda birleştir.

## Akış

| Süre | Ekranda | Söylenecek |
|---|---|---|
| **0:00–0:20** Açılış | Ana sayfa: başlık, arama kutusu, kategori kutuları, öne çıkan fonlar | "Fon Analiz, TEFAS'taki 1.071 yatırım fonunu tek yerde inceleyip karşılaştırmayı ve risk profiline uygun fonları bulmayı sağlayan bir web uygulaması. Veriler her akşam TEFAS'tan güncelleniyor." |
| **0:20–0:45** Fon listesi | Arama kutusuna "teknoloji" yaz → liste açılır; "Büyüklük" sütununa tıkla, sonra "1 yıl"a tıkla | "Fonları kategoriye, riske ve metriklere göre süzüp sıralayabiliyoruz. Fon büyüklüğü ve yatırımcı sayısı da TEFAS'tan geliyor." |
| **0:45–1:20** Fon detayı | TTE'ye tıkla; dönemi 3Y yap; 50 ve 200 günlük ortalamayı aç; trend etiketini ve 52 haftalık aralığı göster; aşağıda risk kartlarına in | "Detayda fiyat grafiği, getiri, volatilite, Sharpe ve maksimum düşüş var. Hareketli ortalamalar ve 52 haftalık aralık geçmişi özetliyor; altında da testlerimizde bunların geleceği tahmin etmediğini açıkça yazıyoruz." |
| **1:20–1:40** Karşılaştırma | "Karşılaştırmaya ekle" → Karşılaştır; AES ve IPB ekle; tabloda vurgulu hücreleri göster | "Dört fona kadar, hepsini 100'den başlatarak yan yana koyabiliyoruz. Tabloda her satırın en iyi değeri vurgulanıyor." |
| **1:40–2:25** Risk anketi ve öneriler | Anketi hızlıca doldur (orta seçenekler) → profil kartı → Öneriler; bir kartın "Neden önerildi" kısmını göster; aşağı kaydırıp geriye dönük test grafiğini göster | "Dokuz soruluk anket bir risk profili çıkarıyor. Öneriler dört ölçütle puanlanıyor ve her birinin gerekçesi yazıyor. Aynı yöntemi geçmişte 24 kez denedik; sonuçları gizlemeden, para piyasası fonlarıyla kıyaslayarak gösteriyoruz." |
| **2:25–3:00** Sanal portföy | Bir öneri kartından fona git → "Sanal portföyde dene"; 10.000 TL yaz, "Alış emri ver"; bekleyen emri ve ayrılan nakdi göster | "Sanal portföyde hayali parayla deneme yapılabiliyor. Emirler TEFAS'taki gibi fonun valörüne göre bekliyor ve o günün fiyatından gerçekleşiyor; bilinen bir fiyattan alım yapılamıyor." |
| **3:00–3:25** Ya o zaman alsaydım? | Sekmeye geç; TTE ve AES, 2 yıl önce, 10.000 TL → Hesapla; tabloyu ve grafiği göster | "Geriye dönük modda 'iki yıl önce alsaydım bugün ne olurdu' sorusunu, aynı dönemde para piyasası fonlarıyla kıyaslayarak cevaplıyoruz." |
| **3:25–3:45** Model performansı | Model sayfası: kırmızı sonuç kutusu ve genel sonuç tablosu | "Bir makine öğrenmesi modeli de denedik. Basit bir referansı geçemedi; bu yüzden sitede ML tahmini değil, geçmiş eğilime dayalı tahmin ve %80 aralık gösteriyoruz." |
| **3:45–4:00** Kapanış | Telefon görünümü ya da koyu tema (birkaç saniye); sonra ana sayfadaki uyarı satırı | "Uygulama telefonda ve koyu temada da çalışıyor, internet olmasa da son verilerle açılıyor. Bu bir bitirme projesi; gösterilen hiçbir şey yatırım tavsiyesi değildir." |

## Notlar

- Sayılar kayıt günü değişir; senaryodaki cümleler sayı içermeyecek şekilde yazıldı ("1.071 fon" dışında). Fon sayısını kayıt günü ana sayfadan kontrol et.
- Uyarı metinleri (simülasyon, yatırım tavsiyesi değildir) ekranda en az bir kez okunacak kadar görünsün.
- Sanal portföyde emir hemen gerçekleşmez; videoda bekleyen emri göstermek yeterli. Gerçekleşmiş bir pozisyon göstermek istersen kayıttan birkaç gün önce bir alış yap.
- Kayıttan sonra: sanal portföyü sıfırla ya da `python -m scripts.geri_yukle` ile demo öncesi yedeğe dön.

[DOLDUR: video bağlantısı, kayıt tarihi, süre]
