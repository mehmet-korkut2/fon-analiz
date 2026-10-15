import { Fragment, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { cancelSanalOrder, getFund, getSanal, getWhatIf, postSanalOrder, resetSanal } from '../api/client'
import FundPicker from '../components/FundPicker'
import RiskBar from '../components/RiskBar'
import { axisDigits, monthTicks } from '../chart'
import { num, pct, signClass, trDate } from '../format'
import { isClosed, STATUS_LABELS } from '../fundStatus'
import { compactTl, parseAmount, signedTl, tl2 } from '../money'
import { C, SERIES } from '../theme'

const MAX_WHATIF = 4
const SIDE = { alis: 'Alış', satis: 'Satış' }
const STATUS = { bekliyor: 'Bekliyor', gerceklesti: 'Gerçekleşti', iptal: 'İptal' }
const errText = (e, fallback) => e.response?.data?.detail || fallback
const fmtPrice = (v) => num(v, v < 100 ? 4 : 2)
const longDate = (d) => trDate(d, { day: 'numeric', month: 'long', year: 'numeric' })

function SimWarning() {
  return (
    <p className="disclaimer sim-warning" role="note">
      <strong>Bu hayali parayla yapılan bir simülasyondur.</strong> Gerçek alım satım yapılmaz. Geçmiş performans
      gelecekteki sonuçların göstergesi değildir. Yatırım tavsiyesi değildir.
    </p>
  )
}

function Stat({ label, value, cls = '', children }) {
  return (
    <div className="card metric">
      <span className="card-label">{label}</span>
      <span className={`card-value num ${cls}`}>{value}</span>
      {children && <span className="metric-desc">{children}</span>}
    </div>
  )
}

// Para değeri grafiği: seriler [{ key, label, color, dashed }]; veri [{ date, key: değer }]
function ValueChart({ data, series, months }) {
  const values = data.flatMap((p) => series.map((s) => p[s.key])).filter((v) => v != null)
  if (data.length < 2 || !values.length) return <p className="muted chart-empty chart-empty-sm">Grafik, portföyün ilk işlem gününden sonra oluşur (en az iki gün gerekiyor).</p>
  const max = Math.max(...values)
  const inThousands = max >= 10_000
  const digits = axisDigits((max - Math.min(...values)) / (inThousands ? 1000 : 1))
  const daily = months <= 1
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid vertical={false} stroke={C.grid} />
        <XAxis
          dataKey="date" tickLine={false} axisLine={{ stroke: C.grid }} tick={{ fontSize: 12, fill: C.axis }}
          ticks={daily ? undefined : monthTicks(data, months)} minTickGap={daily ? 48 : 24}
          tickFormatter={(d) => trDate(d, daily ? { day: 'numeric', month: 'short' } : { month: 'short', year: '2-digit' })}
        />
        <YAxis
          domain={['auto', 'auto']} width={72} orientation="right" tickLine={false} axisLine={false}
          tick={{ fontSize: 12, fill: C.axis }} tickFormatter={(v) => (inThousands ? `${num(v / 1000, digits)} bin` : num(v, digits))}
        />
        <Tooltip
          cursor={{ stroke: C.axis, strokeDasharray: '3 3' }}
          content={({ active, payload, label }) => active && payload?.length ? (
            <div className="chart-tip">
              <span className="muted small">{longDate(label)}</span>
              {series.filter((s) => payload.some((p) => p.dataKey === s.key && p.value != null)).map((s) => (
                <span key={s.key} className="tip-row tip-row-2">
                  <span className="swatch" style={{ background: s.color }} />
                  <span>{s.label}</span>
                  <span className="num">{tl2(payload.find((p) => p.dataKey === s.key).value)}</span>
                </span>
              ))}
            </div>
          ) : null}
        />
        {series.map((s) => (
          <Line
            key={s.key} type="linear" dataKey={s.key} stroke={s.color} strokeWidth={2} dot={false} connectNulls
            strokeDasharray={s.dashed ? '5 4' : undefined} isAnimationActive={false}
            activeDot={{ r: 4, stroke: C.surface, strokeWidth: 2 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}

function ChartLegend({ series, data }) {
  // Her serinin son dolu değeri (fonların son fiyat günü farklı olabilir)
  const last = Object.fromEntries(series.map((s) => [s.key, data.findLast((p) => p[s.key] != null)?.[s.key]]))
  return (
    <div className="legend">
      {series.map((s) => (
        <span key={s.key} className="legend-item">
          <span className={`legend-line${s.dashed ? ' legend-dashed' : ''}`} style={s.dashed ? { borderColor: s.color } : { background: s.color }} />
          {s.label}{last[s.key] != null && <strong className="num">{tl2(last[s.key])}</strong>}
        </span>
      ))}
    </div>
  )
}

const monthsBetween = (a, b) => Math.max(1, Math.round((new Date(b) - new Date(a)) / (30.44 * 864e5)))

// --- Sanal portföy (ileriye dönük) ---------------------------------------------------------

function valorText(v, known) {
  if (!known) return 'TEFAS\'ta valör bilgisi yok: ertesi iş günü fiyatı'
  return v === 0 ? 'aynı gün (T+0) fiyatı' : `${v} iş günü sonraki (T+${v}) fiyat`
}

function BuyForm({ initialCode, available, onDone }) {
  const [code, setCode] = useState(initialCode || '')
  const [fund, setFund] = useState(null)
  const [amount, setAmount] = useState('10.000')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)

  useEffect(() => {
    if (!code) { setFund(null); return }
    let ignore = false
    getFund(code).then((f) => { if (!ignore) setFund(f) }).catch(() => { if (!ignore) setFund(null) })
    return () => { ignore = true }
  }, [code])

  const blocked = fund && (isClosed(fund) || fund.is_stale || !fund.is_active)
  const value = parseAmount(amount)

  const submit = (e) => {
    e.preventDefault()
    if (!fund || !value) return
    setBusy(true)
    setMsg(null)
    postSanalOrder({ code: fund.code, side: 'alis', amount: value })
      .then((d) => {
        const o = d.pending.find((p) => p.code === fund.code && p.side === 'alis')
        setMsg({ ok: true, text: `${fund.code} için ${tl2(value)} tutarında alış emri verildi.${o ? ` ${longDate(o.target_date)} fiyatından gerçekleşecek.` : ''}` })
        onDone(d)
      })
      .catch((err) => setMsg({ ok: false, text: errText(err, 'Emir verilemedi.') }))
      .finally(() => setBusy(false))
  }

  return (
    <form className="panel sim-form" onSubmit={submit} aria-labelledby="buy-title">
      <h2 id="buy-title">Fon al</h2>
      <div className="sim-form-row">
        <div className="sim-field">
          <label htmlFor="buy-fund" className="card-label">Fon</label>
          {fund ? (
            <div className="chip">
              <strong className="num">{fund.code}</strong>
              <span className="chip-name">{fund.name}</span>
              <button type="button" className="chip-x" aria-label="Fonu değiştir" onClick={() => { setCode(''); setMsg(null) }}>×</button>
            </div>
          ) : (
            <FundPicker id="buy-fund" label="Alınacak fonu ara" placeholder="Fon kodu veya adı..." onAdd={(c) => { setCode(c); setMsg(null) }} />
          )}
        </div>
        <div className="sim-field">
          <label htmlFor="buy-amount" className="card-label">Tutar</label>
          <span className="amount-field">
            <input id="buy-amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} aria-describedby="buy-cash" />
            <span className="muted">TL</span>
          </span>
          <span id="buy-cash" className="muted small">Kullanılabilir nakit: <span className="num">{tl2(available)}</span></span>
        </div>
        <button type="submit" className="btn btn-primary" disabled={!fund || blocked || !value || busy}>{busy ? 'Gönderiliyor…' : 'Alış emri ver'}</button>
      </div>
      {fund && !blocked && (
        <p className="small muted sim-valor">
          Son fiyat <span className="num">{fmtPrice(fund.price)} TL</span> ({trDate(fund.price_date)}). Alış: {valorText(fund.buy_valor, fund.buy_valor != null)}
          {fund.cutoff_time && <>; {fund.cutoff_time}'ten sonra verilen emir ertesi iş günü sayılır</>}. Pay adedi tam sayıdır, artan tutar nakitte kalır.
        </p>
      )}
      {blocked && (
        <p className="error" role="alert">
          {fund.code} alınamaz: {isClosed(fund) ? (fund.status_note || 'SPK kararıyla işleme kapatıldı.') : fund.is_stale ? `verisi ${trDate(fund.price_date)} tarihinden beri güncellenmiyor.` : 'TEFAS\'ta işlem görmüyor.'}
        </p>
      )}
      {msg && <p className={msg.ok ? 'notice notice-ok' : 'error'} role="status">{msg.text}</p>}
    </form>
  )
}

function SellRow({ p, onDone, onClose }) {
  const [units, setUnits] = useState(String(p.sellable))
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const n = Number(units.replace(/\./g, ''))
  const valid = Number.isInteger(n) && n > 0 && n <= p.sellable
  const submit = (e) => {
    e.preventDefault()
    setBusy(true)
    postSanalOrder({ code: p.code, side: 'satis', units: n })
      .then((d) => { onDone(d); onClose() })
      .catch((e2) => setErr(errText(e2, 'Satış emri verilemedi.')))
      .finally(() => setBusy(false))
  }
  return (
    <tr className="sell-row">
      <td colSpan={9}>
        <form className="sell-form" onSubmit={submit}>
          <label htmlFor={`sell-${p.code}`} className="small">Satılacak pay ({p.code}, en çok <span className="num">{p.sellable.toLocaleString('tr-TR')}</span>)</label>
          <input id={`sell-${p.code}`} inputMode="numeric" value={units} onChange={(e) => setUnits(e.target.value)} />
          <button type="button" className="btn" onClick={() => setUnits(String(p.sellable))}>Tamamı</button>
          <button type="submit" className="btn btn-primary" disabled={!valid || busy}>Satış emri ver</button>
          <button type="button" className="btn" onClick={onClose}>Vazgeç</button>
          <span className="muted small">Satış: {valorText(p.sell_valor, p.sell_valor != null)}{valid && p.price ? `; bugünkü fiyatla yaklaşık ${tl2(n * p.price)}` : ''}.</span>
          {err && <span className="error small" role="alert">{err}</span>}
        </form>
      </td>
    </tr>
  )
}

function Positions({ data, onDone }) {
  const [selling, setSelling] = useState(null)
  const rows = data.positions.filter((p) => p.units > 0)
  if (!rows.length) return <p className="muted">Henüz fon yok. Yukarıdan bir fon seçip alış emri verebilirsin; emir valör gününde gerçekleşir.</p>
  return (
    <div className="table-wrap">
      <table className="sim-table stack-table">
        <thead>
          <tr>
            <th scope="col">Fon</th><th scope="col" className="r">Pay</th><th scope="col" className="r">Ort. maliyet</th>
            <th scope="col" className="r">Maliyet</th><th scope="col" className="r">Fiyat</th><th scope="col" className="r">Değer</th>
            <th scope="col" className="r">Kâr / zarar</th><th scope="col" className="r">%</th><th scope="col"><span className="sr-only">İşlem</span></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <Fragment key={p.code}>
              <tr>
                <td className="fund-name">
                  <Link to={`/fonlar/${p.code}`}><strong className="num">{p.code}</strong> {p.name}</Link>
                  <span className="rank-meta"><span className="muted small">{p.category}</span><RiskBar level={p.risk_level} />
                    {p.status !== 'aktif' && <span className="closed-badge small">{STATUS_LABELS[p.status] ?? p.status}</span>}</span>
                </td>
                <td data-label="Pay" className="r num">{p.units.toLocaleString('tr-TR')}</td>
                <td data-label="Ort. maliyet" className="r num">{fmtPrice(p.avg_cost)}</td>
                <td data-label="Maliyet" className="r num nowrap">{tl2(p.cost)}</td>
                <td data-label="Fiyat" className="r num" title={p.price_date ? trDate(p.price_date) : undefined}>{fmtPrice(p.price)}</td>
                <td data-label="Değer" className="r num nowrap">{tl2(p.value)}</td>
                <td data-label="Kâr / zarar" className={`r num nowrap ${signClass(p.pnl)}`}>{signedTl(p.pnl)}</td>
                <td data-label="Kâr / zarar %" className={`r num ${signClass(p.pnl_pct)}`}>{pct(p.pnl_pct)}</td>
                <td className="r td-action">
                  <button type="button" className="btn btn-sm" disabled={p.sellable <= 0} onClick={() => setSelling(selling === p.code ? null : p.code)}
                    aria-expanded={selling === p.code} title={p.sellable <= 0 ? 'Bütün paylar bekleyen satış emrinde' : undefined}>
                    Sat
                  </button>
                </td>
              </tr>
              {selling === p.code && <SellRow p={p} onDone={onDone} onClose={() => setSelling(null)} />}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Pending({ data, onDone }) {
  const [err, setErr] = useState(null)
  if (!data.pending.length) return null
  const cancel = (id) => cancelSanalOrder(id).then(onDone).catch((e) => setErr(errText(e, 'İptal edilemedi.')))
  return (
    <section aria-labelledby="pending-title">
      <h2 id="pending-title">Bekleyen emirler <span className="muted small">({data.pending.length})</span></h2>
      <p className="muted small">Emirler valör günündeki fiyattan, o günün fiyatı geldikten sonraki gece güncellemesinde gerçekleşir. Alışlarda tutar şimdiden ayrıldı.</p>
      {err && <p className="error">{err}</p>}
      <div className="table-wrap">
        <table className="sim-table stack-table">
          <thead>
            <tr><th scope="col">Verildi</th><th scope="col">Fon</th><th scope="col">İşlem</th><th scope="col" className="r">Tutar / pay</th>
              <th scope="col">Gerçekleşecek</th><th scope="col"><span className="sr-only">İptal</span></th></tr>
          </thead>
          <tbody>
            {data.pending.map((o) => (
              <tr key={o.id}>
                <td data-label="Verildi" className="num nowrap">{trDate(o.created_at)}</td>
                <td data-label="Fon"><Link to={`/fonlar/${o.code}`}><strong className="num">{o.code}</strong></Link></td>
                <td data-label="İşlem"><span className={`side-badge side-${o.side}`}>{SIDE[o.side]}</span></td>
                <td data-label="Tutar / pay" className="r num nowrap">{o.side === 'alis' ? tl2(o.amount) : `${o.units.toLocaleString('tr-TR')} pay`}</td>
                <td data-label="Gerçekleşecek" className="small">{longDate(o.target_date)} fiyatı <span className="muted">({o.valor_known ? `T+${o.valor}` : 'valör yok, ertesi iş günü'})</span></td>
                <td className="r td-action"><button type="button" className="btn btn-sm" onClick={() => cancel(o.id)}>İptal</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function History({ data }) {
  if (!data.history.length) return null
  return (
    <details className="price-table">
      <summary>İşlem geçmişi ({data.history.length})</summary>
      <div className="table-wrap">
        <table className="sim-table">
          <thead>
            <tr><th scope="col">Tarih</th><th scope="col">Fon</th><th scope="col">İşlem</th><th scope="col" className="r">Pay</th>
              <th scope="col" className="r">Fiyat</th><th scope="col" className="r">Tutar</th><th scope="col">Durum</th></tr>
          </thead>
          <tbody>
            {data.history.map((o) => (
              <tr key={o.id}>
                <td className="num nowrap">{trDate(o.exec_date || o.created_at)}</td>
                <td><strong className="num">{o.code}</strong></td>
                <td><span className={`side-badge side-${o.side}`}>{SIDE[o.side]}</span></td>
                <td className="r num">{o.exec_units?.toLocaleString('tr-TR') ?? '–'}</td>
                <td className="r num">{o.exec_price != null ? fmtPrice(o.exec_price) : '–'}</td>
                <td className="r num nowrap">{o.exec_amount != null ? tl2(o.exec_amount) : o.amount != null ? tl2(o.amount) : '–'}</td>
                <td className="small">{STATUS[o.status]}{o.note && <span className="muted"> · {o.note}</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

function ResetBox({ data, onDone }) {
  const [balance, setBalance] = useState(data.initial_balance.toLocaleString('tr-TR'))
  const [confirm, setConfirm] = useState(false)
  const [err, setErr] = useState(null)
  const value = parseAmount(balance)
  const run = () => resetSanal(value).then((d) => { setConfirm(false); setErr(null); onDone(d) }).catch((e) => setErr(errText(e, 'Sıfırlanamadı.')))
  return (
    <div className="panel sim-reset">
      <h2>Ayarlar</h2>
      <div className="sim-form-row">
        <div className="sim-field">
          <label htmlFor="sim-balance" className="card-label">Başlangıç bakiyesi</label>
          <span className="amount-field">
            <input id="sim-balance" inputMode="decimal" value={balance} onChange={(e) => { setBalance(e.target.value); setConfirm(false) }} />
            <span className="muted">TL</span>
          </span>
        </div>
        {!confirm ? (
          <button type="button" className="btn" disabled={!value} onClick={() => setConfirm(true)}>Portföyü sıfırla</button>
        ) : (
          <span className="sim-confirm" role="alert">
            Bütün emirler ve geçmiş silinecek, bakiye {tl2(value)} olacak.
            <button type="button" className="btn btn-danger" onClick={run}>Evet, sıfırla</button>
            <button type="button" className="btn" onClick={() => setConfirm(false)}>Vazgeç</button>
          </span>
        )}
      </div>
      <p className="muted small">Portföy {longDate(data.start_date)} tarihinde başladı. Sıfırlayınca başlangıç günü bugün olur.</p>
      {err && <p className="error">{err}</p>}
    </div>
  )
}

function Portfolio({ initialCode }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    getSanal().then(setData).catch(() => setError('Sanal portföy yüklenemedi. Backend çalışıyor mu?'))
  }, [])
  const chartSeries = [
    { key: 'total', label: 'Portföy', color: SERIES[0] },
    { key: 'benchmark', label: 'Para piyasası medyanı', color: C.neutral, dashed: true },
  ]
  if (error) return <p className="error">{error}</p>
  if (!data) return <p className="muted">Yükleniyor...</p>
  const diff = data.benchmark != null ? data.total - data.benchmark : null
  return (
    <div className="sim">
      <div className="cards">
        <Stat label="Toplam değer" value={tl2(data.total)}>
          <span className={signClass(data.pnl)}>{signedTl(data.pnl)} ({pct(data.pnl_pct)})</span> · başlangıç {tl2(data.initial_balance)}
        </Stat>
        <Stat label="Nakit" value={tl2(data.cash)}>
          Kullanılabilir {tl2(data.available)}{data.reserved > 0 && <>; bekleyen alışlar için ayrılan {tl2(data.reserved)}</>}
        </Stat>
        <Stat label="Fonlardaki değer" value={tl2(data.holdings)}>
          {data.realized !== 0 ? <>Satışlardan gerçekleşen: <span className={signClass(data.realized)}>{signedTl(data.realized)}</span></> : 'Henüz satış yok.'}
        </Stat>
        <Stat label="Kıyas: para piyasası medyanı" value={data.benchmark != null ? tl2(data.benchmark) : '–'}>
          Aynı para başlangıçta para piyasası fonlarına (medyan) yatırılsaydı{diff != null && <>; fark <span className={signClass(diff)}>{signedTl(diff)}</span></>}.
        </Stat>
      </div>

      <BuyForm initialCode={initialCode} available={data.available} onDone={setData} />
      <Pending data={data} onDone={setData} />

      <section aria-labelledby="pos-title">
        <h2 id="pos-title">Pozisyonlar</h2>
        <Positions data={data} onDone={setData} />
      </section>

      <section className="panel" aria-labelledby="value-title">
        <div className="panel-head">
          <h2 id="value-title">Portföy değeri</h2>
          <ChartLegend series={chartSeries} data={data.values} />
        </div>
        <div className="chart"><ValueChart data={data.values} series={chartSeries} months={monthsBetween(data.start_date, data.as_of || data.start_date)} /></div>
        <p className="muted small chart-note">
          {data.as_of ? `Son fiyat günü ${longDate(data.as_of)}. ` : ''}Değer her gece güncellemeden sonra yeniden hesaplanır.
          Kıyas çizgisi, başlangıç bakiyesinin portföyün başladığı gün para piyasası fonlarının medyanına yatırıldığı varsayımıdır.
        </p>
      </section>

      <History data={data} />
      <ResetBox key={data.start_date + data.initial_balance} data={data} onDone={setData} />
    </div>
  )
}

// --- "Ya o zaman alsaydım?" (geriye dönük) -------------------------------------------------------

const isoDaysAgo = (n) => new Date(Date.now() - n * 864e5).toISOString().slice(0, 10)

function WhatIf({ initialCodes }) {
  const [codes, setCodes] = useState(initialCodes)
  const [date, setDate] = useState(isoDaysAgo(365))
  const [amount, setAmount] = useState('10.000')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const value = parseAmount(amount)
  const colorOf = (c) => SERIES[codes.indexOf(c)] ?? C.axis

  const run = (e) => {
    e?.preventDefault()
    if (!codes.length || !value || !date) return
    setBusy(true)
    getWhatIf(codes, date, value)
      .then((d) => { setData(d); setError(null) })
      .catch((err) => { setData(null); setError(errText(err, 'Hesaplanamadı.')) })
      .finally(() => setBusy(false))
  }

  // Renk, fonun seçim listesindeki yuvasına bağlı (Karşılaştır sayfasıyla aynı kural)
  // Fon bağlantıyla geldiyse (fon detayı, ?fon=A,B) son 1 yıl için hemen hesapla
  useEffect(() => { if (initialCodes.length) run() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const series = [
    ...(data?.funds ?? []).filter((f) => !f.error).map((f) => ({ key: f.code, label: f.code, color: colorOf(f.code) })),
    ...(data ? [{ key: 'mm', label: 'Para piyasası medyanı', color: C.neutral, dashed: true }] : []),
  ]

  return (
    <div className="sim">
      <form className="panel sim-form" onSubmit={run} aria-labelledby="whatif-title">
        <h2 id="whatif-title">Ya o zaman alsaydım?</h2>
        <p className="muted small">Seçtiğin gün (o gün işlem yoksa sonraki ilk işlem günü) fiyatından alınıp bugüne kadar tutulsaydı. En fazla {MAX_WHATIF} fon.</p>
        <div className="chips">
          {codes.map((c) => (
            <span key={c} className="chip">
              <span className="swatch" style={{ background: colorOf(c) }} />
              <strong className="num">{c}</strong>
              <button type="button" className="chip-x" aria-label={`${c} fonunu çıkar`} onClick={() => setCodes(codes.filter((x) => x !== c))}>×</button>
            </span>
          ))}
          {codes.length < MAX_WHATIF && (
            <FundPicker selected={codes} onAdd={(c) => setCodes([...codes, c])} label="Hesaplamaya fon ekle"
              params={{ include_stale: true, include_closed: true }} />
          )}
        </div>
        <div className="sim-form-row">
          <div className="sim-field">
            <label htmlFor="wi-date" className="card-label">Alış tarihi</label>
            <input id="wi-date" type="date" className="date-input" value={date} max={isoDaysAgo(1)} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div className="sim-field">
            <label htmlFor="wi-amount" className="card-label">Tutar</label>
            <span className="amount-field">
              <input id="wi-amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
              <span className="muted">TL</span>
            </span>
          </div>
          <button type="submit" className="btn btn-primary" disabled={!codes.length || !value || !date || busy}>{busy ? 'Hesaplanıyor…' : 'Hesapla'}</button>
        </div>
        {error && <p className="error" role="alert">{error}</p>}
      </form>

      {data && (
        <>
          <div className="table-wrap">
            <table className="sim-table whatif-table stack-table">
              <thead>
                <tr>
                  <th scope="col">Fon</th><th scope="col">Alış</th><th scope="col" className="r">Bugünkü değer</th>
                  <th scope="col" className="r">Kâr / zarar</th><th scope="col" className="r">%</th><th scope="col" className="r">Yıllık</th>
                  <th scope="col" className="r">Para piyasası medyanı</th>
                </tr>
              </thead>
              <tbody>
                {data.funds.map((f) => f.error ? (
                  <tr key={f.code}><td><strong className="num">{f.code}</strong></td><td colSpan={6} className="muted">{f.error}</td></tr>
                ) : (
                  <tr key={f.code}>
                    <td className="fund-name">
                      <span><span className="swatch" style={{ background: colorOf(f.code) }} /> <Link to={`/fonlar/${f.code}`}><strong className="num">{f.code}</strong></Link> <span className="small">{f.name}</span></span>
                      {isClosed(f) && <span className="closed-badge small" title={f.status_note ?? undefined}>{STATUS_LABELS[f.status] ?? f.status}</span>}
                      {f.late_start && <span className="stale-badge small">Fon bu tarihte yoktu; ilk fiyat {trDate(f.buy_date)}</span>}
                    </td>
                    <td data-label="Alış" className="small nowrap">{trDate(f.buy_date)}<br /><span className="muted num">{fmtPrice(f.buy_price)} TL</span></td>
                    <td data-label="Bugünkü değer" className="r num nowrap">{tl2(f.value)}<br /><span className="muted small">{trDate(f.last_date)}</span></td>
                    <td data-label="Kâr / zarar" className={`r num nowrap ${signClass(f.pnl)}`}>{signedTl(f.pnl)}</td>
                    <td data-label="Kâr / zarar %" className={`r num ${signClass(f.pnl_pct)}`}>{pct(f.pnl_pct)}</td>
                    <td data-label="Yıllık" className={`r num ${signClass(f.annualized)}`}>{f.annualized != null ? pct(f.annualized) : '–'}</td>
                    <td data-label="Para piyasası medyanı" className="r num nowrap">{f.mm_value != null ? tl2(f.mm_value) : '–'}<br /><span className={`small ${signClass(f.mm_pct)}`}>{pct(f.mm_pct)}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small">
            Yıllık getiri yalnızca yaklaşık 1 yıl (360 gün) ve daha uzun dönemlerde gösterilir; kısa dönemi yıllığa çevirmek yanıltıcı olur.
            Para piyasası medyanı her fon için aynı alış ve son fiyat günleri arasında hesaplanır. Pay kesirli kabul edilir; komisyon ve vergi yoktur.
          </p>
          <section className="panel" aria-labelledby="wi-chart-title">
            <div className="panel-head">
              <h2 id="wi-chart-title">{compactTl(data.amount)} nasıl değişti?</h2>
              <ChartLegend series={series} data={data.series} />
            </div>
            <div className="chart"><ValueChart data={data.series} series={series} months={monthsBetween(data.date, data.as_of)} /></div>
          </section>
        </>
      )}
    </div>
  )
}

export default function SanalPortfoy() {
  const [params, setParams] = useSearchParams()
  const mode = params.get('mod') === 'geriye' ? 'geriye' : 'portfoy'
  const codes = (params.get('fon') || '').toUpperCase().split(',').map((c) => c.trim()).filter(Boolean).slice(0, MAX_WHATIF)
  const code = codes[0] || ''
  useEffect(() => { document.title = 'Sanal Portföy · Fon Analiz' }, [])
  const setMode = (m) => setParams({ ...(m === 'geriye' ? { mod: 'geriye' } : {}), ...(params.get('fon') ? { fon: params.get('fon') } : {}) }, { replace: true })

  return (
    <section className="sim-page">
      <div>
        <h1>Sanal Portföy</h1>
        <p className="hint">Hayali parayla fon alıp satarak dene ya da geçmişte alsaydın ne olurdu, hesapla.</p>
      </div>
      <SimWarning />
      <div className="tabs" role="tablist" aria-label="Mod">
        <button type="button" role="tab" id="tab-portfoy" aria-selected={mode === 'portfoy'} aria-controls="panel-sim" onClick={() => setMode('portfoy')}>Sanal portföy</button>
        <button type="button" role="tab" id="tab-geriye" aria-selected={mode === 'geriye'} aria-controls="panel-sim" onClick={() => setMode('geriye')}>Ya o zaman alsaydım?</button>
      </div>
      <div id="panel-sim" role="tabpanel" aria-labelledby={`tab-${mode}`}>
        {mode === 'portfoy' ? <Portfolio initialCode={code} /> : <WhatIf initialCodes={codes} />}
      </div>
    </section>
  )
}
