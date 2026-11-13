# ML Tahmin Modülü (teknik belge)

Gelecek 1 aylık (21 işlem günü) fon getirisi tahmini: tasarım, kod, sızıntı önlemleri, değerlendirme, sitedeki kullanım ve çalıştırma. Rapor bölümü: `docs/rapor/06_ml_tahmin.md`. Sonuç tablolarının tamamı: `docs/ml_tahmin_cikti.md`.

Veri tarihi: 13.10.2026.

## Özet

| | |
|---|---|
| Hedef | 21 işlem günlük getiri; modeller para piyasası (PP) medyanına göre **fazla getiriyi** öğrenir, ham tahmin = PP seviyesi (drift) + fazla getiri |
| Referanslar | Sıfır getiri, drift (son 1 yılın aylık ortalaması), momentum (son 1 ay devam eder) |
| Modeller | LightGBM (tüm fonlarda ortak), ARIMA (40 fonluk tabakalı örnek), keşif: LightGBM ay içi sıra hedefi |
| Değerlendirme | Walk-forward; ayar 10.2023–09.2024 (12 ay), test 10.2024–09.2026 (24 ay, 17.261 tahmin) |
| Sonuç | **LightGBM hiçbir risk grubunda drift'i geçemedi**; ARIMA drift ile aynı; keşif varyantı da geçemedi |
| Sitede | ML tahmini yok; "geçmiş eğilime dayalı tahmin" (drift) + konformal %80 aralık + kapsama oranı |
| Tahmin karnesi | 13.11.2026'dan beri her gece her fon için 1..21 işlem günü ufkunda tahmin + ufka ayrı kalibre edilmiş %80 aralık kalıcı saklanır (`forecast_days`), gerçekleşenle karşılaştırılır; canlı ve geriye dönük kayıtlar ayrı (bkz. "Tahmin karnesi") |

## Dosyalar

| Dosya | Ne yapar |
|---|---|
| `backend/app/ml/features.py` | Fiyat paneli, aybaşı başlangıç günleri, `features_at(t)`, `target_at(t)`, `build_dataset` |
| `backend/app/ml/models.py` | `Zero`, `Drift`, `Momentum`, `LightGBM` (+`BEST_PARAMS`), `LightGBMRank` (keşif), `Arima` |
| `backend/app/ml/evaluation.py` | `walk_forward`, `train_rows`, `add_intervals` (konformal), `summarize`, `monthly`, `head_to_head` |
| `backend/app/ml/report.py` | Takvim, başarı ölçütü ve bütün sonuçların JSON raporu (`build_report`) |
| `backend/app/ml/job.py` | Gece işi: gün gün tahminler (`forecast_days`) ve karne özeti (`forecast_summaries`) her gece, rapor (`ml_reports`) 28 günde bir; eski `forecasts` tablosunu bir kez aktarır |
| `backend/app/ml/horizons.py` | Tahmin karnesi: vektörel drift (`DriftPanel`), ufka göre konformal aralık (`Calibrator`), test dönemi değerlendirmesi (`evaluate`), kayıt (`store`), gerçekleşenle karşılaştırma (`realize`, `fund_scorecard`, `summarize_all`) |
| `backend/app/ml/trading_calendar.py` | İşlem günü takvimi: hafta sonu + Türkiye resmî tatilleri (`holidays`), hedef tarih |
| `backend/app/routers/ml.py` | `GET /api/funds/{kod}/forecast`, `GET /api/funds/{kod}/forecast-scorecard?as_of=&source=`, `GET /api/ml/performance` |
| `backend/scripts/ml_degerlendir.py` | Değerlendirme betiği (markdown çıktı) |
| `backend/tests/test_ml.py`, `test_ml_job.py` | Sızıntı, hedef, metrik, model, gece işi ve API testleri |
| `backend/tests/test_horizons.py` | Karne: sızıntı, tatil takvimi, aralık içi/dışı, ufka göre kalibrasyon, canlı/geriye dönük, yöntem sürümü, eski tablonun aktarımı |

## Komutlar

```powershell
cd backend
python -m scripts.ml_degerlendir --arima --kaydet > ..\docs\ml_tahmin_cikti.md   # tam değerlendirme (~4,5 dk), sonucu sayfaya da kaydet
python -m scripts.ml_degerlendir --ayar --arima                                   # hiperparametre ayarını yeniden yap (~6 dk)
python -m scripts.ml_degerlendir --kayittan > ..\docs\ml_tahmin_cikti.md          # kayıtlı son raporu yazdır (hesaplamaz)
```

## Veri ve özellikler

