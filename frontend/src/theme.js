// Grafik renkleri: CSS değişkenlerine bağlanır (index.css :root), böylece koyu temada kendiliğinden değişir.
// SVG sunum öznitelikleri (stroke, fill) var() kabul eder.
export const C = {
  grid: 'var(--chart-grid)',
  axis: 'var(--ink-2)',
  surface: 'var(--surface)',
  neutral: 'var(--chart-neutral)',
  price: 'var(--chart-price)',
  forecast: 'var(--chart-forecast)',
  ma50: 'var(--chart-ma50)',
  ma200: 'var(--chart-ma200)',
  up: 'var(--up)',
  down: 'var(--down)',
}

// Kategorik palet: sıra sabit, renk fonun seçildiği yuvaya bağlı
export const SERIES = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)']
