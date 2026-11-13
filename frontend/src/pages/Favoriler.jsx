import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getFavorites } from '../api/client'
import { useAuth } from '../auth'
import FavoriteButton from '../components/FavoriteButton'
import LoginRequired from '../components/LoginRequired'
import { pct, signClass } from '../format'

export default function Favoriler() {
  const { user, favorites } = useAuth()
  const [funds, setFunds] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => { document.title = 'Favorilerim · Fon Analiz' }, [])
  // listeden çıkarılan fon tabloda kalır (yanlışlıkla çıkarılırsa yıldızla geri eklenebilir); sayfa yenilenince gider
  useEffect(() => {
    if (!user) return
    getFavorites().then(setFunds).catch(() => setError('Favoriler yüklenemedi.'))
  }, [user])

  if (!user) {
    return (
      <section className="auth-page">
        <h1>Favorilerim</h1>
        <LoginRequired title="Favoriler için giriş yap">Fon sayfalarındaki ☆ düğmesiyle favori ekleyebilir, burada hepsini bir arada görebilirsin.</LoginRequired>
      </section>
    )
  }

  const compare = funds?.filter((f) => favorites.has(f.code)).slice(0, 4).map((f) => f.code) ?? []

  return (
    <section className="favorites-page">
      <div>
        <h1>Favorilerim</h1>
        <p className="hint">Fon sayfalarındaki ☆ düğmesiyle ekle ya da çıkar.</p>
      </div>
      {error && <p className="error">{error}</p>}
      {!funds && !error && <p className="muted">Yükleniyor...</p>}
      {funds && funds.length === 0 && (
        <p className="muted">Henüz favori fonun yok. <Link to="/fonlar">Fonlara göz at →</Link></p>
      )}
      {funds && funds.length > 0 && (
        <>
          <div className="table-wrap">
            <table className="funds-table fav-table">
              <thead>
                <tr><th aria-label="Favori" /><th>Fon</th><th>Kategori</th><th className="r">Risk</th><th className="r">1 ay</th><th className="r">1 yıl</th></tr>
              </thead>
              <tbody>
                {funds.map((f) => (
                  <tr key={f.code} className={favorites.has(f.code) ? '' : 'is-removed'}>
                    <td><FavoriteButton code={f.code} compact /></td>
                    <td className="fund-name"><Link to={`/fonlar/${f.code}`}><strong>{f.code}</strong> {f.name}</Link></td>
                    <td>{f.category ?? '–'}</td>
                    <td className="r num">{f.risk_level ?? '–'}</td>
                    <td className={`r num ${signClass(f.metrics?.ret_1m)}`}>{pct(f.metrics?.ret_1m)}</td>
                    <td className={`r num ${signClass(f.metrics?.ret_1y)}`}>{pct(f.metrics?.ret_1y)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {compare.length > 1 && (
            <p><Link className="btn" to={`/karsilastir?fonlar=${compare.join(',')}`}>İlk {compare.length} favoriyi karşılaştır →</Link></p>
          )}
        </>
      )}
    </section>
  )
}
