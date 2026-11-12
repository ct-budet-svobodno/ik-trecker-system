<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

import AppSidebar from '../components/AppSidebar.vue'
import PlayingCard from '../components/PlayingCard.vue'
import SeaGrid from '../components/SeaGrid.vue'
import {
  bunkerLobbyAction,
  createBunkerGame,
  createDurakGame,
  createSeaGame,
  fetchBunkerGames,
  fetchOpenBunkerTables,
  fetchDurakGames,
  fetchSeaGames,
  createPokerGame,
  fetchPokerGames,
  fetchOpenPokerGames,
  pokerLobbyAction,
} from '../api/games'

const router = useRouter()
const authStore = useAuthStore()

const games = ref([])
// Столы из админки, за которые можно сесть самому.
const openTables = ref([])
const openPoker = ref([])
const isCreating = ref(false)
const error = ref('')

// Каждая игра — свой API и свой экран партии; список «Мои партии» общий.
const KINDS = {
  durak: { title: 'Дурак', route: 'durak', create: createDurakGame },
  sea: { title: 'Морской бой', route: 'sea', create: createSeaGame },
  bunker: { title: 'Бункер', route: 'bunker', create: createBunkerGame },
  poker: { title: 'Покер', route: 'poker', create: createPokerGame },
}

// Картинка на плитке бункера: веер карт характеристик в цветах направлений.
const BUNKER_ART = [
  { label: 'Профессия', value: 'Хирург', color: 'var(--dir-ct)' },
  { label: 'Здоровье', value: 'Астма', color: 'var(--dir-prod-a)' },
  { label: 'Багаж', value: 'Рация', color: 'var(--dir-nvk)' },
]

// Картинка на плитке морского боя: пара кораблей и следы выстрелов.
const SEA_ART = {
  ships: [[12, 13, 14], [51, 61], [37], [76, 77, 78, 79]],
  shots: { 12: 'hit', 13: 'hit', 14: 'hit', 37: 'hit', 77: 'hit', 33: 'miss', 55: 'miss', 90: 'miss', 19: 'miss' },
}

onMounted(async () => {
  await refresh()
  scheduleRefresh()
})

// «Мои партии» и открытые столы меняются без нашего участия (соперник сходил,
// кто-то сел за стол) — обновляем список, пока страница открыта.
const REFRESH_MS = 5000
let refreshTimer = null

async function refresh() {
  const [durak, sea, bunker, poker] = await Promise.all([
    fetchDurakGames().catch(() => []),
    fetchSeaGames().catch(() => []),
    fetchBunkerGames().catch(() => []),
    fetchPokerGames().catch(() => []),
  ])
  fetchOpenBunkerTables().then((tables) => (openTables.value = tables)).catch(() => {})
  fetchOpenPokerGames().then((tables) => (openPoker.value = tables)).catch(() => {})
  games.value = [
    ...durak.map((g) => ({ ...g, kind: 'durak' })),
    ...sea.map((g) => ({ ...g, kind: 'sea' })),
    ...bunker.map((g) => ({ ...g, kind: 'bunker' })),
    ...poker.map((g) => ({ ...g, kind: 'poker' })),
  ].sort((a, b) => Number(b.my_turn) - Number(a.my_turn))
}

function scheduleRefresh() {
  clearTimeout(refreshTimer)
  refreshTimer = setTimeout(async () => {
    if (!document.hidden) await refresh()
    scheduleRefresh()
  }, REFRESH_MS)
}

onBeforeUnmount(() => clearTimeout(refreshTimer))

async function startGame(kind, vsBot) {
  isCreating.value = true
  error.value = ''
  try {
    const game = await KINDS[kind].create(vsBot)
    router.push({ name: KINDS[kind].route, params: { code: game.code } })
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось начать партию'
    isCreating.value = false
  }
}

async function joinTable(table) {
  isCreating.value = true
  error.value = ''
  try {
    await bunkerLobbyAction(table.code, 'join')
    router.push({ name: 'bunker', params: { code: table.code } })
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось сесть за стол'
    isCreating.value = false
  }
}

async function joinPoker(table) {
  isCreating.value = true
  error.value = ''
  try {
    await pokerLobbyAction(table.code, 'join')
    router.push({ name: 'poker', params: { code: table.code } })
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось сесть за стол'
    isCreating.value = false
  }
}

function openGame(game) {
  router.push({ name: KINDS[game.kind].route, params: { code: game.code } })
}

function gameName(game) {
  if (game.kind === 'poker') return `Покер · ${game.players} игроков`
  if (game.kind === 'bunker') {
    return `${KINDS.bunker.title} · ${game.title ?? `игроков: ${game.players}`}`
  }
  return `${KINDS[game.kind].title} · ${game.opponent_name ?? 'без соперника'}`
}

