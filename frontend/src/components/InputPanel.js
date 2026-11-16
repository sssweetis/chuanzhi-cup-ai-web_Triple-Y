// @ts-nocheck -- 渐进迁移：核心状态与请求层已启用类型检查。
import { state, setState, toDateKey } from '../state.js'
import {
  analyzeNotification,
  prepareList,
  analyzeImage,
  analyzePdf,
  uploadFile,
  listFiles,
  askQuestion,
  checkDate,
  compareNotifications,
  savePrepareList,
  getEvidence,
} from '../api2.js'
import { SAMPLES } from '../mockMatters.js'
import {
  AppError,
  assertAnalysisResult,
  isCancelled,
  normalizeError,
  renderErrorState,
  userErrorMessage,
} from '../errors.js'
import { closeModal, escapeHtml as esc, openModal, setButtonBusy, showToast as toast, wait } from '../util.js'
import { renderAnalysisProgress } from './AnalysisProgress.js'

let fileListCache = { loaded: false, count: 0, error: '' }
let fileListRequest = null
let activeAnalysis = null
let cancelIntent = ''
let matterRenderer = null
let matterRendererRequest = null
let moreMenuGlobalReady = false

function closeOpenMoreMenu({ restoreFocus = false } = {}) {
  const menu = document.querySelector('#moreMenu')
  const trigger = document.querySelector('#moreBtn')
  if (!menu || !trigger) return
  menu.hidden = true
  menu.classList.remove('is-open')
  trigger.setAttribute('aria-expanded', 'false')
  if (restoreFocus) trigger.focus()
}

function initMoreMenuGlobal() {
  if (moreMenuGlobalReady) return
  moreMenuGlobalReady = true
  document.addEventListener('click', (event) => {
    if (!(event.target instanceof Element)) return
    if (event.target.closest('.more-wrap')) return
    closeOpenMoreMenu()
  })
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeOpenMoreMenu({ restoreFocus: true })
  })
}

async function loadMatterRenderer() {
  if (matterRenderer) return matterRenderer
  if (!matterRendererRequest) {
    matterRendererRequest = import('./ModeCard.js').then((module) => {
      matterRenderer = module.renderMatter
      return matterRenderer
    })
  }
  return matterRendererRequest
}

function analysisReference(error) {
  return normalizeError(error)
}

