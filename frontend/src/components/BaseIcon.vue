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

    <!-- Три точки (Ещё) -->
    <template v-else-if="name === 'dots'">
      <circle cx="5" cy="12" r="1.6" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
      <circle cx="19" cy="12" r="1.6" fill="currentColor" stroke="none" />
    </template>
  </svg>
</template>

<style scoped>
.icon {
  display: block;
  flex-shrink: 0;
}
</style>
