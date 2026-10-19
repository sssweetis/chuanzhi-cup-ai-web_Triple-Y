import { state } from '../state.js'

export function renderProfileCard(mount) {
  mount.innerHTML = `
    <div class="card profile">
      <div class="avatar" id="avatarBox">${(state.profile.nick || 'T').charAt(0).toUpperCase()}</div>
      <div class="who">
        <div class="nick">${state.profile.nick || 'Triple'}</div>
        <div class="hi">hi, ${state.profile.nick || 'Triple'}! 今天也要稳稳推进</div>
      </div>
      <button class="btn btn-ghost btn-sm" id="openUserModal">个人中心</button>
    </div>`
  document.getElementById('avatarBox').style.background = state.profile.color
  mount.querySelector('#openUserModal').onclick = async () => {
    // 懒加载：用户中心弹窗只在第一次点开时才下载代码
    const { openUserModal } = await import('./UserModal.js')
    openUserModal()
  }
}
