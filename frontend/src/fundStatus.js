// SPK kararıyla işleme kapatılan fonlar (backend: app/services/fund_status.py)
export const STATUS_LABELS = {
  islem_kapali: 'İşleme kapalı',
  islem_kapali_tasfiye: 'Tasfiye sürecinde',
}

export const isClosed = (f) => Boolean(f?.status && f.status !== 'aktif')

// "En iyi" vurgusu ve sıralama yarışına girmeyen fonlar
export const isExcludedFromBest = (f) => f.is_stale || isClosed(f)
