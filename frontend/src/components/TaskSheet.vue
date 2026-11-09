<script setup>
import { computed, onMounted, ref } from 'vue'

import BaseIcon from './BaseIcon.vue'
import CommentThread from './CommentThread.vue'
import CreateTaskModal from './CreateTaskModal.vue'
import { addTaskComment, deleteTaskComment, fetchTaskComments } from '../api/tasks'
import { PRIORITY_META, STATUS_META } from '../constants/taskMeta'
import { useAuthStore } from '../stores/auth'
import { useTasksStore } from '../stores/tasks'
import { getAvatarColor, getInitials } from '../utils/avatar'
import { formatDueDate } from '../utils/formatDate'
import { NEXT_STEP, STATUS_STEPS, assigneesDone, daysUntilDue, isOverdue } from '../utils/taskProgress'
import { telegramApp } from '../utils/telegram'

// Карточка задачи: детали и смена статуса. На мобильных — шторка снизу
// (общие стили .modal из style.css), на десктопе — модалка по центру.
const props = defineProps({
  task: { type: Object, required: true },
})

const emit = defineEmits(['close'])

const authStore = useAuthStore()
const tasksStore = useTasksStore()

const isBusy = ref(false)
const error = ref('')

// ── Правка и удаление (права — task.can_manage с бэка) ──
const isEditing = ref(false)

async function removeTask() {
  const what = props.task.is_checklist ? 'чек-лист' : props.task.is_private ? 'поручение' : 'ТЗ'
  if (!window.confirm(`Удалить ${what} «${props.task.title}»? Исполнителям придёт уведомление об отмене.`)) return
  isBusy.value = true
  error.value = ''
  try {
    await tasksStore.removeTask(props.task.id)
    emit('close')
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось удалить'
    isBusy.value = false
  }
}

// ── Обсуждение ──
const comments = ref([])
const commentsLoaded = ref(false)

async function loadComments() {
  try {
    comments.value = await fetchTaskComments(props.task.id)
    tasksStore.setCommentsCount(props.task.id, comments.value.length)
  } catch {
    comments.value = []
  } finally {
    commentsLoaded.value = true
  }
}

async function onAddComment({ body, parentId }) {
  error.value = ''
  try {
    comments.value = [...comments.value, await addTaskComment(props.task.id, body, parentId)]
    tasksStore.setCommentsCount(props.task.id, comments.value.length)
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось отправить комментарий'
  }
}

async function onRemoveComment({ id }) {
  try {
    await deleteTaskComment(props.task.id, id)
    await loadComments() // вместе с комментарием ушли и ответы на него
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось удалить комментарий'
  }
}

onMounted(loadComments)

const priorityMeta = computed(() => PRIORITY_META[props.task.priority])
const statusSteps = computed(() => props.task.is_checklist ? ['todo', 'in_progress', 'done'] : STATUS_STEPS)
const stepIndex = computed(() => statusSteps.value.indexOf(props.task.status))
const nextStep = computed(() => props.task.is_checklist
  ? ({ todo: { status: 'in_progress', label: 'В работе' }, in_progress: { status: 'done', label: 'Сделано' }, done: { status: 'in_progress', label: 'В работе' } })[props.task.status]
  : NEXT_STEP[props.task.status])
const overdue = computed(() => isOverdue(props.task))

// Поручение нескольким: у каждого исполнителя свой статус. Исполнитель видит
// и двигает свою часть (task.status с бэка — его личный), автор — сводный.
const team = computed(() => props.task.assignees ?? [])
const isTeam = computed(() => team.value.length > 1)
const teamDone = computed(() => assigneesDone(props.task))
const myPart = computed(() => team.value.find((a) => a.user.id === authStore.user?.id))
const isAuthor = computed(() => props.task.created_by_id === authStore.user?.id)
// Автор поручения на нескольких сам шаги не двигает — только принимает работу у всех.
const authorOfTeam = computed(() => isTeam.value && isAuthor.value && !myPart.value)

