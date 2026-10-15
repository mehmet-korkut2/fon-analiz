// Uçtan uca test: bütün sayfaları ve akışları gerçek veriyle, gerçek tarayıcıda (Edge headless) dener.
// Uygulama çalışırken (backend :8000, frontend :5173):
//   node scripts/uctan_uca.mjs                 # açık + koyu tema, 1280 px + 390 px (4 tur)
//   node scripts/uctan_uca.mjs --cevrimdisi    # tarayıcının dış ağı kapalı; döviz "son bilinen kurlar" bekler
//   node scripts/uctan_uca.mjs --tur acik-masaustu
// Her adımda: beklenen öğeler, yatay taşma, konsol/sayfa hataları, 5xx API yanıtları, localhost dışına istek.
// Not: sanal portföy boşsa akış bir alış emri verip iptal eder, sonunda portföy aynı başlangıç
// bakiyesiyle yeniden boşaltılır. Portföyde kayıt varsa (gerçek kullanım) alış/iptal adımları atlanır
// ve hiçbir şey silinmez.
import { BASE, connect, evaluate, launch, setViewport, sleep, waitForPage } from './cdp.mjs'

const args = process.argv.slice(2)
const offline = args.includes('--cevrimdisi')
const ROUNDS = [
  { name: 'acik-masaustu', width: 1280, height: 900, mobile: false, dark: false },
  { name: 'koyu-masaustu', width: 1280, height: 900, mobile: false, dark: true },
  { name: 'acik-390', width: 390, height: 844, mobile: true, dark: false },
  { name: 'koyu-390', width: 390, height: 844, mobile: true, dark: true },
].filter((r) => !args.includes('--tur') || r.name === args[args.indexOf('--tur') + 1])

// Sayfaya eklenen küçük yardımcılar (React'in kontrollü inputları için değer, native setter ile verilir)
const HELPERS = `window.__t = {
  q: (s) => document.querySelector(s),
  all: (s) => [...document.querySelectorAll(s)],
  byText(sel, txt) { return [...document.querySelectorAll(sel)].find((e) => e.textContent.trim().includes(txt)) },
  click(sel, txt) {
    const e = txt ? this.byText(sel, txt) : this.q(sel)
    if (!e) throw new Error('bulunamadı: ' + sel + (txt ? ' "' + txt + '"' : ''))
    e.scrollIntoView({ block: 'center' }); e.click(); return true
  },
  type(sel, v) {
    const e = this.q(sel)
    if (!e) throw new Error('bulunamadı: ' + sel)
    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e), 'value').set.call(e, v)
    e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true }))
    return true
  },
  async until(fn, ms = 15000) {
    const end = Date.now() + ms
    while (Date.now() < end) { try { const v = fn(); if (v) return v } catch {} ; await new Promise((r) => setTimeout(r, 200)) }
    throw new Error('zaman aşımı: ' + fn.toString().slice(0, 120))
  },
}; true`

