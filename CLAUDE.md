# Fon Analiz Platformu

Mehmet Korkut'un bilgisayar mühendisliği bitirme projesi. TEFAS yatırım fonlarını analiz eden, karşılaştıran ve risk profiline göre öneren web uygulaması. Kullanıcıyla Türkçe konuş.

Planın tamamı ve ilerleme durumu: `YOL_HARITASI.md` (biten maddeleri `[x]` ile işaretle).

## Ortam

- Windows, PowerShell. Python 3.13, Node.js 24.
- Backend sanal ortamı: `backend\.venv` (komutlardan önce `backend\.venv\Scripts\activate`).
- Veritabanı: yerelde SQLite (`backend\fon.db`, git'e girmez). Canlıda PostgreSQL olacak.

## Yapı

- `backend/` FastAPI + SQLAlchemy 2.0
  - `app/models.py`: funds, prices, fund_metrics, portfolio_allocations, users, risk_profiles
  - `app/routers/`: funds (liste/filtre/sıralama/detay/fiyatlar), fx (döviz), status
  - `app/services/tefas_client.py`: TEFAS'ın 2026 JSON API'si (`/api/funds/fonGetiriBazliBilgiGetir`, `/api/funds/fonFiyatBilgiGetir`)
  - `app/services/updater.py`: fiyatları DB'ye yazar, ardından metrikleri hesaplar
  - `app/services/metrics.py` + `metrics_job.py`: getiri, volatilite, Sharpe, maks. düşüş
  - `app/services/fx.py`: TCMB today.xml (resmi) + Truncgil v4 (anlık)
  - `app/scheduler.py`: APScheduler, hafta içi 21:00; açılışta veri eskiyse günceller
  - `scripts/`: `tefas_yukle`, `metrik_hesapla`, `baglanti_testi`
- `frontend/` React 19 + Vite, React Router, axios. Sayfalar: Home, Funds, Doviz.

## Komutlar

```powershell
# backend (backend klasöründe, .venv aktifken)
uvicorn app.main:app --reload
pytest
python -m scripts.tefas_yukle --limit 0        # tüm fonlar, son 5 yıl
python -m scripts.metrik_hesapla

# frontend (frontend klasöründe)
npm run dev
npm run build
npm run lint
```

## Kurallar ve bilinenler

- Değişiklikten sonra `pytest` ve `npm run lint` / `npm run build` çalıştır.
- `YOL_HARITASI.md`'yi düzenlerken her zaman önce dosyanın son hâlini oku ve sadece ilgili maddeleri değiştir (dosya editörde de düzenleniyor; tamamını yeniden yazmak başka değişiklikleri siler).
- TEFAS artık portföy dağılımı, yatırımcı sayısı ve fon büyüklüğü yayınlamıyor; bu sütunlar boş kalabilir.
- TEFAS fiyat geçmişi en fazla 60 ay; `periyod` sadece 1, 3, 6, 12, 36, 60 olabilir.
- Fon adları Türkçe büyük harf (İ, Ş, Ğ); aramada `tr_upper()` kullanılıyor.
- Metrikler ondalık kesir olarak saklanır (0.25 = %25). Sharpe için risksiz getiri: para piyasası fonlarının 1 yıllık medyan getirisi.
- Kullanıcıya yatırım tavsiyesi verilmez; arayüzde uyarı metinleri korunmalı.
- `funds.status`: SPK Bülteni 2026/60 ile 7 şirketin (Tera, Pusula, Hedef, Atlas, A1 Capital, Pardus, Bulls) fonları `islem_kapali`, tasfiye listesindekiler (`app/data/spk_2026_60_tasfiye.txt`) `islem_kapali_tasfiye`. Bu fonlar ve eski verili fonlar (son fiyatı 7 günden eski) listede varsayılan olarak gizli; sıralamaya ve risksiz getiriye girmez. TEFAS'ın `tefasDurum` alanı bu fonlar için `true` geliyor, kullanılamıyor.
- Fiyat verisi değiştirilmez. Tek günlük sıçrayıp ertesi gün geri dönen fiyatlar sadece metrik hesabında yok sayılır (`data_quality.drop_one_day_glitches`).
- Yeni sütun eklerken `init_db()` boş bırakılabilir sütunları mevcut tabloya ekler (Alembic'e geçene kadar).

## Sıradaki işler

3. aşama devam ediyor: fon detay sayfası (fiyat grafiği, metrik kartları, kategori sırası), karşılaştırma endpoint'i ve sayfası, sıralamalar. Ayrıntı için `YOL_HARITASI.md`.
