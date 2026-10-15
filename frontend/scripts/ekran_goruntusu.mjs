// Sayfaların ekran görüntüsünü alır ve yatay taşmayı ölçer (Edge/Chrome, DevTools protokolü).
// Uygulama çalışırken (backend :8000, `npm run dev` :5173):
//   node scripts/ekran_goruntusu.mjs <klasör> <önek> [--mobil] [--koyu] [--sayfa ana,fonlar,...] [--tab N]
// --ekran: sayfanın tamamı yerine yalnızca ilk ekran (rapor şekilleri için)
// --tab N: çekmeden önce N kez Tab'a basar ve odaktaki öğeyi yazar (klavyeyle gezinme denetimi; yalnızca görünen alan çekilir)
// Örnek: node scripts/ekran_goruntusu.mjs ../docs/rapor/gorseller/tasarim sonra --koyu
// Pencere boyutu Emulation ile verilir; headless tarayıcının en küçük pencere genişliği sorununu aşar.
import { mkdirSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { BASE, connect as client, launch, setViewport, sleep, waitForPage as waitFor } from './cdp.mjs'

const PAGES = {
  ana: '/',
  fonlar: '/fonlar',
  detay: '/fonlar/TTE',
  siralamalar: '/siralamalar',
  karsilastir: '/karsilastir?fonlar=TTE,AFT,IPB,AES',
  anket: '/risk-anketi',
  oneriler: '/oneriler',
  model: '/model-performansi',
  doviz: '/doviz',
  sanal: '/sanal-portfoy',
  geriye: '/sanal-portfoy?mod=geriye&fon=TTE,AFT,IPB,AES',
}

const args = process.argv.slice(2)
const [outDir, prefix] = args
if (!outDir || !prefix) {
  console.error('Kullanım: node scripts/ekran_goruntusu.mjs <klasör> <önek> [--mobil] [--koyu] [--sayfa a,b]')
  process.exit(1)
}
const mobile = args.includes('--mobil')
const dark = args.includes('--koyu')
const tabs = args.includes('--tab') ? Number(args[args.indexOf('--tab') + 1]) : 0
const only = args.includes('--sayfa') ? args[args.indexOf('--sayfa') + 1].split(',') : Object.keys(PAGES)
const width = mobile ? 390 : 1280
const height = mobile ? 844 : 900

// Öneriler sayfası için risk profili: anketteki her sorunun ortadaki seçeneği
const SEED_PROFILE = `(async () => {
  const s = await (await fetch('/api/risk-survey')).json()
  const answers = Object.fromEntries(s.questions.map((q) => [q.id, q.options[Math.floor(q.options.length / 2)].value]))
  const result = await (await fetch('/api/risk-profile', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers, qualified: false }) })).json()
  localStorage.setItem('riskProfili', JSON.stringify({ answers, qualified: false, result, savedAt: new Date().toISOString() }))
  return result.profile
})()`

const { proc, ws } = await launch()
const cdp = client(ws)
await cdp.ready
try {
  await cdp.send('Page.enable')
  await cdp.send('Runtime.enable')
  await setViewport(cdp, { width, height, mobile, dark })

  mkdirSync(resolve(outDir), { recursive: true })
  const report = []
  for (const name of only) {
    // Risk profili yalnızca öneriler sayfası için; ana sayfa profilsiz hâliyle (anket kartı) görünsün
    if (name === 'oneriler') {
      await cdp.send('Page.navigate', { url: BASE + '/' }) // localStorage uygulamanın adresine yazılsın
      await sleep(1500)
      await cdp.send('Runtime.evaluate', { expression: SEED_PROFILE, awaitPromise: true })
    }
    await cdp.send('Page.navigate', { url: BASE + PAGES[name] })
    await waitFor(cdp)
    const { result } = await cdp.send('Runtime.evaluate', {
      expression: 'JSON.stringify({ sw: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight })',
    })
    const { sw, h: pageHeight } = JSON.parse(result.value)
    let h = args.includes('--ekran') ? height : pageHeight
    if (tabs) {
      for (let i = 0; i < tabs; i++) {
        for (const type of ['keyDown', 'keyUp']) {
          await cdp.send('Input.dispatchKeyEvent', { type, key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
        }
        await sleep(150)
      }
      const { result: f } = await cdp.send('Runtime.evaluate', {
        expression: "(() => { const a = document.activeElement; return a ? a.tagName + ' ' + (a.textContent || a.placeholder || '').trim().slice(0, 40) + ' | ' + getComputedStyle(a).outlineStyle + ' ' + getComputedStyle(a).outlineColor : '' })()",
      })
      console.log(`${name}: odak -> ${f.value}`)
      h = height
    }
    // Pencereyi sayfa boyuna büyüt, grafikler yeni boyuta göre çizilsin, sonra çek; ardından eski boyuta dön
    const full = Math.min(h, 6000)
    await cdp.send('Emulation.setDeviceMetricsOverride', { width, height: full, deviceScaleFactor: 1, mobile })
    await sleep(1500)
    const shot = await cdp.send('Page.captureScreenshot', { format: 'png', clip: { x: 0, y: 0, width, height: full, scale: 1 } })
    await cdp.send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile })
    const file = join(resolve(outDir), `${prefix}_${name}${mobile ? '_mobil' : ''}${dark ? '_koyu' : ''}.png`)
    writeFileSync(file, Buffer.from(shot.data, 'base64'))
    report.push({ sayfa: name, genislik: width, sayfa_genisligi: sw, tasma: sw > width ? sw - width : 0 })
  }
  console.table(report)
} finally {
  cdp.close()
  proc.kill()
}