function statusLabel(game) {
  if (game.kind === 'poker') return game.status === 'waiting' ? 'Собираем стол' : game.my_turn ? 'Ваш ход' : 'Идёт игра'
  if (game.kind === 'bunker') {
    if (game.status === 'waiting') return game.my_turn ? 'Можно начинать' : 'Собираем лобби'
    return game.my_turn ? 'Ваш ход' : 'Идёт игра'
  }
  if (game.status === 'waiting') return 'Ждём соперника'
  if (game.status === 'ready_check') return game.my_turn ? 'Подтвердите участие' : 'Ждём подтверждения'
  if (game.status === 'placing') return game.my_turn ? 'Расставьте флот' : 'Соперник расставляет флот'
  return game.my_turn ? 'Ваш ход' : 'Ход соперника'
}
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="games">
        <p class="breadcrumb">ИК · Трекер / Игры</p>
        <h1>Игры</h1>
        <p class="subtitle">Перерыв между задачами. Партии видят только их участники.</p>

        <section class="game-tile">
          <div class="game-tile__art" aria-hidden="true">
            <PlayingCard :card="12" size="table" class="game-tile__card game-tile__card--1" />
            <PlayingCard :card="25" size="table" class="game-tile__card game-tile__card--2" />
            <PlayingCard :card="null" size="table" class="game-tile__card game-tile__card--3" />
          </div>
          <div class="game-tile__body">
            <h2 class="game-tile__title">Дурак</h2>
            <p class="game-tile__desc">Подкидной один на один, колода 36. Играйте с ботом или позовите коллегу ссылкой.</p>
            <div class="game-tile__actions">
              <button class="create-btn" :disabled="isCreating" @click="startGame('durak', true)">С ботом</button>
              <button class="game-tile__secondary" :disabled="isCreating" @click="startGame('durak', false)">
                С человеком
              </button>
            </div>
          </div>
        </section>

        <section class="game-tile">
          <div class="game-tile__art" aria-hidden="true">
            <PlayingCard :card="12" size="table" class="game-tile__card game-tile__card--1" />
            <PlayingCard :card="25" size="table" class="game-tile__card game-tile__card--2" />
          </div>
          <div class="game-tile__body">
            <h2 class="game-tile__title">Покер</h2>
            <p class="game-tile__desc">Техасский холдем на 2–6 человек. Соберите стол и пригласите игроков ссылкой. Фишки только игровые.</p>
            <div class="game-tile__actions">
              <button class="create-btn" :disabled="isCreating" @click="startGame('poker')">Собрать стол</button>
            </div>
          </div>
        </section>

        <section class="game-tile">
          <div class="game-tile__art" aria-hidden="true"><span style="font-size: 72px">🎭</span></div>
          <div class="game-tile__body">
            <h2 class="game-tile__title">Мафия · в Telegram-чате</h2>
            <p class="game-tile__desc">Игра уже есть в боте. В группе напишите <strong>!мафия</strong> или <strong>/mafia</strong>, затем участники нажимают «Вступить». Нужно 5–16 человек. Роли и ночные действия бот пришлёт в личку.</p>
          </div>
        </section>

        <div v-if="openPoker.length" class="tables">
          <p class="tables__title">Открытые столы покера</p>
          <div v-for="table in openPoker" :key="table.code" class="tables__item">
            <span class="tables__info">
              <span class="tables__name">Стол {{ table.code }}</span>
              <span class="tables__meta">{{ table.players }} из 6 · создал {{ table.host_name }}</span>
            </span>
            <button class="game-tile__secondary" :disabled="isCreating" @click="joinPoker(table)">Сесть</button>
          </div>
        </div>

        <section class="game-tile">
          <div class="game-tile__art game-tile__art--sea" aria-hidden="true">
            <SeaGrid compact :ships="SEA_ART.ships" :shots="SEA_ART.shots" />
          </div>
          <div class="game-tile__body">
            <h2 class="game-tile__title">Морской бой</h2>
            <p class="game-tile__desc">Классика 10×10: расставьте флот и топите корабли соперника. С ботом или с коллегой.</p>
            <div class="game-tile__actions">
              <button class="create-btn" :disabled="isCreating" @click="startGame('sea', true)">С ботом</button>
              <button class="game-tile__secondary" :disabled="isCreating" @click="startGame('sea', false)">
                С человеком
              </button>
            </div>
          </div>
        </section>

        <section class="game-tile">
          <div class="game-tile__art" aria-hidden="true">
            <span
              v-for="(card, i) in BUNKER_ART"
              :key="card.label"
              class="trait-art"
              :class="`trait-art--${i + 1}`"
              :style="{ '--cat': card.color }"
            >
              <span class="trait-art__label">{{ card.label }}</span>
              <span class="trait-art__value">{{ card.value }}</span>
            </span>
          </div>
          <div class="game-tile__body">
            <h2 class="game-tile__title">Бункер</h2>
            <p class="game-tile__desc">
              Катастрофа, а мест в убежище вдвое меньше, чем вас. От 4 до 16 игроков, спорим вживую — карты и
              голосование здесь.
            </p>
            <div class="game-tile__actions">
              <button class="create-btn" :disabled="isCreating" @click="startGame('bunker')">Собрать лобби</button>
              <button v-if="authStore.isAdmin" class="game-tile__secondary" @click="router.push({ name: 'bunker-tables' })">
                Столы
              </button>
            </div>
          </div>
        </section>
        <div v-if="openTables.length" class="tables">
          <p class="tables__title">Открытые столы</p>
          <div v-for="table in openTables" :key="table.code" class="tables__item">
            <span class="tables__info">
              <span class="tables__name">{{ table.title }}</span>
              <span class="tables__meta">
                {{ table.players.length }} из 16 · ведёт {{ table.host.full_name }}
              </span>
            </span>
            <button class="game-tile__secondary" :disabled="isCreating" @click="joinTable(table)">Сесть</button>
          </div>
        </div>
        <p v-if="error" class="games__error">{{ error }}</p>

        <section v-if="games.length" class="list">
          <h2 class="list__title">Мои партии</h2>
          <button
            v-for="game in games"
            :key="`${game.kind}-${game.code}`"
            class="list__item"
            @click="openGame(game)"
          >
            <span class="list__name">{{ gameName(game) }}</span>
            <span class="list__status" :class="{ 'list__status--turn': game.my_turn }">
              {{ statusLabel(game) }}
            </span>
          </button>
        </section>

      </div>
    </main>
  </div>