export function renderInputPanel(mount) {
  initMoreMenuGlobal()
  mount.innerHTML = `
    <div class="card in input-card">
      <div class="section-head">
        <div class="lab">输入通知</div>
        <div class="section-meta">文字、截图、PDF 都可以</div>
      </div>
      <textarea id="taskInput" rows="4" maxlength="10000" aria-label="通知原文" placeholder="例如：请于 10 月 25 日 18:00 前提交比赛报名表和成绩单，逾期不候。"></textarea>
      <div class="in-bar">
        <div class="in-bar-left">
          <div class="primary-actions">
            <button class="tool" id="imgBtn" type="button">📷 截图/图片</button>
            <button class="tool" id="pdfBtn" type="button">📄 PDF</button>
          </div>
          <button class="tool" id="compareBtn" type="button">🔄 补充通知对比</button>
          <div class="more-wrap">
            <button class="tool more-trigger" id="moreBtn" type="button" aria-label="更多输入方式" aria-haspopup="menu" aria-expanded="false" aria-controls="moreMenu">
              ＋ 更多 <span aria-hidden="true">▾</span>
            </button>
            <div class="more-menu" id="moreMenu" role="menu" aria-label="更多输入与示例" hidden>
              <button class="more-item" id="micBtn" type="button" role="menuitem">语音输入<span>把通知说出来</span></button>
              <button class="more-item" id="attachBtn" type="button" role="menuitem">上传附件<span>Word / PDF</span></button>
              <button class="more-item" id="demoToggle" type="button" role="menuitem" aria-expanded="false">示例数据<span>离线预览</span></button>
              <div class="demo-row" id="demoRow" hidden>
                ${SAMPLES.map((s, i) => `<button class="tool demo-btn" data-i="${i}" type="button" role="menuitem">${s.label}</button>`).join('')}
              </div>
              <button class="more-item" id="quickDemo" type="button" role="menuitem">一键体验<span>直接打开示例数据</span></button>
              <label class="more-date">截止日期<input type="date" id="taskDate"></label>
            </div>
          </div>
          <input type="file" id="imgInput" accept="image/jpeg,image/png,image/webp" hidden>
          <input type="file" id="pdfInput" accept=".pdf" hidden>
          <input type="file" id="fileInput" accept=".doc,.docx,.pdf" multiple hidden>
        </div>
        <div class="in-bar-right">
          <span class="char-count" id="charCount">0 / 10000</span>
          <button class="btn btn-primary analyze-btn" id="analyzeBtn" type="button" ${state.analyzing ? 'disabled aria-busy="true"' : ''}>
            ${state.analyzing ? '<span class="spinner" aria-hidden="true"></span>解析中…' : 'AI 智能解析'}
          </button>
        </div>
      </div>
      <div class="img-preview-row" id="imgPreviewRow" hidden>
        <img id="imgPreview" alt="通知截图预览">
        <button class="tool" id="imgRemove" type="button">✕ 移除图片</button>
      </div>
      <div class="chips" id="chipBox"></div>
      <div class="attach-note">支持文字型 PDF（≤10MB、≤30 页）；扫描版请改用截图。</div>
      <div class="result-zone" id="resultZone"></div>
    </div>
    <div class="card library-card">
      <div class="mc-sec"><span class="mc-sec-emoji">📚</span>材料库与追问</div>
      <div class="library-toolbar">
        <button class="tool" id="uploadFileBtn" type="button">📎 上传材料（TXT/MD/PDF）</button>
        <input type="file" id="fileUploadInput" accept=".txt,.md,.pdf" hidden>
        <span id="fileList" class="file-list">暂无已上传材料</span>
      </div>
      <div class="ask-row">
        <input type="text" id="askInput" placeholder="对材料提问，如：视频有什么要求？">
        <button class="btn btn-primary" id="askBtn" type="button">提问</button>
      </div>
      <div id="askResult" class="ask-result"><div class="inline-empty">暂无追问记录</div></div>
    </div>`

  // 点"出处"按钮 → 弹窗展示原文片段
  mount.querySelector('#resultZone').addEventListener('click', (e) => {
    const btn = e.target.closest('.src-btn')
    if (btn) {
      const quote = btn.dataset.quote
      const type = btn.dataset.type,
        id = btn.dataset.id
      let mask = document.getElementById('srcMask')
      if (!mask) {
        mask = document.createElement('div')
        mask.id = 'srcMask'
        mask.className = 'mask'
        mask.innerHTML = `<div class="modal">
          <div class="modal-kicker">原文出处</div>
          <h3>📄 原文依据</h3>
          <div class="src-quote-modal" id="srcQuote"></div>
          <div class="modal-foot"><button class="btn btn-primary" id="srcClose" type="button">关闭</button></div>
        </div>`
        document.body.appendChild(mask)
        mask.querySelector('#srcClose').onclick = () => closeModal(mask)
      }
      const qEl = mask.querySelector('#srcQuote')
      if (type && state.analyzeResult) {
        qEl.textContent = '加载中…'
        getEvidence({ matter: state.analyzeResult, target_type: type, target_id: id })
          .then((res) => {
            if (res && res.found) {
              qEl.innerHTML =
                (res.is_suggestion ? '<div class="notice notice-warn">⚠ 系统建议（无原文依据）</div>' : '') +
                '“' +
                esc(res.quote || '') +
                '”'
            } else {
              qEl.textContent = quote ? '“' + quote + '”' : '暂无原文'
            }
          })
          .catch(() => {
            qEl.textContent = quote ? '“' + quote + '”' : '暂无原文'
          })
      } else {
        qEl.textContent = quote ? '“' + quote + '”' : '暂无原文'
      }
      openModal(mask, { initialFocus: '#srcClose' })
      return
    }
    if (e.target.closest('#confirmUpdateBtn')) {
      const m = state.compareMatter || state.analyzeResult
      const matterId = m && (m.matter_id || m.id)
      if (matterId) {
        const todos =
          state.comparePreviewTodo ||
          state.tasks
            .filter((t) => t.generated)
            .map((t) => ({ action: t.title, status: t.done ? 'completed' : 'not_started' }))
        savePrepareList({ matter_id: matterId, todo_list: todos })
          .then(() => toast('已保存到任务清单'))
          .catch((error) => toast(userErrorMessage(error, '保存没有完成，请稍后再试。'), 'error'))
      } else {
        toast('已确认，任务清单将按新通知更新')
      }
    }
  })

  function focusEditor() {
    const input = mount.querySelector('#taskInput')
    input?.focus()
    input?.setSelectionRange(input.value.length, input.value.length)
  }

  function openAnalysisHelp() {
    document.getElementById('helpBtn')?.click()
  }

  function clearAnalysisState(notice = '') {
    setState(
      {
        analyzing: false,
        analyzeError: null,
        analysisSlow: false,
        analysisStage: 'preparing',
        analysisNotice: notice,
      },
      { notify: false },
    )
    paint()
  }

  function handleAnalysisError(error) {
    const normalized = normalizeError(error)
    setState(
      {
        analyzing: false,
        analyzeError: normalized,
        analysisSlow: false,
        analysisStage: 'preparing',
        analysisNotice: '',
      },
      { notify: false },
    )
    const errorButton = mount.querySelector('#analyzeBtn')
    setButtonBusy(errorButton, false)
    paint()
  }

  function cancelAnalysis(intent = 'cancel') {
    cancelIntent = intent
    if (!activeAnalysis) {
      clearAnalysisState(intent === 'edit' ? '已取消，可以继续修改通知。' : '')
      paint()
      if (intent === 'edit') focusEditor()
      return
    }
    activeAnalysis.controller.abort('user_cancelled')
  }

  function showSlowWarning() {
    if (!state.analyzing) return
    setState({ analysisSlow: true }, { notify: false })
    paint()
  }

  function paint() {
    const zone = mount.querySelector('#resultZone')
    if (!zone) return
    if (state.analyzing && state.analysisSlow) {
      renderErrorState(zone, new AppError({ code: 'timeout' }), {
        onContinue: () => {
          setState({ analysisSlow: false }, { notify: false })
          paint()
        },
        onRetry: () => cancelAnalysis('retry'),
        onEdit: () => cancelAnalysis('edit'),
        onHelp: openAnalysisHelp,
      })
      return
    }
    if (state.analyzing) {
      renderAnalysisProgress(zone, {
        stage: state.analysisStage,
        onCancel: () => cancelAnalysis('cancel'),
      })
      return
    }
    if (state.analyzeError) {
      renderErrorState(zone, state.analyzeError, {
        onRetry: () => {
          clearAnalysisState()
          runAnalyze()
        },
        onEdit: () => {
          clearAnalysisState()
          paint()
          focusEditor()
        },
        onReupload: () => {
          clearAnalysisState()
          paint()
          const pdf = mount.querySelector('#pdfInput')?.files[0]
          mount.querySelector(pdf ? '#pdfBtn' : '#imgBtn')?.click()
        },
        onHelp: openAnalysisHelp,
      })
      return
    }
    if (state.analyzeResult) {
      if (!matterRenderer) {
        zone.innerHTML =
          '<div class="loading-state"><span class="spinner spinner-dark" aria-hidden="true"></span><span>正在展开解析结果…</span></div>'
        loadMatterRenderer()
          .then(() => paint())
          .catch((error) => handleAnalysisError(error))
        return
      }
      const imgNotice = state.resultFromImage
        ? '<div class="notice notice-warn">当前结果由图片识别生成，建议核对原文，如有错漏请及时修改。</div>'
        : ''
      const demoNotice = state.resultIsDemo
        ? '<div class="demo-data-banner" role="status"><b>示例数据</b><span>当前内容仅用于体验，不是从你的通知中解析出的真实任务。</span></div>'
        : ''
      zone.innerHTML =
        demoNotice +
        imgNotice +
        matterRenderer(state.analyzeResult) +
        `
        <div class="add-task-bar">
          <button class="btn btn-primary" id="addTaskBtn" type="button">＋ 把这个通知加入任务清单</button>
        </div>`
      mount.querySelector('#addTaskBtn').onclick = () => {
        const matter = state.analyzeResult
        const selectedDate = toDateKey(mount.querySelector('#taskDate')?.value)
        const due = selectedDate || toDateKey(matter?.deadline?.due_at)
        const title = matter?.title || '新任务'
        const srcText = mount.querySelector('#taskInput').value.trim()
        if (!state.tasks.some((task) => task.title === title)) {
          state.tasks.push({
            id: Date.now(),
            title,
            date: due,
            done: false,
            sourceText: srcText,
            isDemo: state.resultIsDemo,
          })
        }
        const todos = matter?.todo_list || matter?.step_list || []
        todos.forEach((item) => {
          const name = item.action || item.title || item.name
          if (!name) return
          const taskDue = toDateKey(item.due_at) || due
          if (!state.tasks.some((task) => task.title === name)) {
            state.tasks.push({
              id: Date.now() + Math.random(),
              title: name,
              date: taskDue,
              done: item.status === 'completed',
              generated: true,
              isDemo: state.resultIsDemo,
            })
          }
        })
        setState({ tasks: state.tasks })
        toast('已加入任务清单')
      }
      return
    }
    const notice = state.analysisNotice
      ? `<div class="notice notice-info" role="status">${esc(state.analysisNotice)}</div>`
      : ''
    zone.innerHTML = `${notice}<div class="ph"><span class="ph-icon" aria-hidden="true">↗</span><span>分析结果会显示在这里</span></div>`
  }

  async function prepareGeneratedTasks(data, sourceText) {
    try {
      const prepared = await prepareList({ matter: data })
      const due = toDateKey(data?.deadline?.due_at)
      const generated = (prepared.todo_list || []).map((item, index) => ({
        id: 9000 + index,
        todo_id: item.todo_id,
        title: item.action,
        date: toDateKey(item.due_at) || due,
        done: item.status === 'completed',
        doneAt: item.status === 'completed' ? new Date().toISOString().slice(0, 10) : '',
        generated: true,
        source_ref: item.source_ref || null,
        sourceText,
      }))
      const manual = state.tasks.filter((task) => !task.generated)
      setState({ tasks: [...manual, ...generated] })
    } catch {
      // 任务解析成功时，准备清单失败不阻塞主流程。
    }
  }

  function showConfirmation(data) {
    if (!Array.isArray(data.confirmation_needed) || !data.confirmation_needed.length) return
    let mask = document.getElementById('confirmMask')
    if (!mask) {
      mask = document.createElement('div')
      mask.id = 'confirmMask'
      mask.className = 'mask'
      mask.innerHTML = `<div class="modal">
        <div class="modal-kicker">图片识别</div>
        <h3>请确认以下内容</h3>
        <div id="confirmList" class="modal-copy-list"></div>
        <div class="modal-foot"><button class="btn btn-primary" id="confirmOk" type="button">确认无误</button></div>
      </div>`
      document.body.appendChild(mask)
      mask.querySelector('#confirmOk').onclick = () => closeModal(mask)
    }
    mask.querySelector('#confirmList').innerHTML = data.confirmation_needed
      .map((item) => `<div>· ${esc(item)}</div>`)
      .join('')
    openModal(mask, { initialFocus: '#confirmOk' })
  }

  async function runAnalyze() {
    if (state.analyzing || activeAnalysis) return
    const text = mount.querySelector('#taskInput').value.trim()
    const imgFile = mount.querySelector('#imgInput').files[0]
    const pdfFile = mount.querySelector('#pdfInput').files[0]
    if (!text && !imgFile && !pdfFile) {
      toast('先粘贴一段通知，或上传截图/PDF')
      focusEditor()
      return
    }

    const controller = new AbortController()
    activeAnalysis = { controller }
    cancelIntent = ''
    const analyzeButton = mount.querySelector('#analyzeBtn')
    setButtonBusy(analyzeButton, true, '解析中…')
    setState(
      {
        analyzing: true,
        analyzeError: null,
        analyzeResult: null,
        analysisSlow: false,
        analysisNotice: '',
        analysisStage: imgFile ? 'upload' : 'extract',
      },
      { notify: false },
    )
    paint()

    const updateStage = async (stage, delay = 40) => {
      if (controller.signal.aborted) throw new AppError({ code: 'cancelled' })
      setState({ analysisStage: stage }, { notify: false })
      paint()
      if (delay) await wait(delay)
    }

    try {
      if (imgFile || pdfFile) {
        await updateStage('upload', 80)
      }
      await updateStage('extract', 80)
      await updateStage('llm', 0)

      let data
      let fromImage = false
      if (imgFile) {
        data = await analyzeImage(imgFile, {
          signal: controller.signal,
          onTimeoutWarning: showSlowWarning,
        })
        fromImage = true
      } else if (pdfFile) {
        data = await analyzePdf(pdfFile, {
          signal: controller.signal,
          onTimeoutWarning: showSlowWarning,
        })
      } else {
        data = await analyzeNotification(text, {
          signal: controller.signal,
          onTimeoutWarning: showSlowWarning,
        })
      }
      if (controller.signal.aborted) throw new AppError({ code: 'cancelled' })

      await updateStage('schema', 60)
      const validated = assertAnalysisResult(data)
      await updateStage('date', 40)
      let dateCheck = null
      if (validated.deadline?.due_at) {
        try {
          dateCheck = await checkDate({ deadline: validated.deadline.due_at }, { signal: controller.signal })
        } catch (error) {
          if (isCancelled(error)) throw error
        }
      }
      await updateStage('complete', 120)
      if (controller.signal.aborted) throw new AppError({ code: 'cancelled' })

      activeAnalysis = null
      setButtonBusy(mount.querySelector('#analyzeBtn'), false)
      setState({
        analyzing: false,
        analyzeError: null,
        analysisSlow: false,
        analysisStage: 'preparing',
        analysisNotice: '',
        analyzeResult: validated,
        resultFromImage: fromImage,
        resultIsDemo: false,
      })

      if (dateCheck) {
        const activeZone = mount.querySelector('#resultZone')
        if (activeZone) {
          const tip = document.createElement('div')
          tip.id = 'dateCheckTip'
          tip.className = 'notice notice-info'
          const dateMessage =
            dateCheck.message ||
            dateCheck.suggestion ||
            (dateCheck.suggested_finish_at
              ? `建议完成时间：${dateCheck.suggested_finish_at}`
              : dateCheck.recommended_date
                ? `建议日期：${dateCheck.recommended_date}`
                : '')
          tip.textContent = dateMessage ? '日期核对：' + dateMessage : '日期核对已完成'
          activeZone.appendChild(tip)
        }
      }
      const dateInput = mount.querySelector('#taskDate')
      if (dateInput && !dateInput.value) dateInput.value = toDateKey(validated.deadline?.due_at)
      showConfirmation(validated)
      void prepareGeneratedTasks(validated, text)
    } catch (error) {
      const normalized = analysisReference(error)
      const intent = cancelIntent
      cancelIntent = ''
      activeAnalysis = null
      setButtonBusy(mount.querySelector('#analyzeBtn'), false)

      if (normalized.code === 'cancelled' || controller.signal.aborted) {
        clearAnalysisState(
          intent === 'edit' ? '已取消，可以继续修改通知。' : '已取消，输入内容和文件选择仍保留在当前页面。',
        )
        paint()
        if (intent === 'retry') runAnalyze()
        else if (intent === 'edit') focusEditor()
        return
      }
      handleAnalysisError(normalized)
    }
  }

  paint()
  const moreBtn = mount.querySelector('#moreBtn')
  const moreMenu = mount.querySelector('#moreMenu')

  function setMoreMenuOpen(open, focusFirst = false) {
    moreMenu.hidden = !open
    moreMenu.classList.toggle('is-open', open)
    moreBtn.setAttribute('aria-expanded', String(open))
    if (open && focusFirst) {
      requestAnimationFrame(() => {
        moreMenu.querySelector('.more-item:not([hidden]), input:not([hidden])')?.focus()
      })
    }
  }

  moreBtn.onclick = () => setMoreMenuOpen(moreMenu.hidden)
  moreBtn.onkeydown = (event) => {
    if (event.key !== 'ArrowDown') return
    event.preventDefault()
    setMoreMenuOpen(true, true)
  }
  moreMenu.onkeydown = (event) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      closeOpenMoreMenu({ restoreFocus: true })
      return
    }
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
    const items = Array.from(moreMenu.querySelectorAll('button, input')).filter((item) => item.offsetParent !== null)
    const index = items.indexOf(document.activeElement)
    const direction = event.key === 'ArrowDown' ? 1 : -1
    const next = items[(index + direction + items.length) % items.length]
    event.preventDefault()
    next?.focus()
  }

  function activateSample(index) {
    const sample = SAMPLES[Number(index)]
    if (!sample) return
    if (state.analyzing || activeAnalysis) {
      toast('当前解析还没结束，请先取消或等待完成。')
      return
    }
    setState({
      analyzing: false,
      analyzeError: null,
      analyzeResult: sample.data,
      resultIsDemo: Boolean(sample.isDemo),
    })
    setMoreMenuOpen(false)
  }

  mount.querySelector('#analyzeBtn').onclick = runAnalyze
  mount.querySelector('#imgBtn').onclick = () => mount.querySelector('#imgInput').click()
  mount.querySelector('#pdfBtn').onclick = () => mount.querySelector('#pdfInput').click()
  mount.querySelector('#pdfInput').onchange = (e) => {
    const f = e.target.files[0]
    if (!f) return
    if (f.size > 10 * 1024 * 1024) {
      handleAnalysisError(new AppError({ code: 'file_too_large', status: 413 }))
      e.target.value = ''
      return
    }
    clearAnalysisState()
    const oldChip = mount.querySelector('[data-pdf-chip]')
    if (oldChip) oldChip.remove()
    const chip = document.createElement('span')
    chip.className = 'chip chip-file'
    chip.dataset.pdfChip = 'true'
    chip.textContent = `PDF · ${f.name}`
    mount.querySelector('#chipBox').appendChild(chip)
    toast('已选 PDF：' + f.name)
  }
  mount.querySelector('#imgInput').onchange = (e) => {
    const f = e.target.files[0]
    if (!f) return
    if (f.size > 5 * 1024 * 1024 || !/jpeg|jpg|png|webp/i.test(f.type)) {
      handleAnalysisError(
        new AppError({
          code: f.size > 5 * 1024 * 1024 ? 'file_too_large' : 'unsupported_media',
          status: f.size > 5 * 1024 * 1024 ? 413 : 415,
        }),
      )
      e.target.value = ''
      return
    }
    clearAnalysisState()
    const reader = new FileReader()
    reader.onload = () => {
      mount.querySelector('#imgPreviewRow').hidden = false
      mount.querySelector('#imgPreview').src = reader.result
      mount.dataset.imgData = reader.result
    }
    reader.readAsDataURL(f)
  }
  mount.querySelector('#imgRemove').onclick = () => {
    mount.querySelector('#imgPreviewRow').hidden = true
    mount.querySelector('#imgPreview').src = ''
    mount.dataset.imgData = ''
    mount.querySelector('#imgInput').value = ''
    clearAnalysisState()
  }

  // 材料库：上传 + 列表 + 追问
  function paintFileList() {
    const target = mount.querySelector('#fileList')
    if (!target) return
    target.textContent =
      fileListCache.error || (fileListCache.count ? `已上传 ${fileListCache.count} 个文件` : '暂无已上传材料')
  }
  async function refreshFileList(force = false) {
    if (force) fileListCache = { loaded: false, count: 0, error: '' }
    if (fileListCache.loaded) {
      paintFileList()
      return
    }
    if (fileListRequest) return
    paintFileList()
    fileListRequest = listFiles()
      .then((files) => {
        fileListCache = { loaded: true, count: files.length, error: '' }
      })
      .catch(() => {
        fileListCache = { loaded: true, count: 0, error: '材料列表暂不可用' }
      })
      .finally(() => {
        fileListRequest = null
        paintFileList()
      })
    await fileListRequest
  }
  if (fileListCache.loaded) paintFileList()
  else {
    const target = mount.querySelector('#fileList')
    if (target) target.textContent = '材料列表加载中…'
    refreshFileList()
  }
  mount.querySelector('#uploadFileBtn').onclick = () => mount.querySelector('#fileUploadInput').click()
  mount.querySelector('#fileUploadInput').onchange = async (e) => {
    const f = e.target.files[0]
    if (!f) return
    if (f.size > 10 * 1024 * 1024) {
      toast('文件不能超过 10MB', 'error')
      e.target.value = ''
      return
    }
    const btn = mount.querySelector('#uploadFileBtn')
    setButtonBusy(btn, true, '上传中…')
    e.target.value = ''
    try {
      await uploadFile(f)
      toast('材料上传成功', 'success')
      await refreshFileList(true)
    } catch (error) {
      toast(userErrorMessage(error, '材料上传失败，请稍后再试。'), 'error')
    } finally {
      setButtonBusy(btn, false)
    }
  }
  mount.querySelector('#askBtn').onclick = async () => {
    const btn = mount.querySelector('#askBtn')
    if (btn.disabled) return
    const q = mount.querySelector('#askInput').value.trim()
    if (!q) {
      toast('先输入想追问的内容')
      mount.querySelector('#askInput').focus()
      return
    }
    const out = mount.querySelector('#askResult')
    setButtonBusy(btn, true, '思考中…')
    out.innerHTML =
      '<div class="loading-inline"><span class="spinner spinner-dark" aria-hidden="true"></span><span>正在检索材料并组织回答…</span></div>'
    try {
      const res = await askQuestion({ question: q })
      const noEvidence = res.found_evidence === false
      const banner = noEvidence
        ? '<div class="notice notice-warn">未找到依据，已停止生成。请补充材料或调整问题后再试。</div>'
        : ''
      const chunks = res.evidence_chunks || res.sources || []
      const chunkHtml = chunks.length
        ? '<div class="evidence-label">📌 原文出处</div>' +
          chunks
            .map(
              (c) =>
                `<div class="evidence-row">${esc(c.doc_name || c.filename || '材料')} · 片段 ${esc(c.chunk_id || '-')} · 匹配度 ${c.score != null ? Math.round(c.score * 100) + '%' : ''}</div>`,
            )
            .join('')
        : ''
      out.innerHTML = noEvidence
        ? banner
        : banner + `<div class="answer-box">${esc(res.answer || '')}</div>` + chunkHtml
    } catch (error) {
      renderErrorState(out, normalizeError(error), {
        onRetry: () => mount.querySelector('#askBtn').click(),
        onEdit: () => mount.querySelector('#askInput').focus(),
        onHelp: openAnalysisHelp,
      })
    } finally {
      setButtonBusy(btn, false)
    }
  }
  mount.querySelector('#demoToggle').onclick = () => {
    const row = mount.querySelector('#demoRow')
    row.hidden = !row.hidden
    mount.querySelector('#demoToggle').setAttribute('aria-expanded', String(!row.hidden))
  }
  mount.querySelector('#quickDemo').onclick = () => {
    mount.querySelector('#taskInput').value =
      '请于10月25日18:00前提交奖学金报名表和成绩单，材料审核由王老师负责，审核通过后10月30日前缴费100元，11月1日打印准考证。'
    syncInput()
    activateSample(0)
  }
  mount.querySelector('#compareBtn').onclick = () => openCompareDialog()

  function openCompareDialog() {
    let mask = document.getElementById('compareMask')
    if (!mask) {
      mask = document.createElement('div')
      mask.id = 'compareMask'
      mask.className = 'mask'
      mask.innerHTML = `<div class="modal modal-wide">
        <div class="modal-kicker">补充通知</div>
        <h3>对比两版通知</h3>
        <form id="compareForm">
          <div class="compare-fields">
            <label class="field">
              <span>原通知</span>
              <textarea id="compareOld" rows="7" placeholder="粘贴原通知内容"></textarea>
              <span class="compare-drop" data-compare-drop="old">也可以拖入 TXT / MD 文件</span>
            </label>
            <label class="field">
              <span>补充通知</span>
              <textarea id="compareNew" rows="7" placeholder="粘贴补充通知内容"></textarea>
              <span class="compare-drop" data-compare-drop="new">也可以拖入 TXT / MD 文件</span>
            </label>
          </div>
          <div class="modal-foot">
            <button class="btn btn-ghost" type="button" data-compare-close>取消</button>
            <button class="btn btn-primary" type="submit" id="compareSubmit">开始对比</button>
          </div>
        </form>
      </div>`
      document.body.appendChild(mask)
    }
    const oldInput = mask.querySelector('#compareOld')
    const newInput = mask.querySelector('#compareNew')
    oldInput.value = ''
    newInput.value = ''
    bindCompareDrop(mask.querySelector('[data-compare-drop="old"]'), oldInput)
    bindCompareDrop(mask.querySelector('[data-compare-drop="new"]'), newInput)
    mask.querySelector('[data-compare-close]').onclick = () => closeModal(mask)
    mask.querySelector('#compareForm').onsubmit = async (event) => {
      event.preventDefault()
      const oldN = oldInput.value.trim()
      const newN = newInput.value.trim()
      if (!oldN || !newN) {
        toast(!oldN ? '请粘贴原通知' : '请粘贴补充通知')
        ;(!oldN ? oldInput : newInput).focus()
        return
      }
      closeModal(mask)
      const compareBtn = mount.querySelector('#compareBtn')
      const zone = mount.querySelector('#resultZone')
      setButtonBusy(compareBtn, true, '对比中…')
      zone.innerHTML =
        '<div class="loading-state"><span class="spinner spinner-dark" aria-hidden="true"></span><span>正在对比两版通知并检查受影响的待办…</span></div>'
      try {
        const res = await compareNotifications({
          left: { filename: '原通知', text: oldN },
          right: { filename: '补充通知', text: newN },
        })
        const diff = res.diff || {}
        const changes = (diff.changes || [])
          .map((c) => {
            const type = ['added', 'removed', 'changed'].includes(c.type) ? c.type : 'info'
            return `<div class="diff-change diff-${type}">${esc(c.text || c.note || '')}</div>`
          })
          .join('')
        const affectedTodos = diff.affected_todos || []
        const affected = affectedTodos.map((t) => `<li>· ${esc(t)}</li>`).join('')
        const previewTodos = diff.preview_todo_list || affectedTodos || []
        state.comparePreviewTodo = previewTodos.length
          ? previewTodos.map((item) => (typeof item === 'string' ? { action: item, status: 'not_started' } : item))
          : undefined
        state.compareMatter = res.right?.matter || res.left?.matter || state.analyzeResult
        zone.innerHTML = `<div class="matter-card compare-result">
          <div class="mc-title-row"><h3>通知对比结果</h3><span class="status-chip status-info">已对比</span></div>
          <div class="diff-list">${changes || '<div class="inline-empty">两份通知未发现明确差异</div>'}</div>
          ${affected ? `<div class="affected-box"><b>受影响待办</b><ul>${affected}</ul></div>` : ''}
          <div class="add-task-bar"><button class="btn btn-primary" id="confirmUpdateBtn" type="button">✅ 确认并更新任务清单</button></div>
        </div>`
        zone.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      } catch (error) {
        renderErrorState(zone, normalizeError(error), {
          onRetry: () => mount.querySelector('#compareBtn').click(),
          onEdit: () => openCompareDialog(),
          onHelp: openAnalysisHelp,
        })
      } finally {
        setButtonBusy(compareBtn, false)
      }
    }
    openModal(mask, { initialFocus: oldInput })
  }

  function bindCompareDrop(dropZone, textarea) {
    dropZone.ondragenter = (event) => {
      event.preventDefault()
      dropZone.classList.add('is-dragging')
    }
    dropZone.ondragover = (event) => event.preventDefault()
    dropZone.ondragleave = () => dropZone.classList.remove('is-dragging')
    dropZone.ondrop = async (event) => {
      event.preventDefault()
      dropZone.classList.remove('is-dragging')
      const file = event.dataTransfer.files[0]
      if (!file) return
      if (!/\.(txt|md)$/i.test(file.name)) {
        toast('这里支持 TXT 或 MD 文件；图片和 PDF 请先通过解析入口识别。', 'error')
        return
      }
      if (file.size > 2 * 1024 * 1024) {
        toast('文字文件不能超过 2MB。', 'error')
        return
      }
      textarea.value = await file.text()
      textarea.focus()
    }
  }
  mount.querySelector('#taskInput').value = localStorage.getItem('zhiban-input') || ''
  function syncInput(fromUser = false) {
    const ta = mount.querySelector('#taskInput')
    localStorage.setItem('zhiban-input', ta.value)
    mount.querySelector('#charCount').textContent = `${ta.value.length} / 10000`
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 300) + 'px'
    if (state.analyzeError || state.analysisNotice) {
      setState({ analyzeError: null, analysisNotice: '' }, { notify: false })
      paint()
    }
    // 输入框清空时，下方分析结果也一起清掉
    if (fromUser && !ta.value.trim() && state.analyzeResult) {
      setState({ analyzeResult: null, analyzeError: null, resultIsDemo: false })
    }
  }
  mount.querySelector('#taskInput').oninput = () => syncInput(true)
  syncInput()
  mount.querySelectorAll('.demo-btn').forEach((button) => {
    button.onclick = () => activateSample(button.dataset.i)
  })
  mount.querySelector('#attachBtn').onclick = () => {
    closeOpenMoreMenu()
    mount.querySelector('#fileInput').click()
  }
  mount.querySelector('#fileInput').onchange = (e) => {
    const box = mount.querySelector('#chipBox')
    Array.from(e.target.files).forEach((f) => {
      const c = document.createElement('span')
      c.className = 'chip'
      c.textContent = f.name
      box.appendChild(c)
    })
  }
  // 语音输入（浏览器原生识别，不支持则提示）
  mount.querySelector('#micBtn').onclick = () => {
    closeOpenMoreMenu()
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) {
      toast('当前浏览器不支持语音输入（推荐 Chrome）')
      return
    }
    const rec = new SR()
    rec.lang = 'zh-CN'
    rec.onresult = (e) => {
      mount.querySelector('#taskInput').value = e.results[0][0].transcript
    }
    rec.start()
  }
}
