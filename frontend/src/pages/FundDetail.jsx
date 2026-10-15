import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getForecast, getFund, getFundPrices, getTechnical } from '../api/client'
import ForecastCard from '../components/ForecastCard'
import RiskBar from '../components/RiskBar'
import TechnicalSummary from '../components/TechnicalSummary'
import { num, pct, signClass, trDate } from '../format'
import { DEFAULT_PERIOD, PERIODS, findPeriod } from '../periods'
import { axisDigits, monthTicks } from '../chart'
import { MAX_COMPARE, getCompareList, setCompareList } from '../compareList'
import { isClosed } from '../fundStatus'
import { compactTl, count } from '../money'
import { C } from '../theme'

const LINE = C.price
const FORECAST = C.forecast // tahmin: fiyattan ayrı bir renk (kategorik paletin 1. rengi)
// Hareketli ortalamalar: fiyat ve tahminden ayrışan iki renk (doğrulayıcıdan geçti); 200 günlük ayrıca noktalı
const MA = {
  ma50: { color: C.ma50, label: '50 günlük ortalama', dash: undefined },
  ma200: { color: C.ma200, label: '200 günlük ortalama', dash: '2 3' },
}
const GRID = C.grid
const INK_MUTED = C.axis

// Fonun KAP sayfası bağlantısı TEFAS'ın fon profilinden gelir (kap_url; KAP'tan veri çekilmez,
// docs/rapor/02_veri_toplama.md 2.8). Bağlantı yoksa KAP'ın yatırım fonları listesine yönlendiriyoruz.
const KAP_FUNDS_URL = 'https://www.kap.org.tr/tr/YatirimFonlari/YF'
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

function ChartTooltip({ active, payload, shown }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  const isForecast = p.price == null && p.fc != null
  return (
    <div className="chart-tip">
      <span className="muted small">{trDate(p.date, { day: 'numeric', month: 'long', year: 'numeric' })}</span>
      {isForecast ? (
        <>
          <span className="small">Geçmiş eğilime dayalı tahmin</span>
          <strong className="num">{fmtPrice(p.fc)} TL</strong>
          <span className="muted small num">%80 aralık: {fmtPrice(p.band[0])} – {fmtPrice(p.band[1])}</span>
        </>
      ) : (
        <>
          <strong className="num">{fmtPrice(p.price)} TL</strong>
          {Object.entries(MA).filter(([k]) => shown?.[k] && p[k] != null).map(([k, s]) => (
            <span key={k} className="small num">
              <span className="legend-line" style={{ background: s.color }} /> {s.label}: {fmtPrice(p[k])}
            </span>
          ))}
        </>
      )}
    </div>
  )
}

// Son tarihten sonraki n iş günü (hafta sonu atlanır; resmi tatiller bilinmediği için dahil)
function nextBusinessDays(lastIso, n) {
  const out = []
  const d = new Date(`${lastIso}T00:00:00Z`)
  while (out.length < n) {
    d.setUTCDate(d.getUTCDate() + 1)
    const wd = d.getUTCDay()
    if (wd !== 0 && wd !== 6) out.push(d.toISOString().slice(0, 10))
  }
  return out
}

// Tahmin konisi: çizgi son fiyattan doğrusal ilerler; bant, zamanın kareköküyle genişleyip 21. günde
// konformal %10-90 aralığına ulaşır (ara günler yaklaşık).
function withForecast(points, f) {
  if (!f || !points.length) return points
  const last = points[points.length - 1]
  const base = last.price
  const h = f.horizon_days
  const future = nextBusinessDays(last.date, h).map((date, i) => {
    const k = (i + 1) / h
    const mid = f.pred_return * k
    return { date, fc: base * (1 + mid), band: [base * (1 + mid + (f.lo - f.pred_return) * Math.sqrt(k)), base * (1 + mid + (f.hi - f.pred_return) * Math.sqrt(k))] }
  })
  return [...points.slice(0, -1), { ...last, fc: base, band: [base, base] }, ...future]
}

