import { useEffect, useState } from 'react'
import { getFunds } from '../api/client'

export default function Funds() {
  const [funds, setFunds] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    getFunds().then(setFunds).catch(() => setError('Fonlar yüklenemedi.'))
  }, [])

  if (error) return <p>{error}</p>

  return (
    <section>
      <h1>Fonlar</h1>
      <p className="hint">Şimdilik örnek veri. TEFAS bağlantısı 2. aşamada eklenecek.</p>
      <table>
        <thead>
          <tr><th>Kod</th><th>Ad</th><th>Kategori</th><th>Fiyat</th></tr>
        </thead>
        <tbody>
          {funds.map((f) => (
            <tr key={f.code}>
              <td>{f.code}</td><td>{f.name}</td><td>{f.category}</td>
              <td>{f.price.toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
