import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { getCategories, getRankings } from '../api/client'
import RiskBar from '../components/RiskBar'
import { num, pct, signClass, trDate } from '../format'

const RETURN_PERIODS = [
  ['ret_1m', '1 ay'], ['ret_3m', '3 ay'], ['ret_6m', '6 ay'],
  ['ret_ytd', 'Yılbaşından bu yana'], ['ret_1y', '1 yıl'], ['ret_3y', '3 yıl'],
]
const DEFAULT_PERIOD = 'ret_1y'

// Liste anahtarına göre başlık, açıklama ve değer biçimi
const LISTS = {
  return: {
    title: (periodLabel) => `En yüksek getiri (${periodLabel})`,
    desc: 'Seçilen dönemde fiyatı en çok artan fonlar. Yüksek getiri çoğu zaman yüksek riskle gelir.',
    fmt: (v) => <span className={signClass(v)}>{pct(v)}</span>,
  },
  volatility: {
    title: () => 'En düşük volatilite (1 yıl)',
    desc: 'Fiyatı en az dalgalanan fonlar. Genellikle para piyasası ve kısa vadeli borçlanma fonlarıdır; düşük risk, düşük getiri de demek olabilir.',
    fmt: (v) => `${num(v * 100, 1)}%`,
  },
  sharpe: {
    title: () => 'En yüksek Sharpe oranı (1 yıl)',
    desc: "Alınan her birim risk için risksiz getirinin (para piyasası fonlarının medyanı) en çok üstüne çıkan fonlar. Volatilitesi %5'in altındaki fonlar (çoğunlukla para piyasası benzeri) dahil değildir; onlarda Sharpe anlamlı değil.",
    fmt: (v) => num(v),
  },
}

function RankingCard({ list, periodLabel }) {
  const meta = LISTS[list.key]
  return (
    <section className="rank-card" aria-labelledby={`rank-${list.key}`}>
      <h2 id={`rank-${list.key}`}>{meta.title(periodLabel)}</h2>
      <p className="metric-desc">{meta.desc}</p>
      {list.items.length === 0 ? (
        <p className="muted">Bu filtreyle sıralanacak fon yok.</p>
      ) : (
        <ol className="rank-list">
          {list.items.map((f) => (
            <li key={f.code}>
              <span className="rank-no num">{f.rank}</span>
              <Link to={`/fonlar/${f.code}`} className="rank-fund">
                <span><strong className="num">{f.code}</strong> <span className="rank-name">{f.name}</span></span>
                <span className="muted small rank-meta">
                  {f.category ?? 'Kategorisiz'} <RiskBar level={f.risk_level} />
                </span>
              </Link>
              <span className="rank-value num">{meta.fmt(f.value)}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

export default function Rankings() {
  const [params, setParams] = useSearchParams()
  const category = params.get('kategori') || ''
  const period = RETURN_PERIODS.some(([k]) => k === params.get('donem')) ? params.get('donem') : DEFAULT_PERIOD
  const [categories, setCategories] = useState([])
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => { document.title = 'Sıralamalar · Fon Analiz' }, [])
  useEffect(() => { getCategories().then(setCategories).catch(() => {}) }, [])

  useEffect(() => {
    let ignore = false
    setLoading(true)
    getRankings({ category: category || undefined, period, limit: 10 })
      .then((d) => { if (!ignore) { setData(d); setError(null) } })
      .catch(() => { if (!ignore) setError('Sıralamalar yüklenemedi. Backend çalışıyor mu?') })
      .finally(() => { if (!ignore) setLoading(false) })
    return () => { ignore = true }
  }, [category, period])

  const setParam = (name, value, fallback) => setParams((p) => {
    const next = new URLSearchParams(p)
    if (!value || value === fallback) next.delete(name)
    else next.set(name, value)
    return next
  }, { replace: true })

  const periodLabel = RETURN_PERIODS.find(([k]) => k === period)[1]

  return (
    <section className="rankings">
      <div>
        <h1>Sıralamalar</h1>
        <p className="hint">
          {data ? `${data.eligible.toLocaleString('tr-TR')} fon arasından ilk 10` : 'Yükleniyor...'}
          {data?.as_of && ` · Veriler ${trDate(data.as_of)} tarihli`}
          {' · Verisi güncellenmeyen, kapanmış ve SPK kararıyla işleme kapatılan fonlar dahil edilmez'}
        </p>
      </div>

      <div className="filters">
        <label>
          <span className="sr-only">Kategori</span>
          <select value={category} onChange={(e) => setParam('kategori', e.target.value)}>
            <option value="">Tüm kategoriler</option>
            {categories.map((c) => <option key={c.name} value={c.name}>{c.name} ({c.count})</option>)}
          </select>
        </label>
        <label>
          <span className="sr-only">Getiri dönemi</span>
          <select value={period} onChange={(e) => setParam('donem', e.target.value, DEFAULT_PERIOD)}>
            {RETURN_PERIODS.map(([k, label]) => <option key={k} value={k}>Getiri: {label}</option>)}
          </select>
        </label>
      </div>

      {error && <p className="error">{error}</p>}

      <div className={`rank-grid${loading ? ' is-loading' : ''}`}>
        {data?.lists.map((l) => <RankingCard key={l.key} list={l} periodLabel={periodLabel} />)}
      </div>

      <p className="hint">
        Sıralamalar geçmiş verilere dayanır ve tek bir metriğe göredir; bir fonun size uygun olduğunu göstermez.
        Geçmiş performans gelecekteki sonuçların göstergesi değildir. Bu site yatırım tavsiyesi vermez.
      </p>
    </section>
  )
}
