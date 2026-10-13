import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getCompare, getFunds } from '../api/client'
import { MAX_COMPARE, getCompareList, setCompareList } from '../compareList'
import RiskBar from '../components/RiskBar'
import { num, pct, signClass, trDate } from '../format'
import { useDebounced } from '../hooks'
import { DEFAULT_PERIOD, PERIODS, findPeriod } from '../periods'
import { monthTicks } from '../chart'

const GRID = '#e5ebe8'
const INK_MUTED = '#5d6b65'
// Kategorik palet (renk körlüğü kontrolünden geçti). Renk fonun seçildiği yuvaya bağlı:
// bir fon çıkarılınca diğerlerinin rengi değişmez.
const SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100']

// [alan, başlık, daha iyi olan: 'max' | 'min' | null, biçim]
const ROWS = [
  ['period_return', null, 'max', 'pct'], // başlık seçili döneme göre yazılır
  ['ret_1m', '1 ay getiri', 'max', 'pct'],
  ['ret_3m', '3 ay getiri', 'max', 'pct'],
  ['ret_6m', '6 ay getiri', 'max', 'pct'],
  ['ret_ytd', 'Yılbaşından bu yana', 'max', 'pct'],
  ['ret_1y', '1 yıl getiri', 'max', 'pct'],
  ['volatility_1y', 'Volatilite (1 yıl)', 'min', 'vol'],
  ['sharpe_1y', 'Sharpe oranı (1 yıl)', 'max', 'num'],
  ['max_drawdown_1y', 'Maksimum düşüş (1 yıl)', 'max', 'pct'],
  ['risk_level', 'TEFAS risk değeri', 'min', 'risk'],
]

const valueOf = (f, key) => (key === 'period_return' || key === 'risk_level' ? f[key] : f.metrics?.[key]) ?? null

// Eski verili fonlar en iyi değer yarışına girmez (metrikleri başka bir döneme ait)
function bestValue(funds, key, better) {
  const vals = funds.filter((f) => !f.is_stale).map((f) => valueOf(f, key)).filter((v) => v != null)
  if (!better || vals.length < 2 || vals.every((v) => v === vals[0])) return null
  return better === 'max' ? Math.max(...vals) : Math.min(...vals)
}

function formatCell(v, fmt) {
  if (fmt === 'risk') return <RiskBar level={v} />
  if (v == null) return '–'
  if (fmt === 'vol') return `${num(v * 100, 1)}%`
  if (fmt === 'num') return num(v)
  return pct(v)
}

// Yuva dizisi: [kod | null] × 4. Seçilen fonlar dolu yuvalar, renk yuva sırasından gelir.
const toSlots = (codes) => Array.from({ length: MAX_COMPARE }, (_, i) => codes[i] ?? null)

