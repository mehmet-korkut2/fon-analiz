# Öneri sistemi analizleri

Veri tarihi: 2026-10-13. Aday havuzu: 841 fon. Risksiz getiri: %46,3.

## 1. RA modu: dengeli profilin ilk 10'u

Dengeli havuz: 163 fon; bunların 60'i düşük volatiliteli (%5 altı, Sharpe yok).

| Sıra | Tüm havuz (seçilen) | puan | vol | Ayrı havuz | puan | vol |
|---|---|---|---|---|---|---|
| 1 | EIL (Para Piyasası) | 0,959 | %1,5 | EIL (Para Piyasası) | 0,953 | %1,5 |
| 2 | NBO (Fon Sepeti) | 0,953 | %1,8 | NBO (Fon Sepeti) | 0,952 | %1,8 |
| 3 | OLE (Fon Sepeti) | 0,952 | %1,4 | OLE (Fon Sepeti) | 0,942 | %1,4 |
| 4 | PLR (Para Piyasası) | 0,950 | %1,5 | PLR (Para Piyasası) | 0,936 | %1,5 |
| 5 | NJR (Borçlanma Araçları) | 0,936 | %1,7 | NJR (Borçlanma Araçları) | 0,935 | %1,7 |
| 6 | KSK (Katılım) | 0,906 | %1,5 | KSK (Katılım) | 0,876 | %1,5 |
| 7 | DBZ (Borçlanma Araçları) | 0,888 | %1,5 | DBZ (Borçlanma Araçları) | 0,850 | %1,5 |
| 8 | TE4 (Değişken) | 0,867 | %1,8 | TE4 (Değişken) | 0,841 | %1,8 |
| 9 | TND (Değişken) | 0,862 | %1,4 | KDE (Katılım) | 0,827 | %6,1 |
| 10 | RRP (Katılım) | 0,842 | %1,4 | TND (Değişken) | 0,799 | %1,4 |

Ortak fon: 9/10. Sadece tüm havuzda: RRP. Sadece ayrı havuzda: KDE.
- Tüm havuz: ilk 10'da düşük volatiliteli fon 10, medyan volatilite %1,5, medyan 1 yıllık getiri %47,0, medyan maks. düşüş %0,0
- Ayrı havuz: ilk 10'da düşük volatiliteli fon 9, medyan volatilite %1,5, medyan 1 yıllık getiri %47,8, medyan maks. düşüş %0,0

## 2. Ağırlık duyarlılığı

Her satırda ağırlıklar değiştirilip ilk 10 (kategori sınırıyla) yeniden seçildi. **Ortak**: temel ilk 10 ile kaç fonun aynı kaldığı. **Spearman**: havuzdaki tüm fonların puan sıralamasının temel sıralamayla korelasyonu.

### Temkinli (havuz 111 fon)

| Ağırlıklar (G / RA / D / T) | Ortak | Spearman | Yeni girenler |
|---|---|---|---|
| Temel: 0,15 / 0,25 / 0,35 / 0,25 | 10/10 | 1,00 | – |
| Eşit ağırlık: 0,25 / 0,25 / 0,25 / 0,25 | 10/10 | 0,99 | – |
| Fazla getiri +0,10: 0,24 / 0,23 / 0,32 / 0,23 | 10/10 | 1,00 | – |
| Riske göre getiri +0,10: 0,14 / 0,33 / 0,32 / 0,23 | 10/10 | 1,00 | – |
| Düşüş direnci +0,10: 0,14 / 0,23 / 0,42 / 0,23 | 9/10 | 1,00 | FYO |
| Tutarlılık +0,10: 0,14 / 0,23 / 0,32 / 0,33 | 10/10 | 1,00 | – |
| Fazla getiri yok: 0,00 / 0,29 / 0,41 / 0,29 | 9/10 | 1,00 | FYO |
| Riske göre getiri yok: 0,20 / 0,00 / 0,47 / 0,33 | 8/10 | 0,98 | FYO, KSK |
| Düşüş direnci yok: 0,23 / 0,38 / 0,00 / 0,38 | 9/10 | 0,95 | HVT |
| Tutarlılık yok: 0,20 / 0,33 / 0,47 / 0,00 | 9/10 | 0,99 | FYO |

