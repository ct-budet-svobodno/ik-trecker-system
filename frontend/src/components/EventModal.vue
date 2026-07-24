<script setup>
import { computed, ref } from 'vue'

import { useEventsStore } from '../stores/events'
import { toDatetimeLocalValue } from '../utils/formatDateTime'

const props = defineProps({
  event: { type: Object, default: null },
  defaultStartAt: { type: String, default: '' },
})

const emit = defineEmits(['close'])

const eventsStore = useEventsStore()
const isEditMode = computed(() => !!props.event)

const title = ref(props.event?.title ?? '')
const description = ref(props.event?.description ?? '')
const location = ref(props.event?.location ?? '')
const startAt = ref(
  props.event ? toDatetimeLocalValue(props.event.start_at) : props.defaultStartAt,
)
const endAt = ref(props.event ? toDatetimeLocalValue(props.event.end_at) : '')

const error = ref('')
const isSubmitting = ref(false)

async function handleSubmit() {
  error.value = ''
  isSubmitting.value = true
  try {
    const payload = {
      title: title.value,
      description: description.value,
      location: location.value || null,
      start_at: new Date(startAt.value).toISOString(),
      end_at: endAt.value ? new Date(endAt.value).toISOString() : null,
    }
    if (isEditMode.value) {
      await eventsStore.editEvent(props.event.id, payload)
    } else {
      await eventsStore.addEvent(payload)
    }
    emit('close')
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось сохранить мероприятие'
  } finally {
    isSubmitting.value = false
  }
}

async function handleDelete() {
  if (!window.confirm('Удалить мероприятие?')) return
  isSubmitting.value = true
  try {
    await eventsStore.removeEvent(props.event.id)
    emit('close')
  } catch {
    error.value = 'Не удалось удалить мероприятие'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="modal-backdrop" @click.self="$emit('close')">
    <form v-swipe-close="() => $emit('close')" class="modal" @submit.prevent="handleSubmit">
      <h2>{{ isEditMode ? 'Мероприятие' : 'Назначить мероприятие' }}</h2>

      <label for="event-title">Название</label>
      <input id="event-title" v-model="title" type="text" required maxlength="200" />

      <label for="event-description">Описание</label>
      <textarea id="event-description" v-model="description" rows="3" maxlength="4000" />

      <label for="event-location">Место</label>
      <input id="event-location" v-model="location" type="text" maxlength="200" placeholder="Необязательно" />

      <div class="modal__row">
        <div class="modal__field">
          <label for="event-start">Начало</label>
          <input id="event-start" v-model="startAt" type="datetime-local" required />
        </div>
        <div class="modal__field">
          <label for="event-end">Конец</label>
          <input id="event-end" v-model="endAt" type="datetime-local" />
        </div>
      </div>

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
            {{ isSubmitting ? 'Сохраняем…' : isEditMode ? 'Сохранить' : 'Назначить' }}
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
.modal textarea {
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
