import { state, setState } from '../state.js'
import { analyzeNotification } from '../api.js'
import { renderMatter } from './ModeCard.js'

export function renderInputPanel(mount) {
  mount.innerHTML = `
    <div class="card in">
      <div class="lab">输入通知 · 粘贴文字、语音说、或附上 Word / PDF</div>
      <textarea id="taskInput" placeholder="例如：请于 10 月 25 日 18:00 前提交比赛报名表和成绩单，逾期不候。"></textarea>
      <div class="in-tools">
        <button class="tool" id="micBtn">语音输入</button>
        <button class="tool" id="attachBtn">添加附件（Word / PDF）</button>
        <input type="file" id="fileInput" accept=".doc,.docx,.pdf" multiple hidden>
        <span class="date-pick">截止 <input type="date" id="taskDate"></span>
      </div>
      <div class="chips" id="chipBox"></div>
      <div class="attach-note">附件暂只记录文件名；文件与大段文字的汇总接口预留在这里，接大模型后自动生成摘要。</div>
      <div class="in-foot">
        <button class="btn btn-primary" id="analyzeBtn">AI 智能解析</button>
      </div>
      <div class="result-zone" id="resultZone"></div>
    </div>`

  const zone = mount.querySelector('#resultZone')
  function paint() {
    if (state.analyzing) {
      zone.innerHTML = `<div class="skeleton"><div class="sk-line w60"></div><div class="sk-line w90"></div><div class="sk-line w40"></div><div class="sk-note">正在判断通知复杂度，提取时间 / 材料 / 要求…</div></div>`
    } else if (state.analyzeError) {
      zone.innerHTML = `<div class="error-box">解析失败：${state.analyzeError} <button class="btn btn-ghost btn-sm" id="retryBtn">重试</button></div>`
      mount.querySelector('#retryBtn').onclick = runAnalyze
    } else if (state.analyzeResult) {
      zone.innerHTML = renderMatter(state.analyzeResult)
    } else {
      zone.innerHTML = `<div class="ph">分析结果会显示在这里</div>`
    }
  }
  paint()

  async function runAnalyze() {
    const text = mount.querySelector('#taskInput').value.trim()
    if (!text) { alert('先粘贴一段通知'); return }
    setState({ analyzing: true, analyzeError: '', analyzeResult: null })
    paint()
    try {
      const data = await analyzeNotification(text)
      setState({ analyzing: false, analyzeResult: data })
    } catch (err) {
      setState({ analyzing: false, analyzeError: err.message || '网络异常' })
    }
    paint()
  }

  mount.querySelector('#analyzeBtn').onclick = runAnalyze
  mount.querySelector('#attachBtn').onclick = () => mount.querySelector('#fileInput').click()
  mount.querySelector('#fileInput').onchange = (e) => {
    const box = mount.querySelector('#chipBox')
    Array.from(e.target.files).forEach(f => {
      const c = document.createElement('span'); c.className = 'chip'; c.textContent = f.name
      box.appendChild(c)
    })
  }
  // 语音输入（浏览器原生识别，不支持则提示）
  mount.querySelector('#micBtn').onclick = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { alert('当前浏览器不支持语音输入（推荐 Chrome）'); return }
    const rec = new SR(); rec.lang = 'zh-CN'
    rec.onresult = e => { mount.querySelector('#taskInput').value = e.results[0][0].transcript }
    rec.start()
  }
}
