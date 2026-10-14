# ML tahmin modülü: walk-forward değerlendirme çıktısı

Veri: 47 aybaşı (01.11.2022 – 01.09.2026), 28,286 örnek, 910 fon. Hedef: 21 işlem günlük getiri.  
Ayar dönemi: 12 ay (10.2023 – 09.2024). Test dönemi: 24 ay (10.2024 – 09.2026), 17,261 tahmin.

## 1. LightGBM hiperparametre ayarı (sadece ayar dönemi)

Seçim ölçütü: ayar dönemindeki aylık fazla getiri MAE'sinin ortalaması. En iyi 5 aday:

| num_leaves | min_child_samples | n_estimators | Fazla MAE |
|---|---|---|---|
| 15 | 100 | 150 | %3,281 |
| 7 | 100 | 150 | %3,288 |
| 7 | 100 | 400 | %3,305 |
| 15 | 100 | 400 | %3,319 |
| 31 | 100 | 150 | %3,342 |

Seçilen: {'num_leaves': 15, 'min_child_samples': 100, 'n_estimators': 150}. Diğer parametreler: objective=l1, learning_rate=0,03, subsample=0,8, colsample=0,8.

## 2. Test dönemi: genel sonuçlar

MAE/RMSE ham getiri, "Fazla" PP medyanına göre fazla getiri üzerinden. Ham yön: getirinin işareti (getirilerin çoğu pozitif olduğundan yanıltıcı). PP üstü/altı yönü: fonun PP medyanını geçip geçmeyeceği. Sıralama korel.: ay içinde tahmin ve gerçekleşen fazla getirinin Spearman korelasyonu (ortalama). İlk 10: her ay tahmini en yüksek 10 fonun gerçekleşen ortalama getirisi.

| Model | Örnek | MAE | RMSE | Fazla MAE | Fazla RMSE | Ham yön | PP üstü/altı yönü | Sıralama korel. | İlk 10 (aylık) | %80 aralık kapsamı |
|---|---|---|---|---|---|---|---|---|---|---|
| Drift (son 1 yılın aylık ortalaması) | 17.261 | %3,71 | %7,34 | %3,65 | %7,31 | %76,0 | %64,5 | 0,155 | %4,10 | %77,0 |
| LightGBM (tüm fonlarda ortak) | 17.261 | %3,91 | %7,49 | %3,88 | %7,46 | %74,8 | %59,6 | 0,054 | %7,57 | %75,1 |
| Sıfır getiri | 17.261 | %4,57 | %7,60 | %4,70 | %7,67 | – | %66,5 | – | – | %76,6 |
| Momentum (son 1 ay devam eder) | 17.261 | %4,90 | %9,47 | %4,91 | %9,44 | %70,3 | %59,6 | 0,140 | %7,37 | %75,8 |

Kıyas: aynı aylarda tüm fonların ortalama getirisi %2,61, PP medyanı %3,54.

## 3. Risk grubuna göre

### Risk 1-2 (2.911 tahmin)

| Model | Örnek | MAE | RMSE | Fazla MAE | Fazla RMSE | Ham yön | PP üstü/altı yönü | Sıralama korel. | İlk 10 (aylık) | %80 aralık kapsamı |
|---|---|---|---|---|---|---|---|---|---|---|
| Drift (son 1 yılın aylık ortalaması) | 2.911 | %0,49 | %0,81 | %0,32 | %0,73 | %99,1 | %74,5 | 0,530 | %3,64 | %80,2 |
| LightGBM (tüm fonlarda ortak) | 2.911 | %0,51 | %0,84 | %0,40 | %0,78 | %99,2 | %66,7 | 0,458 | %3,44 | %77,7 |
| Momentum (son 1 ay devam eder) | 2.911 | %0,54 | %1,01 | %0,55 | %1,00 | %98,6 | %61,0 | 0,460 | %3,51 | %70,0 |
| Sıfır getiri | 2.911 | %3,33 | %3,41 | %3,59 | %3,66 | – | %66,2 | – | – | %76,9 |

### Risk 3-4 (2.163 tahmin)

| Model | Örnek | MAE | RMSE | Fazla MAE | Fazla RMSE | Ham yön | PP üstü/altı yönü | Sıralama korel. | İlk 10 (aylık) | %80 aralık kapsamı |
|---|---|---|---|---|---|---|---|---|---|---|
| Drift (son 1 yılın aylık ortalaması) | 2.163 | %2,02 | %3,03 | %1,97 | %2,98 | %87,8 | %60,3 | 0,103 | %3,15 | %73,0 |
| LightGBM (tüm fonlarda ortak) | 2.163 | %2,22 | %3,34 | %2,21 | %3,28 | %86,9 | %57,7 | 0,022 | %2,81 | %69,8 |
| Momentum (son 1 ay devam eder) | 2.163 | %2,70 | %3,98 | %2,68 | %3,93 | %81,0 | %54,8 | 0,052 | %2,67 | %73,8 |
| Sıfır getiri | 2.163 | %3,37 | %4,02 | %3,55 | %4,18 | – | %65,2 | – | – | %73,5 |

