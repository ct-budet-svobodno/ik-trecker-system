<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import BaseIcon from '../components/BaseIcon.vue'
import {
  cancelBunkerTable,
  createBunkerTable,
  fetchBunkerTables,
  startBunkerTable,
  updateBunkerTable,
} from '../api/games'
import { getAvatarColor, getInitials } from '../utils/avatar'

const router = useRouter()

const MIN_PLAYERS = 4
const MAX_PLAYERS = 16

const tables = ref([])
const isLoading = ref(true)
const isBusy = ref(false)
const error = ref('')
// Теги, которых не нашли после последнего сохранения.
const missing = ref([])
const savedTitle = ref('')

// Форма: новый стол или правка (editing — код стола).
const editing = ref(null)
const title = ref('')
const hostTag = ref('')
const tagsText = ref('')

// Тот же разбор, что на бэке: «@tag», через запятую, пробел или с новой строки.
const parsedTags = computed(() => {
  const seen = new Set()
  return tagsText.value
    .split(/[\s,;]+/)
    .map((t) => t.trim().replace(/^@/, ''))
    .filter((t) => t && !seen.has(t.toLowerCase()) && seen.add(t.toLowerCase()))
})

const STATUS = {
  waiting: 'Ждёт раздачи',
  playing: 'Идёт игра',
  finished: 'Сыграно',
}
const PHASES = { reveal: 'открывают карты', discuss: 'обсуждение', vote: 'голосование', result: 'итог голосования' }

async function load() {
  try {
    tables.value = await fetchBunkerTables()
  } catch {
    error.value = 'Не удалось загрузить столы'
  } finally {
    isLoading.value = false
  }
}


function resetForm() {
  editing.value = null
  title.value = `Стол ${tables.value.filter((t) => t.status !== 'finished').length + 1}`
  hostTag.value = ''
  tagsText.value = ''
}

onMounted(async () => {
  await load()
  resetForm()
})

