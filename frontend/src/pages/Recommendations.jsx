import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getBacktest, getRecommendations } from '../api/client'
import Disclaimer from '../components/Disclaimer'
import PerfChart from '../components/PerfChart'
import ProfileSummary from '../components/ProfileSummary'
import RiskBar from '../components/RiskBar'
import { num, pct, signClass, trDate } from '../format'
import { loadProfile } from '../profileStore'

// Bileşen adları ve kısa açıklamaları (backend: recommender.COMPONENTS)
const COMPONENTS = [
  ['getiri', 'Fazla getiri', '1 yıllık getirinin risksiz getiriden farkı'],
  ['riske_gore', 'Riske göre getiri', 'Sharpe oranı; fiyatı neredeyse hiç dalgalanmayan fonlarda fazla getiri'],
  ['dusus', 'Düşüş direnci', '1 yıldaki en büyük düşüş (küçük olan iyi)'],
  ['tutarlilik', 'Tutarlılık', '3, 6 ve 12 aylık getirilerin en zayıfı'],
]

function ComponentBars({ components, weights }) {
  return (
    <ul className="comp-bars">
      {COMPONENTS.map(([k, label, desc]) => (
        <li key={k} title={`${desc}. Ağırlık: %${Math.round(weights[k] * 100)}`}>
          <span className="comp-label small">{label}</span>
          <span className="comp-track"><span style={{ width: `${components[k] * 100}%` }} /></span>
          <span className="num small comp-val">{Math.round(components[k] * 100)}</span>
        </li>
      ))}
    </ul>
  )
}

