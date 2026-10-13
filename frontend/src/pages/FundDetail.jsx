import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getFund, getFundPrices } from '../api/client'
import RiskBar from '../components/RiskBar'
import { num, pct, signClass, trDate } from '../format'
import { DEFAULT_PERIOD, PERIODS, findPeriod } from '../periods'
import { axisDigits, monthTicks } from '../chart'
import { MAX_COMPARE, getCompareList, setCompareList } from '../compareList'
import { isClosed } from '../fundStatus'

const LINE = '#0f7a5c'
const GRID = '#e5ebe8'
const INK_MUTED = '#5d6b65'

const FUND_TYPES = { YAT: 'Yatırım fonu', EMK: 'Emeklilik fonu', BYF: 'Borsa yatırım fonu' }

// [alan, başlık, açıklama]
const RETURNS = [
  ['ret_1m', '1 ay', 'Son 1 aydaki getiri'],
  ['ret_3m', '3 ay', 'Son 3 aydaki getiri'],
  ['ret_6m', '6 ay', 'Son 6 aydaki getiri'],
  ['ret_ytd', 'Yılbaşından bu yana', 'Geçen yılın son fiyatına göre getiri'],
  ['ret_1y', '1 yıl', 'Son 1 yıldaki getiri'],
  ['ret_3y', '3 yıl', 'Son 3 yıldaki toplam getiri (yıllık değil)'],
]

const fmtPrice = (v) => num(v, v < 100 ? 4 : 2)

function MetricCard({ label, value, cls = '', children }) {
  return (
    <div className="card metric">
      <span className="card-label">{label}</span>
      <span className={`card-value num ${cls}`}>{value}</span>
      {children && <span className="metric-desc">{children}</span>}
    </div>
  )
}

function ChartTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="chart-tip">
      <span className="muted small">{trDate(p.date, { day: 'numeric', month: 'long', year: 'numeric' })}</span>
      <strong className="num">{fmtPrice(p.price)} TL</strong>
    </div>
  )
}