function edit(table) {
  editing.value = table.code
  title.value = table.title
  hostTag.value = table.host.tag ?? ''
  tagsText.value = table.players.map((p) => `@${p.tag}`).join('\n')
  missing.value = []
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function save() {
  error.value = ''
  if (!title.value.trim()) {
    error.value = 'Назовите стол'
    return
  }
  if (parsedTags.value.length > MAX_PLAYERS) {
    error.value = `За столом не больше ${MAX_PLAYERS} игроков`
    return
  }
  isBusy.value = true
  const payload = { title: title.value.trim(), tags: parsedTags.value, host_tag: hostTag.value.trim() || null }
  try {
    const saved = editing.value
      ? await updateBunkerTable(editing.value, payload)
      : await createBunkerTable(payload)
    missing.value = saved.missing
    savedTitle.value = saved.table.title
    await load()
    resetForm()
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось сохранить стол'
  } finally {
    isBusy.value = false
  }
}

// Пустые столы пачкой: «Стол N», игроки садятся сами из «Игр».
const bulkCount = ref(5)

async function createMany() {
  const count = Math.min(20, Math.max(1, Number(bulkCount.value) || 0))
  error.value = ''
  missing.value = []
  isBusy.value = true
  const taken = new Set(tables.value.map((t) => t.title))
  let n = 1
  try {
    for (let made = 0; made < count; made++) {
      while (taken.has(`Стол ${n}`)) n++
      taken.add(`Стол ${n}`)
      await createBunkerTable({ title: `Стол ${n}`, tags: [], host_tag: hostTag.value.trim() || null })
    }
    await load()
    resetForm()
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось создать столы'
    await load()
  } finally {
    isBusy.value = false
  }
}

async function deal(table) {
  isBusy.value = true
  error.value = ''
  try {
    await startBunkerTable(table.code)
    await load()
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось раздать карты'
  } finally {
    isBusy.value = false
  }
}

async function cancel(table) {
  const what = table.status === 'playing' ? 'Остановить игру за этим столом?' : 'Убрать стол?'
  if (!window.confirm(what)) return
  isBusy.value = true
  try {
    await cancelBunkerTable(table.code)
    if (editing.value === table.code) resetForm()
    await load()
  } finally {
    isBusy.value = false
  }
}

function hostLabel(table) {
  const name = table.host.full_name
  return table.host_plays ? `${name}, играет` : `${name}, не играет`
}
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="tables">
        <p class="breadcrumb">ИК · Игры / Бункер</p>
        <h1>Столы</h1>
        <p class="subtitle">
          Для очной игры. Можно создать пустые столы — ребята сядут сами из «Игр» → «Открытые столы», — или сразу
          рассадить по Telegram-тегам. Карты раздаются кнопкой, когда все на месте.
        </p>

        <section class="card bulk">
          <h2 class="card__title">Быстро: пустые столы</h2>
          <div class="bulk__row">
            <label class="field bulk__count">
              <span class="field__label">Сколько</span>
              <input v-model.number="bulkCount" class="field__input" type="number" min="1" max="20" />
            </label>
            <button class="create-btn" :disabled="isBusy" @click="createMany">Создать столы</button>
          </div>
          <span class="field__hint">
            Появятся «Стол N» без игроков; ведущий — вы (или тег из поля «Ведущий» ниже). Сменить ведущего можно правкой
            стола до раздачи.
          </span>
        </section>

        <section class="card form">
          <h2 class="card__title">{{ editing ? `Правка: ${title}` : 'Новый стол' }}</h2>
          <div class="form__row">
            <label class="field">
              <span class="field__label">Название</span>
              <input v-model="title" class="field__input" maxlength="100" />
            </label>
            <label class="field">
              <span class="field__label">Ведущий</span>
              <input v-model="hostTag" class="field__input" autocapitalize="off" spellcheck="false" />
              <span class="field__hint">Telegram-тег. Пусто — ведёте вы. Нет в списке игроков — ведёт, не играя.</span>
            </label>
          </div>
          <label class="field">
            <span class="field__label">
              Игроки (необязательно)
              <span class="field__count" :class="{ 'field__count--bad': parsedTags.length > MAX_PLAYERS }">
                {{ parsedTags.length }} из {{ MAX_PLAYERS }}
              </span>
            </span>
            <textarea v-model="tagsText" class="field__input field__area" rows="6" autocapitalize="off" spellcheck="false" />
            <span class="field__hint">
              Telegram-теги через запятую или каждый с новой строки, «@» можно не писать. Пусто — ребята сядут сами.
              Для игры нужно от {{ MIN_PLAYERS }} человек.
            </span>
          </label>

          <p v-if="missing.length" class="notice">
            <b>«{{ savedTitle }}» сохранён, но не нашлись: {{ missing.map((t) => `@${t}`).join(', ') }}.</b>
            Этих людей нет в трекере или у них другой тег — пусть заполнят анкету в мини-аппе, после одобрения добавьте
            их правкой стола.
          </p>
          <p v-if="error" class="form__error">{{ error }}</p>

          <div class="form__actions">
            <button class="create-btn" :disabled="isBusy" @click="save">
              {{ editing ? 'Сохранить стол' : 'Создать стол' }}
            </button>
            <button v-if="editing" class="ghost" :disabled="isBusy" @click="resetForm">Отмена</button>
          </div>
        </section>

        <AppLoader v-if="isLoading" />
        <p v-else-if="!tables.length" class="empty">Столов пока нет — создайте первый выше.</p>

        <section v-else class="list">
          <article v-for="table in tables" :key="table.code" class="card table" :class="`table--${table.status}`">
            <header class="table__head">
              <h2 class="table__title">{{ table.title }}</h2>
              <span class="chip" :class="`chip--${table.status}`">
                {{ STATUS[table.status] }}<template v-if="table.status === 'playing'"> · раунд {{ table.round }}, {{ PHASES[table.phase] }}</template>
              </span>
            </header>
            <p class="table__host">Ведущий: {{ hostLabel(table) }}</p>

            <ul class="people">
              <li v-for="p in table.players" :key="p.id" class="person" :class="{ 'person--out': p.out }">
                <span class="avatar" :style="{ background: getAvatarColor(p.id) }">{{ getInitials(p.full_name) }}</span>
                <span class="person__text">
                  <span class="person__name">{{ p.full_name }}</span>
                  <span class="person__tag">@{{ p.tag }}</span>
                </span>
              </li>
            </ul>

            <div class="table__actions">
              <button
                v-if="table.status === 'waiting'"
                class="create-btn"
                :disabled="isBusy || table.players.length < MIN_PLAYERS"
                @click="deal(table)"
              >
                {{ table.players.length < MIN_PLAYERS ? `Нужно ещё ${MIN_PLAYERS - table.players.length}` : 'Раздать карты' }}
              </button>
              <button class="ghost" @click="router.push({ name: 'bunker', params: { code: table.code } })">
                Открыть стол
              </button>
              <button v-if="table.status === 'waiting'" class="ghost" :disabled="isBusy" @click="edit(table)">
                <BaseIcon name="pen" :size="14" /> Изменить
              </button>
              <button
                v-if="table.status !== 'finished'"
                class="ghost ghost--danger"
                :disabled="isBusy"
                @click="cancel(table)"
              >
                {{ table.status === 'playing' ? 'Остановить' : 'Убрать' }}
              </button>
            </div>
          </article>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.tables {
  max-width: 860px;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.tables .subtitle {
  margin-bottom: var(--space-2);
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

.card__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.bulk__row {
  display: flex;
  align-items: flex-end;
  gap: var(--space-2);
}

.bulk__count {
  width: 120px;
}

.form__row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--space-3);
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
}

.field__count--bad {
  color: var(--danger);
}

.field__input {
  height: var(--control-h);
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
  color: var(--text);
  font: inherit;
  font-size: 14px;
}

.field__input:focus {
  outline: none;
  border-color: var(--accent);
}

.field__area {
  height: auto;
  padding: 10px 12px;
  resize: vertical;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 20px;
}

.field__hint {
  font-size: 12px;
  line-height: 18px;
  color: var(--text-faint);
}

.notice {
  margin: 0;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--prio-medium) 14%, transparent);
  color: var(--prio-medium);
  font-size: 13px;
  line-height: 20px;
}

