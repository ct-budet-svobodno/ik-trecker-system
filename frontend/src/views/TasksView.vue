<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import BaseIcon from '../components/BaseIcon.vue'
import CreateTaskModal from '../components/CreateTaskModal.vue'
import TaskCard from '../components/TaskCard.vue'
import TaskProgress from '../components/TaskProgress.vue'
import TaskSheet from '../components/TaskSheet.vue'
import { STATUS_META } from '../constants/taskMeta'
import { LEADERSHIP_POSITION_LABELS } from '../constants/roleLabels'
import { fetchLeadershipTasks, updateLeadershipTask } from '../api/leadershipTasks'
import { fetchMyPosts } from '../api/editorial'
import { EDITORIAL_STATUS_LABELS } from '../constants/editorialMeta'
import { useAuthStore } from '../stores/auth'
import { useTasksStore } from '../stores/tasks'
import { addDays, dayKey } from '../utils/dateKey'
import { byUrgency, isAssignedTo, isOverdue, progressStats, todayKey } from '../utils/taskProgress'

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

const shownLeadership = computed(() =>
  showAllLeadership.value ? fromLeadership.value : fromLeadership.value.slice(0, INBOX_LIMIT),
)
const shownPosts = computed(() =>
  showAllPosts.value ? myEditorialItems.value : myEditorialItems.value.slice(0, INBOX_LIMIT),
)

async function loadMyPosts() {
  try {
    myPosts.value = await fetchMyPosts()
  } catch {
    myPosts.value = []
  }
}

// Входящие («От руководства», «Мои посты») показывают первые строки — остальное по кнопке,
// чтобы блоки не выталкивали доску за первый экран.
const INBOX_LIMIT = 3
const showAllLeadership = ref(false)
const showAllPosts = ref(false)

// null | статус | 'overdue' — задаётся счётчиками в карточке прогресса.
const statusFilter = ref(null)
const searchQuery = ref('')
const showCreateModal = ref(false)
const createChecklist = ref(false)
const viewMode = ref('grid')

// Открытая в шторке задача. Держим id, а саму задачу берём из стора —
// так шторка видит смену статуса сразу.
// ?task=<id> — открыть карточку сразу (ссылка из уведомления или напоминания).
const openedTaskId = ref(route.query.task ? Number(route.query.task) : null)
watch(
  () => route.query.task,
  (id) => {
    if (id) openedTaskId.value = Number(id)
  },
)

function closeTask() {
  openedTaskId.value = null
  if (route.query.task) {
    const { task: _task, ...query } = route.query
    router.replace({ query })
  }
}
const openedTask = computed(
  () => tasksStore.tasks.find((task) => task.id === openedTaskId.value) ?? null,
)

const draggedTaskId = ref(null)
const dragOverStatus = ref(null)
const dragError = ref('')

const canCreateTask = computed(() => ['admin', 'manager'].includes(authStore.user?.role))
const canCreateChecklist = computed(() => Boolean(authStore.user))

onMounted(async () => {
  await tasksStore.loadAll()
  await Promise.all([loadLeadership(), loadMyPosts()])
})

const activeDirectionId = computed(() => (route.query.direction ? Number(route.query.direction) : null))

const activeDirection = computed(
  () => tasksStore.directions.find((d) => d.id === activeDirectionId.value) ?? null,
)

// Область просмотра: направление → all (явный список) → private (выданные мной
// поручения) → mine (дефолт при входе).
const scope = computed(() => {
  if (activeDirectionId.value !== null) return 'direction'
  if (route.query.checklist === '1') return 'checklist'
  if (route.query.all === '1') return 'all'
  if (route.query.private === '1') return 'private'
  return 'mine'
})
const statusColumns = computed(() => scope.value === 'checklist' ? ['todo', 'in_progress', 'done'] : STATUS_COLUMNS)

