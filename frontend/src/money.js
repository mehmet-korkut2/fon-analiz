// TL tutarları ve tutar girişi
export const tl = (v) => (v == null || Number.isNaN(v) ? '–' : `${Math.round(v).toLocaleString('tr-TR')} TL`)

// "10.000" ya da "10000,50" gibi girişleri sayıya çevirir; geçersizse null
export function parseAmount(text) {
  const clean = String(text).replace(/\./g, '').replace(',', '.').replace(/[^\d.]/g, '')
  const v = Number(clean)
  return clean && Number.isFinite(v) && v > 0 ? v : null
}
