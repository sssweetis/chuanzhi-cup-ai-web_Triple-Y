import './styles.css'
import { state } from './state.js'
import { renderProfileCard } from './components/ProfileCard.js'
import { renderCalendar } from './components/Calendar.js'
import { renderInputPanel } from './components/InputPanel.js'
import { renderTaskList } from './components/TaskList.js'
import { renderCheckForm } from './components/CheckForm.js'

function boot() {
  const app = document.getElementById('app')
  app.innerHTML = `
    <div class="orb orb1"></div><div class="orb orb2"></div><div class="orb orb3"></div>
    <div class="app">
      <div class="topbar"><h1>智办<span>·</span>通知转任务</h1><div class="slogan">粘贴一段通知，剩下的我帮你记着</div></div>
      <div class="layout">
        <div class="left">
          <div id="profileMount"></div>
          <div id="calMount"></div>
        </div>
        <div class="right">
          <div id="inputMount"></div>
          <div id="listMount"></div>
          <div id="checkMount"></div>
        </div>
      </div>
    </div>`
  renderAll()
  state.onUpdate = renderAll
}

function renderAll() {
  renderProfileCard(document.getElementById('profileMount'))
  renderCalendar(document.getElementById('calMount'))
  renderInputPanel(document.getElementById('inputMount'))
  renderTaskList(document.getElementById('listMount'))
  renderCheckForm(document.getElementById('checkMount'))
}

boot()
