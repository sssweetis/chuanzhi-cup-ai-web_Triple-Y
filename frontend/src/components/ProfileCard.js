import { state } from '../state.js'
import { escapeHtml } from '../util.js'

export function renderProfileCard(mount) {
  const av = state.profile.avatarUrl
  const nick = escapeHtml(state.profile.nick || 'Triple')
  mount.innerHTML = `
    <div class="card profile">
      <div class="avatar" id="avatarBox">${av ? `<img src="${escapeHtml(av)}" alt="" loading="lazy" decoding="async">` : nick.charAt(0).toUpperCase()}</div>
      <div class="who">
        <div class="nick">${nick}</div>
        <div class="hi">hi, ${nick}! 今天也要稳稳推进</div>
      </div>
      <button class="btn btn-ghost btn-sm profile-action" id="openUserModal">个人中心</button>
    </div>`
  if (!av) document.getElementById('avatarBox').style.background = state.profile.color
  mount.querySelector('#openUserModal').onclick = async () => {
    // 懒加载：用户中心弹窗只在第一次点开时才下载代码
    const { openUserModal } = await import('./UserModal.js')
    openUserModal()
  }
}
