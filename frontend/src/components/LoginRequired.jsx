import { Link, useLocation } from 'react-router-dom'

// Giriş gerektiren bölümde girişsiz kullanıcıya gösterilir; giriş/kayıttan sonra aynı sayfaya dönülür.
export default function LoginRequired({ title, children }) {
  const loc = useLocation()
  const next = encodeURIComponent(loc.pathname + loc.search)
  return (
    <div className="panel login-required">
      <h2>{title}</h2>
      <p className="small">{children}</p>
      <div className="detail-actions">
        <Link className="btn btn-primary" to={`/giris?sonra=${next}`}>Giriş yap</Link>
        <Link className="btn" to={`/kayit?sonra=${next}`}>Hesap oluştur</Link>
      </div>
    </div>
  )
}
