import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getClusters } from '../api/client'
import { num, pct, trDate } from '../format'
import { C, SERIES } from '../theme'

const n2 = (v) => (v == null ? '–' : num(v))
const p0 = (v) => (v == null ? '–' : `%${num(v * 100, 1)}`)

// Model performansı sayfası: kümeleme bölümü. GET /api/clusters (ayda bir hesaplanır)
export default function ClusteringReport() {
  const [data, setData] = useState(null)
  const [missing, setMissing] = useState(false)

  useEffect(() => {
    let ignore = false
    getClusters().then((d) => { if (!ignore) setData(d) }).catch(() => { if (!ignore) setMissing(true) })
    return () => { ignore = true }
  }, [])

  if (missing) {
    return (
      <div className="panel" id="kumeleme">
        <h2>Kümeleme: benzer fonlar</h2>
        <p className="muted small">Kümeleme henüz hesaplanmadı. Gece güncellemesinden sonra burada görünecek.</p>
      </div>
    )
  }
  if (!data) return null
  const r = data.report
  const st = r.stability
  const me = r.monday_effect
  return (
    <>
      <h2 id="kumeleme">Kümeleme: benzer fonlar</h2>
      <div className="verdict ok">
        <strong>Tahmin modelinin aksine bu kısım işe yarıyor.</strong>{' '}
        {st ? (
          <>
            Fonların birbiriyle ne kadar birlikte hareket ettiği yıldan yıla büyük ölçüde korunuyor (fon çiftlerinin korelasyonunda
            iki yıl arası sıra korelasyonu {n2(st.corr_persistence)}); getirinin sırası ise korunmuyor ({n2(st.return_persistence)}
            {st.return_persistence_equity != null && <>; hisse fonlarının kendi içinde {n2(st.return_persistence_equity)}</>}).
            Birlikte hareket, fonun ne tuttuğundan gelir; kümeleme bu yapıyı ölçer, geleceği tahmin etmeye çalışmaz.
          </>
        ) : 'Kümeleme geleceği tahmin etmez; fonların bugüne kadarki birlikte hareketini ölçer.'}
      </div>

      <div className="panel">
        <h3>Nasıl yapıldı?</h3>
        <ul className="small method-list">
          <li><strong>Fonlar:</strong> işleme açık, son fiyatı güncel ve en az 1 yıllık fiyatı olan {r.n_funds.toLocaleString('tr-TR')} fon
            ({trDate(r.window_start)} – {trDate(r.data_as_of)}).</li>
          <li><strong>Benzerlik:</strong> haftalık getirilerin korelasyonu. Günlük getiri kullanılmadı: para piyasası fonlarında hafta sonu faizi
            pazartesi fiyatına yansıdığı için günlük getiriler takvim yüzünden birbirine benzer görünür
            {me && <> (para piyasası fonları arası medyan korelasyon günlükte {n2(me.daily)}, haftalıkta {n2(me.weekly)})</>}.
            Gürültüyü azaltmak için hafta pazartesiden cumaya her gün başlatılıp 5 korelasyonun ortalaması alındı.</li>
          <li><strong>Uzaklık ve yöntem:</strong> d = √(2(1 − ρ)) ve Ward hiyerarşik kümeleme. k-means, k-medoids, tam ve ortalama
            bağlantı da denendi (rapor 6.11); ortalama bağlantı fonların çoğunu tek kümeye topladı.</li>
          <li><strong>Küme sayısı:</strong> 5–20 arasında ortalama silhouette en yüksek olan k = {r.k}.</li>
          <li><strong>Benzer fonlar:</strong> her fon için korelasyonu en yüksek 5 fon (k-NN). Kümeler ve benzerlikler ayda bir yeniden
            hesaplanır (son hesap {trDate(data.created_at)}).</li>
        </ul>
      </div>

      <div className="cards">
        <div className="card metric"><span className="card-label">Küme sayısı</span><span className="card-value num">{r.k}</span>
          <span className="metric-desc">Ortalama silhouette {n2(r.silhouette)} (1'e yakın: kümeler net ayrık).</span></div>
        <div className="card metric"><span className="card-label">Kategorilerle örtüşme (ARI)</span><span className="card-value num">{n2(r.ari_category)}</span>
          <span className="metric-desc">Varlık türünü belirten kategorilerde ({r.homogeneous_categories.join(', ')}) {n2(r.ari_homogeneous)}. 1: aynı gruplama, 0: rastgele.</span></div>
        {st && (
          <>
            <div className="card metric"><span className="card-label">Kararlılık (ARI)</span><span className="card-value num">{n2(st.ari)}</span>
              <span className="metric-desc">Önceki 1 yılın verisiyle aynı yöntemle bulunan kümelerle örtüşme ({st.n_funds} fon).</span></div>
            <div className="card metric"><span className="card-label">Geçen yılın benzerleri bu yıl</span><span className="card-value num">{n2(st.prev_neighbors_corr_now)}</span>
              <span className="metric-desc">Geçen yılın en yakın 5 fonunun bu yılki medyan korelasyonu. Bu yılın en yakın 5'i {n2(st.best_neighbors_corr_now)}, rastgele bir çift {n2(st.random_pair_corr_now)}.</span></div>
          </>
        )}
      </div>

      <h3 className="sub">Küme sayısının seçimi</h3>
      <div className="legend">
        <span className="legend-item"><span className="legend-line" style={{ background: SERIES[0] }} /><strong>Silhouette</strong></span>
        {st && <span className="legend-item"><span className="legend-line" style={{ background: SERIES[1] }} /><strong>Kararlılık (ARI)</strong></span>}
        <span className="legend-item muted small">kesikli çizgi: seçilen k</span>
      </div>
      <div role="img" aria-label={`Silhouette ve kararlılık, k=5..20; seçilen k=${r.k}`}>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={r.silhouette_curve} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis dataKey="k" stroke={C.axis} tick={{ fontSize: 12 }} />
            <YAxis stroke={C.axis} tick={{ fontSize: 12 }} width={44} tickFormatter={(v) => num(v, 1)} />
            <Tooltip formatter={(v) => num(v)} labelFormatter={(k) => `k = ${k}`} contentStyle={{ background: 'var(--surface)', border: '1px solid var(--line)' }} />
            <ReferenceLine x={r.k} stroke={C.neutral} strokeDasharray="4 4" />
            <Line type="monotone" dataKey="silhouette" name="Silhouette" stroke={SERIES[0]} strokeWidth={2} dot={false} isAnimationActive={false} />
            {st && <Line type="monotone" dataKey="stability" name="Kararlılık (ARI)" stroke={SERIES[1]} strokeWidth={2} dot={false} isAnimationActive={false} />}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <h3 className="sub">Kümeler</h3>
      <div className="table-wrap">
        <table className="ml-table cluster-table">
          <thead>
            <tr>
              <th>Küme</th><th className="r">Fon</th><th className="r">İç korelasyon</th><th className="r">Medyan oynaklık</th>
              <th className="r">Medyan 1 yıl getiri</th><th>Temsilci</th><th>Kategoriler</th>
            </tr>
          </thead>
          <tbody>
            {r.clusters.map((c) => (
              <tr key={c.id} className={c.diffuse ? 'muted' : ''}>
                <th scope="row">{c.name}</th>
                <td className="r num">{c.size}</td>
                <td className="r num">{n2(c.internal_corr)}</td>
                <td className="r num">{p0(c.median_vol)}</td>
                <td className="r num">{pct(c.median_ret_1y)}</td>
                <td><Link to={`/fonlar/${c.representative}`} className="num">{c.representative}</Link></td>
                <td className="small">{c.categories.map((x) => `${x.category} ${x.n}`).join(' · ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        Örtüşmenin bütün fonlarda düşük olması kümelemenin hatası değil: "Serbest", "Değişken", "Fon Sepeti" ve "Katılım" kategorileri
        fonun neye yatırım yaptığını söylemez; örneğin altın katılım fonları altın kümesine, döviz serbest fonları dolar ve avro kümelerine düşer.
        Temsilci, kümedeki diğer fonlara toplam uzaklığı en küçük fondur.
      </p>

      <div className="panel">
        <h3>Sınırlamalar</h3>
        <ul className="small method-list">
          <li>Ortalama silhouette {n2(r.silhouette)}: yapı zayıf-orta. Altın, döviz, para piyasası ve tahvil kümeleri sıkı; mutlak getiri,
            arbitraj ve karma fonlar hiçbir kümeye tam uymuyor ("belirgin bir gruba girmeyen fonlar").</li>
          <li>Korelasyon yalnızca yönü ölçer, büyüklüğü ölçmez: aynı yönde hareket eden iki fondan biri diğerinin iki katı oynak olabilir.</li>
          <li>Geçmişteki birlikte hareket gelecekte sürmeyebilir; geçen yıl %{Math.round(r.threshold * 100)} üstündeki çiftlerin
            {st?.high_pairs_still_08 != null ? ` %${Math.round(st.high_pairs_still_08 * 100)}'i` : ' çoğu'} bu yıl 0,80'in üstünde kaldı.</li>
          <li>Öneri puanlaması kümeleri kullanmaz; çeşitlendirme uyarısı yalnızca bilgi verir.</li>
        </ul>
      </div>
    </>
  )
}