// Зеркало прав бэка (task_service.update_task): поручение двигают автор и
// исполнители, обычную задачу — руководители и исполнитель.
const canChangeStatus = computed(() => {
  const me = authStore.user?.id
  if (props.task.is_checklist) return props.task.assignee?.id === me
  if (props.task.is_private) {
    if (authorOfTeam.value) return false
    return !!myPart.value || props.task.assignee?.id === me || isAuthor.value
  }
  return props.task.assignee?.id === me || props.task.can_manage
})

// Напомнить может автор поручения, пока кто-то из исполнителей не сдал работу
// (на проверке или готово — напоминать нечего).
const SUBMITTED = ['in_review', 'done']
const notDone = computed(() =>
  team.value.length
    ? team.value.filter((a) => !SUBMITTED.includes(a.status)).length
    : Number(!SUBMITTED.includes(props.task.status)),
)
const canRemind = computed(() => props.task.is_private && isAuthor.value && notDone.value > 0)
const remindNote = ref('')

const remindedAgo = computed(() => {
  if (!props.task.reminded_at) return ''
  const minutes = Math.round((Date.now() - new Date(props.task.reminded_at)) / 60000)
  if (minutes < 1) return 'Напомнили только что'
  if (minutes < 60) return `Напомнили ${minutes} мин назад`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `Напомнили ${hours} ч назад`
  return `Напомнили ${createdFmt.format(new Date(props.task.reminded_at))}`
})

async function remind() {
  if (isBusy.value) return
  isBusy.value = true
  error.value = ''
  remindNote.value = ''
  try {
    await tasksStore.remind(props.task.id)
    remindNote.value = notDone.value > 1 ? `Напомнили ${notDone.value} исполнителям` : 'Напоминание отправлено'
    telegramApp()?.HapticFeedback?.notificationOccurred('success')
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось напомнить'
    telegramApp()?.HapticFeedback?.notificationOccurred('error')
  } finally {
    isBusy.value = false
  }
}

// Главная кнопка автора: принять работу, когда все сдали, или вернуть в работу.
const authorAction = computed(() => {
  if (!authorOfTeam.value) return null
  if (props.task.status === 'done') return { status: 'in_progress', label: 'Вернуть всем в работу' }
  if (props.task.status === 'in_review') return { status: 'done', label: 'Принять работу у всех' }
  return null
})

const dueHint = computed(() => {
  if (props.task.status === 'done') return ''
  const days = daysUntilDue(props.task)
  if (days === null) return ''
  if (days < 0) return `просрочено на ${-days} ${plural(-days, 'день', 'дня', 'дней')}`
  if (days === 0) return 'сегодня'
  if (days === 1) return 'завтра'
  return `через ${days} ${plural(days, 'день', 'дня', 'дней')}`
})

function plural(n, one, few, many) {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few
  return many
}

// Короткие подписи шагов: четыре колонки должны влезать в ширину телефона.
const STEP_LABELS = { todo: 'Новая', in_progress: 'В работе', in_review: 'Проверка', done: 'Готово' }

// Порядок в списке исполнителей: кто ещё не сделал — выше.
const STATUS_ORDER = { todo: 0, in_progress: 1, in_review: 2, done: 3 }
const teamSorted = computed(() =>
  [...team.value].sort((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status]),
)

const createdFmt = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long' })

