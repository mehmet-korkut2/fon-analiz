import { useState } from 'react'
import { Link } from 'react-router-dom'
import { pct, signClass } from '../format'
import { parseAmount, tl } from '../money'
import EducationWarning from './EducationWarning'

// funds: RecommendationsOut.portfolio, forecast: portfolio_forecast, performance: son 1 yıl (geriye bakış)
export default function PortfolioPlanner({ funds, forecast, performance }) {
  const [amountText, setAmountText] = useState('100.000')
  const amount = parseAmount(amountText)
  return (
    <div className="panel planner">
      <h2>Portföy planlayıcı</h2>
      <EducationWarning />
      <label className="calc-input">
        <span>Toplam tutar</span>
        <span className="amount-field">
          <input inputMode="decimal" value={amountText} onChange={(e) => setAmountText(e.target.value)} />
          <span className="muted">TL</span>
        </span>
      </label>
      {amount == null ? (
        <p className="muted small">Geçerli bir tutar gir.</p>
      ) : (
        <>
          <div className="table-wrap">
            <table className="planner-table">
              <thead>
                <tr>
                  <th>Fon</th><th className="r">Pay</th><th className="r">Tutar</th>
                  <th className="r">1 ay sonra (beklenen)</th><th className="r">%80 aralık</th>
                </tr>
              </thead>
              <tbody>
                {funds.map((f) => {
                  const a = amount * f.weight
                  return (
                    <tr key={f.code}>
                      <td><Link to={`/fonlar/${f.code}`} className="num"><strong>{f.code}</strong></Link> <span className="muted small">{f.category}</span></td>
                      <td className="r num">%{Math.round(f.weight * 100)}</td>
                      <td className="r num">{tl(a)}</td>
                      <td className="r num">{f.pred_return == null ? '–' : tl(a * (1 + f.pred_return))}</td>
                      <td className="r num small">{f.lo == null ? '–' : `${tl(a * (1 + f.lo))} – ${tl(a * (1 + f.hi))}`}</td>
                    </tr>
                  )
                })}
              </tbody>
              {forecast && (
                <tfoot>
                  <tr>
                    <th scope="row">Toplam</th><td className="r num">%100</td><td className="r num">{tl(amount)}</td>
                    <td className="r num"><strong>{tl(amount * (1 + forecast.expected_return))}</strong></td>
                    <td className="r num small">{tl(amount * (1 + forecast.lo))} – {tl(amount * (1 + forecast.hi))}</td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
          {forecast && (
            <p className="muted small">
              Beklenen değer, her fonun geçmiş eğilime dayalı 1 aylık tahmininden ({forecast.horizon_days} işlem günü; ML tahmini değil,
              bkz. <Link to="/model-performansi">model performansı</Link>). Portföy toplamı için %80 aralık: {pct(forecast.lo)} ile {pct(forecast.hi)}.
              {' '}{forecast.interval_method} Fonların tek tek aralıkları toplanamaz, çünkü hepsi aynı anda en kötü durumda olmaz.
            </p>
          )}
          {performance && (
            <div className="lookback">
              <span className="lookback-tag">Geriye bakış, garanti değil</span>
              <p className="small">
                Bu dağılım {performance.start && new Date(performance.start).toLocaleDateString('tr-TR')} tarihinde kurulup tutulsaydı,
                {' '}{tl(amount)} bugün <strong className={`num ${signClass(performance.portfolio.return)}`}>{tl(amount * (1 + performance.portfolio.return))}</strong>{' '}
                olurdu ({pct(performance.portfolio.return)}; aynı dönemde para piyasası medyanı {pct(performance.benchmark.return)}). Fonlar bu dönemin
                verisiyle seçildiği için bu rakam iyimserdir; daha gerçekçi tablo için aşağıdaki geriye dönük teste bak.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
