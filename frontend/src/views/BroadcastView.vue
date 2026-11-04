<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import BaseIcon from '../components/BaseIcon.vue'
import { fetchBroadcasts, sendTestBroadcast, startBroadcast } from '../api/broadcasts'

// «23 окт, 18:04». SQLite отдаёт время без зоны, а хранит UTC.
const sentAtFormatter = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
})

function formatSentAt(iso) {
  if (!iso) return ''
  return sentAtFormatter.format(new Date(/Z|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`))
}

const MAX_BUTTONS = 8
const MAX_TEXT = 3500

// Разделы трекера, которые кнопка открывает мини-аппом.
const SECTIONS = [
  { path: '/', label: 'Главная' },
  { path: '/tasks', label: 'Задачи' },
  { path: '/my-day', label: 'Мой день' },
  { path: '/calendar', label: 'Календарь' },
  { path: '/editorial', label: 'Редакция' },
  { path: '/games', label: 'Игры' },
]

const overview = ref(null)
const isLoading = ref(true)
const isBusy = ref(false)
const error = ref('')
const notice = ref('')

const text = ref('')
// kind: section — раздел трекера, link — ссылка наружу.
const buttons = ref([])

function addButton() {
  if (buttons.value.length >= MAX_BUTTONS) return
  buttons.value.push({ text: '', kind: 'section', path: '/games', url: '' })
}

function removeButton(index) {
  buttons.value.splice(index, 1)
}

function moveButton(index, delta) {
  const target = index + delta
  if (target < 0 || target >= buttons.value.length) return
  const list = buttons.value
  ;[list[index], list[target]] = [list[target], list[index]]
}

// ── Превью: та же разметка, что на бэке (**жирный**, __курсив__) ──
function escapeHtml(value) {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function markup(value) {
  return escapeHtml(value.trim())
    .replace(/\*\*([\s\S]+?)\*\*/g, '<b>$1</b>')
    .replace(/__([\s\S]+?)__/g, '<i>$1</i>')
}

const previewHtml = computed(() => markup(text.value))

// ── Проверка и сборка ──
function validate() {
  if (!text.value.trim()) return 'Напишите текст сообщения'
  if (text.value.length > MAX_TEXT) return `Текст длиннее ${MAX_TEXT} символов`
  for (const [i, b] of buttons.value.entries()) {
    if (!b.text.trim()) return `Подпишите кнопку ${i + 1}`
    if (b.kind === 'link' && !/^https?:\/\/\S+$/.test(b.url.trim())) {
      return `Ссылка в кнопке «${b.text.trim()}» должна начинаться с https://`
    }
  }
  return ''
}

function message() {
  return {
    text: text.value.trim(),
    buttons: buttons.value.map((b) =>
      b.kind === 'link' ? { text: b.text.trim(), url: b.url.trim() } : { text: b.text.trim(), path: b.path },
    ),
  }
}

async function run(action, done) {
  error.value = validate()
  notice.value = ''
  if (error.value) return
  isBusy.value = true
  try {
    await action(message())
    done()
  } catch (err) {
    const detail = err.response?.data?.detail
    error.value = Array.isArray(detail) ? 'Проверьте кнопки и текст' : (detail ?? 'Не удалось отправить')
  } finally {
    isBusy.value = false
  }
}

function sendTest() {
  run(sendTestBroadcast, () => (notice.value = 'Отправили вам в личку — посмотрите, как выглядит'))
}

function sendAll() {
  const count = overview.value?.recipients ?? 0
  if (!window.confirm(`Разослать сообщение ${count} ${people(count)}? Отменить после отправки нельзя.`)) return
  run(startBroadcast, async () => {
    text.value = ''
    buttons.value = []
    notice.value = 'Рассылка пошла — прогресс ниже'
    await load()
  })
}

function people(n) {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return 'человеку'
  return 'людям'
}

// ── История и прогресс ──
let pollTimer = null

async function load() {
  try {
    overview.value = await fetchBroadcasts()
  } catch {
    error.value = 'Не удалось загрузить рассылки'
  } finally {
    isLoading.value = false
  }
  clearTimeout(pollTimer)
  if (overview.value?.items.some((b) => b.status === 'sending')) {
    pollTimer = setTimeout(load, 1500)
  }
}

onMounted(load)
onBeforeUnmount(() => clearTimeout(pollTimer))

const isSending = computed(() => overview.value?.items.some((b) => b.status === 'sending'))

function progress(b) {
  return b.total ? Math.round(((b.sent + b.failed) / b.total) * 100) : 100
}

