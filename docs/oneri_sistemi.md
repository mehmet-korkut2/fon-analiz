# Risk Profili ve Fon Öneri Sistemi

Bu belge, platformun risk anketini, fon puanlama yöntemini, örnek portföyü ve geriye dönük testini anlatır. Sayılar 13 Ekim 2026 tarihli veriye aittir. Analiz tablolarının tamamı `docs/oneri_analizi_cikti.md` dosyasındadır ve şu komutla yeniden üretilebilir:

```powershell
cd backend
python -m scripts.oneri_analizi > ..\docs\oneri_analizi_cikti.md
```

Kod: `backend/app/services/risk_survey.py` (anket), `backend/app/services/recommender.py` (puanlama, portföy, geriye dönük test).

> **Yasal not.** Sistem eğitim amaçlı bir algoritmanın çıktısını gösterir; SPK lisanslı yatırım danışmanlığı değildir. Arayüzün her sayfasında bu uyarı yer alır.

---

## 1. Risk anketi

Anket 7 puanlı soru ve puana girmeyen 1 uygunluk sorusundan oluşur. Her cevap 0–4 puan alır ve sorunun ağırlığıyla çarpılır.

| # | Konu | Soru | Cevaplar (0 → 4 puan) | Ağırlık |
|---|---|---|---|---|
| 1 | Vade | Bu parayı ne kadar süre yatırımda tutmayı düşünüyorsun? | 1 yıldan az · 1–2 yıl · 2–3 yıl · 3–5 yıl · 5 yıldan fazla | ×3 |
| 2 | Kayıp toleransı | Yatırımın bir yıl içinde en fazla ne kadar değer kaybetmesine katlanabilirsin? | Hiç · %5 · %10 · %20 · %30 ve üstü | ×3 |
| 3 | Davranış | Yatırımın 3 ayda %15 değer kaybetti. Ne yaparsın? | Hepsini satarım · Yarısını satarım · Düşüş sürerse satarım · Beklerim · Ekleme yaparım | ×2 |
| 4 | Hedef | Bu yatırımdan beklentin ne? | Anaparayı korumak · Enflasyon kadar · Enflasyonun biraz üstü · Belirgin büyüme · En yüksek getiri | ×2 |
| 5 | Gelir durumu | Düzenli gelirin ne kadar istikrarlı? | Yok · Düzensiz · Düzenli ama değişken · Düzenli · Düzenli ve artıyor | ×1 |
| 6 | Birikim | Bu yatırım dışında kaç aylık giderini karşılayacak birikimin var? | Yok · 3 aydan az · 3–6 ay · 6–12 ay · 12 aydan fazla | ×1 |
| 7 | Deneyim | Daha önce hangi ürünlere yatırım yaptın? | Hiç/mevduat · Para piyasası, borçlanma · Karma, değişken · Hisse fonu, hisse · Türev, kaldıraçlı | ×1 |
| – | Nitelikli yatırımcı | SPK tanımına göre nitelikli yatırımcı mısın? | Hayır / bilmiyorum · Evet | puana girmez |

**Ağırlıkların gerekçesi.** Risk taşıma *kapasitesini* en çok belirleyen iki etken vade ve kayıp toleransıdır; bu yüzden ×3. Davranış sorusu, yatırımcının söylediği tolerans ile düşüş anındaki gerçek tepkisi arasındaki farkı yakalamak için, hedef sorusu ise risk *isteğini* ölçmek için ×2'dir. Gelir, birikim ve deneyim profili destekleyen ama tek başına belirlemeyen etkenlerdir (×1).

**Puan ve profil.** Ham puan en fazla 4 × (3+3+2+2+1+1+1) = 52'dir ve 0–100'e ölçeklenir.

| Puan | Profil | TEFAS risk değeri | Fonun 1 yıllık volatilitesi | Aday havuzu* |
|---|---|---|---|---|
| 0–39 | Temkinli | 1–3 | en fazla %5 | 111 fon |
| 40–69 | Dengeli | 2–5 | en fazla %15 | 163 fon |
| 70–100 | Agresif | 4–7 | sınır yok | 382 fon |

\* Nitelikli yatırımcı olmayan kullanıcı için (serbest fonlar hariç).

Aralıklar bilinçli olarak örtüşür (2–3 ve 4–5): sınırdaki bir fon iki komşu profile de uygun olabilir. Volatilite sınırı, TEFAS risk değerinin güncel olmadığı durumlara karşı ikinci bir kontroldür (ör. risk değeri 2 görünen ama %12 dalgalanan fon temkinli profile önerilmez). %5 ve %15, SPK/ESMA risk değeri yönteminde 3. ve 5. sınıfların üst sınırlarıdır.

