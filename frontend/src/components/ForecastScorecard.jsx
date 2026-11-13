import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getScorecard } from '../api/client'
import { axisDigits } from '../chart'
import { num, trDate } from '../format'
import { C } from '../theme'

// Tahmin karnesi: modelin (drift) geçmişte yaptığı gün gün tahminlerin gerçekleşenle karşılaştırması.
// GET /api/funds/{kod}/forecast-scorecard

const SOURCE = { canli: 'Canlı', geriye_donuk: 'Geriye dönük' }
const fmtPrice = (v) => (v == null ? '–' : num(v, v < 100 ? 4 : 2))
const sp = (v, d = 2) => (v == null ? '–' : `${v > 0 ? '+' : v < 0 ? '-' : ''}${num(Math.abs(v) * 100, d)}%`)
const p1 = (v) => (v == null ? '–' : `${num(v * 100, 0)}%`)
const short = (d) => trDate(d, { day: 'numeric', month: 'short' })

function SourceBadge({ source }) {
  return <span className={`source-badge ${source === 'canli' ? 'is-live' : 'is-back'}`}>{SOURCE[source]}</span>
}

function BandStatus({ row }) {
  if (row.realized_price == null) return <span className="muted">Bekleniyor</span>
  return row.in_band ? <span className="badge-ok">✓ Aralıkta</span> : <span className="badge-fail">✗ Aralık dışında</span>
}

function Tip({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="chart-tip">
      <span className="muted small">{trDate(p.date, { day: 'numeric', month: 'long', year: 'numeric' })}{p.h ? ` · ${p.h}. işlem günü` : ' · tahmin günü'}</span>
      <span className="small num"><span className="legend-line legend-dashed" style={{ borderColor: C.forecast }} /> Tahmin: <strong>{fmtPrice(p.fc)}</strong></span>
      {p.h > 0 && <span className="muted small num">%80 aralık: {fmtPrice(p.band[0])} – {fmtPrice(p.band[1])}</span>}
      <span className="small num">
        <span className="legend-line" style={{ background: C.price }} /> Gerçekleşen: <strong>{p.real == null ? 'bekleniyor' : fmtPrice(p.real)}</strong>
      </span>
    </div>
  )
}

function ScoreChart({ sel }) {
  const data = useMemo(() => [
    { date: sel.as_of, h: 0, fc: sel.base_price, band: [sel.base_price, sel.base_price], real: sel.base_price },
    ...sel.rows.map((r) => ({ date: r.realized_date ?? r.target_date, h: r.horizon, fc: r.pred_price, band: [r.lo_price, r.hi_price], real: r.realized_price })),
  ], [sel])
  const values = data.flatMap((d) => [...d.band, d.real]).filter((v) => v != null)
  const digits = axisDigits(Math.max(...values) - Math.min(...values))
  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid vertical={false} stroke={C.grid} />
        <XAxis dataKey="date" tickFormatter={short} minTickGap={28} tick={{ fontSize: 12, fill: C.axis }} tickLine={false} axisLine={{ stroke: C.grid }} />
        <YAxis domain={['auto', 'auto']} width={64} orientation="right" tickFormatter={(v) => num(v, digits)}
          tick={{ fontSize: 12, fill: C.axis }} tickLine={false} axisLine={false} />
        <Tooltip content={<Tip />} cursor={{ stroke: C.axis, strokeDasharray: '3 3' }} />
        <Area type="linear" dataKey="band" stroke="none" fill={C.forecast} fillOpacity={0.16} isAnimationActive={false} activeDot={false} />
        <Line type="linear" dataKey="fc" stroke={C.forecast} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false}
          activeDot={{ r: 4, stroke: C.surface, strokeWidth: 2 }} />
        <Line type="linear" dataKey="real" stroke={C.price} strokeWidth={2} dot={{ r: 3, strokeWidth: 0, fill: C.price }} connectNulls={false}
          isAnimationActive={false} activeDot={{ r: 5, stroke: C.surface, strokeWidth: 2 }} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

