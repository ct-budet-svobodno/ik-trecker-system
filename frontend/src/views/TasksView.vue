<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import BaseIcon from '../components/BaseIcon.vue'
import CreateTaskModal from '../components/CreateTaskModal.vue'
import TaskCard from '../components/TaskCard.vue'
import { STATUS_FILTERS, STATUS_META } from '../constants/taskMeta'
import { LEADERSHIP_POSITION_LABELS } from '../constants/roleLabels'
import { fetchLeadershipTasks, updateLeadershipTask } from '../api/leadershipTasks'
import { fetchMyPosts } from '../api/editorial'
import { EDITORIAL_STATUS_LABELS } from '../constants/editorialMeta'
import { useAuthStore } from '../stores/auth'
import { useTasksStore } from '../stores/tasks'
import { addDays, dayKey } from '../utils/dateKey'

const STATUS_COLUMNS = ['todo', 'in_progress', 'in_review', 'done']

const authStore = useAuthStore()
const tasksStore = useTasksStore()
const route = useRoute()
const router = useRouter()

// Мобильный переключатель области (на десктопе это делает сайдбар).
function setScope(target) {
  router.push(target === 'all' ? { name: 'tasks', query: { all: '1' } } : { name: 'tasks' })
}

// «От руководства» — записи таймлайна руководства по моим направлениям.
const leadershipItems = ref([])

const myDirectionIds = computed(() => {
  const me = authStore.user?.id
  const ids = new Set()
  for (const dir of tasksStore.directions) {
    if ((dir.heads ?? []).some((h) => h.id === me)) ids.add(dir.id)
  }
  return ids
})

const myPosition = computed(() => authStore.user?.leadership_position ?? null)

const fromLeadership = computed(() =>
  leadershipItems.value
    .filter((it) => {
      if (it.status === 'done') return false
      // Записи моих направлений + записи моей должности в тройке.
      if (it.direction_id && myDirectionIds.value.has(it.direction_id)) return true
      if (it.position && it.position === myPosition.value) return true
      return false
    })
    .sort((a, b) => a.date.localeCompare(b.date)),
)

const leadershipDateFmt = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' })
function formatLeadershipDate(value) {
  const [y, m, d] = value.split('-').map(Number)
  return leadershipDateFmt.format(new Date(y, m - 1, d))
}

async function loadLeadership() {
  if (!authStore.isManagerOrAdmin) return
  try {
    const today = new Date()
    leadershipItems.value = await fetchLeadershipTasks({
      dateFrom: dayKey(today),
      dateTo: dayKey(addDays(today, 60)),
    })
  } catch {
    leadershipItems.value = []
  }
}

async function markLeadershipDone(item) {
  try {
    await updateLeadershipTask(item.id, { status: 'done' })
    leadershipItems.value = leadershipItems.value.filter((it) => it.id !== item.id)
  } catch {
    /* молча — не критично для доски */
  }
}

// «Мои посты» — посты Редакции, где я райтер/дизайнер. Показываем незакрытые треки.
const myPosts = ref([])

const myEditorialItems = computed(() => {
  const me = authStore.user?.id
  const items = []
  for (const post of myPosts.value) {
    if (post.writer_id === me && post.text_status !== 'ready') {
      items.push({ post, role: 'Райтер', status: post.text_status })
    }
    if (post.designer_id === me && post.design_status !== 'ready') {
      items.push({ post, role: 'Дизайнер', status: post.design_status })
    }
  }
  return items
})

async function loadMyPosts() {
  try {
    myPosts.value = await fetchMyPosts()
  } catch {
    myPosts.value = []
  }
}

const statusFilter = ref(null)
const searchQuery = ref('')
const showCreateModal = ref(false)
const viewMode = ref('grid')

const draggedTaskId = ref(null)
const dragOverStatus = ref(null)
const dragError = ref('')

const canCreateTask = computed(() => ['admin', 'manager'].includes(authStore.user?.role))

onMounted(async () => {
  await tasksStore.loadAll()
  await Promise.all([loadLeadership(), loadMyPosts()])
})

const activeDirectionId = computed(() => (route.query.direction ? Number(route.query.direction) : null))

const activeDirection = computed(
  () => tasksStore.directions.find((d) => d.id === activeDirectionId.value) ?? null,
)

