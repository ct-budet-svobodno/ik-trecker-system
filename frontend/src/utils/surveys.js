// Общее для анкет: типы вопросов, подписи статусов, разбор ошибок API.

export const QUESTION_TYPES = [
  { value: 'text', label: 'Короткий ответ' },
  { value: 'textarea', label: 'Развёрнутый ответ' },
  { value: 'single', label: 'Один вариант' },
  { value: 'multi', label: 'Несколько вариантов' },
  { value: 'scale', label: 'Шкала' },
]

export const STATUS_LABELS = {
  draft: 'Черновик',
  open: 'Идёт',
  closed: 'Закрыта',
}

export function newQuestionId() {
  return Math.random().toString(36).slice(2, 10)
}

// SQLite отдаёт время без зоны, а хранит UTC.
export function parseUtc(iso) {
  if (!iso) return null
  return new Date(/Z|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`)
}

const dateTimeFormatter = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatWhen(iso) {
  const date = parseUtc(iso)
  return date ? dateTimeFormatter.format(date) : ''
}

// 422 от pydantic — массив; берём понятное сообщение из него.
export function apiError(err, fallback) {
  const detail = err.response?.data?.detail
  if (Array.isArray(detail)) {
    const msg = detail[0]?.msg ?? ''
    return msg.replace(/^Value error, /, '') || fallback
  }
  return detail ?? fallback
}

// Ответ человека на вопрос — строкой для таблицы и CSV.
export function answerText(question, value) {
  if (value == null) return ''
  if (Array.isArray(value)) return value.join(', ')
  if (question.type === 'scale') return `${value} из ${question.max}`
  return String(value)
}

export function plural(n, one, few, many) {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few
  return many
}
