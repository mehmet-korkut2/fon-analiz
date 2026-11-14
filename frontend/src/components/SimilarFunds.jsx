import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getSimilar } from '../api/client'
import { pct, signClass, simPct, trDate } from '../format'

// Fon detayı: en çok benzeyen 5 fon ve fonun kümesi. GET /api/funds/{kod}/similar (ayda bir hesaplanır)
export default function SimilarFunds({ code }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let ignore = false
    setData(null)
    setError(false)
    getSimilar(code).then((d) => { if (!ignore) setData(d) }).catch(() => { if (!ignore) setError(true) })
    return () => { ignore = true }
  }, [code])

  return (
    <section aria-labelledby="similar-title" className="similar">
      <h2 id="similar-title">Bu fona en çok benzeyen 5 fon</h2>
      {error && <p className="muted small">Benzer fonlar yüklenemedi.</p>}
      {!error && !data && <p className="muted small">Yükleniyor...</p>}
      {data && !data.available && <p className="muted small">{data.reason}</p>}
      {data?.available && (
        <>
          {data.cluster && (
            <p className="cluster-line">
              Grubu: <strong>{data.cluster.name}</strong>{' '}
              <span className="muted small">
                ({data.cluster.size} fon
                {data.cluster.diffuse
                  ? '; bu gruptaki fonlar birbirine pek benzemez, ortak noktaları başka bir gruba uymamaları'
                  : `; grubun temsilcisi ${data.cluster.representative}`})
              </span>
            </p>
          )}
          <div className="table-wrap">
            <table className="similar-table">
              <thead>
                <tr><th>Fon</th><th className="r">Benzerlik</th><th className="r">1 yıl getiri</th><th><span className="sr-only">İşlem</span></th></tr>
              </thead>
              <tbody>
                {data.neighbors.map((n) => (
                  <tr key={n.code}>
                    <td>
                      <Link to={`/fonlar/${n.code}`} className="num"><strong>{n.code}</strong></Link>{' '}
                      <span className="small">{n.name}</span> <span className="muted small">{n.category}</span>
                    </td>
                    <td className="r num">
                      <span className="sim-bar" aria-hidden="true"><span style={{ width: `${Math.max(n.corr, 0) * 100}%` }} /></span>
                      {simPct(n.corr)}
                    </td>
                    <td className={`r num ${signClass(n.ret_1y)}`}>{pct(n.ret_1y)}</td>
                    <td className="r">
                      <Link className="btn btn-sm" to={`/karsilastir?fonlar=${code},${n.code}`}>Karşılaştır</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small">
            {data.note} %100 tamamen aynı yönde demektir; %90 ve üstü benzerlikteki iki fonu birlikte tutmak riski pek azaltmaz.
            Gruplar ve benzerlikler ayda bir yeniden hesaplanır (son hesap {trDate(data.as_of)} tarihli fiyatlarla).
          </p>
        </>
      )}
    </section>
  )
}
