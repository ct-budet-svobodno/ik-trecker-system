<script setup>
import { computed, onMounted, ref } from 'vue'

import { fetchUsers } from '../api/users'
import { createTask } from '../api/tasks'
import BaseIcon from './BaseIcon.vue'
import { LEADERSHIP_POSITION_LABELS, ROLE_LABELS } from '../constants/roleLabels'
import { PRIORITY_META } from '../constants/taskMeta'
import { useAuthStore } from '../stores/auth'
import { useTasksStore } from '../stores/tasks'
import { getAvatarColor, getInitials } from '../utils/avatar'

// Одна форма на выдачу и на правку: с task — правим его, без — выдаём новое.
const props = defineProps({
  directions: { type: Array, default: () => [] },
  // Открыто из раздела «Поручения» — сразу в режиме личного поручения.
  privateByDefault: { type: Boolean, default: false },
  checklistByDefault: { type: Boolean, default: false },
  task: { type: Object, default: null },
})

const authStore = useAuthStore()
const tasksStore = useTasksStore()
const isEdit = computed(() => props.task !== null)
const isChecklist = computed(() => props.task?.is_checklist ?? props.checklistByDefault)
// Личные поручения выдаёт руководство: админ или держатель должности.
const canAssignPrivate = computed(() => authStore.isLeadership && !isEdit.value)
const isPrivate = ref(
  props.task ? props.task.is_private : !props.checklistByDefault && props.privateByDefault && authStore.isLeadership,
)

const emit = defineEmits(['close', 'created', 'saved'])

// ТЗ выдают в своё направление: руководитель — туда, где он руководитель,
// руководство и админы — в любое (зеркало task_service.can_issue_to).
const availableDirections = computed(() => {
  const me = authStore.user?.id
  return props.directions.filter(
    (d) =>
      authStore.isLeadership ||
      d.heads?.some((h) => h.id === me) ||
      d.id === props.task?.direction?.id,
  )
})

const title = ref(props.task?.title ?? '')
const description = ref(props.task?.description ?? '')
const directionId = ref(props.task?.direction?.id ?? availableDirections.value[0]?.id ?? null)
const priority = ref(props.task?.priority ?? 'medium')
const assigneeId = ref(props.task?.assignee?.id ?? '')
// Поручение можно дать сразу нескольким руководителям.
const assigneeIds = ref(props.task?.assignees?.map((a) => a.user.id) ?? [])
const dueDate = ref(props.task?.due_date ?? '')

const users = ref([])

// Поручение даётся руководителям: в списке только руководители и админы, кроме себя.
// Сначала руководство (по должности), потом остальные по алфавиту.
const POSITION_ORDER = ['chairman', 'first_deputy', 'secretary', 'brand_manager']
const leaders = computed(() =>
  users.value
    .filter((u) => u.is_active && u.role !== 'employee' && u.id !== authStore.user?.id)
    .sort((a, b) => {
      const pa = POSITION_ORDER.indexOf(a.leadership_position)
      const pb = POSITION_ORDER.indexOf(b.leadership_position)
      if (pa !== pb) return (pa === -1 ? 99 : pa) - (pb === -1 ? 99 : pb)
      return a.full_name.localeCompare(b.full_name, 'ru')
    }),
)

function leaderCaption(user) {
  return LEADERSHIP_POSITION_LABELS[user.leadership_position] ?? ROLE_LABELS[user.role]
}

function toggleLeader(id) {
  assigneeIds.value = assigneeIds.value.includes(id)
    ? assigneeIds.value.filter((x) => x !== id)
    : [...assigneeIds.value, id]
}

const allLeadersPicked = computed(
  () => leaders.value.length > 0 && leaders.value.every((u) => assigneeIds.value.includes(u.id)),
)

function toggleAllLeaders() {
  assigneeIds.value = allLeadersPicked.value ? [] : leaders.value.map((u) => u.id)
}
const error = ref('')
const isSubmitting = ref(false)