function FundPicker({ selected, onAdd }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const q = useDebounced(query.trim())

  useEffect(() => {
    if (!q) { setResults([]); return }
    let ignore = false
    getFunds({ q, page_size: 8, sort: 'ret_1y' })
      .then((d) => { if (!ignore) setResults(d.sample ? [] : d.items) })
      .catch(() => { if (!ignore) setResults([]) })
    return () => { ignore = true }
  }, [q])

  const add = (code) => { onAdd(code); setQuery(''); setResults([]) }

  return (
    <div className="picker">
      <label className="search">
        <span className="sr-only">Karşılaştırmaya fon ekle</span>
        <input
          type="search" placeholder="Fon kodu veya adı yazıp ekle..." value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && results[0] && !selected.includes(results[0].code)) add(results[0].code) }}
        />
      </label>
      {results.length > 0 && (
        <ul className="picker-results">
          {results.map((f) => {
            const taken = selected.includes(f.code)
            return (
              <li key={f.code}>
                <button type="button" disabled={taken} onClick={() => add(f.code)}>
                  <strong className="num">{f.code}</strong>
                  <span className="picker-name">{f.name}</span>
                  {taken && <span className="muted small">seçili</span>}
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

function ChartTooltip({ active, payload, label, colorOf }) {
  if (!active || !payload?.length) return null
  const rows = payload.filter((p) => p.value != null).sort((a, b) => b.value - a.value)
  return (
    <div className="chart-tip">
      <span className="muted small">{trDate(label, { day: 'numeric', month: 'long', year: 'numeric' })}</span>
      {rows.map((p) => (
        <span key={p.dataKey} className="tip-row">
          <span className="swatch" style={{ background: colorOf(p.dataKey) }} />
          <strong>{p.dataKey}</strong>
          <span className="num">{num(p.value, 1)}</span>
          <span className={`num small ${signClass(p.value - 100)}`}>{pct(p.value / 100 - 1)}</span>
        </span>
      ))}
    </div>
  )
}

export default function Compare() {
  const [params, setParams] = useSearchParams()
  const [slots, setSlots] = useState(() => {
    const fromUrl = (params.get('fonlar') || '').split(',').map((c) => c.trim().toUpperCase()).filter(Boolean)
    return toSlots([...new Set(fromUrl.length ? fromUrl : getCompareList())].slice(0, MAX_COMPARE))
  })
  const period = findPeriod(params.get('donem'))
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const selected = useMemo(() => slots.filter(Boolean), [slots])
  const selectedKey = selected.join(',')
  const colorOf = (code) => SERIES[slots.indexOf(code)] ?? INK_MUTED

  // Seçim adres çubuğuna ve tarayıcı listesine yazılır (detay sayfasındaki buton da bu listeyi kullanır)
  useEffect(() => {
    setCompareList(selectedKey ? selectedKey.split(',') : [])
    setParams((p) => {
      const next = new URLSearchParams(p)
      if (selectedKey) next.set('fonlar', selectedKey)
      else next.delete('fonlar')
      return next
    }, { replace: true })
  }, [selectedKey, setParams])

  useEffect(() => {
    document.title = 'Karşılaştır · Fon Analiz'
  }, [])

  useEffect(() => {
    if (selected.length < 2) { setData(null); setError(null); return }
    let ignore = false
    // YBB: baz, geçen yılın 31 Aralık'ı ya da öncesindeki son fiyat (metriklerle aynı)
    const apiParams = period[3] ?? { start: `${new Date().getFullYear() - 1}-12-31` }
    setLoading(true)
    getCompare(selected, apiParams)
      .then((d) => { if (!ignore) { setData(d); setError(null) } })
      .catch((e) => { if (!ignore) setError(e.response?.data?.detail || 'Karşılaştırma yüklenemedi. Backend çalışıyor mu?') })
      .finally(() => { if (!ignore) setLoading(false) })
    return () => { ignore = true }
  }, [selected, period])

  const add = (code) => setSlots((s) => {
    if (s.includes(code)) return s
    const i = s.indexOf(null)
    return i === -1 ? s : s.map((c, j) => (j === i ? code : c))
  })
  const remove = (code) => setSlots((s) => s.map((c) => (c === code ? null : c)))
  const setPeriod = (k) => setParams((p) => {
    const next = new URLSearchParams(p)
    if (k === DEFAULT_PERIOD) next.delete('donem')
    else next.set('donem', k)
    return next
  }, { replace: true })

  // Veri gelene kadar eski veriyle çizilir; sadece hâlâ seçili fonlar gösterilir
  const funds = data ? data.funds.filter((f) => selected.includes(f.code)) : []
  const chartData = useMemo(() => (data ? data.points.map((p) => ({ date: p.date, ...p.values })) : []), [data])
  const months = period[3]?.months ?? new Date().getMonth() + 1
  const daily = months <= 1
  const ticks = useMemo(() => (daily ? undefined : monthTicks(chartData, months)), [chartData, months, daily])

  return (
    <section className="compare">
      <div>
        <h1>Karşılaştır</h1>
        <p className="hint">En fazla {MAX_COMPARE} fon seç. Grafik, dönem başında tüm fonları 100'den başlatır; böylece fiyat düzeyi farklı fonlar yan yana görülebilir.</p>
      </div>

      <div className="chips">
        {slots.map((code, i) => code && (
          <span key={code} className="chip">
            <span className="swatch" style={{ background: SERIES[i] }} />
            <Link to={`/fonlar/${code}`} className="num"><strong>{code}</strong></Link>
            {funds.find((f) => f.code === code) && <span className="chip-name">{funds.find((f) => f.code === code).name}</span>}
            <button type="button" className="chip-x" aria-label={`${code} fonunu çıkar`} onClick={() => remove(code)}>×</button>
          </span>
        ))}
        {selected.length < MAX_COMPARE && <FundPicker selected={selected} onAdd={add} />}
      </div>

      {error && <p className="error">{error}</p>}

      {selected.length < 2 ? (
        <div className="panel empty">
          <p><strong>Karşılaştırmak için en az 2 fon seç.</strong></p>
          <p className="muted">Yukarıdan arayabilir ya da bir fonun sayfasındaki "Karşılaştırmaya ekle" butonunu kullanabilirsin.</p>
        </div>
      ) : (
        <>
          <div className="panel">
            <div className="panel-head">
              <div className="legend">
                {funds.map((f) => (
                  <span key={f.code} className="legend-item">
                    <span className="legend-line" style={{ background: colorOf(f.code) }} />
                    <strong>{f.code}</strong>
                    <span className={`num ${signClass(f.period_return)}`}>{pct(f.period_return)}</span>
                    {f.is_stale && <span className="stale-badge small">eski veri</span>}
                  </span>
                ))}
              </div>
              <div className="seg" role="group" aria-label="Grafik dönemi">
                {PERIODS.map(([k, short, longName]) => (
                  <button key={k} type="button" title={longName} aria-pressed={k === period[0]} onClick={() => setPeriod(k)}>{short}</button>
                ))}
              </div>
            </div>
            <div className={`chart${loading ? ' is-loading' : ''}`}>
              {chartData.length > 1 ? (
                <ResponsiveContainer width="100%" height={340}>
                  <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid vertical={false} stroke={GRID} />
                    <XAxis
                      dataKey="date" ticks={ticks} minTickGap={daily ? 40 : 24} tickLine={false} axisLine={{ stroke: GRID }}
                      tick={{ fontSize: 12, fill: INK_MUTED }}
                      tickFormatter={(d) => trDate(d, daily ? { day: 'numeric', month: 'short' } : { month: 'short', year: '2-digit' })}
                    />
                    <YAxis
                      domain={['auto', 'auto']} width={48} orientation="right" tickLine={false} axisLine={false}
                      tick={{ fontSize: 12, fill: INK_MUTED }} tickFormatter={(v) => num(v, 0)}
                    />
                    <ReferenceLine y={100} stroke={INK_MUTED} strokeDasharray="3 3" />
                    <Tooltip content={<ChartTooltip colorOf={colorOf} />} cursor={{ stroke: INK_MUTED, strokeDasharray: '3 3' }} />
                    {funds.map((f) => (
                      <Line
                        key={f.code} type="linear" dataKey={f.code} stroke={colorOf(f.code)} strokeWidth={2}
                        dot={false} activeDot={{ r: 4, stroke: '#fff', strokeWidth: 2 }} isAnimationActive={false}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="muted chart-empty">{loading ? 'Yükleniyor...' : 'Grafik için veri yok.'}</p>
              )}
            </div>
            {data && <p className="muted small chart-note">Baz gün: {trDate(data.base_date)} = 100</p>}
          </div>

          {funds.length > 0 && (
            <>
              <h2>Metrikler</h2>
              <div className="table-wrap">
                <table className="compare-table">
                  <thead>
                    <tr>
                      <th scope="col"><span className="sr-only">Metrik</span></th>
                      {funds.map((f) => (
                        <th key={f.code} scope="col">
                          <span className="th-fund">
                            <span className="swatch" style={{ background: colorOf(f.code) }} />
                            <Link to={`/fonlar/${f.code}`} className="num">{f.code}</Link>
                          </span>
                          <span className="muted small th-name">{f.name}</span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {ROWS.map(([key, label, better, fmt]) => {
                      const best = bestValue(funds, key, better)
                      return (
                        <tr key={key}>
                          <th scope="row">{label ?? `${period[2]} getirisi (grafik)`}</th>
                          {funds.map((f) => {
                            const v = valueOf(f, key)
                            const isBest = best != null && v === best && !f.is_stale
                            const cls = fmt === 'pct' && key !== 'max_drawdown_1y' ? signClass(v) : key === 'max_drawdown_1y' && v < 0 ? 'down' : ''
                            return (
                              <td key={f.code} className={`r num ${cls}${isBest ? ' best' : ''}`}>
                                {formatCell(v, fmt)}
                                {isBest && <span className="sr-only"> (en iyi)</span>}
                              </td>
                            )
                          })}
                        </tr>
                      )
                    })}
                    <tr>
                      <th scope="row">Kategori</th>
                      {funds.map((f) => <td key={f.code} className="r small">{f.category ?? '–'}</td>)}
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className="hint small">
                Vurgulu hücre o satırdaki en iyi değerdir: getiri ve Sharpe'ta en yüksek, volatilite ve risk değerinde en düşük,
                maksimum düşüşte en küçük kayıp. "En iyi" sadece o metriğe göredir; tek başına bir fonu daha iyi yapmaz.
                {funds.some((f) => f.is_stale) && ' Verisi güncellenmeyen fonlar vurgulamaya dahil edilmez.'}
              </p>
            </>
          )}
        </>
      )}

      <p className="hint">Geçmiş performans gelecekteki sonuçların göstergesi değildir. Bu site yatırım tavsiyesi vermez.</p>
    </section>
  )
}
