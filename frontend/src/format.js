// Sayı biçimlendirme yardımcıları. Metrikler ondalık kesir gelir (0.25 = %25).

export const pct = (v) => {
  if (v == null) return '–'
  if (Math.abs(v) < 0.0005) return '0,0%' // -0,0% gibi görünmesin
  return `${v > 0 ? '+' : ''}${(v * 100).toLocaleString('tr-TR', { maximumFractionDigits: 1, minimumFractionDigits: 1 })}%`
}

export const num = (v, d = 2) => (v == null ? '–' : v.toLocaleString('tr-TR', { maximumFractionDigits: d, minimumFractionDigits: d }))

export const signClass = (v) => (v == null ? '' : v > 0 ? 'up' : v < 0 ? 'down' : '')

export const trDate = (iso, opts) => new Date(iso).toLocaleDateString('tr-TR', opts)
