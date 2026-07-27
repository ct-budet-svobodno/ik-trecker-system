<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import BaseIcon from './BaseIcon.vue'
import PushToggle from './PushToggle.vue'
import { ROLE_LABELS } from '../constants/roleLabels'
import { useAuthStore } from '../stores/auth'
import { useTasksStore } from '../stores/tasks'
import { getAvatarColor, getInitials } from '../utils/avatar'

const authStore = useAuthStore()
const tasksStore = useTasksStore()
const router = useRouter()
const route = useRoute()

const sheetOpen = ref(false)

// Закрываем шторку при любом переходе.
watch(() => route.fullPath, () => {
  sheetOpen.value = false
})

const isTasksActive = computed(() => route.name === 'tasks')
const isCalendarActive = computed(() => route.name === 'calendar')
const isEditorialActive = computed(
  () => route.name === 'editorial' || route.name === 'editorial-post',
)
// «Ещё» активна, когда открыт раздел из шторки.
const isMoreActive = computed(() =>
  ['leadership-timeline', 'zavod', 'users'].includes(route.name),
)

// query по умолчанию пустой: таб «Задачи» всегда сбрасывает на «Мои задачи».
// Шторку закрываем явно — при переходе «в то же место» маршрут не меняется.
function go(name, query = {}) {
  sheetOpen.value = false
  router.push({ name, query })
}

function selectDirection(directionId) {
  sheetOpen.value = false
  router.push({ name: 'tasks', query: { direction: directionId } })
}

function handleLogout() {
  sheetOpen.value = false
  authStore.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <nav class="tabbar" aria-label="Основная навигация">
    <button class="tab" :class="{ 'tab--active': isTasksActive }" @click="go('tasks')">
      <span class="tab__indicator" />
      <BaseIcon name="columns" :size="21" />
      <span class="tab__label">Задачи</span>
    </button>

    <button class="tab" :class="{ 'tab--active': isCalendarActive }" @click="go('calendar')">
      <span class="tab__indicator" />
      <BaseIcon name="calendar" :size="21" />
      <span class="tab__label">Календарь</span>
    </button>

    <button
      v-if="authStore.isEditorial"
      class="tab"
      :class="{ 'tab--active': isEditorialActive }"
      @click="go('editorial')"
    >
      <span class="tab__indicator" />
      <BaseIcon name="pen" :size="21" />
      <span class="tab__label">Редакция</span>
    </button>

    <button class="tab" :class="{ 'tab--active': isMoreActive || sheetOpen }" @click="sheetOpen = true">
      <span class="tab__indicator" />
      <BaseIcon name="dots" :size="21" />
      <span class="tab__label">Ещё</span>
    </button>
  </nav>

  <!-- Шторка «Ещё» -->
  <Teleport to="body">
    <div v-if="sheetOpen" class="sheet-backdrop" @click.self="sheetOpen = false">
      <div v-swipe-close="() => (sheetOpen = false)" class="sheet">
        <span class="sheet__grip" />

        <div class="sheet__section">
          <button class="sheet-item" @click="go('tasks', { all: '1' })">Все ТЗ</button>
          <button
            v-if="authStore.isManagerOrAdmin"
            class="sheet-item"
            @click="go('leadership-timeline')"
          >
            Таймлайн руководства
            <span class="sheet-item__lock">🔒</span>
          </button>
          <button v-if="authStore.isZavod" class="sheet-item" @click="go('zavod')">
            ZAVOD
            <span class="sheet-item__lock">🔒</span>
          </button>
          <button v-if="authStore.isAdmin" class="sheet-item" @click="go('users')">
            Пользователи
          </button>
        </div>

        <div v-if="tasksStore.directions.length" class="sheet__section">
          <p class="sheet__label">Направления</p>
          <div class="sheet-dirs">
            <button
              v-for="direction in tasksStore.directions"
              :key="direction.id"
              class="sheet-dir"
              @click="selectDirection(direction.id)"
            >
              <span class="sheet-dir__dot" :class="`sheet-dir__dot--${direction.color}`" />
              {{ direction.short_code }}
            </button>
          </div>
        </div>

        <div class="sheet__section">
          <PushToggle />
        </div>

        <div class="sheet__user">
          <span class="sheet__avatar" :style="{ background: getAvatarColor(authStore.user?.id) }">
            {{ getInitials(authStore.user?.full_name) }}
          </span>
          <span class="sheet__user-info">
            <span class="sheet__user-name">{{ authStore.user?.full_name }}</span>
            <span class="sheet__user-role">{{ ROLE_LABELS[authStore.user?.role] ?? authStore.user?.role }}</span>
          </span>
          <button class="sheet__logout" @click="handleLogout">Выйти</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* Таб-бар — только на мобильных. */
.tabbar {
  display: none;
}

@media (max-width: 768px) {
  .tabbar {
    position: fixed;
    left: 10px;
    right: 10px;
    bottom: calc(10px + env(safe-area-inset-bottom));
    z-index: 90;
    display: flex;
    align-items: stretch;
    /* Стекло в духе сайдбара: фирменные свечения фона просвечивают. */
    background: color-mix(in srgb, var(--surface) 80%, transparent);
    backdrop-filter: blur(18px) saturate(140%);
    -webkit-backdrop-filter: blur(18px) saturate(140%);
    border: 1px solid var(--border);
    border-radius: 18px;
    box-shadow:
      0 12px 32px rgba(0, 0, 0, 0.45),
      inset 0 1px 0 rgba(255, 255, 255, 0.06);
    padding: 6px;
  }
}

.tab {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  padding: 7px 4px 6px;
  border-radius: 13px;
  transition: color 0.15s ease, transform 0.1s ease;
}

.tab:active {
  transform: scale(0.94);
}

.tab--active {
  color: var(--text);
}

/* Брендовый индикатор активной вкладки: малиновый → бирюзовый. */
.tab__indicator {
  position: absolute;
  top: 0;
  width: 20px;
  height: 3px;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--dir-prod-a), var(--dir-prod-b));
  opacity: 0;
  transform: scaleX(0.4);
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.tab--active .tab__indicator {
  opacity: 1;
  transform: scaleX(1);
}

