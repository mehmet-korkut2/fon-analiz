import { useEffect, useState } from 'react'
import { getHealth, getStatus } from '../api/client'

const fmtDate = (s) => (s ? new Date(s).toLocaleString('tr-TR', { dateStyle: 'medium', timeStyle: s.length > 10 ? 'short' : undefined }) : '–')

export default function Home() {
  const [health, setHealth] = useState('kontrol ediliyor...')
  const [status, setStatus] = useState(null)

  useEffect(() => {
    getHealth()
      .then((d) => setHealth(d.status === 'ok' ? 'Backend bağlı ✓' : 'Beklenmeyen yanıt'))
      .catch(() => setHealth("Backend'e ulaşılamadı. FastAPI çalışıyor mu?"))
    getStatus().then(setStatus).catch(() => {})
  }, [])

  const last = status?.last_update

  return (
    <section>
      <h1>Fon Analiz Platformu</h1>
      <p>Yatırım fonlarını incele, karşılaştır ve risk profiline uygun fonları bul.</p>
      <p className="status">Durum: {health}</p>
      {status && (
        <div className="cards">
          <div className="card"><span className="card-label">Fon sayısı</span><span className="card-value num">{status.fund_count}</span></div>
          <div className="card"><span className="card-label">Fiyat kaydı</span><span className="card-value num">{status.price_count.toLocaleString('tr-TR')}</span></div>
          <div className="card"><span className="card-label">En son fiyat tarihi</span><span className="card-value">{fmtDate(status.latest_price_date)}</span></div>
          <div className="card">
            <span className="card-label">Sonraki otomatik güncelleme</span>
            <span className="card-value">{status.next_update ? fmtDate(status.next_update) : 'Kapalı'}</span>
            {last && <span className="muted">Son çalışma: {last.status}, {last.new_prices} yeni fiyat</span>}
          </div>
        </div>
      )}
    </section>
  )
}
