// Локальный «день» YYYY-MM-DD без сдвига часового пояса.
export function dayKey(date) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

// 'YYYY-MM-DD' → локальная Date (а не UTC).
export function parseDateOnly(value) {
  const [y, m, d] = value.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function addDays(date, n) {
  const copy = new Date(date)
  copy.setDate(copy.getDate() + n)
  return copy
}

// Понедельник недели, в которую попадает date (локально).
export function startOfWeek(date) {
  const copy = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const weekday = (copy.getDay() + 6) % 7 // Пн=0 … Вс=6
  copy.setDate(copy.getDate() - weekday)
  return copy
}
