import { state, daysLeft } from '../state.js'

export function renderCalendar(mount) {
  const now = new Date()
  const curY = now.getFullYear(), curM = now.getMonth(), curD = now.getDate()
  let view = { y: curY, m: curM }
  // 自动跳到最早未完成任务所在月（每次渲染都执行，新任务加入后会自动切过去）
  const upcoming = state.tasks.filter(t => !t.done && t.date).map(t => t.date).sort()
  if (upcoming.length) {
    const [y, m] = upcoming[0].split('-').map(Number)
    view = { y, m: m - 1 }
  }

  mount.innerHTML = `
    <div class="card">
      <div class="cal-head">
        <div class="ym" id="calYMD"></div>
        <div class="cal-nav">
          <button class="icon-btn" data-m="-1">‹</button>
          <button class="icon-btn" data-m="1">›</button>
        </div>
      </div>
      <table class="cal">
        <thead><tr><th>日</th><th>一</th><th>二</th><th>三</th><th>四</th><th>五</th><th>六</th></tr></thead>
        <tbody id="calBody"></tbody>
      </table>
      <div class="cal-legend">
        <span><i style="background:#d93b3b"></i>紧急 DDL</span>
        <span><i style="background:#8b86e8"></i>普通待办</span>
      </div>
    </div>`

  function pad(n) { return String(n).padStart(2, '0') }

  function draw() {
    mount.querySelector('#calYMD').textContent = `${view.y}年${view.m + 1}月`
    const first = new Date(view.y, view.m, 1).getDay()
    const days = new Date(view.y, view.m + 1, 0).getDate()
    const prevDays = new Date(view.y, view.m, 0).getDate()
    const todayStr = `${curY}-${pad(curM + 1)}-${pad(curD)}`
    const hot = {}, overdue = {}
    state.tasks.forEach(t => {
      if (t.done) return
      const n = daysLeft(t.date)
      if (n < 0) overdue[t.date] = 1
      else if (n <= 2) hot[t.date] = 1
    })
    const byDate = {}
    state.tasks.forEach(t => {
      if (!byDate[t.date]) byDate[t.date] = []
      byDate[t.date].push(t.title)
      // 子任务标题里解析日期（如 "12月5日答辩"）
      if (Array.isArray(t.steps)) {
        t.steps.forEach(s => {
          const m = (s.title || '').match(/(\d{1,2})月(\d{1,2})日/)
          if (m) {
            const ds = `${view.y}-${String(m[1]).padStart(2,'0')}-${String(m[2]).padStart(2,'0')}`
            if (!byDate[ds]) byDate[ds] = []
            byDate[ds].push(s.title)
          }
        })
      }
    })
    let cells = []
    for (let i = 0; i < first; i++) cells.push(`<td class="other blank">${prevDays - first + 1 + i}</td>`)
    for (let d = 1; d <= days; d++) {
      const ds = `${view.y}-${pad(view.m + 1)}-${pad(d)}`
      const cls = ds === todayStr ? 'today' : ''
      const dayTasks = byDate[ds] || []
      const dot = dayTasks.length
        ? `<span class="dot ${overdue[ds] ? 'over' : hot[ds] ? 'hot' : ''}"></span>` : ''
      const tip = dayTasks.length ? ` title="${dayTasks.join('\n')}"` : ''
      const tdCls = [cls, dayTasks.length ? 'has-task' : ''].filter(Boolean).join(' ')
      cells.push(`<td class="${tdCls}" data-date="${dayTasks.length ? ds : ''}"${tip}><span class="cal-num">${d}</span>${dot}</td>`)
    }
    const rows = []
    for (let i = 0; i < cells.length; i += 7) rows.push('<tr>' + cells.slice(i, i + 7).join('') + '</tr>')
    mount.querySelector('#calBody').innerHTML = rows.join('')
    // 点有任务的日期 → 滚动到任务清单并高亮当天任务
    mount.querySelectorAll('td.has-task').forEach(td => td.onclick = () => {
      const ds = td.dataset.date
      state.focusDate = ds
      import('../state.js').then(({ setState }) => {
        setState({})
        setTimeout(() => {
          const row = document.querySelector(`.task-row.focus-row`)
          if (row) row.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }, 50)
      })
    })
  }
  draw()
  mount.querySelectorAll('.icon-btn').forEach(b => b.onclick = () => {
    view.m += Number(b.dataset.m)
    if (view.m < 0) { view.m = 11; view.y-- }
    if (view.m > 11) { view.m = 0; view.y++ }
    draw()
  })
}
