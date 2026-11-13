import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { useAuth } from '../auth'
import { safeNext } from './Giris'

const MIN = 8

export default function Kayit() {
  const { user, register } = useAuth()
  const [params] = useSearchParams()
  const next = safeNext(params.get('sonra'))
  const nav = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [repeat, setRepeat] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => { document.title = 'Hesap oluştur · Fon Analiz' }, [])
  if (user && !busy) return <Navigate to={next} replace />

  const short = password.length > 0 && password.length < MIN
  const mismatch = repeat.length > 0 && repeat !== password

  async function submit(e) {
    e.preventDefault()
    if (password.length < MIN) return setError(`Şifre en az ${MIN} karakter olmalı.`)
    if (password !== repeat) return setError('Şifreler aynı değil.')
    setBusy(true)
    setError(null)
    try {
      await register(name, email, password)
      nav(next, { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Hesap oluşturulamadı.'))
      setBusy(false)
    }
  }

  return (
    <section className="auth-page">
      <h1>Hesap oluştur</h1>
      <p className="hint">Fon listesi, karşılaştırma ve tahminler girişsiz de açık. Hesap; sanal portföy, favoriler ve risk profilini saklamak için.</p>
      <form className="panel auth-form" onSubmit={submit} noValidate>
        <label className="field">
          <span>Ad</span>
          <input autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required />
        </label>
        <label className="field">
          <span>E-posta</span>
          <input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label className="field">
          <span>Şifre</span>
          <input type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)}
            aria-describedby="pw-rule" maxLength={128} required />
          <span id="pw-rule" className={`small ${short ? 'error' : 'muted'}`}>En az {MIN} karakter.</span>
        </label>
        <label className="field">
          <span>Şifre (tekrar)</span>
          <input type="password" autoComplete="new-password" value={repeat} onChange={(e) => setRepeat(e.target.value)} maxLength={128} required />
          {mismatch && <span className="small error">Şifreler aynı değil.</span>}
        </label>
        {error && <p className="error small" role="alert">{error}</p>}
        <button type="submit" className="btn btn-primary" disabled={busy || !name.trim() || !email || !password || !repeat}>
          {busy ? 'Hesap oluşturuluyor...' : 'Hesap oluştur'}
        </button>
        <p className="small muted">Zaten hesabın var mı? <Link to={`/giris${params.get('sonra') ? `?sonra=${encodeURIComponent(next)}` : ''}`}>Giriş yap</Link></p>
        <p className="small muted">Şifren düz metin olarak saklanmaz (Argon2id ile özetlenir). E-posta doğrulaması ve e-postayla şifre sıfırlama yoktur; şifreni unutursan uygulamanın çalıştığı bilgisayardan sıfırlanabilir.</p>
      </form>
    </section>
  )
}
