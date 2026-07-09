// Статусы трека (текст/дизайн) в посте Редакции.
export const EDITORIAL_STATUS_LABELS = {
  empty: '—',
  draft: 'Черновик',
  review: 'На проверке',
  fixes: 'Правки',
  ready: 'Готово',
}

// Цвет точки статуса (для календаря и бейджей).
export const EDITORIAL_STATUS_COLORS = {
  empty: 'var(--text-faint)',
  draft: 'var(--text-muted)',
  review: 'var(--warning, #fbbf24)',
  fixes: 'var(--danger)',
  ready: 'var(--status-done)',
}

export const EDITORIAL_ROLE_LABELS = {
  writer: 'Райтер',
  designer: 'Дизайнер',
}

// Приоритет для агрегированного статуса поста (какой трек «главнее» на плашке).
const STATUS_ORDER = ['fixes', 'review', 'draft', 'ready', 'empty']

// Возвращает «худший» из двух статусов для точки в календаре.
export function aggregatePostStatus(post) {
  const both = [post.text_status, post.design_status]
  // Если оба ready → готово; иначе берём самый «срочный» по STATUS_ORDER.
  if (both.every((s) => s === 'ready')) return 'ready'
  for (const status of STATUS_ORDER) {
    if (both.includes(status)) return status
  }
  return 'empty'
}
