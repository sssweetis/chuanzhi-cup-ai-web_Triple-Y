import { state, setState } from '../state.js'
import { analyzeNotification, prepareList, analyzeImage } from '../api.js'
import { renderMatter } from './ModeCard.js'
import { SAMPLES } from '../mockMatters.js'

export function renderInputPanel(mount) {
  mount.innerHTML = `
    <div class="card in">
      <div class="lab">输入通知 · 粘贴文字、语音说、或附上 Word / PDF</div>
      <textarea id="taskInput" rows="4" placeholder="例如：请于 10 月 25 日 18:00 前提交比赛报名表和成绩单，逾期不候。"></textarea>
      <div class="in-bar">
        <div class="in-bar-left">
          <button class="tool" id="micBtn">语音</button>
          <button class="tool" id="imgBtn">📷 截图/图片</button>
          <input type="file" id="imgInput" accept="image/*" hidden>
          <button class="tool" id="attachBtn">附件</button>
          <input type="file" id="fileInput" accept=".doc,.docx,.pdf" multiple hidden>
          <span class="date-pick">截止 <input type="date" id="taskDate"></span>
          <button class="tool" id="demoToggle" title="离线示例数据">示例</button>
        </div>
        <div class="in-bar-right">
          <span class="char-count" id="charCount">0 / 3000</span>
          <button class="btn btn-primary" id="analyzeBtn">AI 智能解析</button>
        </div>
      </div>
      <div class="img-preview-row" id="imgPreviewRow" style="display:none">
        <img id="imgPreview" alt="">
        <button class="tool" id="imgRemove">✕ 移除图片</button>
      </div>
      <div class="chips" id="chipBox"></div>
      <div class="attach-note">Word/PDF 附件解析开发中，当前仅记录文件名。</div>
      <div class="demo-row" id="demoRow" style="display:none">
        ${SAMPLES.map((s, i) => `<button class="tool demo-btn" data-i="${i}">${s.label}</button>`).join('')}
      </div>
      <div class="result-zone" id="resultZone"></div>
    </div>`

  const zone = mount.querySelector('#resultZone')

  // 点"出处"按钮 → 弹窗展示原文片段
  zone.addEventListener('click', (e) => {
    const btn = e.target.closest('.src-btn')
    if (btn) {
      const quote = btn.dataset.quote
      const type = btn.dataset.type, id = btn.dataset.id
      let mask = document.getElementById('srcMask')
      if (!mask) {
        mask = document.createElement('div')
        mask.id = 'srcMask'
        mask.className = 'mask'
        mask.innerHTML = `<div class="modal">
          <h3>📄 原文依据</h3>
          <div class="src-quote-modal" id="srcQuote"></div>
          <div class="modal-foot"><button class="btn btn-primary" id="srcClose">关闭</button></div>
        </div>`
        document.body.appendChild(mask)
        mask.onclick = (e) => { if (e.target === mask) mask.classList.remove('show') }
        mask.querySelector('#srcClose').onclick = () => mask.classList.remove('show')
      }
      const qEl = mask.querySelector('#srcQuote')
      if (type && state.analyzeResult) {
        qEl.textContent = '加载中…'
        import('../api.js').then(({ getEvidence }) =>
          getEvidence({ matter: state.analyzeResult, target_type: type, target_id: id })
            .then(res => {
              if (res && res.found) {
                qEl.innerHTML = (res.is_suggestion ? '<div style="color:#b36b00">⚠ 系统建议（无原文依据）</div>' : '') + '“' + (res.quote || '') + '”'
              } else { qEl.textContent = quote ? '“' + quote + '”' : '暂无原文' }
            })
            .catch(() => { qEl.textContent = quote ? '“' + quote + '”' : '暂无原文' })
        )
      } else {
        qEl.textContent = quote ? '“' + quote + '”' : '暂无原文'
      }
      mask.classList.add('show')
      return
    }
    if (e.target.closest('#confirmUpdateBtn')) {
      alert('已确认，任务清单将按新通知更新')
    }
  })

  function paint() {
    if (state.analyzing) {
      zone.innerHTML = `<div class="skeleton"><div class="sk-line w60"></div><div class="sk-line w90"></div><div class="sk-line w40"></div><div class="sk-note">正在判断通知复杂度，提取时间 / 材料 / 要求…</div></div>`
    } else if (state.analyzeError) {
      zone.innerHTML = `<div class="error-box">解析失败：${state.analyzeError} <button class="btn btn-ghost btn-sm" id="retryBtn">重试</button></div>`
      mount.querySelector('#retryBtn').onclick = runAnalyze
    } else if (state.analyzeResult) {
      zone.innerHTML = renderMatter(state.analyzeResult) + `
        <div class="add-task-bar">
          <button class="btn btn-primary" id="addTaskBtn">＋ 把这个通知加入任务清单</button>
        </div>`
      mount.querySelector('#addTaskBtn').onclick = () => {
        const m = state.analyzeResult
        const due = m && m.deadline && m.deadline.due_at ? m.deadline.due_at.slice(0, 10) : new Date().toISOString().slice(0, 10)
        const title = (m && m.title) || '新任务'
        const srcText = mount.querySelector('#taskInput').value.trim()
        if (!state.tasks.some(t => t.title === title)) {
          state.tasks.push({ id: Date.now(), title, date: due, done: false, sourceText: srcText })
        }
        setState({})
        alert('已加入任务清单')
      }
    } else {
      zone.innerHTML = `<div class="ph">分析结果会显示在这里</div>`
    }
  }
  paint()

  async function runAnalyze() {
    const text = mount.querySelector('#taskInput').value.trim()
    const imgFile = mount.querySelector('#imgInput').files[0]
    if (!text && !imgFile) { alert('先粘贴一段通知，或上传一张截图'); return }
    setState({ analyzing: true, analyzeError: '', analyzeResult: null })
    paint()
    try {
      let data
      if (imgFile) {
        data = await analyzeImage(imgFile)
      } else {
        data = await analyzeNotification(text)
      }
      setState({ analyzing: false, analyzeResult: data })
      // 自动拉准备清单，把 todo_list 合并进任务清单
      try {
        const prep = await prepareList({ matter: data })
        const due = data && data.deadline && data.deadline.due_at
          ? data.deadline.due_at.slice(0, 10) : new Date().toISOString().slice(0, 10)
        const existing = new Set(state.tasks.map(t => t.title))
        const srcText = text
        ;(prep.todo_list || []).forEach(todo => {
          if (!existing.has(todo.action)) {
            state.tasks.push({ id: Date.now() + Math.random(), title: todo.action, date: due, done: false, sourceText: srcText })
            existing.add(todo.action)
          }
        })
      } catch (e) { /* prepare-list 失败不阻塞主流程 */ }
    } catch (err) {
      const tip = /连不上后端|Failed to fetch|NetworkError/i.test(String(err))
        ? '后端服务还没启动，可以先点下面三个示例按钮看效果'
        : (err.message || '网络异常')
      setState({ analyzing: false, analyzeError: tip })
    }
    paint()
  }

  mount.querySelector('#analyzeBtn').onclick = runAnalyze
  mount.querySelector('#imgBtn').onclick = () => mount.querySelector('#imgInput').click()
  mount.querySelector('#imgInput').onchange = (e) => {
    const f = e.target.files[0]
    if (!f) return
    if (f.size > 10 * 1024 * 1024) { alert('图片不能超过 10MB'); e.target.value = ''; return }
    const reader = new FileReader()
    reader.onload = () => {
      mount.querySelector('#imgPreviewRow').style.display = 'flex'
      mount.querySelector('#imgPreview').src = reader.result
      mount.dataset.imgData = reader.result
    }
    reader.readAsDataURL(f)
  }
  mount.querySelector('#imgRemove').onclick = () => {
    mount.querySelector('#imgPreviewRow').style.display = 'none'
    mount.querySelector('#imgPreview').src = ''
    mount.dataset.imgData = ''
    mount.querySelector('#imgInput').value = ''
  }
  mount.querySelector('#demoToggle').onclick = () => {
    const row = mount.querySelector('#demoRow')
    row.style.display = row.style.display === 'none' ? 'flex' : 'none'
  }
  mount.querySelector('#taskInput').value = localStorage.getItem('zhiban-input') || ''
  function syncInput() {
    const ta = mount.querySelector('#taskInput')
    localStorage.setItem('zhiban-input', ta.value)
    mount.querySelector('#charCount').textContent = `${ta.value.length} / 3000`
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 300) + 'px'
    // 输入框清空时，下方分析结果也一起清掉
    if (!ta.value.trim() && state.analyzeResult) {
      setState({ analyzeResult: null, analyzeError: '' })
    }
  }
  mount.querySelector('#taskInput').oninput = syncInput
  syncInput()
  mount.querySelectorAll('.demo-btn').forEach(b => b.onclick = () => {
    setState({ analyzing: false, analyzeError: '', analyzeResult: SAMPLES[Number(b.dataset.i)].data })
    paint()
  })
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
