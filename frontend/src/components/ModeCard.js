// 按 data.mode 渲染：simple 不渲染 materials/steps（设计如此，不补空模块）
export function ModeCard(data) {
  if (!data) return ''
  const chips = { simple: '极简', standard: '标准', complex: '完整流程' }
  let html = `<div class="mode-chip">${chips[data.mode] || data.mode}</div>`
  html += `<div class="mode-title">${data.title || '未命名任务'}</div>`
  if (data.deadline) html += `<div class="mode-row">截止：${data.deadline}</div>`
  if (data.location) html += `<div class="mode-row">地点：${data.location}</div>`
  // standard 才有 materials
  if (data.materials && data.materials.length) {
    html += `<div class="mode-sub">材料清单</div><ul class="mode-list">${data.materials.map(m => `<li>${m}</li>`).join('')}</ul>`
  }
  if (data.notes && data.notes.length) {
    html += `<div class="mode-sub">注意事项</div><ul class="mode-list">${data.notes.map(n => `<li>${n}</li>`).join('')}</ul>`
  }
  // complex 才有 steps
  if (data.steps && data.steps.length) {
    html += `<div class="mode-sub">流程</div><ol class="mode-steps">${data.steps.map((s, i) => `<li><b>${i + 1}.</b> ${s.name || s}${s.owner ? `（${s.owner}）` : ''}</li>`).join('')}</ol>`
  }
  if (data.warnings && data.warnings.length) {
    html += `<div class="mode-warn">预警：${data.warnings.join('；')}</div>`
  }
  return html
}
