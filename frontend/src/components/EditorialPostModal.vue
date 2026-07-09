<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useEditorialStore } from '../stores/editorial'

const props = defineProps({
  // Режим создания: передаётся дата ячейки (YYYY-MM-DD).
  date: { type: String, default: '' },
  // Режим редактирования: передаётся сам пост.
  post: { type: Object, default: null },
})

const emit = defineEmits(['close'])

const router = useRouter()
const store = useEditorialStore()
const isEditMode = computed(() => !!props.post)

const form = ref({
  date: props.post?.date ?? props.date,
  title: props.post?.title ?? '',
  format: props.post?.format ?? '',
  brief: props.post?.brief ?? '',
  reference: props.post?.reference ?? '',
})

const error = ref('')
const isSubmitting = ref(false)

async function handleSubmit() {
  error.value = ''
  isSubmitting.value = true
  try {
    const payload = {
      date: form.value.date,
      title: form.value.title.trim(),
      format: form.value.format.trim() || null,
      brief: form.value.brief,
      reference: form.value.reference.trim() || null,
    }
    if (isEditMode.value) {
      await store.update(props.post.id, payload)
      emit('close')
    } else {
      const created = await store.create(payload)
      emit('close')
      router.push({ name: 'editorial-post', params: { id: created.id } })
    }
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось сохранить пост'
  } finally {
    isSubmitting.value = false
  }
}

async function handleDelete() {
  if (!window.confirm('Удалить пост целиком?')) return
  isSubmitting.value = true
  try {
    await store.remove(props.post.id)
    emit('close')
    router.push({ name: 'editorial' })
  } catch {
    error.value = 'Не удалось удалить пост'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="modal-backdrop" @click.self="$emit('close')">
    <form class="modal" @submit.prevent="handleSubmit">
      <h2>{{ isEditMode ? 'Редактировать пост' : 'Новый пост' }}</h2>

      <div class="modal__row">
        <div class="modal__field">
          <label>Дата выхода</label>
          <input v-model="form.date" type="date" required />
        </div>
        <div class="modal__field">
          <label>Формат</label>
          <input v-model="form.format" placeholder="карусель, reels, СЗ…" maxlength="100" />
        </div>
      </div>

      <label>Название</label>
      <input v-model="form.title" required maxlength="200" placeholder="О чём пост" autofocus />

      <label>Суть / бриф</label>
      <textarea v-model="form.brief" rows="4" placeholder="Что за пост, ключевые смыслы" />

      <label>Референс (ссылка)</label>
      <input v-model="form.reference" maxlength="500" placeholder="https://…" />

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
            {{ isSubmitting ? 'Сохраняем…' : isEditMode ? 'Сохранить' : 'Создать' }}
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
  margin: 0 0 8px;
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
  background: var(--surface);
  color: var(--text);
  font-family: inherit;
  font-size: 14px;
}

.modal textarea {
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