// [ad, yol, adımlar]. Her adım sayfada çalışan bir ifade; doğruysa geçer, metin dönerse ayrıntıdır.
const FLOWS = [
  ['Ana sayfa', '/', [
    ['Başlık', `__t.q('h1')?.textContent.includes('Fonları karşılaştır')`],
    ['Kategori kutuları', `__t.all('.cat-tile').length >= 5 && __t.all('.cat-tile').length + ' kategori'`],
    ['Öne çıkan fonlar (8)', `__t.all('.featured-table tbody tr').length === 8`],
    ['Risk anketi kartı', `!!__t.byText('.home-cta a', 'anket') || !!__t.byText('.home-cta a', 'Önerileri')`],
    ['Arama: "altın" → fon listesi', `(async () => { __t.type('#home-q', 'altın'); __t.click('.home-search button');
      await __t.until(() => location.pathname === '/fonlar' && __t.all('.funds-table tbody tr td.fund-name').length);
      return __t.all('.funds-table tbody tr td.fund-name').length + ' sonuç, ilk: ' + __t.q('.funds-table tbody td.fund-name a').textContent.slice(0, 40) })()`],
  ]],
  ['Fon listesi', '/fonlar', [
    ['25 satır', `__t.all('.funds-table tbody tr').length === 25`],
    ['Büyüklüğe göre sıralama', `(async () => { __t.click('.funds-table th button', 'Büyüklük');
      await __t.until(() => __t.q('.funds-table tbody tr td:nth-last-child(2)')?.textContent.includes('milyar'));
      return __t.q('.funds-table tbody tr td:nth-last-child(2)').textContent })()`],
    ['Sayfalama', `(async () => { __t.click('.pager button', 'Sonraki'); await __t.until(() => __t.q('.pager .num')?.textContent.startsWith('Sayfa 2')); return true })()`],
  ]],
  ['Fon detayı ve teknik göstergeler', '/fonlar/TTE', [
    ['Fiyat grafiği', `!!__t.q('.chart .recharts-area path, .chart .recharts-line path')`],
    ['50 günlük ortalama aç', `(async () => { __t.click('.ma-toggle input'); await __t.until(() => __t.q('path[stroke="var(--chart-ma50)"]')); return true })()`],
    ['200 günlük ortalama aç', `(async () => { __t.all('.ma-toggle input')[1].click(); await __t.until(() => __t.q('path[stroke="var(--chart-ma200)"]')); return true })()`],
    ['Trend ve 52 haftalık aralık', `!!__t.q('.tech-trend') && !!__t.q('.range-dot') && __t.q('.tech-trend').textContent`],
    ['Dönem 3Y', `(async () => { __t.click('.seg button', '3Y'); await __t.until(() => location.search.includes('donem=3Y')); return true })()`],
    ['Tahmin kartı ve hesaplayıcı', `!!__t.byText('h2', 'Geçmiş eğilime dayalı tahmin') && !!__t.q('.calc input')`],
    ['Fon büyüklüğü ve yatırımcı', `__t.byText('.card', 'Fon büyüklüğü')?.textContent.includes('TL')`],
    ['KAP bağlantısı (TEFAS)', `__t.q('.kap-link a')?.href.startsWith('https://www.kap.org.tr/')`],
    ['Sanal portföyde dene', `__t.byText('.detail-actions a', 'Sanal portföyde dene')?.getAttribute('href') === '/sanal-portfoy?fon=TTE'`],
  ]],
  ['Karşılaştırma', '/karsilastir?fonlar=TTE,AFT,IPB,AES', [
    ['4 fon çizgisi', `__t.all('.recharts-line').length >= 4`],
    ['Metrik tablosu', `__t.all('.compare-table tbody tr').length >= 10`],
    ['Logaritmik ölçek', `(async () => { const c = __t.byText('label', 'Logaritmik')?.querySelector('input'); c.click(); await __t.until(() => c.checked); return true })()`],
  ]],
  ['Sıralamalar', '/siralamalar', [
    ['3 liste × 10 fon', `__t.all('.rank-card').length === 3 && __t.all('.rank-card').every((c) => c.querySelectorAll('li').length === 10)`],
  ]],
  ['Risk anketi', '/risk-anketi', [
    ['9 soruyu yanıtla', `(async () => {
      for (let i = 0; i < 12; i++) {
        if (__t.q('.profile-card')) return 'profil: ' + __t.q('.profile-label')?.textContent
        const opts = __t.all('.option')
        if (!opts.length) { await new Promise((r) => setTimeout(r, 300)); continue }
        opts[Math.floor(opts.length / 2)].click()
        await new Promise((r) => setTimeout(r, 150))
        const next = __t.byText('.survey-actions button', 'İleri') || __t.byText('.survey-actions button', 'Profilimi göster')
        next.click()
        await new Promise((r) => setTimeout(r, 400))
      }
      await __t.until(() => __t.q('.profile-card'))
      return 'profil: ' + __t.q('.profile-label')?.textContent })()`],
  ]],
  ['Öneriler ve portföy planlayıcı', '/oneriler', [
    ['10 öneri', `__t.all('.rec-card').length === 10`],
    ['Örnek portföy grafiği', `!!__t.q('.perf .recharts-line')`],
    ['Planlayıcı tutarı değişir', `(async () => { __t.type('.planner input', '50.000');
      await __t.until(() => __t.q('.planner-table tfoot')?.textContent.includes('50.000')); return true })()`],
    ['Kayan pencereli test', `!!__t.byText('h2', 'Geriye dönük test') && !!__t.q('.rolling .recharts-bar-rectangle, .rolling .recharts-rectangle')`],
  ]],
  ['Sanal portföy', '/sanal-portfoy', [
    ['Uyarı metni', `__t.q('.sim-warning')?.textContent.includes('Bu hayali parayla yapılan bir simülasyondur')`],
    ['Fon seç (TTE)', `(async () => { __t.type('#buy-fund', 'TTE'); await __t.until(() => __t.byText('.picker-results button', 'TTE'));
      __t.byText('.picker-results button', 'TTE').click(); await __t.until(() => __t.q('.sim-valor')); return __t.q('.sim-valor').textContent.slice(0, 80) })()`],
    ['Alış emri ver', `(async () => { __t.type('#buy-amount', '5.000'); __t.click('.sim-form button[type=submit]');
      await __t.until(() => __t.q('.notice-ok')); return __t.q('.notice-ok').textContent })()`],
    ['Bekleyen emirde görünür', `__t.byText('#pending-title', 'Bekleyen')?.parentElement.textContent.includes('TTE')`],
    ['Nakit ayrıldı', `__t.byText('.card', 'Nakit')?.textContent.includes('ayrılan')`],
    ['Emri iptal et', `(async () => { __t.click('section button', 'İptal'); await __t.until(() => !__t.q('#pending-title')); return true })()`],
    ['İşlem geçmişi', `!!__t.byText('summary', 'İşlem geçmişi')`],
  ]],
  ['Ya o zaman alsaydım?', '/sanal-portfoy?mod=geriye&fon=TTE,AFT', [
    ['2 fonun sonucu', `__t.all('.whatif-table tbody tr').length === 2`],
    ['Grafik', `__t.all('.recharts-line').length >= 3`],
    ['4 yıl önce: yıllıklandırılmış getiri', `(async () => { __t.type('#wi-date', '2022-10-03');
      await __t.until(() => __t.q('#wi-date').value === '2022-10-03'); __t.click('.sim-form button[type=submit]');
      await __t.until(() => __t.q('.whatif-table td[data-label="Alış"]')?.textContent.includes('2022'));
      return __t.all('.whatif-table td[data-label="Alış"]').map((t) => t.textContent.slice(0, 10)).join(', ') + ' → yıllık ' +
        __t.all('.whatif-table td[data-label="Yıllık"]').map((t) => t.textContent).join(' / ') })()`],
  ]],
  ['Döviz ve altın', '/doviz', offline ? [
    ['Son bilinen kurlar notu', `__t.q('.notice')?.textContent.includes('en son')`],
    ['Kur tablosu (anlık)', `__t.all('.fx table tbody tr').length > 3`],
    ['TCMB sekmesi', `(async () => { __t.click('.seg button', 'TCMB'); await __t.until(() => __t.q('.hint')?.textContent.includes('TCMB')); await __t.until(() => __t.all('.fx table tbody tr').length > 3); return __t.q('.notice')?.textContent.slice(0, 60) || 'not yok' })()`],
  ] : [
    ['Kur tablosu (anlık)', `__t.all('.fx table tbody tr').length > 3`],
    ['TCMB sekmesi', `(async () => { __t.click('.seg button', 'TCMB'); await __t.until(() => __t.q('.hint')?.textContent.includes('TCMB')); await __t.until(() => __t.all('.fx table tbody tr').length > 3); return true })()`],
  ]],
  ['Model performansı', '/model-performansi', [
    ['Sonuç tabloları', `__t.all('.ml-table').length >= 3`],
    ['Aylık hata grafiği', `__t.all('.recharts-line').length >= 4`],
  ]],
]