Her ayın ilk işlem günü (`month_starts`), en az 1 yıllık geçmişi olan ve fiyatı güncel olan fonlar için bir örnek: 47 aybaşı (01.11.2022 – 01.09.2026), **28.286 örnek, 910 fon**.

| Özellik | Açıklama |
|---|---|
| `ret_1m`, `ret_3m`, `ret_6m`, `ret_12m` | 21/63/126/252 işlem günlük getiri |
| `vol_3m`, `vol_12m` | Günlük getirilerin yıllıklandırılmış standart sapması |
| `mdd_12m`, `dist_high_12m` | 1 yıllık maksimum düşüş, 1 yıllık zirveye uzaklık |
| `rank_ret_1m`, `rank_ret_12m` | Aynı gün bütün fonlar arasındaki yüzdelik sıra |
| `category`, `risk_level` | Kategori (kategorik), TEFAS risk değeri (boş olabilir) |
| `mm_ret_1m`, `mm_ret_12m` | PP fonlarının medyan getirisi (aynı gün bütün fonlar için aynı) |

Hedef dağılımı: 21 günlük getirilerin %79,3'ü pozitif, %38,4'ü PP medyanının üstünde; risk 1–2 / 3–4 / 5–7 gruplarında standart sapma %1,1 / %3,3 / %8,9.

## Sızıntı önlemleri

