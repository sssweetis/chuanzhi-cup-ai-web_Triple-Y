// 10/18 用户情况填写；10/19：把结果分成 已准备 / 缺少 / 需要确认 三类
// POST /api/check 收 { notification_id, profile:{team_size,has_doc,has_video,has_teacher_confirm}, checked_material_ids }
import { checkProfile } from '../api.js'

const MATERIALS = [
  { id: 'm1', name: '作品演示视频（≤3 分钟）' },
  { id: 'm2', name: '项目说明文档（PPT）' },
  { id: 'm3', name: '成绩单复印件' },
  { id: 'm4', name: '报名表' }
]

export function renderCheckForm(mount, notificationId = 'demo-notice') {
  mount.innerHTML = `
    <div class="card">
      <div class="list-title">我们队的情况</div>
      <div class="sub">勾选已具备的材料，系统把材料分成"已准备 / 缺少 / 需要确认"</div>
      <div class="field"><label>团队人数</label><input type="number" id="fTeamSize" value="3" min="1" max="10"></div>
      <div class="field"><label>是否已有说明文档</label>
        <select id="fHasDoc"><option value="yes">有</option><option value="no">没有</option><option value="unknown">不确定</option></select>
      </div>
      <div class="field"><label>是否已有演示视频</label>
        <select id="fHasVideo"><option value="no">没有</option><option value="yes">有</option><option value="unknown">不确定</option></select>
      </div>
      <div class="field"><label>是否需要指导老师签字</label>
        <select id="fHasTeacher"><option value="unknown">不确定</option><option value="yes">需要</option><option value="no">不需要</option></select>
      </div>
      <div class="field"><label>已备材料</label>
        ${MATERIALS.map(m => `<label class="chk"><input type="checkbox" value="${m.id}"> ${m.name}</label>`).join('')}
      </div>
      <div class="in-foot">
        <button class="btn btn-primary" id="checkBtn">提交核对</button>
      </div>
      <div id="checkResult"></div>
    </div>`

  // 前端本地兜底分类（后端没通时也能看到三类结果）
  function localClassify(profile, checked) {
    const ready = [], missing = [], needConfirm = []
    MATERIALS.forEach(m => {
      if (checked.includes(m.id)) ready.push(m.name)
      else missing.push(m.name)
    })
    if (profile.has_doc === null || profile.has_doc === undefined && mount.querySelector('#fHasDoc').value === 'unknown') needConfirm.push('说明文档是否必须？需向主办方确认')
    if (mount.querySelector('#fHasVideo').value === 'unknown') needConfirm.push('演示视频是否必须？需向主办方确认')
    if (mount.querySelector('#fHasTeacher').value === 'unknown') needConfirm.push('指导老师签字要求？需向主办方确认')
    return { ready, missing, needConfirm }
  }

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
    const teacherVal = mount.querySelector('#fHasTeacher').value
    const profile = {
      team_size: Number(mount.querySelector('#fTeamSize').value),
      has_doc: mount.querySelector('#fHasDoc').value === 'yes',
      has_video: mount.querySelector('#fHasVideo').value === 'yes',
      has_teacher_confirm: teacherVal === 'unknown' ? null : teacherVal === 'yes'
    }
    const box = mount.querySelector('#checkResult')
    box.textContent = '核对中…'
    try {
      const res = await checkProfile({ notification_id: notificationId, profile, checked_material_ids: checked })
      // 后端若返回 ready/missing/need_confirm 就用，否则本地算
      const buckets = res && (res.ready || res.missing || res.needConfirm)
        ? { ready: res.ready || [], missing: res.missing || [], needConfirm: res.needConfirm || [] }
        : localClassify(profile, checked)
      box.innerHTML = renderBuckets(buckets)
    } catch (err) {
      // 后端没通：本地兜底展示
      box.innerHTML = renderBuckets(localClassify(profile, checked)) +
        `<div class="error-box" style="margin-top:8px">后端暂未连通，以上为前端本地分类：${err.message}</div>`
    }
  }
}