.form__error {
  margin: 0;
  font-size: 13px;
  color: var(--danger);
}

.form__actions,
.table__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.ghost {
  height: var(--control-h);
  display: inline-flex;
  align-items: center;
  gap: 6px;
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

.empty {
  margin: 0;
  font-size: 14px;
  color: var(--text-muted);
}

.list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.table--finished {
  opacity: 0.7;
}

.table__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.table__title {
  margin: 0;
  font: 500 18px/24px var(--font-display);
}

.chip {
  flex-shrink: 0;
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  background: var(--surface-raised);
  font-size: 12px;
  color: var(--text-muted);
}

.chip--playing {
  background: color-mix(in srgb, var(--success) 16%, transparent);
  color: var(--success);
}

.table__host {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.people {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: var(--space-2);
}

.person {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  padding: 6px var(--space-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-raised);
}

.person--out {
  opacity: 0.5;
}

.person__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.person__name,
.person__tag {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.person__name {
  font-size: 13px;
}

.person__tag {
  font-size: 11px;
  color: var(--text-faint);
}

.avatar {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
}

@media (max-width: 768px) {
  .card {
    padding: var(--space-4);
  }

  .bulk__row {
  display: flex;
  align-items: flex-end;
  gap: var(--space-2);
}

.bulk__count {
  width: 120px;
}

.form__row {
    grid-template-columns: minmax(0, 1fr);
  }

  .field__input:not(.field__area),
  .ghost,
  .form__actions .create-btn,
  .table__actions .create-btn {
    height: var(--control-h-touch);
  }

  .form__actions > *,
  .table__actions > * {
    flex: 1;
    justify-content: center;
  }
}
</style>
