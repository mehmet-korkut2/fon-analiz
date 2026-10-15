# Fon Analiz Platformu

Mehmet Korkut'un bilgisayar mühendisliği bitirme projesi. TEFAS yatırım fonlarını analiz eden, karşılaştıran ve risk profiline göre öneren web uygulaması. Kullanıcıyla Türkçe konuş.

Planın tamamı ve ilerleme durumu: `YOL_HARITASI.md` (biten maddeleri `[x]` ile işaretle).

## Ortam

- Windows, PowerShell. Python 3.13, Node.js 24.
- Backend sanal ortamı: `backend\.venv` (komutlardan önce `backend\.venv\Scripts\activate`).
- Veritabanı: yerelde SQLite (`backend\fon.db`, git'e girmez).
- **Yayın yok:** Uygulama yayına alınmayacak; sunumda kendi bilgisayarında çalışacak. PostgreSQL, Render/Vercel, gece işini sunucuya taşıma, alan adı ve Alembic `YOL_HARITASI.md`'de "Gelecek çalışmalar"da. Sunum hazırlığı yapıldı: `FonAnaliz_Baslat.bat` / `FonAnaliz_Durdur.bat` (kökte), internetsiz çalışma (döviz son bilinen kurlar `fx_snapshots`'ta; güncelleme internet yoksa `offline` durumuyla atlanır, bağlantı koparsa durur), yedek `scripts.yedekle` / `scripts.geri_yukle` (`backups/`, git'e girmez).

## Yapı

- `backend/` FastAPI + SQLAlchemy 2.0
  - `app/models.py`: funds, prices, fund_metrics, portfolio_allocations, users, risk_profiles
  - `app/routers/`: funds (liste/filtre/sıralama/detay/fiyatlar), compare, rankings, risk (anket, profil), recommendations (öneri, geriye dönük test), fx (döviz), status
  - `app/services/tefas_client.py`: TEFAS'ın 2026 JSON API'si (`/api/funds/fonGetiriBazliBilgiGetir`, `/api/funds/fonFiyatBilgiGetir`)
  - `app/services/updater.py`: fiyatları DB'ye yazar, ardından metrikleri hesaplar
  - `app/services/metrics.py` + `metrics_job.py`: getiri, volatilite, Sharpe, maks. düşüş
  - `app/services/risk_survey.py` + `recommender.py`: risk anketi, öneri puanlaması (dengeli profilde riskli fon kotası), örnek portföy, kayan pencereli geriye dönük test (yöntem ve gerekçeler: `docs/oneri_sistemi.md`). Geriye dönük test ~1 dk sürer; gece güncellemesinden sonra hesaplanıp `backtest_windows` tablosuna yazılır, API oradan okur
  - `app/services/fund_status.py`, `data_quality.py`: SPK kararıyla kapatılan fonlar, fiyat sıçramaları
  - `app/ml/`: 1 aylık getiri tahmini (features, models, evaluation, report, job). LightGBM drift'i geçemedi; sitede ML tahmini değil, drift + konformal %80 aralık gösterilir (`forecasts` her gece, `ml_reports` 28 günde bir). Ayrıntı: `docs/ml_tahmin.md`, rapor bölümü `docs/rapor/06_ml_tahmin.md`
  - `app/services/technical.py`: 50/200 günlük ortalama, trend, 52 haftalık aralık (`/api/funds/{kod}/technical`)
  - `app/services/sanal_portfoy.py`: Sanal Portföy (hayali para, tek kullanıcı; tablolar sanal_portfoy, sanal_emirler, sanal_degerler). Nakit/pozisyon emir kayıtlarından hesaplanır. Valör: alış = TEFAS `fonGeriAlisValor`, satış = `fonSatisValor` (adlar ters görünür; yabancı hisse fonunda 1 / 3). İleri fiyat: hedef günün fiyatı biliniyorsa sonraki iş günü. Gece güncellemesinden sonra `process()`
  - `app/services/fx.py`: TCMB today.xml (resmi) + Truncgil v4 (anlık)
  - `app/scheduler.py`: APScheduler, hafta içi 21:00; açılışta veri eskiyse günceller
  - `scripts/`: `tefas_yukle`, `metrik_hesapla`, `baglanti_testi`, `veri_kalitesi`, `fon_durumu_isaretle`, `fon_bilgisi_yukle`, `geriye_donuk_test`, `oneri_analizi`, `ml_degerlendir`
- `frontend/` React 19 + Vite, React Router, axios, Recharts. Sayfalar: Home, Funds, FundDetail, Rankings, Compare, RiskSurvey, Recommendations, SanalPortfoy, ModelPerformance, Doviz. Risk profili `localStorage`'da (`profileStore.js`).
  - Tema: renkler ve yazı tipleri `src/index.css` başındaki CSS değişkenlerinde (açık + koyu tema, `prefers-color-scheme`); grafik renkleri `src/theme.js` (var(--…)). Sayfa ve bileşenlerde sabit renk kodu yazma. Fontlar `@fontsource` ile gömülü (latin + latin-ext).
  - Ekran görüntüsü + yatay taşma ölçümü: `node scripts/ekran_goruntusu.mjs <klasör> <önek> [--mobil] [--koyu] [--ekran] [--sayfa ...]` (backend ve `npm run dev` açıkken)

## Komutlar

```powershell
# hepsini başlat / durdur (proje kökünde, çift tıklama da olur)
.FonAnaliz_Baslat.bat
.FonAnaliz_Durdur.bat

# backend (backend klasöründe, .venv aktifken)
uvicorn app.main:app --reload
pytest
python -m scripts.yedekle [--not sunum-oncesi]  # backups/fon_<tarih>.db
python -m scripts.geri_yukle [--liste | <dosya>]  # varsayılan en son yedek; önce backend'i durdur
python -m scripts.tefas_yukle --limit 0        # tüm fonlar, son 5 yıl
python -m scripts.metrik_hesapla

# frontend (frontend klasöründe)
npm run dev
npm run build
npm run lint
node scripts/uctan_uca.mjs [--cevrimdisi]      # uçtan uca test (uygulama açıkken), docs/rapor/07 7.3
```

## Kurallar ve bilinenler

- Değişiklikten sonra `pytest` ve `npm run lint` / `npm run build` çalıştır.
- `YOL_HARITASI.md`'yi düzenlerken her zaman önce dosyanın son hâlini oku ve sadece ilgili maddeleri değiştir (dosya editörde de düzenleniyor; tamamını yeniden yazmak başka değişiklikleri siler).
- TEFAS portföy dağılımı ve yönetim ücreti yayınlamıyor. Fon büyüklüğü ve yatırımcı sayısı yalnızca güncel değer olarak `fonBilgiGetir`'den (fon başına bir istek) gelir; gece güncellemesinde `funds.total_value`, `investor_count`, `info_date`'e yazılır. Geçmişi yok, bu yüzden öneri ve geriye dönük testte kullanılmaz. `prices` tablosundaki `total_value`/`investor_count` sütunları boş. KAP bağlantısı, valör ve son işlem saati `fonProfilBilgiGetir`'den (`funds.kap_url`, `buy_valor`, `sell_valor`, `cutoff_time`; 30 günde bir yenilenir); KAP'tan veri çekilmez.
- TEFAS fiyat geçmişi en fazla 60 ay; `periyod` sadece 1, 3, 6, 12, 36, 60 olabilir.
- Fon adları Türkçe büyük harf (İ, Ş, Ğ); aramada `tr_upper()` kullanılıyor.
- Metrikler ondalık kesir olarak saklanır (0.25 = %25). Sharpe için risksiz getiri: para piyasası fonlarının 1 yıllık medyan getirisi.
- 1 yıllık volatilitesi %5'in altındaki fonlarda Sharpe hesaplanmaz (`MIN_VOL_FOR_SHARPE`), API `sharpe_note` döner. Bu fonlar para piyasası benzeri: fiyat neredeyse doğrusal, volatilitenin çoğu pazartesiye yansıyan hafta sonu faizi. TEFAS fiyatları her gün değişiyor; "fiyatı seyrek güncellenen fon" sorunu veride yok (incelendi, 13.10.2026).
- Kullanıcıya yatırım tavsiyesi verilmez; arayüzde uyarı metinleri korunmalı.
- KAP verisi (bildirimler, portföy dağılım raporları, KAP'ın fon listesi) saklanmaz ve uygulamada gösterilmez: KAP'ın kullanım koşulu MKK'nın yazılı izni olmadan kopyalamayı ve "ileride kullanılmak üzere saklamayı" yasaklıyor. Fon detayında yalnızca KAP'ın yatırım fonları listesine bağlantı var (`KAP_FUNDS_URL`).
- Her iş bittiğinde ilgili rapor bölümünü (`docs/rapor/NN_*.md`) da güncelle: birinci çoğul şahıs, sayılar gerçek veriden, emin olunmayan yer `[DOLDUR: ...]`. Görseller `python -m scripts.rapor_gorselleri`, Word/PDF `python -m scripts.rapor_olustur` (Word gerekir; bağımlılıklar `requirements-rapor.txt`).
- `funds.status`: SPK Bülteni 2026/60 ile 7 şirketin (Tera, Pusula, Hedef, Atlas, A1 Capital, Pardus, Bulls) fonları `islem_kapali`, tasfiye listesindekiler (`app/data/spk_2026_60_tasfiye.txt`) `islem_kapali_tasfiye`. Bu fonlar ve eski verili fonlar (son fiyatı 7 günden eski) listede varsayılan olarak gizli; sıralamaya ve risksiz getiriye girmez. TEFAS'ın `tefasDurum` alanı bu fonlar için `true` geliyor, kullanılamıyor.
- Fiyat verisi değiştirilmez. Tek günlük sıçrayıp ertesi gün geri dönen fiyatlar sadece metrik hesabında yok sayılır (`data_quality.drop_one_day_glitches`).
- Yeni sütun eklerken `init_db()` boş bırakılabilir sütunları mevcut tabloya ekler (Alembic'e geçene kadar).

## Sıradaki işler

5. ve 6. aşamalar (öneri sistemi, ML tahmin) tamamlandı. Sırada 7. aşama (yerel sunum hazırlığı, kullanıcı testi, rapor, sunum) ve 3. aşamada kalan kıyaslama (BIST 100, enflasyon, beta). Ayrıntı için `YOL_HARITASI.md`.
