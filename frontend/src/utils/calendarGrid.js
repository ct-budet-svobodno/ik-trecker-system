function startOfWeekMonday(date) {
  const result = new Date(date)
  const isoWeekday = (result.getDay() + 6) % 7 // 0 = Monday ... 6 = Sunday
  result.setDate(result.getDate() - isoWeekday)
  result.setHours(0, 0, 0, 0)
  return result
}

export function isSameDay(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
}

/**
 * Возвращает массив недель (по 7 дней) для месяца, включая хвосты соседних
 * месяцев, неделя начинается с понедельника.
 */
export function getMonthGrid(year, month) {
  const firstOfMonth = new Date(year, month, 1)
  const gridStart = startOfWeekMonday(firstOfMonth)

  const lastOfMonth = new Date(year, month + 1, 0)
  const gridEnd = startOfWeekMonday(lastOfMonth)
  gridEnd.setDate(gridEnd.getDate() + 6)

  const weeks = []
  let current = new Date(gridStart)
  while (current <= gridEnd) {
    const week = []
    for (let i = 0; i < 7; i++) {
      week.push({ date: new Date(current), isCurrentMonth: current.getMonth() === month })
      current.setDate(current.getDate() + 1)
    }
    weeks.push(week)
  }
  return weeks
}