### Risk 5-7 (9.997 tahmin)

| Model | Örnek | MAE | RMSE | Fazla MAE | Fazla RMSE | Ham yön | PP üstü/altı yönü | Sıralama korel. | İlk 10 (aylık) | %80 aralık kapsamı |
|---|---|---|---|---|---|---|---|---|---|---|
| Drift (son 1 yılın aylık ortalaması) | 9.997 | %5,36 | %9,29 | %5,32 | %9,26 | %64,7 | %58,7 | 0,070 | %4,51 | %76,0 |
| Sıfır getiri | 9.997 | %5,53 | %9,35 | %5,59 | %9,40 | – | %63,2 | – | – | %75,7 |
| LightGBM (tüm fonlarda ortak) | 9.997 | %5,62 | %9,44 | %5,59 | %9,41 | %63,0 | %53,8 | -0,002 | %7,58 | %74,1 |
| Momentum (son 1 ay devam eder) | 9.997 | %7,11 | %11,96 | %7,10 | %11,93 | %58,0 | %56,6 | 0,111 | %7,74 | %77,0 |

### Risk değeri yok (2.190 tahmin)

| Model | Örnek | MAE | RMSE | Fazla MAE | Fazla RMSE | Ham yön | PP üstü/altı yönü | Sıralama korel. | İlk 10 (aylık) | %80 aralık kapsamı |
|---|---|---|---|---|---|---|---|---|---|---|
| Drift (son 1 yılın aylık ortalaması) | 2.190 | %2,15 | %4,57 | %2,14 | %4,55 | %84,8 | %82,1 | 0,214 | %2,66 | %81,7 |
| LightGBM (tüm fonlarda ortak) | 2.190 | %2,30 | %4,83 | %2,34 | %4,81 | %84,1 | %78,9 | 0,029 | %1,98 | %81,3 |
| Momentum (son 1 ay devam eder) | 2.190 | %2,81 | %6,09 | %2,88 | %6,09 | %77,8 | %76,4 | 0,104 | %2,45 | %79,6 |
| Sıfır getiri | 2.190 | %3,05 | %4,92 | %3,23 | %5,02 | – | %83,0 | – | – | %83,2 |

## 4. Başarı ölçütü (risk grubu bazında)

| Risk grubu | En iyi referans | LightGBM fazla MAE | Referans fazla MAE | LightGBM ilk 10 | Referans ilk 10 | LightGBM'in daha iyi olduğu ay | Aylık MAE farkı (± std. hata) | Sonuç |
|---|---|---|---|---|---|---|---|---|
| Risk 1-2 | Drift (son 1 yılın aylık ortalaması) | %0,399 | %0,320 | %3,44 | %3,64 | 4/24 | %0,079 ± %0,018 | Başarısız |
| Risk 3-4 | Drift (son 1 yılın aylık ortalaması) | %2,209 | %1,970 | %2,81 | %3,15 | 7/24 | %0,232 ± %0,118 | Başarısız |
| Risk 5-7 | Drift (son 1 yılın aylık ortalaması) | %5,595 | %5,316 | %7,58 | %4,51 | 9/24 | %0,296 ± %0,232 | Başarısız |
| Risk değeri yok | Drift (son 1 yılın aylık ortalaması) | %2,338 | %2,136 | %1,98 | %2,66 | 8/24 | %0,202 ± %0,095 | Başarısız |

Aylık MAE farkı: LightGBM eksi referans (negatif: LightGBM daha iyi).

## 5. Ay ay: fazla getiri MAE'si ve ilk 10

