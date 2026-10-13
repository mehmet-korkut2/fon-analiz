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

## 3. Geriye dönük test özeti

| Profil | Seçim günü | Seçimdeki risksiz getiri | Portföy | Getiri | Kıyas (PP medyanı) | Fark | Volatilite | Maks. düşüş |
|---|---|---|---|---|---|---|---|---|
| temkinli | 2025-10-13 | %57,1 | HVK, HVT, OLE | %41,0 | %46,3 | -%5,3 | %3,5 | -%2,5 |
| dengeli | 2025-10-13 | %57,1 | HVK, PRY, OLE, RIK | %34,0 | %46,3 | -%12,3 | %4,1 | -%3,2 |
| agresif | 2025-10-13 | %57,1 | BIH, NAU, HAM, OTJ, RIK | %27,7 | %46,3 | -%18,6 | %18,3 | -%15,4 |

## 4. Örnek kişiler

### Ayşe, 26, uzun vadeli birikim

- Puan 77/100 → puana göre agresif, sonuç **agresif** (sınır: yok)
- İlk 5 öneri: KNJ (Katılım, risk 5), CKL (Değişken, risk 5), OPF (Değişken, risk 5), KTJ (Katılım, risk 6), GBG (Hisse Senedi, risk 6)
- Örnek portföy: KNJ, CKL, GBG, OPF, KTJ
- Geriye dönük test (2025-10-13 seçim → 2026-10-13): portföy %27,7, para piyasası medyanı %46,3; portföy volatilitesi %18,3, maks. düşüş -%15,4. Seçilen fonlar: BIH %65,4, NAU %13,6, HAM %23,6, OTJ %26,5, RIK %9,5

### Mehmet, 58, emekliliğe 2 yıl

- Puan 35/100 → puana göre temkinli, sonuç **temkinli** (sınır: yok)
- İlk 5 öneri: RBP (Para Piyasası, risk 1), EIL (Para Piyasası, risk 2), OSD (Borçlanma Araçları, risk 1), OLE (Fon Sepeti, risk 2), NSP (Katılım, risk 1)
- Örnek portföy: RBP, OSD, OLE
- Geriye dönük test (2025-10-13 seçim → 2026-10-13): portföy %41,0, para piyasası medyanı %46,3; portföy volatilitesi %3,5, maks. düşüş -%2,5. Seçilen fonlar: HVK %23,9, HVT %51,3, OLE %47,8

### Zeynep, 40, orta yol

- Puan 60/100 → puana göre dengeli, sonuç **dengeli** (sınır: yok)
- İlk 5 öneri: EIL (Para Piyasası, risk 2), NBO (Fon Sepeti, risk 2), OLE (Fon Sepeti, risk 2), PLR (Para Piyasası, risk 2), NJR (Borçlanma Araçları, risk 2)
- Örnek portföy: EIL, NBO, NJR, OLE
- Geriye dönük test (2025-10-13 seçim → 2026-10-13): portföy %34,0, para piyasası medyanı %46,3; portföy volatilitesi %4,1, maks. düşüş -%3,2. Seçilen fonlar: HVK %23,9, PRY %54,8, OLE %47,8, RIK %9,5

### Can, 30, birikimi yok ama riskli

- Puan 87/100 → puana göre agresif, sonuç **dengeli** (sınır: Acil durum birikimi yok: beklenmedik bir ihtiyaçta fonu düşük fiyattan satmak gerekebilir.)
- İlk 5 öneri: EIL (Para Piyasası, risk 2), NBO (Fon Sepeti, risk 2), OLE (Fon Sepeti, risk 2), PLR (Para Piyasası, risk 2), NJR (Borçlanma Araçları, risk 2)
- Örnek portföy: EIL, NBO, NJR, OLE
- Geriye dönük test (2025-10-13 seçim → 2026-10-13): portföy %34,0, para piyasası medyanı %46,3; portföy volatilitesi %4,1, maks. düşüş -%3,2. Seçilen fonlar: HVK %23,9, PRY %54,8, OLE %47,8, RIK %9,5

