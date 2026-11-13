import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getFavorites } from '../api/client'
import { useAuth } from '../auth'
import { MAX_COMPARE, setCompareList } from '../compareList'
import FavoriteButton from '../components/FavoriteButton'
import LoginRequired from '../components/LoginRequired'
import RiskBar from '../components/RiskBar'
import { num, pct, signClass, trDate } from '../format'
import { tl } from '../money'

const fmtPrice = (v) => (v == null ? '–' : num(v, v < 100 ? 4 : 2))

// Kısa karne: son tahmin günlerinin 1 günlük tahminlerinden kaçı %80 aralıkta kaldı; en sonuncusu işaretle.
function ForecastHits({ f }) {
  const h = f.forecast
  if (!h) return <span className="muted small">Tahmin yok</span>
  const back = h.n - h.live
  return (
    <span className="fav-hits" title={`Son ${h.n} tahmin gününün 1 günlük tahmini${back ? `; ${back} tanesi geriye dönük hesaplanmış` : ''}. En son: ${trDate(h.last_as_of)}`}>
      <span className="num">{h.in_band}/{h.n}</span> aralıkta
      <span className={h.last_in_band ? 'badge-ok' : 'badge-fail'}>son: {h.last_in_band ? '✓ içinde' : '✗ dışında'}</span>
    </span>
  )
}

function Position({ p }) {
  if (!p) return <span className="muted">–</span>
  return (
    <span className="fav-pos">
      <span className="num">{p.units.toLocaleString('tr-TR')} pay · {tl(p.value)}</span>
      {p.pnl_pct != null && <span className={`num small ${signClass(p.pnl_pct)}`}>{pct(p.pnl_pct)}</span>}
    </span>
  )
}

export default function Favoriler() {
  const { user, favorites } = useAuth()
  const nav = useNavigate()
  const [funds, setFunds] = useState(null)
  const [error, setError] = useState(null)
  const [picked, setPicked] = useState(null) // karşılaştırmaya seçilenler; null: ilk 4 favori

  useEffect(() => { document.title = 'Favorilerim · Fon Analiz' }, [])
  // listeden çıkarılan fon tabloda soluk kalır (yanlışlıkla çıkarılırsa yıldızla geri eklenebilir); yenileyince gider
  useEffect(() => {
    if (!user) return
    getFavorites().then(setFunds).catch(() => setError('Favoriler yüklenemedi.'))
  }, [user])

  const active = useMemo(() => (funds ?? []).filter((f) => favorites.has(f.code)), [funds, favorites])
  const selected = (picked ?? active.slice(0, MAX_COMPARE).map((f) => f.code)).filter((c) => favorites.has(c))
  const warned = active.filter((f) => f.warning)

  if (!user) {
    return (
      <section className="auth-page">
        <h1>Favorilerim</h1>
        <LoginRequired title="Favoriler için giriş yap">Fon sayfalarındaki ☆ düğmesiyle favori ekleyebilir, burada hepsini bir arada görebilirsin.</LoginRequired>
      </section>
    )
  }

  const toggle = (code) => {
    const has = selected.includes(code)
    setPicked(has ? selected.filter((c) => c !== code) : [...selected, code].slice(-MAX_COMPARE))
  }
  const compare = () => {
    setCompareList(selected)
    nav(`/karsilastir?fonlar=${selected.join(',')}`)
  }

  return (
    <section className="favorites-page">
      <div>
        <h1>Favorilerim</h1>
        <p className="hint">Fon listesindeki, fon sayfalarındaki, karşılaştırmadaki ve sıralamalardaki ☆ düğmesiyle ekle ya da çıkar.</p>
      </div>
      {error && <p className="error">{error}</p>}
      {!funds && !error && <p className="muted">Yükleniyor...</p>}
      {funds && funds.length === 0 && (
        <p className="muted">Henüz favori fonun yok. <Link to="/fonlar">Fonlara göz at →</Link></p>
      )}
      {warned.length > 0 && (
        <div className="notice notice-closed small fav-warning" role="note">
          <strong>{warned.length} favori fonda uyarı var:</strong>{' '}
          {warned.map((f, i) => <span key={f.code}>{i > 0 && ' · '}<Link to={`/fonlar/${f.code}`}>{f.code}</Link> {f.warning}</span>)}
        </div>
      )}
      {funds && funds.length > 0 && (
        <>
          <div className="fav-actions">
            <button type="button" className="btn btn-primary" disabled={selected.length < 2} onClick={compare}>
              Seçilenleri karşılaştır ({selected.length})
            </button>
            <span className="muted small">En fazla {MAX_COMPARE} fon; varsayılan olarak ilk {MAX_COMPARE} favori seçili.</span>
          </div>
          <div className="table-wrap">
            <table className="funds-table fav-table stack-table">
              <thead>
                <tr>
                  <th><span className="sr-only">Favori</span></th>
                  <th><span className="sr-only">Karşılaştırmaya seç</span></th>
                  <th>Fon</th>
                  <th className="r">Fiyat</th>
                  <th className="r">Günlük</th>
                  <th className="r">1 ay</th>
                  <th className="r">1 yıl</th>
                  <th>Risk</th>
                  <th title="Son 10 tahmin gününün 1 günlük tahminlerinden kaçının %80 aralıkta kaldığı">Tahmin karnesi</th>
                  <th>Sanal portföy</th>
                </tr>
              </thead>
              <tbody>
                {funds.map((f) => {
                  const on = favorites.has(f.code)
                  const m = f.metrics
                  return (
                    <tr key={f.code} className={on ? '' : 'is-removed'}>
                      <td data-label="Favori"><FavoriteButton code={f.code} compact /></td>
                      <td data-label="Karşılaştır">
                        <input type="checkbox" aria-label={`${f.code} karşılaştırmaya`} disabled={!on}
                          checked={selected.includes(f.code)} onChange={() => toggle(f.code)} />
                      </td>
                      <td className="fund-name">
                        <Link to={`/fonlar/${f.code}`}><strong>{f.code}</strong> {f.name}</Link>
                        {f.category && <span className="muted small">{f.category}</span>}
                        {f.warning && <span className={`small ${f.status !== 'aktif' ? 'closed-badge' : 'stale-badge'}`}>{f.warning}</span>}
                      </td>
                      <td data-label="Fiyat" className="r num">{fmtPrice(f.price)}{f.price_date && <span className="muted small fav-date">{trDate(f.price_date, { day: 'numeric', month: 'short' })}</span>}</td>
                      <td data-label="Günlük" className={`r num ${signClass(m?.daily_change)}`}>{pct(m?.daily_change)}</td>
                      <td data-label="1 ay" className={`r num ${signClass(m?.ret_1m)}`}>{pct(m?.ret_1m)}</td>
                      <td data-label="1 yıl" className={`r num ${signClass(m?.ret_1y)}`}>{pct(m?.ret_1y)}</td>
                      <td data-label="Risk"><RiskBar level={f.risk_level} /></td>
                      <td data-label="Tahmin karnesi"><ForecastHits f={f} /></td>
                      <td data-label="Sanal portföy"><Position p={f.position} /></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="muted small">
            Tahmin karnesi: fonun son 10 tahmin gününün 1 günlük tahminlerinden gerçekleşenlerin kaçının %80 aralıkta kaldığı
            (geriye dönük hesaplananlar dahil; ayrıntı fon sayfasında). Sanal portföy sütunu, sanal portföyündeki açık pozisyonu gösterir.
            Geçmiş performans gelecekteki sonuçların göstergesi değildir.
          </p>
        </>
      )}
    </section>
  )
}
