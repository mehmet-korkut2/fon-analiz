export default function RiskBar({ level }) {
  if (!level) return <span className="muted">–</span>
  const color = level >= 6 ? '#b4570e' : level >= 4 ? '#c98a1a' : '#0f7a5c'
  return (
    <span className="risk" title={`Risk değeri ${level}/7`}>
      <span className="risk-track"><span style={{ width: `${(level / 7) * 100}%`, background: color }} /></span>
      <span className="num">{level}</span>
    </span>
  )
}
