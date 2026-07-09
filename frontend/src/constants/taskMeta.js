export const STATUS_META = {
  todo: { label: 'К ВЫПОЛНЕНИЮ', color: 'grey' },
  in_progress: { label: 'В РАБОТЕ', color: 'orange' },
  in_review: { label: 'НА ПРОВЕРКЕ', color: 'purple' },
  done: { label: 'ГОТОВО', color: 'green' },
}

export const STATUS_FILTERS = [
  { value: null, label: 'Все' },
  { value: 'todo', label: 'К выполнению' },
  { value: 'in_progress', label: 'В работе' },
  { value: 'in_review', label: 'На проверке' },
  { value: 'done', label: 'Готово' },
]

// Приоритет — отдельная ось «интенсивности», не пересекается с цветами статусов.
export const PRIORITY_META = {
  low: { label: 'Низкий', tone: 'low' },
  medium: { label: 'Средний', tone: 'medium' },
  high: { label: 'Высокий', tone: 'high' },
}

export const DIRECTION_COLOR_CLASS = {
  violet: 'chip--violet',
  blue: 'chip--blue',
  pink: 'chip--pink',
  green: 'chip--green',
  orange: 'chip--orange',
  cyan: 'chip--cyan',
}
