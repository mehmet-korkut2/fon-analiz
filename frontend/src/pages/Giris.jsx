import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { useAuth } from '../auth'

// Girişten sonra dönülecek sayfa: yalnızca site içi yol (açık yönlendirmeye karşı)
// eslint-disable-next-line react-refresh/only-export-components
export function safeNext(v) {
  return v && v.startsWith('/') && !v.startsWith('//') && !v.startsWith('/\\') ? v : '/'
}

export default function Giris() {
  const { user, login } = useAuth()
  const [params] = useSearchParams()
  const next = safeNext(params.get('sonra'))
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => { document.title = 'Giriş · Fon Analiz' }, [])
  if (user && !busy) return <Navigate to={next} replace />

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
      nav(next, { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Giriş yapılamadı.'))
      setBusy(false)
    }
  }

  return (
    <section className="auth-page">
      <h1>Giriş yap</h1>
      <p className="hint">Sanal portföyün, favorilerin ve risk profilin hesabında saklanır.</p>
      <form className="panel auth-form" onSubmit={submit} noValidate>
        <label className="field">
          <span>E-posta</span>
          <input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label className="field">
          <span>Şifre</span>
          <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        {error && <p className="error small" role="alert">{error}</p>}
        <button type="submit" className="btn btn-primary" disabled={busy || !email || !password}>{busy ? 'Giriş yapılıyor...' : 'Giriş yap'}</button>
        <p className="small muted">Hesabın yok mu? <Link to={`/kayit${params.get('sonra') ? `?sonra=${encodeURIComponent(next)}` : ''}`}>Hesap oluştur</Link></p>
      </form>
    </section>
  )
}
