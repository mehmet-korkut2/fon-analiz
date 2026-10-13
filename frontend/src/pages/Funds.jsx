import { useEffect, useState } from 'react'
import { getCategories, getFunds } from '../api/client'

const PAGE_SIZE = 25

// [alan, başlık, açıklama]
const COLUMNS = [
  ['ret_1m', '1 ay', 'Son 1 aydaki getiri'],
  ['ret_3m', '3 ay', 'Son 3 aydaki getiri'],
  ['ret_1y', '1 yıl', 'Son 1 yıldaki getiri'],
  ['ret_ytd', 'YBB', 'Yılbaşından bu yana getiri'],
  ['volatility_1y', 'Volatilite', 'Fiyatın ne kadar dalgalandığı (yıllık). Yüksekse risk yüksektir.'],
  ['sharpe_1y', 'Sharpe', 'Alınan risk başına getiri. Risksiz getiri olarak para piyasası fonlarının medyanı kullanılır.'],
  ['max_drawdown_1y', 'Maks. düşüş', 'Son 1 yılda bir zirveden sonraki en büyük kayıp'],
]

const pct = (v) => {
  if (v == null) return '–'
  if (Math.abs(v) < 0.0005) return '0,0%' // -0,0% gibi görünmesin
  return `${v > 0 ? '+' : ''}${(v * 100).toLocaleString('tr-TR', { maximumFractionDigits: 1, minimumFractionDigits: 1 })}%`
}
const num = (v, d = 2) => (v == null ? '–' : v.toLocaleString('tr-TR', { maximumFractionDigits: d, minimumFractionDigits: d }))
const isReturn = (k) => k.startsWith('ret_')

function useDebounced(value, ms = 300) {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

function RiskBar({ level }) {
  if (!level) return <span className="muted">–</span>
  const color = level >= 6 ? '#b4570e' : level >= 4 ? '#c98a1a' : '#0f7a5c'
  return (
    <span className="risk" title={`Risk değeri ${level}/7`}>
      <span className="risk-track"><span style={{ width: `${(level / 7) * 100}%`, background: color }} /></span>
      <span className="num">{level}</span>
    </span>
  )
}

export default function Funds() {
  const [categories, setCategories] = useState([])
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [risk, setRisk] = useState('')
  const [sort, setSort] = useState({ key: 'ret_1y', order: 'desc' })
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const q = useDebounced(query)

  useEffect(() => { getCategories().then(setCategories).catch(() => {}) }, [])
  useEffect(() => { setPage(1) }, [q, category, risk, sort])

  useEffect(() => {
    const [riskMin, riskMax] = risk ? risk.split('-').map(Number) : [undefined, undefined]
    setLoading(true)
    getFunds({
      q: q || undefined, category: category || undefined,
      risk_min: riskMin, risk_max: riskMax,
      sort: sort.key, order: sort.order, page, page_size: PAGE_SIZE,
    })
      .then((d) => { setData(d); setError(null) })
      .catch(() => setError('Fonlar yüklenemedi. Backend çalışıyor mu?'))
      .finally(() => setLoading(false))
  }, [q, category, risk, sort, page])

  const toggleSort = (key) =>
    setSort((s) => (s.key === key ? { key, order: s.order === 'desc' ? 'asc' : 'desc' } : { key, order: key === 'code' ? 'asc' : 'desc' }))

  const SortHeader = ({ k, children, title, right }) => (
    <th className={right ? 'r' : undefined} title={title} aria-sort={sort.key === k ? (sort.order === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button type="button" className="th-btn" onClick={() => toggleSort(k)}>
        {children}
        <span className="sort-ind">{sort.key === k ? (sort.order === 'asc' ? '▲' : '▼') : ''}</span>
      </button>
    </th>
  )

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1
  const asOf = data?.items.find((f) => f.price_date)?.price_date

  return (
    <section className="funds">
      <div className="fx-head">
        <div>
          <h1>Fonlar</h1>
          <p className="hint">
            {data ? `${data.total.toLocaleString('tr-TR')} fon` : 'Yükleniyor...'}
            {asOf && ` · Veriler ${new Date(asOf).toLocaleDateString('tr-TR')} tarihli`}
            {data?.sample && ' · Veritabanı boş, örnek veri gösteriliyor'}
          </p>
        </div>
      </div>

      <div className="filters">
        <label className="search">
          <span className="sr-only">Fon ara</span>
          <input type="search" placeholder="Fon kodu veya adı ara..." value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
        <label>
          <span className="sr-only">Kategori</span>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">Tüm kategoriler</option>
            {categories.map((c) => <option key={c.name} value={c.name}>{c.name} ({c.count})</option>)}
          </select>
        </label>
        <label>
          <span className="sr-only">Risk</span>
          <select value={risk} onChange={(e) => setRisk(e.target.value)}>
            <option value="">Tüm risk seviyeleri</option>
            <option value="1-3">Düşük risk (1–3)</option>
            <option value="4-5">Orta risk (4–5)</option>
            <option value="6-7">Yüksek risk (6–7)</option>
          </select>
        </label>
      </div>

      {error && <p className="error">{error}</p>}

      <div className={`table-wrap${loading ? ' is-loading' : ''}`}>
        <table className="funds-table">
          <thead>
            <tr>
              <SortHeader k="code">Kod</SortHeader>
              <SortHeader k="name">Fon</SortHeader>
              <SortHeader k="risk_level" title="TEFAS risk değeri (1 en düşük, 7 en yüksek)">Risk</SortHeader>
              <th className="r">Fiyat</th>
              {COLUMNS.map(([k, label, title]) => <SortHeader key={k} k={k} title={title} right>{label}</SortHeader>)}
            </tr>
          </thead>
          <tbody>
            {data && data.items.length === 0 && <tr><td colSpan={4 + COLUMNS.length} className="muted">Aramana uyan fon yok.</td></tr>}
            {data?.items.map((f) => (
              <tr key={f.code}>
                <td className="num"><strong>{f.code}</strong></td>
                <td className="fund-name">
                  <span>{f.name}</span>
                  {f.category && <span className="muted small">{f.category}</span>}
                </td>
                <td><RiskBar level={f.risk_level} /></td>
                <td className="r num">{f.price != null ? num(f.price, 4) : '–'}</td>
                {COLUMNS.map(([k]) => {
                  const v = f.metrics?.[k]
                  const cls = isReturn(k) && v != null ? (v > 0 ? 'up' : v < 0 ? 'down' : '') : k === 'max_drawdown_1y' && v < 0 ? 'down' : ''
                  return (
                    <td key={k} className={`r num ${cls}`}>
                      {k === 'sharpe_1y' ? num(v) : k === 'volatility_1y' ? (v == null ? '–' : `${num(v * 100, 1)}%`) : pct(v)}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="pager">
        <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>← Önceki</button>
        <span className="num">Sayfa {page} / {totalPages}</span>
        <button type="button" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Sonraki →</button>
      </div>
      <p className="hint">Geçmiş performans gelecekteki sonuçların göstergesi değildir. Bu site yatırım tavsiyesi vermez.</p>
    </section>
  )
}