async function setStatus(status) {
  if (status === props.task.status || isBusy.value) return
  isBusy.value = true
  error.value = ''
  try {
    await tasksStore.setTaskStatus(props.task.id, status)
    telegramApp()?.HapticFeedback?.notificationOccurred('success')
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось изменить статус'
    telegramApp()?.HapticFeedback?.notificationOccurred('error')
  } finally {
    isBusy.value = false
  }
}
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <div v-swipe-close="() => emit('close')" class="modal sheet" role="dialog" aria-modal="true">
      <header class="sheet__labels">
        <span v-if="task.direction" class="sheet__chip" :class="`sheet__chip--${task.direction.color}`">
          {{ task.direction.short_code }}
        </span>
        <span v-else class="sheet__chip sheet__chip--private">
          <BaseIcon name="lock" :size="12" />
          {{ task.is_checklist ? 'Чек-лист' : 'Поручение' }}
        </span>
        <span class="sheet__prio" :class="`sheet__prio--${priorityMeta.tone}`">
          {{ priorityMeta.label }} приоритет
        </span>
        <span v-if="task.can_manage" class="sheet__tools">
          <button class="sheet__tool" aria-label="Изменить" title="Изменить" @click="isEditing = true">
            <BaseIcon name="pen" :size="16" />
          </button>
          <button
            class="sheet__tool sheet__tool--danger"
            aria-label="Удалить"
            title="Удалить"
            :disabled="isBusy"
            @click="removeTask"
          >
            <BaseIcon name="trash" :size="16" />
          </button>
        </span>
      </header>

      <h2 class="sheet__title">{{ task.title }}</h2>
      <p v-if="task.description" class="sheet__desc">{{ task.description }}</p>

      <p v-if="isTeam" class="steps__caption">
        {{ myPart ? 'Ваша часть' : 'Общий статус' }}
      </p>
      <!-- Шаги: пройденные закрашены, текущий подсвечен. Нажатие — перейти на шаг. -->
      <div class="steps" :class="{ 'steps--readonly': !canChangeStatus }">
        <button
          v-for="(status, idx) in statusSteps"
          :key="status"
          class="step"
          :class="{
            'step--passed': idx < stepIndex,
            'step--current': idx === stepIndex,
            [`step--${STATUS_META[status].color}`]: true,
          }"
          :disabled="!canChangeStatus || isBusy"
          @click="setStatus(status)"
        >
          <span class="step__bar" />
          <span class="step__label">{{ task.is_checklist && status === 'todo' ? 'Не начато' : task.is_checklist && status === 'done' ? 'Сделано' : STEP_LABELS[status] }}</span>
        </button>
      </div>

      <!-- Исполнители поручения: кто на каком шаге -->
      <section v-if="isTeam" class="team">
        <header class="team__head">
          <span class="team__title">Исполнители</span>
          <span class="team__count">{{ teamDone }} из {{ team.length }} сделали</span>
        </header>
        <div class="team__bar" aria-hidden="true">
          <span
            v-for="a in [...teamSorted].reverse()"
            :key="a.user.id"
            class="team__seg"
            :class="`team__seg--${STATUS_META[a.status].color}`"
          />
        </div>
        <ul class="team__list">
          <li
            v-for="a in teamSorted"
            :key="a.user.id"
            class="team__row"
            :class="{ 'team__row--me': a.user.id === authStore.user?.id }"
          >
            <span class="meta__avatar" :style="{ background: getAvatarColor(a.user.id) }">
              {{ getInitials(a.user.full_name) }}
            </span>
            <span class="team__name">
              {{ a.user.full_name }}<span v-if="a.user.id === authStore.user?.id" class="team__you"> · вы</span>
            </span>
            <span class="team__status" :class="`team__status--${STATUS_META[a.status].color}`">
              <span class="team__dot" />
              {{ STEP_LABELS[a.status] }}
            </span>
          </li>
        </ul>
      </section>

      <dl class="meta">
        <div v-if="!isTeam" class="meta__row">
          <dt>Исполнитель</dt>
          <dd class="meta__person">
            <span
              v-if="task.assignee"
              class="meta__avatar"
              :style="{ background: getAvatarColor(task.assignee.id) }"
            >
              {{ getInitials(task.assignee.full_name) }}
            </span>
            {{ task.assignee?.full_name ?? 'Не назначен' }}
          </dd>
        </div>
        <div class="meta__row">
          <dt>Срок</dt>
          <dd>
            {{ formatDueDate(task.due_date) }}
            <span v-if="dueHint" class="meta__hint" :class="{ 'meta__hint--danger': overdue }">
              {{ dueHint }}
            </span>
          </dd>
        </div>
        <div class="meta__row">
          <dt>{{ task.is_private ? 'Поручил' : 'Выдал' }}</dt>
          <dd>{{ task.created_by?.full_name ?? '—' }}</dd>
        </div>
        <div v-if="task.direction" class="meta__row">
          <dt>Направление</dt>
          <dd>{{ task.direction.name }}</dd>
        </div>
        <div class="meta__row">
          <dt>Создана</dt>
          <dd>{{ createdFmt.format(new Date(task.created_at)) }}</dd>
        </div>
      </dl>

      <section class="discussion">
        <h3 class="discussion__title">
          Обсуждение
          <span v-if="comments.length" class="discussion__count">{{ comments.length }}</span>
        </h3>
        <p v-if="!commentsLoaded" class="discussion__hint">Загружаем…</p>
        <CommentThread
          v-else
          :comments="comments"
          :can-comment="task.can_comment"
          :can-resolve="false"
          :current-user-id="authStore.user?.id ?? null"
          @add="onAddComment"
          @remove="onRemoveComment"
        />
        <p v-if="commentsLoaded && !task.can_comment" class="discussion__hint">
          Писать могут исполнитель, выдавший и руководители направления.
        </p>
      </section>

      <div v-if="canRemind" class="remind">
        <button class="remind__btn" :disabled="isBusy" @click="remind">
          <BaseIcon name="bell" :size="16" />
          {{ isTeam ? `Напомнить, кто не сдал · ${notDone}` : 'Напомнить исполнителю' }}
        </button>
        <span v-if="remindNote || remindedAgo" class="remind__note">{{ remindNote || remindedAgo }}</span>
      </div>

      <p v-if="error" class="sheet__error">{{ error }}</p>

      <div class="sheet__actions">
        <button
          v-if="authorAction"
          class="create-btn sheet__next"
          :class="{ 'sheet__next--back': authorAction.status !== 'done' }"
          :disabled="isBusy"
          @click="setStatus(authorAction.status)"
        >
          <BaseIcon v-if="authorAction.status === 'done'" name="check" :size="16" />
          {{ authorAction.label }}
        </button>
        <button
          v-if="canChangeStatus"
          class="create-btn sheet__next"
          :class="{ 'sheet__next--back': task.status === 'done' }"
          :disabled="isBusy"
          @click="setStatus(nextStep.status)"
        >
          <BaseIcon v-if="task.status !== 'done'" name="check" :size="16" />
          {{ nextStep.label }}
        </button>
        <button class="sheet__close" @click="emit('close')">Закрыть</button>
      </div>
    </div>

    <CreateTaskModal
      v-if="isEditing"
      :task="task"
      :directions="tasksStore.directions"
      @close="isEditing = false"
    />
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
  padding: var(--space-5);
  z-index: 100;
}

