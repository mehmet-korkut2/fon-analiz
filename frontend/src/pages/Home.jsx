import { useEffect, useState } from 'react'
import { getHealth } from '../api/client'

export default function Home() {
  const [status, setStatus] = useState('kontrol ediliyor...')

  useEffect(() => {
    getHealth()
      .then((d) => setStatus(d.status === 'ok' ? 'Backend bağlı ✓' : 'Beklenmeyen yanıt'))
      .catch(() => setStatus('Backend\'e ulaşılamadı. FastAPI çalışıyor mu?'))
  }, [])

  return (
    <section>
      <h1>Fon Analiz Platformu</h1>
      <p>Yatırım fonlarını incele, karşılaştır ve risk profiline uygun fonları bul.</p>
      <p className="status">Durum: {status}</p>
    </section>
  )
}
