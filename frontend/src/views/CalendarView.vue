<script setup>
import { computed, onMounted, ref } from 'vue'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import BaseIcon from '../components/BaseIcon.vue'
import EventModal from '../components/EventModal.vue'
import { useAuthStore } from '../stores/auth'
import { useEventsStore } from '../stores/events'
import { getMonthGrid, isSameDay } from '../utils/calendarGrid'
import { dayKey, parseDateOnly } from '../utils/dateKey'
import { formatMonthYear, formatTime } from '../utils/formatDateTime'

const WEEKDAY_LABELS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
// Сколько мероприятий видно в клетке на десктопе, остальные — «ещё N».
const EVENTS_IN_CELL = 2
const UPCOMING_LIMIT = 5

const authStore = useAuthStore()
const eventsStore = useEventsStore()

const today = new Date()
const viewYear = ref(today.getFullYear())
const viewMonth = ref(today.getMonth())

const showModal = ref(false)
const editingEvent = ref(null)
const defaultDate = ref('')

const canManageEvents = computed(() => ['admin', 'manager'].includes(authStore.user?.role))

onMounted(() => eventsStore.loadAll())

const capitalize = (text) => text.charAt(0).toUpperCase() + text.slice(1)

// «октябрь 2026 г.» → месяц и год отдельно: год набираем приглушённо.
const monthName = computed(() =>
  capitalize(formatMonthYear(new Date(viewYear.value, viewMonth.value, 1)).replace(/\s*\d{4}\s*г\.$/, '')),
)
const isCurrentMonth = computed(
  () => viewYear.value === today.getFullYear() && viewMonth.value === today.getMonth(),
)

const sortedEvents = computed(() =>
  [...eventsStore.events].sort((a, b) => a.start_at.localeCompare(b.start_at)),
)

function eventsOn(date) {
  return sortedEvents.value.filter((event) => isSameDay(new Date(event.start_at), date))
}

const days = computed(() =>
  getMonthGrid(viewYear.value, viewMonth.value)
    .flat()
    .map((day, idx) => ({
      ...day,
      key: dayKey(day.date),
      isToday: isSameDay(day.date, today),
      isWeekend: idx % 7 >= 5,
      events: eventsOn(day.date),
    })),
)

const monthEventsCount = computed(
  () => days.value.filter((d) => d.isCurrentMonth).reduce((sum, d) => sum + d.events.length, 0),
)

function shiftMonth(delta) {
  const date = new Date(viewYear.value, viewMonth.value + delta, 1)
  viewYear.value = date.getFullYear()
  viewMonth.value = date.getMonth()
}

function goToToday() {
  viewYear.value = today.getFullYear()
  viewMonth.value = today.getMonth()
  selectedDayKey.value = dayKey(today)
}

// Выбранный день: его мероприятия — в панели справа (на телефоне — под сеткой).
const selectedDayKey = ref(dayKey(today))
const selectedDate = computed(() => parseDateOnly(selectedDayKey.value))
const selectedDayEvents = computed(() => eventsOn(selectedDate.value))

function selectDay(day) {
  selectedDayKey.value = day.key
  // Клик по дню соседнего месяца перелистывает на него.
  if (!day.isCurrentMonth) {
    viewYear.value = day.date.getFullYear()
    viewMonth.value = day.date.getMonth()
  }
}

const weekdayFmt = new Intl.DateTimeFormat('ru-RU', { weekday: 'long' })
const dayMonthFmt = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long' })
const shortMonthFmt = new Intl.DateTimeFormat('ru-RU', { month: 'short' })

const selectedWeekday = computed(() => capitalize(weekdayFmt.format(selectedDate.value)))
const selectedDayMonth = computed(() => dayMonthFmt.format(selectedDate.value))
const selectedIsToday = computed(() => isSameDay(selectedDate.value, today))

// Ближайшие — от сегодняшнего утра (утреннее мероприятие не пропадает до вечера),
// без выбранного дня: его мероприятия и так показаны выше.
const upcoming = computed(() => {
  const from = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  return sortedEvents.value
    .filter((e) => new Date(e.start_at) >= from && !isSameDay(new Date(e.start_at), selectedDate.value))
    .slice(0, UPCOMING_LIMIT)
})

function timeRange(event) {
  return event.end_at ? `${formatTime(event.start_at)} – ${formatTime(event.end_at)}` : formatTime(event.start_at)
}

function upcomingDay(event) {
  return new Date(event.start_at).getDate()
}

