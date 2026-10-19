import { state, daysLeft } from '../state.js'

export function renderCalendar(mount) {
  const now = new Date()
  const y = now.getFullYear(), m = now.getMonth()
  mount.innerHTML = `
    <div class="card">
      <div class="cal-head">
        <div class="ym">${y}年${m + 1}月</div>
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
  let view = { y, m }
  function draw() {
    const first = new Date(view.y, view.m, 1).getDay()
    const days = new Date(view.y, view.m + 1, 0).getDate()
    const prevDays = new Date(view.y, view.m, 0).getDate()
    const todayStr = `${y}-${String(m + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
    const hot = {}
    state.tasks.forEach(t => { if (!t.done && daysLeft(t.date) <= 2) hot[t.date] = 1 })
    let cells = []
    for (let i = 0; i < first; i++) cells.push(`<td class="other blank">${prevDays - first + 1 + i}</td>`)
    for (let d = 1; d <= days; d++) {
      const ds = `${view.y}-${String(view.m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
      const cls = ds === todayStr ? 'today' : ''
      const dot = state.tasks.some(t => !t.done && t.date === ds)
        ? `<span class="dot ${hot[ds] ? 'hot' : ''}"></span>` : ''
      cells.push(`<td class="${cls}">${d}${dot}</td>`)
    }
    const rows = []
    for (let i = 0; i < cells.length; i += 7) rows.push('<tr>' + cells.slice(i, i + 7).join('') + '</tr>')
    mount.querySelector('#calBody').innerHTML = rows.join('')
  }
  draw()
  mount.querySelectorAll('.icon-btn').forEach(b => b.onclick = () => {
    view.m += Number(b.dataset.m)
    if (view.m < 0) { view.m = 11; view.y-- }
    if (view.m > 11) { view.m = 0; view.y++ }
    draw()
  })
}
