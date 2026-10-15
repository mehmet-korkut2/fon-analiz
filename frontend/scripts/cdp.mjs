// Edge/Chrome'u headless açıp DevTools protokolüyle (CDP) süren ortak yardımcılar
// (ekran_goruntusu.mjs, uctan_uca.mjs). Ek bağımlılık yok: Node 22+ yerleşik WebSocket ve fetch.
import { spawn } from 'node:child_process'
import { existsSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

export const BASE = process.env.APP_URL || 'http://localhost:5173'
const BROWSERS = [
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
]

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

// extraArgs: ör. ['--proxy-server=127.0.0.1:9'] (dış ağı kesmek için; localhost proxy'yi atlar)
export async function launch(extraArgs = []) {
  const exe = BROWSERS.find((b) => existsSync(b))
  if (!exe) throw new Error('Edge ya da Chrome bulunamadı')
  const port = 9300 + Math.floor(Math.random() * 500)
  const profile = mkdtempSync(join(tmpdir(), 'fon-cdp-'))
  const proc = spawn(exe, ['--headless=new', '--disable-gpu', '--no-first-run', `--user-data-dir=${profile}`,
    `--remote-debugging-port=${port}`, ...extraArgs, 'about:blank'], { stdio: 'ignore' })
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

// CDP istemcisi: send(method, params) ve on(event, handler)
export function connect(url) {
  const ws = new WebSocket(url)
  let id = 0
  const pending = new Map()
  const handlers = new Map()
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data)
    if (msg.id && pending.has(msg.id)) {
      const { ok, fail } = pending.get(msg.id)
      pending.delete(msg.id)
      msg.error ? fail(new Error(msg.error.message)) : ok(msg.result)
    } else if (msg.method) {
      for (const h of handlers.get(msg.method) ?? []) h(msg.params)
    }
  }
  const ready = new Promise((r) => { ws.onopen = r })
  const send = (method, params = {}) => new Promise((ok, fail) => {
    pending.set(++id, { ok, fail })
    ws.send(JSON.stringify({ id, method, params }))
  })
  const on = (method, h) => handlers.set(method, [...(handlers.get(method) ?? []), h])
  return { ready, send, on, close: () => ws.close() }
}

// Sayfada ifade değerlendirir (Promise ise bekler) ve değeri döndürür
export async function evaluate(cdp, expression) {
  const { result, exceptionDetails } = await cdp.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (exceptionDetails) throw new Error(exceptionDetails.exception?.description || exceptionDetails.text)
  return result.value
}

// Yükleme yazıları kaybolana ve her grafik kabında çizilmiş bir SVG olana kadar bekle (en çok 20 sn)
const READY = `(() => {
  const text = document.querySelector('main')?.innerText ?? ''
  if (/Yükleniyor|Hesaplanıyor/.test(text)) return false
  const boxes = [...document.querySelectorAll('.recharts-responsive-container')]
  return boxes.every((b) => b.querySelector('svg path, svg rect'))
})()`

export async function waitForPage(cdp) {
  await sleep(800)
  for (let i = 0; i < 40; i++) {
    if (await evaluate(cdp, READY)) break
    await sleep(500)
  }
  await sleep(700) // yazı tipleri ve son çizim
}

export async function setViewport(cdp, { width, height, mobile, dark }) {
  await cdp.send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile })
  await cdp.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: dark ? 'dark' : 'light' }] })
}