function buttonTarget(b) {
  if (b.url) return b.url.replace(/^https?:\/\//, '')
  return SECTIONS.find((s) => s.path === b.path)?.label ?? b.path
}
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="broadcast">
        <p class="breadcrumb">ИК · Трекер / Рассылка</p>
        <h1>Рассылка</h1>
        <p class="subtitle">
          Сообщение от бота в личку всем, кого он знает.
          <template v-if="overview">Сейчас это {{ overview.recipients }} человек.</template>
          Дойдёт тем, кто хоть раз запускал бота.
        </p>

        <AppLoader v-if="isLoading" />

        <template v-else>
          <p v-if="overview && !overview.enabled" class="warn">Бот не подключён — рассылка недоступна.</p>

          <div class="compose">
            <section class="card editor">
              <label class="field">
                <span class="field__label">
                  Текст
                  <span class="field__count" :class="{ 'field__count--bad': text.length > MAX_TEXT }">
                    {{ text.length }}/{{ MAX_TEXT }}
                  </span>
                </span>
                <textarea v-model="text" class="field__input field__area" rows="8" />
                <span class="field__hint">**жирный**, __курсив__. Ссылки в тексте Telegram подсветит сам.</span>
              </label>

              <div class="btns">
                <div class="btns__head">
                  <span class="field__label">Кнопки</span>
                  <span class="field__count">{{ buttons.length }}/{{ MAX_BUTTONS }}</span>
                </div>
                <div v-for="(b, i) in buttons" :key="i" class="btn-row">
                  <div class="btn-row__main">
                    <input v-model="b.text" class="field__input" maxlength="64" :aria-label="`Подпись кнопки ${i + 1}`" />
                    <div class="seg" role="group" aria-label="Куда ведёт">
                      <button type="button" :class="{ 'seg--on': b.kind === 'section' }" @click="b.kind = 'section'">Раздел</button>
                      <button type="button" :class="{ 'seg--on': b.kind === 'link' }" @click="b.kind = 'link'">Ссылка</button>
                    </div>
                  </div>
                  <div class="btn-row__main">
                    <select v-if="b.kind === 'section'" v-model="b.path" class="field__input" aria-label="Раздел трекера">
                      <option v-for="s in SECTIONS" :key="s.path" :value="s.path">{{ s.label }}</option>
                    </select>
                    <input
                      v-else
                      v-model="b.url"
                      class="field__input"
                      inputmode="url"
                      autocapitalize="off"
                      spellcheck="false"
                      aria-label="Ссылка"
                    />
                    <div class="btn-row__tools">
                      <button type="button" class="icon-btn" :disabled="i === 0" aria-label="Выше" @click="moveButton(i, -1)">
                        <BaseIcon name="chevron-left" :size="14" class="icon-up" />
                      </button>
                      <button
                        type="button"
                        class="icon-btn"
                        :disabled="i === buttons.length - 1"
                        aria-label="Ниже"
                        @click="moveButton(i, 1)"
                      >
                        <BaseIcon name="chevron-left" :size="14" class="icon-down" />
                      </button>
                      <button type="button" class="icon-btn icon-btn--danger" aria-label="Убрать кнопку" @click="removeButton(i)">
                        <BaseIcon name="trash" :size="14" />
                      </button>
                    </div>
                  </div>
                </div>
                <button v-if="buttons.length < MAX_BUTTONS" type="button" class="ghost" @click="addButton">
                  <BaseIcon name="plus" :size="14" /> Добавить кнопку
                </button>
                <span class="field__hint">«Раздел» откроет трекер в Telegram на нужной странице.</span>
              </div>

              <p v-if="error" class="form-error">{{ error }}</p>
              <p v-if="notice" class="form-notice">{{ notice }}</p>

              <div class="actions">
                <button
                  class="ghost"
                  :disabled="isBusy || !overview?.enabled || !overview?.has_telegram"
                  :title="overview?.has_telegram ? '' : 'Привяжите Telegram к аккаунту, чтобы проверять на себе'"
                  @click="sendTest"
                >
                  Отправить себе
                </button>
                <button class="create-btn" :disabled="isBusy || isSending || !overview?.enabled" @click="sendAll">
                  <BaseIcon name="send" :size="14" />
                  {{ isSending ? 'Идёт рассылка…' : `Разослать (${overview?.recipients ?? 0})` }}
                </button>
              </div>
            </section>

            <!-- Превью: как сообщение выглядит в Telegram -->
            <aside class="preview" aria-label="Превью сообщения">
              <p class="preview__label">Так увидят в Telegram</p>
              <div class="chat">
                <div class="bubble">
                  <p v-if="text.trim()" class="bubble__text" v-html="previewHtml" />
                  <p v-else class="bubble__text bubble__text--empty">Текст сообщения</p>
                </div>
                <div v-if="buttons.length" class="kb">
                  <span v-for="(b, i) in buttons" :key="i" class="kb__btn">
                    {{ b.text.trim() || `Кнопка ${i + 1}` }}
                    <BaseIcon v-if="b.kind === 'link'" name="arrow-right" :size="12" class="kb__icon" />
                  </span>
                </div>
              </div>
            </aside>
          </div>

          <section v-if="overview?.items.length" class="history">
            <h2 class="history__title">Отправленные</h2>
            <article v-for="b in overview.items" :key="b.id" class="card sent">
              <header class="sent__head">
                <span class="sent__meta">{{ formatSentAt(b.created_at) }} · {{ b.author_name ?? 'админ' }}</span>
                <span class="sent__status" :class="{ 'sent__status--live': b.status === 'sending' }">
                  {{ b.status === 'sending' ? `Отправляем… ${progress(b)}%` : 'Готово' }}
                </span>
              </header>
              <p class="sent__text" v-html="markup(b.text)" />
              <ul v-if="b.buttons.length" class="sent__btns">
                <li v-for="(btn, i) in b.buttons" :key="i">{{ btn.text }} → {{ buttonTarget(btn) }}</li>
              </ul>
              <div class="bar" aria-hidden="true">
                <span class="bar__ok" :style="{ width: `${b.total ? (b.sent / b.total) * 100 : 0}%` }" />
                <span class="bar__fail" :style="{ width: `${b.total ? (b.failed / b.total) * 100 : 0}%` }" />
              </div>
              <p class="sent__stats">
                Дошло <b>{{ b.sent }}</b> из {{ b.total }}<template v-if="b.failed"> · не дошло {{ b.failed }} — не запускали бота или заблокировали</template>
              </p>
            </article>
          </section>
        </template>
      </div>
    </main>
  </div>
</template>

<style scoped>
.broadcast {
  max-width: 980px;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.broadcast .subtitle {
  margin-bottom: var(--space-2);
}

.warn {
  margin: 0;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--prio-medium) 14%, transparent);
  color: var(--prio-medium);
  font-size: 13px;
}

