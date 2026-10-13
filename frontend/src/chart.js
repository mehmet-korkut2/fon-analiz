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
