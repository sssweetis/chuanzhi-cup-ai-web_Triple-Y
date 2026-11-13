import { spawn } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const chromePath = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const port = Number(process.env.CHROME_DEBUG_PORT || 9335)
const outputDir = resolve('docs/frontend/screenshots/errors')
const profileDir = join(tmpdir(), `triple-y-error-capture-${process.pid}-${Date.now()}`)
const scenarios = [
  'offline',
  'network',
  'timeout',
  'rate_limited',
  'file_too_large',
  'unsupported_media',
  'scanned_pdf',
  'empty_result',
  'auth',
  'ocr_unavailable',
  'server_error',
  'invalid_response',
]
const sleep = ms => new Promise(resolvePromise => setTimeout(resolvePromise, ms))

await mkdir(outputDir, { recursive: true })
const chrome = spawn(chromePath, [
  '--headless=new',
  '--disable-gpu',
  '--no-first-run',
  '--remote-allow-origins=*',
  `--remote-debugging-port=${port}`,
  `--user-data-dir=${profileDir}`,
  'about:blank',
], { stdio: 'ignore' })

async function getTarget() {
  for (let index = 0; index < 60; index++) {
    try {
      const targets = await fetch(`http://127.0.0.1:${port}/json/list`).then(response => response.json())
      const page = targets.find(target => target.type === 'page')
      if (page) return page
    } catch {}
    await sleep(100)
  }
  throw new Error('无法连接 Chrome DevTools')
}

const target = await getTarget()
const socket = new WebSocket(target.webSocketDebuggerUrl)
const pending = new Map()
let messageId = 0
await new Promise((resolveOpen, rejectOpen) => {
  socket.addEventListener('open', resolveOpen, { once: true })
  socket.addEventListener('error', rejectOpen, { once: true })
})
socket.addEventListener('message', event => {
  const message = JSON.parse(event.data)
  if (!message.id) return
  const promise = pending.get(message.id)
  if (!promise) return
  pending.delete(message.id)
  if (message.error) promise.reject(new Error(message.error.message))
  else promise.resolve(message.result)
})

function send(method, params = {}) {
  const id = ++messageId
  socket.send(JSON.stringify({ id, method, params }))
  return new Promise((resolveRequest, rejectRequest) => {
    pending.set(id, { resolve: resolveRequest, reject: rejectRequest })
  })
}

await send('Page.enable')
await send('Emulation.setDeviceMetricsOverride', {
  width: 960,
  height: 720,
  deviceScaleFactor: 1,
  mobile: false,
})

for (const [index, code] of scenarios.entries()) {
  await send('Page.navigate', { url: `http://127.0.0.1:5173/error-lab.html?scenario=${code}` })
  await sleep(350)
  const result = await send('Page.captureScreenshot', { format: 'png', fromSurface: true })
  const filename = `${String(index + 1).padStart(2, '0')}-${code}.png`
  await writeFile(resolve(outputDir, filename), Buffer.from(result.data, 'base64'))
  console.log(filename)
}

await send('Browser.close').catch(() => {})
socket.close()
