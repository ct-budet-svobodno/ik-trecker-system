<script setup>
import { computed, ref } from 'vue'

import BaseIcon from './BaseIcon.vue'
import { useEventsStore } from '../stores/events'
import { dayKey } from '../utils/dateKey'
import { formatTime } from '../utils/formatDateTime'

// Мероприятие: просмотр (для всех), правка и создание (руководители и админы).
// Дата и время — отдельными полями: системное «дата+время» на телефоне не
// помещается в половину ширины и выглядит по-разному в каждом браузере.
const props = defineProps({
  event: { type: Object, default: null },
  // День, на который создаём (YYYY-MM-DD); без него — сегодня.
  defaultDate: { type: String, default: '' },
  canEdit: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])

const eventsStore = useEventsStore()
const isNew = computed(() => !props.event)
// Существующее мероприятие сначала показываем карточкой; править — по кнопке.
const isEditing = ref(isNew.value)

const pad = (n) => String(n).padStart(2, '0')
const timeOf = (iso) => {
  const d = new Date(iso)
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const title = ref(props.event?.title ?? '')
const description = ref(props.event?.description ?? '')
const location = ref(props.event?.location ?? '')
const date = ref(props.event ? dayKey(new Date(props.event.start_at)) : props.defaultDate || dayKey(new Date()))
const startTime = ref(props.event ? timeOf(props.event.start_at) : '12:00')
const endTime = ref(props.event?.end_at ? timeOf(props.event.end_at) : '')

const error = ref('')
const isSubmitting = ref(false)

const dateFmt = new Intl.DateTimeFormat('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })

const whenLabel = computed(() => {
  if (!props.event) return ''
  const day = dateFmt.format(new Date(props.event.start_at))
  const time = props.event.end_at
    ? `${formatTime(props.event.start_at)} – ${formatTime(props.event.end_at)}`
    : formatTime(props.event.start_at)
  return `${day[0].toUpperCase()}${day.slice(1)}, ${time}`
})

function toDate(day, time) {
  const [y, m, d] = day.split('-').map(Number)
  const [hh, mm] = time.split(':').map(Number)
  return new Date(y, m - 1, d, hh, mm)
}

// Время «как на часах», без пояса: бэк так и хранит, а читаем его как местное.
// Не toISOString() — тот переводит в UTC, и время уезжало назад на каждом сохранении.
function wallClock(value) {
  return `${dayKey(value)}T${pad(value.getHours())}:${pad(value.getMinutes())}:00`
}

async function handleSubmit() {
  error.value = ''
  const start = toDate(date.value, startTime.value)
  let end = null
  if (endTime.value) {
    end = toDate(date.value, endTime.value)
    // Конец раньше начала — значит, после полуночи.
    if (end <= start) end.setDate(end.getDate() + 1)
  }
  isSubmitting.value = true
  try {
    const payload = {
      title: title.value,
      description: description.value,
      location: location.value || null,
      start_at: wallClock(start),
      end_at: end ? wallClock(end) : null,
    }
    if (isNew.value) await eventsStore.addEvent(payload)
    else await eventsStore.editEvent(props.event.id, payload)
    emit('close')
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось сохранить мероприятие'
  } finally {
    isSubmitting.value = false
  }
}

// ── Приду / Не приду ──
// Берём из стора: после ответа там свежая версия, а props.event — снимок на момент открытия.
const live = computed(() => eventsStore.events.find((e) => e.id === props.event?.id) ?? props.event)
const isPast = computed(() => {
  const e = live.value
  return !!e && new Date(e.end_at ?? e.start_at) < new Date()
})
const isRsvpBusy = ref(false)
const showPeople = ref(false)

async function answer(status) {
  if (isRsvpBusy.value) return
  isRsvpBusy.value = true
  error.value = ''
  try {
    // Повторное нажатие на свой ответ — снять его.
    await eventsStore.setRsvp(live.value.id, live.value.my_rsvp === status ? null : status)
  } catch {
    error.value = 'Не удалось сохранить ответ'
  } finally {
    isRsvpBusy.value = false
  }
}

async function handleDelete() {
  if (!window.confirm(`Удалить мероприятие «${props.event.title}»?`)) return
  isSubmitting.value = true
  try {
    await eventsStore.removeEvent(props.event.id)
    emit('close')
  } catch {
    error.value = 'Не удалось удалить мероприятие'
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <!-- Просмотр -->
    <div v-if="!isEditing" v-swipe-close="() => emit('close')" class="modal ev">
      <div class="ev__head">
        <span class="ev__chip">
          <BaseIcon name="calendar" :size="12" />
          Мероприятие
        </span>
        <span v-if="canEdit" class="ev__tools">
          <button class="ev__tool" aria-label="Изменить" title="Изменить" @click="isEditing = true">
            <BaseIcon name="pen" :size="16" />
          </button>
          <button
            class="ev__tool ev__tool--danger"
            aria-label="Удалить"
            title="Удалить"
            :disabled="isSubmitting"
            @click="handleDelete"
          >
            <BaseIcon name="trash" :size="16" />
          </button>
        </span>
      </div>
      <h2 class="ev__title">{{ event.title }}</h2>
      <dl class="ev__facts">
        <div class="ev__fact">
          <dt>Когда</dt>
          <dd>{{ whenLabel }}</dd>
        </div>
        <div v-if="event.location" class="ev__fact">
          <dt>Где</dt>
          <dd>{{ event.location }}</dd>
        </div>
      </dl>
      <p v-if="event.description" class="ev__desc">{{ event.description }}</p>

      <section class="rsvp" aria-label="Ответ на мероприятие">
        <div v-if="!isPast" class="rsvp__btns">
          <button
            class="rsvp__btn rsvp__btn--yes"
            :class="{ 'rsvp__btn--on': live.my_rsvp === 'going' }"
            :aria-pressed="live.my_rsvp === 'going'"
            :disabled="isRsvpBusy"
            @click="answer('going')"
          >
            <BaseIcon v-if="live.my_rsvp === 'going'" name="check" :size="16" />
            Приду
          </button>
          <button
            class="rsvp__btn rsvp__btn--no"
            :class="{ 'rsvp__btn--on': live.my_rsvp === 'not_going' }"
            :aria-pressed="live.my_rsvp === 'not_going'"
            :disabled="isRsvpBusy"
            @click="answer('not_going')"
          >
            Не приду
          </button>
        </div>
        <!-- Имена приходят только админам — остальным просто счётчики. -->
        <button
          v-if="live.going.length || live.not_going.length"
          class="rsvp__summary"
          :aria-expanded="showPeople"
          @click="showPeople = !showPeople"
        >
          <span>Придут: <b>{{ live.going_count }}</b></span>
          <span>Не придут: <b>{{ live.not_going_count }}</b></span>
          <BaseIcon name="chevron-right" :size="14" class="rsvp__chevron" :class="{ 'rsvp__chevron--open': showPeople }" />
        </button>
        <p v-else-if="live.going_count || live.not_going_count" class="rsvp__summary rsvp__summary--static">
          <span>Придут: <b>{{ live.going_count }}</b></span>
          <span>Не придут: <b>{{ live.not_going_count }}</b></span>
        </p>
        <p v-else class="rsvp__empty">{{ isPast ? 'Никто не отмечался' : 'Пока никто не ответил' }}</p>
        <div v-if="showPeople" class="rsvp__people">
          <div v-if="live.going.length">
            <p class="rsvp__label">Придут</p>
            <p class="rsvp__names">{{ live.going.map((p) => p.full_name).join(', ') }}</p>
          </div>
          <div v-if="live.not_going.length">
            <p class="rsvp__label">Не придут</p>
            <p class="rsvp__names">{{ live.not_going.map((p) => p.full_name).join(', ') }}</p>
          </div>
        </div>
      </section>

      <p v-if="error" class="ev__error">{{ error }}</p>
      <button class="ev__secondary" @click="emit('close')">Закрыть</button>
    </div>

    <!-- Создание и правка -->
    <form v-else v-swipe-close="() => emit('close')" class="modal ev" @submit.prevent="handleSubmit">
      <h2 class="ev__title">{{ isNew ? 'Новое мероприятие' : 'Изменить мероприятие' }}</h2>

      <label class="ev__field">
        <span class="ev__label">Название</span>
        <input v-model="title" class="ev__input" type="text" required maxlength="200" placeholder="Например, планёрка актива" />
      </label>

      <label class="ev__field">
        <span class="ev__label">Дата</span>
        <input v-model="date" class="ev__input" type="date" required />
      </label>

      <div class="ev__row">
        <label class="ev__field">
          <span class="ev__label">Начало</span>
          <input v-model="startTime" class="ev__input" type="time" required />
        </label>
        <label class="ev__field">
          <span class="ev__label">Конец <span class="ev__optional">— необяз.</span></span>
          <input v-model="endTime" class="ev__input" type="time" />
        </label>
      </div>

      <label class="ev__field">
        <span class="ev__label">Место <span class="ev__optional">— необяз.</span></span>
        <input v-model="location" class="ev__input" type="text" maxlength="200" placeholder="Аудитория, адрес или ссылка" />
      </label>

      <label class="ev__field">
        <span class="ev__label">Описание <span class="ev__optional">— необяз.</span></span>
        <textarea v-model="description" class="ev__input ev__textarea" rows="3" maxlength="4000" />
      </label>

      <p v-if="error" class="ev__error">{{ error }}</p>

      <div class="ev__actions">
        <button type="submit" class="ev__primary" :disabled="isSubmitting">
          {{ isSubmitting ? 'Сохраняем…' : isNew ? 'Назначить' : 'Сохранить' }}
        </button>
        <button type="button" class="ev__secondary" @click="isNew ? emit('close') : (isEditing = false)">
          Отмена
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
  padding: var(--space-5);
  z-index: 100;
}

.modal {
  width: 100%;
  max-width: 460px;
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

.ev__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.ev__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  font-size: 11px;
  font-weight: 600;
}

.ev__tools {
  display: flex;
  gap: 4px;
}

.ev__tool {
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

.ev__tool:hover:not(:disabled) {
  color: var(--text);
  background: var(--surface-hover);
}

.ev__tool--danger:hover:not(:disabled) {
  color: var(--danger);
}

.ev__title {
  margin: 0;
  font-size: 18px;
  line-height: 24px;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.ev__facts {
  margin: 0;
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--border);
}

.ev__fact {
  display: flex;
  gap: var(--space-3);
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}

.ev__fact dt {
  width: 56px;
  flex-shrink: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.ev__fact dd {
  margin: 0;
  font-size: 14px;
  overflow-wrap: anywhere;
}

.ev__desc {
  margin: 0;
  font-size: 14px;
  line-height: 21px;
  color: var(--text-muted);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.rsvp {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.rsvp__btns {
  display: flex;
  gap: var(--space-2);
}

.rsvp__btn {
  flex: 1;
  height: var(--control-h);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text);
  font-size: 14px;
  font-weight: 600;
}

.rsvp__btn--yes {
  border-color: color-mix(in srgb, var(--rsvp-yes) 55%, transparent);
  background: color-mix(in srgb, var(--rsvp-yes) 12%, transparent);
  color: var(--rsvp-yes);
}

.rsvp__btn--no {
  border-color: color-mix(in srgb, var(--rsvp-no) 55%, transparent);
  background: color-mix(in srgb, var(--rsvp-no) 12%, transparent);
  color: var(--rsvp-no);
}

.rsvp__btn--yes:hover:not(:disabled) {
  background: color-mix(in srgb, var(--rsvp-yes) 22%, transparent);
}

.rsvp__btn--no:hover:not(:disabled) {
  background: color-mix(in srgb, var(--rsvp-no) 22%, transparent);
}

.rsvp__btn--yes.rsvp__btn--on {
  border-color: transparent;
  background: var(--rsvp-yes);
  color: var(--on-success);
}

.rsvp__btn--no.rsvp__btn--on {
  border-color: transparent;
  background: var(--rsvp-no);
  color: var(--text);
}

.rsvp__summary {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: 0;
  border: none;
  background: none;
  color: var(--text-muted);
  font-size: 13px;
  text-align: left;
}

.rsvp__summary b {
  color: var(--text);
}

.rsvp__summary--static {
  margin: 0;
}

.rsvp__chevron {
  margin-left: auto;
  transition: transform 0.15s;
}

.rsvp__chevron--open {
  transform: rotate(90deg);
}

.rsvp__empty {
  margin: 0;
  font-size: 13px;
  color: var(--text-faint);
}

.rsvp__people {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface);
}

.rsvp__label {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.rsvp__names {
  margin: 2px 0 0;
  font-size: 13px;
  line-height: 19px;
}

.ev__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  flex: 1;
}

.ev__label {
  font-size: 13px;
  color: var(--text-muted);
}

.ev__optional {
  color: var(--text-faint);
}

.ev__input {
  width: 100%;
  min-width: 0;
  height: var(--control-h);
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: 14px;
  color-scheme: dark;
}

.ev__textarea {
  height: auto;
  padding: 10px 12px;
  resize: vertical;
}

.ev__input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 22%, transparent);
}

.ev__row {
  display: flex;
  gap: var(--space-3);
}

.ev__error {
  margin: 0;
  font-size: 13px;
  color: var(--danger);
}

.ev__actions {
  display: flex;
  flex-direction: row-reverse;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.ev__primary,
.ev__secondary {
  height: var(--control-h);
  padding: 0 16px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 600;
}

.ev__primary {
  flex: 1;
  border: none;
  background: var(--success);
  color: var(--on-success);
}

.ev__primary:hover:not(:disabled) {
  background: var(--success-hover);
}

.ev__primary:disabled {
  opacity: 0.6;
}

.ev__secondary {
  border: 1px solid var(--border-strong);
  background: transparent;
  color: var(--text);
}

@media (max-width: 768px) {
  .ev__input,
  .ev__primary,
  .ev__secondary,
  .rsvp__btn {
    height: var(--control-h-touch);
  }

  .ev__textarea {
    height: auto;
  }
}
</style>
