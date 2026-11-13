import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getMlPerformance } from '../api/client'
import { num, trDate } from '../format'
import { C, SERIES } from '../theme'

const GRID = C.grid
const INK_MUTED = C.axis
// Renk modele bağlı (kategorik palet, renk körlüğü kontrolünden geçti)
const COLORS = { lightgbm: SERIES[0], drift: SERIES[1], momentum: SERIES[2], sifir: SERIES[3] }
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
            contentStyle={{ borderRadius: 8, borderColor: 'var(--line)', background: 'var(--surface)', color: 'var(--ink)', fontSize: 13 }}
          />
          {models.map((m) => (
            <Line key={m} type="linear" dataKey={m} stroke={COLORS[m]} strokeWidth={2} dot={false} isAnimationActive={false}
              activeDot={{ r: 4, stroke: C.surface, strokeWidth: 2 }} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </>
  )
}

// --- Ufka göre tahmin karnesi (report.horizons: test dönemi, her işlem günü başlangıç) ---------------
const KEY_H = [1, 2, 5, 10, 21]
const H_LABEL = { 1: '1 gün', 2: '2 gün', 5: '1 hafta', 10: '2 hafta', 21: '1 ay' }
const GROUP_ORDER = ['1-2', '3-4', '5-7', 'bilinmiyor']
const GROUP_COLORS = { '1-2': SERIES[0], '3-4': SERIES[1], '5-7': SERIES[2], bilinmiyor: SERIES[3] }
const SRC = { canli: 'Canlı', geriye_donuk: 'Geriye dönük' }

function HorizonTable({ rows }) {
  const get = (h, g) => rows.find((r) => r.horizon === h && r.group === g)
  return (
    <div className="table-wrap">
      <table className="ml-table">
        <thead>
          <tr>
            <th rowSpan={2}>Risk grubu</th>
            {KEY_H.map((h) => <th key={h} colSpan={2} className="c">{H_LABEL[h]}</th>)}
          </tr>
          <tr>{KEY_H.map((h) => [<th key={`${h}c`} className="r">Kapsama</th>, <th key={`${h}m`} className="r">Ort. sapma</th>])}</tr>
        </thead>
        <tbody>
          {[...GROUP_ORDER, 'tumu'].map((g) => (
            <tr key={g}>
              <th scope="row">{g === 'tumu' ? <strong>Tümü</strong> : <><span className="swatch" style={{ background: GROUP_COLORS[g] }} /> {GROUPS[g]}</>}</th>
              {KEY_H.map((h) => {
                const r = get(h, g)
                return [<td key={`${h}c`} className="r num">{p(r?.coverage, 1)}</td>, <td key={`${h}m`} className="r num">{p(r?.mae_pct)}</td>]
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function HorizonChart({ rows }) {
  const data = useMemo(() => Array.from({ length: 21 }, (_, i) => {
    const h = i + 1
    const o = { h }
    for (const g of GROUP_ORDER) o[g] = rows.find((r) => r.horizon === h && r.group === g)?.mae_pct
    return o
  }), [rows])
  return (
    <>
      <div className="legend">
        {GROUP_ORDER.map((g) => (
          <span key={g} className="legend-item"><span className="legend-line" style={{ background: GROUP_COLORS[g] }} /><strong>{GROUPS[g]}</strong></span>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 16, left: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="h" type="number" domain={[1, 21]} ticks={KEY_H} interval={0} padding={{ left: 10, right: 10 }} tickLine={false} axisLine={{ stroke: GRID }} tick={{ fontSize: 12, fill: INK_MUTED }}
            label={{ value: 'Ufuk (işlem günü)', position: 'insideBottom', offset: -10, fontSize: 12, fill: INK_MUTED }} />
          <YAxis width={44} orientation="right" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: INK_MUTED }}
            tickFormatter={(v) => `${num(v * 100, 1)}%`} />
          <Tooltip
            formatter={(v, g) => [p(v), GROUPS[g]]}
            labelFormatter={(h) => `${h}. işlem günü${H_LABEL[h] ? ` (${H_LABEL[h]})` : ''}`}
            contentStyle={{ borderRadius: 8, borderColor: 'var(--line)', background: 'var(--surface)', color: 'var(--ink)', fontSize: 13 }}
          />
          {GROUP_ORDER.map((g) => (
            <Line key={g} type="linear" dataKey={g} stroke={GROUP_COLORS[g]} strokeWidth={2} dot={false} isAnimationActive={false}
              activeDot={{ r: 4, stroke: C.surface, strokeWidth: 2 }} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </>
  )
}

function LiveScorecard({ sc }) {
  const rows = sc.rows.filter((r) => r.risk_group === 'tumu' && KEY_H.includes(r.horizon))
  // sütun grubu: kaynak + yöntem sürümü (sürümler ayrı sayılır)
  const sources = [...new Set(rows.map((r) => `${r.source}|${r.method_version}`))]
    .sort((a, b) => (a.startsWith('canli') ? 0 : 1) - (b.startsWith('canli') ? 0 : 1) || b.localeCompare(a))
  const label = (g) => { const [s, v] = g.split('|'); return `${SRC[s]} · ${v}` }
  return (
    <>
      <div className="table-wrap">
        <table className="ml-table score-summary">
          <thead>
            <tr><th rowSpan={2}>Ufuk</th>{sources.map((s) => <th key={s} colSpan={3} className="c">{label(s)}</th>)}</tr>
            <tr>{sources.map((s) => [<th key={`${s}c`} className="r">Aralıkta kalma</th>, <th key={`${s}m`} className="r">Ort. mutlak sapma</th>, <th key={`${s}n`} className="r">Tahmin</th>])}</tr>
          </thead>
          <tbody>
            {KEY_H.map((h) => (
              <tr key={h}>
                <th scope="row">{H_LABEL[h]}</th>
                {sources.map((s) => {
                  const r = rows.find((x) => `${x.source}|${x.method_version}` === s && x.horizon === h)
                  return [<td key={`${s}c`} className="r num">{p(r?.coverage, 1)}</td>, <td key={`${s}m`} className="r num">{p(r?.mae_pct)}</td>,
                    <td key={`${s}n`} className="r num">{r ? r.n.toLocaleString('tr-TR') : 0}</td>]
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        {['canli', 'geriye_donuk'].map((s) => {
          const c = sc.counts[s]
          return c ? `${SRC[s]}: ${c.days} tahmin günü, ${c.records.toLocaleString('tr-TR')} kayıt, ${c.realized.toLocaleString('tr-TR')} gerçekleşti` : null
        }).filter(Boolean).join(' · ')}. Veri tarihi {trDate(sc.data_as_of)}. Aynı günün tahminleri birbirine bağlıdır
        (bütün fonlar aynı piyasa hareketini yaşar); az sayıda tahmin gününe dayanan yüzdeler dalgalı olabilir.
      </p>
      {sc.versions && (
        <ul className="small method-list">
          {Object.entries(sc.versions).map(([v, d]) => <li key={v}><strong>{v}:</strong> {d}</li>)}
        </ul>
      )}
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

      {r.horizons?.rows && (
        <>
          <h2>Ufka göre tahmin karnesi</h2>
          <div className="panel">
            <p className="small">
              Sitede gösterilen tahmin (drift) her fon için 1'den 21'e kadar her işlem günü ufkunda ayrı yapılır; %80 aralık da her ufuk ve
              risk grubu için ayrı kurulur (yalnızca o güne kadar gerçekleşmiş hatalarla). Aşağıda test dönemindeki
              ({trDate(r.horizons.test[0])} – {trDate(r.horizons.test[1])}, {r.horizons.origins} işlem günü) her gün başlatılan tahminlerin sonuçları var.
              Kapsama: gerçekleşen fiyatın %80 aralığın içinde kalma oranı (hedef %80). Ort. sapma: |gerçekleşen − tahmin| / tahmin.
            </p>
            <HorizonTable rows={r.horizons.rows} />
            <h3 className="sub">Ufuk uzadıkça hata nasıl büyüyor?</h3>
            <p className="muted small">Ortalama mutlak sapma, risk grubuna göre. Hata kabaca ufkun karekökü ile büyür; riskli fonlarda çok daha hızlı.</p>
            <HorizonChart rows={r.horizons.rows} />
            <details className="price-table">
              <summary>Bütün ufuklar (tablo)</summary>
              <div className="table-wrap">
                <table className="ml-table">
                  <thead><tr><th>Ufuk</th><th>Risk grubu</th><th className="r">Tahmin</th><th className="r">Kapsama</th><th className="r">Ort. sapma</th><th className="r">Ort. yanlılık</th><th className="r">Aralık genişliği</th></tr></thead>
                  <tbody>
                    {r.horizons.rows.map((x) => (
                      <tr key={`${x.horizon}-${x.group}`}>
                        <td className="num">{x.horizon}</td><td>{x.group === 'tumu' ? 'Tümü' : GROUPS[x.group]}</td>
                        <td className="r num">{x.n.toLocaleString('tr-TR')}</td><td className="r num">{p(x.coverage, 1)}</td>
                        <td className="r num">{p(x.mae_pct)}</td><td className="r num">{sp(x.bias_pct)}</td><td className="r num">{p(x.width_pct)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
            <p className="muted small">
              Hız için değerlendirmede aralık ayda bir (ayın ilk işlem günü) yeniden kurulur; sitedeki canlı tahminde her gece kurulur.
              Ardışık günlerin tahminleri örtüşür; tahmin sayısı bağımsız gözlem sayısı değildir.
            </p>
          </div>
        </>
      )}

      {data.scorecard && (
        <>
          <h2>Kaydedilen tahminlerin karnesi (bütün fonlar)</h2>
          <div className="panel">
            <p className="small">
              Her gece kaydedilen tahminlerin gerçekleşenle karşılaştırması. <span className="source-badge is-live">Canlı</span> tahminler
              o günün gece güncellemesinde kaydedildi; <span className="source-badge is-back">Geriye dönük</span> olanlar sonradan, yalnızca
              o tarihe kadarki veriyle hesaplandı. İkisi ayrı sayılır. Fon bazında karne fon sayfalarında.
            </p>
            <LiveScorecard sc={data.scorecard} />
          </div>
        </>
      )}

      <h2>İlk yöntem: aylık başlangıçlarla 21 günlük aralık</h2>
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
      <p className="muted small">Aralık, drift tahmininin geçmiş hatalarından (risk grubuna göre) kurulur. Kapsam: test döneminde, her ay sadece o güne kadarki hatalarla kurulan aralığın gerçekleşmeyi içerme oranı; hedef %80. Yalnızca ayın ilk işlem günü başlatılan tahminlerle kurulduğu için ufka göre karneyle birebir aynı değildir; sitede artık ufka göre aralık kullanılıyor.</p>

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
