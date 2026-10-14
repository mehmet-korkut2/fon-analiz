import { useState } from 'react'
import { Link } from 'react-router-dom'
import { pct, signClass } from '../format'
import { parseAmount, tl } from '../money'
import EducationWarning from './EducationWarning'

// forecast: GET /api/funds/{kod}/forecast yanıtı
export default function ForecastCard({ forecast, unavailable }) {
  const [amountText, setAmountText] = useState('10.000')
  if (unavailable) {
    return (
      <div className="panel forecast">
        <h2>Gelecek 1 ay</h2>
        <p className="muted small">{unavailable}</p>
      </div>
    )
  }
  if (!forecast) return null
  const f = forecast
  const amount = parseAmount(amountText)
  return (
    <div className="panel forecast">
      <div className="forecast-head">
        <div>
          <h2>{f.method_label}: gelecek 1 ay</h2>
          <p className="muted small">{f.horizon_days} işlem günü · {f.risk_group_label}</p>
        </div>
        <div className="forecast-value">
          <span className={`num ${signClass(f.pred_return)}`}>{pct(f.pred_return)}</span>
          <span className="muted small">%80 aralık: {pct(f.lo)} ile {pct(f.hi)}</span>
        </div>
      </div>
      <p className="forecast-note small">
        <strong>{f.note}</strong>{' '}
        {f.coverage != null && <>Testlerde bu risk grubunda aralığın gerçekleşmeyi içerme oranı: <strong>%{Math.round(f.coverage * 100)}</strong> (hedef %80).</>}
        {f.model_note && <> {f.model_note}</>} <Link to="/model-performansi">Model performansı →</Link>
      </p>

      <div className="calc">
        <label className="calc-input">
          <span>Yatırım tutarı</span>
          <span className="amount-field">
            <input inputMode="decimal" value={amountText} onChange={(e) => setAmountText(e.target.value)} aria-describedby="calc-out" />
            <span className="muted">TL</span>
          </span>
        </label>
        <div id="calc-out" className="calc-out" aria-live="polite">
          {amount == null ? (
            <span className="muted small">Geçerli bir tutar gir.</span>
          ) : (
            <>
              <span className="card-label">1 ay sonra beklenen değer</span>
              <span className="calc-main num">{tl(amount * (1 + f.pred_return))}</span>
              <span className="small">%80 aralık: <strong>{tl(amount * (1 + f.lo))}</strong> – <strong>{tl(amount * (1 + f.hi))}</strong></span>
            </>
          )}
        </div>
      </div>
      <EducationWarning />
    </div>
  )
}
