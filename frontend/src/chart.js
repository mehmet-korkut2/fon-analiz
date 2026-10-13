// Grafik ekseni yardımcıları (detay ve karşılaştırma sayfaları ortak kullanır)

// Eksen etiketleri: ondalık sayısı tek tek değere değil, grafiğin aralığına göre (hepsi aynı uzunlukta olsun)
export const axisDigits = (span) => (span < 0.1 ? 3 : span < 1 ? 2 : span < 10 ? 1 : 0)

// Ay başı tikleri: her ayın ilk işlem günü; uzun dönemlerde 3 ya da 6 ayda bir.
// Recharts'ın kendi tikleri aynı ayı iki kez yazabildiği için ("Ara 25 Ara 25") elle seçiyoruz.
export function monthTicks(points, months) {
  const step = months <= 12 ? 1 : months <= 36 ? 3 : 6
  return points
    .filter((p, i) => i > 0 && p.date.slice(5, 7) !== points[i - 1].date.slice(5, 7))
    .filter((p) => (Number(p.date.slice(5, 7)) - 1) % step === 0)
    .map((p) => p.date)
}

// Logaritmik eksen tikleri: 1-2-5 dizisi (…, 50, 100, 200, 500, 1000, …); çok fazlaysa sadece 10'un katları.
// 100 (baz) aralıktaysa her zaman dahil.
export function logTicks(min, max) {
  if (!(min > 0) || !(max > min)) return undefined
  const ticks = []
  for (let e = Math.floor(Math.log10(min)); e <= Math.ceil(Math.log10(max)); e++) {
    for (const m of [1, 2, 5]) {
      const v = m * 10 ** e
      if (v >= min && v <= max) ticks.push(v)
    }
  }
  const out = ticks.length > 8 ? ticks.filter((v) => Number.isInteger(Math.log10(v)) || v === 100) : ticks
  return out.length >= 2 ? out : [min, ...out, max]
}
