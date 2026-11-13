import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { useAuth } from '../auth'

// Favori düğmesi. Girişsiz kullanıcıyı giriş sayfasına götürür (sonra bu sayfaya döner).
// compact: tablo satırında yalnızca yıldız; durum aria-pressed ve başlıkla da belirtilir (renge bağlı değil).
export default function FavoriteButton({ code, compact = false }) {
  const { user, favorites, toggleFavorite } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const on = favorites.has(code)
  const label = on ? 'Favorilerden çıkar' : 'Favorilere ekle'

  async function click() {
    if (!user) {
      nav(`/giris?sonra=${encodeURIComponent(loc.pathname + loc.search)}`)
      return
    }
    setBusy(true)
    setError(null)
    try {
      await toggleFavorite(code)
    } catch (e) {
      setError(errorMessage(e, 'Favori güncellenemedi.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button
        type="button" className={`btn fav-btn${compact ? ' fav-compact' : ''}${on ? ' is-on' : ''}`}
        aria-pressed={on} aria-label={`${code}: ${label}`} title={user ? label : 'Favoriler için giriş yapın'}
        onClick={click} disabled={busy}
      >
        <span aria-hidden="true">{on ? '★' : '☆'}</span>
        {!compact && <span>{on ? 'Favorilerde' : 'Favorilere ekle'}</span>}
      </button>
      {error && <span className="error small" role="alert">{error}</span>}
    </>
  )
}