// Область просмотра: направление → all (явный список) → mine (дефолт при входе).
const scope = computed(() => {
  if (activeDirectionId.value !== null) return 'direction'
  if (route.query.all === '1') return 'all'
  return 'mine'
})

// Базовый набор задач для текущей области (до фильтров статуса и поиска).
const scopedTasks = computed(() => {
  if (scope.value === 'direction') {
    return tasksStore.tasks.filter((task) => task.direction.id === activeDirectionId.value)
  }
  if (scope.value === 'mine') {
    return tasksStore.tasks.filter((task) => task.assignee?.id === authStore.user?.id)
  }
  return tasksStore.tasks
})

const heading = computed(() => {
  if (scope.value === 'direction') {
    return {
      crumb: activeDirection.value?.name ?? '—',
      title: activeDirection.value?.name ?? '—',
      subtitle: `Задачи направления «${activeDirection.value?.name ?? ''}»`,
    }
  }
  if (scope.value === 'all') {
    return {
      crumb: 'Все',
      title: 'Все ТЗ',
      subtitle: 'Сводный список задач по всем направлениям',
    }
  }
  return {
    crumb: 'Мои',
    title: 'Мои задачи',
    subtitle: 'Задачи, назначенные на вас',
  }
})

const stats = computed(() => {
  const counts = { total: scopedTasks.value.length, in_progress: 0, in_review: 0, done: 0 }
  for (const task of scopedTasks.value) {
    if (task.status in counts) counts[task.status] += 1
  }
  return counts
})

const visibleTasks = computed(() => {
  let result = scopedTasks.value

  if (statusFilter.value !== null) {
    result = result.filter((task) => task.status === statusFilter.value)
  }
  const query = searchQuery.value.trim().toLowerCase()
  if (query) {
    result = result.filter(
      (task) =>
        task.title.toLowerCase().includes(query) || task.description.toLowerCase().includes(query),
    )
  }
  return result
})

function handleTaskCreated(task) {
  tasksStore.addTask(task)
}

const tasksByStatus = computed(() => {
  const groups = { todo: [], in_progress: [], in_review: [], done: [] }
  for (const task of visibleTasks.value) {
    groups[task.status]?.push(task)
  }
  return groups
})

function onDragStart(task) {
  draggedTaskId.value = task.id
}

function onDragEnd() {
  draggedTaskId.value = null
  dragOverStatus.value = null
}

function onDragEnter(status) {
  dragOverStatus.value = status
}

function onDragLeave(status) {
  if (dragOverStatus.value === status) dragOverStatus.value = null
}

