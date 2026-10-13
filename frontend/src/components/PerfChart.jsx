import { useMemo } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { monthTicks } from '../chart'
import { num, pct, signClass, trDate } from '../format'

const GRID = '#e5ebe8'
const INK_MUTED = '#5d6b65'
const PORTFOLIO = '#2a78d6' // kategorik paletin 1. rengi
const BENCHMARK = '#8a948f' // kıyas: nötr gri, kesikli

function Tip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tip">
      <span className="muted small">{trDate(label, { day: 'numeric', month: 'long', year: 'numeric' })}</span>
      {payload.map((p) => (
        <span key={p.dataKey} className="tip-row">
          <span className="swatch" style={{ background: p.dataKey === 'portfolio' ? PORTFOLIO : BENCHMARK }} />
          <strong>{p.dataKey === 'portfolio' ? 'Portföy' : 'Kıyas'}</strong>
          <span className="num">{num(p.value, 1)}</span>
          <span className={`num small ${signClass(p.value - 100)}`}>{pct(p.value / 100 - 1)}</span>
        </span>
      ))}
    </div>
  )
}

// perf: PerformanceOut (backend). 100'den başlayan portföy ve kıyas serileri.
export default function PerfChart({ perf, height = 260 }) {
  const ticks = useMemo(() => monthTicks(perf.series, 12), [perf.series])
  return (
    <div className="perf">
      <div className="legend">
        <span className="legend-item">
          <span className="legend-line" style={{ background: PORTFOLIO }} />
          <strong>Portföy</strong>
          <span className={`num ${signClass(perf.portfolio.return)}`}>{pct(perf.portfolio.return)}</span>
        </span>
        <span className="legend-item">
          <span className="legend-line legend-dashed" style={{ borderColor: BENCHMARK }} />
          <strong>{perf.benchmark_label}</strong>
          <span className={`num ${signClass(perf.benchmark.return)}`}>{pct(perf.benchmark.return)}</span>
          <span className="muted small">({perf.benchmark_funds} fon)</span>
        </span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={perf.series} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis
            dataKey="date" ticks={ticks} minTickGap={24} tickLine={false} axisLine={{ stroke: GRID }}
            tick={{ fontSize: 12, fill: INK_MUTED }} tickFormatter={(d) => trDate(d, { month: 'short', year: '2-digit' })}
          />
          <YAxis
            domain={['auto', 'auto']} width={44} orientation="right" tickLine={false} axisLine={false}
            tick={{ fontSize: 12, fill: INK_MUTED }} tickFormatter={(v) => num(v, 0)}
          />
          <ReferenceLine y={100} stroke={INK_MUTED} strokeDasharray="3 3" />
          <Tooltip content={<Tip />} cursor={{ stroke: INK_MUTED, strokeDasharray: '3 3' }} />
          <Line type="linear" dataKey="benchmark" stroke={BENCHMARK} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
          <Line type="linear" dataKey="portfolio" stroke={PORTFOLIO} strokeWidth={2} dot={false} activeDot={{ r: 4, stroke: '#fff', strokeWidth: 2 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      <table className="perf-stats">
        <thead><tr><th /><th className="r">Getiri</th><th className="r">Volatilite</th><th className="r">Maks. düşüş</th></tr></thead>
        <tbody>
          {[['Portföy', perf.portfolio], ['Kıyas', perf.benchmark]].map(([label, s]) => (
            <tr key={label}>
              <th scope="row">{label}</th>
              <td className={`r num ${signClass(s.return)}`}>{pct(s.return)}</td>
              <td className="r num">{s.volatility == null ? '–' : `${num(s.volatility * 100, 1)}%`}</td>
              <td className={`r num ${s.max_drawdown < -0.0005 ? 'down' : ''}`}>{pct(s.max_drawdown)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small chart-note">
        {trDate(perf.start)} – {trDate(perf.end)} · başlangıçta 100 · eşit ağırlıklı, al-tut (yeniden dengeleme yok)
      </p>
    </div>
  )
}
