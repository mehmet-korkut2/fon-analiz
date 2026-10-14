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

## Dosyalar

| Dosya | Ne yapar |
|---|---|
| `backend/app/ml/features.py` | Fiyat paneli, aybaşı başlangıç günleri, `features_at(t)`, `target_at(t)`, `build_dataset` |
| `backend/app/ml/models.py` | `Zero`, `Drift`, `Momentum`, `LightGBM` (+`BEST_PARAMS`), `LightGBMRank` (keşif), `Arima` |
| `backend/app/ml/evaluation.py` | `walk_forward`, `train_rows`, `add_intervals` (konformal), `summarize`, `monthly`, `head_to_head` |
| `backend/app/ml/report.py` | Takvim, başarı ölçütü ve bütün sonuçların JSON raporu (`build_report`) |
| `backend/app/ml/job.py` | Gece işi: tahminler (`forecasts`) her gece, rapor (`ml_reports`) 28 günde bir |
| `backend/app/routers/ml.py` | `GET /api/funds/{kod}/forecast`, `GET /api/ml/performance` |
| `backend/scripts/ml_degerlendir.py` | Değerlendirme betiği (markdown çıktı) |
| `backend/tests/test_ml.py`, `test_ml_job.py` | Sızıntı, hedef, metrik, model, gece işi ve API testleri |

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

- **Fon detayı:** `forecasts` tablosundan drift tahmini ve %80 aralık; kapsama oranı, "Bu bir ML tahmini değildir; testlerde en isabetli yöntem fonun geçmiş ortalama getirisinin sürmesi varsayımı çıktı." etiketi, LightGBM'in o risk grubundaki sonucu, fiyat grafiğinde tahmin konisi ve yatırım hesaplayıcı. İşleme kapatılmış fonlarda tahmin yok.
- **Aralık:** `pred + q10` ile `pred + q90`; q10/q90, drift'in o risk grubundaki geçmiş hatalarının dilimleri (ham getiri). Test dönemi kapsamı: %73,4 (risk 1–2), %75,0 (3–4), %75,7 (5–7), %82,6 (risk değeri yok).
- **Portföy planlayıcı:** Fonların drift tahminlerinin ağırlıklı ortalaması; portföy aralığı, portföyün son 1 yıldaki 21 günlük getirilerinin ortalamadan sapmalarının %10/%90 dilimleri (fon aralıkları toplanmaz).
- **`/model-performansi`:** `ml_reports`'taki son rapor.

## Gece işi ve süreler

`app/services/updater.run_update` → metrikler → kayan pencereli öneri testi → `app/ml/job.run`:

| Adım | Ne zaman | Süre (1.071 fon, 13.10.2026) |
|---|---|---|
| Panel + veri seti | her gece | ~10 sn (5,0 + 4,6) |
| Tahminler (`forecasts`, 841 fon) | her gece | 0,2 sn |
| Gece işinin tamamı, rapor yenilenmeden | her gece | 10,1 sn |
| Rapor (ARIMA'sız, keşif dahil) | rapor 28 günden eskiyse | +~20 sn |
| ARIMA (40 fon × 24 ay) | sadece betikle | ~4 dk |

Yeterli geçmiş yoksa (yeni kurulum) iş atlanır ve hata sayılmaz.
