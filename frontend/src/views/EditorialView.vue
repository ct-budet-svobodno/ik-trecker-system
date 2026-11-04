<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import EditorialPostModal from '../components/EditorialPostModal.vue'
import { aggregatePostStatus, EDITORIAL_STATUS_COLORS } from '../constants/editorialMeta'
import { useAuthStore } from '../stores/auth'
import { useEditorialStore } from '../stores/editorial'
import { getMonthGrid, isSameDay } from '../utils/calendarGrid'
import { dayKey } from '../utils/dateKey'
import { formatMonthYear } from '../utils/formatDateTime'

const WEEKDAY_LABELS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

const router = useRouter()
const authStore = useAuthStore()
const store = useEditorialStore()

const today = new Date()
const viewYear = ref(today.getFullYear())
const viewMonth = ref(today.getMonth())

const canManage = computed(() => authStore.isEditorialEditor)

const showModal = ref(false)
const modalDate = ref('')

// Мобильный режим: тап по дню выбирает его (список ниже), создание — кнопкой в шапке.
const isMobile = window.matchMedia('(max-width: 768px)').matches
const selectedDayKey = ref(dayKey(today))

const selectedDayPosts = computed(() =>
  store.posts.filter((post) => post.date === selectedDayKey.value),
)

const selectedDayLabel = computed(() => {
  const [y, m, d] = selectedDayKey.value.split('-').map(Number)
  return new Intl.DateTimeFormat('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' }).format(
    new Date(y, m - 1, d),
  )
})

function onDayClick(day) {
  if (isMobile) {
    selectedDayKey.value = dayKey(day.date)
    return
  }
  openCreate(day)
}

const grid = computed(() => getMonthGrid(viewYear.value, viewMonth.value))
const monthLabel = computed(() => formatMonthYear(new Date(viewYear.value, viewMonth.value, 1)))

const weeks = computed(() =>
  grid.value.map((week) =>
    week.map((day) => ({
      ...day,
      isToday: isSameDay(day.date, today),
      posts: store.posts.filter((post) => post.date === dayKey(day.date)),
    })),
  ),
)

async function loadMonth() {
  const flat = grid.value.flat()
  await store.load({
    dateFrom: dayKey(flat[0].date),
    dateTo: dayKey(flat[flat.length - 1].date),
  })
}

onMounted(loadMonth)
watch([viewYear, viewMonth], loadMonth)

function goToPreviousMonth() {
  const date = new Date(viewYear.value, viewMonth.value - 1, 1)
  viewYear.value = date.getFullYear()
  viewMonth.value = date.getMonth()
}

function goToNextMonth() {
  const date = new Date(viewYear.value, viewMonth.value + 1, 1)
  viewYear.value = date.getFullYear()
  viewMonth.value = date.getMonth()
}

function goToToday() {
  viewYear.value = today.getFullYear()
  viewMonth.value = today.getMonth()
}

function statusColor(post) {
  return EDITORIAL_STATUS_COLORS[aggregatePostStatus(post)]
}

function openPost(post) {
  router.push({ name: 'editorial-post', params: { id: post.id } })
}

function openCreate(day) {
  if (!canManage.value) return
  // Без дня (кнопка в шапке): на мобильных подставляем выбранный день.
  modalDate.value = day ? dayKey(day.date) : isMobile ? selectedDayKey.value : dayKey(today)
  showModal.value = true
}

