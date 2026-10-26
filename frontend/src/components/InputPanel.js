import { state, setState } from '../state.js'
import { analyzeNotification, prepareList, analyzeImage, analyzePdf, uploadFile, listFiles, askQuestion } from '../api.js'
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
          <input type="file" id="imgInput" accept="image/jpeg,image/png,image/webp" hidden>
          <button class="tool" id="pdfBtn">📄 PDF</button>
          <input type="file" id="pdfInput" accept=".pdf" hidden>
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
      <div class="attach-note">支持文字型 PDF（≤10MB、≤30页）；扫描版 PDF 请改用截图粘贴。</div>
      <div class="demo-row" id="demoRow" style="display:none">
        ${SAMPLES.map((s, i) => `<button class="tool demo-btn" data-i="${i}">${s.label}</button>`).join('')}
      </div>
      <div class="result-zone" id="resultZone"></div>
    </div>
    <div class="card">
      <div class="mc-sec"><span class="mc-sec-emoji">📚</span>材料库与追问</div>
      <div style="display:flex;gap:8px;align-items:center;margin:8px 0">
        <button class="tool" id="uploadFileBtn">📎 上传材料（TXT/MD/PDF）</button>
        <input type="file" id="fileUploadInput" accept=".txt,.md,.pdf" hidden>
        <span id="fileList" style="font-size:12px;color:#888"></span>
      </div>
      <div style="display:flex;gap:8px;margin-top:10px">
        <input type="text" id="askInput" placeholder="对材料提问，如：视频有什么要求？" style="flex:1;padding:8px;border:1px solid #d8d5ef;border-radius:8px">
        <button class="btn btn-primary" id="askBtn">提问</button>
      </div>
      <div id="askResult" style="margin-top:10px"></div>
    </div>`

  const zone = mount.querySelector('#resultZone')

  function toast(msg) {
    let t = document.getElementById('toast')
    if (!t) {
      t = document.createElement('div')
      t.id = 'toast'
      t.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:10px 18px;border-radius:8px;z-index:9999;font-size:14px;box-shadow:0 4px 16px rgba(0,0,0,.2);transition:opacity .3s;'
      document.body.appendChild(t)
    }
    t.textContent = msg
    t.style.opacity = '1'
    clearTimeout(t._timer)
    t._timer = setTimeout(() => t.style.opacity = '0', 2500)
  }

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
      const imgNotice = state.resultFromImage
        ? `<div style="background:#fff4e0;color:#b36b00;padding:8px 12px;border-radius:8px;font-size:13px;margin-bottom:10px">🤖 当前结果由图片识别生成，建议您核对原文，如有错漏请及时修改</div>` : ''
      zone.innerHTML = imgNotice + renderMatter(state.analyzeResult) + `
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
    const pdfFile = mount.querySelector('#pdfInput').files[0]
    if (!text && !imgFile && !pdfFile) { alert('先粘贴一段通知，或上传截图/PDF'); return }
    setState({ analyzing: true, analyzeError: '', analyzeResult: null })
    paint()
    try {
      let data
      if (imgFile) {
        data = await analyzeImage(imgFile)
        state.resultFromImage = true
      } else if (pdfFile) {
        data = await analyzePdf(pdfFile)
        state.resultFromImage = false
      } else {
        data = await analyzeNotification(text)
        state.resultFromImage = false
      }
      setState({ analyzing: false, analyzeResult: data })
      // 自动拉准备清单，按 generated/todo_id 覆盖式合并进任务清单
      try {
        const prep = await prepareList({ matter: data })
        const due = data && data.deadline && data.deadline.due_at
          ? data.deadline.due_at.slice(0, 10) : new Date().toISOString().slice(0, 10)
        const srcText = text
        const generated = (prep.todo_list || []).map((t, i) => ({
          id: 9000 + i,
          todo_id: t.todo_id,
          title: t.action,
          date: due,
          done: t.status === 'completed',
          doneAt: t.status === 'completed' ? new Date().toISOString().slice(0, 10) : '',
          generated: true,
          source_ref: t.source_ref || null,
          sourceText
        }))
        const manual = state.tasks.filter(t => !t.generated)
        state.tasks = [...manual, ...generated]
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
  mount.querySelector('#pdfBtn').onclick = () => mount.querySelector('#pdfInput').click()
  mount.querySelector('#pdfInput').onchange = (e) => {
    const f = e.target.files[0]
    if (!f) return
    if (f.size > 10 * 1024 * 1024) { toast('PDF 不能超过 10MB'); e.target.value = ''; return }
    toast('已选 PDF：' + f.name)
  }
  mount.querySelector('#imgInput').onchange = (e) => {
    const f = e.target.files[0]
    if (!f) return
    if (f.size > 5 * 1024 * 1024 || !/jpeg|jpg|png|webp/i.test(f.type)) {
      toast('图片过大或格式不支持（仅 JPG/PNG/WEBP，≤5MB）')
      e.target.value = ''
      return
    }
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

  // 材料库：上传 + 列表 + 追问
  async function refreshFileList() {
    const files = await listFiles().catch(() => [])
    mount.querySelector('#fileList').textContent = files.length ? `已上传 ${files.length} 个文件` : ''
  }
  refreshFileList()
  mount.querySelector('#uploadFileBtn').onclick = () => mount.querySelector('#fileUploadInput').click()
  mount.querySelector('#fileUploadInput').onchange = async (e) => {
    const f = e.target.files[0]
    if (!f) return
    if (f.size > 10 * 1024 * 1024) { toast('文件不能超过 10MB'); return }
    try {
      await uploadFile(f)
      toast('上传成功')
      refreshFileList()
    } catch (err) { toast(err.message) }
  }
  mount.querySelector('#askBtn').onclick = async () => {
    const q = mount.querySelector('#askInput').value.trim()
    if (!q) return
    const out = mount.querySelector('#askResult')
    out.innerHTML = '<div style="color:#888;font-size:13px">思考中…</div>'
    try {
      const res = await askQuestion({ question: q })
      out.innerHTML = `<div style="background:#f6f5ff;padding:10px;border-radius:8px;font-size:13px;line-height:1.7">${res.answer || '没有找到依据'}</div>` +
        (res.sources && res.sources.length ? `<div style="margin-top:6px;font-size:12px;color:#888">出处：${res.sources.map(s => s.filename + ' · 片段' + (s.chunk_id || '')).join('、')}</div>` : '')
    } catch (err) { out.innerHTML = `<div style="color:#c0392b;font-size:13px">${err.message}</div>` }
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
