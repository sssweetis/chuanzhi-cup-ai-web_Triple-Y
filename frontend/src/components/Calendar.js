import { state, setState, daysLeft } from '../state.js'
import { escapeHtml } from '../util.js'

let view = null
let previousTasks = new Map()
let lastFocusDate = ''

function pad(n) {
  return String(n).padStart(2, '0')
}

function dateParts(dateStr) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(dateStr || ''))
  if (!match) return null
  const year = Number(match[1])
  const month = Number(match[2]) - 1
  const day = Number(match[3])
  const date = new Date(year, month, day)
  if (date.getFullYear() !== year || date.getMonth() !== month || date.getDate() !== day) return null
  return { year, month, day }
}

function taskKey(task, index) {
  return String(task.id ?? `${task.title || 'task'}-${task.date || 'date'}-${index}`)
}

function tooltipLine(tag, className, text) {
  const element = document.createElement(tag)
  if (className) element.className = className
  element.textContent = text
  return element
}

export function renderCalendar(mount) {
  const now = new Date()
  const curY = now.getFullYear()
  const curM = now.getMonth()
  const curD = now.getDate()
  const currentTaskMap = new Map()

  state.tasks.forEach((task, index) => {
    if (dateParts(task.date)) currentTaskMap.set(taskKey(task, index), task.date)
  })

  const activeDates = state.tasks
    .filter((task) => !task.done && dateParts(task.date))
    .map((task) => task.date)
    .sort()

  let newlyAddedDate = ''
  state.tasks.forEach((task, index) => {
    const key = taskKey(task, index)
    if (!task.done && dateParts(task.date) && (!previousTasks.has(key) || previousTasks.get(key) !== task.date)) {
      newlyAddedDate = task.date
    }
  })

  if (!view) {
    const initial = activeDates[0] ? dateParts(activeDates[0]) : null
    view = initial ? { y: initial.year, m: initial.month } : { y: curY, m: curM }
  } else if (newlyAddedDate) {
    const next = dateParts(newlyAddedDate)
    view = { y: next.year, m: next.month }
  } else if (state.focusDate && state.focusDate !== lastFocusDate) {
    const focused = dateParts(state.focusDate)
    if (focused) view = { y: focused.year, m: focused.month }
  }

  lastFocusDate = state.focusDate || ''
  previousTasks = currentTaskMap

  mount.innerHTML = `
    <div class="card calendar-card">
      <div class="cal-head">
        <div>
          <div class="ym" id="calYMD"></div>
          <div class="cal-subtitle">截止日自动标记</div>
        </div>
        <div class="cal-nav">
          <button class="icon-btn" data-m="-1" type="button" aria-label="上个月">‹</button>
          <button class="icon-btn" data-m="1" type="button" aria-label="下个月">›</button>
        </div>
      </div>
      <div class="cal-scroll">
        <table class="cal" aria-label="任务日历">
          <thead><tr><th>日</th><th>一</th><th>二</th><th>三</th><th>四</th><th>五</th><th>六</th></tr></thead>
          <tbody id="calBody"></tbody>
        </table>
      </div>
      <div class="cal-legend">
        <span><i class="dot over"></i>逾期</span>
        <span><i class="dot hot"></i>紧急</span>
        <span><i class="dot"></i>普通待办</span>
      </div>
      <div class="cal-tooltip" id="calTooltip" role="tooltip" hidden></div>
    </div>`

  const card = mount.querySelector('.calendar-card')
  const tooltip = mount.querySelector('#calTooltip')
  let tipDate = ''

  function hideTooltip() {
    tipDate = ''
    tooltip.hidden = true
  }

  function showTooltip(cell, dateStr, items) {
    if (!items.length) return
    tipDate = dateStr
    const parts = dateParts(dateStr)
    const remaining = items.filter((item) => !item.done)
    const overdue = daysLeft(dateStr) < 0
    const urgent = daysLeft(dateStr) >= 0 && daysLeft(dateStr) <= 2

    const head = document.createElement('div')
    head.className = 'cal-tip-head'
    head.append(tooltipLine('span', 'cal-tip-date', `${parts.month + 1}月${parts.day}日`))
    head.append(
      tooltipLine(
        'span',
        `cal-tip-status ${overdue ? 'is-overdue' : urgent ? 'is-urgent' : 'is-normal'}`,
        overdue ? '逾期' : urgent ? '紧急' : '待办',
      ),
    )

    const summary = tooltipLine(
      'div',
      'cal-tip-summary',
      remaining.length ? `${remaining.length} 项任务待处理` : '当天任务已全部完成',
    )
    const list = document.createElement('ul')
    list.className = 'cal-tip-list'
    items.slice(0, 4).forEach((item) => {
      const row = document.createElement('li')
      if (item.done) row.classList.add('is-done')
      row.textContent = item.title
      list.append(row)
    })
    tooltip.replaceChildren(head, summary, list)
    if (items.length > 4) tooltip.append(tooltipLine('div', 'cal-tip-more', `还有 ${items.length - 4} 项`))
    tooltip.hidden = false

    const cardRect = card.getBoundingClientRect()
    const cellRect = cell.getBoundingClientRect()
    const tipWidth = Math.min(232, cardRect.width - 20)
    const center = cellRect.left - cardRect.left + cellRect.width / 2
    const left = Math.max(tipWidth / 2 + 10, Math.min(center, cardRect.width - tipWidth / 2 - 10))
    tooltip.style.left = `${left}px`
    tooltip.style.top = `${cellRect.bottom - cardRect.top + 6}px`

    requestAnimationFrame(() => {
      if (tipDate !== dateStr) return
      const tipRect = tooltip.getBoundingClientRect()
      if (tipRect.bottom > window.innerHeight - 8) {
        tooltip.style.top = `${Math.max(8, cellRect.top - cardRect.top - tipRect.height - 6)}px`
      }
    })
  }

  function draw() {
    mount.querySelector('#calYMD').textContent = `${view.y}年${view.m + 1}月`
    hideTooltip()
    const first = new Date(view.y, view.m, 1).getDay()
    const days = new Date(view.y, view.m + 1, 0).getDate()
    const prevDays = new Date(view.y, view.m, 0).getDate()
    const todayStr = `${curY}-${pad(curM + 1)}-${pad(curD)}`
    const byDate = {}

    state.tasks.forEach((task) => {
      if (!task.title || !dateParts(task.date)) return
      if (!byDate[task.date]) byDate[task.date] = []
      byDate[task.date].push({ title: task.title, done: Boolean(task.done) })

      const taskYear = dateParts(task.date).year
      if (Array.isArray(task.steps)) {
        task.steps.forEach((step) => {
          const match = String(step.title || '').match(/(\d{1,2})月(\d{1,2})日/)
          if (!match) return
          const stepMonth = Number(match[1])
          const stepDay = Number(match[2])
          const stepDate = `${taskYear}-${pad(stepMonth)}-${pad(stepDay)}`
          if (!dateParts(stepDate)) return
          if (!byDate[stepDate]) byDate[stepDate] = []
          byDate[stepDate].push({ title: step.title, done: Boolean(step.done) })
        })
      }
    })

    const cells = []
    for (let i = 0; i < first; i++) cells.push(`<td class="other blank">${prevDays - first + 1 + i}</td>`)
    for (let d = 1; d <= days; d++) {
      const ds = `${view.y}-${pad(view.m + 1)}-${pad(d)}`
      const items = (byDate[ds] || []).sort((a, b) => Number(a.done) - Number(b.done))
      const remainingDays = daysLeft(ds)
      const status = remainingDays < 0 ? 'over' : remainingDays <= 2 ? 'hot' : ''
      const dot = items.length ? `<span class="dot ${status}"></span>` : ''
      const classes = [ds === todayStr ? 'today' : '', items.length ? 'has-task' : ''].filter(Boolean).join(' ')
      const label = items.length
        ? `${view.m + 1}月${d}日，${items.length} 项任务：${items.map((item) => item.title).join('、')}`
        : ''
      cells.push(
        `<td class="${classes}" data-date="${items.length ? ds : ''}"${items.length ? ` tabindex="0" role="button" aria-label="${escapeHtml(label)}"` : ''}><span class="cal-num">${d}</span>${dot}</td>`,
      )
    }
    while (cells.length % 7) cells.push('<td class="other blank"></td>')

    const rows = []
    for (let i = 0; i < cells.length; i += 7) rows.push(`<tr>${cells.slice(i, i + 7).join('')}</tr>`)
    mount.querySelector('#calBody').innerHTML = rows.join('')

    mount.querySelectorAll('td.has-task').forEach((cell) => {
      const ds = cell.dataset.date
      const items = byDate[ds] || []
      cell.addEventListener('mouseenter', () => showTooltip(cell, ds, items))
      cell.addEventListener('mouseleave', hideTooltip)
      cell.addEventListener('focus', () => showTooltip(cell, ds, items))
      cell.addEventListener('blur', hideTooltip)
      cell.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ') return
        event.preventDefault()
        cell.click()
      })
      cell.addEventListener('click', () => {
        hideTooltip()
        setState({ focusDate: ds })
        setTimeout(() => {
          const row = document.querySelector('.task-row.focus-row')
          if (row) row.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }, 50)
      })
    })
  }

  draw()
  mount.querySelectorAll('.icon-btn').forEach((button) => {
    button.onclick = () => {
      view.m += Number(button.dataset.m)
      if (view.m < 0) {
        view.m = 11
        view.y--
      }
      if (view.m > 11) {
        view.m = 0
        view.y++
      }
      draw()
    }
  })
}
