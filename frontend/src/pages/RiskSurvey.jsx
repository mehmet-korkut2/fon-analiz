import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { errorMessage, getSurvey, postRiskProfile } from '../api/client'
import { useAuth } from '../auth'
import ProfileSummary from '../components/ProfileSummary'

export default function RiskSurvey() {
  const { user, profile: saved, saveProfile } = useAuth()
  const loc = useLocation()
  const [survey, setSurvey] = useState(null)
  const [error, setError] = useState(null)
  const [editing, setEditing] = useState(() => !saved)
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState(() => saved?.answers ?? {})
  const [qualified, setQualified] = useState(() => saved?.qualified ?? null)
  const [sending, setSending] = useState(false)

  useEffect(() => { document.title = 'Risk Anketi · Fon Analiz' }, [])
  useEffect(() => {
    getSurvey().then(setSurvey).catch(() => setError('Anket yüklenemedi. Backend çalışıyor mu?'))
  }, [])

  if (error) return <section className="survey"><h1>Risk anketi</h1><p className="error">{error}</p></section>
  if (!survey) return <section className="survey"><p className="muted">Yükleniyor...</p></section>

  if (saved && !editing) {
    return (
      <section className="survey">
        <h1>Risk anketi</h1>
        <ProfileSummary saved={saved} />
        {!user && (
          <p className="notice notice-info small">
            Profilin yalnızca bu oturumda tutuluyor. Kalıcı olarak kaydetmek için{' '}
            <Link to={`/giris?sonra=${encodeURIComponent(loc.pathname)}`}>giriş yap</Link> ya da{' '}
            <Link to={`/kayit?sonra=${encodeURIComponent(loc.pathname)}`}>hesap oluştur</Link>; bu profil hesabına aktarılır.
          </p>
        )}
        <div className="survey-actions">
          <Link className="btn btn-primary" to="/oneriler">Önerileri gör →</Link>
          <button type="button" className="btn" onClick={() => { setEditing(true); setStep(0) }}>Anketi yeniden doldur</button>
        </div>
      </section>
    )
  }

  const questions = [...survey.questions, survey.qualified_question]
  const q = questions[step]
  const isQualified = q.id === survey.qualified_question.id
  const value = isQualified ? (qualified == null ? undefined : Number(qualified)) : answers[q.id]
  const last = step === questions.length - 1

  const choose = (v) => {
    if (isQualified) setQualified(v === 1)
    else setAnswers((a) => ({ ...a, [q.id]: v }))
  }

  const submit = async () => {
    setSending(true)
    setError(null)
    try {
      const result = user ? null : await postRiskProfile(answers, Boolean(qualified)) // girişliyse sunucu hesaplayıp kaydeder
      await saveProfile(answers, Boolean(qualified), result)
      setEditing(false)
      window.scrollTo(0, 0)
    } catch (e) {
      setError(errorMessage(e, 'Profil hesaplanamadı.'))
    } finally {
      setSending(false)
    }
  }

  return (
    <section className="survey">
      <div>
        <h1>Risk anketi</h1>
        <p className="hint">
          {questions.length} soru. {user ? 'Sonuç hesabına kaydedilir.' : 'Giriş yapmadan sonuç yalnızca bu oturumda tutulur.'}
        </p>
      </div>
      <div className="progress" role="progressbar" aria-valuemin={1} aria-valuemax={questions.length} aria-valuenow={step + 1}>
        <span style={{ width: `${((step + 1) / questions.length) * 100}%` }} />
      </div>
      <fieldset className="question" key={q.id}>
        <legend>
          <span className="muted small">Soru {step + 1} / {questions.length} · {q.topic}</span>
          <span className="question-text">{q.text}</span>
        </legend>
        <div className="options">
          {q.options.map((o) => (
            <label key={o.value} className={`option${value === o.value ? ' selected' : ''}`}>
              <input type="radio" name={q.id} value={o.value} checked={value === o.value} onChange={() => choose(o.value)} />
              <span>{o.text}</span>
            </label>
          ))}
        </div>
      </fieldset>
      {error && <p className="error">{error}</p>}
      <div className="survey-actions">
        <button type="button" className="btn" disabled={step === 0} onClick={() => setStep((s) => s - 1)}>← Geri</button>
        {last ? (
          <button type="button" className="btn btn-primary" disabled={value === undefined || sending} onClick={submit}>
            {sending ? 'Hesaplanıyor...' : 'Profilimi göster'}
          </button>
        ) : (
          <button type="button" className="btn btn-primary" disabled={value === undefined} onClick={() => setStep((s) => s + 1)}>İleri →</button>
        )}
        {saved && <button type="button" className="btn btn-link" onClick={() => setEditing(false)}>Vazgeç</button>}
      </div>
    </section>
  )
}
