<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import BaseIcon from './BaseIcon.vue'
import PushToggle from './PushToggle.vue'
import logoIk from '../assets/logo_ik.svg'
import { ROLE_LABELS } from '../constants/roleLabels'
import { useAuthStore } from '../stores/auth'
import { useTasksStore } from '../stores/tasks'
import { useUiStore } from '../stores/ui'
import { getAvatarColor, getInitials } from '../utils/avatar'

const authStore = useAuthStore()
const tasksStore = useTasksStore()
const uiStore = useUiStore()
const router = useRouter()
const route = useRoute()

const activeDirectionId = computed(() =>
  route.query.direction ? Number(route.query.direction) : null,
)

const totalCount = computed(() => tasksStore.tasks.length)

const myTasksCount = computed(() => {
  const uid = authStore.user?.id
  return tasksStore.tasks.filter((task) => task.assignee?.id === uid).length
})

// Пустой /tasks (без direction и без all) = «Мои задачи».
const isMyTasksActive = computed(
  () => route.name === 'tasks' && activeDirectionId.value === null && route.query.all !== '1',
)
const isAllTasksActive = computed(() => route.name === 'tasks' && route.query.all === '1')

const countsByDirectionId = computed(() => {
  const counts = new Map()
  for (const task of tasksStore.tasks) {
    const id = task.direction.id
    counts.set(id, (counts.get(id) ?? 0) + 1)
  }
  return counts
})

function goToMyTasks() {
  router.push({ name: 'tasks' })
}

function goToAllTasks() {
  router.push({ name: 'tasks', query: { all: '1' } })
}

function goToCalendar() {
  router.push({ name: 'calendar' })
}

function goToLeadershipTimeline() {
  router.push({ name: 'leadership-timeline' })
}

function goToEditorial() {
  router.push({ name: 'editorial' })
}

function goToZavod() {
  router.push({ name: 'zavod' })
}

function goToUsers() {
  router.push({ name: 'users' })
}

function selectDirection(directionId) {
  router.push({ name: 'tasks', query: { direction: directionId } })
}

function handleLogout() {
  authStore.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <button
    v-if="uiStore.sidebarCollapsed"
    class="sidebar-reopen"
    title="Показать меню"
    @click="uiStore.toggleSidebar()"
  >
    <BaseIcon name="menu" :size="18" />
  </button>

  <aside v-else class="sidebar">
    <div class="brand">
      <img :src="logoIk" class="brand__badge" alt="ИК" />
      <button class="brand__collapse" title="Скрыть меню" @click="uiStore.toggleSidebar()">
        <BaseIcon name="chevron-left" :size="18" />
      </button>
    </div>

    <div class="nav-section">
      <div class="nav-section__label">Общее</div>
      <button
        class="nav-item"
        :class="{ 'nav-item--active': isMyTasksActive }"
        @click="goToMyTasks"
      >
        <span class="nav-item__dot nav-item__dot--all" />
        <span class="nav-item__name">Мои задачи</span>
        <span class="nav-item__count">{{ myTasksCount }}</span>
      </button>
      <button
        class="nav-item"
        :class="{ 'nav-item--active': isAllTasksActive }"
        @click="goToAllTasks"
      >
        <span class="nav-item__dot nav-item__dot--all" />
        <span class="nav-item__name">Все ТЗ</span>
        <span class="nav-item__count">{{ totalCount }}</span>
      </button>
      <button
        class="nav-item"
        :class="{ 'nav-item--active': route.name === 'calendar' }"
        @click="goToCalendar"
      >
        <span class="nav-item__dot nav-item__dot--all" />
        <span class="nav-item__name">Календарь</span>
      </button>
      <button
        v-if="authStore.isEditorial"
        class="nav-item"
        :class="{ 'nav-item--active': route.name === 'editorial' || route.name === 'editorial-post' }"
        @click="goToEditorial"
      >
        <span class="nav-item__dot nav-item__dot--all" />
        <span class="nav-item__name">Редакция</span>
      </button>
      <button
        v-if="authStore.isManagerOrAdmin"
        class="nav-item"
        :class="{ 'nav-item--active': route.name === 'leadership-timeline' }"
        @click="goToLeadershipTimeline"
      >
        <span class="nav-item__dot nav-item__dot--all" />
        <span class="nav-item__name">Таймлайн руководства</span>
        <span class="nav-item__lock" title="Только для руководителей">🔒</span>
      </button>
      <button
        v-if="authStore.isZavod"
        class="nav-item"
        :class="{ 'nav-item--active': route.name === 'zavod' }"
        @click="goToZavod"
      >
        <span class="nav-item__dot nav-item__dot--all" />
        <span class="nav-item__name">ZAVOD</span>
        <span class="nav-item__lock" title="Доступ по списку">🔒</span>
      </button>
      <button
        v-if="authStore.isAdmin"
        class="nav-item"
        :class="{ 'nav-item--active': route.name === 'users' }"
        @click="goToUsers"
      >
        <span class="nav-item__dot nav-item__dot--all" />
        <span class="nav-item__name">Пользователи</span>
      </button>
    </div>

    <div class="nav-section">
      <div class="nav-section__label">Направления</div>
      <button
        v-for="direction in tasksStore.directions"
        :key="direction.id"
        class="nav-item"
        :class="{ 'nav-item--active': route.name === 'tasks' && activeDirectionId === direction.id }"
        @click="selectDirection(direction.id)"
      >
        <span class="nav-item__dot" :class="`nav-item__dot--${direction.color}`" />
        <span class="nav-item__name">
          {{ direction.short_code }}
          <span v-if="direction.short_code !== direction.name" class="nav-item__name-full">
            {{ direction.name }}
          </span>
        </span>
        <span class="nav-item__count">{{ countsByDirectionId.get(direction.id) ?? 0 }}</span>
      </button>
    </div>

    <PushToggle class="sidebar-push" />

    <div class="user-footer">
      <div class="user-footer__avatar" :style="{ background: getAvatarColor(authStore.user?.id) }">
        {{ getInitials(authStore.user?.full_name) }}
      </div>
      <div class="user-footer__info">
        <div class="user-footer__name">{{ authStore.user?.full_name }}</div>
        <div class="user-footer__role">{{ ROLE_LABELS[authStore.user?.role] ?? authStore.user?.role }}</div>
      </div>
      <button class="user-footer__logout" title="Выйти" @click="handleLogout">⏻</button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 260px;
  flex-shrink: 0;
  /* Полупрозрачное «стекло» — фирменные свечения фона просвечивают сквозь меню */
  background: color-mix(in srgb, var(--surface) 72%, transparent);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 20px 16px;
  gap: 24px;
}

