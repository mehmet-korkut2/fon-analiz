// Karşılaştırmaya eklenen fonlar; detay sayfaları arasında gezerken kaybolmasın diye
// tarayıcıda saklanır. Gizli pencerede depolama kapalı olabilir, o yüzden try/catch.
const KEY = 'karsilastirma'
export const MAX_COMPARE = 4

export function getCompareList() {
  try {
    const v = JSON.parse(localStorage.getItem(KEY))
    return Array.isArray(v) ? v.filter((c) => typeof c === 'string').slice(0, MAX_COMPARE) : []
  } catch {
    return []
  }
}

export function setCompareList(codes) {
  try {
    localStorage.setItem(KEY, JSON.stringify(codes.slice(0, MAX_COMPARE)))
  } catch {
    // depolama yoksa liste sadece bu sayfada yaşar
  }
}
