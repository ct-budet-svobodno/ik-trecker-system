<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import BaseIcon from '../components/BaseIcon.vue'
import {
  checklistByTag,
  fetchChecklistFile,
  fetchChecklists,
  prepareChecklists,
  resetChecklists,
  sendChecklists,
  sendOneChecklist,
  sendTestChecklist,
  uploadChecklistImage,
} from '../api/checklists'
import { renderChecklist } from '../utils/checklistImage'

const overview = ref(null)
const isLoading = ref(true)
const isBusy = ref(false)
const error = ref('')
const notice = ref('')
const factsText = ref('')
// Подготовка: сколько картинок уже нарисовано и загружено.
const drawn = ref(null)

const filter = ref('all')
const FILTERS = [
  { key: 'all', label: 'Все' },
  { key: 'done', label: 'Выполнили' },
  { key: 'progress', label: 'В процессе' },
  { key: 'none', label: 'Без фото' },
  { key: 'failed', label: 'Не дошло' },
]

const facts = computed(() =>
  factsText.value
    .split('\n')
    .map((f) => f.trim())
    .filter(Boolean),
)

const cards = computed(() => overview.value?.cards ?? [])
const sentCards = computed(() => cards.value.filter((c) => c.status === 'sent'))
const anySent = computed(() => cards.value.some((c) => c.status !== 'draft'))
const unsent = computed(() => cards.value.filter((c) => c.status !== 'sent'))
const photosOf = (c) => c.photos.filter(Boolean).length

const stats = computed(() => ({
  sent: sentCards.value.length,
  failed: cards.value.filter((c) => c.status === 'failed').length,
  done: sentCards.value.filter((c) => photosOf(c) === 3).length,
  progress: sentCards.value.filter((c) => photosOf(c) > 0 && photosOf(c) < 3).length,
}))

const visible = computed(() => {
  const list = cards.value
  switch (filter.value) {
    case 'done':
      return list.filter((c) => photosOf(c) === 3)
    case 'progress':
      return list.filter((c) => photosOf(c) > 0 && photosOf(c) < 3)
    case 'none':
      return list.filter((c) => c.status === 'sent' && photosOf(c) === 0)
    case 'failed':
      return list.filter((c) => c.status === 'failed')
    default:
      return list
  }
})

// ── Загрузка и опрос ──
let pollTimer = null

async function load() {
  try {
    const fresh = await fetchChecklists()
    if (!overview.value && !factsText.value) factsText.value = fresh.default_facts.join('\n')
    overview.value = fresh
  } catch {
    error.value = 'Не удалось загрузить чек-листы'
  } finally {
    isLoading.value = false
  }
  schedule()
}

// Пока рассылаем — часто, потом раз в 5 с: подтягиваем присланные фото.
function schedule() {
  clearTimeout(pollTimer)
  if (!overview.value) return
  if (overview.value.sending) pollTimer = setTimeout(load, 1500)
  else if (anySent.value) pollTimer = setTimeout(load, 5000)
}

onMounted(load)
onBeforeUnmount(() => clearTimeout(pollTimer))

// ── Подготовка: раздать факты, нарисовать и загрузить картинки ──
async function prepare() {
  error.value = ''
  if (facts.value.length < 3) {
    error.value = 'Нужно хотя бы три факта'
    return
  }
  if (cards.value.length && !window.confirm('Раздать факты заново? Текущие чек-листы заменятся.')) return
  isBusy.value = true
  try {
    overview.value = await prepareChecklists(facts.value)
    await drawAll(overview.value.cards)
    await load()
  } catch (err) {
    error.value = err.response?.data?.detail ?? err.message ?? 'Не удалось подготовить'
  } finally {
    isBusy.value = false
    drawn.value = null
  }
}

async function drawAll(list) {
  drawn.value = 0
  for (const card of list) {
    const blob = await renderChecklist(card)
    await uploadChecklistImage(card.id, blob)
    drawn.value += 1
  }
}