async function onDrop(status) {
  const taskId = draggedTaskId.value
  dragOverStatus.value = null
  if (taskId == null) return

  const task = tasksStore.tasks.find((t) => t.id === taskId)
  if (!task || task.status === status) return

  try {
    await tasksStore.setTaskStatus(taskId, status)
  } catch (err) {
    dragError.value = err.response?.data?.detail ?? 'Не удалось изменить статус'
    setTimeout(() => {
      dragError.value = ''
    }, 3000)
  }
}
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="page-head">
        <div class="page-head__titles">
          <p class="breadcrumb">ИК · Трекер / {{ heading.crumb }}</p>
          <h1>{{ heading.title }}</h1>
          <p class="subtitle">{{ heading.subtitle }}</p>
        </div>
        <div class="metrics">
          <div class="metric">
            <span class="metric__num">{{ stats.total }}</span>
            <span class="metric__label">Всего</span>
          </div>
          <span class="metric__sep" />
          <div class="metric">
            <span class="metric__num">{{ stats.in_progress }}</span>
            <span class="metric__label">В работе</span>
          </div>
          <span class="metric__sep" />
          <div class="metric">
            <span class="metric__num">{{ stats.in_review }}</span>
            <span class="metric__label">На проверке</span>
          </div>
          <span class="metric__sep" />
          <div class="metric">
            <span class="metric__num">{{ stats.done }}</span>
            <span class="metric__label">Готово</span>
          </div>
        </div>
      </div>

      <!-- Мои/Все — только на мобильных (на десктопе переключает сайдбар). -->
      <div class="scope-switch">
        <button
          class="scope-switch__btn"
          :class="{ 'scope-switch__btn--active': scope === 'mine' }"
          @click="setScope('mine')"
        >
          Мои задачи
        </button>
        <button
          class="scope-switch__btn"
          :class="{ 'scope-switch__btn--active': scope === 'all' }"
          @click="setScope('all')"
        >
          Все ТЗ
        </button>
        <button
          v-if="scope === 'direction'"
          class="scope-switch__btn scope-switch__btn--active scope-switch__btn--dir"
          @click="setScope('mine')"
        >
          {{ activeDirection?.short_code ?? '…' }} ✕
        </button>
      </div>

      <section v-if="scope === 'mine' && fromLeadership.length" class="from-leadership">
        <div class="from-leadership__head">
          <span class="from-leadership__title">От руководства</span>
          <span class="from-leadership__count">{{ fromLeadership.length }}</span>
        </div>
        <ul class="from-leadership__list">
          <li v-for="item in fromLeadership" :key="item.id" class="fl-item">
            <span class="fl-item__date">{{ formatLeadershipDate(item.date) }}</span>
            <span
              v-if="item.direction"
              class="fl-chip"
              :class="`fl-chip--${item.direction.color}`"
            >
              {{ item.direction.short_code }}
            </span>
            <span v-else class="fl-chip fl-chip--position">
              {{ LEADERSHIP_POSITION_LABELS[item.position] ?? item.position }}
            </span>
            <span class="fl-item__title">{{ item.title }}</span>
            <button class="fl-item__done" title="Отметить выполненным" @click="markLeadershipDone(item)">
              ✓ Выполнено
            </button>
          </li>
        </ul>
      </section>

      <!-- Мои посты Редакции: видно каждому, кого назначили райтером/дизайнером. -->
      <section v-if="scope === 'mine' && myEditorialItems.length" class="from-leadership my-posts">
        <div class="from-leadership__head">
          <span class="from-leadership__title">Мои посты</span>
          <span class="from-leadership__count">{{ myEditorialItems.length }}</span>
        </div>
        <ul class="from-leadership__list">
          <li
            v-for="item in myEditorialItems"
            :key="`${item.post.id}-${item.role}`"
            class="fl-item"
          >
            <span class="fl-item__date">{{ formatLeadershipDate(item.post.date) }}</span>
            <span class="fl-chip fl-chip--editorial">{{ item.role }}</span>
            <span class="fl-item__title">{{ item.post.title }}</span>
            <span class="my-posts__status">{{ EDITORIAL_STATUS_LABELS[item.status] }}</span>
            <button
              class="fl-item__done"
              @click="router.push({ name: 'editorial-post', params: { id: item.post.id } })"
            >
              Открыть →
            </button>
          </li>
        </ul>
      </section>

      <AppLoader v-if="tasksStore.isLoading" />
      <div v-else-if="tasksStore.loadError" class="state-message state-message--error">
        {{ tasksStore.loadError }}
      </div>

      <template v-else>
        <div class="controls-row">
          <label class="search">
            <BaseIcon class="search__icon" name="search" :size="16" />
            <input v-model="searchQuery" class="search__input" type="text" placeholder="Поиск по ТЗ…" />
          </label>

          <div v-if="viewMode === 'grid'" class="filter-tabs">
            <button
              v-for="filter in STATUS_FILTERS"
              :key="filter.label"
              class="filter-tab"
              :class="{ 'filter-tab--active': statusFilter === filter.value }"
              @click="statusFilter = filter.value"
            >
              {{ filter.label }}
            </button>
          </div>

          <div class="view-toggle">
            <button
              class="view-toggle__btn"
              :class="{ 'view-toggle__btn--active': viewMode === 'grid' }"
              title="Сетка"
              @click="viewMode = 'grid'"
            >
              <BaseIcon name="grid" :size="16" />
            </button>
            <button
              class="view-toggle__btn"
              :class="{ 'view-toggle__btn--active': viewMode === 'kanban' }"
              title="Канбан"
              @click="viewMode = 'kanban'; statusFilter = null"
            >
              <BaseIcon name="columns" :size="16" />
            </button>
          </div>

          <button v-if="canCreateTask" class="create-btn" @click="showCreateModal = true">
            <BaseIcon name="plus" :size="16" />
            Выдать ТЗ
          </button>
        </div>

        <template v-if="viewMode === 'grid'">
          <div v-if="visibleTasks.length === 0" class="state-message">Задач не найдено.</div>
          <div v-else class="task-grid">
            <TaskCard v-for="task in visibleTasks" :key="task.id" :task="task" />
          </div>
        </template>

        <template v-else>
          <div class="kanban-board">
            <section
              v-for="status in STATUS_COLUMNS"
              :key="status"
              class="kanban-column"
              :class="{ 'kanban-column--drag-over': dragOverStatus === status }"
              @dragover.prevent
              @dragenter="onDragEnter(status)"
              @dragleave="onDragLeave(status)"
              @drop="onDrop(status)"
            >
              <div class="kanban-column__header">
                <span class="kanban-dot" :class="`kanban-dot--${STATUS_META[status].color}`" />
                <span class="kanban-column__title">{{ STATUS_META[status].label }}</span>
                <span class="kanban-column__count">{{ tasksByStatus[status].length }}</span>
              </div>

              <div class="kanban-column__cards">
                <div
                  v-for="task in tasksByStatus[status]"
                  :key="task.id"
                  class="kanban-card"
                  draggable="true"
                  @dragstart="onDragStart(task)"
                  @dragend="onDragEnd"
                >
                  <TaskCard :task="task" :show-status="false" />
                </div>
              </div>
            </section>
          </div>
          <p v-if="dragError" class="drag-error">{{ dragError }}</p>
        </template>
      </template>
    </main>

    <CreateTaskModal
      v-if="showCreateModal"
      :directions="tasksStore.directions"
      @close="showCreateModal = false"
      @created="handleTaskCreated"
    />
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}