// Sütun grubu: kaynak + yöntem sürümü (yöntem değişirse sonuçlar karışmaz)
const groupsOf = (rows) => [...new Set(rows.map((r) => `${r.source}|${r.method_version}`))]
  .sort((a, b) => (a.startsWith('canli') ? 0 : 1) - (b.startsWith('canli') ? 0 : 1) || b.localeCompare(a))
const groupLabel = (g) => { const [s, v] = g.split('|'); return `${SOURCE[s]} · ${v}` }

function Summary({ rows }) {
  const sources = groupsOf(rows)
  const horizons = [...new Map(rows.map((r) => [r.horizon, r.label])).entries()].sort((a, b) => a[0] - b[0])
  if (!rows.length) return <p className="muted small">Henüz gerçekleşmiş tahmin yok.</p>
  return (
    <div className="table-wrap">
      <table className="ml-table score-summary">
        <thead>
          <tr>
            <th rowSpan={2}>Ufuk</th>
            {sources.map((s) => <th key={s} colSpan={3} className="c">{groupLabel(s)}</th>)}
          </tr>
          <tr>
            {sources.map((s) => [
              <th key={`${s}c`} className="r">Aralıkta kalma</th>,
              <th key={`${s}m`} className="r">Ort. mutlak sapma</th>,
              <th key={`${s}n`} className="r">Tahmin</th>,
            ])}
          </tr>
        </thead>
        <tbody>
          {horizons.map(([h, label]) => (
            <tr key={h}>
              <th scope="row">{label} <span className="muted small">({h} işlem günü)</span></th>
              {sources.map((s) => {
                const r = rows.find((x) => `${x.source}|${x.method_version}` === s && x.horizon === h)
                return [
                  <td key={`${s}c`} className="r num">{p1(r?.coverage)}</td>,
                  <td key={`${s}m`} className="r num">{r ? `${num(r.mae_pct * 100, 2)}%` : '–'}</td>,
                  <td key={`${s}n`} className="r num">{r ? r.n : 0}</td>,
                ]
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function ForecastScorecard({ code }) {
  const [card, setCard] = useState(null)
  const [pickState, setPick] = useState(null) // { code, as_of, source }; null: sunucunun seçtiği gün
  const pickKey = pickState?.code === code ? `${pickState.as_of}|${pickState.source}` : ''
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let ignore = false
    setLoading(true)
    setError(null)
    const [as_of, source] = pickKey ? pickKey.split('|') : []
    getScorecard(code, pickKey ? { as_of, source } : undefined)
      .then((d) => { if (!ignore) setCard(d) })
      .catch((e) => { if (!ignore) setError(e.response?.status === 404 ? 'Bu fon için kayıtlı tahmin yok.' : 'Tahmin karnesi yüklenemedi.') })
      .finally(() => { if (!ignore) setLoading(false) })
    return () => { ignore = true }
  }, [code, pickKey])

  if (error) {
    return <div className="panel"><h2>Tahmin karnesi</h2><p className="muted small">{error}</p></div>
  }
  if (!card || card.code !== code.toUpperCase()) return <div className="panel"><h2>Tahmin karnesi</h2><p className="muted small">Yükleniyor...</p></div>
  const sel = card.selected
  const value = sel ? `${sel.as_of}|${sel.source}` : ''
  const realized = sel ? sel.rows.filter((r) => r.realized_price != null) : []
  const inBand = realized.filter((r) => r.in_band).length

  return (
    <div className={`panel scorecard${loading ? ' is-loading' : ''}`}>
      <div className="scorecard-head">
        <div>
          <h2>Tahmin karnesi</h2>
          <p className="muted small">Geçmiş tahminler gün gün, gerçekleşen fiyatla karşılaştırmalı (geçmiş eğilime dayalı tahmin, %80 aralık).</p>
        </div>
        <label className="score-pick small">
          <span>Tahmin günü</span>
          <select value={value} onChange={(e) => { const [a, s] = e.target.value.split('|'); setPick({ code, as_of: a, source: s }) }}>
            {card.days.map((d) => (
              <option key={`${d.as_of}|${d.source}`} value={`${d.as_of}|${d.source}`}>
                {trDate(d.as_of, { day: 'numeric', month: 'short', year: 'numeric' })} · {SOURCE[d.source]} · {d.method_version}
                {d.horizons < 21 ? ` (yalnızca ${d.horizons} ufuk)` : ''} · {d.realized}/{d.horizons} gerçekleşti
              </option>
            ))}
          </select>
        </label>
      </div>

      {sel && (
        <>
          <p className={`source-note small ${sel.source === 'canli' ? 'is-live' : 'is-back'}`}>
            <SourceBadge source={sel.source} />{' '}
            {sel.source === 'canli'
              ? 'Bu tahmin o günün gece güncellemesinde, o günkü veriyle kaydedildi; sonradan değiştirilmedi.'
              : card.backfill_note}
            <br />Yöntem: <strong>{sel.method} {sel.method_version}</strong>{sel.method_note && ` (${sel.method_note})`}.
          </p>
          <div className="legend small">
            <span className="legend-item"><span className="legend-line legend-dashed" style={{ borderColor: C.forecast }} />Tahmin</span>
            <span className="legend-item"><span className="legend-swatch" style={{ background: C.forecast }} />%80 aralık</span>
            <span className="legend-item"><span className="legend-line" style={{ background: C.price }} />Gerçekleşen fiyat</span>
          </div>
          <ScoreChart sel={sel} />
          <p className="muted small">
            {trDate(sel.as_of)} günündeki fiyat {fmtPrice(sel.base_price)} TL.{' '}
            {realized.length
              ? <>Gerçekleşen {realized.length} günün <strong>{inBand}</strong> tanesinde fiyat %80 aralığın içinde kaldı.</>
              : 'Bu tahminin hiçbir günü henüz gerçekleşmedi.'}
            {realized.length < sel.rows.length && ` ${sel.rows.length - realized.length} gün bekleniyor.`}
          </p>
          <details className="price-table" open>
            <summary>Gün gün tablo</summary>
            <div className="table-wrap">
              <table className="ml-table score-table">
                <thead>
                  <tr>
                    <th className="r">Ufuk</th><th>Hedef tarih</th><th className="r">Tahmin</th><th className="r">%80 aralık</th>
                    <th className="r">Gerçekleşen</th><th className="r">Sapma (TL)</th><th className="r">Sapma (%)</th><th>Aralıkta mı?</th>
                  </tr>
                </thead>
                <tbody>
                  {sel.rows.map((r) => (
                    <tr key={r.horizon} className={r.realized_price == null ? 'is-pending' : ''}>
                      <td className="r num">{r.horizon}</td>
                      <td className="num">
                        {trDate(r.realized_date ?? r.target_date)}
                        {r.realized_date && r.realized_date !== r.target_date && <span className="muted small"> (takvimde {trDate(r.target_date)})</span>}
                      </td>
                      <td className="r num">{fmtPrice(r.pred_price)}</td>
                      <td className="r num">{fmtPrice(r.lo_price)} – {fmtPrice(r.hi_price)}</td>
                      <td className="r num">{r.realized_price == null ? <span className="muted">bekleniyor</span> : fmtPrice(r.realized_price)}</td>
                      <td className="r num">{r.error_tl == null ? '–' : `${r.error_tl > 0 ? '+' : ''}${fmtPrice(r.error_tl)}`}</td>
                      <td className="r num">{sp(r.error_pct)}</td>
                      <td><BandStatus row={r} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}

      <h3>Bu fonun karnesi</h3>
      <p className="muted small">
        Bu fon için kaydedilen bütün gerçekleşmiş tahminler. Aralıkta kalma oranı %80'e yakınsa aralık iyi kalibre edilmiştir.
        Sapma: (gerçekleşen − tahmin) / tahmin. Canlı ve geriye dönük tahminler ayrı sayılır.
      </p>
      <Summary rows={card.summary} />
      <p className="muted small">
        {card.note} Bütün fonların karnesi: <Link to="/model-performansi">Model performansı →</Link>
      </p>
    </div>
  )
}
