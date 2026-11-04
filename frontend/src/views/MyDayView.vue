<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import BaseIcon from '../components/BaseIcon.vue'
import { useMyDayStore } from '../stores/myDay'

const store = useMyDayStore()

onMounted(() => store.goToToday())

const newTitle = ref('')
const isAdding = ref(false)
const actionError = ref('')

const dayFmt = new Intl.DateTimeFormat('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })
const dayLabel = computed(() => dayFmt.format(store.day))

// Сначала то, что ещё предстоит, выполненное — внизу.
const pending = computed(() => store.items.filter((item) => !item.done))
const done = computed(() => store.items.filter((item) => item.done))
const progress = computed(() =>
  store.items.length ? Math.round((store.doneCount / store.items.length) * 100) : 0,
)

function pluralItems(n) {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return `${n} пункт`
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${n} пункта`
  return `${n} пунктов`
}

async function run(action, fallback) {
  actionError.value = ''
  try {
    await action()
  } catch (err) {
    actionError.value = err.response?.data?.detail ?? fallback
  }
}

async function handleAdd() {
  const title = newTitle.value.trim()
  if (!title || isAdding.value) return
  isAdding.value = true
  await run(async () => {
    await store.add(title)
    newTitle.value = ''
  }, 'Не удалось добавить пункт')
  isAdding.value = false
}

// --- Правка названия прямо в строке ---
const editingId = ref(null)
const editingTitle = ref('')
const editInput = ref(null)

async function startEdit(item) {
  editingId.value = item.id
  editingTitle.value = item.title
  await nextTick()
  // ref внутри v-for — массив из одного элемента.
  const input = Array.isArray(editInput.value) ? editInput.value[0] : editInput.value
  input?.focus()
}

function cancelEdit() {
  editingId.value = null
}

async function saveEdit(item) {
  if (editingId.value !== item.id) return
  const title = editingTitle.value.trim()
  editingId.value = null
  if (!title || title === item.title) return
  await run(() => store.edit(item.id, { title }), 'Не удалось сохранить название')
}

const toggle = (item) => run(() => store.toggle(item), 'Не удалось отметить пункт')
const moveToNextDay = (item) => run(() => store.moveToNextDay(item), 'Не удалось перенести пункт')
const remove = (item) => run(() => store.remove(item.id), 'Не удалось удалить пункт')
const carryOver = () => run(() => store.carryOver(), 'Не удалось перенести пункты')
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="day">
        <div class="page-head">
          <div class="page-head__titles">
            <p class="breadcrumb">ИК · Трекер / Мой день</p>
            <h1>Мой день</h1>
            <p class="subtitle">Личный список дел. Его видите только вы.</p>
          </div>
          <div class="daynav">
            <button class="daynav__btn" title="Предыдущий день" aria-label="Предыдущий день" @click="store.shiftDay(-1)">
              <BaseIcon name="chevron-left" :size="18" />
            </button>
            <button class="daynav__today" :disabled="store.isToday" @click="store.goToToday()">
              Сегодня
            </button>
            <button class="daynav__btn" title="Следующий день" aria-label="Следующий день" @click="store.shiftDay(1)">
              <BaseIcon name="chevron-right" :size="18" />
            </button>
          </div>
        </div>

        <div class="summary">
          <span class="summary__date">{{ dayLabel }}</span>
          <span v-if="store.items.length" class="summary__count">
            {{ store.doneCount }} из {{ store.items.length }}
          </span>
        </div>
        <div
          v-if="store.items.length"
          class="progress"
          role="progressbar"
          aria-label="Выполнено за день"
          :aria-valuenow="progress"
          aria-valuemin="0"
          aria-valuemax="100"
        >
          <span class="progress__bar" :style="{ width: `${progress}%` }" />
        </div>

        <form class="add" @submit.prevent="handleAdd">
          <input
            id="my-day-new"
            v-model="newTitle"
            class="add__input"
            type="text"
            maxlength="200"
            placeholder="Что нужно сделать?"
            autocomplete="off"
            enterkeyhint="done"
          />
          <button class="create-btn add__btn" type="submit" :disabled="!newTitle.trim() || isAdding">
            <BaseIcon name="plus" :size="16" />
            <span class="add__btn-text">Добавить</span>
          </button>
        </form>

        <p v-if="actionError" class="error" role="alert">{{ actionError }}</p>

        <div v-if="store.isToday && store.overdue.length" class="overdue">
          <span class="overdue__text">
            С прошлых дней осталось: {{ pluralItems(store.overdue.length) }}
          </span>
          <button class="overdue__btn" @click="carryOver">Перенести на сегодня</button>
        </div>

        <AppLoader v-if="store.isLoading && !store.items.length" />
        <p v-else-if="store.loadError" class="state state--error">{{ store.loadError }}</p>
        <p v-else-if="!store.items.length" class="state">
          На этот день ничего не запланировано. Добавьте первый пункт в поле выше.
        </p>

        <template v-else>
          <ul class="list">
            <li
              v-for="item in [...pending, ...done]"
              :key="item.id"
              class="todo"
              :class="{ 'todo--done': item.done }"
            >
              <button
                class="todo__check"
                role="checkbox"
                :aria-checked="item.done"
                :aria-label="item.done ? 'Вернуть в работу' : 'Отметить выполненным'"
                @click="toggle(item)"
              >
                <span class="todo__box">
                  <BaseIcon v-if="item.done" name="check" :size="14" />
                </span>
              </button>

              <input
                v-if="editingId === item.id"
                ref="editInput"
                v-model="editingTitle"
                class="todo__edit"
                type="text"
                maxlength="200"
                aria-label="Название пункта"
                @keydown.enter.prevent="saveEdit(item)"
                @keydown.esc="cancelEdit"
                @blur="saveEdit(item)"
              />
              <button v-else class="todo__title" title="Изменить название" @click="startEdit(item)">
                {{ item.title }}
              </button>

              <div class="todo__actions">
                <button
                  v-if="!item.done"
                  class="todo__action"
                  title="Перенести на следующий день"
                  aria-label="Перенести на следующий день"
                  @click="moveToNextDay(item)"
                >
                  <BaseIcon name="arrow-right" :size="16" />
                </button>
                <button
                  class="todo__action todo__action--danger"
                  title="Удалить"
                  aria-label="Удалить"
                  @click="remove(item)"
                >
                  <BaseIcon name="trash" :size="16" />
                </button>
              </div>
            </li>
          </ul>
        </template>
      </div>
    </main>
  </div>
</template>

<style scoped>
/* Список читается как колонка текста — не растягиваем на весь экран. */
.day {
  max-width: 720px;
}

.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-6);
  flex-wrap: wrap;
  margin-bottom: var(--space-6);
}

.page-head__titles {
  min-width: 0;
}

.daynav {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.daynav__btn,
.daynav__today {
  display: flex;
  align-items: center;
  justify-content: center;
  height: var(--control-h);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--text);
  font-size: 14px;
}

.daynav__btn {
  width: var(--control-h);
}

.daynav__today {
  padding: 0 14px;
}

.daynav__btn:hover,
.daynav__today:hover:not(:disabled) {
  background: var(--surface-hover);
  border-color: var(--border-strong);
}

.daynav__today:disabled {
  color: var(--text-muted);
  cursor: default;
}

.summary {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.summary__date {
  font-size: 15px;
  font-weight: 600;
  line-height: 20px;
}

.summary__date::first-letter {
  text-transform: uppercase;
}

.summary__count {
  font-family: var(--font-mono);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  color: var(--text-muted);
  white-space: nowrap;
}

.progress {
  height: 4px;
  border-radius: var(--radius-full);
  background: var(--surface-raised);
  overflow: hidden;
  margin-bottom: var(--space-5);
}

.progress__bar {
  display: block;
  height: 100%;
  border-radius: var(--radius-full);
  background: var(--status-done);
  transition: width 0.25s ease;
}

.add {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.summary + .add {
  margin-top: var(--space-4);
}

.add__input {
  flex: 1;
  min-width: 0;
  height: var(--control-h);
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 14px;
}

.add__input::placeholder {
  color: var(--text-faint);
}

.add__input:focus {
  border-color: var(--border-strong);
  outline: none;
}

.add__btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.error {
  color: var(--danger);
  font-size: 13px;
  margin: 0 0 var(--space-3);
}

.overdue {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
  padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-4);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.overdue__text {
  font-size: 13px;
  color: var(--text-muted);
}

.overdue__btn {
  height: 28px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text);
  font-size: 12px;
  white-space: nowrap;
}

.overdue__btn:hover {
  background: var(--surface-hover);
  border-color: var(--border-strong);
}

.state {
  margin: 0;
  padding: var(--space-10) var(--space-4);
  text-align: center;
  color: var(--text-muted);
  border: 1px dashed var(--border);
  border-radius: var(--radius-lg);
}

.state--error {
  color: var(--danger);
}

.list {
  list-style: none;
  margin: 0;
  padding: 0;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.todo {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  min-height: 48px;
  padding: 0 var(--space-2);
}

.todo + .todo {
  border-top: 1px solid var(--border);
}

.todo__check {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 44px;
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: var(--on-success);
}

.todo__box {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: 1.5px solid var(--border-strong);
  border-radius: var(--radius-full);
  transition: background 0.15s ease, border-color 0.15s ease;
}

.todo__check:hover .todo__box {
  border-color: var(--status-done);
}

.todo--done .todo__box {
  background: var(--status-done);
  border-color: var(--status-done);
}

.todo__title,
.todo__edit {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  line-height: 21px;
}

.todo__title {
  padding: 12px 4px;
  border: none;
  background: transparent;
  color: var(--text);
  text-align: left;
  overflow-wrap: anywhere;
  cursor: text;
}

.todo--done .todo__title {
  color: var(--text-muted);
  text-decoration: line-through;
}

.todo__edit {
  height: var(--control-h);
  padding: 0 8px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
}

.todo__actions {
  display: flex;
  flex-shrink: 0;
}

.todo__action {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--control-h);
  height: var(--control-h);
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-muted);
}

.todo__action:hover {
  background: var(--surface-raised);
  color: var(--text);
}

.todo__action--danger:hover {
  color: var(--danger);
}

@media (max-width: 768px) {
  .page-head {
    margin-bottom: var(--space-4);
  }

  /* Навигация по дням — во всю ширину, «Сегодня» растягивается между стрелками. */
  .daynav {
    width: 100%;
  }

  .daynav__btn,
  .daynav__today {
    height: var(--control-h-touch);
  }

  .daynav__btn {
    width: var(--control-h-touch);
  }

  .daynav__today {
    flex: 1;
  }

  /* Поле ввода держится над таб-баром — добавлять пункт можно одной рукой. */
  .add {
    position: fixed;
    left: 10px;
    right: 10px;
    bottom: calc(84px + env(safe-area-inset-bottom));
    z-index: 80;
    margin: 0;
    padding: var(--space-2);
    background: color-mix(in srgb, var(--surface) 88%, transparent);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
  }

  .add__input,
  .add__btn {
    height: var(--control-h-touch);
  }

  .add__btn {
    width: var(--control-h-touch);
    padding: 0;
  }

  .add__btn-text {
    display: none;
  }

  /* Место под закреплённое поле ввода, чтобы оно не закрывало последние пункты. */
  .day {
    padding-bottom: 72px;
  }

  .todo {
    min-height: 52px;
  }

  .todo__check {
    width: 44px;
  }

  .todo__action {
    width: var(--control-h-touch);
    height: var(--control-h-touch);
  }
}
</style>