function upcomingMonth(event) {
  return shortMonthFmt.format(new Date(event.start_at)).replace('.', '')
}

function plural(n, one, few, many) {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few
  return many
}

function openCreateModal() {
  editingEvent.value = null
  defaultDate.value = selectedDayKey.value
  showModal.value = true
}

function openEvent(event) {
  editingEvent.value = event
  showModal.value = true
}

function openUpcoming(event) {
  const date = new Date(event.start_at)
  selectedDayKey.value = dayKey(date)
  viewYear.value = date.getFullYear()
  viewMonth.value = date.getMonth()
  openEvent(event)
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
          <p class="subtitle">
            <template v-if="monthEventsCount">
              {{ monthEventsCount }} {{ plural(monthEventsCount, 'мероприятие', 'мероприятия', 'мероприятий') }}
              в этом месяце
            </template>
            <template v-else>В этом месяце мероприятий пока нет</template>
          </p>
        </div>
        <button v-if="canManageEvents" class="create-btn" @click="openCreateModal">
          <BaseIcon name="plus" :size="16" />
          Мероприятие
        </button>
      </div>

      <AppLoader v-if="eventsStore.isLoading" />
      <p v-else-if="eventsStore.loadError" class="state-error">{{ eventsStore.loadError }}</p>

      <div v-else class="cal">
        <!-- Месяц -->
        <section class="board">
          <header class="board__bar">
            <h2 class="board__month">
              {{ monthName }} <span class="board__year">{{ viewYear }}</span>
            </h2>
            <div class="board__nav">
              <button v-if="!isCurrentMonth" class="board__today" @click="goToToday">Сегодня</button>
              <button class="board__arrow" aria-label="Предыдущий месяц" @click="shiftMonth(-1)">
                <BaseIcon name="chevron-left" :size="18" />
              </button>
              <button class="board__arrow" aria-label="Следующий месяц" @click="shiftMonth(1)">
                <BaseIcon name="chevron-right" :size="18" />
              </button>
            </div>
          </header>

          <div class="weekdays">
            <span
              v-for="(label, idx) in WEEKDAY_LABELS"
              :key="label"
              :class="{ 'weekdays__day--weekend': idx >= 5 }"
            >
              {{ label }}
            </span>
          </div>

          <div class="grid">
            <button
              v-for="day in days"
              :key="day.key"
              type="button"
              class="cell"
              :class="{
                'cell--muted': !day.isCurrentMonth,
                'cell--weekend': day.isWeekend,
                'cell--today': day.isToday,
                'cell--selected': day.key === selectedDayKey,
              }"
              :aria-label="`${day.date.getDate()}, мероприятий: ${day.events.length}`"
              @click="selectDay(day)"
            >
              <span class="cell__num">{{ day.date.getDate() }}</span>

              <!-- Десктоп: мероприятия списком -->
              <span class="cell__events">
                <span
                  v-for="event in day.events.slice(0, EVENTS_IN_CELL)"
                  :key="event.id"
                  class="cell__event"
                  :title="`${formatTime(event.start_at)} ${event.title}`"
                  @click.stop="openEvent(event)"
                >
                  <span class="cell__event-time">{{ formatTime(event.start_at) }}</span>
                  <span class="cell__event-title">{{ event.title }}</span>
                </span>
                <span v-if="day.events.length > EVENTS_IN_CELL" class="cell__more">
                  ещё {{ day.events.length - EVENTS_IN_CELL }}
                </span>
              </span>

              <!-- Телефон: точки -->
              <span v-if="day.events.length" class="cell__dots" aria-hidden="true">
                <span v-for="n in Math.min(day.events.length, 3)" :key="n" class="cell__dot" />
              </span>
            </button>
          </div>
        </section>

        <aside class="side">
          <!-- Выбранный день -->
          <section class="panel">
            <header class="day-head">
              <span class="day-head__num">{{ selectedDate.getDate() }}</span>
              <span class="day-head__text">
                <span class="day-head__weekday">
                  {{ selectedWeekday }}
                  <span v-if="selectedIsToday" class="day-head__badge">сегодня</span>
                </span>
                <span class="day-head__date">{{ selectedDayMonth }}</span>
              </span>
              <button
                v-if="canManageEvents"
                class="day-head__add"
                aria-label="Добавить мероприятие на этот день"
                title="Добавить на этот день"
                @click="openCreateModal"
              >
                <BaseIcon name="plus" :size="16" />
              </button>
            </header>

            <p v-if="!selectedDayEvents.length" class="panel__empty">
              {{ canManageEvents ? 'Ничего не запланировано — нажмите +, чтобы добавить' : 'Ничего не запланировано' }}
            </p>
            <ul v-else class="agenda">
              <li v-for="event in selectedDayEvents" :key="event.id">
                <button class="agenda__item" @click="openEvent(event)">
                  <span class="agenda__time">
                    <span>{{ formatTime(event.start_at) }}</span>
                    <span v-if="event.end_at" class="agenda__end">{{ formatTime(event.end_at) }}</span>
                  </span>
                  <span class="agenda__body">
                    <span class="agenda__title">{{ event.title }}</span>
                    <span v-if="event.location" class="agenda__place">{{ event.location }}</span>
                    <span class="agenda__rsvp">
                      <span v-if="event.my_rsvp" class="rsvp-mark" :class="`rsvp-mark--${event.my_rsvp}`">
                        {{ event.my_rsvp === 'going' ? 'Вы придёте' : 'Вы не придёте' }}
                      </span>
                      <span v-if="event.going_count">Придут: {{ event.going_count }}</span>
                    </span>
                  </span>
                  <BaseIcon name="chevron-right" :size="16" class="agenda__chevron" />
                </button>
              </li>
            </ul>
          </section>

          <!-- Ближайшие -->
          <section v-if="upcoming.length" class="panel">
            <h3 class="panel__title">Ближайшие</h3>
            <ul class="upcoming">
              <li v-for="event in upcoming" :key="event.id">
                <button class="upcoming__item" @click="openUpcoming(event)">
                  <span class="upcoming__date">
                    <span class="upcoming__day">{{ upcomingDay(event) }}</span>
                    <span class="upcoming__month">{{ upcomingMonth(event) }}</span>
                  </span>
                  <span class="upcoming__body">
                    <span class="upcoming__title">{{ event.title }}</span>
                    <span class="upcoming__meta">
                      {{ timeRange(event) }}<template v-if="event.location"> · {{ event.location }}</template>
                    </span>
                    <span v-if="event.my_rsvp" class="rsvp-mark" :class="`rsvp-mark--${event.my_rsvp}`">
                      {{ event.my_rsvp === 'going' ? 'Вы придёте' : 'Вы не придёте' }}
                    </span>
                  </span>
                </button>
              </li>
            </ul>
          </section>
        </aside>
      </div>
    </main>

    <EventModal
      v-if="showModal"
      :event="editingEvent"
      :default-date="defaultDate"
      :can-edit="canManageEvents"
      @close="closeModal"
    />
  </div>