**Sınırlayıcı kurallar.** Toplam puan yüksek olsa bile:
- vade 1 yıldan kısaysa ya da kayıp toleransı "hiç" ise profil en fazla **temkinli**,
- acil durum birikimi yoksa profil en fazla **dengeli** olur.

Toplama dayalı puanlarda bir sorudaki düşük cevap diğerlerinin yüksekliğiyle telafi edilebilir; oysa 6 ay sonra parasına ihtiyacı olan biri, kayıp toleransı ne kadar yüksek olursa olsun hisse fonuna uygun değildir. Uygulanan sınır, sonuç ekranında gerekçesiyle gösterilir.

**Nitelikli yatırımcı sorusu.** Serbest fonlar mevzuat gereği yalnızca nitelikli yatırımcılara satılabilir. Varsayılan cevap "Hayır"dır ve serbest fonlar öneri dışında kalır.

## 2. Aday fonlar

Bir fonun aday olabilmesi için:
1. TEFAS'ta işlem görüyor olması,
2. son fiyatının en güncel tarihten en fazla 7 gün eski olması,
3. SPK kararıyla işleme kapatılmamış olması (Bülten 2026/60),
4. 1 yıllık getirisinin ve volatilitesinin hesaplanabilmesi (en az 1 yıllık veri),
5. TEFAS risk değerinin dolu olması (105 fonda boş; bunlar öneri dışında),
6. risk değerinin ve volatilitesinin profilin aralığında olması,
7. nitelikli yatırımcı değilse serbest fon olmaması

gerekir. 13.10.2026 itibarıyla ilk dört koşulu sağlayan **841** fon vardır.

## 3. Puanlama

Dört bileşen, **profilin aday havuzu içinde** yüzdelik dilime çevrilir: en iyi fon 1, en kötü fon 1/n alır. Böylece Sharpe oranı ile maksimum düşüş gibi farklı ölçekteki metrikler toplanabilir hale gelir ve aykırı değerler (ör. tek bir fonun çok yüksek getirisi) puanı orantısız etkilemez. Risksiz getiri (r_f), para piyasası fonlarının 1 yıllık medyan getirisidir (%46,3).

| Bileşen | Tanım | İyi olan |
|---|---|---|
| **G – Fazla getiri** | 1 yıllık getiri − r_f | büyük |
| **RA – Riske göre getiri** | Volatilitesi %5 ve üstü fonlarda Sharpe oranı. Volatilitesi %5 altı fonlarda (Sharpe hesaplanmaz) fazla getiri; yüzdelik havuzu profile göre değişir (aşağıda) | büyük |
| **D – Düşüş direnci** | 1 yıllık maksimum düşüş | küçük kayıp |
| **T – Tutarlılık** | min(3 aylık getirinin yıllığı, 6 aylık getirinin yıllığı, 1 yıllık getiri) − r_f | büyük |

**Sharpe'ı olmayan fonlar neden ayrı ele alınıyor?** Para piyasası benzeri fonların fiyatı neredeyse doğrusal artar; ölçülen %1,5 civarındaki volatilitenin büyük kısmı, hafta sonu faizinin pazartesi fiyatına yansımasından gelir. Payda sıfıra yaklaştığı için Sharpe anlamsız büyür (ör. %1,8 volatiliteyle 6,9). Platform bu fonlarda Sharpe hesaplamaz; öneri sisteminde ise bu fonları cezalandırmamak için RA bileşeni fazla getiriyle ölçülür.

**RA havuzu profile göre değişir:**
- **Temkinli – ayrı havuz:** Düşük volatiliteli fonların fazla getirisi yalnızca birbirleriyle karşılaştırılır. Temkinli havuzun büyük kısmı bu fonlardan oluşur; aralarındaki farklar küçük (ör. %48 ile %50) ama temkinli yatırımcı için anlamlıdır. En iyi para piyasası fonu RA'da 1'e yakın puan alır.
- **Dengeli ve agresif – tüm havuz:** Düşük volatiliteli fonların fazla getirisi, havuzdaki tüm fonların fazla getirileri içinde yüzdeliğe çevrilir (yani RA = G). Bu profillerde riskli fonların arasında bir para piyasası fonu, ancak getirisi gerçekten yüksekse öne çıkmalıdır.

