<script setup>
import { onMounted, ref } from 'vue'

import { fetchUsers } from '../api/users'
import { createTask } from '../api/tasks'
import { PRIORITY_META } from '../constants/taskMeta'

const props = defineProps({
  directions: { type: Array, default: () => [] },
})

const emit = defineEmits(['close', 'created'])

const title = ref('')
const description = ref('')
const directionId = ref(props.directions[0]?.id ?? null)
const priority = ref('medium')
const assigneeId = ref('')
const dueDate = ref('')

const users = ref([])
const error = ref('')
const isSubmitting = ref(false)

onMounted(async () => {
  try {
    users.value = await fetchUsers()
  } catch {
    users.value = []
  }
})

async function handleSubmit() {
  error.value = ''
  isSubmitting.value = true
  try {
    const task = await createTask({
      title: title.value,
      description: description.value,
      direction_id: directionId.value,
      priority: priority.value,
      assignee_id: assigneeId.value === '' ? null : Number(assigneeId.value),
      due_date: dueDate.value || null,
    })
    emit('created', task)
    emit('close')
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось создать задачу'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="modal-backdrop" @click.self="$emit('close')">
    <form v-swipe-close="() => $emit('close')" class="modal" @submit.prevent="handleSubmit">
      <h2>Выдать ТЗ</h2>

      <label for="task-title">Название</label>
      <input id="task-title" v-model="title" type="text" required maxlength="200" />

      <label for="task-description">Описание</label>
      <textarea id="task-description" v-model="description" rows="3" maxlength="4000" />

      <div class="modal__row">
        <div class="modal__field">
          <label for="task-direction">Направление</label>
          <select id="task-direction" v-model.number="directionId" required>
            <option v-for="direction in directions" :key="direction.id" :value="direction.id">
              {{ direction.name }}
            </option>
          </select>
        </div>

        <div class="modal__field">
          <label for="task-priority">Приоритет</label>
          <select id="task-priority" v-model="priority">
            <option v-for="(meta, value) in PRIORITY_META" :key="value" :value="value">
              {{ meta.label }}
            </option>
          </select>
        </div>
      </div>

      <div class="modal__row">
        <div class="modal__field">
          <label for="task-assignee">Исполнитель</label>
          <select id="task-assignee" v-model="assigneeId">
            <option value="">Не назначен</option>
            <option v-for="user in users" :key="user.id" :value="user.id">{{ user.full_name }}</option>
          </select>
        </div>

        <div class="modal__field">
          <label for="task-due-date">Срок</label>
          <input id="task-due-date" v-model="dueDate" type="date" />
        </div>
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <div class="modal__actions">
        <button type="button" class="modal__cancel" @click="$emit('close')">Отмена</button>
        <button type="submit" class="modal__submit" :disabled="isSubmitting">
          {{ isSubmitting ? 'Сохраняем…' : 'Выдать ТЗ' }}
        </button>
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
  max-width: 480px;
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.modal h2 {
  margin: 0 0 12px;
  font-size: 18px;
}

.modal label {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 10px;
}

.modal input,
.modal textarea,
.modal select {
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-top: 4px;
  font-family: inherit;
  resize: vertical;
}

.modal__row {
  display: flex;
  gap: 12px;
}

.modal__field {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.error {
  color: var(--danger);
  font-size: 13px;
  margin-top: 10px;
}

.modal__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}

.modal__cancel {
  padding: 9px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: transparent;
  color: var(--text);
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

.modal__submit:disabled {
  opacity: 0.6;
}
</style>
