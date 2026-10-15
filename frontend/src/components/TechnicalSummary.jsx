import { num, trDate } from '../format'

const fmtPrice = (v) => num(v, v < 100 ? 4 : 2)

const TREND = {
  ustunde: 'Fiyat 200 günlük ortalamanın üstünde',
  altinda: 'Fiyat 200 günlük ortalamanın altında',
  esit: 'Fiyat 200 günlük ortalamaya eşit',
}

// Trend etiketi ve 52 haftalık aralık (son fiyat gününe göre; grafik döneminden bağımsız)
export default function TechnicalSummary({ summary }) {
  const r = summary.range_52w
  const rangeLabel = r.full ? '52 haftalık aralık' : `${trDate(r.since)} tarihinden beri aralık`
  return (
    <div className="tech">
      <div className="tech-item">
        <span className="card-label">Trend</span>
        {summary.trend ? (
          <>
            <strong className={`tech-trend ${summary.trend === 'ustunde' ? 'up' : summary.trend === 'altinda' ? 'down' : ''}`}>
              {summary.trend === 'ustunde' ? '▲ ' : summary.trend === 'altinda' ? '▼ ' : ''}{TREND[summary.trend]}
            </strong>
            <span className="muted small">
              Son fiyat {fmtPrice(summary.price)} TL · 200 günlük ortalama {fmtPrice(summary.ma200)} TL
            </span>
          </>
        ) : (
          <span className="muted small">200 günlük ortalama için yeterli fiyat geçmişi yok.</span>
        )}
      </div>
      <div className="tech-item">
        <span className="card-label">{rangeLabel}</span>
        {r.position != null ? (
          <div
            className="range" role="img"
            aria-label={`Son fiyat, en düşük ${fmtPrice(r.low)} TL ile en yüksek ${fmtPrice(r.high)} TL arasında; aralığın %${Math.round(r.position * 100)} noktasında`}
          >
            <div className="range-track"><span className="range-dot" style={{ left: `${r.position * 100}%` }} /></div>
            <div className="range-ends small">
              <span>En düşük {fmtPrice(r.low)} <span className="muted">({trDate(r.low_date)})</span></span>
              <span>En yüksek {fmtPrice(r.high)} <span className="muted">({trDate(r.high_date)})</span></span>
            </div>
          </div>
        ) : (
          <span className="small">{fmtPrice(r.high)} TL (bu dönemde fiyat değişmedi)</span>
        )}
        {r.position != null && (
          <span className="small">
            Son fiyat aralığın <strong>%{Math.round(r.position * 100)}</strong> noktasında
            <span className="muted"> (%0 en düşük, %100 en yüksek)</span>
          </span>
        )}
      </div>
    </div>
  )
}
