<script setup>
import { computed, onMounted, ref } from 'vue'

import AppSidebar from '../components/AppSidebar.vue'
import LeadershipTaskModal from '../components/LeadershipTaskModal.vue'
import { LEADERSHIP_POSITION_LABELS } from '../constants/roleLabels'
import { useAuthStore } from '../stores/auth'
import { useLeadershipTasksStore } from '../stores/leadershipTasks'
import { useTasksStore } from '../stores/tasks'
import { dayKey } from '../utils/dateKey'

const authStore = useAuthStore()
const tasksStore = useTasksStore()
const store = useLeadershipTasksStore()

onMounted(async () => {
  await tasksStore.loadAll()
  await store.load()
})

const weekDays = computed(() => store.weekDays)

// id направлений, где текущий пользователь — руководитель.
const myDirectionIds = computed(() => {
  const me = authStore.user?.id
  const ids = new Set()
  for (const dir of tasksStore.directions) {
    if ((dir.heads ?? []).some((h) => h.id === me)) ids.add(dir.id)
  }
  return ids
})

// Строки сетки: направления + 3 должности тройки.
const rows = computed(() => {
  const dirRows = tasksStore.directions.map((d) => ({
    key: `d:${d.id}`,
    kind: 'direction',
    name: d.short_code,
    color: d.color,
    directionId: d.id,
    position: null,
  }))
  const posRows = Object.entries(LEADERSHIP_POSITION_LABELS).map(([pos, label]) => ({
    key: `p:${pos}`,
    kind: 'position',
    name: label,
    color: null,
    directionId: null,
    position: pos,
  }))
  return [...dirRows, ...posRows]
})

function canEditRow(row) {
  if (row.kind === 'position') return authStore.isLeadership
  return authStore.isLeadership || myDirectionIds.value.has(row.directionId)
}

// Быстрый доступ: записи по ключу строки + дня.
const itemsByCell = computed(() => {
  const map = new Map()
  for (const item of store.items) {
    const rowKey = item.position ? `p:${item.position}` : `d:${item.direction_id}`
    const key = `${rowKey}|${item.date}`
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(item)
  }
  return map
})

function cellItems(row, day) {
  return itemsByCell.value.get(`${row.key}|${dayKey(day)}`) ?? []
}

const todayKey = dayKey(new Date())
const dayLabelFmt = new Intl.DateTimeFormat('ru-RU', { weekday: 'short', day: 'numeric', month: 'short' })
const weekRangeLabel = computed(() => {
  const days = weekDays.value
  const fmt = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long' })
  return `${fmt.format(days[0])} — ${fmt.format(days[6])}`
})

// --- Модалка ---
const modal = ref(null)

function openCreate(row, day) {
  if (!canEditRow(row)) return
  modal.value = {
    task: null,
    directionId: row.directionId,
    position: row.position,
    targetName: row.name,
    date: dayKey(day),
  }
}

function openEdit(row, item) {
  if (!canEditRow(row)) return
  modal.value = {
    task: item,
    directionId: row.directionId,
    position: row.position,
    targetName: row.name,
    date: item.date,
  }
}

function closeModal() {
  modal.value = null
}
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="app-main__header">
        <div>
          <p class="breadcrumb">ИК · ТРЕКЕР / ТАЙМЛАЙН РУКОВОДСТВА</p>
          <h1>ТАЙМЛАЙН РУКОВОДСТВА</h1>
          <p class="subtitle">
            Задачи по направлениям и дням. Видно только руководству и руководителям направлений.
          </p>
        </div>
        <div class="weeknav">
          <button class="weeknav__btn" title="Прошлая неделя" @click="store.shiftWeek(-1)">‹</button>
          <button class="weeknav__today" @click="store.goToCurrentWeek()">Сегодня</button>
          <button class="weeknav__btn" title="Следующая неделя" @click="store.shiftWeek(1)">›</button>
          <span class="weeknav__range">{{ weekRangeLabel }}</span>
        </div>
      </div>

      <p v-if="store.loadError" class="error">{{ store.loadError }}</p>

      <div class="grid-wrap">
        <div class="grid">
          <!-- Шапка -->
          <div class="corner" />
          <div
            v-for="day in weekDays"
            :key="`h-${day.toISOString()}`"
            class="colhead"
            :class="{ 'colhead--today': dayKey(day) === todayKey }"
          >
            {{ dayLabelFmt.format(day) }}
          </div>

          <!-- Строки: направления + должности тройки -->
          <template v-for="row in rows" :key="row.key">
            <div
              class="rowhead"
              :class="row.kind === 'position' ? 'rowhead--position' : `rowhead--${row.color}`"
            >
              <span class="rowhead__name">{{ row.name }}</span>
            </div>
            <div
              v-for="day in weekDays"
              :key="`${row.key}-${day.toISOString()}`"
              class="cell"
              :class="{ 'cell--editable': canEditRow(row), 'cell--today': dayKey(day) === todayKey }"
              @click="openCreate(row, day)"
            >
              <button
                v-for="item in cellItems(row, day)"
                :key="item.id"
                class="note"
                :class="{ 'note--done': item.status === 'done' }"
                @click.stop="openEdit(row, item)"
              >
                <span class="note__title">{{ item.title }}</span>
                <span v-if="item.status === 'done'" class="note__done">выполнено</span>
              </button>
              <span v-if="canEditRow(row)" class="cell__add">+</span>
            </div>
          </template>
        </div>
      </div>
    </main>

    <LeadershipTaskModal
      v-if="modal"
      :task="modal.task"
      :direction-id="modal.directionId"
      :position="modal.position"
      :target-name="modal.targetName"
      :date="modal.date"
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
  gap: 24px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.breadcrumb {
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--text-faint);
  margin: 0 0 6px;
}

