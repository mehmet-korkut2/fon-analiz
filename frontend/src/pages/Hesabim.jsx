import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { deleteAccount, errorMessage, postPassword } from '../api/client'
import { useAuth } from '../auth'
import LoginRequired from '../components/LoginRequired'
import { trDate } from '../format'

function PasswordForm() {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [repeat, setRepeat] = useState('')
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    if (next.length < 8) return setMsg({ error: 'Yeni şifre en az 8 karakter olmalı.' })
    if (next !== repeat) return setMsg({ error: 'Yeni şifreler aynı değil.' })
    setBusy(true)
    setMsg(null)
    try {
      await postPassword({ current_password: current, new_password: next })
      setCurrent(''); setNext(''); setRepeat('')
      setMsg({ ok: 'Şifren değiştirildi. Diğer cihazlardaki oturumlar kapatıldı.' })
    } catch (err) {
      setMsg({ error: errorMessage(err, 'Şifre değiştirilemedi.') })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="panel auth-form" onSubmit={submit} noValidate>
      <h2>Şifre değiştir</h2>
      <label className="field"><span>Mevcut şifre</span>
        <input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
      </label>
      <label className="field"><span>Yeni şifre</span>
        <input type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} maxLength={128} required />
        <span className="small muted">En az 8 karakter.</span>
      </label>
      <label className="field"><span>Yeni şifre (tekrar)</span>
        <input type="password" autoComplete="new-password" value={repeat} onChange={(e) => setRepeat(e.target.value)} maxLength={128} required />
      </label>
      {msg?.error && <p className="error small" role="alert">{msg.error}</p>}
      {msg?.ok && <p className="ok-note small" role="status">{msg.ok}</p>}
      <button type="submit" className="btn btn-primary" disabled={busy || !current || !next || !repeat}>Şifreyi değiştir</button>
    </form>
  )
}

function DeleteAccount() {
  const { forget } = useAuth()
  const nav = useNavigate()
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await deleteAccount(password)
      forget()
      nav('/', { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Hesap silinemedi.'))
      setBusy(false)
    }
  }

  return (
    <div className="panel danger-zone">
      <h2>Hesabı sil</h2>
      <p className="small">Hesabın, risk profilin, sanal portföyün ve favorilerin kalıcı olarak silinir. Geri alınamaz.</p>
      {!open ? (
        <div><button type="button" className="btn btn-danger" onClick={() => setOpen(true)}>Hesabımı sil...</button></div>
      ) : (
        <form className="auth-form" onSubmit={submit} noValidate>
          <label className="field"><span>Onaylamak için şifren</span>
            <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          {error && <p className="error small" role="alert">{error}</p>}
          <div className="detail-actions">
            <button type="submit" className="btn btn-danger" disabled={busy || !password}>Hesabımı kalıcı olarak sil</button>
            <button type="button" className="btn" onClick={() => { setOpen(false); setPassword(''); setError(null) }}>Vazgeç</button>
          </div>
        </form>
      )}
    </div>
  )
}

export default function Hesabim() {
  const { user, profile, favorites, logout } = useAuth()
  const nav = useNavigate()
  useEffect(() => { document.title = 'Hesabım · Fon Analiz' }, [])
  if (!user) return <section className="auth-page"><h1>Hesabım</h1><LoginRequired title="Giriş yapmalısın">Hesap ayarları için giriş yap.</LoginRequired></section>

  return (
    <section className="auth-page account">
      <div>
        <h1>Hesabım</h1>
        <p className="hint">{user.name} · {user.email}{user.created_at && ` · ${trDate(user.created_at)} tarihinden beri üye`}</p>
      </div>
      <div className="cards">
        <Link className="card account-link" to="/sanal-portfoy"><span className="card-label">Sanal portföy</span><span>Hayali parayla al-sat →</span></Link>
        <Link className="card account-link" to="/favoriler"><span className="card-label">Favoriler</span><span>{favorites.size} fon →</span></Link>
        <Link className="card account-link" to="/risk-anketi"><span className="card-label">Risk profili</span><span>{profile ? `${profile.result.label} →` : 'Anketi doldur →'}</span></Link>
      </div>
      <PasswordForm />
      <div className="panel">
        <h2>Oturum</h2>
        <p className="small">Oturumun bu tarayıcıda 14 gün açık kalır. Ortak bir bilgisayardaysan çıkış yap.</p>
        <div><button type="button" className="btn" onClick={async () => { await logout(); nav('/') }}>Çıkış yap</button></div>
      </div>
      <DeleteAccount />
    </section>
  )
}
