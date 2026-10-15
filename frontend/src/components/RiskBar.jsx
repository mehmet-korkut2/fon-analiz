// TEFAS risk değeri (1-7): 7 bölmeli çubuk + sayı. Renk düşük (1-3) / orta (4-5) / yüksek (6-7).
export default function RiskBar({ level }) {
  if (!level) return <span className="muted">–</span>
  const band = level >= 6 ? 'high' : level >= 4 ? 'mid' : 'low'
  return (
    <span className={`risk risk-${band}`} title={`Risk değeri ${level}/7`}>
      <span className="risk-seg" aria-hidden="true">
        {Array.from({ length: 7 }, (_, i) => <span key={i} className={i < level ? 'on' : undefined} />)}
      </span>
      <span className="num">{level}</span>
      <span className="sr-only">/ 7 risk değeri</span>
    </span>
  )
}
