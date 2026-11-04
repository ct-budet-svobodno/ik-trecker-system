<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppSidebar from '../components/AppSidebar.vue'
import BaseIcon from '../components/BaseIcon.vue'
import EventModal from '../components/EventModal.vue'
import TaskSheet from '../components/TaskSheet.vue'
import { fetchPersonalTodos, updatePersonalTodo } from '../api/personalTodos'
import { fetchMySurveys } from '../api/surveys'
import { useAuthStore } from '../stores/auth'
import { useEventsStore } from '../stores/events'
import { useTasksStore } from '../stores/tasks'
import { dayKey } from '../utils/dateKey'
import { formatTime } from '../utils/formatDateTime'
import { byUrgency, daysUntilDue, isAssignedTo, isOverdue, todayKey } from '../utils/taskProgress'

// Сколько строк в каждом блоке — главная показывает тезисно, остальное в разделах.
const EVENTS_LIMIT = 3
const TASKS_LIMIT = 5
const TODOS_LIMIT = 4

const STATUS_LABELS = {
  todo: 'К выполнению',
  in_progress: 'В работе',
  in_review: 'На проверке',
  done: 'Готово',
}

const authStore = useAuthStore()
const eventsStore = useEventsStore()
const tasksStore = useTasksStore()
const router = useRouter()

const todos = ref([])
const surveys = ref([])

onMounted(() => {
  eventsStore.loadAll()
  tasksStore.loadAll()
  fetchPersonalTodos(dayKey(new Date()))
    .then((data) => (todos.value = data))
    .catch(() => {})
  fetchMySurveys()
    .then((data) => (surveys.value = data))
    .catch(() => {})
})

