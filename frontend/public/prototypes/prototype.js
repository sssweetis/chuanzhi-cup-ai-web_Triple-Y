document.documentElement.classList.add('has-js')

document.querySelectorAll('.task-tabs').forEach(tabs => {
  tabs.addEventListener('click', event => {
    const button = event.target.closest('button')
    if (!button) return
    tabs.querySelectorAll('button').forEach(item => item.classList.remove('is-active'))
    button.classList.add('is-active')
  })
})

document.querySelectorAll('.calendar-day[data-selectable]').forEach(day => {
  const select = () => {
    day.closest('.month-grid')?.querySelectorAll('.calendar-day').forEach(item => item.classList.remove('is-selected'))
    day.classList.add('is-selected')
  }
  day.addEventListener('click', select)
  day.addEventListener('keydown', event => {
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    select()
  })
})

requestAnimationFrame(() => document.body.classList.add('is-ready'))
