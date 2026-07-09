const formatter = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long' })

export function formatDueDate(isoDateString) {
  if (!isoDateString) return '—'
  return formatter.format(new Date(isoDateString))
}
