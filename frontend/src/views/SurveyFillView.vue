<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import BaseIcon from '../components/BaseIcon.vue'
import { fetchSurveyToFill, submitSurveyResponse } from '../api/surveys'
import { apiError, formatWhen } from '../utils/surveys'

const route = useRoute()
const router = useRouter()

const survey = ref(null)
const isLoading = ref(true)
const loadError = ref('')
const answers = ref({})
const isSaving = ref(false)
const error = ref('')
const editing = ref(false)
// id вопроса, на который не ответили — подсвечиваем.
const missingId = ref(null)

// Админ, которому анкету не присылали, видит её как предпросмотр.
const isPreview = computed(() => survey.value && !survey.value.sent_at)
const isClosed = computed(() => survey.value?.status === 'closed')
const showForm = computed(() => survey.value && (!survey.value.answers || editing.value) && !isClosed.value)

function fillFrom(saved) {
  const next = {}
  for (const q of survey.value.questions) {
    const value = saved?.[q.id]
    next[q.id] = q.type === 'multi' ? [...(value ?? [])] : (value ?? (q.type === 'scale' || q.type === 'single' ? null : ''))
  }
  answers.value = next
}

async function load() {
  try {
    survey.value = await fetchSurveyToFill(route.params.id)
    fillFrom(survey.value.answers)
  } catch (err) {
    loadError.value = err.response?.status === 404 ? 'Анкета не найдена или прислана не вам' : 'Не удалось загрузить анкету'
  } finally {
    isLoading.value = false
  }
}

onMounted(load)

function isEmpty(q) {
  const value = answers.value[q.id]
  if (q.type === 'multi') return !value.length
  if (q.type === 'text' || q.type === 'textarea') return !String(value ?? '').trim()
  return value == null
}

