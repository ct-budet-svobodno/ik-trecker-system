<script setup>
import { computed, ref } from 'vue'

import { LEADERSHIP_BLOCK_COLORS } from '../constants/leadershipColors'
import { LEADERSHIP_POSITION_LABELS } from '../constants/roleLabels'
import { useLeadershipTasksStore } from '../stores/leadershipTasks'

const props = defineProps({
  task: { type: Object, default: null },
  // Ровно одно из трёх задаёт строку: направление, должность четвёрки или Редакция.
  directionId: { type: Number, default: null },
  position: { type: String, default: null },
  isEditorial: { type: Boolean, default: false },
  targetName: { type: String, default: '' },
  date: { type: String, required: true }, // YYYY-MM-DD
})

const emit = defineEmits(['close'])

const store = useLeadershipTasksStore()
const isEditMode = computed(() => !!props.task)
const blockColors = LEADERSHIP_BLOCK_COLORS
const positionEntries = Object.entries(LEADERSHIP_POSITION_LABELS)

// Запись четвёрки (по должности) — для неё доступны галочки должностей и цвет.
const isPositionTask = computed(() => !!(props.position || props.task?.position))
const isCreatePosition = computed(() => !isEditMode.value && !!props.position)

const title = ref(props.task?.title ?? '')
const done = ref(props.task?.status === 'done')
const color = ref(props.task?.color ?? null)
// Кому из четвёрки назначить задачу (только при создании). По умолчанию —
// та должность, по клетке которой открыли модалку.
const selectedPositions = ref(props.position ? [props.position] : [])

const error = ref('')
const isSubmitting = ref(false)

const dateLabel = computed(() => {
  const [y, m, d] = props.date.split('-').map(Number)
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long' }).format(
    new Date(y, m - 1, d),
  )
})

async function handleSubmit() {
  error.value = ''
  const status = done.value ? 'done' : 'todo'
  isSubmitting.value = true
  try {
    if (isEditMode.value) {
      const patch = { title: title.value, status }
      // Для записей четвёрки цвет передаём всегда — null очищает его.
      if (isPositionTask.value) patch.color = color.value
      await store.edit(props.task.id, patch)
    } else if (props.position) {
      if (!selectedPositions.value.length) {
        error.value = 'Отметьте хотя бы одну должность'
        return
      }
      // Одна задача на каждую отмеченную должность — своя карточка в её строке.
      for (const pos of selectedPositions.value) {
        const payload = { title: title.value, date: props.date, status, position: pos }
        if (color.value) payload.color = color.value
        await store.add(payload)
      }
    } else {
      const payload = { title: title.value, date: props.date, status }
      if (props.isEditorial) payload.is_editorial = true
      else payload.direction_id = props.directionId
      await store.add(payload)
    }
    emit('close')
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось сохранить запись'
  } finally {
    isSubmitting.value = false
  }
}

async function handleDelete() {
  if (!window.confirm('Удалить запись?')) return
  isSubmitting.value = true
  try {
    await store.remove(props.task.id)
    emit('close')
  } catch {
    error.value = 'Не удалось удалить запись'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="modal-backdrop" @click.self="$emit('close')">
    <form v-swipe-close="() => $emit('close')" class="modal" @submit.prevent="handleSubmit">
      <h2>{{ isEditMode ? 'Запись руководства' : 'Новая запись' }}</h2>
      <p class="modal__meta">{{ targetName }} · {{ dateLabel }}</p>

      <label for="lt-title">Задача</label>
      <textarea id="lt-title" v-model="title" rows="3" required maxlength="200" autofocus />

      <template v-if="isCreatePosition">
        <label>Кому назначить</label>
        <div class="pos-picker">
          <label v-for="[key, label] in positionEntries" :key="key" class="pos-opt">
            <input v-model="selectedPositions" type="checkbox" :value="key" />
            {{ label }}
          </label>
        </div>
      </template>

      <label class="modal__check">
        <input v-model="done" type="checkbox" />
        Выполнено
      </label>

      <template v-if="isPositionTask">
        <label>Цвет</label>
        <div class="colors">
          <button
            type="button"
            class="colors__dot colors__dot--none"
            :class="{ 'colors__dot--active': !color }"
            title="Без цвета"
            @click="color = null"
          />
          <button
            v-for="c in blockColors"
            :key="c.value"
            type="button"
            class="colors__dot"
            :class="{ 'colors__dot--active': color === c.value }"
            :style="{ background: c.value }"
            :title="c.label"
            @click="color = c.value"
          />
        </div>
      </template>

      <p v-if="error" class="error">{{ error }}</p>

      <div class="modal__actions">
        <button
          v-if="isEditMode"
          type="button"
          class="modal__delete"
          :disabled="isSubmitting"
          @click="handleDelete"
        >
          Удалить
        </button>
        <div class="modal__actions-right">
          <button type="button" class="modal__cancel" @click="$emit('close')">Отмена</button>
          <button type="submit" class="modal__submit" :disabled="isSubmitting">
            {{ isSubmitting ? 'Сохраняем…' : isEditMode ? 'Сохранить' : 'Добавить' }}
          </button>
        </div>
      </div>
    </form>
  </div>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  z-index: 100;
}

.modal {
  width: 100%;
  max-width: 460px;
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.modal h2 {
  margin: 0;
  font-size: 18px;
}

.modal__meta {
  margin: 2px 0 8px;
  font-size: 13px;
  color: var(--text-muted);
}

.modal label {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 10px;
}

.modal textarea {
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-top: 4px;
  font-family: inherit;
  resize: vertical;
}

.pos-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin-top: 6px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
}

.pos-opt {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text);
  margin: 0;
}

.pos-opt input {
  width: 15px;
  height: 15px;
  margin: 0;
}

.modal__check {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text);
  margin-top: 14px;
}

.modal__check input {
  width: 16px;
  height: 16px;
}

.colors {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
}

.colors__dot {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  padding: 0;
  transition: transform 0.1s ease;
}

.colors__dot:hover {
  transform: scale(1.1);
}

.colors__dot--active {
  border-color: var(--text);
  box-shadow: 0 0 0 2px var(--surface-raised);
}

.colors__dot--none {
  background: var(--surface);
  border: 1px dashed var(--border-strong);
  position: relative;
}

.colors__dot--none::after {
  content: '';
  position: absolute;
  left: 3px;
  right: 3px;
  top: 50%;
  height: 2px;
  background: var(--danger);
  transform: rotate(-45deg);
}

.colors__dot--none.colors__dot--active {
  border-color: var(--text);
  border-style: solid;
}

.error {
  color: var(--danger);
  font-size: 13px;
  margin-top: 10px;
}

.modal__actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-top: 18px;
}

.modal__actions-right {
  display: flex;
  gap: 10px;
}

.modal__cancel {
  padding: 9px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: transparent;
  color: var(--text);
}

.modal__delete {
  padding: 9px 14px;
  border: 1px solid var(--danger);
  border-radius: 8px;
  background: transparent;
  color: var(--danger);
}

.modal__submit {
  padding: 9px 14px;
  border: none;
  border-radius: 8px;
  background: var(--success);
  color: #0c1410;
  font-weight: 600;
}

.modal__submit:hover:not(:disabled) {
  background: var(--success-hover);
}

.modal__submit:disabled,
.modal__delete:disabled {
  opacity: 0.6;
}
</style>
