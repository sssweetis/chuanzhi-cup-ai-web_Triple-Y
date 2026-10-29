import './styles.css'
import { state } from './state.js'
import { renderProfileCard } from './components/ProfileCard.js'
import { renderCalendar } from './components/Calendar.js'
import { renderInputPanel } from './components/InputPanel.js'
import { renderTaskList } from './components/TaskList.js'

function boot() {
  const app = document.getElementById('app')
  app.innerHTML = `
    <div id="splash" style="position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;background:radial-gradient(circle at 50% 40%,#a5a0f0 0%,#8b86e8 60%,#6f68d8 100%);transition:opacity .8s ease;">
      <div style="color:#fff;font-size:88px;font-weight:800;letter-spacing:2px;text-shadow:0 8px 40px rgba(255,255,255,.25);opacity:0;transform:scale(.8);animation:spIn 1.2s cubic-bezier(.2,.8,.2,1) forwards;">Triple Y</div>
    </div>
    <style>@keyframes spIn{to{opacity:1;transform:scale(1);}}</style>
    <div class="orb orb1"></div><div class="orb orb2"></div><div class="orb orb3"></div>
    <div class="app">
      <div class="topbar"><h1>Triple Y<span>·</span>通知转任务</h1><div class="slogan">粘贴一段通知，剩下的我帮你记着</div><button class="btn btn-ghost btn-sm" id="helpBtn">❓ 使用说明</button></div>
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
  setTimeout(() => {
    const s = document.getElementById('splash')
    if (s) { s.style.opacity = '0'; setTimeout(() => s.remove(), 900) }
  }, 1800)
  state.onUpdate = renderAll
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
        <h3>❓ 三步上手</h3>
        <ol class="help-list">
          <li><b>粘贴通知</b>：把辅导员/群里的通知原文粘到输入框，或点"📷 截图"上传通知截图。</li>
          <li><b>点"AI 智能解析"</b>：自动拆出截止时间、流程步骤、材料清单。</li>
          <li><b>加入任务清单</b>：点"＋ 加入任务清单"，下面的日历和清单会自动排好。</li>
        </ol>
        <div class="help-tip">💡 小技巧：点任务可展开加子任务，点日历上的圆点可跳到对应任务。</div>
        <div class="modal-foot"><button class="btn btn-primary" id="helpClose">开始使用</button></div>
      </div>`
      document.body.appendChild(mask)
      mask.onclick = (e) => { if (e.target === mask) mask.classList.remove('show') }
      mask.querySelector('#helpClose').onclick = () => mask.classList.remove('show')
    }
    mask.classList.add('show')
  }
}

function renderAll() {
  renderProfileCard(document.getElementById('profileMount'))
  renderCalendar(document.getElementById('calMount'))
  renderInputPanel(document.getElementById('inputMount'))
  renderTaskList(document.getElementById('listMount'))
}

boot()
