import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getMlPerformance } from '../api/client'
import { num, trDate } from '../format'

const GRID = '#e5ebe8'
const INK_MUTED = '#5d6b65'
// Renk modele bağlı (kategorik palet, renk körlüğü kontrolünden geçti)
const COLORS = { lightgbm: '#2a78d6', drift: '#eb6834', momentum: '#1baf7a', sifir: '#eda100' }
const SHORT = { lightgbm: 'LightGBM', drift: 'Drift', momentum: 'Momentum', sifir: 'Sıfır', lightgbm_sira: 'LightGBM sıra (keşif)', arima: 'ARIMA' }
const GROUPS = { '1-2': 'Risk 1–2', '3-4': 'Risk 3–4', '5-7': 'Risk 5–7', bilinmiyor: 'Risk değeri yok' }

// Hata, oran ve kapsam işaretsiz; getiriler işaretli. Hata farkları küçük olduğu için 2 ondalık.
const p = (v, d = 2) => (v == null ? '–' : `${v < 0 ? '-' : ''}${num(Math.abs(v) * 100, d)}%`) // sitenin geri kalanı gibi: 3,65%
const sp = (v, d = 2) => (v == null ? '–' : `${v > 0 ? '+' : ''}${p(v, d)}`)

const COLS = [
  ['mae_excess', 'Fazla getiri MAE', (v) => p(v)],
  ['rmse_excess', 'Fazla getiri RMSE', (v) => p(v)],
  ['dir_excess', 'PP üstü/altı yönü', (v) => p(v, 1)],
  ['dir_raw', 'Ham yön', (v, r) => (r.model === 'sifir' ? '–' : p(v, 1))],
  ['ic', 'Sıralama korelasyonu', (v) => num(v, 3)],
  ['top10', 'İlk 10 (aylık)', (v) => sp(v)],
  ['coverage', '%80 aralık kapsamı', (v) => p(v, 1)],
]

