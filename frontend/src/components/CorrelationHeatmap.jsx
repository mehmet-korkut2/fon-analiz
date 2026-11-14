import { num } from '../format'

// İki uçlu renk: pozitif korelasyon kırmızıya, negatif maviye, 0 nötr griye (renkler index.css --heat-*)
function cellStyle(v) {
  if (v == null) return undefined
  const a = Math.round(Math.min(Math.abs(v), 1) * 100)
  const pole = v >= 0 ? 'var(--heat-pos)' : 'var(--heat-neg)'
  return {
    background: `color-mix(in srgb, ${pole} ${a}%, var(--heat-mid))`,
    color: Math.abs(v) > 0.6 ? 'var(--heat-on-strong)' : undefined,
  }
}

// codes: matris sırası, matrix: korelasyonlar (null: hesaplanamadı)
export default function CorrelationHeatmap({ codes, matrix, caption }) {
  return (
    <div className="table-wrap">
      <table className="heatmap">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th><span className="sr-only">Fon</span></th>
            {codes.map((c) => <th key={c} scope="col" className="num">{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {codes.map((a, i) => (
            <tr key={a}>
              <th scope="row" className="num">{a}</th>
              {codes.map((b, j) => {
                const v = matrix[i]?.[j]
                return i === j ? (
                  <td key={b} className="heat-diag" aria-label={`${a} kendisi`}>–</td>
                ) : (
                  <td key={b} className="num" style={cellStyle(v)} title={`${a} – ${b}: ${v == null ? 'hesaplanamadı' : num(v)}`}>
                    {v == null ? '–' : num(v)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="heat-legend small muted" aria-hidden="true">
        <span>-1 ters</span>
        <span className="heat-scale" />
        <span>+1 aynı yönde</span>
      </div>
    </div>
  )
}