async function send() {
  const count = unsent.value.length
  if (!window.confirm(`Разослать чек-листы ${count} людям? Каждому придёт его картинка в личку от бота.`)) return
  isBusy.value = true
  error.value = ''
  try {
    overview.value = await sendChecklists()
    schedule()
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось разослать'
  } finally {
    isBusy.value = false
  }
}

async function sendTest() {
  isBusy.value = true
  error.value = ''
  try {
    overview.value = await sendTestChecklist()
    notice.value = 'Ваш лист у вас в личке. Пришлите боту фото — проверьте, что они дошли до группы'
    schedule()
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось отправить'
  } finally {
    isBusy.value = false
  }
}

// ── Отправка по тегу: не дошло или человека не было в раздаче ──
const tagInput = ref('')
const tagBusy = ref(false)
const tagResult = ref(null) // { ok, text }

async function sendByTag() {
  const tag = tagInput.value.trim().replace(/^@/, '')
  if (!tag) return
  tagBusy.value = true
  tagResult.value = null
  try {
    const { card, needs_image: needsImage } = await checklistByTag(tag)
    if (needsImage) await uploadChecklistImage(card.id, await renderChecklist(card))
    overview.value = await sendOneChecklist(card.id)
    tagResult.value = {
      ok: true,
      text: `Отправили @${tag} лист №${card.number}${needsImage ? ' (новый)' : ''}: ${card.facts.join(' · ')}`,
    }
    tagInput.value = ''
    schedule()
  } catch (err) {
    tagResult.value = { ok: false, text: err.response?.data?.detail ?? err.message ?? 'Не удалось отправить' }
    await load()
  } finally {
    tagBusy.value = false
  }
}

async function reset() {
  if (!window.confirm('Начать заново? Чек-листы и присланные фото пропадут из трекера, бот перестанет их принимать. В группе фото останутся.')) {
    return
  }
  isBusy.value = true
  try {
    overview.value = await resetChecklists()
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось сбросить'
  } finally {
    isBusy.value = false
  }
}

// ── Просмотр: картинка листа и присланные фото ──
const viewing = ref(null)
const viewUrls = ref({ image: null, photos: [null, null, null] })
const viewLoading = ref(false)

function revokeAll() {
  const urls = [viewUrls.value.image, ...viewUrls.value.photos].filter(Boolean)
  urls.forEach((u) => URL.revokeObjectURL(u))
  viewUrls.value = { image: null, photos: [null, null, null] }
}

async function open(card) {
  revokeAll()
  viewing.value = card
  viewLoading.value = true
  const url = (blob) => URL.createObjectURL(blob)
  const tasks = [fetchChecklistFile(card.id).then((b) => (viewUrls.value.image = url(b))).catch(() => {})]
  card.photos.forEach((has, i) => {
    if (has) {
      tasks.push(
        fetchChecklistFile(card.id, i + 1)
          .then((b) => (viewUrls.value.photos[i] = url(b)))
          .catch(() => {}),
      )
    }
  })
  await Promise.all(tasks)
  viewLoading.value = false
}

function close() {
  viewing.value = null
  revokeAll()
}

watch(viewing, (v) => {
  if (v) document.addEventListener('keydown', onKey)
  else document.removeEventListener('keydown', onKey)
})

function onKey(e) {
  if (e.key === 'Escape') close()
}