</template>

<style scoped>
.app-main__header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
  margin-bottom: var(--space-5);
}

.state-error {
  color: var(--danger);
  padding: var(--space-10) 0;
  text-align: center;
}

.cal {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: var(--space-5);
  align-items: start;
}

/* ── Месяц ── */
.board {
  padding: var(--space-4);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.board__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.board__month {
  margin: 0;
  font-size: 20px;
  line-height: 26px;
  font-weight: 600;
}

.board__year {
  font-weight: 400;
  color: var(--text-muted);
}

.board__nav {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.board__arrow,
.board__today {
  height: var(--control-h);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.board__arrow {
  width: var(--control-h);
}

.board__today {
  padding: 0 12px;
  margin-right: var(--space-1);
  font-size: 13px;
  color: var(--text-muted);
}

.board__arrow:hover,
.board__today:hover {
  border-color: var(--border-strong);
  background: var(--surface-hover);
  color: var(--text);
}

.weekdays {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 4px;
  margin-bottom: var(--space-2);
  font-size: 12px;
  color: var(--text-faint);
}

.weekdays span {
  padding: 0 var(--space-2);
}

.weekdays__day--weekend {
  color: var(--text-muted);
}

.grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 4px;
}

.cell {
  position: relative;
  container-type: inline-size;
  min-width: 0;
  min-height: 104px;
  padding: var(--space-2);
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 6px;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  background: var(--surface-raised);
  color: var(--text);
  text-align: left;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.cell:hover {
  border-color: var(--border-strong);
}

.cell--weekend {
  background: color-mix(in srgb, var(--surface-raised) 70%, var(--surface));
}

.cell--muted {
  background: transparent;
  color: var(--text-faint);
}

.cell--selected {
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 8%, var(--surface-raised));
}

.cell__num {
  align-self: flex-start;
  min-width: 26px;
  height: 26px;
  padding: 0 6px;
  border-radius: var(--radius-full);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font: 500 13px/1 var(--font-mono);
}

.cell--today .cell__num {
  background: var(--accent);
  color: #fff;
}

.cell__events {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.cell__event {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  padding: 3px 6px;
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  font-size: 12px;
  line-height: 16px;
  cursor: pointer;
}

.cell__event:hover {
  background: color-mix(in srgb, var(--accent) 35%, var(--surface-raised));
}

.cell__event-time {
  flex-shrink: 0;
  font: 500 11px/16px var(--font-mono);
  color: var(--text-muted);
}

.cell__event-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Узкая клетка: время прячем, название важнее. */
@container (max-width: 120px) {
  .cell__event-time {
    display: none;
  }
}

.cell__more {
  padding: 0 6px;
  font-size: 11px;
  color: var(--text-muted);
}

.cell__dots {
  display: none;
}

/* ── Панель справа ── */
.side {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.panel {
  padding: var(--space-4);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.panel__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.panel__empty {
  margin: 0;
  padding: var(--space-4);
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
  color: var(--text-muted);
  font-size: 13px;
  line-height: 19px;
  text-align: center;
}

.day-head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.day-head__num {
  font: 500 24px/1 var(--font-mono);
  min-width: 36px;
}

.day-head__text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.day-head__weekday {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
}

.day-head__badge {
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  font-size: 11px;
  font-weight: 500;
}

.day-head__date {
  font-size: 13px;
  color: var(--text-muted);
}

.day-head__add {
  width: var(--control-h);
  height: var(--control-h);
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text);
}

.day-head__add:hover {
  border-color: var(--border-strong);
  background: var(--surface-hover);
}

.agenda__rsvp {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  font-size: 12px;
  color: var(--text-muted);
}

.agenda__rsvp:empty {
  display: none;
}

.rsvp-mark {
  align-self: flex-start;
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

.agenda,
.upcoming {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.agenda__item,
.upcoming__item {
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

.agenda__item:hover,
.upcoming__item:hover {
  border-color: var(--border-strong);
  background: var(--surface-hover);
}

.agenda__time {
  display: flex;
  flex-direction: column;
  min-width: 44px;
  font: 500 13px/18px var(--font-mono);
}

.agenda__end {
  font-size: 11px;
  color: var(--text-muted);
}

.agenda__body,
.upcoming__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.agenda__title,
.upcoming__title {
  font-size: 14px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agenda__place,
.upcoming__meta {
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agenda__chevron {
  color: var(--text-faint);
}

.upcoming__date {
  width: 44px;
  flex-shrink: 0;
  padding: 4px 0;
  border-radius: var(--radius-md);
  background: var(--accent-soft);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.upcoming__day {
  font: 500 18px/22px var(--font-mono);
}

.upcoming__month {
  font-size: 11px;
  color: var(--text-muted);
}

@media (max-width: 1100px) {
  .cal {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 768px) {
  .app-main__header {
    align-items: center;
    margin-bottom: var(--space-4);
  }

  .board {
    padding: var(--space-3);
  }

  .board__arrow,
  .board__today {
    height: var(--control-h-touch);
  }

  .board__arrow {
    width: var(--control-h-touch);
  }

  .weekdays {
    text-align: center;
  }

  .weekdays span {
    padding: 0;
  }

  /* Клетки-плитки: число по центру, мероприятия — точками. */
  .grid {
    gap: 3px;
  }

  .cell {
    min-height: 0;
    aspect-ratio: 1 / 1.05;
    padding: 4px 0;
    align-items: center;
    justify-content: flex-start;
    gap: 3px;
  }

  .cell__num {
    align-self: center;
    min-width: 28px;
    height: 28px;
    font-size: 13px;
  }

  .cell__events {
    display: none;
  }

  .cell__dots {
    display: flex;
    gap: 3px;
  }

  .cell__dot {
    width: 5px;
    height: 5px;
    border-radius: var(--radius-full);
    background: var(--accent);
  }

  .cell--muted .cell__dot {
    background: var(--text-faint);
  }

  .panel {
    padding: var(--space-3);
  }

  .day-head__add {
    width: var(--control-h-touch);
    height: var(--control-h-touch);
  }

  .agenda__item,
  .upcoming__item {
    min-height: 56px;
  }
}
</style>
