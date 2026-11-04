<script setup>
// Лёгкий набор иконок на простых геометрических примитивах (без сторонних
// зависимостей). Единый stroke, наследуют currentColor — красятся через color.
defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 18 },
})
</script>

<template>
  <svg
    class="icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <!-- Сетка -->
    <template v-if="name === 'grid'">
      <rect x="4" y="4" width="7" height="7" rx="1.5" />
      <rect x="13" y="4" width="7" height="7" rx="1.5" />
      <rect x="4" y="13" width="7" height="7" rx="1.5" />
      <rect x="13" y="13" width="7" height="7" rx="1.5" />
    </template>

    <!-- Канбан (колонки) -->
    <template v-else-if="name === 'columns'">
      <rect x="4" y="4" width="4" height="16" rx="1.2" />
      <rect x="10" y="4" width="4" height="11" rx="1.2" />
      <rect x="16" y="4" width="4" height="13" rx="1.2" />
    </template>

    <!-- Календарь -->
    <template v-else-if="name === 'calendar'">
      <rect x="3.5" y="5" width="17" height="15.5" rx="2" />
      <line x1="3.5" y1="9.5" x2="20.5" y2="9.5" />
      <line x1="8" y1="3" x2="8" y2="6.5" />
      <line x1="16" y1="3" x2="16" y2="6.5" />
    </template>

    <!-- Главная (домик) -->
    <template v-else-if="name === 'home'">
      <path d="M4 10.5 12 4l8 6.5V19a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19z" />
      <path d="M9.5 20.5v-6h5v6" />
    </template>

    <!-- Поиск -->
    <template v-else-if="name === 'search'">
      <circle cx="11" cy="11" r="6.25" />
      <line x1="20" y1="20" x2="15.6" y2="15.6" />
    </template>

    <!-- Плюс -->
    <template v-else-if="name === 'plus'">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </template>

    <!-- Меню (гамбургер) -->
    <template v-else-if="name === 'menu'">
      <line x1="4" y1="7" x2="20" y2="7" />
      <line x1="4" y1="12" x2="20" y2="12" />
      <line x1="4" y1="17" x2="20" y2="17" />
    </template>

    <!-- Шеврон влево (свернуть) -->
    <template v-else-if="name === 'chevron-left'">
      <polyline points="14 6 9 12 14 18" />
    </template>

    <!-- Перо (Редакция) -->
    <template v-else-if="name === 'pen'">
      <path d="M12 20h8" />
      <path d="M16.4 3.6a2.1 2.1 0 0 1 3 3L7.5 19 3.5 20l1-4Z" />
    </template>

    <!-- Шеврон вправо -->
    <template v-else-if="name === 'chevron-right'">
      <polyline points="10 6 15 12 10 18" />
    </template>

    <!-- Замок (раздел с ограниченным доступом) -->
    <template v-else-if="name === 'lock'">
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </template>

    <!-- Выход -->
    <template v-else-if="name === 'logout'">
      <path d="M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4" />
      <polyline points="15 8 19 12 15 16" />
      <line x1="19" y1="12" x2="9" y2="12" />
    </template>

    <!-- Галочка -->
    <template v-else-if="name === 'check'">
      <polyline points="5 12.5 10 17.5 19 7" />
    </template>

    <!-- Список с галочками (Мой день) -->
    <template v-else-if="name === 'checklist'">
      <polyline points="4 6.5 5.8 8.3 9 5" />
      <polyline points="4 16.5 5.8 18.3 9 15" />
      <line x1="12.5" y1="7" x2="20" y2="7" />
      <line x1="12.5" y1="17" x2="20" y2="17" />
    </template>

    <!-- Стрелка вправо (перенести на завтра) -->
    <template v-else-if="name === 'arrow-right'">
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="13 6 19 12 13 18" />
    </template>

    <!-- Корзина -->
    <template v-else-if="name === 'trash'">
      <line x1="4.5" y1="7" x2="19.5" y2="7" />
      <path d="M9.5 7V5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v2" />
      <path d="M6.5 7l.8 11.2a1.5 1.5 0 0 0 1.5 1.3h6.4a1.5 1.5 0 0 0 1.5-1.3L17.5 7" />
    </template>

    <!-- Бумажный самолётик (Telegram) -->
    <template v-else-if="name === 'send'">
      <path d="M20.5 4 3.5 11l6.5 2.5L12.5 20Z" />
      <line x1="20.5" y1="4" x2="10" y2="13.5" />
    </template>

    <!-- Три точки (Ещё) -->
    <template v-else-if="name === 'dots'">
      <circle cx="5" cy="12" r="1.6" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
      <circle cx="19" cy="12" r="1.6" fill="currentColor" stroke="none" />
    </template>

    <!-- Комментарии -->
    <template v-else-if="name === 'chat'">
      <path d="M5 5.5h14a1.5 1.5 0 0 1 1.5 1.5v8.5A1.5 1.5 0 0 1 19 17h-8l-4.5 3.5V17H5A1.5 1.5 0 0 1 3.5 15.5V7A1.5 1.5 0 0 1 5 5.5z" />
    </template>

    <!-- Колокольчик -->
    <template v-else-if="name === 'bell'">
      <path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.5h-15z" />
      <path d="M10 20.5a2.2 2.2 0 0 0 4 0" />
    </template>

    <!-- Поворот -->
    <template v-else-if="name === 'rotate'">
      <path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3" />
      <path d="M19.5 4v4h-4" />
    </template>

    <!-- Перемешать -->
    <template v-else-if="name === 'shuffle'">
      <path d="M4 7h3.5c4.5 0 4.5 10 9 10H20" />
      <path d="M4 17h3.5c1.6 0 2.6-1.3 3.4-3M13.1 10c.8-1.7 1.8-3 3.4-3H20" />
      <path d="M17.5 4.5 20 7l-2.5 2.5M17.5 14.5 20 17l-2.5 2.5" />
    </template>
  </svg>
</template>

<style scoped>
.icon {
  display: block;
  flex-shrink: 0;
}
</style>