**Tutarlılık neden en kötü dönem?** 1 yıllık getirisi yüksek ama son 3 ayda düşen bir fon, getirisinin tamamını bir yıl önce elde etmiş olabilir. Üç dönemin en kötüsünü almak, yalnızca her dönemde iyi performans gösteren fonları ödüllendirir.

### Ağırlıklar

| Profil | G | RA | D | T |
|---|---|---|---|---|
| Temkinli | 0,15 | 0,25 | **0,35** | 0,25 |
| Dengeli | 0,20 | **0,35** | 0,25 | 0,20 |
| Agresif | **0,35** | 0,30 | 0,15 | 0,20 |

**Gerekçe:**
- **Temkinli:** Öncelik anaparayı korumaktır. Kayıplar asimetriktir (%20 kaybı telafi etmek %25 kazanç ister), bu yüzden en yüksek ağırlık düşüş direncindedir. Kısa vadeli yatırımcı için getirinin istikrarı (T) da önemlidir. Ham getiri en düşük ağırlıktadır; bu profilde getiri farkları zaten küçüktür ve RA bileşeni para piyasası fonlarını fazla getirileriyle sıralar.
- **Dengeli:** Klasik "riske göre getiri" yaklaşımı; en yüksek ağırlık RA'dadır, düşüş ve getiri dengelidir.
- **Agresif:** Uzun vade düşüşlerden toparlanmaya zaman tanır, bu yüzden D en düşük ağırlıktadır ve getiri öne çıkar. RA'nın 0,30'luk ağırlığı, yalnızca şansla yükselmiş çok oynak fonların zirveye çıkmasını önler.
- **Tutarlılık** her profilde 0,20–0,25'tir: geçen yılın kazananı bu yıl kaybettirebilir.

Ağırlıklar uzman görüşüne dayanır; geçmiş veriyle optimize **edilmemiştir**. Az sayıda dönemle ağırlıkları "en iyi sonucu verecek" şekilde ayarlamak aşırı uyum (overfitting) riski taşır. Ağırlıkların sonuca etkisi Bölüm 6.2'deki duyarlılık analiziyle ölçülmüştür.

## 4. Çeşitlendirme ve "neden önerildi"

Fonlar puan sırasıyla seçilir; **aynı kategoriden en fazla 2 fon** alınır ve ilk 10 gösterilir.

Her önerinin gerekçesi otomatik üretilir: fonun en yüksek yüzdelikteki iki bileşeni somut sayılarla yazılır, ardından profil uyumu eklenir. En zayıf bileşen alt %25'teyse "Dikkat" notu düşülür. Örnek (dengeli profil, EIL):

> Son 3, 6 ve 12 aylık getirilerinin hepsi, yıllık bazda risksiz getirinin üstünde. Son 1 yılda %48,2 getiri sağladı; risksiz getirinin 1,9 puan üstünde (risksiz getiri %46,3). Bu, adayların ilk %10'unda. TEFAS risk değeri 2, dengeli profilin aralığında (2-5).

## 5. Örnek portföy ve geriye dönük test

**Örnek portföy.** Öneriler arasından temkinli profilde 3, dengeli profilde 4, agresif profilde 5 fon seçilir: önce her kategoriden en iyi fon, yetmezse kalan en iyiler. Ağırlıklar eşittir; portföy dönem başında alınıp yeniden dengelenmeden tutulur. Dönem içinde verisi kesilen fon son fiyatında kalır (yatırımcı o fiyattan çıkamamış sayılır).

**Kıyas:** Para piyasası fonlarının her gün, 100'den başlayan serilerinin medyanı. Kıyasa sonradan kapatılan para piyasası fonları da dahildir (yalnızca bugün ayakta kalanları almak kıyası olduğundan iyi gösterirdi).

**İki ayrı performans:**
1. *Son 1 yıl (arayüzdeki "geçmiş performans"):* Fonlar bu dönemin verisiyle seçildiği için sonuç **iyimserdir** (seçim yanlılığı). Arayüzde bu açıkça yazar.
2. *Gerçek geriye dönük test:* Seçim, 12 ay önceki (13.10.2025) veriyle yapılır; sonraki 12 ayın performansı ölçülür. O gün fiyatı olan **tüm** fonlar adaydır, sonradan SPK kararıyla kapatılan ya da verisi kesilen fonlar dahil; metrikler ve risksiz getiri o tarihe kadarki fiyatlardan yeniden hesaplanır.

## 6. Sonuçlar

### 6.1 RA modu: dengeli profilin ilk 10'u

Dengeli havuzda 163 fon var; 60'ı düşük volatiliteli. İki modun ilk 10'u:

