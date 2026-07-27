// Статусы карточек на доске ZAVOD. Цвета берутся из общих CSS-переменных
// статусов (--status-todo / --status-progress / --status-done).
export const ZAVOD_STATUS_META = {
  todo: { label: 'Не начато', tone: 'todo' },
  in_progress: { label: 'В работе', tone: 'progress' },
  done: { label: 'Готово', tone: 'done' },
}

export const ZAVOD_STATUS_ORDER = ['todo', 'in_progress', 'done']

// Размеры новой карточки и шаг раскладки деревом — в «мировых» единицах холста.
export const NODE_DEFAULT_WIDTH = 220
export const NODE_DEFAULT_HEIGHT = 120
export const LAYOUT_COLUMN = 300
export const LAYOUT_ROW = 170
