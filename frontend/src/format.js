// Sayı biçimlendirme yardımcıları. Metrikler ondalık kesir gelir (0.25 = %25).

export const pct = (v) => {
  if (v == null) return '–'
  if (Math.abs(v) < 0.0005) return '0,0%' // -0,0% gibi görünmesin
  return `${v > 0 ? '+' : ''}${(v * 100).toLocaleString('tr-TR', { maximumFractionDigits: 1, minimumFractionDigits: 1 })}%`
}

export const num = (v, d = 2) => (v == null ? '–' : v.toLocaleString('tr-TR', { maximumFractionDigits: d, minimumFractionDigits: d }))

export const signClass = (v) => (v == null ? '' : v > 0 ? 'up' : v < 0 ? 'down' : '')

export const trDate = (iso, opts) => new Date(iso).toLocaleDateString('tr-TR', opts)

// Ay adı: "Ekim 2026" (TÜFE ayları)
export const monthLabel = (iso) => trDate(iso, { month: 'long', year: 'numeric' })

// Benzerlik yüzdesi = haftalık getiri korelasyonu × 100 (son 1 yıl)
export const simPct = (v) => (v == null ? '–' : `%${Math.round(v * 100)}`)