.app-main__header h1 {
  margin: 0;
  font-size: 22px;
  letter-spacing: 0.02em;
}

.subtitle {
  margin: 6px 0 0;
  color: var(--text-muted);
  font-size: 13px;
  max-width: 520px;
}

.weeknav {
  display: flex;
  align-items: center;
  gap: 8px;
}

.weeknav__btn,
.weeknav__today {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 14px;
}

.weeknav__btn:hover,
.weeknav__today:hover {
  background: var(--surface-hover);
}

.weeknav__range {
  font-size: 12px;
  color: var(--text-muted);
  margin-left: 4px;
}

.grid-wrap {
  overflow-x: auto;
}

.grid {
  display: grid;
  grid-template-columns: 130px repeat(7, minmax(150px, 1fr));
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  min-width: 900px;
}

.corner {
  background: var(--surface);
  position: sticky;
  left: 0;
  z-index: 3;
}

.colhead {
  background: var(--surface);
  padding: 10px 12px;
  font-size: 12px;
  color: var(--text-muted);
  text-transform: capitalize;
}

.colhead--today {
  color: var(--accent);
  font-weight: 600;
}

.rowhead {
  background: var(--surface);
  padding: 12px;
  display: flex;
  align-items: center;
  border-left: 3px solid var(--border-strong);
  /* Названия строк не уезжают при горизонтальном скролле сетки. */
  position: sticky;
  left: 0;
  z-index: 2;
}

.rowhead__name {
  font-size: 13px;
  font-weight: 600;
}

/* Цвета направлений (повторяют --dir-* из style.css). */
.rowhead--violet { border-left-color: var(--dir-ct); }
.rowhead--pink { border-left-color: var(--dir-design); }
.rowhead--cyan { border-left-color: var(--dir-nvk); }
.rowhead--green { border-left-color: var(--dir-photo); }
.rowhead--orange { border-left-color: var(--dir-smi); }
.rowhead--blue { border-left-color: var(--dir-prod-a); }

/* Строки руководства (тройка + бренд-менеджер) — красный текст на чёрном фоне. */
.rowhead--position {
  border-left-color: #ff3b3b;
  background: #000;
}
.rowhead--position .rowhead__name {
  color: #ff3b3b;
  font-weight: 700;
}

.cell {
  background: var(--bg);
  min-height: 64px;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  position: relative;
}

.cell--today {
  background: color-mix(in srgb, var(--accent) 6%, var(--bg));
}

.cell--editable {
  cursor: pointer;
}

.cell__add {
  opacity: 0;
  align-self: flex-start;
  color: var(--text-faint);
  font-size: 16px;
  line-height: 1;
  transition: opacity 0.12s ease;
}

.cell--editable:hover .cell__add {
  opacity: 1;
}

.note {
  text-align: left;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: var(--surface-raised);
  color: var(--text);
  padding: 6px 8px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  font: inherit;
}

.note:hover {
  border-color: var(--border-strong);
}

.note__title {
  font-size: 12.5px;
  line-height: 1.35;
}

.note--done .note__title {
  color: var(--text-muted);
  text-decoration: line-through;
}

.note__done {
  font-size: 10px;
  font-style: italic;
  color: var(--status-done);
}

.error {
  color: var(--danger);
  font-size: 13px;
  margin: 0 0 12px;
}

@media (max-width: 768px) {
  .grid {
    grid-template-columns: 96px repeat(7, minmax(132px, 1fr));
    min-width: 0;
  }

  .rowhead {
    padding: 10px 8px;
  }

  .rowhead__name {
    font-size: 12px;
  }

  .grid-wrap {
    margin: 0 -14px;
    padding: 0 14px;
  }

  .app-main__header h1 {
    font-size: 19px;
  }
}
</style>
