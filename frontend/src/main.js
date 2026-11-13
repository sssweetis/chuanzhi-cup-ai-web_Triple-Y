// @ts-nocheck -- 渐进迁移：入口在组件迁移完成后补严格 DOM 类型。
import './styles.css'
import { renderProfileCard } from './components/ProfileCard.js'
import { renderCalendar } from './components/Calendar.js'
import { renderInputPanel } from './components/InputPanel.js'
import { renderTaskList } from './components/TaskList.js'
import { closeModal, initModalA11y, openModal } from './util.js'

function boot() {
  initModalA11y()
  const app = document.getElementById('app')
  app.innerHTML = `
    <div id="splash" class="splash" role="presentation">
      <div class="splash-mark">Triple Y</div>
    </div>
    <div class="app">
      <header class="topbar">
        <div class="brand-block">
          <h1>Triple Y<span>·</span>通知转任务</h1>
          <div class="slogan">粘贴一段通知，剩下的我帮你记着</div>
        </div>
        <div class="topbar-actions">
          <a class="btn btn-ghost btn-sm prototype-link" href="/prototypes/index.html" target="_blank" rel="noopener">新版样板</a>
          <button class="btn btn-ghost btn-sm" id="helpBtn"><span class="help-icon" aria-hidden="true">?</span>使用说明</button>
        </div>
      </header>
      <div class="layout">
        <div class="left">
          <div id="profileMount"></div>
          <div id="calMount"></div>
        </div>
        <div class="right">
          <div id="inputMount"></div>
          <div id="listMount"></div>
        </div>
      </div>
    </div>`
  renderAll()
  const splash = document.getElementById('splash')
  const splashSeen = sessionStorage.getItem('triple-y-splash-seen') === '1'
  const dismissSplash = () => {
    if (!splash || splash.classList.contains('is-leaving')) return
    splash.classList.add('is-leaving')
    sessionStorage.setItem('triple-y-splash-seen', '1')
    window.setTimeout(() => splash.remove(), 150)
  }
  if (splashSeen) splash.remove()
  else {
    splash.addEventListener('click', dismissSplash)
    window.setTimeout(dismissSplash, 650)
  }
  window.addEventListener('zhiban:state-change', (event) => {
    renderChanged(event.detail && event.detail.keys)
  })
  // 倒计时只刷新任务列表，避免重渲染输入框导致正在填的内容被重置
  setInterval(() => renderTaskList(document.getElementById('listMount')), 60000)

  // 使用说明弹窗
  document.getElementById('helpBtn').onclick = () => {
    let mask = document.getElementById('helpMask')
    if (!mask) {
      mask = document.createElement('div')
      mask.id = 'helpMask'
      mask.className = 'mask'
      mask.innerHTML = `<div class="modal">
        <div class="modal-kicker">使用说明</div>
        <h3>三步上手</h3>
        <ol class="help-list">
          <li><b>粘贴通知</b>：把辅导员/群里的通知原文粘到输入框，或点"📷 截图"上传通知截图。</li>
          <li><b>点"AI 智能解析"</b>：自动拆出截止时间、流程步骤、材料清单。</li>
          <li><b>加入任务清单</b>：点"＋ 加入任务清单"，下面的日历和清单会自动排好。</li>
        </ol>
        <div class="help-tip">💡 小技巧：点任务可展开加子任务，点日历上的圆点可跳到对应任务。</div>
        <div class="modal-foot"><button class="btn btn-primary" id="helpClose">开始使用</button></div>
      </div>`
      document.body.appendChild(mask)
      mask.querySelector('#helpClose').onclick = () => closeModal(mask)
    }
    openModal(mask, { initialFocus: '#helpClose' })
  }
}

function renderAll() {
  renderProfileCard(document.getElementById('profileMount'))
  renderCalendar(document.getElementById('calMount'))
  renderInputPanel(document.getElementById('inputMount'))
  renderTaskList(document.getElementById('listMount'))
}

function renderChanged(keys = []) {
  const changed = new Set(keys)
  if (!changed.size) {
    renderAll()
    return
  }
  if (changed.has('profile')) renderProfileCard(document.getElementById('profileMount'))
  if (changed.has('tasks') || changed.has('focusDate')) renderCalendar(document.getElementById('calMount'))
  if (['analyzeResult', 'resultFromImage'].some((key) => changed.has(key))) {
    renderInputPanel(document.getElementById('inputMount'))
  }
  if (changed.has('tasks') || changed.has('focusDate') || changed.has('activeTab')) {
    renderTaskList(document.getElementById('listMount'))
  }
}

boot()