.tab__label {
  font-size: 10.5px;
  letter-spacing: 0.01em;
}

/* --- Шторка «Ещё» --- */
.sheet-backdrop {
  position: fixed;
  inset: 0;
  z-index: 95;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: flex-end;
}

.sheet {
  width: 100%;
  max-height: 88dvh;
  overflow-y: auto;
  overscroll-behavior: contain;
  background: color-mix(in srgb, var(--surface) 94%, transparent);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-top: 1px solid var(--border-strong);
  border-radius: 20px 20px 0 0;
  padding: 10px 16px calc(18px + env(safe-area-inset-bottom));
  animation: sheet-up 0.24s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes sheet-up {
  from { transform: translateY(24px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .sheet {
    animation: none;
  }
}

.sheet__grip {
  display: block;
  width: 36px;
  height: 4px;
  border-radius: 999px;
  background: var(--border-strong);
  margin: 2px auto 12px;
}

.sheet__section {
  padding: 4px 0 10px;
}

.sheet__section + .sheet__section {
  border-top: 1px solid var(--border);
  padding-top: 12px;
}

.sheet-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  border: none;
  background: transparent;
  color: var(--text);
  text-align: left;
  font-size: 15px;
  padding: 12px 6px;
  border-radius: 10px;
}

.sheet-item:active {
  background: var(--surface-raised);
}

.sheet-item__lock {
  font-size: 11px;
  opacity: 0.7;
}

.sheet__label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin: 0 0 8px;
  padding: 0 6px;
}

.sheet-dirs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 2px;
}

.sheet-dir {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid var(--border);
  background: var(--surface-raised);
  color: var(--text);
  border-radius: 999px;
  padding: 7px 13px;
  font-size: 13px;
}

.sheet-dir:active {
  border-color: var(--border-strong);
}

.sheet-dir__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
}

.sheet-dir__dot--violet { background: var(--dir-ct); }
.sheet-dir__dot--blue { background: var(--dir-prod); }
.sheet-dir__dot--pink { background: var(--dir-design); }
.sheet-dir__dot--green { background: var(--dir-photo); }
.sheet-dir__dot--orange { background: var(--dir-smi); }
.sheet-dir__dot--cyan { background: var(--dir-nvk); }

.sheet__user {
  display: flex;
  align-items: center;
  gap: 10px;
  border-top: 1px solid var(--border);
  padding-top: 14px;
  margin-top: 4px;
}

.sheet__avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}

.sheet__user-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.sheet__user-name {
  font-size: 14px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sheet__user-role {
  font-size: 12px;
  color: var(--text-muted);
}

.sheet__logout {
  border: 1px solid var(--border);
  background: transparent;
  color: var(--danger);
  border-radius: 9px;
  padding: 8px 14px;
  font-size: 13px;
}
</style>