async function submit() {
  error.value = ''
  missingId.value = null
  const missing = survey.value.questions.find((q) => q.required && isEmpty(q))
  if (missing) {
    missingId.value = missing.id
    error.value = `Ответьте на вопрос «${missing.title}»`
    document.getElementById(`q-${missing.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    return
  }
  isSaving.value = true
  try {
    survey.value = await submitSurveyResponse(survey.value.id, answers.value)
    editing.value = false
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (err) {
    error.value = apiError(err, 'Не удалось отправить ответ')
  } finally {
    isSaving.value = false
  }
}

function startEdit() {
  fillFrom(survey.value.answers)
  editing.value = true
}

function toggleMulti(q, option) {
  const list = answers.value[q.id]
  const i = list.indexOf(option)
  if (i === -1) list.push(option)
  else list.splice(i, 1)
}

function savedAnswer(q) {
  const value = survey.value.answers?.[q.id]
  if (value == null) return '—'
  if (Array.isArray(value)) return value.join(', ')
  if (q.type === 'scale') return `${value} из ${q.max}`
  return value
}
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="fill">
        <button class="back" @click="router.push({ name: 'surveys' })">
          <BaseIcon name="chevron-left" :size="14" /> Анкеты
        </button>

        <AppLoader v-if="isLoading" />
        <p v-else-if="loadError" class="form-error">{{ loadError }}</p>

        <template v-else-if="survey">
          <header class="intro">
            <h1>{{ survey.title }}</h1>
            <p v-if="survey.description" class="intro__text">{{ survey.description }}</p>
          </header>

          <p v-if="isPreview" class="banner">Предпросмотр: так анкету увидят получатели. Ответить может только тот, кому её отправили.</p>
          <p v-else-if="isClosed && !survey.answers" class="banner">Анкета закрыта — ответы больше не принимаются.</p>

          <!-- Уже ответил: сводка ответов -->
          <section v-if="survey.answers && !editing" class="card done">
            <div class="done__head">
              <span class="done__icon"><BaseIcon name="check" :size="16" /></span>
              <div>
                <p class="done__title">Спасибо, ответ отправлен</p>
                <p class="done__meta">{{ formatWhen(survey.submitted_at) }}</p>
              </div>
            </div>
            <dl class="done__list">
              <div v-for="q in survey.questions" :key="q.id">
                <dt>{{ q.title }}</dt>
                <dd>{{ savedAnswer(q) }}</dd>
              </div>
            </dl>
            <button v-if="!isClosed" class="ghost" @click="startEdit">Изменить ответ</button>
          </section>

          <form v-if="showForm" class="questions" novalidate @submit.prevent="submit">
            <fieldset
              v-for="(q, i) in survey.questions"
              :id="`q-${q.id}`"
              :key="q.id"
              class="card question"
              :class="{ 'question--missing': missingId === q.id }"
            >
              <legend class="question__title">
                <span class="question__num">{{ i + 1 }}</span>
                {{ q.title }}
                <span v-if="q.required" class="question__req" aria-label="обязательный">*</span>
              </legend>
              <p v-if="q.hint" class="question__hint">{{ q.hint }}</p>

              <input
                v-if="q.type === 'text'"
                v-model="answers[q.id]"
                class="field__input"
                maxlength="4000"
                :aria-label="q.title"
              />
              <textarea
                v-else-if="q.type === 'textarea'"
                v-model="answers[q.id]"
                class="field__input field__area"
                rows="4"
                maxlength="4000"
                :aria-label="q.title"
              />
              <div v-else-if="q.type === 'single'" class="options">
                <label v-for="o in q.options" :key="o" class="option" :class="{ 'option--on': answers[q.id] === o }">
                  <input v-model="answers[q.id]" type="radio" :name="q.id" :value="o" />
                  <span>{{ o }}</span>
                </label>
              </div>
              <div v-else-if="q.type === 'multi'" class="options">
                <label v-for="o in q.options" :key="o" class="option" :class="{ 'option--on': answers[q.id].includes(o) }">
                  <input type="checkbox" :checked="answers[q.id].includes(o)" @change="toggleMulti(q, o)" />
                  <span>{{ o }}</span>
                </label>
              </div>
              <div v-else-if="q.type === 'scale'" class="scale" role="radiogroup" :aria-label="q.title">
                <button
                  v-for="n in q.max"
                  :key="n"
                  type="button"
                  class="scale__btn"
                  :class="{ 'scale__btn--on': answers[q.id] === n }"
                  :aria-pressed="answers[q.id] === n"
                  @click="answers[q.id] = answers[q.id] === n ? null : n"
                >
                  {{ n }}
                </button>
              </div>
            </fieldset>

            <p v-if="error" class="form-error">{{ error }}</p>
            <div class="actions">
              <button v-if="editing" type="button" class="ghost" @click="editing = false">Отмена</button>
              <button type="submit" class="create-btn" :disabled="isSaving || isPreview">
                <BaseIcon name="send" :size="14" />
                {{ isSaving ? 'Отправляем…' : 'Отправить ответ' }}
              </button>
            </div>
          </form>
        </template>
      </div>
    </main>
  </div>
</template>

<style scoped>
.fill {
  max-width: 680px;
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

.intro h1 {
  margin: 0;
  overflow-wrap: anywhere;
}

.intro__text {
  margin: var(--space-2) 0 0;
  font-size: 14px;
  line-height: 21px;
  color: var(--text-muted);
  white-space: pre-wrap;
}

.banner {
  margin: 0;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--accent-soft);
  color: var(--text);
  font-size: 13px;
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
}

.questions {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.question {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-width: 0;
}

.question--missing {
  border-color: var(--danger);
}

.question__title {
  float: left;
  width: 100%;
  padding: 0;
  font-size: 15px;
  font-weight: 600;
  line-height: 22px;
  overflow-wrap: anywhere;
}

.question__title + * {
  clear: both;
}

.question__num {
  display: inline-block;
  min-width: 20px;
  margin-right: 4px;
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-faint);
}

.question__req {
  color: var(--danger);
}

.question__hint {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.field__input {
  width: 100%;
  min-width: 0;
  height: var(--control-h-touch);
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
  color: var(--text);
  font: inherit;
  font-size: 15px;
  box-sizing: border-box;
}

.field__input:focus {
  outline: none;
  border-color: var(--accent);
}

.field__area {
  height: auto;
  padding: 10px 12px;
  resize: vertical;
  line-height: 21px;
}

.options {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.option {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-height: var(--control-h-touch);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 14px;
  cursor: pointer;
}

.option input {
  width: 18px;
  height: 18px;
  margin: 0;
  flex-shrink: 0;
  accent-color: var(--accent);
}

.option--on {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.scale {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.scale__btn {
  width: var(--control-h-touch);
  height: var(--control-h-touch);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text);
  font-family: var(--font-mono);
  font-size: 15px;
}

.scale__btn--on {
  border-color: var(--accent);
  background: var(--accent);
  color: #fff;
}

.done {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.done__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.done__icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full);
  background: color-mix(in srgb, var(--success) 20%, transparent);
  color: var(--success);
}

.done__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.done__meta {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.done__list {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.done__list dt {
  font-size: 12px;
  color: var(--text-muted);
}

.done__list dd {
  margin: 2px 0 0;
  font-size: 14px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
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
}

.done .ghost {
  align-self: flex-start;
}

.ghost:hover:not(:disabled) {
  background: var(--surface-hover);
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}

.actions .create-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.form-error {
  margin: 0;
  font-size: 13px;
  color: var(--danger);
}

@media (max-width: 768px) {
  .actions {
    flex-direction: column-reverse;
  }

  .actions > *,
  .ghost {
    width: 100%;
    height: var(--control-h-touch);
    justify-content: center;
  }
}
</style>