const EXTERNAL_OK = /^(data:|blob:|chrome|about:|devtools:)/
const API = 'http://127.0.0.1:8000/api'
const sanalBefore = await (await fetch(`${API}/sanal-portfoy`)).json()
const sanalEmpty = !sanalBefore.pending.length && !sanalBefore.history.length
const SANAL_WRITES = new Set(['Fon seç (TTE)', 'Alış emri ver', 'Bekleyen emirde görünür', 'Nakit ayrıldı', 'Emri iptal et'])

async function runRound(round) {
  const { proc, ws } = await launch(offline ? ['--proxy-server=127.0.0.1:9', '--proxy-bypass-list=localhost;127.0.0.1'] : [])
  const cdp = connect(ws)
  await cdp.ready
  const issues = []
  let current = ''
  cdp.on('Runtime.exceptionThrown', (p) => issues.push(`${current}: sayfa hatası: ${p.exceptionDetails.exception?.description?.split('\n')[0] ?? p.exceptionDetails.text}`))
  cdp.on('Runtime.consoleAPICalled', (p) => {
    if (p.type === 'error') issues.push(`${current}: konsol hatası: ${p.args.map((a) => a.value ?? a.description ?? '').join(' ').slice(0, 200)}`)
  })
  cdp.on('Network.requestWillBeSent', (p) => {
    const u = p.request.url
    if (!EXTERNAL_OK.test(u) && !/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?\//.test(u)) issues.push(`${current}: dış istek: ${u.slice(0, 120)}`)
  })
  cdp.on('Network.responseReceived', (p) => {
    if (p.response.url.includes('/api/') && p.response.status >= 500) issues.push(`${current}: API ${p.response.status}: ${p.response.url}`)
  })
  const results = []
  try {
    await cdp.send('Page.enable')
    await cdp.send('Runtime.enable')
    await cdp.send('Network.enable')
    await setViewport(cdp, round)
    for (const [title, path, steps] of FLOWS) {
      current = title
      await cdp.send('Page.navigate', { url: BASE + path })
      await waitForPage(cdp)
      await evaluate(cdp, HELPERS)
      for (const [name, expr] of steps) {
        const t0 = Date.now()
        if (!sanalEmpty && title === 'Sanal portföy' && SANAL_WRITES.has(name)) {
          results.push({ tur: round.name, sayfa: title, adim: name, sonuc: 'GEÇTİ', ayrinti: 'ATLANDI: portföyde gerçek kayıt var', ms: 0 })
          continue
        }
        try {
          const v = await evaluate(cdp, expr)
          results.push({ tur: round.name, sayfa: title, adim: name, sonuc: v ? 'GEÇTİ' : 'KALDI', ayrinti: typeof v === 'string' ? v.replace(/\s+/g, ' ').slice(0, 70) : '', ms: Date.now() - t0 })
        } catch (e) {
          results.push({ tur: round.name, sayfa: title, adim: name, sonuc: 'KALDI', ayrinti: e.message.slice(0, 90), ms: Date.now() - t0 })
        }
        await sleep(150)
      }
      const sw = await evaluate(cdp, 'document.documentElement.scrollWidth')
      results.push({ tur: round.name, sayfa: title, adim: 'Yatay taşma yok', sonuc: sw <= round.width ? 'GEÇTİ' : 'KALDI', ayrinti: `${sw} px`, ms: 0 })
    }
  } finally {
    cdp.close()
    proc.kill()
  }
  return { results, issues }
}

const all = []
const allIssues = []
for (const round of ROUNDS) {
  const { results, issues } = await runRound(round)
  all.push(...results)
  allIssues.push(...issues.map((i) => `[${round.name}] ${i}`))
  const failed = results.filter((r) => r.sonuc !== 'GEÇTİ')
  console.log(`${round.name}: ${results.length - failed.length}/${results.length} geçti${issues.length ? `, ${issues.length} uyarı` : ''}`)
}
if (sanalEmpty) {  // deneme emirlerini temizle, portföyü eski (boş) hâline döndür
  await fetch(`${API}/sanal-portfoy/sifirla`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ initial_balance: sanalBefore.initial_balance }),
  }).catch(() => {})
}

const failed = all.filter((r) => r.sonuc !== 'GEÇTİ')
if (failed.length) console.table(failed)
if (allIssues.length) console.log('Uyarılar:\n' + [...new Set(allIssues)].map((i) => '  - ' + i).join('\n'))
if (args.includes('--ayrinti')) console.table(all.filter((r) => r.tur === ROUNDS[0].name).map(({ sayfa, adim, sonuc, ayrinti }) => ({ sayfa, adim, sonuc, ayrinti })))
console.log(`Toplam: ${all.length - failed.length}/${all.length} adım geçti${offline ? ' (çevrimdışı)' : ''}.`)
process.exit(failed.length || allIssues.length ? 1 : 0)
