import { useEffect, useState } from 'react'
import { getCorrelation } from '../api/client'
import { num, simPct } from '../format'
import CorrelationHeatmap from './CorrelationHeatmap'

const fmt1 = (v) => num(v, 1)

// Ağırlıklarla ulaşılabilecek en yüksek etkin fon sayısı (fonlar tamamen bağımsız olsaydı): 1 / Σw²
function maxEff(ok, codes, weights) {
  if (!weights) return ok.length
  const w = ok.map((c) => weights[codes.indexOf(c)] ?? 0)
  const s = w.reduce((a, b) => a + b, 0)
  return s > 0 ? 1 / w.reduce((a, b) => a + (b / s) ** 2, 0) : ok.length
}

function PairWarning({ pair }) {
  return (
    <li>
      <strong className="num">{pair.a}</strong> ve <strong className="num">{pair.b}</strong> büyük ölçüde aynı hareket ediyor
      (benzerlik {simPct(pair.corr)}).{' '}
      {pair.low_vol
        ? 'İkisi de düşük oynaklıklı (para piyasası benzeri); birlikte tutmak çeşitlendirme sağlamaz ama risk zaten düşük.'
        : 'İkisini birlikte tutmak riski azaltmaz.'}
    </li>
  )
}

// Seçilen fonlar için çeşitlendirme uyarısı (korelasyonu %90 ve üstü çiftler), isteğe bağlı skor ve ısı haritası.
// GET /api/correlation (anlık hesaplanır). weights verilirse skor ağırlıklı hesaplanır.
export default function DiversificationCheck({ codes, weights = null, showScore = false, showHeatmap = false, title = 'Çeşitlendirme' }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(false)
  const key = codes.join(',') + '|' + (weights ? weights.map((w) => w.toFixed(4)).join(',') : '')

  useEffect(() => {
    if (codes.length < 2) return undefined
    let ignore = false
    setError(false)
    const t = setTimeout(() => {  // ağırlık girilirken her tuşta istek atılmasın
      getCorrelation(codes, weights).then((d) => { if (!ignore) setData(d) }).catch(() => { if (!ignore) setError(true) })
    }, 300)
    return () => { ignore = true; clearTimeout(t) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  if (codes.length < 2) return null
  if (error) return <p className="muted small">Çeşitlendirme kontrolü yüklenemedi.</p>
  if (!data) return <p className="muted small">Çeşitlendirme kontrol ediliyor...</p>

  const enough = data.ok.length >= 2
  const maxN = maxEff(data.ok, codes, weights)
  return (
    <div className="divers" aria-live="polite">
      <h3>{title}</h3>
      {showHeatmap && enough && (
        <CorrelationHeatmap codes={data.ok} matrix={data.matrix} caption="Seçilen fonlar arası korelasyon (haftalık getiri, son 1 yıl)" />
      )}
      {data.pairs.length > 0 ? (
        <ul className="divers-warn" role="note">
          {data.pairs.map((p) => <PairWarning key={`${p.a}-${p.b}`} pair={p} />)}
        </ul>
      ) : enough ? (
        <p className="small">Bu fonların hiçbir ikisi arasında %{Math.round(data.threshold * 100)} ve üstü benzerlik yok.</p>
      ) : null}
      {showScore && enough && data.n_eff != null && (
        <div className="divers-score">
          <div>
            <span className="divers-big num">{fmt1(data.n_eff)}</span>
            <span className="muted small"> / en fazla {fmt1(maxN)}</span>
          </div>
          <p className="small">
            <strong>Etkin bağımsız fon sayısı.</strong> Bu dağılım, birbirinden bağımsız hareket eden yaklaşık {fmt1(data.n_eff)} fona
            denk. Fonlar tamamen bağımsız olsaydı {fmt1(maxN)} olurdu; 1'e yaklaştıkça fonlar aynı yönde hareket ediyor, yani
            çeşitlendirme azalıyor. Ağırlıklar hesaba katılır. Fonlar arası ortalama korelasyon {data.mean_corr == null ? '–' : num(data.mean_corr)}.
          </p>
        </div>
      )}
      {data.missing.length > 0 && (
        <p className="muted small">
          Hesaba girmeyen: {data.missing.map((m) => `${m.code} (${m.reason})`).join(', ')}. Korelasyon için en az 1 yıllık güncel fiyat gerekir.
        </p>
      )}
      <p className="muted small">{data.note}</p>
    </div>
  )
}
