import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getCategories, getFunds, getHealth, getStatus } from '../api/client'
import RiskBar from '../components/RiskBar'
import { pct, signClass } from '../format'
import { compactTl, count } from '../money'
import { loadProfile } from '../profileStore'

const FEATURED = 8
const fmtDate = (s) => (s ? new Date(s).toLocaleString('tr-TR', { dateStyle: 'medium', timeStyle: s.length > 10 ? 'short' : undefined }) : '–')

export default function Home() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [online, setOnline] = useState(null)
  const [status, setStatus] = useState(null)
  const [categories, setCategories] = useState(null)
  const [featured, setFeatured] = useState(null)
  const [error, setError] = useState(null)
  const profile = loadProfile()?.result

  useEffect(() => {
    document.title = 'Fon Analiz'
    getHealth().then((d) => setOnline(d.status === 'ok')).catch(() => setOnline(false))
    getStatus().then(setStatus).catch(() => {})
    getCategories().then(setCategories).catch(() => setCategories([]))
    getFunds({ sort: 'total_value', order: 'desc', page_size: FEATURED })
      .then((d) => setFeatured(d.items))
      .catch(() => setError('Fonlar yüklenemedi. Backend çalışıyor mu?'))
  }, [])

  const search = (e) => {
    e.preventDefault()
    const q = query.trim()
    navigate(q ? `/fonlar?q=${encodeURIComponent(q)}` : '/fonlar')
  }

  return (
    <section className="home">
      <div className="home-hero">
        <div className="home-intro">
          <h1 className="home-title">Fonları karşılaştır, <em>sana uygun</em> olanı bul.</h1>
          <p className="home-lead">
            TEFAS'taki {status ? status.fund_count.toLocaleString('tr-TR') : 'bütün'} yatırım fonunun getirisi, riski ve
            geçmişi tek yerde. Fonları incele, yan yana koy, risk profiline uyanları gör.
          </p>
          <form className="home-search" role="search" onSubmit={search}>
            <label htmlFor="home-q" className="sr-only">Fon ara</label>
            <input
              id="home-q" type="search" placeholder="Fon kodu ya da adı (ör. TTE, altın)"
              value={query} onChange={(e) => setQuery(e.target.value)}
            />
            <button type="submit" className="btn btn-primary">Ara</button>
          </form>
        </div>

        <aside className="home-cta" aria-labelledby="cta-title">
          {profile ? (
            <>
              <div>
                <h2 id="cta-title">Profilin: {profile.label}</h2>
                <p>Risk anketine göre profiline uygun fonları ve örnek bir portföyü gör.</p>
              </div>
              <Link to="/oneriler" className="cta-link">Önerileri gör →</Link>
              <Link to="/risk-anketi" className="cta-secondary small">Anketi yeniden doldur</Link>
            </>
          ) : (
            <>
              <div>
                <h2 id="cta-title">Hangi fonlar sana uygun?</h2>
                <p>Kısa bir risk anketiyle yatırım süreni ve kayıplara tepkini ölç; profiline uyan fonları gerekçeleriyle gör.</p>
              </div>
              <ul className="cta-steps">
                <li>9 kısa soru</li>
                <li>Kayıt gerekmez</li>
                <li>Cevaplar tarayıcında kalır</li>
              </ul>
              <Link to="/risk-anketi" className="cta-link">Risk anketine başla →</Link>
            </>
          )}
        </aside>
      </div>

      <section aria-labelledby="cat-title">
        <div className="section-head">
          <h2 id="cat-title">Kategoriler</h2>
          <Link to="/fonlar" className="small">Bütün fonlar →</Link>
        </div>
        {categories === null && <p className="muted">Yükleniyor...</p>}
        {categories?.length > 0 && (
          <ul className="cat-grid">
            {categories.map((c) => (
              <li key={c.name}>
                <Link to={`/fonlar?kategori=${encodeURIComponent(c.name)}`} className="cat-tile">
                  <span className="cat-name">{c.name}</span>
                  <span className="cat-count"><span className="num">{c.count}</span> fon</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="featured-title">
        <div className="section-head">
          <h2 id="featured-title">Öne çıkan fonlar</h2>
          <span className="muted small">Portföy büyüklüğüne göre en büyük {FEATURED} fon. Bir sıralama ya da öneri değildir.</span>
        </div>
        {error && <p className="error">{error}</p>}
        <div className="table-wrap">
          <table className="featured-table">
            <thead>
              <tr>
                <th scope="col">Kod</th>
                <th scope="col">Fon</th>
                <th scope="col">Risk</th>
                <th scope="col" className="r">1 yıl</th>
                <th scope="col" className="r">Büyüklük</th>
                <th scope="col" className="r">Yatırımcı</th>
              </tr>
            </thead>
            <tbody>
              {!featured && !error && <tr><td colSpan={6} className="muted">Yükleniyor...</td></tr>}
              {featured?.map((f) => (
                <tr key={f.code}>
                  <td className="num"><Link to={`/fonlar/${f.code}`}><strong>{f.code}</strong></Link></td>
                  <td className="fund-name">
                    <Link to={`/fonlar/${f.code}`}>{f.name}</Link>
                    {f.category && <span className="muted small">{f.category}</span>}
                  </td>
                  <td><RiskBar level={f.risk_level} /></td>
                  <td className={`r num ${signClass(f.metrics?.ret_1y)}`}>{pct(f.metrics?.ret_1y)}</td>
                  <td className="r num nowrap">{compactTl(f.total_value)}</td>
                  <td className="r num">{count(f.investor_count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <p className="home-status" aria-live="polite">
        <span>
          <span className={`status-dot${online === false ? ' off' : ''}`} aria-hidden="true" />
          {online === null ? 'Bağlantı kontrol ediliyor...' : online ? 'Veri sunucusu bağlı' : "Veri sunucusuna ulaşılamadı. Backend çalışıyor mu?"}
        </span>
        {status && <span>Son fiyat tarihi: {fmtDate(status.latest_price_date)}</span>}
        {status && <span>{status.price_count.toLocaleString('tr-TR')} fiyat kaydı</span>}
        {status && <span>Sonraki otomatik güncelleme: {status.next_update ? fmtDate(status.next_update) : 'kapalı'}</span>}
      </p>
    </section>
  )
}
