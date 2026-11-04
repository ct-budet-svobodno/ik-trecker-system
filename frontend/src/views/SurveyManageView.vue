<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import BaseIcon from '../components/BaseIcon.vue'
import { fetchDirections } from '../api/directions'
import {
  createSurvey,
  deleteSurvey,
  fetchSurvey,
  remindSurvey,
  sendSurvey,
  setSurveyStatus,
  updateSurvey,
} from '../api/surveys'
import { fetchUsers } from '../api/users'
import {
  QUESTION_TYPES,
  STATUS_LABELS,
  answerText,
  apiError,
  formatWhen,
  newQuestionId,
  plural,
} from '../utils/surveys'

const route = useRoute()
const router = useRouter()

const survey = ref(null) // ответ GET /surveys/:id; null — новая анкета
const isLoading = ref(true)
const loadError = ref('')
const tab = ref('questions') // questions | send | answers

const isNew = computed(() => !survey.value)

// ── Вопросы ──
const draft = ref({ title: '', description: '', questions: [] })
const isSaving = ref(false)
const saveError = ref('')
const saveNotice = ref('')
const locked = computed(() => survey.value && !survey.value.can_edit_questions)

function blankQuestion(type = 'single') {
  return {
    id: newQuestionId(),
    type,
    title: '',
    hint: '',
    required: true,
    options: type === 'single' || type === 'multi' ? ['', ''] : [],
    max: 5,
  }
}

function fromSurvey(s) {
  draft.value = {
    title: s.title,
    description: s.description,
    questions: s.questions.map((q) => ({ ...q, options: [...q.options] })),
  }
}

function addQuestion() {
  draft.value.questions.push(blankQuestion())
}

function removeQuestion(i) {
  draft.value.questions.splice(i, 1)
}

function moveQuestion(i, delta) {
  const list = draft.value.questions
  const target = i + delta
  if (target < 0 || target >= list.length) return
  ;[list[i], list[target]] = [list[target], list[i]]
}

function changeType(q, type) {
  q.type = type
  if ((type === 'single' || type === 'multi') && q.options.length < 2) {
    q.options = [...q.options, '', ''].slice(0, Math.max(2, q.options.length))
  }
}

function validate() {
  const d = draft.value
  if (!d.title.trim()) return 'Назовите анкету'
  if (!d.questions.length) return 'Добавьте хотя бы один вопрос'
  for (const [i, q] of d.questions.entries()) {
    if (!q.title.trim()) return `Напишите текст вопроса ${i + 1}`
    if (q.type === 'single' || q.type === 'multi') {
      const options = q.options.map((o) => o.trim()).filter(Boolean)
      if (options.length < 2) return `В вопросе ${i + 1} нужно хотя бы два варианта`
      if (new Set(options).size !== options.length) return `В вопросе ${i + 1} варианты повторяются`
    }
  }
  return ''
}

function payload() {
  const d = draft.value
  return {
    title: d.title.trim(),
    description: d.description.trim(),
    questions: d.questions.map((q) => ({
      id: q.id,
      type: q.type,
      title: q.title.trim(),
      hint: q.hint.trim(),
      required: q.required,
      options: q.type === 'single' || q.type === 'multi' ? q.options.map((o) => o.trim()).filter(Boolean) : [],
      max: q.max,
    })),
  }
}

async function save() {
  saveError.value = validate()
  saveNotice.value = ''
  if (saveError.value) return
  isSaving.value = true
  try {
    if (isNew.value) {
      const created = await createSurvey(payload())
      survey.value = created
      fromSurvey(created)
      router.replace({ name: 'survey-manage', params: { id: created.id } })
      saveNotice.value = 'Анкета сохранена — теперь выберите, кому отправить'
      tab.value = 'send'
    } else {
      survey.value = await updateSurvey(survey.value.id, payload())
      fromSurvey(survey.value)
      saveNotice.value = 'Сохранено'
    }
  } catch (err) {
    saveError.value = apiError(err, 'Не удалось сохранить')
  } finally {
    isSaving.value = false
  }
}

async function removeSurvey() {
  if (!window.confirm(`Удалить анкету «${survey.value.title}» вместе со всеми ответами?`)) return
  try {
    await deleteSurvey(survey.value.id)
    router.push({ name: 'surveys' })
  } catch (err) {
    saveError.value = apiError(err, 'Не удалось удалить')
  }
}

