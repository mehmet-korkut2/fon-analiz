import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

// Menünün sağı: girişsiz "Giriş / Kayıt ol", girişli kullanıcı adı ve açılır menü.
export default function UserMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const nav = useNavigate()
  const loc = useLocation()

  useEffect(() => { setOpen(false) }, [loc.pathname])
  useEffect(() => {
    if (!open) return
    const close = (e) => { if (!ref.current?.contains(e.target)) setOpen(false) }
    const esc = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc) }
  }, [open])

  if (!user) {
    const next = loc.pathname.startsWith('/giris') || loc.pathname.startsWith('/kayit') ? '' : `?sonra=${encodeURIComponent(loc.pathname + loc.search)}`
    return (
      <div className="user-area">
        <NavLink to={`/giris${next}`} className="user-login">Giriş</NavLink>
        <Link to={`/kayit${next}`} className="btn btn-primary btn-sm">Kayıt ol</Link>
      </div>
    )
  }

  async function out() {
    setOpen(false)
    await logout()
    nav('/')
  }

  return (
    <div className="user-area" ref={ref}>
      <button type="button" className="user-btn" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="user-avatar" aria-hidden="true">{(user.name || user.email).trim()[0].toLocaleUpperCase('tr-TR')}</span>
        <span className="user-name">{user.name || user.email}</span>
        <span aria-hidden="true">▾</span>
      </button>
      {open && (
        <div className="user-menu" role="menu">
          <p className="user-email small muted">{user.email}</p>
          <Link role="menuitem" to="/hesabim">Hesabım</Link>
          <Link role="menuitem" to="/favoriler">Favorilerim</Link>
          <Link role="menuitem" to="/sanal-portfoy">Sanal portföyüm</Link>
          <Link role="menuitem" to="/risk-anketi">Risk profilim</Link>
          <button type="button" role="menuitem" onClick={out}>Çıkış yap</button>
        </div>
      )}
    </div>
  )
}