function PriceChart({ points, months }) {
  const daily = months <= 1 // 1 ayda ay başı tiki tek kalır; günlük tikler kullanılır
  const tickFmt = (d) => trDate(d, daily ? { day: 'numeric', month: 'short' } : { month: 'short', year: '2-digit' })
  const values = points.map((p) => p.price)
  const digits = axisDigits(Math.max(...values) - Math.min(...values))
  return (
    <ResponsiveContainer width="100%" height={320}>
      <AreaChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={LINE} stopOpacity={0.14} />
            <stop offset="100%" stopColor={LINE} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis
          dataKey="date" tickFormatter={tickFmt} minTickGap={daily ? 48 : 24} ticks={daily ? undefined : monthTicks(points, months)}
          tick={{ fontSize: 12, fill: INK_MUTED }} tickLine={false} axisLine={{ stroke: GRID }}
        />
        <YAxis
          domain={['auto', 'auto']} width={64} orientation="right"
          tickFormatter={(v) => num(v, digits)}
          tick={{ fontSize: 12, fill: INK_MUTED }} tickLine={false} axisLine={false}
        />
        <Tooltip content={<ChartTooltip />} cursor={{ stroke: INK_MUTED, strokeDasharray: '3 3' }} />
        <Area
          type="linear" dataKey="price" stroke={LINE} strokeWidth={2} fill="url(#priceFill)"
          dot={false} activeDot={{ r: 4, stroke: '#fff', strokeWidth: 2 }} isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export default function FundDetail() {
  const { code } = useParams()
  const [params, setParams] = useSearchParams()
  const period = findPeriod(params.get('donem'))
  const periodKey = period[0]
  const [fund, setFund] = useState(null)
  const [fundError, setFundError] = useState(null)
  const [prices, setPrices] = useState(null)
  const [pricesError, setPricesError] = useState(null)
  const [loadingPrices, setLoadingPrices] = useState(true)
  const [compareList, setCompareState] = useState(getCompareList)
  const updateCompare = (codes) => { setCompareList(codes); setCompareState(codes) }

  useEffect(() => {
    let ignore = false
    setFund(null)
    setFundError(null)
    getFund(code)
      .then((d) => { if (!ignore) setFund(d) })
      .catch((e) => {
        if (ignore) return
        setFundError(e.response?.status === 404 ? `${code.toUpperCase()} kodlu fon bulunamadı.` : 'Fon bilgileri yüklenemedi. Backend çalışıyor mu?')
      })
    return () => { ignore = true }
  }, [code])

  useEffect(() => {
    if (fund?.code) document.title = `${fund.code} · Fon Analiz`
  }, [fund?.code])

  // YBB için yıl, fonun son fiyat tarihinden alınır (yılın ilk günlerinde veri gecikmeli olabilir)
  const ytdYear = fund ? new Date(fund.price_date || Date.now()).getFullYear() : null

  useEffect(() => {
    if (!fund) return
    let ignore = false
    // YBB'de baz geçen yılın son fiyatı (ret_ytd ile aynı); onu da almak için birkaç gün geriden istenir
    const apiParams = periodKey === 'YBB' ? { start: `${ytdYear - 1}-12-15` } : period[3]
    setLoadingPrices(true)
    getFundPrices(fund.code, apiParams)
      .then((d) => {
        if (ignore) return
        if (periodKey === 'YBB') {
          const base = d.findLastIndex((p) => p.date < `${ytdYear}-01-01`)
          d = d.slice(Math.max(base, 0))
        }
        setPrices(d)
        setPricesError(null)
      })
      .catch((e) => {
        if (ignore) return
        setPrices([])
        setPricesError(e.response?.status === 404 ? null : 'Fiyat geçmişi yüklenemedi.')
      })
      .finally(() => { if (!ignore) setLoadingPrices(false) })
    return () => { ignore = true }
  }, [fund, period, periodKey, ytdYear])

  const periodReturn = useMemo(() => {
    if (!prices || prices.length < 2) return null
    return prices[prices.length - 1].price / prices[0].price - 1
  }, [prices])

  if (fundError) {
    return (
      <section className="detail">
        <Link to="/fonlar" className="back">← Fonlar</Link>
        <p className="error">{fundError}</p>
      </section>
    )
  }
  if (!fund) return <section className="detail"><p className="muted">Yükleniyor...</p></section>

  const m = fund.metrics
  const inCompare = compareList.includes(fund.code)
  const compareFull = compareList.length >= MAX_COMPARE
  const compareUrl = `/karsilastir?fonlar=${compareList.join(',')}`
  const months = period[3]?.months ??new Date(fund.price_date || Date.now()).getMonth() + 1

  return (
    <section className="detail">
      <Link to="/fonlar" className="back">← Fonlar</Link>

      <div className="detail-head">
        <div className="detail-title">
          <span className="detail-code num">{fund.code}</span>
          <h1>{fund.name}</h1>
          <div className="detail-tags">
            {fund.category && <Link to={`/fonlar?kategori=${encodeURIComponent(fund.category)}`} className="tag">{fund.category}</Link>}
            {fund.fund_type && <span className="tag">{FUND_TYPES[fund.fund_type] || fund.fund_type}</span>}
            <span className="tag">Risk <RiskBar level={fund.risk_level} /></span>
          </div>
        </div>
        <div className="detail-price">
          <span className="card-label">Birim pay fiyatı</span>
          <span className="detail-price-value num">{fund.price != null ? `${fmtPrice(fund.price)} TL` : '–'}</span>
          {m && (
            <span className="small">
              <span className={signClass(m.daily_change)}>{pct(m.daily_change)}</span>
              <span className="muted"> günlük · {trDate(m.as_of)}</span>
            </span>
          )}
        </div>
      </div>

      <div className="detail-actions">
        {inCompare ? (
          <>
            <Link className="btn btn-primary" to={compareUrl}>Karşılaştır ({compareList.length}) →</Link>
            <button type="button" className="btn" onClick={() => updateCompare(compareList.filter((c) => c !== fund.code))}>
              Karşılaştırmadan çıkar
            </button>
          </>
        ) : (
          <>
            <button
              type="button" className="btn" disabled={compareFull}
              onClick={() => updateCompare([...compareList, fund.code])}
            >
              + Karşılaştırmaya ekle
            </button>
            {compareList.length > 0 && (
              <span className="muted small">
                {compareFull ? `Listede zaten ${MAX_COMPARE} fon var. ` : ''}
                <Link to={compareUrl}>Karşılaştırma listesi ({compareList.length})</Link>
              </span>
            )}
          </>
        )}
      </div>

      {isClosed(fund) && fund.status_note && (
        <p className="notice notice-closed" role="note">
          <strong>{fund.status_note}</strong>
          {fund.status_source && (
            <>
              {' '}Kaynak:{' '}
              {fund.status_url
                ? <a href={fund.status_url} target="_blank" rel="noopener noreferrer">{fund.status_source}</a>
                : fund.status_source}
            </>
          )}
        </p>
      )}
      {fund.is_stale && fund.price_date && (
        <p className="notice">
          Bu fonun verisi {trDate(fund.price_date)} tarihinden beri güncellenmiyor. Metrikler o tarihe aittir;
          fon kategori sıralamasına dahil edilmez.
        </p>
      )}
      {!fund.is_active && <p className="notice">Bu fon TEFAS'ta artık işlem görmüyor. Gösterilen veriler son işlem gününe aittir.</p>}

      <div className="panel">
        <div className="panel-head">
          <div>
            <span className="card-label">{period[2]} getirisi</span>
            <span className={`panel-value num ${signClass(periodReturn)}`}>{pct(periodReturn)}</span>
          </div>
          <div className="seg" role="group" aria-label="Grafik dönemi">
            {PERIODS.map(([k, short, long]) => (
              <button
                key={k} type="button" title={long} aria-pressed={k === periodKey}
                onClick={() => setParams(k === DEFAULT_PERIOD ? {} : { donem: k }, { replace: true })}
              >
                {short}
              </button>
            ))}
          </div>
        </div>
        {pricesError && <p className="error">{pricesError}</p>}
        <div className={`chart${loadingPrices ? ' is-loading' : ''}`}>
          {prices && prices.length > 1 && <PriceChart points={prices} months={months} />}
          {prices && prices.length <= 1 && !pricesError && <p className="muted chart-empty">Bu dönem için fiyat verisi yok.</p>}
          {!prices && <p className="muted chart-empty">Yükleniyor...</p>}
        </div>
        {prices && prices.length > 0 && (
          <details className="price-table">
            <summary>Fiyatları tablo olarak göster ({prices.length} gün)</summary>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Tarih</th><th className="r">Fiyat (TL)</th></tr></thead>
                <tbody>
                  {[...prices].reverse().map((p) => (
                    <tr key={p.date}><td className="num">{trDate(p.date)}</td><td className="r num">{fmtPrice(p.price)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}
      </div>

      {m ? (
        <>
          <h2>Getiriler</h2>
          <div className="cards">
            {RETURNS.map(([k, label, desc]) => (
              <MetricCard key={k} label={label} value={pct(m[k])} cls={signClass(m[k])}>{desc}</MetricCard>
            ))}
          </div>

          <h2>Risk ve verimlilik <span className="muted small">(son 1 yıl)</span></h2>
          <div className="cards">
            <MetricCard label="Volatilite" value={m.volatility_1y == null ? '–' : `${num(m.volatility_1y * 100, 1)}%`}>
              Fiyatın yıllık ne kadar dalgalandığı. Yükseldikçe fiyat daha sert iner çıkar, risk artar.
            </MetricCard>
            <MetricCard label="Sharpe oranı" value={num(m.sharpe_1y)}>
              Alınan her birim risk için risksiz getirinin (para piyasası fonlarının medyanı) ne kadar üstüne çıkıldığı.
              Yüksek olması daha iyidir; 0'ın altı, fonun risksiz getiriyi bile geçemediğini gösterir.
            </MetricCard>
            <MetricCard label="Maksimum düşüş" value={pct(m.max_drawdown_1y)} cls={m.max_drawdown_1y < 0 ? 'down' : ''}>
              Bir zirveden sonra görülen en büyük kayıp. Kötü senaryoda ne kadar değer kaybedilebildiğini gösterir.
            </MetricCard>
            <MetricCard
              label="Kategori sırası"
              value={fund.category_rank_1y ? `${fund.category_rank_1y} / ${fund.category_size}` : '–'}
            >
              {fund.category_rank_1y
                ? `1 yıllık getiriye göre ${fund.category} kategorisindeki ${fund.category_size} fon arasında.`
                : isClosed(fund)
                  ? 'İşleme kapatıldığı için sıralamaya alınmadı.'
                  : fund.is_stale
                  ? 'Verisi güncellenmediği için sıralamaya alınmadı.'
                  : 'Bu fon için kategori sıralaması hesaplanamadı.'}
            </MetricCard>
          </div>
        </>
      ) : (
        <p className="muted">Bu fon için henüz metrik hesaplanmadı.</p>
      )}

      <p className="hint">
        Veriler TEFAS'tan alınır. Geçmiş performans gelecekteki sonuçların göstergesi değildir. Bu site yatırım tavsiyesi vermez.
      </p>
    </section>
  )
}