// ── Отправка ──
const users = ref([])
const directions = ref([])
const picked = ref(new Set())
const search = ref('')
const isSending = ref(false)
const sendError = ref('')
const sendNotice = ref('')

const alreadySent = computed(() => new Set((survey.value?.recipients ?? []).map((r) => r.user_id)))

const visibleUsers = computed(() => {
  const q = search.value.trim().toLowerCase().replace(/^@/, '')
  const list = users.value.filter((u) => u.is_active)
  if (!q) return list
  return list.filter(
    (u) => u.full_name.toLowerCase().includes(q) || (u.telegram_username ?? '').toLowerCase().includes(q),
  )
})

const pickedCount = computed(() => [...picked.value].filter((id) => !alreadySent.value.has(id)).length)

function toggleUser(id) {
  if (alreadySent.value.has(id)) return
  const next = new Set(picked.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  picked.value = next
}

function pickWhere(test) {
  const next = new Set(picked.value)
  for (const u of users.value) {
    if (u.is_active && test(u) && !alreadySent.value.has(u.id)) next.add(u.id)
  }
  picked.value = next
}

function directionCodes(u) {
  return directions.value.filter((d) => u.direction_ids.includes(d.id)).map((d) => d.short_code)
}

async function loadPeople() {
  if (users.value.length) return
  const [usersData, directionsData] = await Promise.all([fetchUsers(), fetchDirections()])
  users.value = usersData.sort((a, b) => a.full_name.localeCompare(b.full_name, 'ru'))
  directions.value = directionsData
}

async function send() {
  const ids = [...picked.value].filter((id) => !alreadySent.value.has(id))
  if (!ids.length) return
  const n = ids.length
  if (!window.confirm(`Отправить анкету ${n} ${plural(n, 'человеку', 'людям', 'людям')}? Им придёт сообщение от бота.`)) return
  isSending.value = true
  sendError.value = ''
  sendNotice.value = ''
  try {
    const result = await sendSurvey(survey.value.id, ids)
    picked.value = new Set()
    survey.value = await fetchSurvey(survey.value.id)
    sendNotice.value =
      `Отправили ${result.added} ${plural(result.added, 'человеку', 'людям', 'людям')}` +
      (result.without_telegram
        ? `. Без Telegram — ${result.without_telegram}: увидят анкету только в трекере, в разделе «Анкеты»`
        : '')
  } catch (err) {
    sendError.value = apiError(err, 'Не удалось отправить')
  } finally {
    isSending.value = false
  }
}

// ── Ответы ──
const answersError = ref('')
const answersNotice = ref('')
const openPerson = ref(null)

const recipients = computed(() => survey.value?.recipients ?? [])
const answered = computed(() => recipients.value.filter((r) => r.answers))
const waiting = computed(() => recipients.value.filter((r) => !r.answers))

// Сводка по вопросу: для вариантов — сколько выбрали, для шкалы — среднее, для текста — сами ответы.
function stats(q) {
  const values = answered.value.map((r) => r.answers[q.id]).filter((v) => v != null)
  if (q.type === 'single' || q.type === 'multi') {
    const counts = Object.fromEntries(q.options.map((o) => [o, 0]))
    for (const v of values) for (const o of Array.isArray(v) ? v : [v]) if (o in counts) counts[o] += 1
    const max = Math.max(1, ...Object.values(counts))
    return { kind: 'bars', total: values.length, rows: q.options.map((o) => ({ label: o, count: counts[o], share: counts[o] / max })) }
  }
  if (q.type === 'scale') {
    const counts = Array.from({ length: q.max }, (_, i) => values.filter((v) => v === i + 1).length)
    const avg = values.length ? values.reduce((a, b) => a + b, 0) / values.length : null
    const max = Math.max(1, ...counts)
    return { kind: 'scale', total: values.length, avg, rows: counts.map((c, i) => ({ label: String(i + 1), count: c, share: c / max })) }
  }
  return {
    kind: 'text',
    total: values.length,
    rows: answered.value.filter((r) => r.answers[q.id]).map((r) => ({ name: r.full_name, text: r.answers[q.id] })),
  }
}

async function remind() {
  answersError.value = ''
  answersNotice.value = ''
  try {
    const { reminded } = await remindSurvey(survey.value.id)
    answersNotice.value = `Напомнили ${reminded} ${plural(reminded, 'человеку', 'людям', 'людям')}`
    survey.value = await fetchSurvey(survey.value.id)
  } catch (err) {
    answersError.value = apiError(err, 'Не удалось напомнить')
  }
}

async function toggleStatus() {
  const next = survey.value.status === 'open' ? 'closed' : 'open'
  if (next === 'closed' && !window.confirm('Закрыть анкету? Ответы перестанут приниматься — открыть снова можно в любой момент.')) return
  answersError.value = ''
  try {
    survey.value = await setSurveyStatus(survey.value.id, next)
  } catch (err) {
    answersError.value = apiError(err, 'Не удалось сменить статус')
  }
}

function csvCell(value) {
  const s = String(value ?? '')
  return /[";\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

// CSV через «;» и с BOM — Excel открывает кириллицу и колонки без настройки.
function exportCsv() {
  const qs = survey.value.questions
  const head = ['ФИО', 'Telegram', 'Ответ получен', ...qs.map((q) => q.title)]
  const lines = recipients.value.map((r) => [
    r.full_name,
    r.telegram_username ? `@${r.telegram_username.replace(/^@/, '')}` : '',
    r.submitted_at ? formatWhen(r.submitted_at) : 'нет',
    ...qs.map((q) => answerText(q, r.answers?.[q.id])),
  ])
  const csv = [head, ...lines].map((row) => row.map(csvCell).join(';')).join('\r\n')
  const blob = new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `${survey.value.title.replace(/[\\/:*?"<>|]+/g, ' ').trim() || 'анкета'}.csv`
  link.click()
  URL.revokeObjectURL(link.href)
}

// ── Загрузка ──
async function load() {
  isLoading.value = true
  loadError.value = ''
  try {
    if (route.params.id) {
      survey.value = await fetchSurvey(route.params.id)
      fromSurvey(survey.value)
      tab.value = survey.value.status === 'draft' ? 'questions' : 'answers'
    } else {
      survey.value = null
      draft.value = { title: '', description: '', questions: [blankQuestion('text')] }
      tab.value = 'questions'
    }
  } catch {
    loadError.value = 'Анкета не найдена'
  } finally {
    isLoading.value = false
  }
}

onMounted(load)

watch(tab, async (value) => {
  if (value !== 'send') return
  try {
    await loadPeople()
  } catch {
    sendError.value = 'Не удалось загрузить список людей'
  }
})
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="manage">
        <button class="back" @click="router.push({ name: 'surveys' })">
          <BaseIcon name="chevron-left" :size="14" /> Анкеты
        </button>

        <AppLoader v-if="isLoading" />
        <p v-else-if="loadError" class="form-error">{{ loadError }}</p>

        <template v-else>
          <div class="head">
            <div class="head__text">
              <h1>{{ isNew ? 'Новая анкета' : survey.title }}</h1>
              <p v-if="!isNew" class="subtitle">
                <span class="state" :class="`state--${survey.status}`">{{ STATUS_LABELS[survey.status] }}</span>
                Ответили {{ answered.length }} из {{ recipients.length }}
              </p>
            </div>
            <button
              v-if="!isNew"
              class="ghost"
              @click="router.push({ name: 'survey-fill', params: { id: survey.id } })"
            >
              Предпросмотр
            </button>
          </div>

          <nav v-if="!isNew" class="tabs" aria-label="Разделы анкеты">
            <button :class="{ 'tabs__on': tab === 'questions' }" @click="tab = 'questions'">Вопросы</button>
            <button :class="{ 'tabs__on': tab === 'send' }" @click="tab = 'send'">Отправить</button>
            <button :class="{ 'tabs__on': tab === 'answers' }" @click="tab = 'answers'">
              Ответы <span class="tabs__count">{{ answered.length }}</span>
            </button>
          </nav>

          <!-- ── Вопросы ── -->
          <section v-if="tab === 'questions'" class="pane">
            <div class="card meta">
              <label class="field">
                <span class="field__label">Название</span>
                <input v-model="draft.title" class="field__input" maxlength="200" placeholder="Например: Данные для мерча" />
              </label>
              <label class="field">
                <span class="field__label">Описание (необязательно)</span>
                <textarea
                  v-model="draft.description"
                  class="field__input field__area"
                  rows="3"
                  maxlength="2000"
                  placeholder="Зачем анкета и до какого числа ответить"
                />
              </label>
            </div>

            <p v-if="locked" class="banner">На анкету уже ответили — вопросы менять нельзя, только название и описание.</p>

            <article v-for="(q, i) in draft.questions" :key="q.id" class="card q">
              <div class="q__head">
                <span class="q__num">{{ i + 1 }}</span>
                <select
                  :value="q.type"
                  class="field__input q__type"
                  :disabled="locked"
                  aria-label="Тип вопроса"
                  @change="changeType(q, $event.target.value)"
                >
                  <option v-for="t in QUESTION_TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
                </select>
                <div class="q__tools">
                  <button type="button" class="icon-btn" :disabled="locked || i === 0" aria-label="Выше" @click="moveQuestion(i, -1)">
                    <BaseIcon name="chevron-left" :size="14" class="icon-up" />
                  </button>
                  <button
                    type="button"
                    class="icon-btn"
                    :disabled="locked || i === draft.questions.length - 1"
                    aria-label="Ниже"
                    @click="moveQuestion(i, 1)"
                  >
                    <BaseIcon name="chevron-left" :size="14" class="icon-down" />
                  </button>
                  <button
                    type="button"
                    class="icon-btn icon-btn--danger"
                    :disabled="locked || draft.questions.length === 1"
                    aria-label="Удалить вопрос"
                    @click="removeQuestion(i)"
                  >
                    <BaseIcon name="trash" :size="14" />
                  </button>
                </div>
              </div>

              <input v-model="q.title" class="field__input" maxlength="300" placeholder="Текст вопроса" :disabled="locked" />
              <input v-model="q.hint" class="field__input field__input--soft" maxlength="300" placeholder="Подсказка (необязательно)" :disabled="locked" />

              <div v-if="q.type === 'single' || q.type === 'multi'" class="opts">
                <div v-for="(o, j) in q.options" :key="j" class="opts__row">
                  <span class="opts__mark" :class="{ 'opts__mark--multi': q.type === 'multi' }" />
                  <input v-model="q.options[j]" class="field__input" maxlength="200" :placeholder="`Вариант ${j + 1}`" :disabled="locked" />
                  <button
                    type="button"
                    class="icon-btn icon-btn--danger"
                    :disabled="locked || q.options.length <= 2"
                    aria-label="Убрать вариант"
                    @click="q.options.splice(j, 1)"
                  >
                    <BaseIcon name="trash" :size="14" />
                  </button>
                </div>
                <button v-if="!locked && q.options.length < 30" type="button" class="link-btn" @click="q.options.push('')">
                  <BaseIcon name="plus" :size="14" /> Добавить вариант
                </button>
              </div>

              <label v-if="q.type === 'scale'" class="scale-max">
                Шкала от 1 до
                <select v-model.number="q.max" class="field__input" :disabled="locked">
                  <option v-for="n in [3, 4, 5, 6, 7, 8, 9, 10]" :key="n" :value="n">{{ n }}</option>
                </select>
              </label>

              <label class="check">
                <input v-model="q.required" type="checkbox" :disabled="locked" />
                Обязательный вопрос
              </label>
            </article>

            <button v-if="!locked && draft.questions.length < 50" type="button" class="ghost add-q" @click="addQuestion">
              <BaseIcon name="plus" :size="14" /> Добавить вопрос
            </button>

            <p v-if="saveError" class="form-error">{{ saveError }}</p>
            <p v-if="saveNotice" class="form-notice">{{ saveNotice }}</p>

            <div class="actions">
              <button v-if="!isNew" type="button" class="ghost ghost--danger" @click="removeSurvey">Удалить анкету</button>
              <button class="create-btn" :disabled="isSaving" @click="save">
                {{ isSaving ? 'Сохраняем…' : isNew ? 'Сохранить и выбрать получателей' : 'Сохранить' }}
              </button>
            </div>
          </section>

          <!-- ── Отправка ── -->
          <section v-else-if="tab === 'send'" class="pane">
            <p v-if="survey.status === 'closed'" class="banner">Анкета закрыта — откройте её на вкладке «Ответы», чтобы отправить ещё.</p>

            <div class="card picker">
              <div class="quick">
                <button type="button" class="chip" @click="pickWhere((u) => u.is_activist)">Весь актив</button>
                <button
                  v-for="d in directions"
                  :key="d.id"
                  type="button"
                  class="chip"
                  @click="pickWhere((u) => u.direction_ids.includes(d.id))"
                >
                  + {{ d.short_code }}
                </button>
                <button type="button" class="chip" @click="pickWhere(() => true)">Все</button>
                <button v-if="picked.size" type="button" class="chip chip--muted" @click="picked = new Set()">Снять выбор</button>
              </div>

              <input v-model="search" class="field__input" placeholder="Поиск по ФИО или @тегу" />

              <AppLoader v-if="!users.length && !sendError" />
              <ul v-else class="people">
                <li v-for="u in visibleUsers" :key="u.id">
                  <label class="person" :class="{ 'person--sent': alreadySent.has(u.id) }">
                    <input
                      type="checkbox"
                      :checked="alreadySent.has(u.id) || picked.has(u.id)"
                      :disabled="alreadySent.has(u.id)"
                      @change="toggleUser(u.id)"
                    />
                    <span class="person__main">
                      <span class="person__name">{{ u.full_name }}</span>
                      <span class="person__meta">
                        <template v-if="u.telegram_username">@{{ u.telegram_username.replace(/^@/, '') }}</template>
                        <span v-for="code in directionCodes(u)" :key="code" class="dir-code">{{ code }}</span>
                        <span v-if="!u.is_activist" class="muted">не в активе</span>
                        <span v-if="!u.telegram_linked" class="warn-text">без Telegram</span>
                      </span>
                    </span>
                    <span v-if="alreadySent.has(u.id)" class="person__sent">отправлено</span>
                  </label>
                </li>
              </ul>
            </div>

            <p v-if="sendError" class="form-error">{{ sendError }}</p>
            <p v-if="sendNotice" class="form-notice">{{ sendNotice }}</p>

            <div class="actions actions--sticky">
              <span class="muted">Уже получили: {{ alreadySent.size }}</span>
              <button class="create-btn" :disabled="isSending || !pickedCount || survey.status === 'closed'" @click="send">
                <BaseIcon name="send" :size="14" />
                {{ isSending ? 'Отправляем…' : `Отправить (${pickedCount})` }}
              </button>
            </div>
          </section>

          <!-- ── Ответы ── -->
          <section v-else class="pane">
            <div class="toolbar">
              <button class="ghost" :disabled="survey.status !== 'open' || !waiting.length" @click="remind">
                <BaseIcon name="bell" :size="14" /> Напомнить не ответившим ({{ waiting.length }})
              </button>
              <button class="ghost" :disabled="survey.status === 'draft'" @click="toggleStatus">
                {{ survey.status === 'closed' ? 'Открыть снова' : 'Закрыть приём' }}
              </button>
              <button class="ghost" :disabled="!recipients.length" @click="exportCsv">Скачать CSV</button>
            </div>
            <p v-if="survey.reminded_at" class="muted small">Последнее напоминание: {{ formatWhen(survey.reminded_at) }}</p>
            <p v-if="answersError" class="form-error">{{ answersError }}</p>
            <p v-if="answersNotice" class="form-notice">{{ answersNotice }}</p>

            <p v-if="!recipients.length" class="empty">Анкету ещё никому не отправили — это на вкладке «Отправить».</p>

            <template v-else>
              <article v-for="(q, i) in survey.questions" :key="q.id" class="card stat">
                <p class="stat__title"><span class="q__num">{{ i + 1 }}</span>{{ q.title }}</p>
                <template v-for="s in [stats(q)]" :key="'s'">
                  <p class="stat__meta">
                    {{ s.total }} {{ plural(s.total, 'ответ', 'ответа', 'ответов') }}
                    <template v-if="s.kind === 'scale' && s.avg != null"> · среднее {{ s.avg.toFixed(1) }} из {{ q.max }}</template>
                  </p>
                  <ul v-if="s.kind !== 'text'" class="bars">
                    <li v-for="row in s.rows" :key="row.label" class="bars__row">
                      <span class="bars__label">{{ row.label }}</span>
                      <span class="bars__track"><span class="bars__fill" :style="{ width: `${row.share * 100}%` }" /></span>
                      <span class="bars__count">{{ row.count }}</span>
                    </li>
                  </ul>
                  <ul v-else-if="s.rows.length" class="texts">
                    <li v-for="row in s.rows" :key="row.name">
                      <span class="texts__name">{{ row.name }}</span>
                      <span class="texts__text">{{ row.text }}</span>
                    </li>
                  </ul>
                </template>
              </article>

              <article class="card">
                <p class="stat__title">Люди</p>
                <ul class="who">
                  <li v-for="r in [...answered, ...waiting]" :key="r.user_id">
                    <button
                      class="who__row"
                      :disabled="!r.answers"
                      :aria-expanded="openPerson === r.user_id"
                      @click="openPerson = openPerson === r.user_id ? null : r.user_id"
                    >
                      <span class="who__name">{{ r.full_name }}</span>
                      <span v-if="!r.telegram_linked" class="warn-text">без Telegram</span>
                      <span class="state" :class="r.answers ? 'state--done' : 'state--wait'">
                        {{ r.answers ? `ответ ${formatWhen(r.submitted_at)}` : 'ждём' }}
                      </span>
                    </button>
                    <dl v-if="openPerson === r.user_id && r.answers" class="who__answers">
                      <div v-for="q in survey.questions" :key="q.id">
                        <dt>{{ q.title }}</dt>
                        <dd>{{ answerText(q, r.answers[q.id]) || '—' }}</dd>
                      </div>
                    </dl>
                  </li>
                </ul>
              </article>
            </template>
          </section>
        </template>
      </div>
    </main>
  </div>
</template>

<style scoped>
.manage {
  max-width: 820px;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.back {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0;
  border: none;
  background: none;
  color: var(--text-muted);
  font-size: 13px;
}

.back:hover {
  color: var(--text);
}

.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.head__text {
  min-width: 0;
}

.head h1 {
  margin: 0;
  overflow-wrap: anywhere;
}

.head .subtitle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: var(--space-2) 0 0;
}

.tabs {
  display: flex;
  gap: var(--space-1);
  border-bottom: 1px solid var(--border);
}

.tabs button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: var(--space-2) var(--space-3);
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  background: none;
  color: var(--text-muted);
  font-size: 14px;
}

.tabs button.tabs__on {
  color: var(--text);
  border-bottom-color: var(--accent);
}

.tabs__count {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-faint);
}

.pane {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
}

.meta,
.q,
.picker {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.banner {
  margin: 0;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--accent-soft);
  font-size: 13px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field__label {
  font-size: 13px;
  color: var(--text-muted);
}

.field__input {
  width: 100%;
  min-width: 0;
  height: var(--control-h);
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
  color: var(--text);
  font: inherit;
  font-size: 14px;
  box-sizing: border-box;
}

.field__input:focus {
  outline: none;
  border-color: var(--accent);
}

.field__input:disabled {
  opacity: 0.7;
}

.field__input--soft {
  font-size: 13px;
  color: var(--text-muted);
}

.field__area {
  height: auto;
  padding: 10px 12px;
  resize: vertical;
  line-height: 21px;
}

.q__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.q__num {
  display: inline-block;
  min-width: 22px;
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-faint);
}

.q__type {
  flex: 1;
  max-width: 240px;
}

.q__tools {
  display: flex;
  gap: var(--space-1);
  margin-left: auto;
}

.icon-btn {
  width: var(--control-h);
  height: var(--control-h);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-muted);
}

