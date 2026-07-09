<script setup>
import { computed, onMounted, ref } from 'vue'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import EventModal from '../components/EventModal.vue'
import { useAuthStore } from '../stores/auth'
import { useEventsStore } from '../stores/events'
import { getMonthGrid, isSameDay } from '../utils/calendarGrid'
import { dayKey, parseDateOnly } from '../utils/dateKey'
import { formatMonthYear, formatTime } from '../utils/formatDateTime'

const WEEKDAY_LABELS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

const authStore = useAuthStore()
const eventsStore = useEventsStore()

const today = new Date()
const viewYear = ref(today.getFullYear())
const viewMonth = ref(today.getMonth())

const showModal = ref(false)
const editingEvent = ref(null)
const defaultStartAt = ref('')

const canManageEvents = computed(() => ['admin', 'manager'].includes(authStore.user?.role))

onMounted(() => eventsStore.loadAll())

const monthLabel = computed(() => formatMonthYear(new Date(viewYear.value, viewMonth.value, 1)))

const weeks = computed(() => {
  const grid = getMonthGrid(viewYear.value, viewMonth.value)
  return grid.map((week) =>
    week.map((day) => ({
      ...day,
      isToday: isSameDay(day.date, today),
      events: eventsStore.events.filter((event) => isSameDay(new Date(event.start_at), day.date)),
    })),
  )
})

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

// Мобильная «повестка дня»: тап по дню выбирает его, события показываются списком.
const selectedDayKey = ref(dayKey(today))

function selectDay(day) {
  selectedDayKey.value = dayKey(day.date)
}

const selectedDayEvents = computed(() => {
  const selected = parseDateOnly(selectedDayKey.value)
  return eventsStore.events
    .filter((event) => isSameDay(new Date(event.start_at), selected))
    .sort((a, b) => a.start_at.localeCompare(b.start_at))
})

const selectedDayLabel = computed(() =>
  new Intl.DateTimeFormat('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' }).format(
    parseDateOnly(selectedDayKey.value),
  ),
)

function openCreateModal() {
  editingEvent.value = null
  const now = new Date()
  now.setHours(12, 0, 0, 0)
  const pad = (n) => String(n).padStart(2, '0')
  defaultStartAt.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T12:00`
  showModal.value = true
}

function openEditModal(event) {
  editingEvent.value = event
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  editingEvent.value = null
}
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="app-main__header">
        <div>
          <p class="breadcrumb">ИК · ТРЕКЕР / КАЛЕНДАРЬ</p>
          <h1>Календарь</h1>
        </div>
        <button v-if="canManageEvents" class="create-btn" @click="openCreateModal">
          + Назначить мероприятие
        </button>
      </div>

      <div class="month-nav">
        <button class="month-nav__btn" @click="goToPreviousMonth">‹</button>
        <span class="month-nav__label">{{ monthLabel }}</span>
        <button class="month-nav__btn" @click="goToNextMonth">›</button>
        <button class="month-nav__today" @click="goToToday">Сегодня</button>
      </div>

      <AppLoader v-if="eventsStore.isLoading" />
      <div v-else-if="eventsStore.loadError" class="state-message state-message--error">
        {{ eventsStore.loadError }}
      </div>

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
              'calendar__day--selected': dayKey(day.date) === selectedDayKey,
            }"
            @click="selectDay(day)"
          >
            <span class="calendar__day-number">{{ day.date.getDate() }}</span>
            <button
              v-for="event in day.events"
              :key="event.id"
              class="calendar__event"
              :title="event.title"
              @click.stop="openEditModal(event)"
            >
              <span class="calendar__event-time" v-if="event.start_at">{{ formatTime(event.start_at) }}</span>
              {{ event.title }}
            </button>
          </div>
        </div>

        <!-- Повестка выбранного дня — только на мобильных. -->
        <section class="day-agenda">
          <p class="day-agenda__title">{{ selectedDayLabel }}</p>
          <p v-if="!selectedDayEvents.length" class="day-agenda__empty">Нет мероприятий.</p>
          <button
            v-for="event in selectedDayEvents"
            :key="event.id"
            class="day-agenda__item"
            @click="openEditModal(event)"
          >
            <span class="day-agenda__time">{{ formatTime(event.start_at) }}</span>
            <span class="day-agenda__name">{{ event.title }}</span>
          </button>
        </section>
      </div>
    </main>

    <EventModal
      v-if="showModal"
      :event="editingEvent"
      :default-start-at="defaultStartAt"
      @close="closeModal"
    />
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}

.app-main {
  flex-grow: 1;
  padding: 28px 32px;
  max-width: 100%;
  overflow-x: hidden;
}

.app-main__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.breadcrumb {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0 0 6px;
}

h1 {
  font-size: 26px;
  margin: 0;
  letter-spacing: 0.02em;
}

.create-btn {
  border: none;
  border-radius: 8px;
  background: var(--success);
  color: #0c1410;
  font-weight: 600;
  padding: 9px 16px;
  white-space: nowrap;
}

.create-btn:hover {
  background: var(--success-hover);
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
  min-height: 100px;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
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

.calendar__event {
  border: none;
  background: var(--accent-soft);
  color: var(--text);
  border-radius: 6px;
  padding: 3px 6px;
  font-size: 11px;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.calendar__event:hover {
  background: var(--accent);
  color: #fff;
}

.calendar__event-time {
  font-weight: 600;
  margin-right: 4px;
}

.state-message {
  color: var(--text-muted);
  padding: 40px 0;
  text-align: center;
}

.state-message--error {
  color: var(--danger);
}

/* Повестка дня — мобильный компаньон сетки. */
.day-agenda {
  display: none;
}

@media (max-width: 768px) {
  /* Компактная сетка: события превращаются в точки, тап по дню выбирает его. */
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

  .calendar__event {
    width: 7px;
    height: 7px;
    padding: 0;
    border-radius: 50%;
    background: var(--accent);
    font-size: 0;
    pointer-events: none; /* тап уходит дню — события открываются из списка ниже */
    flex: 0 0 auto;
  }

  .calendar__event-time {
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
    gap: 12px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
    border-radius: 10px;
    padding: 11px 13px;
    text-align: left;
  }

  .day-agenda__item:active {
    background: var(--surface-raised);
  }

  .day-agenda__time {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--accent);
    flex-shrink: 0;
  }

  .day-agenda__name {
    font-size: 14px;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}
</style>
