export const STATUS_META = {
  todo: { label: 'К выполнению', color: 'grey' },
  in_progress: { label: 'В работе', color: 'orange' },
  in_review: { label: 'На проверке', color: 'purple' },
  done: { label: 'Готово', color: 'green' },
}

export const STATUS_FILTERS = [
  { value: null, label: 'Все' },
  { value: 'todo', label: 'К выполнению' },
  { value: 'in_progress', label: 'В работе' },
  { value: 'in_review', label: 'На проверке' },
  { value: 'done', label: 'Готово' },
]

// Путь задачи слева направо — по нему строятся шаги и полоса прогресса.
export const STATUS_ORDER = ['todo', 'in_progress', 'in_review', 'done']

// Следующий шаг для кнопки в карточке задачи: на «Готово» — откат в работу.
export const NEXT_STEP = {
  todo: { status: 'in_progress', label: 'Взять в работу' },
  in_progress: { status: 'in_review', label: 'Отправить на проверку' },
  in_review: { status: 'done', label: 'Готово' },
  done: { status: 'in_progress', label: 'Вернуть в работу' },
}

// Просрочена: срок прошёл, а задача не закрыта. todayKey — 'YYYY-MM-DD' (utils/dateKey).
export function isOverdue(task, todayKey) {
  return !!task.due_date && task.status !== 'done' && task.due_date < todayKey
}

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