### Dengeli (havuz 163 fon)

| Ağırlıklar (G / RA / D / T) | Ortak | Spearman | Yeni girenler |
|---|---|---|---|
| Temel: 0,20 / 0,35 / 0,25 / 0,20 | 10/10 | 1,00 | – |
| Eşit ağırlık: 0,25 / 0,25 / 0,25 / 0,25 | 10/10 | 1,00 | – |
| Fazla getiri +0,10: 0,28 / 0,32 / 0,23 / 0,18 | 9/10 | 1,00 | KDE |
| Riske göre getiri +0,10: 0,18 / 0,42 / 0,23 / 0,18 | 9/10 | 1,00 | KDE |
| Düşüş direnci +0,10: 0,18 / 0,32 / 0,33 / 0,18 | 10/10 | 1,00 | – |
| Tutarlılık +0,10: 0,18 / 0,32 / 0,23 / 0,28 | 10/10 | 1,00 | – |
| Fazla getiri yok: 0,00 / 0,44 / 0,31 / 0,25 | 10/10 | 0,99 | – |
| Riske göre getiri yok: 0,31 / 0,00 / 0,38 / 0,31 | 10/10 | 0,95 | – |
| Düşüş direnci yok: 0,27 / 0,47 / 0,00 / 0,27 | 7/10 | 0,98 | KNJ, PRD, RKC |
| Tutarlılık yok: 0,25 / 0,44 / 0,31 / 0,00 | 9/10 | 0,99 | KDE |

### Agresif (havuz 382 fon)

| Ağırlıklar (G / RA / D / T) | Ortak | Spearman | Yeni girenler |
|---|---|---|---|
| Temel: 0,35 / 0,30 / 0,15 / 0,20 | 10/10 | 1,00 | – |
| Eşit ağırlık: 0,25 / 0,25 / 0,25 / 0,25 | 6/10 | 0,98 | AFA, FFH, SPT, YAN |
| Fazla getiri +0,10: 0,42 / 0,27 / 0,14 / 0,18 | 10/10 | 1,00 | – |
| Riske göre getiri +0,10: 0,32 / 0,37 / 0,14 / 0,18 | 10/10 | 1,00 | – |
| Düşüş direnci +0,10: 0,32 / 0,27 / 0,24 / 0,18 | 7/10 | 0,99 | AFA, HIZ, SPT |
| Tutarlılık +0,10: 0,32 / 0,27 / 0,14 / 0,28 | 10/10 | 1,00 | – |
| Fazla getiri yok: 0,00 / 0,46 / 0,23 / 0,31 | 8/10 | 0,98 | AFA, YAN |
| Riske göre getiri yok: 0,50 / 0,00 / 0,21 / 0,29 | 6/10 | 0,95 | AFA, FFH, SPT, YAN |
| Düşüş direnci yok: 0,41 / 0,35 / 0,00 / 0,24 | 5/10 | 0,98 | AES, BBP, BTK, SGT, YAY |
| Tutarlılık yok: 0,44 / 0,38 / 0,19 / 0,00 | 7/10 | 0,98 | CPU, ECA, HIZ |

## 3. Kayan pencereli geriye dönük test

Son 3 yılda her ayın ilk işlem günü o güne kadarki veriyle seçim, 12 ay tutma; kıyas para piyasası fonlarının medyanı. Kaynak: backtest_windows tablosu (`python -m scripts.geriye_donuk_test`).

**Nitelikli olmayan yatırımcı**

| Profil | Dönem | PP medyanını geçtiği | Ort. fazla getiri | Medyan fazla getiri | Ort. portföy / PP | En iyi dönem | En kötü dönem |
|---|---|---|---|---|---|---|---|
| temkinli | 24 | 12/24 | -%0,9 | -%0,1 | %54,3 / %55,3 | 07.2025: +%4,9 | 12.2023: -%8,5 |
| dengeli | 24 | 5/24 | -%11,0 | -%9,3 | %44,3 / %55,3 | 06.2025: +%8,0 | 04.2024: -%32,3 |
| agresif | 24 | 9/24 | -%7,0 | -%9,3 | %48,3 / %55,3 | 04.2025: +%55,1 | 07.2024: -%46,6 |

