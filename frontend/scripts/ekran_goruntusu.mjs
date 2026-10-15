// Sayfaların ekran görüntüsünü alır ve yatay taşmayı ölçer (Edge/Chrome, DevTools protokolü).
// Uygulama çalışırken (backend :8000, `npm run dev` :5173):
//   node scripts/ekran_goruntusu.mjs <klasör> <önek> [--mobil] [--koyu] [--sayfa ana,fonlar,...] [--tab N]
// --ekran: sayfanın tamamı yerine yalnızca ilk ekran (rapor şekilleri için)
// --tab N: çekmeden önce N kez Tab'a basar ve odaktaki öğeyi yazar (klavyeyle gezinme denetimi; yalnızca görünen alan çekilir)
// Örnek: node scripts/ekran_goruntusu.mjs ../docs/rapor/gorseller/tasarim sonra --koyu
// Pencere boyutu Emulation ile verilir; headless tarayıcının en küçük pencere genişliği sorununu aşar.
import { spawn } from 'node:child_process'
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const BASE = process.env.APP_URL || 'http://localhost:5173'
const BROWSERS = [
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
]
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
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function launch() {
  const { existsSync } = await import('node:fs')
  const exe = BROWSERS.find((b) => existsSync(b))
  if (!exe) throw new Error('Edge ya da Chrome bulunamadı')
  const port = 9300 + Math.floor(Math.random() * 500)
  const profile = mkdtempSync(join(tmpdir(), 'fon-ekran-'))
  const proc = spawn(exe, ['--headless=new', '--disable-gpu', '--no-first-run', `--user-data-dir=${profile}`,
    `--remote-debugging-port=${port}`, 'about:blank'], { stdio: 'ignore' })
  for (let i = 0; i < 50; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()
      const page = list.find((t) => t.type === 'page')
      if (page) return { proc, ws: page.webSocketDebuggerUrl }
    } catch { /* tarayıcı henüz açılmadı */ }
    await sleep(200)
  }
  proc.kill()
  throw new Error('Tarayıcıya bağlanılamadı')
}

function client(url) {
  const ws = new WebSocket(url)
  let id = 0
  const pending = new Map()
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data)
    if (msg.id && pending.has(msg.id)) {
      const { ok, fail } = pending.get(msg.id)
      pending.delete(msg.id)
      msg.error ? fail(new Error(msg.error.message)) : ok(msg.result)
    }
  }
  const ready = new Promise((r) => { ws.onopen = r })
  const send = (method, params = {}) => new Promise((ok, fail) => {
    pending.set(++id, { ok, fail })
    ws.send(JSON.stringify({ id, method, params }))
  })
  return { ready, send, close: () => ws.close() }
}

// Öneriler sayfası için risk profili: anketteki her sorunun ortadaki seçeneği
const SEED_PROFILE = `(async () => {
  const s = await (await fetch('/api/risk-survey')).json()
  const answers = Object.fromEntries(s.questions.map((q) => [q.id, q.options[Math.floor(q.options.length / 2)].value]))
  const result = await (await fetch('/api/risk-profile', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers, qualified: false }) })).json()
  localStorage.setItem('riskProfili', JSON.stringify({ answers, qualified: false, result, savedAt: new Date().toISOString() }))
  return result.profile
})()`

// Yükleme yazıları kaybolana ve her grafik kabında çizilmiş bir SVG olana kadar bekle (en çok 20 sn)
const READY = `(() => {
  const text = document.querySelector('main')?.innerText ?? ''
  if (/Yükleniyor/.test(text)) return false
  const boxes = [...document.querySelectorAll('.recharts-responsive-container')]
  return boxes.every((b) => b.querySelector('svg path, svg rect'))
})()`
async function waitForPage() {
  await sleep(800)
  for (let i = 0; i < 40; i++) {
    const { result } = await cdp.send('Runtime.evaluate', { expression: READY })
    if (result.value) break
    await sleep(500)
  }
  await sleep(700) // yazı tipleri ve son çizim
}

const { proc, ws } = await launch()
const cdp = client(ws)
await cdp.ready
try {
  await cdp.send('Page.enable')
  await cdp.send('Runtime.enable')
  await cdp.send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile })
  await cdp.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: dark ? 'dark' : 'light' }] })

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
    await waitForPage()
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