| Ay | MAE lightgbm | MAE drift | MAE momentum | MAE sifir | İlk 10 lightgbm | İlk 10 drift | İlk 10 momentum | Tüm fonlar | PP medyanı |
|---|---|---|---|---|---|---|---|---|---|
| 10.2024 | %4,43 | %4,23 | %3,77 | %3,58 | -%2,17 | %3,94 | %5,44 | -%0,36 | %4,03 |
| 11.2024 | %5,31 | %3,30 | %5,77 | %5,11 | %4,59 | %9,63 | %3,11 | %4,72 | %4,17 |
| 12.2024 | %2,79 | %1,96 | %3,32 | %3,43 | %3,94 | %5,77 | %2,30 | %2,81 | %3,91 |
| 01.2025 | %1,81 | %1,74 | %2,82 | %3,76 | %9,77 | %10,76 | %7,31 | %3,14 | %3,90 |
| 02.2025 | %2,34 | %2,25 | %2,44 | %3,30 | %17,88 | %22,57 | %21,34 | %1,59 | %3,33 |
| 03.2025 | %3,76 | %3,62 | %4,21 | %4,69 | %6,08 | %7,46 | %19,87 | %2,31 | %3,27 |
| 04.2025 | %3,22 | %2,75 | %3,63 | %3,57 | -%5,50 | %8,26 | %5,81 | %1,31 | %4,41 |
| 05.2025 | %2,52 | %2,35 | %4,43 | %3,86 | %4,00 | %10,72 | %8,36 | %3,54 | %4,34 |
| 06.2025 | %5,29 | %5,90 | %5,27 | %7,51 | %27,98 | %11,39 | %12,75 | %7,32 | %3,96 |
| 07.2025 | %2,62 | %3,13 | %2,57 | %4,96 | %4,39 | %6,44 | %4,57 | %4,65 | %3,82 |
| 08.2025 | %1,99 | %2,04 | %2,61 | %3,83 | %7,40 | %5,06 | %5,57 | %3,19 | %3,71 |
| 09.2025 | %3,73 | %3,70 | %4,38 | %5,17 | %11,39 | %1,14 | %5,47 | %3,22 | %3,27 |
| 10.2025 | %1,97 | %1,84 | %3,29 | %3,42 | %14,12 | %9,45 | %12,96 | %2,21 | %3,41 |
| 11.2025 | %2,81 | %2,75 | %3,37 | %3,92 | %9,22 | %2,49 | %7,30 | %1,53 | %3,15 |
| 12.2025 | %3,26 | %2,57 | %4,31 | %4,89 | %10,61 | %18,75 | %26,52 | %3,86 | %3,07 |
| 01.2026 | %7,30 | %7,61 | %7,33 | %10,01 | %40,14 | %28,78 | %39,51 | %9,44 | %3,29 |
| 02.2026 | %4,42 | %3,54 | %9,68 | %3,34 | -%6,85 | -%7,78 | -%10,94 | -%0,26 | %2,91 |
| 03.2026 | %7,74 | %5,92 | %3,86 | %4,64 | %2,93 | -%14,13 | %4,59 | -%2,52 | %3,04 |
| 04.2026 | %3,19 | %4,72 | %9,54 | %6,82 | %10,86 | %1,54 | %3,43 | %6,67 | %3,66 |
| 05.2026 | %2,98 | %3,49 | %5,36 | %3,85 | %9,29 | %2,79 | %13,39 | %2,07 | %3,83 |
| 06.2026 | %3,32 | %3,48 | %4,92 | %4,20 | %2,77 | -%4,77 | %2,03 | %1,50 | %3,21 |
| 07.2026 | %5,01 | %4,13 | %4,73 | %3,67 | %2,41 | -%2,94 | -%5,56 | -%0,33 | %3,27 |
| 08.2026 | %2,98 | %2,95 | %5,33 | %4,99 | %10,42 | %4,03 | %5,33 | %4,43 | %3,17 |
| 09.2026 | %6,75 | %5,86 | %7,69 | %5,37 | -%13,92 | -%43,05 | -%23,49 | -%3,32 | %2,88 |

## 6. Özellik önemi (son test ayında eğitilen model, kazanç payı)

| Özellik | Pay |
|---|---|
| mm_ret_12m | %25,0 |
| mm_ret_1m | %16,2 |
| mdd_12m | %13,4 |
| category | %12,9 |
| ret_1m | %7,0 |
| ret_6m | %4,1 |
| rank_ret_12m | %3,7 |
| ret_3m | %3,6 |
| vol_12m | %3,5 |
| vol_3m | %2,7 |
| risk_level | %2,5 |
| ret_12m | %2,5 |
| rank_ret_1m | %1,8 |
| dist_high_12m | %1,1 |

## 7. ARIMA (40 fonluk tabakalı örnek)

Aynı 40 fon ve 24 test ayında karşılaştırma (ilk 10 bu küçük örnekte anlamlı olmadığından gösterilmez):

| Model | Örnek | MAE | RMSE | Fazla MAE | Fazla RMSE | Ham yön | PP üstü/altı yönü | Sıralama korel. |
|---|---|---|---|---|---|---|---|---|
| ARIMA (fon bazında) | 960 | %2,40 | %3,94 | %2,32 | %3,88 | %82,8 | %66,2 | 0,210 |
| Drift (son 1 yılın aylık ortalaması) | 960 | %2,41 | %3,99 | %2,33 | %3,95 | %82,1 | %68,3 | 0,185 |
| LightGBM (tüm fonlarda ortak) | 960 | %2,60 | %4,28 | %2,56 | %4,22 | %81,2 | %64,8 | 0,052 |
| Momentum (son 1 ay devam eder) | 960 | %3,11 | %5,19 | %3,11 | %5,14 | %77,4 | %61,7 | 0,135 |
| Sıfır getiri | 960 | %3,62 | %4,61 | %3,76 | %4,72 | – | %70,9 | – |

Seçilen mertebeler: (0,0,1) 9 fon, (1,0,0) 7 fon, (0,0,0) 6 fon, (2,0,0) 5 fon, (2,0,1) 4 fon, (1,0,1) 4 fon, (1,0,2) 3 fon, (2,0,2) 1 fon, (0,0,2) 1 fon