.sidebar-reopen {
  position: fixed;
  top: 16px;
  left: 14px;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: var(--surface-raised);
  color: var(--text-muted);
  transition: color 0.15s ease, border-color 0.15s ease;
}

.sidebar-reopen:hover {
  color: var(--text);
  border-color: var(--border-strong);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand__text {
  min-width: 0;
  flex-grow: 1;
}

.brand__collapse {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: auto;
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: var(--text-muted);
  transition: color 0.15s ease, background 0.15s ease;
}

.brand__collapse:hover {
  color: var(--text);
  background: var(--surface-raised);
}

.brand__badge {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  object-fit: contain;
  flex-shrink: 0;
  transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), filter 0.2s ease;
}

/* Логотип оживает при наведении: лёгкий наклон + фирменное свечение. */
@media (prefers-reduced-motion: no-preference) {
  .brand__badge:hover {
    transform: rotate(-5deg) scale(1.08);
    filter: drop-shadow(0 0 10px color-mix(in srgb, var(--dir-prod-a) 55%, transparent));
  }
}

.nav-section {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-section__label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  padding: 0 10px 6px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  border: none;
  background: transparent;
  color: var(--text);
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 14px;
  text-align: left;
}

.nav-item {
  transition: background 0.15s ease, transform 0.15s ease;
}

.nav-item:hover {
  background: var(--surface-raised);
}

@media (prefers-reduced-motion: no-preference) {
  .nav-item:hover {
    transform: translateX(3px);
  }
}

.nav-item--active {
  background: var(--accent-soft);
  color: var(--text);
}

.nav-item__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
  flex-shrink: 0;
}

.nav-item__lock {
  font-size: 11px;
  opacity: 0.7;
  flex-shrink: 0;
}

.nav-item__dot--all {
  background: var(--accent);
}

.nav-item__dot--violet { background: var(--dir-ct); }
.nav-item__dot--blue { background: var(--dir-prod); }
.nav-item__dot--pink { background: var(--dir-design); }
.nav-item__dot--green { background: var(--dir-photo); }
.nav-item__dot--orange { background: var(--dir-smi); }
.nav-item__dot--cyan { background: var(--dir-nvk); }

.nav-item__name {
  flex-grow: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav-item__name-full {
  color: var(--text-muted);
}

.nav-item__count {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--surface-raised);
  border-radius: 999px;
  padding: 1px 8px;
}

.sidebar-push {
  margin-top: auto;
}

.user-footer {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.user-footer__avatar {
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

.user-footer__info {
  flex-grow: 1;
  overflow: hidden;
}

.user-footer__name {
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-footer__role {
  font-size: 12px;
  color: var(--text-muted);
}

.user-footer__logout {
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 16px;
  cursor: pointer;
  flex-shrink: 0;
}

.user-footer__logout:hover {
  color: var(--danger);
}

/* На мобильных навигация — нижний таб-бар (AppTabBar), сайдбар скрыт. */
@media (max-width: 768px) {
  .sidebar,
  .sidebar-reopen {
    display: none;
  }
}
</style>