// Базовый набор задач для текущей области (до фильтров статуса и поиска).
const scopedTasks = computed(() => {
  if (scope.value === 'checklist') {
    return tasksStore.tasks.filter((task) => task.is_checklist && (authStore.isAdmin || task.created_by_id === authStore.user?.id || task.assignee?.id === authStore.user?.id))
  }
  if (scope.value === 'direction') {
    return tasksStore.tasks.filter((task) => task.direction?.id === activeDirectionId.value)
  }
  if (scope.value === 'mine') {
    return tasksStore.tasks.filter((task) => isAssignedTo(task, authStore.user?.id))
  }
  if (scope.value === 'private') {
    // Админы и секретарь видят все поручения, остальные — только выданные ими.
    return tasksStore.tasks.filter(
      (task) =>
        task.is_private && !task.is_checklist && (authStore.seesAllPrivate || task.created_by_id === authStore.user?.id),
    )
  }
  // «Все ТЗ» — сводка по направлениям; личные поручения живут вне них.
  return tasksStore.tasks.filter((task) => !task.is_private && !task.is_checklist)
})

const heading = computed(() => {
  if (scope.value === 'checklist') return { crumb: 'Чек-листы задач', title: 'Чек-листы задач', subtitle: 'Выданные вами и назначенные вам задачи' }
  if (scope.value === 'direction') {
    return {
      crumb: activeDirection.value?.name ?? '—',
      title: activeDirection.value?.name ?? '—',
      subtitle: `Задачи направления «${activeDirection.value?.name ?? ''}»`,
    }
  }
  if (scope.value === 'private') {
    return {
      crumb: 'Поручения',
      title: 'Поручения',
      subtitle: authStore.seesAllPrivate
        ? 'Личные поручения руководства. Их видят автор, исполнитель, админы и секретарь.'
        : 'Личные поручения, которые вы выдали. Их видят исполнитель, админы и секретарь.',
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

const stats = computed(() => progressStats(scopedTasks.value))

const visibleTasks = computed(() => {
  let result = scopedTasks.value

  const today = todayKey()
  if (statusFilter.value === 'overdue') {
    result = result.filter((task) => isOverdue(task, today))
  } else if (statusFilter.value !== null) {
    result = result.filter((task) => task.status === statusFilter.value)
  }
  const query = searchQuery.value.trim().toLowerCase()
  if (query) {
    result = result.filter(
      (task) =>
        task.title.toLowerCase().includes(query) || task.description.toLowerCase().includes(query),
    )
  }
  return [...result].sort((a, b) => byUrgency(a, b, today))
})

function handleTaskCreated(task) {
  tasksStore.addTask(task)
  if (task.is_checklist) router.push({ name: 'tasks', query: { checklist: '1' } })
}

const tasksByStatus = computed(() => {
  const groups = { todo: [], in_progress: [], in_review: [], done: [] }
  for (const task of visibleTasks.value) {
    groups[task.status]?.push(task)
  }
  return groups
})

// Двигать статус можно своей задачей или той, которой управляешь (права — с бэка).
function canMove(task) {
  if (task.is_checklist) return task.assignee?.id === authStore.user?.id
  return task.can_manage || isAssignedTo(task, authStore.user?.id)
}

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
  if (!task || task.status === status || (task.is_checklist && status === 'in_review')) return

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
        <div class="page-head__side">
          <button v-if="canCreateTask" class="create-btn" @click="createChecklist = false; showCreateModal = true">
            <BaseIcon name="plus" :size="16" />
            Выдать ТЗ
          </button>
          <button v-if="canCreateChecklist" class="create-btn" @click="createChecklist = true; showCreateModal = true">
            <BaseIcon name="plus" :size="16" />
            Выдать чек-лист
          </button>
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
        <button class="scope-switch__btn" :class="{ 'scope-switch__btn--active': scope === 'checklist' }" @click="router.push({ name: 'tasks', query: { checklist: '1' } })">
          Чек-листы задач
        </button>
        <button
          v-if="scope === 'direction'"
          class="scope-switch__btn scope-switch__btn--active scope-switch__btn--dir"
          @click="setScope('mine')"
        >
          {{ activeDirection?.short_code ?? '…' }} ✕
        </button>
      </div>

      <div v-if="scope === 'mine' && (fromLeadership.length || myEditorialItems.length)" class="inbox">
      <section v-if="fromLeadership.length" class="from-leadership">
        <div class="from-leadership__head">
          <span class="from-leadership__title">От руководства</span>
          <span class="from-leadership__count">{{ fromLeadership.length }}</span>
        </div>
        <ul class="from-leadership__list">
          <li v-for="item in shownLeadership" :key="item.id" class="fl-item">
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
              Выполнено
            </button>
          </li>
        </ul>
        <button
          v-if="fromLeadership.length > INBOX_LIMIT"
          class="inbox__more"
          @click="showAllLeadership = !showAllLeadership"
        >
          {{ showAllLeadership ? 'Свернуть' : `Ещё ${fromLeadership.length - INBOX_LIMIT}` }}
        </button>
      </section>

      <!-- Мои посты Редакции: видно каждому, кого назначили райтером/дизайнером. -->
      <section v-if="myEditorialItems.length" class="from-leadership my-posts">
        <div class="from-leadership__head">
          <span class="from-leadership__title">Мои посты</span>
          <span class="from-leadership__count">{{ myEditorialItems.length }}</span>
        </div>
        <ul class="from-leadership__list">
          <li
            v-for="item in shownPosts"
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
              Открыть
            </button>
          </li>
        </ul>
        <button
          v-if="myEditorialItems.length > INBOX_LIMIT"
          class="inbox__more"
          @click="showAllPosts = !showAllPosts"
        >
          {{ showAllPosts ? 'Свернуть' : `Ещё ${myEditorialItems.length - INBOX_LIMIT}` }}
        </button>
      </section>
      </div>

      <AppLoader v-if="tasksStore.isLoading" />
      <div v-else-if="tasksStore.loadError" class="state-message state-message--error">
        {{ tasksStore.loadError }}
      </div>

      <template v-else>
        <TaskProgress v-model:filter="statusFilter" :stats="stats" :checklist="scope === 'checklist'" />

        <div class="controls-row">
          <label class="search">
            <BaseIcon class="search__icon" name="search" :size="16" />
            <input v-model="searchQuery" class="search__input" type="text" :placeholder="scope === 'checklist' ? 'Поиск по чек-листам…' : 'Поиск по ТЗ…'" />
          </label>

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
        </div>

        <template v-if="viewMode === 'grid'">
          <div v-if="visibleTasks.length === 0" class="state-message">Задач не найдено.</div>
          <div v-else class="task-grid">
            <TaskCard
              v-for="task in visibleTasks"
              :key="task.id"
              :task="task"
              class="task-grid__card"
              @click="openedTaskId = task.id"
            />
          </div>
        </template>

        <template v-else>
          <div class="kanban-board" :class="{ 'kanban-board--checklist': scope === 'checklist' }">
            <section
              v-for="status in statusColumns"
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
                <span class="kanban-column__title">{{ scope === 'checklist' && status === 'todo' ? 'Не начато' : scope === 'checklist' && status === 'done' ? 'Сделано' : STATUS_META[status].label }}</span>
                <span class="kanban-column__count">{{ tasksByStatus[status].length }}</span>
              </div>

              <div class="kanban-column__cards">
                <div
                  v-for="task in tasksByStatus[status]"
                  :key="task.id"
                  class="kanban-card"
                  :draggable="canMove(task)"
                  @dragstart="onDragStart(task)"
                  @dragend="onDragEnd"
                >
                  <TaskCard :task="task" :show-status="false" @click="openedTaskId = task.id" />
                </div>
              </div>
            </section>
          </div>
          <p v-if="dragError" class="drag-error">{{ dragError }}</p>
        </template>
      </template>
    </main>

    <TaskSheet v-if="openedTask" :task="openedTask" @close="closeTask" />

    <CreateTaskModal
      v-if="showCreateModal"
      :directions="tasksStore.directions"
      :private-by-default="scope === 'private'"
      :checklist-by-default="createChecklist"
      @close="showCreateModal = false"
      @created="handleTaskCreated"
    />
  </div>
</template>

<style scoped>
/* Панель «От руководства» — записи таймлайна руководства по моим направлениям. */
.inbox {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap: 16px;
  align-items: start;
  margin-bottom: 24px;
}

.from-leadership {
  min-width: 0;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px 16px;
}

.inbox__more {
  margin-top: 8px;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
}

.inbox__more:hover {
  color: var(--text);
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
  font-family: var(--font-mono);
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
  gap: 12px;
  min-height: 32px;
}

.fl-item + .fl-item {
  border-top: 1px solid var(--border);
  padding-top: 8px;
}

.fl-item__date {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
  min-width: 56px;
}

.fl-chip {
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  border-radius: 6px;
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

.my-posts__status {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
}

.fl-item__title {
  flex-grow: 1;
  font-size: 13px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fl-item__done {
  border: 1px solid var(--border);
  background: transparent;
  color: var(--status-done);
  border-radius: 8px;
  height: 28px;
  padding: 0 10px;
  font-size: 12px;
  white-space: nowrap;
  flex-shrink: 0;
}

.fl-item__done:hover {
  background: color-mix(in srgb, var(--status-done) 14%, transparent);
}

.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
  margin-bottom: 24px;
}

.page-head__titles {
  min-width: 0;
}

.page-head__side {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
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
  max-width: 320px;
  min-width: 180px;
  display: flex;
  align-items: center;
  gap: 8px;
  height: var(--control-h);
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
  min-width: 0;
  padding: 0;
  font-size: 14px;
}

.search__input::placeholder {
  color: var(--text-faint);
}

.view-toggle {
  display: flex;
  gap: 2px;
  height: var(--control-h);
  /* Переключатель вида уходит вправо: слева поиск и фильтры, справа — вид. */
  margin-left: auto;
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
  height: 100%;
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

.task-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.task-grid__card {
  cursor: pointer;
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

.kanban-board--checklist {
  grid-template-columns: repeat(3, minmax(240px, 1fr));
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

/* Карточки в колонке лежат на более тёмном фоне, чтобы отделяться от самой колонки. */
.kanban-card :deep(.task-card) {
  background: var(--bg);
}

.kanban-card :deep(.task-card:hover) {
  background: var(--surface-hover);
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
    border-radius: 8px;
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
    font-size: 13px;
    transition: color 0.15s ease, background 0.15s ease;
  }

  .scope-switch__btn {
    min-height: 38px;
  }

  .scope-switch__btn--active {
    background: var(--accent-soft);
    color: var(--text);
    font-weight: 600;
  }

  .scope-switch__btn--dir {
    flex: 0 0 auto;
  }

  /* Заголовок и «Выдать ТЗ» — одной строкой: прогресс должен быть виден сразу. */
  .page-head {
    flex-wrap: nowrap;
    align-items: center;
    gap: var(--space-3);
  }

  .page-head__side {
    flex-shrink: 0;
  }

  .inbox {
    grid-template-columns: 1fr;
    margin-bottom: 16px;
  }

  .search {
    max-width: none;
    height: var(--control-h-touch);
  }

  /* Канбан на телефоне не нужен: перетаскивание не работает пальцем,
     статус меняется в шторке задачи. */
  .view-toggle,
  .kanban-board {
    display: none;
  }

  /* В мини-аппе каждый пиксель на счету — подзаголовок только на десктопе. */
  .page-head .subtitle {
    display: none;
  }

  .controls-row {
    margin-bottom: var(--space-3);
  }

  .task-grid {
    grid-template-columns: 1fr;
    gap: var(--space-2);
  }

  .task-grid :deep(.task-card) {
    padding: var(--space-3) var(--space-4);
  }

  .task-grid :deep(.task-card__desc) {
    -webkit-line-clamp: 1;
  }

  .task-grid :deep(.task-card:hover) {
    transform: none;
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
    margin: 0 -16px;
    padding: 0 16px 10px;
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
