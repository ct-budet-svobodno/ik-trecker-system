import { dayKey } from './dateKey'

// Порядок шагов задачи — он же порядок сегментов на полосе прогресса.
export const STATUS_STEPS = ['todo', 'in_progress', 'in_review', 'done']

// Главная кнопка в шторке задачи: следующий шаг от текущего статуса.
export const NEXT_STEP = {
  todo: { status: 'in_progress', label: 'Взять в работу' },
  in_progress: { status: 'in_review', label: 'Отправить на проверку' },
  in_review: { status: 'done', label: 'Готово' },
  done: { status: 'in_progress', label: 'Вернуть в работу' },
}

// Задача на этом человеке: исполнитель обычной задачи или один из исполнителей поручения.
export function isAssignedTo(task, userId) {
  if (userId == null) return false
  return task.assignee?.id === userId || (task.assignees ?? []).some((a) => a.user.id === userId)
}

// Сколько исполнителей поручения уже сделали свою часть.
export function assigneesDone(task) {
  return (task.assignees ?? []).filter((a) => a.status === 'done').length
}

export function todayKey() {
  return dayKey(new Date())
}

// Срок прошёл, а задача не закрыта. due_date — 'YYYY-MM-DD', сравниваем строками.
export function isOverdue(task, today = todayKey()) {
  return task.status !== 'done' && !!task.due_date && task.due_date < today
}

// Сколько дней до срока: <0 — просрочено, 0 — сегодня. null — срока нет.
export function daysUntilDue(task) {
  if (!task.due_date) return null
  const [y, m, d] = task.due_date.split('-').map(Number)
  const due = new Date(y, m - 1, d)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  return Math.round((due - today) / 86400000)
}

export function progressStats(tasks, today = todayKey()) {
  const counts = { total: tasks.length, todo: 0, in_progress: 0, in_review: 0, done: 0, overdue: 0 }
  for (const task of tasks) {
    if (task.status in counts) counts[task.status] += 1
    if (isOverdue(task, today)) counts.overdue += 1
  }
  counts.percent = counts.total ? Math.round((counts.done / counts.total) * 100) : 0
  return counts
}

// Сначала то, что горит: просроченные, затем в работе → на проверке → к выполнению,
// внутри — по сроку (без срока в конце). Готовые уходят вниз.
const STATUS_RANK = { in_progress: 0, in_review: 1, todo: 2, done: 3 }

export function byUrgency(a, b, today = todayKey()) {
  const overdue = Number(isOverdue(b, today)) - Number(isOverdue(a, today))
  if (overdue) return overdue
  const rank = STATUS_RANK[a.status] - STATUS_RANK[b.status]
  if (rank) return rank
  if (a.due_date !== b.due_date) {
    if (!a.due_date) return 1
    if (!b.due_date) return -1
    return a.due_date < b.due_date ? -1 : 1
  }
  return b.id - a.id
}
