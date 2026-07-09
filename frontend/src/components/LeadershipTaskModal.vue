<script setup>
import { computed, ref } from 'vue'

import { useLeadershipTasksStore } from '../stores/leadershipTasks'

const props = defineProps({
  task: { type: Object, default: null },
  // Ровно одно из двух задаёт строку: направление или должность тройки.
  directionId: { type: Number, default: null },
  position: { type: String, default: null },
  targetName: { type: String, default: '' },
  date: { type: String, required: true }, // YYYY-MM-DD
})

const emit = defineEmits(['close'])

const store = useLeadershipTasksStore()
const isEditMode = computed(() => !!props.task)

const title = ref(props.task?.title ?? '')
const done = ref(props.task?.status === 'done')

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
  isSubmitting.value = true
  try {
    const status = done.value ? 'done' : 'todo'
    if (isEditMode.value) {
      await store.edit(props.task.id, { title: title.value, status })
    } else {
      const payload = { title: title.value, date: props.date, status }
      if (props.position) payload.position = props.position
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
    <form class="modal" @submit.prevent="handleSubmit">
      <h2>{{ isEditMode ? 'Запись руководства' : 'Новая запись' }}</h2>
      <p class="modal__meta">{{ targetName }} · {{ dateLabel }}</p>

      <label for="lt-title">Задача</label>
      <textarea id="lt-title" v-model="title" rows="3" required maxlength="200" autofocus />

      <label class="modal__check">
        <input v-model="done" type="checkbox" />
        Выполнено
      </label>

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
