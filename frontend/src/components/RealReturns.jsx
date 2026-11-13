import { useEffect, useState } from 'react'
import { getFundReal } from '../api/client'
import { monthLabel, pct, signClass, trDate } from '../format'

// Fon detayı: enflasyona göre reel getiri. GET /api/funds/{kod}/real
// Dönem sonu açıklanmış son TÜFE ayının son günü; etiket yalnızca renge değil, metne ve işarete dayanır.

function Beat({ p }) {
  if (p.beat == null) return <span className="muted">–</span>
  return p.beat
    ? <span className="beat-yes">✓ Enflasyonu yendi</span>
    : <span className="beat-no">✗ Yenemedi</span>
}

export default function RealReturns({ code }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let ignore = false
    setData(null)
    setError(null)
    getFundReal(code)
      .then((d) => { if (!ignore) setData(d) })
      .catch(() => { if (!ignore) setError('Reel getiri yüklenemedi.') })
    return () => { ignore = true }
  }, [code])

  if (error) return <div className="panel real-panel"><h2>Enflasyona göre reel getiri</h2><p className="muted small">{error}</p></div>
  if (!data) return null
  if (!data.available) {
    return (
      <div className="panel real-panel">
        <h2>Enflasyona göre reel getiri</h2>
        <p className="muted small">{data.message} TÜFE verisi TCMB EVDS'ten alınır; API anahtarı tanımlı değilse ya da henüz yüklenmediyse bu bölüm boş kalır.</p>
      </div>
    )
  }
  return (
    <div className="panel real-panel">
      <div>
        <h2>Enflasyona göre reel getiri</h2>
        <p className="muted small">
          {monthLabel(data.last_month)} sonuna kadar (açıklanmış son TÜFE ayı; dönem sonu {trDate(data.end)}).
          Reel getiri = (1 + getiri) / (1 + enflasyon) − 1.
        </p>
      </div>
      <div className="table-wrap">
        <table className="ml-table real-table">
          <thead>
            <tr><th>Dönem</th><th className="r">Getiri</th><th className="r">Enflasyon (TÜFE)</th><th className="r">Reel getiri</th><th>Sonuç</th></tr>
          </thead>
          <tbody>
            {data.periods.map((p) => (
              <tr key={p.months}>
                <th scope="row">{p.label} <span className="muted small">({trDate(p.start)} – {trDate(p.end)})</span></th>
                <td className={`r num ${signClass(p.nominal)}`}>{pct(p.nominal)}</td>
                <td className="r num">{pct(p.inflation)}</td>
                <td className={`r num ${signClass(p.real)}`}><strong>{pct(p.real)}</strong></td>
                <td><Beat p={p} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        Boş dönem: fonun o tarihte fiyatı yok ya da TÜFE ayı eksik. TÜFE aylık ortalama fiyat düzeyidir, fon fiyatı ay sonu
        değeridir (yaklaşık bir karşılaştırma). {data.source_note} Geçmiş performans gelecekteki sonuçların göstergesi değildir.
      </p>
    </div>
  )
}