/* Панель «От руководства» — записи таймлайна руководства по моим направлениям. */
.from-leadership {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 20px;
}

.from-leadership__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.from-leadership__title {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.from-leadership__count {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--surface-raised);
  border-radius: 999px;
  padding: 1px 8px;
}

.from-leadership__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.fl-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.fl-item__date {
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--text-muted);
  min-width: 56px;
}

.fl-chip {
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  border-radius: 4px;
  padding: 2px 6px;
  white-space: nowrap;
}

.fl-chip--violet { background: var(--dir-ct); }
.fl-chip--pink { background: var(--dir-design); }
.fl-chip--cyan { background: var(--dir-nvk); }
.fl-chip--green { background: var(--dir-photo); }
.fl-chip--orange { background: var(--dir-smi); }
.fl-chip--blue { background: var(--dir-prod); }
.fl-chip--position { background: var(--accent); }
.fl-chip--editorial { background: var(--dir-smi); }

/* «Мои посты» — та же плашка, но с бирюзовой рамкой Редакции. */
.my-posts {
  border-left-color: var(--dir-prod-b);
}

.my-posts__status {
  font-size: 11.5px;
  color: var(--text-muted);
  white-space: nowrap;
}

.fl-item__title {
  flex-grow: 1;
  font-size: 13.5px;
  min-width: 0;
}

.fl-item__done {
  border: 1px solid var(--border);
  background: transparent;
  color: var(--status-done);
  border-radius: 7px;
  padding: 4px 10px;
  font-size: 12px;
  white-space: nowrap;
  flex-shrink: 0;
}

.fl-item__done:hover {
  background: color-mix(in srgb, var(--status-done) 14%, transparent);
}

.app-main {
  flex-grow: 1;
  padding: 28px 32px;
  max-width: 100%;
  overflow-x: hidden;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
  margin-bottom: 26px;
}

/* Единственный капс-уровень на странице (mono, разрежённый). */
.breadcrumb {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-faint);
  margin: 0 0 8px;
}

h1 {
  font-size: 26px;
  font-weight: 600;
  letter-spacing: -0.01em;
  margin: 0 0 6px;
}

.subtitle {
  color: var(--text-muted);
  font-size: 14px;
  margin: 0;
}

/* Метрики чистой строкой: моно-числа + подпись, разделители-волоски, без точек. */
.metrics {
  display: flex;
  align-items: stretch;
  gap: 18px;
  padding: 4px 0;
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.metric__num {
  font-family: var(--font-mono);
  font-size: 20px;
  font-weight: 500;
  line-height: 1;
  color: var(--text);
}

.metric__label {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}

.metric__sep {
  width: 1px;
  align-self: stretch;
  background: var(--border);
}

.controls-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.search {
  flex: 1 1 220px;
  min-width: 180px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-raised);
  transition: border-color 0.15s ease;
}