// Исполнитель ТЗ: активные по алфавиту (при правке — и нынешний, даже если неактивен).
const assigneeOptions = computed(() =>
  users.value
    .filter((u) => (u.is_active || u.id === props.task?.assignee?.id) && (!isChecklist.value || u.id !== authStore.user?.id))
    .sort((a, b) => a.full_name.localeCompare(b.full_name, 'ru')),
)

const noDirections = computed(() => !isPrivate.value && !isChecklist.value && !availableDirections.value.length)

const heading = computed(() => {
  if (isChecklist.value) return isEdit.value ? 'Изменить чек-лист' : 'Выдать чек-лист'
  if (isEdit.value) return isPrivate.value ? 'Изменить поручение' : 'Изменить ТЗ'
  return isPrivate.value ? 'Личное поручение' : 'Выдать ТЗ'
})

const submitLabel = computed(() => {
  if (isEdit.value) return 'Сохранить'
  if (isChecklist.value) return 'Выдать чек-лист'
  if (!isPrivate.value) return 'Выдать ТЗ'
  const n = assigneeIds.value.length
  return n > 1 ? `Дать поручение (${n})` : 'Дать поручение'
})

onMounted(async () => {
  try {
    users.value = await fetchUsers()
  } catch {
    users.value = []
  }
})

async function saveEdit() {
  const payload = {
    title: title.value,
    description: description.value,
    priority: priority.value,
    due_date: dueDate.value || null,
  }
  if (isPrivate.value) {
    payload.assignee_ids = assigneeIds.value
  } else {
    payload.assignee_id = assigneeId.value === '' ? null : Number(assigneeId.value)
    if (!isChecklist.value && directionId.value !== props.task.direction?.id) payload.direction_id = directionId.value
  }
  try {
    emit('saved', await tasksStore.updateFields(props.task.id, payload))
    emit('close')
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось сохранить'
  } finally {
    isSubmitting.value = false
  }
}