| Sıra | Tüm havuz (kullanılan) | Puan | Ayrı havuz | Puan |
|---|---|---|---|---|
| 1 | EIL (Para Piyasası) | 0,959 | EIL (Para Piyasası) | 0,953 |
| 2 | NBO (Fon Sepeti) | 0,953 | NBO (Fon Sepeti) | 0,952 |
| 3 | OLE (Fon Sepeti) | 0,952 | OLE (Fon Sepeti) | 0,942 |
| 4 | PLR (Para Piyasası) | 0,950 | PLR (Para Piyasası) | 0,936 |
| 5 | NJR (Borçlanma Araçları) | 0,936 | NJR (Borçlanma Araçları) | 0,935 |
| 6 | KSK (Katılım) | 0,906 | KSK (Katılım) | 0,876 |
| 7 | DBZ (Borçlanma Araçları) | 0,888 | DBZ (Borçlanma Araçları) | 0,850 |
| 8 | TE4 (Değişken) | 0,867 | TE4 (Değişken) | 0,841 |
| 9 | TND (Değişken) | 0,862 | KDE (Katılım, vol %6,1) | 0,827 |
| 10 | RRP (Katılım) | 0,842 | TND (Değişken) | 0,799 |

**Değerlendirme.** İki mod 9/10 aynı fonu seçiyor; tek fark, tüm havuz modunda RRP'nin, ayrı havuz modunda KDE'nin (tek Sharpe'lı fon) listeye girmesi. Değişiklik ilk 10'u neredeyse etkilemiyor, çünkü dengeli profilin ilk 10'unu belirleyen RA değil, düşük volatiliteli fonların fazla getiri, düşüş ve tutarlılıkta zaten en üstte olmasıdır.

**Asıl bulgu:** Dengeli profilin ilk 10'u, tüm havuz modunda tamamen, ayrı havuz modunda 9/10 oranında volatilitesi %2'nin altında, maksimum düşüşü ~0 olan fonlardan oluşuyor (medyan 1 yıllık getiri ~%47). Bunun nedeni dönemin piyasa koşulu: risksiz getiri %46 iken düşük riskli fonlar son bir yılda riskli fonlardan hem daha çok kazandırdı hem de hiç düşmedi (risk değeri 1–2 fonların medyan getirisi %45, risk değeri 7 fonlarınki %15). Riske göre getiriyi ödüllendiren her yöntem bu dönemde dengeli yatırımcıyı muhafazakâr fonlara yönlendirir. Bu, yöntemin bir hatası değil, piyasa rejimine duyarlı olduğunun göstergesidir; ancak dengeli bir yatırımcı farklı bir dağılım bekleyebilir. Olası bir iyileştirme, dengeli portföyde risk değeri 4 ve üstü fonlara asgari bir pay ayırmaktır (Bölüm 8).

### 6.2 Ağırlık duyarlılığı

Her profilde ağırlıklar değiştirilip ilk 10 yeniden seçildi: her bileşene +0,10 (diğerleri orantılı azalır), her bileşenin çıkarılması ve eşit ağırlık. "Ortak": temel ilk 10 ile aynı kalan fon sayısı; Spearman: havuzdaki tüm fonların puan sıralamasının temel sıralamayla korelasyonu.

| Profil | Ortak fon (en az – en çok) | Spearman (en az) | En çok etkileyen değişiklik |
|---|---|---|---|
| Temkinli | 8–10 / 10 | 0,95 | RA'nın çıkarılması (8/10), D'nin çıkarılması (ρ = 0,95) |
| Dengeli | 7–10 / 10 | 0,95 | D'nin çıkarılması (7/10: KNJ, PRD, RKC girer) |
| Agresif | 5–10 / 10 | 0,95 | D'nin çıkarılması (5/10), eşit ağırlık ve RA'nın çıkarılması (6/10) |

**Değerlendirme.** Temkinli ve dengeli profiller ağırlıklara karşı sağlamdır: ±0,10'luk değişikliklerin hiçbiri ilk 10'dan birden fazla fonu değiştirmiyor. Agresif profil daha duyarlıdır, çünkü havuzu büyük (382 fon) ve fonlar birbirine yakın puanlar alıyor; özellikle düşüş direnci çıkarıldığında ilk 10'un yarısı değişiyor. Bu, agresif profilde D'nin düşük de olsa (0,15) korunmasının önemini gösterir. Tam tablo: `docs/oneri_analizi_cikti.md`, Bölüm 2.

### 6.3 Gerçek geriye dönük test (13.10.2025 seçim → 13.10.2026)

| Profil | Seçimdeki r_f | Portföy | Getiri | Kıyas (PP medyanı) | Fark | Volatilite | Maks. düşüş |
|---|---|---|---|---|---|---|---|
| Temkinli | %57,1 | HVK, HVT, OLE | %41,0 | %46,3 | −%5,3 | %3,5 | −%2,5 |
| Dengeli | %57,1 | HVK, PRY, OLE, RIK | %34,0 | %46,3 | −%12,3 | %4,1 | −%3,2 |
| Agresif | %57,1 | BIH, NAU, HAM, OTJ, RIK | %27,7 | %46,3 | −%18,6 | %18,3 | −%15,4 |

**Değerlendirme.** Test döneminde üç profilin örnek portföyü de para piyasası medyanının gerisinde kaldı. Bunun nedenleri:
1. **Piyasa koşulu:** Para piyasası fonlarının 1 yıllık medyan getirisi seçim gününde %57,1, test döneminde %46,3 oldu; yüksek faizli bu dönemde risk almak ek getiri sağlamadı (bugün risk değeri 7 fonların medyan 1 yıllık getirisi %15). Agresif portföyün en çok geride kalması bu koşulla tutarlıdır.
2. **Sonradan kapatılan fonlar:** Temkinli ve dengeli portföydeki HVK (Hedef Portföy) ile dengeli portföydeki PRY (Pusula Portföy), 17.09.2026'da SPK kararıyla işleme kapatılan şirketlerin fonlarıdır. Seçim günü bu bilinemezdi; test bu riski bilinçli olarak dışarıda bırakmaz. HVK'nın dönem getirisi %23,9'da kaldı.
3. **Tek dönem:** Sonuç yalnızca bir 12 aylık döneme aittir ve istatistiksel olarak genellenemez. Kayan pencerelerle (ör. son 4 yılın her çeyreğinde seçim) yapılacak bir test daha güvenilir olur (Bölüm 8).

Bu sonuç, arayüzdeki "son 1 yıl" grafiğinin neden iyimser olduğunu da gösteriyor: aynı yöntemle bugün seçilen portföyler, seçimde kullanılan dönemde kıyası geçiyor (temkinli %48,8, dengeli %48,7, agresif %54,5; kıyas %46,3), 12 ay önce seçilenler ise sonraki dönemde geçemedi.

### 6.4 Örnek kişiler

| Kişi | Puan | Profil | İlk öneriler | Not |
|---|---|---|---|---|
| Ayşe, 26, uzun vadeli birikim | 77 | Agresif | KNJ, CKL, OPF, KTJ, GBG | – |
| Mehmet, 58, emekliliğe 2 yıl | 35 | Temkinli | RBP, EIL, OSD, OLE, NSP | – |
| Zeynep, 40, orta yol | 60 | Dengeli | EIL, NBO, OLE, PLR, NJR | – |
| Can, 30, birikimi yok ama riskli | 87 | Dengeli | EIL, NBO, OLE, PLR, NJR | Puana göre agresif; acil durum birikimi olmadığı için dengeliye indi |

## 7. Sınırlamalar

- **Geriye dönük testte bugünkü risk değeri ve kategori:** TEFAS'ın geçmiş risk değerlerine erişimimiz yok; seçim gününde de bugünkü değerler kullanıldı.
- **Maliyet ve vergi:** Fon yönetim ücretleri fiyata yansımıştır; alım-satım masrafı ve stopaj hesaba katılmadı.
- **Al-tut ve eşit ağırlık:** Portföy yeniden dengelenmez; gerçek bir yatırımcının davranışını basitleştirir.
- **Ağırlıklar optimize edilmedi:** Uzman görüşüne dayanır; duyarlılık analizi sonuçların ağırlıklara ne kadar bağlı olduğunu gösterir.
- **Tek dönem:** Geriye dönük test tek bir 12 aylık dönemdir.
- **Veri:** Fiyatlar TEFAS'tan alınır; tek günlük hatalı fiyatlar metriklerde yok sayılır, SPK kararıyla kapatılan fonlar işaretlidir (bkz. `CLAUDE.md`).

## 8. Gelecek çalışmalar

- Kayan pencereli geriye dönük test (çok dönem, ortalama ve dağılım).
- Dengeli portföyde risk değeri 4+ fonlara asgari pay.
- Aynı portföy yönetim şirketinden en fazla 1–2 fon (şirket riskini çeşitlendirmek; Bölüm 6.3'teki SPK kararı bu riskin gerçek bir örneği).
- Kullanıcı girişiyle profillerin `risk_profiles` tablosunda saklanması.