.modal {
  width: 100%;
  max-width: 480px;
  max-height: 90vh;
  overflow-y: auto;
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.sheet__labels {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.sheet__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  color: #fff;
  white-space: nowrap;
}

.sheet__chip--violet { background: var(--dir-ct); }
.sheet__chip--pink { background: var(--dir-design); }
.sheet__chip--cyan { background: var(--dir-nvk); }
.sheet__chip--green { background: var(--dir-photo); }
.sheet__chip--orange { background: var(--dir-smi); }
.sheet__chip--blue { background: var(--dir-prod); }
.sheet__chip--private { background: var(--accent-soft); color: var(--text); }

.sheet__tools {
  display: flex;
  gap: 4px;
  margin-left: auto;
}

.sheet__tool {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-muted);
}

.sheet__tool:hover:not(:disabled) {
  color: var(--text);
  background: var(--surface-hover);
}

.sheet__tool--danger:hover:not(:disabled) {
  color: var(--danger);
}

.discussion {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.discussion__title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: var(--space-2) 0 0;
  font-size: 14px;
  font-weight: 600;
}

.discussion__count {
  font: 12px var(--font-mono);
  color: var(--text-muted);
}

.discussion__hint {
  margin: 0;
  font-size: 12px;
  color: var(--text-faint);
}

.sheet__prio {
  font-size: 12px;
  color: var(--text-muted);
}

.sheet__prio--medium { color: var(--prio-medium); }
.sheet__prio--high { color: var(--prio-high); }

.sheet__title {
  margin: 0;
  font-size: 18px;
  line-height: 24px;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.sheet__desc {
  margin: 0;
  font-size: 14px;
  line-height: 21px;
  color: var(--text-muted);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.steps__caption {
  margin: var(--space-1) 0 -4px;
  font-size: 12px;
  color: var(--text-muted);
}

/* Исполнители поручения */
.team {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
}

.team__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--space-2);
}

.team__title {
  font-size: 13px;
  font-weight: 600;
}