function RecCard({ item, weights }) {
  const m = item.metrics || {}
  return (
    <li className="rec-card">
      <div className="rec-head">
        <span className="rec-rank num">{item.rank}</span>
        <div className="rec-title">
          <Link to={`/fonlar/${item.code}`}><strong className="num">{item.code}</strong> <span className="rec-name">{item.name}</span></Link>
          <span className="muted small rec-meta">{item.category} <RiskBar level={item.risk_level} /></span>
        </div>
        <div className="rec-score">
          <span className="card-label">Puan</span>
          <span className="num">{Math.round(item.score * 100)}</span>
        </div>
      </div>
      <dl className="rec-metrics small">
        <div><dt>1 yıl</dt><dd className={`num ${signClass(m.ret_1y)}`}>{pct(m.ret_1y)}</dd></div>
        <div><dt>Volatilite</dt><dd className="num">{m.volatility_1y == null ? '–' : `${num(m.volatility_1y * 100, 1)}%`}</dd></div>
        <div><dt>Maks. düşüş</dt><dd className={`num ${m.max_drawdown_1y < -0.0005 ? 'down' : ''}`}>{pct(m.max_drawdown_1y)}</dd></div>
        <div><dt>Sharpe</dt><dd className="num" title={m.sharpe_note ?? undefined}>{m.sharpe_1y == null ? '–' : num(m.sharpe_1y)}</dd></div>
      </dl>
      <ComponentBars components={item.components} weights={weights} />
      <div className="rec-why">
        <span className="card-label">Neden önerildi</span>
        <ul>{item.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
        {item.caution && <p className="rec-caution small">{item.caution}</p>}
      </div>
    </li>
  )
}

function PortfolioTable({ funds, showReturn }) {
  return (
    <div className="table-wrap">
      <table className="portfolio-table">
        <thead>
          <tr><th>Fon</th><th className="r">Ağırlık</th>{showReturn && <th className="r">Dönem getirisi</th>}</tr>
        </thead>
        <tbody>
          {funds.map((f) => (
            <tr key={f.code}>
              <td>
                <Link to={`/fonlar/${f.code}`} className="num"><strong>{f.code}</strong></Link>{' '}
                <span className="muted small">{f.category}</span>
              </td>
              <td className="r num">%{Math.round(f.weight * 100)}</td>
              {showReturn && <td className={`r num ${signClass(f.period_return)}`}>{pct(f.period_return)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Backtest({ profile, qualified }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let ignore = false
    getBacktest(profile, qualified)
      .then((d) => { if (!ignore) setData(d) })
      .catch(() => { if (!ignore) setError('Geriye dönük test yüklenemedi.') })
    return () => { ignore = true }
  }, [profile, qualified])

  if (error) return <p className="error">{error}</p>
  if (!data) return <p className="muted">Geriye dönük test hesaplanıyor (ilk açılışta birkaç saniye sürebilir)...</p>
  if (!data.performance) return <p className="muted">Bu profil için geriye dönük test yapılamadı.</p>
  const diff = data.performance.portfolio.return - data.performance.benchmark.return
  return (
    <>
      <p className="small">
        <strong>{trDate(data.selection_date)}</strong> tarihindeki veriyle (o günkü risksiz getiri {pct(data.risk_free_rate)})
        aynı yöntemle seçilen portföy, sonraki 12 ayda para piyasası fonlarının medyanından{' '}
        <strong className={signClass(diff)}>{num(Math.abs(diff) * 100, 1)} puan {diff >= 0 ? 'daha iyi' : 'daha kötü'}</strong> performans gösterdi.
        Seçimde sadece o güne kadarki veri kullanıldı; sonradan işleme kapatılan fonlar da o gün aday sayıldı.
      </p>
      <PerfChart perf={data.performance} />
      <PortfolioTable funds={data.portfolio} showReturn />
    </>
  )
}

export default function Recommendations() {
  const [saved] = useState(loadProfile)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const profile = saved?.result.profile
  const qualified = Boolean(saved?.qualified)

  useEffect(() => { document.title = 'Öneriler · Fon Analiz' }, [])
  useEffect(() => {
    if (!profile) return
    let ignore = false
    getRecommendations(profile, qualified)
      .then((d) => { if (!ignore) setData(d) })
      .catch(() => { if (!ignore) setError('Öneriler yüklenemedi. Backend çalışıyor mu?') })
    return () => { ignore = true }
  }, [profile, qualified])

  if (!saved) {
    return (
      <section className="recs">
        <h1>Öneriler</h1>
        <Disclaimer />
        <div className="panel empty">
          <p><strong>Önce risk profilini belirleyelim.</strong></p>
          <p className="muted">7 soruluk anketi doldurduğunda profiline uygun fonları, neden önerildiklerini ve örnek bir portföyü burada görürsün.</p>
          <p><Link className="btn btn-primary" to="/risk-anketi">Risk anketini doldur →</Link></p>
        </div>
      </section>
    )
  }

  return (
    <section className="recs">
      <div>
        <h1>Sana uygun fonlar</h1>
        <p className="hint">
          {data ? `${data.pool_size} uygun fon arasından, puanı en yüksek ${data.items.length} fon` : 'Yükleniyor...'}
          {data?.as_of && ` · Veriler ${trDate(data.as_of)} tarihli`}
          {data && ` · Aynı kategoriden en fazla ${data.category_limit} fon`}
        </p>
      </div>

      <Disclaimer />

      <div className="recs-top">
        <ProfileSummary saved={saved} compact />
        <div className="panel how">
          <h2>Puan nasıl hesaplanıyor?</h2>
          <p className="small">
            Profiline uygun fonlar dört ölçüte göre birbiriyle karşılaştırılır; her ölçütte fon, adayların yüzde kaçından
            iyi olduğuna göre 0–100 arası puan alır. Toplam puan, profiline göre ağırlıklı ortalamadır.
          </p>
          {data && (
            <ul className="weights small">
              {COMPONENTS.map(([k, label, desc]) => (
                <li key={k}><strong>{label}</strong> %{Math.round(data.weights[k] * 100)} <span className="muted">· {desc}</span></li>
              ))}
            </ul>
          )}
          {data && <p className="muted small">Risksiz getiri (para piyasası fonlarının 1 yıllık medyanı): {pct(data.risk_free_rate)}</p>}
          <p className="small"><Link to="/risk-anketi">Anketi yeniden doldur</Link></p>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {data && data.items.length === 0 && <p className="panel empty">Bu profile uygun fon bulunamadı.</p>}

      {data && data.items.length > 0 && (
        <>
          <h2>Öneriler</h2>
          <ol className="rec-list">
            {data.items.map((item) => <RecCard key={item.code} item={item} weights={data.weights} />)}
          </ol>

          <h2>Örnek portföy</h2>
          <div className="panel">
            <p className="small">
              Önerilerden {data.portfolio.length} fon, mümkün olduğunca farklı kategorilerden, eşit ağırlıkla.{' '}
              <Link to={`/karsilastir?fonlar=${data.portfolio.slice(0, 4).map((f) => f.code).join(',')}`}>Fonları karşılaştır →</Link>
            </p>
            {data.performance && (
              <>
                <h3>Son 1 yılda nasıl giderdi?</h3>
                <p className="notice small">
                  Bu fonlar aynı dönemin verisiyle seçildiği için bu grafik <strong>iyimserdir</strong> (seçim yanlılığı).
                  Gerçekçi bir test için aşağıdaki geriye dönük teste bak.
                </p>
                <PerfChart perf={data.performance} />
              </>
            )}
            <PortfolioTable funds={data.portfolio} showReturn={Boolean(data.performance)} />
          </div>

          <h2>Geriye dönük test</h2>
          <div className="panel">
            <Backtest profile={profile} qualified={qualified} />
          </div>
        </>
      )}
    </section>
  )
}