.icon-btn:disabled {
  opacity: 0.4;
}

.icon-btn--danger:hover:not(:disabled) {
  color: var(--danger);
}

.icon-up {
  transform: rotate(90deg);
}

.icon-down {
  transform: rotate(-90deg);
}

.opts {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.opts__row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.opts__mark {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  border: 1.5px solid var(--border-strong);
  border-radius: var(--radius-full);
}

.opts__mark--multi {
  border-radius: 3px;
}

.link-btn {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0;
  border: none;
  background: none;
  color: var(--accent);
  font-size: 13px;
}

.scale-max {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 13px;
  color: var(--text-muted);
}

.scale-max .field__input {
  width: 80px;
}

.check {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 13px;
  color: var(--text-muted);
}

.check input {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: var(--accent);
}

.ghost {
  height: var(--control-h);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 14px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text);
  font-size: 14px;
  white-space: nowrap;
}

.ghost:hover:not(:disabled) {
  background: var(--surface-hover);
}

.ghost:disabled {
  opacity: 0.5;
}

.ghost--danger {
  color: var(--danger);
  margin-right: auto;
}

.add-q {
  align-self: flex-start;
}

.actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-2);
}

.actions .create-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.actions--sticky {
  justify-content: space-between;
}

.form-error {
  margin: 0;
  font-size: 13px;
  color: var(--danger);
}

