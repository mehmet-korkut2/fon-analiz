import { useCallback, useEffect, useMemo, useState } from 'react'
import { getFx } from '../api/client'

const REFRESH_MS = 60_000
const FEATURED = ['USD', 'EUR', 'GBP', 'GRA']
const GROUPS = [
  { key: 'doviz', label: 'Döviz' },
  { key: 'altin', label: 'Altın ve değerli madenler' },
  { key: 'diger', label: 'Borsa ve emtia' },
]

const fmt = (v, digits = 4) =>
  v == null ? '–' : v.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: digits })

function Change({ value }) {
  if (value == null) return <span className="muted">–</span>
  const cls = value > 0 ? 'up' : value < 0 ? 'down' : 'muted'
  const arrow = value > 0 ? '▲' : value < 0 ? '▼' : ''
  return <span className={cls}>{arrow} %{fmt(Math.abs(value), 2)}</span>
}

export default function Doviz() {
  const [source, setSource] = useState('canli')
  const [group, setGroup] = useState('doviz')
  const [query, setQuery] = useState('')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    getFx(source)
      .then((d) => { setData(d); setError(null) })
      .catch((e) => setError(e.response?.data?.detail || 'Kurlar alınamadı. Backend çalışıyor mu?'))
      .finally(() => setLoading(false))
  }, [source])

  useEffect(() => {
    setLoading(true)
    load()
    const id = setInterval(load, REFRESH_MS)
    return () => clearInterval(id)
  }, [load])

  // TCMB sadece döviz yayınlar
  const activeGroup = source === 'tcmb' ? 'doviz' : group

  const rows = useMemo(() => {
    if (!data) return []
    const q = query.trim().toLocaleLowerCase('tr')
    return data.rates.filter(
      (r) =>
        r.group === activeGroup &&
        (!q || r.code.toLocaleLowerCase('tr').includes(q) || r.name.toLocaleLowerCase('tr').includes(q)),
    )
  }, [data, activeGroup, query])

  const featured = data ? FEATURED.map((c) => data.rates.find((r) => r.code === c)).filter(Boolean) : []

  return (
    <section className="fx">
      <div className="fx-head">
        <div>
          <h1>Döviz ve altın</h1>
          <p className="hint">
            {data ? <>Kaynak: {data.source_name} · Son güncelleme: {data.updated_at}</> : 'Yükleniyor...'}
            {data?.stale && <strong> · Kaynağa ulaşılamadı, son bilinen veriler gösteriliyor</strong>}
          </p>
        </div>
        <div className="seg" role="group" aria-label="Veri kaynağı">
          <button type="button" aria-pressed={source === 'canli'} onClick={() => setSource('canli')}>Anlık</button>
          <button type="button" aria-pressed={source === 'tcmb'} onClick={() => setSource('tcmb')}>TCMB resmi</button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {featured.length > 0 && (
        <div className="cards">
          {featured.map((r) => (
            <div key={r.code} className="card">
              <span className="card-label">{r.name}</span>
              <span className="card-value num">{fmt(r.selling ?? r.buying)}</span>
              <Change value={r.change} />
            </div>
          ))}
        </div>
      )}

      <div className="fx-tools">
        {source === 'canli' && (
          <div className="tabs" role="tablist">
            {GROUPS.map((g) => (
              <button key={g.key} type="button" role="tab" aria-selected={group === g.key} onClick={() => setGroup(g.key)}>
                {g.label}
              </button>
            ))}
          </div>
        )}
        <label className="search">
          <span className="sr-only">Ara</span>
          <input type="search" placeholder="Ara: USD, euro, gram..." value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Kod</th><th>Ad</th>
              <th className="r">Alış</th><th className="r">Satış</th>
              {source === 'canli' ? <th className="r">Günlük değişim</th> : <th className="r">Efektif satış</th>}
            </tr>
          </thead>
          <tbody>
            {loading && !data && <tr><td colSpan={5} className="muted">Yükleniyor...</td></tr>}
            {data && rows.length === 0 && <tr><td colSpan={5} className="muted">Sonuç yok.</td></tr>}
            {rows.map((r) => (
              <tr key={r.code}>
                <td className="num"><strong>{r.code}</strong>{r.unit > 1 && <span className="muted"> ({r.unit})</span>}</td>
                <td>{r.name}</td>
                <td className="r num">{fmt(r.buying)}</td>
                <td className="r num">{fmt(r.selling)}</td>
                <td className="r num">{source === 'canli' ? <Change value={r.change} /> : fmt(r.banknote_selling)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint">
        Fiyatlar her dakika yenilenir. Anlık veriler gayriresmi bir kaynaktan gelir ve gecikmeli olabilir.
        Resmi kur için TCMB sekmesini kullan. Yatırım kararı için kullanmadan önce teyit et.
      </p>
    </section>
  )
}
