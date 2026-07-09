const timeFormatter = new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' })
const monthYearFormatter = new Intl.DateTimeFormat('ru-RU', { month: 'long', year: 'numeric' })

export function formatTime(isoString) {
  if (!isoString) return ''
  return timeFormatter.format(new Date(isoString))
}

export function formatMonthYear(date) {
  return monthYearFormatter.format(date)
}

export function toDatetimeLocalValue(isoString) {
  if (!isoString) return ''
  const date = new Date(isoString)
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}