function closeModal() {
  showModal.value = false
}
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="app-main__header">
        <div>
          <p class="breadcrumb">ИК · ТРЕКЕР / РЕДАКЦИЯ</p>
          <h1>Редакция</h1>
          <p class="subtitle">SMM-план: посты СМИ и Дизайна по датам выхода.</p>
        </div>
        <button v-if="canManage" class="create-btn" @click="openCreate(null)">+ Новый пост</button>
      </div>

      <div class="month-nav">
        <button class="month-nav__btn" @click="goToPreviousMonth">‹</button>
        <span class="month-nav__label">{{ monthLabel }}</span>
        <button class="month-nav__btn" @click="goToNextMonth">›</button>
        <button class="month-nav__today" @click="goToToday">Сегодня</button>
      </div>

      <p v-if="store.loadError" class="state-message state-message--error">{{ store.loadError }}</p>
      <AppLoader v-else-if="store.isLoading" />

      <div v-else class="calendar">
        <div class="calendar__weekdays">
          <span v-for="label in WEEKDAY_LABELS" :key="label">{{ label }}</span>
        </div>
        <div class="calendar__grid">
          <div
            v-for="day in weeks.flat()"
            :key="day.date.toISOString()"
            class="calendar__day"
            :class="{
              'calendar__day--muted': !day.isCurrentMonth,
              'calendar__day--today': day.isToday,
              'calendar__day--editable': canManage,
              'calendar__day--selected': dayKey(day.date) === selectedDayKey,
            }"
            @click="onDayClick(day)"
          >
            <span class="calendar__day-number">{{ day.date.getDate() }}</span>
            <button
              v-for="post in day.posts"
              :key="post.id"
              class="post-chip"
              :title="post.title"
              @click.stop="openPost(post)"
            >
              <span class="post-chip__dot" :style="{ background: statusColor(post) }" />
              <span class="post-chip__title">{{ post.title }}</span>
            </button>
          </div>
        </div>

        <!-- Посты выбранного дня — только на мобильных. -->
        <section class="day-agenda">
          <p class="day-agenda__title">{{ selectedDayLabel }}</p>
          <p v-if="!selectedDayPosts.length" class="day-agenda__empty">Нет постов на этот день.</p>
          <button
            v-for="post in selectedDayPosts"
            :key="post.id"
            class="day-agenda__item"
            @click="openPost(post)"
          >
            <span class="post-chip__dot" :style="{ background: statusColor(post) }" />
            <span class="day-agenda__name">{{ post.title }}</span>
            <span v-if="post.format" class="day-agenda__format">{{ post.format }}</span>
          </button>
        </section>
      </div>
    </main>

    <EditorialPostModal v-if="showModal" :date="modalDate" @close="closeModal" />
  </div>
</template>

<style scoped>
.app-main__header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.month-nav {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.month-nav__btn {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  width: 32px;
  height: 32px;
  border-radius: 8px;
  font-size: 16px;
}

.month-nav__btn:hover {
  border-color: var(--accent);
}

.month-nav__label {
  font-weight: 600;
  text-transform: capitalize;
  min-width: 160px;
}

.month-nav__today {
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 13px;
}

.month-nav__today:hover {
  border-color: var(--accent);
  color: var(--text);
}

.calendar__weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 1px;
  font-size: 12px;
  color: var(--text-muted);
  padding: 0 2px 8px;
}

.calendar__grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}

.calendar__day {
  background: var(--surface);
  min-height: 108px;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.calendar__day--editable {
  cursor: pointer;
}

.calendar__day--muted {
  background: var(--bg);
  color: var(--text-muted);
}

.calendar__day--muted .calendar__day-number {
  color: var(--text-muted);
}

.calendar__day--today .calendar__day-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
}

.calendar__day-number {
  font-size: 13px;
  font-weight: 600;
}

.post-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--border);
  background: var(--surface-raised);
  color: var(--text);
  border-radius: 6px;
  padding: 4px 6px;
  font-size: 12px;
  text-align: left;
  width: 100%;
}

.post-chip:hover {
  border-color: var(--border-strong);
}

.post-chip__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.post-chip__title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.state-message {
  color: var(--text-muted);
  padding: 40px 0;
  text-align: center;
}

.state-message--error {
  color: var(--danger);
}

/* Список постов выбранного дня — мобильный компаньон сетки. */
.day-agenda {
  display: none;
}

@media (max-width: 768px) {
  /* Компактная сетка: посты превращаются в статусные точки. */
  .calendar__day {
    min-height: 52px;
    padding: 5px 4px;
    flex-direction: row;
    flex-wrap: wrap;
    align-content: flex-start;
    gap: 3px;
  }

  .calendar__day-number {
    font-size: 12px;
    width: 100%;
  }

  .post-chip {
    width: auto;
    border: none;
    background: transparent;
    padding: 0;
    pointer-events: none; /* тап уходит дню — посты открываются из списка ниже */
  }

  .post-chip__dot {
    width: 7px;
    height: 7px;
  }

  .post-chip__title {
    display: none;
  }

  .calendar__day--selected {
    outline: 1.5px solid var(--accent);
    outline-offset: -1.5px;
    border-radius: 8px;
  }

  .day-agenda {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 16px;
  }

  .day-agenda__title {
    font-size: 13px;
    font-weight: 600;
    text-transform: capitalize;
    color: var(--text-muted);
    margin: 0 0 2px;
  }

  .day-agenda__empty {
    color: var(--text-faint);
    font-size: 13px;
    margin: 0;
  }

  .day-agenda__item {
    display: flex;
    align-items: center;
    gap: 10px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
    border-radius: 8px;
    padding: 11px 13px;
    text-align: left;
  }

  .day-agenda__item:active {
    background: var(--surface-raised);
  }

  .day-agenda__item .post-chip__dot {
    pointer-events: auto;
    flex-shrink: 0;
  }

  .day-agenda__name {
    font-size: 14px;
    min-width: 0;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .day-agenda__format {
    font-size: 11px;
    color: var(--text-faint);
    flex-shrink: 0;
  }
}
</style>