</template>

<style scoped>
.games {
  max-width: 640px;
}

.game-tile {
  display: flex;
  gap: var(--space-5);
  align-items: center;
  margin-top: var(--space-6);
  padding: var(--space-5);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.game-tile__art {
  position: relative;
  width: 124px;
  height: 108px;
  flex-shrink: 0;
}

.game-tile__art--sea {
  height: auto;
  padding: 4px 0;
}

.trait-art {
  position: absolute;
  width: 78px;
  height: 92px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  border: 1px solid color-mix(in srgb, var(--cat) 55%, var(--border));
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--cat) 18%, var(--surface-raised));
  box-shadow: var(--shadow-lift);
}

.trait-art__label {
  font-size: 11px;
  color: var(--text-muted);
}

.trait-art__value {
  font-size: 12px;
  font-weight: 600;
  color: var(--text);
}

.trait-art--1 { left: 0; top: 12px; transform: rotate(-10deg); }
.trait-art--2 { left: 23px; top: 4px; z-index: 1; }
.trait-art--3 { left: 46px; top: 12px; transform: rotate(10deg); z-index: 2; }

/* Открытые столы — сразу под плиткой бункера. */
.tables {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-top: var(--space-2);
  padding: var(--space-4) var(--space-5);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.tables__title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
}

.tables__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-raised);
}

.tables__info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.tables__name {
  font-size: 14px;
  font-weight: 600;
}

.tables__meta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--text-muted);
}

.game-tile + .game-tile {
  margin-top: var(--space-3);
}

.game-tile__card {
  position: absolute;
  top: 10px;
}

.game-tile__card--1 { left: 0; transform: rotate(-12deg); }
.game-tile__card--2 { left: 30px; transform: rotate(0deg); top: 4px; }
.game-tile__card--3 { left: 60px; transform: rotate(12deg); }

.game-tile__body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.game-tile__title {
  margin: 0;
  font: 500 20px/26px var(--font-display);
}

.game-tile__desc {
  margin: 0;
  font-size: 14px;
  line-height: 21px;
  color: var(--text-muted);
}

.game-tile__actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.game-tile__secondary {
  height: var(--control-h);
  padding: 0 14px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text);
  font-weight: 600;
  font-size: 14px;
}

.game-tile__secondary:hover {
  background: var(--surface-hover);
}

.games__error {
  margin: var(--space-2) 0 0;
  font-size: 13px;
  color: var(--danger);
}

.list {
  margin-top: var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.list__title {
  margin: 0 0 var(--space-1);
  font-size: 15px;
  font-weight: 600;
}

.list__item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  min-height: 48px;
  padding: 0 var(--space-4);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  color: var(--text);
  font-size: 14px;
  text-align: left;
}

.list__item:hover {
  background: var(--surface-hover);
}

.list__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.list__status {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.list__status--turn {
  color: var(--success);
  font-weight: 600;
}

@media (max-width: 768px) {
  .game-tile {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-3);
    padding: var(--space-4);
  }

  .game-tile__actions {
    width: 100%;
  }

  .game-tile__actions > * {
    flex: 1;
    height: var(--control-h-touch);
  }
}
</style>
