import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getFavorites } from '../api/client'
import { useAuth } from '../auth'
import { pct, signClass } from '../format'

const SHOW = 5

// Ana sayfadaki favori özeti (yalnızca girişli kullanıcı): ilk 5 favori, günlük değişim ve 1 yıl getirisi.
export default function FavoritesSummary() {
  const { user, favorites } = useAuth()
  const [funds, setFunds] = useState(null)
  const size = favorites.size

  useEffect(() => {
    if (!user || size === 0) return
    let ignore = false
    getFavorites().then((d) => { if (!ignore) setFunds(d) }).catch(() => { if (!ignore) setFunds([]) })
    return () => { ignore = true }
  }, [user, size])

  if (!user) return null
  const list = (funds ?? []).filter((f) => favorites.has(f.code))
  const warned = list.filter((f) => f.warning).length

  return (
    <section aria-labelledby="fav-title" className="fav-summary">
      <div className="section-head">
        <h2 id="fav-title">Favorilerim</h2>
        {size > 0 && <Link to="/favoriler" className="small">Hepsi ({size}) →</Link>}
      </div>
      {size === 0 ? (
        <p className="muted small">Henüz favorin yok. Fon listesinde ya da fon sayfasında ☆ düğmesine bas.</p>
      ) : !funds ? (
        <p className="muted small">Yükleniyor...</p>
      ) : (
        <>
          {warned > 0 && <p className="notice notice-closed small">{warned} favori fonda uyarı var (işleme kapatıldı ya da verisi eski). <Link to="/favoriler">Ayrıntı →</Link></p>}
          <ul className="fav-mini">
            {list.slice(0, SHOW).map((f) => (
              <li key={f.code}>
                <Link to={`/fonlar/${f.code}`} className="fav-mini-name">
                  <strong className="num">{f.code}</strong> <span>{f.name}</span>
                </Link>
                {f.warning && <span className="fav-mini-warn small" title={f.warning}>⚠ uyarı</span>}
                <span className={`num small ${signClass(f.metrics?.daily_change)}`} title="Günlük değişim">{pct(f.metrics?.daily_change)}</span>
                <span className={`num small ${signClass(f.metrics?.ret_1y)}`} title="1 yıllık getiri">1Y {pct(f.metrics?.ret_1y)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