const STATUS = { draft: 'Не отправлен', sent: 'Отправлен', failed: 'Не дошло' }
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="lists">
        <p class="breadcrumb">ИК · Трекер / Чек-листы</p>
        <h1>Чек-листы</h1>
        <p class="subtitle">
          «Найди того, кто…»: каждому по три факта, нужно найти подходящих людей и сфоткаться с ними. Фото человек
          шлёт боту в личку, бот пересылает их в группу проверки с ФИО и номером пункта.
        </p>

        <AppLoader v-if="isLoading" />

        <template v-else-if="overview">
          <p v-if="!overview.enabled" class="warn">
            Бот или его база не подключены — подготовить можно, разослать и принимать фото нельзя.
          </p>

          <!-- Шаг 1: факты -->
          <section v-if="!anySent" class="card">
            <header class="card__head">
              <h2 class="card__title"><span class="step">1</span> Факты</h2>
              <span class="count">{{ facts.length }}</span>
            </header>
            <textarea v-model="factsText" class="area" rows="10" spellcheck="false" />
            <p class="hint">
              По одному в строке, в творительном падеже: на карточке перед фактом стоит «Сфоткайся с». Факты
              перемешаются и разойдутся по три — каждый достанется почти одинаковому числу людей.
            </p>
            <div class="row">
              <button class="create-btn" :disabled="isBusy" @click="prepare">
                {{ cards.length ? 'Раздать заново' : `Подготовить чек-листы (${overview.people})` }}
              </button>
              <span v-if="drawn !== null" class="progress-text">Рисуем картинки: {{ drawn }} из {{ cards.length }}</span>
            </div>
          </section>

          <!-- Шаг 2: рассылка -->
          <section v-if="cards.length" class="card">
            <header class="card__head">
              <h2 class="card__title"><span class="step">2</span> {{ anySent ? 'Разослано' : 'Рассылка' }}</h2>
            </header>
            <div class="stats">
              <div class="stat">
                <span class="stat__num">{{ cards.length }}</span>
                <span class="stat__label">чек-листов</span>
              </div>
              <div class="stat">
                <span class="stat__num">{{ stats.sent }}</span>
                <span class="stat__label">дошло</span>
              </div>
              <div class="stat stat--ok">
                <span class="stat__num">{{ stats.done }}</span>
                <span class="stat__label">выполнили</span>
              </div>
              <div class="stat">
                <span class="stat__num">{{ stats.progress }}</span>
                <span class="stat__label">в процессе</span>
              </div>
              <div v-if="stats.failed" class="stat stat--bad">
                <span class="stat__num">{{ stats.failed }}</span>
                <span class="stat__label">не дошло</span>
              </div>
            </div>
            <p v-if="stats.failed" class="hint">
              «Не дошло» — человек ни разу не запускал бота. Пусть нажмёт «Старт» у бота, потом «Дослать».
            </p>
            <div class="row">
              <button
                v-if="unsent.length"
                class="create-btn"
                :disabled="isBusy || overview.sending || !overview.enabled"
                @click="send"
              >
                <BaseIcon name="send" :size="14" />
                <template v-if="overview.sending">Рассылаем…</template>
                <template v-else>{{ stats.sent > 1 ? `Дослать (${unsent.length})` : `Разослать (${unsent.length})` }}</template>
              </button>
              <button
                v-if="!anySent"
                class="ghost"
                :disabled="isBusy || overview.sending || !overview.enabled"
                @click="sendTest"
              >
                Проверить на себе
              </button>
              <button class="ghost ghost--danger" :disabled="isBusy || overview.sending" @click="reset">
                Начать заново
              </button>
            </div>
          </section>

          <p v-if="error" class="form-error">{{ error }}</p>
          <p v-if="notice" class="form-notice">{{ notice }}</p>

          <!-- Кому не дошло или кого не было в раздаче -->
          <section v-if="cards.length" class="card">
            <header class="card__head">
              <h2 class="card__title"><span class="step">+</span> Отправить по юзернейму</h2>
            </header>
            <p class="hint">
              Человеку не пришёл лист или его не было в раздаче: пусть напишет боту в личку /start, потом введите его
              тег. Лист, который не дошёл, уйдёт заново; новому человеку соберём свободный лист из самых редких фактов.
            </p>
            <form class="tag-form" @submit.prevent="sendByTag">
              <input
                v-model="tagInput"
                class="tag-input"
                autocapitalize="off"
                autocomplete="off"
                spellcheck="false"
                aria-label="Telegram-тег"
              />
              <button class="create-btn" :disabled="tagBusy || !tagInput.trim() || !overview.enabled">
                <BaseIcon name="send" :size="14" />
                {{ tagBusy ? 'Отправляем…' : 'Отправить' }}
              </button>
            </form>
            <p v-if="tagResult" :class="tagResult.ok ? 'form-notice' : 'form-error'">{{ tagResult.text }}</p>
          </section>

          <!-- Участники -->
          <section v-if="cards.length" class="people">
            <div class="filters" role="tablist">
              <button
                v-for="f in FILTERS"
                :key="f.key"
                class="filter"
                :class="{ 'filter--on': filter === f.key }"
                role="tab"
                :aria-selected="filter === f.key"
                @click="filter = f.key"
              >
                {{ f.label }}
              </button>
            </div>
            <p v-if="!visible.length" class="hint">Здесь пока никого.</p>
            <button v-for="c in visible" :key="c.id" class="person" @click="open(c)">
              <span class="person__num">{{ c.number }}</span>
              <span class="person__main">
                <span class="person__name">
                  {{ c.full_name }}
                  <span v-if="c.username" class="person__tag">@{{ c.username }}</span>
                </span>
                <span class="person__facts">{{ c.facts.join(' · ') }}</span>
              </span>
              <span class="person__side">
                <span v-if="c.status !== 'sent'" class="chip" :class="`chip--${c.status}`">{{ STATUS[c.status] }}</span>
                <span v-else class="dots" :aria-label="`Фото: ${photosOf(c)} из 3`">
                  <span v-for="(has, i) in c.photos" :key="i" class="dot" :class="{ 'dot--on': has }">{{ i + 1 }}</span>
                </span>
              </span>
            </button>
          </section>
        </template>
      </div>

      <!-- Просмотр листа и фото. В body: у страницы своя анимация (свой слой),
           внутри неё окно не перекрыло бы нижний таб-бар. -->
      <Teleport to="body">
      <div v-if="viewing" class="modal-backdrop" @click.self="close">
        <div v-swipe-close="close" class="modal" role="dialog" aria-modal="true">
          <header class="modal__head">
            <div>
              <p class="modal__title">№{{ viewing.number }} · {{ viewing.full_name }}</p>
              <p class="hint">{{ STATUS[viewing.status] }} · фото {{ photosOf(viewing) }} из 3</p>
            </div>
            <button class="icon-btn" aria-label="Закрыть" @click="close">
              <BaseIcon name="plus" :size="18" class="icon-close" />
            </button>
          </header>
          <AppLoader v-if="viewLoading" />
          <img v-if="viewUrls.image" :src="viewUrls.image" class="modal__sheet" alt="Чек-лист" />
          <div class="shots">
            <figure v-for="(fact, i) in viewing.facts" :key="i" class="shot">
              <img v-if="viewUrls.photos[i]" :src="viewUrls.photos[i]" :alt="`Фото к пункту ${i + 1}`" />
              <div v-else class="shot__empty">{{ viewing.photos[i] ? 'Загружаем…' : 'Нет фото' }}</div>
              <figcaption><b>{{ i + 1 }}.</b> {{ fact }}</figcaption>
            </figure>
          </div>
        </div>
      </div>
      </Teleport>
    </main>
  </div>