const capitalize = (text) => text.charAt(0).toUpperCase() + text.slice(1)
const todayFmt = new Intl.DateTimeFormat('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })
const today = capitalize(todayFmt.format(new Date()))

// ФИО из анкеты — по имени (второе слово). Из двух слов имя не угадать
// («Имя Фамилия» и «Фамилия Имя» встречаются оба) — тогда целиком.
const greeting = computed(() => {
  const words = authStore.user?.full_name?.trim().split(/\s+/).filter(Boolean) ?? []
  if (!words.length) return 'Привет'
  return `Привет, ${words.length > 2 ? words[1] : words.join(' ')}`
})

// ── Анкеты, которые ждут ответа ──
const pendingSurveys = computed(() => surveys.value.filter((s) => !s.answers && s.status === 'open'))

// ── Ближайшие мероприятия: ещё не закончились ──
const upcomingEvents = computed(() => {
  const now = new Date()
  return [...eventsStore.events]
    .filter((e) => new Date(e.end_at ?? e.start_at) >= now)
    .sort((a, b) => a.start_at.localeCompare(b.start_at))
    .slice(0, EVENTS_LIMIT)
})

const shortMonthFmt = new Intl.DateTimeFormat('ru-RU', { month: 'short' })
const weekdayShortFmt = new Intl.DateTimeFormat('ru-RU', { weekday: 'short' })

function eventDay(event) {
  return new Date(event.start_at).getDate()
}

function eventMonth(event) {
  return shortMonthFmt.format(new Date(event.start_at)).replace('.', '')
}

function eventMeta(event) {
  const start = new Date(event.start_at)
  const parts = [capitalize(weekdayShortFmt.format(start)), formatTime(event.start_at)]
  if (event.location) parts.push(event.location)
  return parts.join(' · ')
}

const openedEvent = ref(null)

// ── Мои задачи: на мне и не закрыты, сначала горящие ──
const myOpenTasks = computed(() => {
  const uid = authStore.user?.id
  const key = todayKey()
  return tasksStore.tasks
    .filter((t) => isAssignedTo(t, uid) && t.status !== 'done')
    .sort((a, b) => byUrgency(a, b, key))
})

const shownTasks = computed(() => myOpenTasks.value.slice(0, TASKS_LIMIT))

const taskCounts = computed(() => {
  const key = todayKey()
  const counts = { todo: 0, in_progress: 0, in_review: 0, overdue: 0 }
  for (const task of myOpenTasks.value) {
    counts[task.status] += 1
    if (isOverdue(task, key)) counts.overdue += 1
  }
  return counts
})

// Выданные мной и сданные на проверку — ждут моего решения.
const toReview = computed(() => {
  const uid = authStore.user?.id
  return tasksStore.tasks.filter(
    (t) => t.created_by_id === uid && t.status === 'in_review' && !isAssignedTo(t, uid),
  )
})

const dueFmt = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' })

function dueLabel(task) {
  const days = daysUntilDue(task)
  if (days === null) return ''
  if (days < 0) return 'просрочено'
  if (days === 0) return 'сегодня'
  if (days === 1) return 'завтра'
  const [y, m, d] = task.due_date.split('-').map(Number)
  return `до ${dueFmt.format(new Date(y, m - 1, d)).replace('.', '')}`
}

function dueClass(task) {
  const days = daysUntilDue(task)
  if (days === null) return ''
  if (days < 0) return 'due--overdue'
  if (days <= 1) return 'due--soon'
  return ''
}

const openedTaskId = ref(null)
const openedTask = computed(() => tasksStore.tasks.find((t) => t.id === openedTaskId.value) ?? null)

// ── Мой день: пункты на сегодня ──
const todosDone = computed(() => todos.value.filter((t) => t.done).length)
const shownTodos = computed(() =>
  [...todos.value].sort((a, b) => Number(a.done) - Number(b.done)).slice(0, TODOS_LIMIT),
)

async function toggleTodo(todo) {
  todo.done = !todo.done
  try {
    await updatePersonalTodo(todo.id, { done: todo.done })
  } catch {
    todo.done = !todo.done
  }
}

function plural(n, one, few, many) {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few
  return many
}
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="home">
        <header>
          <p class="breadcrumb">ИК · Трекер / Главная</p>
          <h1>{{ greeting }}</h1>
          <p class="subtitle">{{ today }}</p>
        </header>

        <!-- Анкеты — короткой плашкой сверху: ответить нужно им, а не нам. -->
        <button
          v-for="survey in pendingSurveys"
          :key="survey.id"
          class="notice"
          @click="router.push({ name: 'survey-fill', params: { id: survey.id } })"
        >
          <span class="notice__icon"><BaseIcon name="checklist" :size="18" /></span>
          <span class="notice__body">
            <span class="notice__title">Ответьте на анкету</span>
            <span class="notice__text">{{ survey.title }}</span>
          </span>
          <BaseIcon name="chevron-right" :size="16" class="chevron" />
        </button>

        <div class="grid">
          <!-- Мероприятия -->
          <section class="panel">
            <div class="panel__head">
              <h2 class="panel__title">Ближайшие мероприятия</h2>
              <button class="panel__link" @click="router.push({ name: 'calendar' })">
                Календарь <BaseIcon name="chevron-right" :size="14" />
              </button>
            </div>
            <p v-if="!upcomingEvents.length" class="empty">
              {{ eventsStore.isLoading ? 'Загружаем…' : 'Пока ничего не запланировано' }}
            </p>
            <ul v-else class="list">
              <li v-for="event in upcomingEvents" :key="event.id">
                <button class="item" @click="openedEvent = event">
                  <span class="date">
                    <span class="date__day">{{ eventDay(event) }}</span>
                    <span class="date__month">{{ eventMonth(event) }}</span>
                  </span>
                  <span class="item__body">
                    <span class="item__title">{{ event.title }}</span>
                    <span class="item__meta">{{ eventMeta(event) }}</span>
                    <span v-if="event.my_rsvp || event.going_count" class="item__tags">
                      <span v-if="event.my_rsvp" class="rsvp-mark" :class="`rsvp-mark--${event.my_rsvp}`">
                        {{ event.my_rsvp === 'going' ? 'Вы придёте' : 'Вы не придёте' }}
                      </span>
                      <span v-if="event.going_count" class="item__meta">Придут: {{ event.going_count }}</span>
                    </span>
                    <span v-else class="ask">Ответьте, придёте ли</span>
                  </span>
                  <BaseIcon name="chevron-right" :size="16" class="chevron" />
                </button>
              </li>
            </ul>
          </section>

          <!-- Мои задачи -->
          <section class="panel">
            <div class="panel__head">
              <h2 class="panel__title">Мои задачи</h2>
              <button class="panel__link" @click="router.push({ name: 'tasks' })">
                Все <BaseIcon name="chevron-right" :size="14" />
              </button>
            </div>
            <div v-if="myOpenTasks.length" class="counters">
              <span v-if="taskCounts.overdue" class="counter counter--overdue">
                <b>{{ taskCounts.overdue }}</b> просрочено
              </span>
              <span v-if="taskCounts.in_progress" class="counter"><b>{{ taskCounts.in_progress }}</b> в работе</span>
              <span v-if="taskCounts.in_review" class="counter"><b>{{ taskCounts.in_review }}</b> на проверке</span>
              <span v-if="taskCounts.todo" class="counter"><b>{{ taskCounts.todo }}</b> к выполнению</span>
            </div>
            <p v-if="!myOpenTasks.length" class="empty">
              {{ tasksStore.isLoading ? 'Загружаем…' : 'Открытых задач нет — можно выдохнуть' }}
            </p>
            <ul v-else class="list">
              <li v-for="task in shownTasks" :key="task.id">
                <button class="item item--task" @click="openedTaskId = task.id">
                  <span class="status-dot" :class="`status-dot--${task.status}`" :title="STATUS_LABELS[task.status]" />
                  <span class="item__body">
                    <span class="item__title">{{ task.title }}</span>
                    <span class="item__meta">
                      {{ task.direction ? task.direction.short_code : 'Поручение' }}
                      · {{ STATUS_LABELS[task.status] }}
                    </span>
                  </span>
                  <span v-if="dueLabel(task)" class="due" :class="dueClass(task)">{{ dueLabel(task) }}</span>
                </button>
              </li>
            </ul>
            <button
              v-if="myOpenTasks.length > TASKS_LIMIT"
              class="more"
              @click="router.push({ name: 'tasks' })"
            >
              Ещё {{ myOpenTasks.length - TASKS_LIMIT }}
              {{ plural(myOpenTasks.length - TASKS_LIMIT, 'задача', 'задачи', 'задач') }}
            </button>
          </section>

          <!-- Ждут проверки — только если я что-то выдавал -->
          <section v-if="toReview.length" class="panel">
            <div class="panel__head">
              <h2 class="panel__title">Ждут вашей проверки</h2>
            </div>
            <ul class="list">
              <li v-for="task in toReview.slice(0, TASKS_LIMIT)" :key="task.id">
                <button class="item item--task" @click="openedTaskId = task.id">
                  <span class="status-dot status-dot--in_review" />
                  <span class="item__body">
                    <span class="item__title">{{ task.title }}</span>
                    <span class="item__meta">
                      {{ task.assignee?.full_name ?? '—' }}
                      <template v-if="task.direction"> · {{ task.direction.short_code }}</template>
                    </span>
                  </span>
                  <BaseIcon name="chevron-right" :size="16" class="chevron" />
                </button>
              </li>
            </ul>
          </section>

          <!-- Мой день -->
          <section class="panel">
            <div class="panel__head">
              <h2 class="panel__title">Мой день</h2>
              <button class="panel__link" @click="router.push({ name: 'my-day' })">
                Открыть <BaseIcon name="chevron-right" :size="14" />
              </button>
            </div>
            <template v-if="todos.length">
              <div class="day-progress">
                <span class="day-progress__bar">
                  <span :style="{ width: `${(todosDone / todos.length) * 100}%` }" />
                </span>
                <span class="day-progress__num">{{ todosDone }}/{{ todos.length }}</span>
              </div>
              <ul class="todos">
                <li v-for="todo in shownTodos" :key="todo.id">
                  <button class="todo" :class="{ 'todo--done': todo.done }" @click="toggleTodo(todo)">
                    <span class="todo__box">
                      <BaseIcon v-if="todo.done" name="check" :size="12" />
                    </span>
                    <span class="todo__title">{{ todo.title }}</span>
                  </button>
                </li>
              </ul>
            </template>
            <p v-else class="empty">
              На сегодня пусто.
              <button class="inline-link" @click="router.push({ name: 'my-day' })">Составить план</button>
            </p>
          </section>
        </div>
      </div>
    </main>

    <EventModal
      v-if="openedEvent"
      :event="openedEvent"
      :can-edit="['admin', 'manager'].includes(authStore.user?.role)"
      @close="openedEvent = null"
    />
    <TaskSheet v-if="openedTask" :task="openedTask" @close="openedTaskId = null" />
  </div>
</template>

<style scoped>
.home {
  max-width: 1080px;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.home header {
  margin-bottom: var(--space-2);
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
  align-items: start;
}

.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.panel__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.panel__link {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 13px;
  padding: 4px 0;
}

.panel__link:hover {
  color: var(--text);
}

.empty {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.inline-link {
  border: none;
  background: transparent;
  padding: 0;
  color: var(--accent);
  font-size: 13px;
}

.list,
.todos {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-raised);
  color: var(--text);
  text-align: left;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.item:hover {
  border-color: var(--border-strong);
  background: var(--surface-hover);
}

.item__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.item__title {
  font-size: 14px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item__meta {
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item__tags {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: 2px;
}

.ask {
  margin-top: 2px;
  font-size: 12px;
  color: var(--accent);
}

.chevron {
  flex-shrink: 0;
  color: var(--text-faint);
}

.date {
  width: 44px;
  flex-shrink: 0;
  padding: 4px 0;
  border-radius: var(--radius-md);
  background: var(--accent-soft);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.date__day {
  font: 500 18px/22px var(--font-mono);
}

.date__month {
  font-size: 11px;
  color: var(--text-muted);
}

.rsvp-mark {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
}

.rsvp-mark--going {
  background: color-mix(in srgb, var(--rsvp-yes) 20%, transparent);
  color: var(--rsvp-yes);
}

.rsvp-mark--not_going {
  background: color-mix(in srgb, var(--rsvp-no) 20%, transparent);
  color: var(--rsvp-no);
}

/* ── Задачи ── */
.counters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.counter {
  font-size: 12px;
  color: var(--text-muted);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  background: var(--surface-raised);
}

.counter b {
  color: var(--text);
  font-weight: 600;
}

.counter--overdue,
.counter--overdue b {
  color: var(--danger);
}

.status-dot {
  width: 8px;
  height: 8px;
  flex-shrink: 0;
  border-radius: 50%;
}

.status-dot--todo { background: var(--status-todo); }
.status-dot--in_progress { background: var(--status-progress); }
.status-dot--in_review { background: var(--status-review); }
.status-dot--done { background: var(--status-done); }

.due {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
}

.due--soon {
  color: var(--status-progress);
}

.due--overdue {
  color: var(--danger);
}

.more {
  align-self: flex-start;
  border: none;
  background: transparent;
  padding: 0;
  color: var(--accent);
  font-size: 13px;
}

/* ── Мой день ── */
.day-progress {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.day-progress__bar {
  flex: 1;
  height: 4px;
  border-radius: var(--radius-full);
  background: var(--border);
  overflow: hidden;
}

.day-progress__bar span {
  display: block;
  height: 100%;
  background: var(--success);
  transition: width 0.2s ease;
}

.day-progress__num {
  font: 500 12px var(--font-mono);
  color: var(--text-muted);
}

.todo {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px 2px;
  border: none;
  background: transparent;
  color: var(--text);
  text-align: left;
  font-size: 14px;
}

.todo__box {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid var(--border-strong);
  border-radius: var(--radius-sm);
}

.todo--done .todo__box {
  border-color: var(--success);
  background: var(--success);
  color: var(--on-success);
}

.todo__title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.todo--done .todo__title {
  color: var(--text-muted);
  text-decoration: line-through;
}

/* ── Плашка анкеты ── */
.notice {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  padding: var(--space-3) var(--space-4);
  border: 1px solid color-mix(in srgb, var(--accent) 45%, transparent);
  border-radius: var(--radius-lg);
  background: var(--accent-soft);
  color: var(--text);
  text-align: left;
}

.notice__icon {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  background: var(--accent);
  color: var(--text);
}

.notice__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.notice__title {
  font-size: 14px;
  font-weight: 600;
}

.notice__text {
  font-size: 13px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 768px) {
  .panel {
    padding: var(--space-3);
  }

  .todo {
    min-height: var(--control-h-touch);
  }
}
</style>