.search:focus-within {
  border-color: var(--border-strong);
}

.search__icon {
  color: var(--text-faint);
}

.search__input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  padding: 9px 0;
  font-size: 14px;
}

.search__input::placeholder {
  color: var(--text-faint);
}

.filter-tabs {
  display: flex;
  gap: 4px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 3px;
}

.filter-tab {
  border: none;
  background: transparent;
  color: var(--text-muted);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 13px;
  transition: color 0.15s ease, background 0.15s ease;
}

.filter-tab:hover {
  color: var(--text);
}

.filter-tab--active {
  background: var(--accent-soft);
  color: var(--text);
}

.view-toggle {
  display: flex;
  gap: 2px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 3px;
}

.view-toggle__btn {
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--text-muted);
  width: 32px;
  height: 30px;
  border-radius: 6px;
  transition: color 0.15s ease, background 0.15s ease;
}

.view-toggle__btn:hover {
  color: var(--text);
}

.view-toggle__btn--active {
  background: var(--surface-raised);
  color: var(--text);
}

.create-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  border-radius: 8px;
  background: var(--success);
  color: #0c1410;
  font-weight: 600;
  font-size: 14px;
  padding: 9px 16px;
  white-space: nowrap;
  transition: background 0.15s ease, transform 0.1s ease;
}

.create-btn:hover {
  background: var(--success-hover);
}

.create-btn:active {
  transform: scale(0.98);
}

.task-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.state-message {
  color: var(--text-muted);
  padding: 40px 0;
  text-align: center;
}

.state-message--error {
  color: var(--danger);
}

.kanban-board {
  display: grid;
  grid-template-columns: repeat(4, minmax(240px, 1fr));
  gap: 16px;
  align-items: start;
}

.kanban-column {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: border-color 0.15s ease;
}

.kanban-column--drag-over {
  border-color: var(--accent);
}

.kanban-column__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  font-size: 13px;
  font-weight: 600;
}

.kanban-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.kanban-dot--grey { background: var(--status-todo); }
.kanban-dot--orange { background: var(--status-progress); }
.kanban-dot--purple { background: var(--status-review); }
.kanban-dot--green { background: var(--status-done); }

.kanban-column__title {
  flex-grow: 1;
}

.kanban-column__count {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
  background: var(--surface-raised);
  border-radius: 999px;
  padding: 1px 8px;
}

.kanban-column__cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 80px;
}

.kanban-card {
  cursor: grab;
}

.kanban-card:active {
  cursor: grabbing;
  opacity: 0.7;
}

.drag-error {
  margin-top: 16px;
  color: var(--danger);
  font-size: 13px;
}

/* Переключатель «Мои/Все» — виден только на мобильных. */
.scope-switch {
  display: none;
}

@media (max-width: 768px) {
  .scope-switch {
    display: flex;
    gap: 4px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 3px;
    margin-bottom: 16px;
  }

  .scope-switch__btn {
    flex: 1;
    border: none;
    background: transparent;
    color: var(--text-muted);
    padding: 8px 10px;
    border-radius: 8px;
    font-size: 13.5px;
    transition: color 0.15s ease, background 0.15s ease;
  }

  .scope-switch__btn--active {
    background: var(--accent-soft);
    color: var(--text);
    font-weight: 600;
  }

  .scope-switch__btn--dir {
    flex: 0 0 auto;
  }

  .metrics {
    gap: 14px;
    width: 100%;
    justify-content: space-between;
  }

  h1 {
    font-size: 22px;
  }

  .page-head {
    margin-bottom: 18px;
  }

  /* Канбан — свайп между колонками (как в мобильных трекерах). */
  .kanban-board {
    display: flex;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    gap: 12px;
    margin: 0 -14px;
    padding: 0 14px 10px;
    -webkit-overflow-scrolling: touch;
  }

  .kanban-board::-webkit-scrollbar {
    display: none;
  }

  .kanban-column {
    flex: 0 0 84%;
    scroll-snap-align: center;
  }

  /* «От руководства» — строки складываются в две линии. */
  .fl-item {
    flex-wrap: wrap;
    row-gap: 4px;
  }

  .fl-item__title {
    flex-basis: 100%;
    order: 3;
  }
}
</style>
