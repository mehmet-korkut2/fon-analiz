// TL tutarları ve tutar girişi
export const tl = (v) => (v == null || Number.isNaN(v) ? '–' : `${Math.round(v).toLocaleString('tr-TR')} TL`)
// Kuruşlu: 12.345,67 TL
export const tl2 = (v) => (v == null || Number.isNaN(v) ? '–' : `${v.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} TL`)
// İşaretli kuruşlu (kâr/zarar): +1.234,56 TL
export const signedTl = (v) => (v == null || Number.isNaN(v) ? '–' : `${v > 0 ? '+' : ''}${tl2(v)}`)

// "10.000" ya da "10000,50" gibi girişleri sayıya çevirir; geçersizse null
export function parseAmount(text) {
  const clean = String(text).replace(/\./g, '').replace(',', '.').replace(/[^\d.]/g, '')
  const v = Number(clean)
  return clean && Number.isFinite(v) && v > 0 ? v : null
}

// Büyük TL tutarlarını kısaltır: 2,27 milyar TL, 512,3 milyon TL
export function compactTl(v) {
  if (v == null || Number.isNaN(v)) return '–'
  const fmt = (x, d) => x.toLocaleString('tr-TR', { maximumFractionDigits: d, minimumFractionDigits: d })
  if (v >= 1e9) return `${fmt(v / 1e9, 2)} milyar TL`
  if (v >= 1e6) return `${fmt(v / 1e6, 1)} milyon TL`
  if (v >= 1e3) return `${fmt(v / 1e3, 0)} bin TL`
  return tl(v)
}

export const count = (v) => (v == null ? '–' : v.toLocaleString('tr-TR'))