.compose {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
  gap: var(--space-4);
  align-items: start;
}

.card {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-5);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field__label {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--text-muted);
}

.field__count {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
}

.field__count--bad {
  color: var(--danger);
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

.field__area {
  height: auto;
  padding: 10px 12px;
  resize: vertical;
  line-height: 21px;
}

.field__hint {
  font-size: 12px;
  line-height: 18px;
  color: var(--text-faint);
}

.btns {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.btns__head {
  display: flex;
  justify-content: space-between;
}

.btn-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-raised);
}

.btn-row__main {
  display: flex;
  gap: var(--space-2);
}

.btn-row__tools {
  display: flex;
  gap: var(--space-1);
}

.seg {
  height: var(--control-h);
  box-sizing: border-box;
  display: flex;
  flex-shrink: 0;
  padding: 2px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
}

.seg button {
  padding: 0 10px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-muted);
  font-size: 13px;
}

.seg button.seg--on {
  background: var(--accent-soft);
  color: var(--text);
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

.icon-btn--danger:hover {
  color: var(--danger);
}

.icon-up {
  transform: rotate(90deg);
}

.icon-down {
  transform: rotate(-90deg);
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

.btns > .ghost {
  align-self: flex-start;
}

.ghost:hover:not(:disabled) {
  background: var(--surface-hover);
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

/* Превью в духе Telegram, но в цветах трекера */
.preview {
  position: sticky;
  top: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.preview__label {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.chat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--space-4);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg);
}

.bubble {
  align-self: flex-start;
  max-width: 100%;
  padding: 8px 12px;
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-lg) var(--radius-sm);
  background: var(--surface-raised);
}

.bubble__text {
  margin: 0;
  font-size: 14px;
  line-height: 20px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.bubble__text--empty {
  color: var(--text-faint);
}

.kb {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.kb__btn {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 0 24px;
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--surface-raised) 70%, transparent);
  font-size: 13px;
  font-weight: 600;
  text-align: center;
}

.kb__icon {
  position: absolute;
  top: 6px;
  right: 6px;
  transform: rotate(-45deg);
  color: var(--text-muted);
}

/* История */
.history {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-top: var(--space-2);
}

.history__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.sent {
  gap: var(--space-2);
  padding: var(--space-4);
}

.sent__head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
}

.sent__meta {
  font-size: 12px;
  color: var(--text-muted);
}

.sent__status {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.sent__status--live {
  color: var(--success);
  font-weight: 600;
}

.sent__text {
  margin: 0;
  font-size: 14px;
  line-height: 20px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.sent__btns {
  margin: 0;
  padding-left: var(--space-4);
  font-size: 12px;
  color: var(--text-muted);
}

.bar {
  display: flex;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--border);
  overflow: hidden;
}

.bar__ok {
  background: var(--success);
  transition: width 0.3s;
}

.bar__fail {
  background: var(--danger);
  transition: width 0.3s;
}

.sent__stats {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.sent__stats b {
  color: var(--text);
}

@media (max-width: 768px) {
  .compose {
    grid-template-columns: minmax(0, 1fr);
  }

  .preview {
    position: static;
  }

  .card {
    padding: var(--space-4);
  }

  .field__input:not(.field__area),
  .ghost,
  .icon-btn,
  .actions .create-btn {
    height: var(--control-h-touch);
  }

  .icon-btn {
    width: var(--control-h-touch);
  }

  .seg {
    height: var(--control-h-touch);
  }

  .btn-row__main {
    flex-wrap: wrap;
  }

  .btn-row__main > .field__input {
    flex: 1 1 100%;
  }

  .btn-row__tools {
    margin-left: auto;
  }

  .actions {
    flex-direction: column-reverse;
  }

  .actions > * {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .bar__ok,
  .bar__fail {
    transition: none;
  }
}
</style>