.team__count {
  font-size: 12px;
  color: var(--text-muted);
}

/* По отрезку на исполнителя, цветом его статуса. */
.team__bar {
  display: flex;
  gap: 3px;
}

.team__seg {
  flex: 1;
  height: 6px;
  border-radius: var(--radius-sm);
  background: var(--border);
}

.team__seg--orange { background: var(--status-progress); }
.team__seg--purple { background: var(--status-review); }
.team__seg--green { background: var(--status-done); }

.team__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
}

.team__row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 40px;
}

.team__row + .team__row {
  border-top: 1px solid var(--border);
}

.team__name {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.team__row--me .team__name {
  font-weight: 600;
}

.team__you {
  font-weight: 400;
  color: var(--text-muted);
}

.team__status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.team__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--status-todo);
}

.team__status--orange .team__dot { background: var(--status-progress); }
.team__status--purple .team__dot { background: var(--status-review); }
.team__status--green { color: var(--status-done); }
.team__status--green .team__dot { background: var(--status-done); }

/* Шаги статуса: четыре отрезка, пройденные и текущий — цветом своего статуса. */
.steps {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4px;
  margin-top: var(--space-1);
}

.step {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 0;
  border: none;
  background: transparent;
  text-align: left;
  min-width: 0;
}

.step:disabled {
  cursor: default;
}

/* Внутри <button> flex-элементы не растягиваются сами — ширина явно. */
.step__bar {
  display: block;
  width: 100%;
  height: 6px;
  border-radius: var(--radius-sm);
  background: var(--border);
  transition: background 0.25s ease;
}

.step__label {
  display: block;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 14px;
  color: var(--text-faint);
}

.step--passed .step__bar { background: var(--border-strong); }
.step--passed .step__label { color: var(--text-muted); }

.step--current .step__label {
  color: var(--text);
  font-weight: 600;
}

.step--current.step--grey .step__bar { background: var(--status-todo); }
.step--current.step--orange .step__bar { background: var(--status-progress); }
.step--current.step--purple .step__bar { background: var(--status-review); }
.step--current.step--green .step__bar { background: var(--status-done); }

.steps:not(.steps--readonly) .step:not(.step--current):not(:disabled):hover .step__bar {
  background: var(--text-faint);
}

.meta {
  margin: var(--space-1) 0 0;
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--border);
}

.meta__row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  min-height: 40px;
  border-bottom: 1px solid var(--border);
}

.meta dt {
  font-size: 13px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.meta dd {
  margin: 0;
  font-size: 14px;
  text-align: right;
  min-width: 0;
  overflow-wrap: anywhere;
}

.meta__person {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.meta__avatar {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.meta__hint {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
}

.meta__hint--danger {
  color: var(--danger);
}

.remind {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 6px;
}

.remind__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  height: var(--control-h);
  border: 1px solid color-mix(in srgb, var(--accent) 45%, transparent);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  color: var(--text);
  font-size: 14px;
  font-weight: 500;
}

.remind__btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--accent) 18%, transparent);
}

.remind__btn:disabled {
  opacity: 0.6;
}

.remind__note {
  font-size: 12px;
  color: var(--text-muted);
  text-align: center;
}

.sheet__error {
  margin: 0;
  font-size: 13px;
  color: var(--danger);
}

.sheet__actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.sheet__next {
  flex: 1;
}

.sheet__next:disabled {
  opacity: 0.6;
  cursor: default;
}

/* «Вернуть в работу» — не главное действие, без заливки. */
.sheet__next--back {
  background: transparent;
  border: 1px solid var(--border-strong);
  color: var(--text);
}

.sheet__next--back:hover {
  background: var(--surface-hover);
}

.sheet__close {
  height: var(--control-h);
  padding: 0 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-muted);
}

.sheet__close:hover {
  color: var(--text);
}

@media (max-width: 768px) {
  .modal {
    max-height: 92dvh;
  }

  .step__bar {
    height: 8px;
  }

  /* Пальцу нужна высокая зона нажатия: подпись шага — часть кнопки. */
  .step {
    padding-bottom: var(--space-1);
  }

  .sheet__close,
  .remind__btn {
    height: var(--control-h-touch);
  }
}
</style>
