import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getBacktest } from '../api/client'
import { num, pct, signClass, trDate } from '../format'

const GRID = '#e5ebe8'
const INK_MUTED = '#5d6b65'
const UP = '#0f7a5c'
const DOWN = '#b3261e'

const month = (d) => trDate(d, { month: 'short', year: '2-digit' })
const pts = (v) => `${v >= 0 ? '+' : '-'}${num(Math.abs(v) * 100, 1)} puan`

function Tip({ active, payload }) {
  if (!active || !payload?.length) return null
  const w = payload[0].payload
  return (
    <div className="chart-tip">
      <span className="muted small">{trDate(w.start)} → {trDate(w.end)}</span>
      <span className="small">Portföy <strong className="num">{pct(w.portfolio_return)}</strong> · PP medyanı <strong className="num">{pct(w.benchmark_return)}</strong></span>
      <strong className={`num ${signClass(w.excess)}`}>{pts(w.excess)}</strong>
      <span className="muted small">{w.codes.join(', ')}</span>
    </div>
  )
}

function Stat({ label, value, cls = '', note }) {
  return (
    <div className="card">
      <span className="card-label">{label}</span>
      <span className={`card-value num ${cls}`}>{value}</span>
      {note && <span className="muted small">{note}</span>}
    </div>
  )
}

export default function RollingBacktest({ profile, qualified }) {
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
  if (!data) return <p className="muted">Yükleniyor...</p>
  const s = data.summary
  if (!s) {
    return (
      <p className="muted">
        Geriye dönük test henüz hesaplanmadı. Gece güncellemesinden sonra otomatik hesaplanır
        (elle: <code>python -m scripts.geriye_donuk_test</code>).
      </p>
    )
  }

  return (
    <div className="rolling">
      <p className="small">
        Son {data.years} yılda her ayın ilk işlem günü, <strong>o güne kadarki veriyle</strong> aynı yöntemle örnek portföy
        seçildi ve {data.horizon_months} ay tutuldu ({s.windows} dönem). Her dönemde portföyün getirisi, para piyasası
        fonlarının medyanıyla karşılaştırıldı. Sonradan işleme kapatılan fonlar da seçim gününde aday sayıldı.
      </p>
      <div className="cards">
        <Stat label="Para piyasası medyanını geçtiği dönem" value={`${s.beats} / ${s.windows}`} />
        <Stat label="Ortalama fazla getiri" value={pts(s.mean_excess)} cls={signClass(s.mean_excess)}
          note={`Portföy ${pct(s.mean_portfolio)}, PP medyanı ${pct(s.mean_benchmark)} (12 aylık ortalama)`} />
        <Stat label="Medyan fazla getiri" value={pts(s.median_excess)} cls={signClass(s.median_excess)} />
        <Stat label="En iyi dönem" value={pts(s.best.excess)} cls={signClass(s.best.excess)}
          note={`${trDate(s.best.start)} seçim: portföy ${pct(s.best.portfolio_return)}, PP ${pct(s.best.benchmark_return)}`} />
        <Stat label="En kötü dönem" value={pts(s.worst.excess)} cls={signClass(s.worst.excess)}
          note={`${trDate(s.worst.start)} seçim: portföy ${pct(s.worst.portfolio_return)}, PP ${pct(s.worst.benchmark_return)}`} />
      </div>

      <h3>Seçim ayına göre fazla getiri</h3>
      <p className="muted small">Çubuk: portföyün sonraki 12 aydaki getirisi eksi para piyasası medyanı. Yeşil: geçti, kırmızı: geride kaldı.</p>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data.windows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="start" tickFormatter={month} minTickGap={16} tickLine={false} axisLine={{ stroke: GRID }} tick={{ fontSize: 12, fill: INK_MUTED }} />
          <YAxis width={44} orientation="right" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: INK_MUTED }}
            tickFormatter={(v) => `${num(v * 100, 0)}`} />
          <ReferenceLine y={0} stroke={INK_MUTED} />
          <Tooltip content={<Tip />} cursor={{ fill: 'rgba(23, 33, 29, .05)' }} />
          <Bar dataKey="excess" radius={[3, 3, 3, 3]} isAnimationActive={false}>
            {data.windows.map((w) => <Cell key={w.start} fill={w.excess >= 0 ? UP : DOWN} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <details className="price-table">
        <summary>Tüm dönemleri tablo olarak göster</summary>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Seçim</th><th>Fonlar</th><th className="r">Portföy</th><th className="r">PP medyanı</th><th className="r">Fark</th></tr>
            </thead>
            <tbody>
              {data.windows.map((w) => (
                <tr key={w.start}>
                  <td className="num">{trDate(w.start)}</td>
                  <td className="small">{w.codes.join(', ')}</td>
                  <td className={`r num ${signClass(w.portfolio_return)}`}>{pct(w.portfolio_return)}</td>
                  <td className="r num">{pct(w.benchmark_return)}</td>
                  <td className={`r num ${signClass(w.excess)}`}>{pts(w.excess)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <p className="muted small">
        Dönemler birer ay arayla başladığı ve 12 ay sürdüğü için birbirleriyle örtüşür; {s.windows} dönem, birbirinden
        bağımsız {s.windows} deneme değildir. Geçmiş performans gelecekteki sonuçların göstergesi değildir.
      </p>
    </div>
  )
}
