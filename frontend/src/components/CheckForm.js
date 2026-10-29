// 用户情况填写（C 对齐 10/20）：
// POST /api/check body = { matter: state.analyzeResult, profile:{people_count,has_doc,has_video,has_teacher_confirm}, checked_material_ids }
// 后端返回 checked / missing_required / missing_optional / need_confirm / profile_issues / summary → 前端映射成三类
import { state, setState } from '../state.js'
import { checkProfile } from '../api.js'

const FALLBACK_MATERIALS = [
  { id: 'm1', name: '作品演示视频（≤3 分钟）' },
  { id: 'm2', name: '项目说明文档（PPT）' },
  { id: 'm3', name: '成绩单复印件' },
  { id: 'm4', name: '报名表' }
]

export function renderCheckForm(mount) {
  // 材料列表优先从最近解析结果取，没有解析结果时用示例列表
  const materials = Array.isArray(state.analyzeResult && state.analyzeResult.materials) && state.analyzeResult.materials.length
    ? state.analyzeResult.materials.map(m => ({ id: m.material_id, name: m.material_name }))
    : FALLBACK_MATERIALS

  mount.innerHTML = `
    <div class="card">
      <div class="list-title">我们队的情况</div>
      <div class="sub">勾选已具备的材料，系统分成"已准备 / 缺少 / 需要确认"</div>
      <div class="field"><label>团队人数</label><input type="number" id="fPeopleCount" value="3" min="1" max="10"></div>
      <div class="field"><label>年级</label>
        <select id="fGrade"><option value="freshman">大一</option><option value="sophomore_plus">大二及以上</option></select>
      </div>
      <div class="field"><label>是否已有说明文档</label>
        <select id="fHasDoc"><option value="unknown">不确定</option><option value="yes">有</option><option value="no">没有</option></select>
      </div>
      <div class="field"><label>是否已有演示视频</label>
        <select id="fHasVideo"><option value="unknown">不确定</option><option value="yes">有</option><option value="no">没有</option></select>
      </div>
      <div class="field"><label>是否需要指导老师签字</label>
        <select id="fHasTeacher"><option value="unknown">不确定</option><option value="yes">需要</option><option value="no">不需要</option></select>
      </div>
      <div class="field"><label>已备材料</label>
        ${materials.map(m => `<label class="chk"><input type="checkbox" value="${m.id}"> ${m.name}</label>`).join('')}
      </div>
      <div class="in-foot">
        <button class="btn btn-primary" id="checkBtn">提交核对</button>
      </div>
      <div id="checkResult"></div>
    </div>`

  function renderBuckets(b) {
    const row = (cls, label, items, emoji) => items && items.length
      ? `<div class="bucket ${cls}"><div class="bucket-head">${emoji} ${label}（${items.length}）</div><ul>${items.map(i => `<li>${i}</li>`).join('')}</ul></div>`
      : `<div class="bucket ${cls}"><div class="bucket-head">${emoji} ${label}（0）</div><div class="bucket-empty">无</div></div>`
    return `<div class="buckets">
      ${row('b-ok', '已准备', b.ready, '✅')}
      ${row('b-bad', '缺少', b.missing, '❌')}
      ${row('b-warn', '需要确认', b.needConfirm, '❓')}
    </div>`
  }

  mount.querySelector('#checkBtn').onclick = async () => {
    const checked = Array.from(mount.querySelectorAll('input[type=checkbox]:checked')).map(c => c.value)
    // "不确定"的 key 不传，避免被当成 false
    const profile = { people_count: Number(mount.querySelector('#fPeopleCount').value), grade: mount.querySelector('#fGrade').value }
    const doc = mount.querySelector('#fHasDoc').value
    const video = mount.querySelector('#fHasVideo').value
    const teacher = mount.querySelector('#fHasTeacher').value
    if (doc !== 'unknown') profile.has_doc = doc === 'yes'
    if (video !== 'unknown') profile.has_video = video === 'yes'
    if (teacher !== 'unknown') profile.has_teacher_confirm = teacher === 'yes'

    const box = mount.querySelector('#checkResult')
    box.textContent = '核对中…'
    try {
      const body = { profile, checked_material_ids: checked }
      if (state.analyzeResult) body.matter = state.analyzeResult
      const res = await checkProfile(body)
      // C 返回 checked / missing_required / missing_optional / need_confirm / profile_issues / summary
      const buckets = {
        ready: res.checked || [],
        missing: [...(res.missing_required || []), ...(res.missing_optional || [])],
        needConfirm: [...(res.need_confirm || []), ...(res.profile_issues || [])]
      }
      box.innerHTML = renderBuckets(buckets)
    } catch (err) {
      // 后端没通：本地兜底
      const ready = [], missing = [], needConfirm = []
      materials.forEach(m => (checked.includes(m.id) ? ready : missing).push(m.name))
      if (doc === 'unknown') needConfirm.push('说明文档是否必须？需向主办方确认')
      if (video === 'unknown') needConfirm.push('演示视频是否必须？需向主办方确认')
      if (teacher === 'unknown') needConfirm.push('指导老师签字要求？需向主办方确认')
      box.innerHTML = renderBuckets({ ready, missing, needConfirm }) +
        `<div class="error-box" style="margin-top:8px">后端暂未连通，以上为前端本地分类：${err.message}</div>`
    }
  }
}
