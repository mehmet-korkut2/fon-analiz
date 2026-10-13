import { trDate } from '../format'

const MARKS = [40, 70] // profil eşikleri (backend: risk_survey.PROFILE_RULES)

export default function ProfileSummary({ saved, compact = false }) {
  const r = saved.result
  return (
    <div className={`profile-card profile-${r.profile}`}>
      <div className="profile-head">
        <div>
          <span className="card-label">Risk profilin</span>
          <span className="profile-label">{r.label}</span>
        </div>
        <div className="profile-score">
          <span className="card-label">Puan</span>
          <span className="num">{r.score}<span className="muted small"> / 100</span></span>
        </div>
      </div>
      <div className="score-meter" role="img" aria-label={`Puan ${r.score} / 100`}>
        <span className="score-fill" style={{ width: `${r.score}%` }} />
        {MARKS.map((m) => <span key={m} className="score-mark" style={{ left: `${m}%` }} />)}
      </div>
      <div className="score-scale muted small"><span>Temkinli</span><span>Dengeli</span><span>Agresif</span></div>
      {!compact && <p className="profile-desc">{r.description}</p>}
      <ul className="profile-facts small">
        <li>Uygun TEFAS risk değeri: <strong>{r.risk_range[0]}–{r.risk_range[1]}</strong></li>
        <li>Fonun yıllık volatilitesi: <strong>{r.max_volatility == null ? 'sınır yok' : `en fazla %${r.max_volatility * 100}`}</strong></li>
        <li>Serbest fonlar: <strong>{r.qualified ? 'dahil (nitelikli yatırımcı)' : 'dahil değil'}</strong></li>
        {saved.savedAt && <li className="muted">Anket tarihi: {trDate(saved.savedAt)}</li>}
      </ul>
      {r.caps.length > 0 && (
        <div className="caps">
          <p className="small"><strong>Puanına göre profilin {r.score_profile} olurdu, ama şu nedenle {r.label.toLowerCase()} olarak belirlendi:</strong></p>
          <ul className="small">{r.caps.map((c) => <li key={c.rule}>{c.message}</li>)}</ul>
        </div>
      )}
    </div>
  )
}