</template>

<style scoped>
.lists {
  max-width: 900px;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.lists .subtitle {
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

.card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-5);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card__title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.step {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full);
  background: var(--accent-soft);
  color: var(--text);
  font: 500 12px var(--font-mono);
}

.count {
  font: 500 12px var(--font-mono);
  color: var(--text-muted);
}

.area {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
  color: var(--text);
  font: 13px/20px var(--font-mono);
  resize: vertical;
}

.area:focus {
  outline: none;
  border-color: var(--accent);
}

.hint {
  margin: 0;
  font-size: 12px;
  line-height: 18px;
  color: var(--text-muted);
}

.row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.row .create-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.progress-text {
  font-size: 13px;
  color: var(--success);
}

.ghost {
  height: var(--control-h);
  padding: 0 14px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text);
  font-size: 14px;
}

.ghost:hover:not(:disabled) {
  background: var(--surface-hover);
}

.ghost--danger:hover:not(:disabled) {
  color: var(--danger);
}

.tag-form {
  display: flex;
  gap: var(--space-2);
}

.tag-input {
  flex: 1;
  min-width: 0;
  height: var(--control-h);
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
  color: var(--text);
  font: inherit;
  font-size: 14px;
}

.tag-input:focus {
  outline: none;
  border-color: var(--accent);
}

