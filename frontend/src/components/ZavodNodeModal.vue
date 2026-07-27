<script setup>
import { ref } from 'vue'

// Палитра общая с блоками таймлайна — на бэкенде это один ALLOWED_COLORS.
import { LEADERSHIP_BLOCK_COLORS } from '../constants/leadershipColors'
import { ZAVOD_STATUS_META, ZAVOD_STATUS_ORDER } from '../constants/zavodMeta'
import { useZavodStore } from '../stores/zavod'

const props = defineProps({
  node: { type: Object, required: true },
  people: { type: Array, default: () => [] },
})

const emit = defineEmits(['close'])

const store = useZavodStore()
const colors = LEADERSHIP_BLOCK_COLORS
const statuses = ZAVOD_STATUS_ORDER.map((key) => ({ key, ...ZAVOD_STATUS_META[key] }))

const title = ref(props.node.title)
const content = ref(props.node.content ?? '')
const status = ref(props.node.status)
const color = ref(props.node.color ?? null)
const assigneeIds = ref(props.node.assignees.map((a) => a.id))

const error = ref('')
const isSubmitting = ref(false)

async function handleSubmit() {
  error.value = ''
  isSubmitting.value = true
  try {
    await store.editNode(props.node.id, {
      title: title.value.trim(),
      content: content.value.trim() || null,
      status: status.value,
      color: color.value,
      assignee_ids: assigneeIds.value,
    })
    emit('close')
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось сохранить карточку'
  } finally {
    isSubmitting.value = false
  }
}

async function handleDelete() {
  if (!window.confirm('Удалить карточку вместе с её связями?')) return
  isSubmitting.value = true
  try {
    await store.removeNode(props.node.id)
    emit('close')
  } catch {
    error.value = 'Не удалось удалить карточку'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="modal-backdrop" @click.self="$emit('close')">
    <form v-swipe-close="() => $emit('close')" class="modal" @submit.prevent="handleSubmit">
      <h2>Карточка</h2>

      <label for="zn-title">Заголовок</label>
      <input id="zn-title" v-model="title" required maxlength="200" />

      <label for="zn-content">Описание</label>
      <textarea id="zn-content" v-model="content" rows="4" placeholder="Необязательно" />

      <label>Статус</label>
      <div class="statuses">
        <button
          v-for="s in statuses"
          :key="s.key"
          type="button"
          class="statuses__item"
          :class="[`statuses__item--${s.tone}`, { 'statuses__item--active': status === s.key }]"
          @click="status = s.key"
        >
          {{ s.label }}
        </button>
      </div>

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
          v-for="c in colors"
          :key="c.value"
          type="button"
          class="colors__dot"
          :class="{ 'colors__dot--active': color === c.value }"
          :style="{ background: c.value }"
          :title="c.label"
          @click="color = c.value"
        />
      </div>

      <label>Ответственные</label>
      <div class="people">
        <label v-for="person in people" :key="person.id" class="people__opt">
          <input v-model="assigneeIds" type="checkbox" :value="person.id" />
          {{ person.full_name }}
        </label>
        <p v-if="!people.length" class="people__empty">Список людей не загрузился</p>
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <div class="modal__actions">
        <button type="button" class="modal__delete" :disabled="isSubmitting" @click="handleDelete">
          Удалить
        </button>
        <div class="modal__actions-right">
          <button type="button" class="modal__cancel" @click="$emit('close')">Отмена</button>
          <button type="submit" class="modal__submit" :disabled="isSubmitting">
            {{ isSubmitting ? 'Сохраняем…' : 'Сохранить' }}
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
  margin: 0 0 8px;
  font-size: 18px;
}

.modal label {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 10px;
}

.modal input[type='text'],
.modal input:not([type]),
.modal textarea {
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-top: 4px;
  font-family: inherit;
  color: var(--text);
}

.modal textarea {
  resize: vertical;
}

.statuses {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
}

.statuses__item {
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
}

.statuses__item--active.statuses__item--todo {
  border-color: var(--status-todo);
  color: var(--status-todo);
  background: color-mix(in srgb, var(--status-todo) 16%, transparent);
}

.statuses__item--active.statuses__item--progress {
  border-color: var(--status-progress);
  color: var(--status-progress);
  background: color-mix(in srgb, var(--status-progress) 16%, transparent);
}

.statuses__item--active.statuses__item--done {
  border-color: var(--status-done);
  color: var(--status-done);
  background: color-mix(in srgb, var(--status-done) 16%, transparent);
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

.people {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin-top: 6px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  max-height: 150px;
  overflow-y: auto;
}

.people__opt {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text);
  margin: 0;
}

.people__opt input {
  width: 15px;
  height: 15px;
  margin: 0;
}

.people__empty {
  margin: 0;
  font-size: 13px;
  color: var(--text-faint);
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