function MetricTable({ rows, best = 'mae_excess' }) {
  const cols = COLS.filter(([k]) => rows.some((r) => r[k] != null))
  const bestVal = Math.min(...rows.map((r) => r[best]).filter((v) => v != null))
  return (
    <div className="table-wrap">
      <table className="ml-table">
        <thead>
          <tr><th>Model</th>{cols.map(([k, label]) => <th key={k} className="r">{label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.model}>
              <th scope="row">
                {COLORS[r.model] && <span className="swatch" style={{ background: COLORS[r.model] }} />} {r.label}
              </th>
              {cols.map(([k, , fmt]) => (
                <td key={k} className={`r num${k === best && r[k] === bestVal ? ' best' : ''}`}>{fmt(r[k], r)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function MonthlyChart({ monthly }) {
  const models = ['lightgbm', 'drift', 'momentum', 'sifir']
  const data = useMemo(() => {
    const by = {}
    for (const r of monthly) {
      by[r.date] = by[r.date] || { date: r.date }
      by[r.date][r.model] = r.mae_excess
    }
    return Object.values(by).sort((a, b) => a.date.localeCompare(b.date))
  }, [monthly])
  return (
    <>
      <div className="legend">
        {models.map((m) => (
          <span key={m} className="legend-item"><span className="legend-line" style={{ background: COLORS[m] }} /><strong>{SHORT[m]}</strong></span>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="date" tickFormatter={(d) => trDate(d, { month: 'short', year: '2-digit' })} minTickGap={24}
            tickLine={false} axisLine={{ stroke: GRID }} tick={{ fontSize: 12, fill: INK_MUTED }} />
          <YAxis width={44} orientation="right" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: INK_MUTED }}
            tickFormatter={(v) => `${num(v * 100, 0)}%`} />
          <Tooltip
            formatter={(v, name) => [p(v), SHORT[name]]}
            labelFormatter={(d) => trDate(d, { month: 'long', year: 'numeric' })}
            contentStyle={{ borderRadius: 8, borderColor: '#dde4e1', fontSize: 13 }}
          />
          {models.map((m) => (
            <Line key={m} type="linear" dataKey={m} stroke={COLORS[m]} strokeWidth={2} dot={false} isAnimationActive={false}
              activeDot={{ r: 4, stroke: '#fff', strokeWidth: 2 }} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </>
  )
}

export default function ModelPerformance() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => { document.title = 'Model Performansı · Fon Analiz' }, [])
  useEffect(() => {
    getMlPerformance().then(setData).catch((e) => setError(e.response?.status === 404
      ? 'Model değerlendirmesi henüz yapılmadı. Gece güncellemesinden sonra burada görünecek.'
      : 'Model performansı yüklenemedi. Backend çalışıyor mu?'))
  }, [])

  if (error) return <section className="mlp"><h1>Model performansı</h1><p className="muted">{error}</p></section>
  if (!data) return <section className="mlp"><p className="muted">Yükleniyor...</p></section>
  const r = data.report
  const c = r.calendar
  const anySuccess = r.verdicts.some((v) => v.success)
  const monthly = r.monthly
  const mmTop = r.importance.slice(0, 2).every((x) => x.feature.startsWith('mm_'))

  return (
    <section className="mlp">
      <div>
        <h1>Model performansı</h1>
        <p className="hint">
          Gelecek 1 aylık ({r.horizon} işlem günü) fon getirisi tahmini · {c.test[2]} test ayı ({trDate(c.test[0])} – {trDate(c.test[1])}),
          {' '}{c.test_samples.toLocaleString('tr-TR')} tahmin · Rapor: {data.created_at}
        </p>
      </div>

      <div className={`verdict ${anySuccess ? 'ok' : 'fail'}`}>
        <strong>{anySuccess ? 'LightGBM bazı risk gruplarında referansı geçti.' : 'LightGBM hiçbir risk grubunda basit referansı geçemedi.'}</strong>{' '}
        Bu yüzden fon sayfalarında ML tahmini değil, testlerde en isabetli çıkan <strong>geçmiş eğilime dayalı tahmin</strong> (drift:
        fonun son 1 yıllık ortalama getirisinin sürmesi) ve konformal %80 aralık gösteriliyor.
      </div>

      <div className="panel">
        <h2>Nasıl test edildi?</h2>
        <ul className="small method-list">
          <li><strong>Hedef:</strong> fiyat değil, gelecek {r.horizon} işlem gününün getirisi. Fiyat seviyeleri fonlar arasında karşılaştırılamaz; "yarın da bugünkü fiyat" demek bile fiyatta %99 isabet gibi görünür.</li>
          <li><strong>Walk-forward:</strong> her ayın ilk işlem günü model, sadece o güne kadar <em>gerçekleşmiş</em> örneklerle yeniden eğitildi ve o günkü fonlar için tahmin yaptı. Gelecekten bilgi sızmaz.</li>
          <li><strong>Ayar ve test ayrı:</strong> LightGBM ayarları {trDate(c.valid[0])} – {trDate(c.valid[1])} döneminde seçildi; test dönemine ayar sırasında bakılmadı.</li>
          <li><strong>Başarı ölçütü (önceden belirlendi):</strong> bir risk grubunda o grubun en iyi referansına göre hem daha düşük fazla getiri hatası hem daha yüksek "ilk 10" getirisi.</li>
          <li><strong>Fazla getiri:</strong> fon getirisi eksi para piyasası (PP) fonlarının medyanı. Getirilerin %75'ten fazlası pozitif olduğu için ham yön doğruluğu yanıltıcıdır; asıl yön ölçütü PP'nin üstünde mi altında mı kalacağı.</li>
        </ul>
      </div>

      <h2>Genel sonuçlar</h2>
      <MetricTable rows={r.overall} />
      <p className="muted small">
        Aynı aylarda tüm fonların ortalama aylık getirisi {sp(r.benchmarks.universe)}, PP medyanı {sp(r.benchmarks.mm)}. Vurgulu hücre: en düşük fazla getiri hatası.
      </p>

      <h2>Risk grubuna göre başarı ölçütü</h2>
      <div className="table-wrap">
        <table className="ml-table">
          <thead>
            <tr>
              <th>Risk grubu</th><th className="r">LightGBM hata</th><th className="r">Referans hata</th>
              <th className="r">LightGBM ilk 10</th><th className="r">Referans ilk 10</th><th className="r">Daha iyi olduğu ay</th><th>Sonuç</th>
            </tr>
          </thead>
          <tbody>
            {r.verdicts.map((v) => (
              <tr key={v.group}>
                <th scope="row">{GROUPS[v.group]} <span className="muted small">({v.reference_label.split(' (')[0]})</span></th>
                <td className="r num">{p(v.model_mae_excess)}</td>
                <td className="r num">{p(v.reference_mae_excess)}</td>
                <td className="r num">{sp(v.model_top10)}</td>
                <td className="r num">{sp(v.reference_top10)}</td>
                <td className="r num">{v.wins} / {v.months}</td>
                <td>{v.success ? <span className="badge-ok">Başarılı</span> : <span className="badge-fail">Başarısız</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>Ay ay tahmin hatası</h2>
      <div className="panel">
        <p className="muted small">Fazla getiri MAE'si (düşük olan iyi). Her nokta, o ayın başında yapılan tahminlerin ortalama mutlak hatası.</p>
        <MonthlyChart monthly={monthly} />
        <details className="price-table">
          <summary>Tablo olarak göster</summary>
          <div className="table-wrap">
            <table className="ml-table">
              <thead><tr><th>Ay</th>{['lightgbm', 'drift', 'momentum', 'sifir'].map((m) => <th key={m} className="r">{SHORT[m]}</th>)}<th className="r">Tüm fonlar</th><th className="r">PP medyanı</th></tr></thead>
              <tbody>
                {[...new Set(monthly.map((x) => x.date))].sort().map((d) => {
                  const row = Object.fromEntries(monthly.filter((x) => x.date === d).map((x) => [x.model, x]))
                  const any = Object.values(row)[0]
                  return (
                    <tr key={d}>
                      <td className="num">{trDate(d, { month: 'short', year: 'numeric' })}</td>
                      {['lightgbm', 'drift', 'momentum', 'sifir'].map((m) => <td key={m} className="r num">{p(row[m]?.mae_excess)}</td>)}
                      <td className="r num">{sp(any.universe)}</td><td className="r num">{sp(any.mm)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </details>
      </div>

      <h2>Sitede gösterilen tahminin aralığı</h2>
      <div className="table-wrap">
        <table className="ml-table">
          <thead><tr><th>Risk grubu</th><th className="r">Alt uç (hata %10)</th><th className="r">Üst uç (hata %90)</th><th className="r">Test dönemi kapsamı</th></tr></thead>
          <tbody>
            {Object.entries(r.drift_interval).map(([g, v]) => (
              <tr key={g}><th scope="row">{GROUPS[g]}</th><td className="r num">{sp(v.q10)}</td><td className="r num">{sp(v.q90)}</td><td className="r num">{p(v.coverage, 1)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">Aralık, drift tahmininin geçmiş hatalarından (risk grubuna göre) kurulur. Kapsam: test döneminde, her ay sadece o güne kadarki hatalarla kurulan aralığın gerçekleşmeyi içerme oranı; hedef %80.</p>

      <h2>Risk grubu ayrıntıları</h2>
      {Object.entries(r.groups).map(([g, rows]) => (
        <details key={g} className="price-table">
          <summary>{GROUPS[g]} ({rows[0].n.toLocaleString('tr-TR')} tahmin)</summary>
          <MetricTable rows={rows} />
        </details>
      ))}

      <h2>LightGBM neye bakıyor?</h2>
      <div className="panel">
        <ul className="importance">
          {r.importance.map((x) => (
            <li key={x.feature}>
              <span className="small num">{x.feature}</span>
              <span className="imp-track"><span style={{ width: `${(x.share / r.importance[0].share) * 100}%` }} /></span>
              <span className="small num">{p(x.share, 1)}</span>
            </li>
          ))}
        </ul>
        <p className="muted small">
          Kazanç payı (son test ayında eğitilen model).
          {mmTop && (
            <>
              {' '}En önemli iki özellik para piyasası getirileri; bunlar aynı ay içinde bütün fonlar için aynıdır. Model fonları
              birbirinden ayırt etmekten çok &quot;bu ay fonlar PP&apos;yi ne kadar geçer&quot; sorusunu öğrenmeye çalıştı; sıralama
              korelasyonunun düşük olmasının nedeni bu.
            </>
          )}
        </p>
      </div>

      {r.arima && (
        <>
          <h2>ARIMA ({r.arima.funds} fonluk örnek)</h2>
          <MetricTable rows={r.arima.rows} />
          <p className="muted small">
            Fon bazında, günlük getiriler üzerinde; mertebe her fon için ilk test ayından önce bir kez seçildi. Seçilen mertebeler:{' '}
            {Object.entries(r.arima.orders).map(([k, v]) => `${k} ${v} fon`).join(', ')}.
            {r.arima_as_of && ` ARIMA sonucu ${trDate(r.arima_as_of)} tarihli değerlendirmeden.`}
          </p>
        </>
      )}

      {r.exploration && (
        <>
          <h2>Keşif: ay içi sıra hedefi</h2>
          <div className="notice small">
            <strong>Keşif amaçlı, test sonuçları görüldükten sonra tanımlandı.</strong> Hedef, fonun aynı ay içindeki göreli sırası; ay
            içinde bütün fonlar için aynı olan özellikler çıkarıldı. Sonuç ne olursa olsun sitedeki karar değişmez.
          </div>
          <MetricTable rows={r.exploration.overall} best="ic" />
          <p className="muted small">Vurgulu hücre: en yüksek sıralama korelasyonu.</p>
        </>
      )}

      <div className="panel">
        <h2>Sınırlamalar</h2>
        <ul className="small method-list">
          <li>Test dönemi ~2 yıl ve tek bir yüksek faiz ortamı; sonuçlar başka piyasa koşullarına genellenemez.</li>
          <li>Fonların kategori ve risk değeri için sadece bugünkü değerler biliniyor.</li>
          <li>Eylül 2026'da SPK kararıyla kapatılan fonların sert düşüşleri test dönemine dahildir (seçim günü bilinemezdi).</li>
        </ul>
        <p className="small">Yöntemin ayrıntıları: <Link to="/oneriler">öneri sistemi</Link> ve proje belgeleri (docs/ml_tahmin.md).</p>
      </div>
    </section>
  )
}