async function handleSubmit() {
  error.value = ''
  if (isChecklist.value && (!assigneeId.value || !dueDate.value)) {
    error.value = 'Выберите исполнителя и дедлайн'
    return
  }
  if (isPrivate.value && !assigneeIds.value.length) {
    error.value = 'Выберите, кому даёте поручение'
    return
  }
  isSubmitting.value = true
  if (isEdit.value) {
    await saveEdit()
    return
  }
  try {
    const task = await createTask({
      title: title.value,
      description: description.value,
      is_private: isPrivate.value,
      is_checklist: isChecklist.value,
      direction_id: isPrivate.value || isChecklist.value ? null : directionId.value,
      priority: priority.value,
      ...(isPrivate.value
        ? { assignee_ids: assigneeIds.value }
        : { assignee_id: assigneeId.value === '' ? null : Number(assigneeId.value) }),
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
      <h2>{{ heading }}</h2>

      <label v-if="canAssignPrivate && !isChecklist" class="private-toggle">
        <input v-model="isPrivate" type="checkbox" />
        <span>
          <span class="private-toggle__title">Личное поручение</span>
          <span class="private-toggle__hint">Без направления. Видят только вы, исполнители, админы и секретарь.</span>
        </span>
      </label>

      <label for="task-title">Название</label>
      <input id="task-title" v-model="title" type="text" required maxlength="200" />

      <label for="task-description">Описание</label>
      <textarea id="task-description" v-model="description" rows="3" maxlength="4000" />

      <div class="modal__row">
        <div v-if="!isPrivate && !isChecklist" class="modal__field">
          <label for="task-direction">Направление</label>
          <select id="task-direction" v-model.number="directionId" required>
            <option v-for="direction in availableDirections" :key="direction.id" :value="direction.id">
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

      <!-- Кому поручение: можно сразу нескольким, у каждого будет свой статус. -->
      <div v-if="isPrivate" class="leaders">
        <div class="leaders__head">
          <span class="leaders__label">
            Кому
            <span v-if="assigneeIds.length" class="leaders__count">{{ assigneeIds.length }}</span>
          </span>
          <button v-if="leaders.length > 1" type="button" class="leaders__all" @click="toggleAllLeaders">
            {{ allLeadersPicked ? 'Снять всех' : 'Выбрать всех' }}
          </button>
        </div>
        <div class="leaders__list">
          <button
            v-for="user in leaders"
            :key="user.id"
            type="button"
            class="leader"
            :class="{ 'leader--on': assigneeIds.includes(user.id) }"
            :aria-pressed="assigneeIds.includes(user.id)"
            @click="toggleLeader(user.id)"
          >
            <span class="leader__avatar" :style="{ background: getAvatarColor(user.id) }">
              {{ getInitials(user.full_name) }}
            </span>
            <span class="leader__text">
              <span class="leader__name">{{ user.full_name }}</span>
              <span class="leader__caption">{{ leaderCaption(user) }}</span>
            </span>
            <span class="leader__check">
              <BaseIcon v-if="assigneeIds.includes(user.id)" name="check" :size="14" />
            </span>
          </button>
          <p v-if="!leaders.length" class="leaders__empty">Список руководителей не загрузился</p>
        </div>
        <p v-if="assigneeIds.length > 1" class="leaders__hint">
          Одно поручение на всех: каждый отмечает свою часть, вы видите, кто уже сделал.
        </p>
      </div>

      <div class="modal__row">
        <div v-if="!isPrivate" class="modal__field">
          <label for="task-assignee">Исполнитель</label>
          <select id="task-assignee" v-model="assigneeId" :required="isChecklist">
            <option value="">{{ isChecklist ? 'Выберите исполнителя' : 'Не назначен' }}</option>
            <option v-for="user in assigneeOptions" :key="user.id" :value="user.id">
              {{ user.full_name }}
            </option>
          </select>
        </div>

        <div class="modal__field">
          <label for="task-due-date">Срок</label>
          <input id="task-due-date" v-model="dueDate" type="date" :required="isChecklist" />
        </div>
      </div>

      <p v-if="noDirections" class="error">
        Вы не руководите ни одним направлением. ТЗ выдают руководители направлений и руководство —
        а личное поручение можно дать, если у вас есть должность.
      </p>
      <p v-if="error" class="error">{{ error }}</p>

      <div class="modal__actions">
        <button type="button" class="modal__cancel" @click="$emit('close')">Отмена</button>
        <button type="submit" class="modal__submit" :disabled="isSubmitting || noDirections">
          {{ isSubmitting ? 'Сохраняем…' : submitLabel }}
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
  max-height: 92dvh;
  overflow-y: auto;
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

.private-toggle {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin: 0 0 4px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
}

.modal .private-toggle input {
  margin: 2px 0 0;
  padding: 0;
  accent-color: var(--accent);
}

.private-toggle__title {
  display: block;
  font-size: 14px;
  font-weight: 500;
}

.private-toggle__hint {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
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

.leaders {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 10px;
}

.leaders__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.leaders__label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-muted);
}

.leaders__count {
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: var(--radius-full);
  background: var(--accent);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  line-height: 20px;
  text-align: center;
}

.leaders__all {
  padding: 0;
  border: none;
  background: none;
  color: var(--accent);
  font-size: 13px;
}

.leaders__list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 264px;
  overflow-y: auto;
  padding: 4px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
}

.leader {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 48px;
  padding: 6px 10px;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text);
  text-align: left;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.leader:hover {
  background: var(--surface-hover);
}

.leader--on {
  border-color: color-mix(in srgb, var(--accent) 55%, transparent);
  background: color-mix(in srgb, var(--accent) 12%, transparent);
}

.leader__avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}

.leader__text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.leader__name {
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.leader__caption {
  font-size: 12px;
  color: var(--text-muted);
}

.leader__check {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid var(--border-strong);
  border-radius: 50%;
  color: #fff;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.leader--on .leader__check {
  border-color: var(--accent);
  background: var(--accent);
}

.leaders__empty,
.leaders__hint {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.leaders__empty {
  padding: 8px;
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