// Ortalama serisini fiyat noktalarına tarihe göre ekler (tek günlük hatalı fiyat günlerinde ortalama boş kalır)
function withMa(points, series) {
  if (!series?.length) return points
  const byDate = new Map(series.map((s) => [s.date, s]))
  return points.map((p) => {
    const s = byDate.get(p.date)
    return s ? { ...p, ma50: s.ma50, ma200: s.ma200 } : p
  })
}

function PriceChart({ points, months, forecast, ma, shown }) {
  const daily = months <= 1 // 1 ayda ay başı tiki tek kalır; günlük tikler kullanılır
  const tickFmt = (d) => trDate(d, daily ? { day: 'numeric', month: 'short' } : { month: 'short', year: '2-digit' })
  const data = useMemo(() => withForecast(withMa(points, ma), forecast), [points, ma, forecast])
  const values = data.flatMap((p) => [p.price, ...(p.band ?? []), shown.ma50 && p.ma50, shown.ma200 && p.ma200]).filter((v) => v != null && v !== false)
  const digits = axisDigits(Math.max(...values) - Math.min(...values))
  return (
    <ResponsiveContainer width="100%" height={320}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={LINE} stopOpacity={0.14} />
            <stop offset="100%" stopColor={LINE} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis
          dataKey="date" tickFormatter={tickFmt} minTickGap={daily ? 48 : 24} ticks={daily ? undefined : monthTicks(data, months)}
          tick={{ fontSize: 12, fill: INK_MUTED }} tickLine={false} axisLine={{ stroke: GRID }}
        />
        <YAxis
          domain={['auto', 'auto']} width={64} orientation="right"
          tickFormatter={(v) => num(v, digits)}
          tick={{ fontSize: 12, fill: INK_MUTED }} tickLine={false} axisLine={false}
        />
        <Tooltip content={<ChartTooltip shown={shown} />} cursor={{ stroke: INK_MUTED, strokeDasharray: '3 3' }} />
        <Area
          type="linear" dataKey="price" stroke={LINE} strokeWidth={2} fill="url(#priceFill)"
          dot={false} activeDot={{ r: 4, stroke: C.surface, strokeWidth: 2 }} isAnimationActive={false} connectNulls={false}
        />
        {/* Recharts 2, Fragment içindeki serileri görmez: her seri ayrı koşulla */}
        {forecast && <Area type="linear" dataKey="band" stroke="none" fill={FORECAST} fillOpacity={0.16} isAnimationActive={false} activeDot={false} />}
        {forecast && <Line type="linear" dataKey="fc" stroke={FORECAST} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />}
        {shown.ma50 && <Line type="linear" dataKey="ma50" stroke={MA.ma50.color} strokeWidth={1.5} dot={false} activeDot={false} isAnimationActive={false} connectNulls />}
        {shown.ma200 && <Line type="linear" dataKey="ma200" stroke={MA.ma200.color} strokeWidth={2} strokeDasharray={MA.ma200.dash} dot={false} activeDot={false} isAnimationActive={false} connectNulls />}
      </ComposedChart>
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
  const [forecast, setForecast] = useState(null)
  const [forecastMissing, setForecastMissing] = useState(null)
  const [tech, setTech] = useState(null)
  const [shownMa, setShownMa] = useState({ ma50: false, ma200: false })
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
    if (!fund?.code) return
    let ignore = false
    setForecast(null)
    setForecastMissing(null)
    getForecast(fund.code)
      .then((d) => { if (!ignore) setForecast(d) })
      .catch((e) => {
        if (ignore) return
        setForecastMissing(e.response?.status === 404 ? (e.response.data?.detail || 'Bu fon için tahmin yok.') : 'Tahmin yüklenemedi.')
      })
    return () => { ignore = true }
  }, [fund?.code])

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
    // Ortalamalar aynı dönem için; başarısız olursa grafik ortalamasız çizilir
    getTechnical(fund.code, apiParams)
      .then((d) => { if (!ignore) setTech(d) })
      .catch(() => { if (!ignore) setTech(null) })
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
        <Link className="btn" to={`/sanal-portfoy?fon=${fund.code}`}>Sanal portföyde dene</Link>
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
          {prices && prices.length > 1 && <PriceChart points={prices} months={months} forecast={forecast} ma={tech?.series} shown={shownMa} />}
          {prices && prices.length <= 1 && !pricesError && <p className="muted chart-empty">Bu dönem için fiyat verisi yok.</p>}
          {!prices && <p className="muted chart-empty">Yükleniyor...</p>}
        </div>
        {forecast && prices && prices.length > 1 && (
          <p className="muted small chart-note">
            <span className="legend-line legend-dashed" style={{ borderColor: FORECAST }} /> Kesikli çizgi: geçmiş eğilime dayalı
            1 aylık tahmin; açık alan: %80 aralık (ara günlerdeki genişlik yaklaşık).
          </p>
        )}
        {tech && prices && prices.length > 1 && (
          <div className="ma-toggles" role="group" aria-label="Hareketli ortalamalar">
            {Object.entries(MA).map(([k, s]) => (
              <label key={k} className="ma-toggle small">
                <input type="checkbox" checked={shownMa[k]} onChange={(e) => setShownMa({ ...shownMa, [k]: e.target.checked })} />
                <span className="legend-line" style={s.dash ? { borderTop: `3px dotted ${s.color}`, height: 0 } : { background: s.color }} />
                {s.label}
              </label>
            ))}
            {shownMa.ma200 && tech.series.every((p) => p.ma200 == null) && (
              <span className="muted small">200 günlük ortalama için yeterli geçmiş yok.</span>
            )}
          </div>
        )}
        {tech && <TechnicalSummary summary={tech.summary} />}
        {tech && (
          <p className="muted small chart-note">
            Teknik göstergeler geçmiş fiyat hareketini özetler. Testlerimizde momentum ve 52 haftalık zirveye uzaklık gibi
            göstergeler gelecekteki getiriyi tahmin etmede basit ortalamadan daha iyi sonuç vermedi; hareketli ortalamalar
            ayrıca test edilmedi.
          </p>
        )}
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

      <ForecastCard forecast={forecast} unavailable={forecastMissing} />

      {(fund.total_value != null || fund.investor_count != null) && (
        <>
          <h2>Fon bilgileri {fund.info_date && <span className="muted small">(TEFAS, {trDate(fund.info_date)})</span>}</h2>
          <div className="cards">
            <MetricCard label="Fon büyüklüğü" value={compactTl(fund.total_value)}>Fonun toplam portföy değeri.</MetricCard>
            <MetricCard label="Yatırımcı sayısı" value={count(fund.investor_count)}>Fonda payı bulunan yatırımcı sayısı.</MetricCard>
          </div>
        </>
      )}

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
              {m.sharpe_note ?? (
                <>
                  Alınan her birim risk için risksiz getirinin (para piyasası fonlarının medyanı) ne kadar üstüne çıkıldığı.
                  Yüksek olması daha iyidir; 0'ın altı, fonun risksiz getiriyi bile geçemediğini gösterir.
                </>
              )}
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

      <p className="small kap-link">
        {fund.kap_url ? (
          <a href={fund.kap_url} target="_blank" rel="noopener noreferrer">Bu fonun KAP sayfasını görüntüle ↗</a>
        ) : (
          <>
            <a href={KAP_FUNDS_URL} target="_blank" rel="noopener noreferrer">Bu fonun KAP bildirimlerini görüntüle ↗</a>
            <span className="muted"> KAP'ın yatırım fonları listesi açılır; arama kutusuna {fund.code} yazarak fonu bulabilirsiniz.</span>
          </>
        )}
      </p>

      <p className="hint">
        Veriler TEFAS'tan alınır. Geçmiş performans gelecekteki sonuçların göstergesi değildir. Bu site yatırım tavsiyesi vermez.
      </p>
    </section>
  )
}