.form-notice {
  margin: 0;
  font-size: 13px;
  color: var(--success);
}

.muted {
  color: var(--text-muted);
  font-size: 13px;
}

.small {
  margin: 0;
  font-size: 12px;
}

.empty {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.warn-text {
  font-size: 12px;
  color: var(--prio-medium);
}

/* Выбор получателей */
.quick {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.chip {
  height: 30px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  background: var(--surface-raised);
  color: var(--text);
  font-size: 13px;
}

.chip:hover {
  border-color: var(--accent);
}

.chip--muted {
  color: var(--text-muted);
  background: transparent;
}

.people {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 460px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.people li + li {
  border-top: 1px solid var(--border);
}

.person {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
}

.person:hover {
  background: var(--surface-hover);
}

.person input {
  width: 18px;
  height: 18px;
  margin: 0;
  flex-shrink: 0;
  accent-color: var(--accent);
}

.person--sent {
  cursor: default;
  opacity: 0.6;
}

.person__main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.person__name {
  font-size: 14px;
}

.person__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
}

.person__sent {
  font-size: 12px;
  color: var(--success);
  white-space: nowrap;
}

.dir-code {
  font-size: 11px;
  background: var(--surface-raised);
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  padding: 0 6px;
}

/* Ответы */
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.stat {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.stat__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.stat__meta {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.bars {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.bars__row {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 3fr) 32px;
  align-items: center;
  gap: var(--space-2);
  font-size: 13px;
}

.bars__label {
  overflow-wrap: anywhere;
}

.bars__track {
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--border);
  overflow: hidden;
}

.bars__fill {
  display: block;
  height: 100%;
  border-radius: var(--radius-full);
  background: var(--accent);
}

.bars__count {
  font-family: var(--font-mono);
  font-size: 12px;
  text-align: right;
  color: var(--text-muted);
}

.texts {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  max-height: 320px;
  overflow-y: auto;
}

.texts li {
  display: flex;
  flex-direction: column;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface-raised);
}

.texts__name {
  font-size: 12px;
  color: var(--text-muted);
}

.texts__text {
  font-size: 14px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.who {
  list-style: none;
  margin: var(--space-2) 0 0;
  padding: 0;
}

.who li + li {
  border-top: 1px solid var(--border);
}

.who__row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) 0;
  border: none;
  background: none;
  color: var(--text);
  font: inherit;
  text-align: left;
}

.who__row:not(:disabled) {
  cursor: pointer;
}

.who__name {
  flex: 1;
  min-width: 0;
  font-size: 14px;
}

.who__answers {
  margin: 0 0 var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface-raised);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.who__answers dt {
  font-size: 12px;
  color: var(--text-muted);
}

.who__answers dd {
  margin: 0;
  font-size: 13px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.state {
  flex-shrink: 0;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  white-space: nowrap;
}

.state--wait,
.state--open {
  background: var(--accent-soft);
  color: var(--accent);
}

.state--done {
  background: color-mix(in srgb, var(--success) 20%, transparent);
  color: var(--success);
}

.state--closed,
.state--draft {
  background: var(--surface-raised);
  color: var(--text-muted);
}

@media (max-width: 768px) {
  .card {
    padding: var(--space-3);
  }

  .head {
    flex-direction: column;
  }

  .field__input,
  .ghost,
  .icon-btn {
    height: var(--control-h-touch);
  }

  .field__area {
    height: auto;
  }

  .icon-btn {
    width: var(--control-h-touch);
  }

  .q__head {
    flex-wrap: wrap;
  }

  .q__type {
    max-width: none;
  }

  .tabs {
    overflow-x: auto;
  }

  .tabs button {
    flex-shrink: 0;
  }

  .toolbar .ghost {
    flex: 1 1 100%;
  }

  .actions {
    flex-direction: column-reverse;
    align-items: stretch;
  }

  .actions .create-btn {
    height: var(--control-h-touch);
    justify-content: center;
  }

  .ghost--danger {
    margin-right: 0;
  }

  /* На телефоне список длинный — кнопка отправки всегда под рукой, над таб-баром. */
  .actions--sticky {
    position: sticky;
    bottom: calc(76px + env(safe-area-inset-bottom));
    padding: var(--space-2);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: var(--surface);
  }

  .people {
    max-height: none;
  }

  .bars__row {
    grid-template-columns: minmax(0, 1fr) 80px 28px;
  }
}
</style>
