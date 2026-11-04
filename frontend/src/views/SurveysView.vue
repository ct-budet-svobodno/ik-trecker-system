<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import BaseIcon from '../components/BaseIcon.vue'
import { fetchMySurveys, fetchSurveys } from '../api/surveys'
import { useAuthStore } from '../stores/auth'
import { STATUS_LABELS, formatWhen, plural } from '../utils/surveys'

const authStore = useAuthStore()
const router = useRouter()

const mine = ref([])
const all = ref([])
const isLoading = ref(true)
const error = ref('')

async function load() {
  try {
    const [mineData, allData] = await Promise.all([
      fetchMySurveys(),
      authStore.isAdmin ? fetchSurveys() : Promise.resolve([]),
    ])
    mine.value = mineData
    all.value = allData
  } catch {
    error.value = 'Не удалось загрузить анкеты'
  } finally {
    isLoading.value = false
  }
}

onMounted(load)

function myState(s) {
  if (s.answers) return { label: 'Ответ отправлен', cls: 'state--done' }
  if (s.status === 'closed') return { label: 'Закрыта', cls: 'state--off' }
  return { label: 'Ждёт ответа', cls: 'state--wait' }
}
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="surveys">
        <div class="head">
          <div>
            <p class="breadcrumb">ИК · Трекер / Анкеты</p>
            <h1>Анкеты</h1>
            <p class="subtitle">
              {{ authStore.isAdmin ? 'Соберите опрос и отправьте его нужным людям — ответы соберутся здесь.' : 'Опросы, которые вам прислали.' }}
            </p>
          </div>
          <button v-if="authStore.isAdmin" class="create-btn" @click="router.push({ name: 'survey-new' })">
            <BaseIcon name="plus" :size="14" /> Новая анкета
          </button>
        </div>

        <AppLoader v-if="isLoading" />
        <p v-else-if="error" class="form-error">{{ error }}</p>

        <template v-else>
          <section v-if="!authStore.isAdmin || mine.length" class="block">
            <h2 class="block__title">Мне прислали</h2>
            <p v-if="!mine.length" class="empty">Пока анкет нет — когда пришлют, они появятся здесь и в боте.</p>
            <button
              v-for="s in mine"
              :key="s.id"
              class="card row"
              @click="router.push({ name: 'survey-fill', params: { id: s.id } })"
            >
              <span class="row__main">
                <span class="row__title">{{ s.title }}</span>
                <span class="row__meta">
                  {{ s.questions.length }} {{ plural(s.questions.length, 'вопрос', 'вопроса', 'вопросов') }}
                  <template v-if="s.sent_at"> · прислали {{ formatWhen(s.sent_at) }}</template>
                </span>
              </span>
              <span class="state" :class="myState(s).cls">{{ myState(s).label }}</span>
              <BaseIcon name="chevron-right" :size="16" class="row__chevron" />
            </button>
          </section>

          <section v-if="authStore.isAdmin" class="block">
            <h2 class="block__title">Все анкеты</h2>
            <p v-if="!all.length" class="empty">Анкет ещё нет. Нажмите «Новая анкета», чтобы собрать первую.</p>
            <button
              v-for="s in all"
              :key="s.id"
              class="card row"
              @click="router.push({ name: 'survey-manage', params: { id: s.id } })"
            >
              <span class="row__main">
                <span class="row__title">{{ s.title }}</span>
                <span class="row__meta">
                  {{ s.questions_count }} {{ plural(s.questions_count, 'вопрос', 'вопроса', 'вопросов') }}
                  · {{ formatWhen(s.created_at) }}<template v-if="s.author_name"> · {{ s.author_name }}</template>
                </span>
              </span>
              <span v-if="s.recipients" class="progress">
                <span class="progress__num">{{ s.responses }}/{{ s.recipients }}</span>
                <span class="progress__bar"><span :style="{ width: `${(s.responses / s.recipients) * 100}%` }" /></span>
              </span>
              <span class="state" :class="`state--${s.status}`">{{ STATUS_LABELS[s.status] }}</span>
              <BaseIcon name="chevron-right" :size="16" class="row__chevron" />
            </button>
          </section>
        </template>
      </div>
    </main>
  </div>
</template>

<style scoped>
.surveys {
  max-width: 880px;
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.head .create-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.block {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.block__title {
  margin: 0 0 var(--space-1);
  font-size: 15px;
  font-weight: 600;
}

.empty {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  padding: var(--space-3) var(--space-4);
  color: var(--text);
  text-align: left;
  font: inherit;
  cursor: pointer;
}

.row:hover {
  background: var(--surface-hover);
}

.row__main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.row__title {
  font-size: 14px;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.row__meta {
  font-size: 12px;
  color: var(--text-muted);
}

.row__chevron {
  color: var(--text-faint);
}

.progress {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
}

.progress__num {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
}

.progress__bar {
  width: 72px;
  height: 4px;
  border-radius: var(--radius-full);
  background: var(--border);
  overflow: hidden;
}

.progress__bar span {
  display: block;
  height: 100%;
  background: var(--success);
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

.state--off,
.state--closed,
.state--draft {
  background: var(--surface-raised);
  color: var(--text-muted);
}

.form-error {
  margin: 0;
  font-size: 13px;
  color: var(--danger);
}

@media (max-width: 768px) {
  .head .create-btn {
    width: 100%;
    justify-content: center;
    height: var(--control-h-touch);
  }

  .progress__bar {
    width: 48px;
  }
}
</style>