.tag-form .create-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.form-notice {
  margin: 0;
  font-size: 13px;
  color: var(--success);
}

.form-error {
  margin: 0;
  font-size: 13px;
  color: var(--danger);
}

.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: var(--space-2);
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface-raised);
}

.stat__num {
  font: 500 24px/30px var(--font-display);
}

.stat__label {
  font-size: 12px;
  color: var(--text-muted);
}

.stat--ok .stat__num {
  color: var(--success);
}

.stat--bad .stat__num {
  color: var(--danger);
}

/* Участники */
.people {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  margin-bottom: var(--space-1);
}

.filter {
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  background: transparent;
  color: var(--text-muted);
  font-size: 13px;
}

.filter--on {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--text);
}

.person {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  color: var(--text);
  text-align: left;
}

.person:hover {
  background: var(--surface-hover);
}

.person__num {
  width: 32px;
  flex-shrink: 0;
  font: 500 13px var(--font-mono);
  color: var(--text-muted);
}

.person__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.person__name {
  font-size: 14px;
  font-weight: 600;
}

.person__tag {
  margin-left: 4px;
  font-size: 12px;
  font-weight: 400;
  color: var(--text-faint);
}

.person__facts {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--text-muted);
}

.person__side {
  flex-shrink: 0;
}

.chip {
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  background: var(--surface-raised);
  font-size: 12px;
  color: var(--text-muted);
}

.chip--failed {
  background: color-mix(in srgb, var(--danger) 14%, transparent);
  color: var(--danger);
}

.dots {
  display: flex;
  gap: 4px;
}

.dot {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-full);
  font: 500 11px var(--font-mono);
  color: var(--text-faint);
}

.dot--on {
  border: none;
  background: var(--success);
  color: var(--on-success);
}

/* Просмотр — общий каркас модалки (.modal-backdrop/.modal); на телефоне
   глобальные стили делают из неё шторку. */
.modal-backdrop {
  position: fixed;
  inset: 0;
  /* Выше нижнего таб-бара. */
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-5);
  background: rgba(0, 0, 0, 0.5);
}

.modal {
  width: 100%;
  max-width: 860px;
  max-height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-5);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.modal__head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
}

.modal__title {
  margin: 0 0 2px;
  font: 500 18px/24px var(--font-display);
}

.icon-btn {
  width: var(--control-h);
  height: var(--control-h);
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-muted);
}

.icon-close {
  transform: rotate(45deg);
}

.modal__sheet {
  width: 100%;
  border-radius: var(--radius-md);
}

.shots {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-2);
}

.shot {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.shot img,
.shot__empty {
  width: 100%;
  aspect-ratio: 3 / 4;
  object-fit: cover;
  border-radius: var(--radius-md);
  background: var(--surface-raised);
}

.shot__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed var(--border-strong);
  box-sizing: border-box;
  font-size: 12px;
  color: var(--text-faint);
}

.shot figcaption {
  font-size: 12px;
  line-height: 17px;
  color: var(--text-muted);
}

@media (max-width: 768px) {
  .card,
  .modal {
    padding: var(--space-4);
  }

  .ghost,
  .row .create-btn,
  .icon-btn,
  .tag-input,
  .tag-form .create-btn {
    height: var(--control-h-touch);
  }

  .icon-btn {
    width: var(--control-h-touch);
  }

  .row > * {
    flex: 1 1 100%;
    justify-content: center;
  }

  .person {
    padding: var(--space-3);
  }

}
</style>
