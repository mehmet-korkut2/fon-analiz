import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getInflation } from '../api/client'
import { monthLabel, num, pct, trDate } from '../format'

const share = (v) => (v == null ? '–' : `%${num(v * 100, 1)}`) // bir ondalık: iki evren arasındaki fark yuvarlamada kaybolmasın

// Ana sayfa: son 12 ayda enflasyonu yenen fonların payı, kategoriye göre. GET /api/inflation
// Pay, dönem başında fiyatı olan her fonu kapsar (dönem içinde kapanan ve SPK kararıyla kapatılanlar dahil);
// yalnızca bugün aktif olanlarla hesaplanan pay karşılaştırma için yazılır.
export default function InflationSummary() {
  const [data, setData] = useState(null)

  useEffect(() => {
    let ignore = false
    getInflation().then((d) => { if (!ignore) setData(d) }).catch(() => { if (!ignore) setData({ available: false }) })
    return () => { ignore = true }
  }, [])

  if (!data) {
    return (
      <section aria-labelledby="infl-title" className="infl-summary">
        <div className="section-head"><h2 id="infl-title">Son 1 yılda enflasyonu yenen fonlar</h2></div>
        <p className="muted small">Yükleniyor...</p>
      </section>
    )
  }
  const s = data.summary
  if (!data.available || !s?.available) {
    return (
      <section aria-labelledby="infl-title" className="infl-summary">
        <div className="section-head"><h2 id="infl-title">Enflasyonu yenen fonlar</h2></div>
        <p className="muted small">Enflasyon verisi yok. TÜFE, TCMB EVDS'ten alınır (API anahtarı gerekir).</p>
      </section>
    )
  }
  return (
    <section aria-labelledby="infl-title" className="infl-summary">
      <div className="section-head">
        <h2 id="infl-title">Son 1 yılda enflasyonu yenen fonlar</h2>
        <Link to="/fonlar?enflasyon=1" className="small">Enflasyonu yenenler →</Link>
      </div>
      <div className="infl-headline">
        <span className="infl-big num">{share(s.all.share)}</span>
        <span>
          {s.all.n.toLocaleString('tr-TR')} fonun {s.all.beat.toLocaleString('tr-TR')} tanesi {monthLabel(s.start)} sonundan{' '}
          {monthLabel(s.last_month)} sonuna enflasyonu ({pct(s.inflation)}) yendi.
        </span>
      </div>
      <p className="muted small">
        Dönem başında fiyatı olan bütün fonlar sayıldı; dönem içinde kapanan ya da SPK kararıyla işleme kapatılan fonlar da
        dahil ({s.exited} fonun fiyatı dönem içinde kesildi, son fiyatıyla sayıldı). Yalnızca bugün aktif olan{' '}
        {s.active.n.toLocaleString('tr-TR')} fon sayılsaydı oran {share(s.active.share)} olurdu.
      </p>
      <ul className="infl-cats">
        {s.categories.filter((c) => c.all.n >= 5).map((c) => (
          <li key={c.category}>
            <span>{c.category} <span className="muted small">({c.all.n})</span></span>
            <span className="imp-track" aria-hidden="true"><span style={{ width: `${(c.all.share ?? 0) * 100}%` }} /></span>
            <span className="num small">{share(c.all.share)}</span>
          </li>
        ))}
      </ul>
      <p className="muted small">
        En az 5 fonu olan kategoriler. {data.source_note} TÜFE {trDate(data.fetched_at)} tarihinde alındı.
        Geçmiş performans gelecekteki sonuçların göstergesi değildir.
      </p>
    </section>
  )
}