1. `features_at(t)` yalnızca `t` ve öncesindeki fiyatları kullanır (test: `t`'den sonraki fiyatlar değiştirildiğinde özellikler aynı kalır).
2. Tek günlük hatalı fiyat temizliği bir günü ertesi güne bakarak işaretler; bu yüzden `t` gününün kendisi için **temizlenmemiş** fiyat kullanılır.
3. Eğitimde yalnızca hedef penceresi `t`'den **önce** biten örnekler (`train_rows`: `end < t`). Test: `t`'de bilinmeyen bütün gerçekleşmeler bozulduğunda `t`'deki tahmin değişmez.
4. Konformal aralık yalnızca hedefi `t`'den önce biten tahminlerin hatalarıyla kurulur.
5. Hiperparametreler yalnızca ayar döneminde seçildi; test dönemi ayarda kullanılmadı. Takvim ve başarı ölçütü sonuçlardan önce koda yazıldı.
6. Bilinen sızıntı: kategori ve risk değeri için yalnızca bugünkü değerler var.

## Hiperparametreler

12 aday (`num_leaves` 7/15/31 × `min_child_samples` 100/400 × `n_estimators` 150/400), ölçüt ayar dönemindeki aylık fazla getiri MAE'si ortalaması. En iyi 5:

| num_leaves | min_child_samples | n_estimators | Fazla MAE |
|---|---|---|---|
| **15** | **100** | **150** | **%3,281** |
| 7 | 100 | 150 | %3,288 |
| 7 | 100 | 400 | %3,305 |
| 15 | 100 | 400 | %3,319 |
| 31 | 100 | 150 | %3,342 |

Sabit: `objective=l1`, `learning_rate=0.03`, `subsample=0.8`, `colsample_bytree=0.8`, `seed=42`. Eğitim hedefi %0,5–99,5 dilimlerine kırpılır (SPK kapanışındaki −%99 gibi uç değerler için); değerlendirmede kırpma yok. Aylık yeniden değerlendirme yeniden ayar yapmaz (`BEST_PARAMS`).

## Sonuçlar (test dönemi)

| Model | Fazla MAE | Fazla RMSE | PP üstü/altı yönü | Sıralama korel. | İlk 10 (aylık) |
|---|---|---|---|---|---|
| **Drift** | **%3,65** | **%7,31** | %64,5 | **0,155** | %4,10 |
| LightGBM | %3,88 | %7,46 | %59,6 | 0,054 | %7,57 |
| Sıfır | %4,70 | %7,67 | %66,5 | – | – |
| Momentum | %4,91 | %9,44 | %59,6 | 0,140 | %7,37 |
| *Keşif: LightGBM sıra* | *%4,06* | *%7,48* | *%60,2* | *0,109* | *%6,97* |

Başarı ölçütü (risk grubu bazında, en iyi referans her grupta drift): LightGBM 4 grubun hiçbirinde başarılı değil. Risk 5–7'de ilk 10'u daha iyi (%7,58'e karşı %4,51) ama hatası daha yüksek. ARIMA (40 fon): fazla MAE %2,32, aynı fonlarda drift %2,33. Ayrıntılar ve yorum: rapor bölümü.

## Sitede kullanım

- **Fon detayı:** `forecast_days`'in son tahmin günündeki 21 günlük kaydından drift tahmini ve %80 aralık; kapsama oranı, "Bu bir ML tahmini değildir; testlerde en isabetli yöntem fonun geçmiş ortalama getirisinin sürmesi varsayımı çıktı." etiketi, LightGBM'in o risk grubundaki sonucu, fiyat grafiğinde tahmin konisi (1..21 günlük kayıtlar: gerçek hedef tarihler ve her günün kendi aralığı) ve yatırım hesaplayıcı. Altında tahmin karnesi. İşleme kapatılmış fonlarda tahmin yok.
- **Aralık:** `pred + q10` ile `pred + q90`; q10/q90, drift'in o ufuk ve risk grubundaki geçmiş hatalarının dilimleri (ham getiri). Kartta gösterilen kapsama, ufka göre değerlendirmenin 21 günlük satırıdır (aşağıda). İlk sürümün (aylık başlangıçlı, yalnız 21 gün) kapsaması: %73,4 (risk 1–2), %75,0 (3–4), %75,7 (5–7), %82,6 (risk değeri yok); raporun `drift_interval` bölümünde ve sayfada "İlk yöntem" olarak duruyor.
- **Portföy planlayıcı:** Fonların drift tahminlerinin ağırlıklı ortalaması; portföy aralığı, portföyün son 1 yıldaki 21 günlük getirilerinin ortalamadan sapmalarının %10/%90 dilimleri (fon aralıkları toplanmaz).
- **`/model-performansi`:** `ml_reports`'taki son rapor (ufka göre karne dahil) ve `forecast_summaries` (kaydedilen tahminlerin karnesi, kaynak ve yöntem sürümüne göre).

## Gece işi ve süreler

`app/services/updater.run_update` → metrikler → kayan pencereli öneri testi → `app/ml/job.run`:

| Adım | Ne zaman | Süre (1.071 fon, 13.10.2026) |
|---|---|---|
| Panel + veri seti | her gece | ~10 sn (5,0 + 4,6) |
| Tahminler (`forecasts`, 841 fon), karneden önce | her gece | 0,2 sn |
| Gece işinin tamamı, rapor yenilenmeden | her gece | 10,1 sn |
| Rapor (ARIMA'sız, keşif dahil) | rapor 28 günden eskiyse | +~20 sn |
| ARIMA (40 fon × 24 ay) | sadece betikle | ~4 dk |

Tahmin karnesi eklendikten sonra (13.11.2026, 1.075 fon, 860 fon tahminli):

| Adım | Ne zaman | Süre |
|---|---|---|
| 21 ufuk için kalibrasyon (`Calibrator`) | her gece | 1,6 sn |
| Bir günün kayıtları (18.060) | her gece | 0,3 sn + yazma |
| Bütün fonların karne özeti (`summarize_all`, 1,07 milyon kayıt) | her gece | 9,8 sn (kayıt sayısıyla doğrusal; bir yılda ~40 sn) |
| Ufka göre değerlendirme (`evaluate`, rapora) | rapor yenilenince | 5,3 sn |
| İlk çalıştırma: 60 günü geriye dönük doldurma | bir kez | ~45 sn |
| Fon karnesi API | istek başına | 36–47 ms |

Yeterli geçmiş yoksa (yeni kurulum) iş atlanır ve hata sayılmaz.

## Tahmin karnesi

Her gece, her fon ve her ufuk (1..21 işlem günü) için bir kayıt `forecast_days`'e eklenir: tahmin günü (`as_of`), o günkü fiyat, ufuk, hedef tarih, tahmin edilen fiyat, %80 aralığın alt/üst sınırı, `method` (`drift-konformal`), `method_version`, `source` (`canli` / `geriye_donuk`), risk grubu, aralığın kurulduğu hata sayısı (`calib_n`). Kayıtlar güncellenmez ve silinmez; gerçekleşen fiyat tutulmaz, `prices`'tan okunur.

**Tahmin.** h günlük ufukta (1 + ret_12m)^(h/252) − 1; h = 21'de `features_at`'teki drift ile aynı (test: `test_vectorized_drift_matches_features_at`).

**Aralık.** Ufuk h, risk grubu g, tahmin günü t: drift'in her işlem gününden başlatılan h günlük tahminlerinin hatalarından (gerçekleşen − tahmin, ham getiri), hedef günü t'den önce gelenlerin (başlangıç satırı + h < t) %10 ve %90 dilimleri. Grupta 50'den az hata varsa bütün gruplar. Canlı ve geriye dönük kayıtlarda her gün için ayrı kurulur; rapordaki değerlendirmede hız için ayda bir (ayın ilk işlem günü).

**Ek sızıntı önlemi.** t'deki uygunluk (son 7 günde fiyat, son 252 günde ≥ 200 fiyat) t günü için temizlenmemiş fiyatın varlığına bakar; `features_at`'te t'nin temizlenmiş değeri kullanılıyordu (temizlik t+1'e bakar). Test: t'den sonraki bütün fiyatlar bozulup t+1 t'yi "tek günlük hata" gibi gösterecek şekilde değiştirildiğinde t'deki kayıtlar aynı kalır.

**Hedef tarih.** `trading_calendar.target_dates`: verideki işlem günleri önce, sonrası takvimle (hafta sonu + `holidays.Turkey`). Takvim 14.10.2021–22.10.2026 arasındaki 1.264 fiyat günüyle birebir tuttu; arife günleri işlem günü. Gerçekleşen, verideki h'inci işlem gününden ölçülür; takvimle farklıysa karnede "takvimde X" notu çıkar.

**Canlı / geriye dönük.** Canlı: son fiyat gününün gece işinde (o gün için canlı kayıt yoksa) yazılır. Geriye dönük: son 60 işlem gününden canlı (1 günlük ufuk dahil) ya da geriye dönük kaydı olmayan günler, yalnızca o güne kadarki veriyle. İlk çalıştırmada 20.08–12.11.2026 dolduruldu (1.052.184 kayıt). Bilinen sınırlama: işleme kapalı fon listesi ve risk değeri bugünkü.

**Yöntem sürümleri** (`horizons.METHOD_VERSIONS`):

| Sürüm | Yöntem | Kayıtlar |
|---|---|---|
| v0 | 21 günlük drift; aralık yalnızca aybaşı başlatılan tahminlerin hatalarıyla, risk grubuna göre | 22.10.2026, 844 kayıt (eski `forecasts`'tan kurtarıldı) |
| v1 | 1..21 günlük drift; aralık her ufuk ve risk grubu için, her işlem günü başlangıçlı hatalarla; tatil takvimi | 13.11.2026'dan beri |

Yöntem değişirse `METHOD_VERSION` artırılır: yeni günler yeni sürümle yazılır, dolu günler yeniden hesaplanmaz, karne ve özetler sürüme göre ayrı gösterilir (test: `test_method_version_change_keeps_old_records`).

**Test dönemi sonuçları** (01.10.2024–30.09.2026, 502 işlem günü, her ufukta 364.465 tahmin; kapsama / ortalama mutlak sapma, sapma = (gerçekleşen − tahmin) / tahmin):

| Risk grubu | 1 gün | 2 gün | 1 hafta | 2 hafta | 1 ay |
|---|---|---|---|---|---|
| Risk 1–2 | %78,7 / %0,10 | %77,0 / %0,14 | %78,7 / %0,16 | %77,3 / %0,28 | %74,0 / %0,62 |
| Risk 3–4 | %80,7 / %0,31 | %81,1 / %0,46 | %81,7 / %0,78 | %82,5 / %1,15 | %83,3 / %1,85 |
| Risk 5–7 | %80,4 / %0,94 | %80,7 / %1,40 | %80,5 / %2,35 | %82,1 / %3,35 | %83,2 / %5,21 |
| Risk değeri yok | %84,5 / %0,34 | %85,1 / %0,51 | %85,8 / %0,85 | %86,9 / %1,26 | %88,6 / %1,98 |
| Tümü | %80,6 / %0,64 | %80,7 / %0,96 | %81,0 / %1,60 | %81,9 / %2,30 | %82,3 / %3,61 |

Geriye dönük kayıtların karnesi (20.08–12.11.2026, 13.11.2026 itibarıyla): 1 gün %79,5 / %0,69, 2 gün %80,4 / %1,02, 1 hafta %79,0 / %1,77, 2 hafta %78,9 / %2,66, 1 ay %71,5 / %4,99 (ortalama sapma −%4,48: dönemde fonlar geçmiş eğilimin altında kaldı).

**Boyut.** Kayıt başına ~205 bayt (indeksler dahil); bir gece ~18.000 kayıt ≈ 3,7 MB, yılda ≈ 0,9 GB. 13.11.2026'da veritabanı 303,6 MB; sıkıştırılmış yedek 79,5 MB (`scripts.yedekle`, gzip). İndeksler: benzersiz (`fund_code`, `as_of`, `horizon`, `source`) fon sorgusunu karşılar; `as_of` indeksi gün sorgularını (gece işi, son tahmin günü).