**Nitelikli yatırımcı (serbest fonlar dahil)**

| Profil | Dönem | PP medyanını geçtiği | Ort. fazla getiri | Medyan fazla getiri | Ort. portföy / PP | En iyi dönem | En kötü dönem |
|---|---|---|---|---|---|---|---|
| temkinli | 24 | 18/24 | +%1,1 | +%1,2 | %56,3 / %55,3 | 03.2025: +%2,9 | 09.2025: -%2,0 |
| dengeli | 24 | 6/24 | -%10,1 | -%11,2 | %45,2 / %55,3 | 06.2025: +%7,9 | 04.2024: -%26,7 |
| agresif | 24 | 7/24 | -%10,0 | -%6,1 | %45,2 / %55,3 | 03.2025: +%39,3 | 07.2024: -%55,1 |

## 4. Örnek kişiler

### Ayşe, 26, uzun vadeli birikim

- Puan 77/100 → puana göre agresif, sonuç **agresif** (sınır: yok)
- İlk 5 öneri: KNJ (Katılım, risk 5), CKL (Değişken, risk 5), OPF (Değişken, risk 5), KTJ (Katılım, risk 6), GBG (Hisse Senedi, risk 6)
- Örnek portföy: KNJ, CKL, OPF, KTJ, GBG
- Kayan pencereli test (agresif): 9/24 dönemde para piyasası medyanını geçti, ortalama fazla getiri -%7,0

### Mehmet, 58, emekliliğe 2 yıl

- Puan 37/100 → puana göre temkinli, sonuç **temkinli** (sınır: yok)
- İlk 5 öneri: RBP (Para Piyasası, risk 1), EIL (Para Piyasası, risk 2), OSD (Borçlanma Araçları, risk 1), OLE (Fon Sepeti, risk 2), NSP (Katılım, risk 1)
- Örnek portföy: RBP, OSD, OLE
- Kayan pencereli test (temkinli): 12/24 dönemde para piyasası medyanını geçti, ortalama fazla getiri -%0,9

### Zeynep, 40, orta yol

- Puan 58/100 → puana göre dengeli, sonuç **dengeli** (sınır: yok)
- İlk 5 öneri: EIL (Para Piyasası, risk 2), NBO (Fon Sepeti, risk 2), OLE (Fon Sepeti, risk 2), FFH (Katılım, risk 4), IDY (Değişken, risk 4)
- Örnek portföy: EIL, NBO, FFH, IDY
- Kayan pencereli test (dengeli): 5/24 dönemde para piyasası medyanını geçti, ortalama fazla getiri -%11,0

### Can, 30, birikimi yok ama riskli

- Puan 78/100 → puana göre agresif, sonuç **dengeli** (sınır: Acil durum birikimi yok: beklenmedik bir ihtiyaçta fonu düşük fiyattan satmak gerekebilir.)
- İlk 5 öneri: EIL (Para Piyasası, risk 2), NBO (Fon Sepeti, risk 2), OLE (Fon Sepeti, risk 2), FFH (Katılım, risk 4), IDY (Değişken, risk 4)
- Örnek portföy: EIL, NBO, FFH, IDY
- Kayan pencereli test (dengeli): 5/24 dönemde para piyasası medyanını geçti, ortalama fazla getiri -%11,0

## 5. Dengeli profil: riskli fon kotası

Kota: önerilerin ve örnek portföyün en az 2'si risk değeri 4+ ve volatilitesi %5+ fonlardan.

| | İlk 10 | Örnek portföy | PP medyanını geçtiği | Ort. fazla getiri | Medyan fazla getiri |
|---|---|---|---|---|---|
| Kotalı (kullanılan) | EIL, NBO, OLE, PLR, NJR, KSK, DBZ, TE4, FFH, IDY | EIL, NBO, FFH, IDY | 5/24 | -%11,0 | -%9,3 |
| Kotasız | EIL, NBO, OLE, PLR, NJR, KSK, DBZ, TE4, TND, RRP | EIL, NBO, NJR, KSK | 8/24 | -%8,1 | -%4,2 |

