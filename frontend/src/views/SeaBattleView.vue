<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import BaseIcon from '../components/BaseIcon.vue'
import SeaGrid from '../components/SeaGrid.vue'
import {
  cancelSeaGame,
  createSeaGame,
  fetchSeaGame,
  inviteSeaToChat,
  joinSeaGame,
  readySeaGame,
  sendSeaMove,
} from '../api/games'
import {
  FLEET,
  N,
  canPlace,
  cellLabel,
  fitShip,
  randomFleet,
  remainingSizes,
} from '../utils/seabattle'
import { telegramApp } from '../utils/telegram'

const route = useRoute()
const router = useRouter()

const game = ref(null)
const loadError = ref('')
const moveError = ref('')
const isBusy = ref(false)
const copied = ref(false)
// Чем закончилась проверка готовности, если она сорвалась (как в дураке).
const readyOutcome = ref(null)
const chatInviteError = ref('')

const code = computed(() => String(route.params.code).toUpperCase())
const haptic = () => telegramApp()?.HapticFeedback

// ── Загрузка и опрос ──
// Пока ждём соперника (его прихода, расстановки или выстрела) — раз в 1.5 с
// спрашиваем поле; на подтверждении участия — чаще, там счёт на секунды.
const POLL_MS = 1500
const READY_POLL_MS = 500
let pollTimer = null

function applyGame(fresh) {
  const prev = game.value
  if (prev?.status === 'ready_check' && fresh.status !== 'ready_check') {
    if (fresh.status === 'waiting' && fresh.seat === 0) readyOutcome.value = 'guest-missed'
    else if (fresh.can_join) readyOutcome.value = 'me-missed'
  }
  if (fresh.status === 'ready_check' && prev?.status !== 'ready_check') {
    readyOutcome.value = null
    haptic()?.notificationOccurred('warning')
  }
  game.value = fresh
  startCountdown()
}

// /games/sea/new?vs=bot|human — новая партия (так открывают игру из бота).
async function startNew() {
  try {
    const fresh = await createSeaGame(route.query.vs !== 'human')
    router.replace({ name: 'sea', params: { code: fresh.code } })
  } catch {
    loadError.value = 'Не удалось начать партию'
  }
}

async function load() {
  if (code.value === 'NEW') return startNew()
  try {
    const fresh = await fetchSeaGame(code.value)
    const g = game.value
    const changed = !g || fresh.version !== g.version || fresh.status !== g.status
    if (changed || fresh.status === 'ready_check') {
      const becameMyTurn = fresh.status === 'playing' && fresh.my_turn && !g?.my_turn
      applyGame(fresh)
      if (becameMyTurn) haptic()?.impactOccurred('light')
    }
    loadError.value = ''
  } catch (err) {
    loadError.value = err.response?.status === 404
      ? 'Партия не найдена или места уже заняты'
      : 'Не удалось загрузить партию'
  }
}

const needsPolling = computed(() => {
  const g = game.value
  if (!g || g.status === 'finished' || g.status === 'cancelled') return false
  if (g.status === 'waiting' || g.status === 'ready_check') return true
  return !g.vs_bot && !g.my_turn
})

function schedulePoll() {
  clearTimeout(pollTimer)
  if (!needsPolling.value) return
  const delay = game.value?.status === 'ready_check' ? READY_POLL_MS : POLL_MS
  pollTimer = setTimeout(async () => {
    if (!document.hidden) await load()
    schedulePoll()
  }, delay)
}

// ── Подтверждение участия ──
const READY_SECONDS = 5
const secondsLeft = ref(0)
let countdownTimer = null

function startCountdown() {
  clearInterval(countdownTimer)
  const ready = game.value?.ready
  if (!ready) return
  const endsAt = performance.now() + ready.seconds_left * 1000
  const tick = () => {
    secondsLeft.value = Math.max(0, (endsAt - performance.now()) / 1000)
    if (secondsLeft.value <= 0) clearInterval(countdownTimer)
  }
  tick()
  countdownTimer = setInterval(tick, 100)
}

const RING = 2 * Math.PI * 40
const ringOffset = computed(() => RING * (1 - secondsLeft.value / READY_SECONDS))

async function confirmReady() {
  if (isBusy.value) return
  isBusy.value = true
  try {
    applyGame(await readySeaGame(code.value))
    haptic()?.impactOccurred('medium')
  } catch (err) {
    moveError.value = err.response?.data?.detail ?? 'Не удалось подтвердить'
  } finally {
    isBusy.value = false
  }
}

watch(needsPolling, schedulePoll)
watch(code, async () => {
  game.value = null
  readyOutcome.value = null
  chatInviteError.value = ''
  moveError.value = ''
  loadError.value = ''
  copied.value = false
  lastShot.value = null
  pendingCell.value = null
  resetDraft()
  await load()
  schedulePoll()
})

onMounted(async () => {
  await load()
  schedulePoll()
})

onBeforeUnmount(() => {
  clearTimeout(pollTimer)
  clearInterval(countdownTimer)
})

async function sendMove(payload) {
  const before = game.value
  const fresh = await sendSeaMove(code.value, { ...payload, version: before.version })
  applyGame(fresh)
  if (fresh.result) haptic()?.notificationOccurred(fresh.result === 'lose' ? 'error' : 'success')
  return fresh
}

function moveFailed(err, fallback) {
  if (err.response?.status === 409) return load() // соперник успел сходить
  moveError.value = err.response?.data?.detail ?? fallback
  haptic()?.notificationOccurred('error')
}

// ── Расстановка ──
// Тап по клетке ставит выбранный корабль носом в неё (у края — сдвигаем, чтобы
// влез), тап по своему кораблю — убирает его обратно в док.
const draft = ref([])
const vertical = ref(false)
const chosenSize = ref(null)
const lastPlaced = ref([])
const placeError = ref('')

function resetDraft() {
  draft.value = []
  lastPlaced.value = []
  chosenSize.value = null
  placeError.value = ''
}

const remaining = computed(() => remainingSizes(draft.value))
const currentSize = computed(() =>
  remaining.value.includes(chosenSize.value) ? chosenSize.value : (remaining.value[0] ?? null),
)
// Док: по одной плашке на каждый корабль флота, расставленные притушены.
const dock = computed(() => {
  const left = [...remaining.value]
  return FLEET.map((size, idx) => {
    const at = left.indexOf(size)
    if (at !== -1) left.splice(at, 1)
    return { idx, size, placed: at === -1 }
  })
})
const allCells = new Set(Array.from({ length: N * N }, (_, i) => i))

function onPlaceCell(cell) {
  placeError.value = ''
  const existing = draft.value.find((ship) => ship.includes(cell))
  if (existing) {
    draft.value = draft.value.filter((ship) => ship !== existing)
    chosenSize.value = existing.length
    lastPlaced.value = []
    haptic()?.selectionChanged()
    return
  }
  if (currentSize.value === null) {
    placeError.value = 'Флот расставлен. Нажмите на корабль, чтобы убрать его'
    return
  }
  const cells = fitShip(cell, currentSize.value, vertical.value)
  if (!canPlace(draft.value, cells)) {
    placeError.value = 'Сюда не встанет: корабли не должны касаться даже углами'
    haptic()?.notificationOccurred('error')
    return
  }
  draft.value = [...draft.value, cells]
  lastPlaced.value = cells
  chosenSize.value = null
  haptic()?.impactOccurred('light')
}

function shuffleFleet() {
  draft.value = randomFleet()
  lastPlaced.value = []
  placeError.value = ''
  haptic()?.impactOccurred('light')
}

async function submitFleet() {
  if (isBusy.value || remaining.value.length) return
  isBusy.value = true
  moveError.value = ''
  try {
    await sendMove({ action: 'place', ships: draft.value })
    haptic()?.notificationOccurred('success')
  } catch (err) {
    await moveFailed(err, 'Не удалось расставить флот')
  } finally {
    isBusy.value = false
  }
}

// ── Бой ──
const pendingCell = ref(null)
// Чем кончился мой последний выстрел — для подсказки.
const lastShot = ref(null)

const enemyClickable = computed(() => {
  const g = game.value
  if (!g || g.status !== 'playing' || !g.my_turn || isBusy.value) return []
  const shots = g.enemy_board.shots
  return Array.from({ length: N * N }, (_, i) => i).filter((c) => !(c in shots))
})

async function fire(cell) {
  if (isBusy.value) return
  isBusy.value = true
  moveError.value = ''
  pendingCell.value = cell
  const sunkBefore = game.value.enemy_board.ships.length
  try {
    const fresh = await sendMove({ action: 'fire', cell })
    const hit = fresh.enemy_board.shots[cell] === 'hit'
    const sunk = fresh.enemy_board.ships.length > sunkBefore && fresh.status !== 'finished'
    lastShot.value = { cell, outcome: sunk ? 'sunk' : hit ? 'hit' : 'miss' }
    if (hit) haptic()?.impactOccurred(sunk ? 'heavy' : 'medium')
  } catch (err) {
    await moveFailed(err, 'Выстрел не прошёл')
  } finally {
    pendingCell.value = null
    isBusy.value = false
  }
}

function resign() {
  if (!window.confirm('Сдаться? Партия будет проиграна.')) return
  isBusy.value = true
  sendMove({ action: 'resign' })
    .catch((err) => moveFailed(err, 'Не удалось сдаться'))
    .finally(() => (isBusy.value = false))
}

const hint = computed(() => {
  const g = game.value
  if (!g || g.status !== 'playing') return ''
  const shot = lastShot.value
  if (g.my_turn) {
    if (shot?.outcome === 'sunk') return `${cellLabel(shot.cell)} — потоплен! Стреляйте ещё`
    if (shot?.outcome === 'hit') return `${cellLabel(shot.cell)} — ранил! Стреляйте ещё`
    const incoming = g.my_board.recent.length
    if (incoming && g.vs_bot) return `Бот промахнулся после ${incoming} ${incoming === 1 ? 'выстрела' : 'выстрелов'} — ваш ход`
    return 'Ваш выстрел — выберите клетку на поле соперника'
  }
  if (shot?.outcome === 'miss') return `${cellLabel(shot.cell)} — мимо. Стреляет соперник…`
  return 'Стреляет соперник…'
})

const resultText = computed(() => ({
  win: 'Победа! Флот соперника на дне',
  lose: 'Ваш флот потоплен',
}[game.value?.result] ?? ''))

async function join() {
  isBusy.value = true
  readyOutcome.value = null
  try {
    applyGame(await joinSeaGame(code.value))
  } catch (err) {
    loadError.value = err.response?.data?.detail ?? 'Не удалось присоединиться'
  } finally {
    isBusy.value = false
  }
}

async function rematch() {
  const next = await createSeaGame(game.value.vs_bot)
  router.push({ name: 'sea', params: { code: next.code } })
}

// ── Приглашение ──
const inviteUrl = computed(
  () => game.value?.invite_url ?? `${window.location.origin}/games/sea/${code.value}`,
)
const inviteText = 'Сыграем в морской бой? Жми, чтобы сесть за стол'

async function inviteToChat() {
  isBusy.value = true
  chatInviteError.value = ''
  try {
    applyGame(await inviteSeaToChat(code.value))
    haptic()?.notificationOccurred('success')
  } catch (err) {
    chatInviteError.value = err.response?.data?.detail ?? 'Не удалось отправить приглашение'
  } finally {
    isBusy.value = false
  }
}

function shareInvite() {
  const tg = telegramApp()
  const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(inviteUrl.value)}&text=${encodeURIComponent(inviteText)}`
  if (tg) {
    tg.openTelegramLink(shareUrl)
  } else if (navigator.share) {
    navigator.share({ text: inviteText, url: inviteUrl.value }).catch(() => {})
  } else {
    window.open(shareUrl, '_blank', 'noopener')
  }
}

async function copyInvite() {
  try {
    await navigator.clipboard.writeText(inviteUrl.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    /* без доступа к буферу — остаётся «Отправить лично» */
  }
}

// Закрыть брошенное лобби: партия не останется висеть в «Моих партиях».
async function cancelGame() {
  if (!window.confirm('Закрыть лобби? Партия исчезнет из «Моих партий».')) return
  isBusy.value = true
  chatInviteError.value = ''
  try {
    await cancelSeaGame(code.value)
    router.push({ name: 'games' })
  } catch (err) {
    chatInviteError.value = err.response?.data?.detail ?? 'Не удалось закрыть лобби'
  } finally {
    isBusy.value = false
  }
}
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="battle">
        <div class="battle__head">
          <button class="battle__back" aria-label="К играм" @click="router.push({ name: 'games' })">
            <BaseIcon name="chevron-left" :size="18" />
          </button>
          <div class="battle__titles">
            <p class="breadcrumb">ИК · Игры / Морской бой</p>
            <h1>Морской бой</h1>
          </div>
          <button
            v-if="(game?.status === 'playing' || game?.status === 'placing') && game.seat !== null"
            class="battle__resign"
            :disabled="isBusy"
            @click="resign"
          >
            Сдаться
          </button>
        </div>

        <AppLoader v-if="!game && !loadError" />
        <p v-else-if="loadError && !game" class="battle__error">{{ loadError }}</p>

        <!-- Ждём соперника: приглашение -->
        <section v-else-if="game.status === 'waiting' && game.seat === 0" class="panel">
          <p v-if="readyOutcome === 'guest-missed'" class="panel__notice">
            Соперник не подтвердил участие — место снова свободно.
          </p>
          <p class="panel__title">Ждём соперника</p>
          <p v-if="game.chat_invite.sent" class="panel__text">
            Приглашение висит в чате актива. Кто первым нажмёт «Присоединиться» — садится за стол,
            кнопка тут же пропадёт.
          </p>
          <p v-else-if="game.chat_invite.available" class="panel__text">
            Позовите в чат актива — бот опубликует приглашение с кнопкой «Присоединиться».
            Или отправьте ссылку лично.
          </p>
          <p v-else class="panel__text">
            Отправьте ссылку тому, с кем хотите сыграть: партия начнётся, когда он нажмёт её
            и вы оба подтвердите участие.
          </p>
          <button
            v-if="game.chat_invite.available && !game.chat_invite.sent"
            class="create-btn panel__btn"
            :disabled="isBusy"
            @click="inviteToChat"
          >
            <BaseIcon name="send" :size="16" />
            Позвать в чат актива
          </button>
          <p v-if="chatInviteError" class="battle__error">{{ chatInviteError }}</p>
          <button
            :class="game.chat_invite.available && !game.chat_invite.sent ? 'panel__ghost' : 'create-btn panel__btn'"
            @click="shareInvite"
          >
            Отправить лично
          </button>
          <button class="panel__ghost" @click="copyInvite">
            {{ copied ? 'Ссылка скопирована' : 'Скопировать ссылку' }}
          </button>
          <button class="panel__ghost" :disabled="isBusy" @click="cancelGame">
            Закрыть лобби
          </button>
        </section>

        <!-- Пришли по приглашению -->
        <section v-else-if="game.can_join" class="panel">
          <p v-if="readyOutcome === 'me-missed'" class="panel__notice">
            Вы не успели подтвердить участие — место освободилось. Можно сесть снова, если никто не опередит.
          </p>
          <p class="panel__title">{{ game.opponent?.full_name }} зовёт сыграть</p>
          <p class="panel__text">
            Классический морской бой 10×10. После входа у обоих будет
            {{ READY_SECONDS }} секунд, чтобы подтвердить участие.
          </p>
          <button class="create-btn panel__btn" :disabled="isBusy" @click="join">Присоединиться</button>
        </section>

        <!-- Партия отменена -->
        <section v-else-if="game.status === 'cancelled'" class="panel">
          <p class="panel__title">Партия отменена</p>
          <p class="panel__text">
            {{ game.seat === 0
              ? 'Лобби закрыто или участие не подтвердили вовремя.'
              : 'Создатель закрыл лобби или не подтвердил участие.' }}
          </p>
          <button class="create-btn panel__btn" @click="router.push({ name: 'games' })">К играм</button>
        </section>

        <!-- Соперник найден: оба подтверждают участие за 5 секунд -->
        <section v-else-if="game.status === 'ready_check'" class="panel ready">
          <p class="panel__title">Соперник найден</p>
          <p class="panel__text">
            Вы против <b>{{ game.opponent?.full_name }}</b>. Подтвердите участие, пока не кончилось время.
          </p>
          <div class="ready__ring" :class="{ 'ready__ring--low': secondsLeft < 2 }">
            <svg viewBox="0 0 96 96" aria-hidden="true">
              <circle class="ready__track" cx="48" cy="48" r="40" />
              <circle
                class="ready__arc"
                cx="48"
                cy="48"
                r="40"
                :stroke-dasharray="RING"
                :stroke-dashoffset="ringOffset"
              />
            </svg>
            <span class="ready__seconds">{{ Math.ceil(secondsLeft) }}</span>
          </div>
          <div class="ready__players">
            <span class="ready__player" :class="{ 'ready__player--ok': game.ready?.me }">
              <BaseIcon v-if="game.ready?.me" name="check" :size="14" />
              Вы
            </span>
            <span class="ready__player" :class="{ 'ready__player--ok': game.ready?.opponent }">
              <BaseIcon v-if="game.ready?.opponent" name="check" :size="14" />
              {{ game.opponent?.full_name }}
            </span>
          </div>
          <button
            v-if="!game.ready?.me"
            class="create-btn panel__btn ready__btn"
            :disabled="isBusy || secondsLeft <= 0"
            @click="confirmReady"
          >
            Готов играть
          </button>
          <p v-else class="panel__text ready__wait">Ждём, пока подтвердит соперник…</p>
          <p v-if="moveError" class="battle__error">{{ moveError }}</p>
        </section>

        <!-- Расстановка флота -->
        <section v-else-if="game.status === 'placing' && !game.me?.placed" class="place">
          <p class="hint hint--turn">
            <template v-if="currentSize">
              Нажмите клетку — встанет {{ currentSize }}-палубный
              {{ vertical ? 'вниз' : 'вправо' }}
            </template>
            <template v-else>Флот готов — в бой!</template>
          </p>

          <div class="dock">
            <button
              v-for="ship in dock"
              :key="ship.idx"
              class="dock__ship"
              :class="{
                'dock__ship--placed': ship.placed,
                'dock__ship--current': !ship.placed && ship.size === currentSize,
              }"
              :disabled="ship.placed"
              :aria-label="`${ship.size}-палубный`"
              @click="chosenSize = ship.size"
            >
              <span v-for="n in ship.size" :key="n" class="dock__deck" />
            </button>
          </div>

          <div class="place__grid">
            <SeaGrid :ships="draft" :clickable="allCells" :marked="lastPlaced" @cell="onPlaceCell" />
          </div>
          <p v-if="placeError" class="battle__error place__error">{{ placeError }}</p>

          <div class="tools">
            <button class="tool" :class="{ 'tool--on': vertical }" @click="vertical = !vertical">
              <BaseIcon name="rotate" :size="16" />
              {{ vertical ? 'Вертикально' : 'Горизонтально' }}
            </button>
            <button class="tool" @click="shuffleFleet">
              <BaseIcon name="shuffle" :size="16" />
              Случайно
            </button>
            <button class="tool" :disabled="!draft.length" @click="resetDraft">
              <BaseIcon name="trash" :size="16" />
            </button>
          </div>

          <button
            class="create-btn action action--wide"
            :disabled="isBusy || remaining.length > 0"
            @click="submitFleet"
          >
            {{ remaining.length ? `Осталось кораблей: ${remaining.length}` : 'В бой' }}
          </button>
          <p v-if="moveError" class="battle__error">{{ moveError }}</p>
        </section>

        <!-- Флот расставлен, ждём соперника -->
        <section v-else-if="game.status === 'placing'" class="place">
          <p class="hint">{{ game.opponent?.full_name }} расставляет флот…</p>
          <div class="place__grid">
            <SeaGrid :ships="game.my_board.ships" />
          </div>
        </section>

        <!-- Бой -->
        <template v-else>
          <p v-if="game.status === 'finished'" class="result" :class="`result--${game.result}`">
            {{ resultText }}
          </p>
          <p v-else class="hint" :class="{ 'hint--turn': game.my_turn }">{{ hint }}</p>
          <p v-if="moveError" class="battle__error">{{ moveError }}</p>

          <div class="boards">
            <section class="board board--enemy" :class="{ 'board--active': game.my_turn && game.status === 'playing' }">
              <header class="board__head">
                <span class="board__name">{{ game.opponent?.full_name ?? 'Соперник' }}</span>
                <span class="fleet" :aria-label="`Осталось кораблей: ${game.opponent?.fleet.length ?? 0}`">
                  <span v-for="(size, i) in game.opponent?.fleet ?? []" :key="i" class="fleet__ship">
                    <span v-for="n in size" :key="n" class="fleet__deck" />
                  </span>
                </span>
              </header>
              <SeaGrid
                :ships="game.enemy_board.ships"
                :shots="game.enemy_board.shots"
                :clickable="enemyClickable"
                :pending="pendingCell"
                @cell="fire"
              />
            </section>

            <section class="board board--own">
              <header class="board__head">
                <span class="board__name">Ваш флот</span>
                <span class="board__count">{{ game.me?.fleet.length ?? 0 }} из {{ FLEET.length }}</span>
              </header>
              <SeaGrid
                compact
                :ships="game.my_board.ships"
                :shots="game.my_board.shots"
                :recent="game.status === 'playing' ? game.my_board.recent : []"
              />
            </section>
          </div>

          <div v-if="game.status === 'finished'" class="actions">
            <button class="create-btn action" @click="rematch">Ещё партию</button>
            <button class="action" @click="router.push({ name: 'games' })">К играм</button>
          </div>
        </template>
      </div>
    </main>
  </div>
</template>

<style scoped>
.battle {
  max-width: 760px;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.battle__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.battle__titles {
  flex: 1;
  min-width: 0;
}

.battle__back,
.battle__resign {
  height: var(--control-h);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-muted);
}

.battle__back {
  width: var(--control-h);
  display: flex;
  align-items: center;
  justify-content: center;
}

.battle__resign {
  padding: 0 12px;
  font-size: 13px;
}

.battle__resign:hover {
  color: var(--danger);
}

.battle__error {
  margin: 0;
  font-size: 13px;
  color: var(--danger);
}

/* Приглашение / присоединение — как в дураке */
.panel {
  max-width: 560px;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-5);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.panel__title {
  margin: 0;
  font: 500 18px/24px var(--font-display);
}

.panel__text {
  margin: 0;
  font-size: 14px;
  line-height: 21px;
  color: var(--text-muted);
}

.panel__ghost {
  height: var(--control-h);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text);
}

.panel__notice {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--prio-medium) 14%, transparent);
  color: var(--prio-medium);
  font-size: 13px;
}

.ready {
  align-items: center;
  text-align: center;
}

.ready__ring {
  position: relative;
  width: 112px;
  height: 112px;
  margin: var(--space-2) 0;
}

.ready__ring svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.ready__track {
  fill: none;
  stroke: var(--surface-raised);
  stroke-width: 8;
}

.ready__arc {
  fill: none;
  stroke: var(--success);
  stroke-width: 8;
  stroke-linecap: round;
  transition: stroke 0.2s ease;
}

.ready__ring--low .ready__arc {
  stroke: var(--danger);
}

.ready__seconds {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font: 500 24px/1 var(--font-display);
  font-variant-numeric: tabular-nums;
}

.ready__players {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  justify-content: center;
}

.ready__player {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 28px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  font-size: 13px;
  color: var(--text-muted);
}

.ready__player--ok {
  border-color: var(--success);
  color: var(--success);
}

.ready__btn {
  align-self: stretch;
}

.ready__wait {
  color: var(--text);
}

/* Расстановка */
.place {
  max-width: 440px;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.place__grid {
  padding: var(--space-3);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.place__error {
  text-align: center;
}

.dock {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  justify-content: center;
}

.dock__ship {
  display: flex;
  gap: 2px;
  padding: 6px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  transition: border-color 0.15s ease, opacity 0.15s ease;
}

.dock__ship--current {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}

.dock__ship--placed {
  opacity: 0.3;
}

.dock__deck {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  background: color-mix(in srgb, var(--accent) 70%, var(--surface-raised));
}

.tools {
  display: flex;
  gap: var(--space-2);
}

.tool {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: var(--control-h);
  padding: 0 12px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text);
  font-size: 14px;
}

.tool:last-child {
  flex: 0 0 var(--control-h);
  padding: 0;
}

.tool--on {
  border-color: var(--accent);
  color: var(--accent);
}

/* Поля */
.boards {
  display: flex;
  gap: var(--space-4);
  align-items: flex-start;
}

.board {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.board--enemy {
  flex: 1 1 440px;
  max-width: 440px;
}

.board--own {
  flex: 0 1 260px;
}

.board--active {
  border-color: color-mix(in srgb, var(--accent) 60%, transparent);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 30%, transparent);
}

.board__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-2);
  min-height: 20px;
}

.board__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
}

.board__count {
  font: 12px var(--font-mono);
  color: var(--text-muted);
}

/* Сколько кораблей соперника на плаву */
.fleet {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 4px;
}

.fleet__ship {
  display: flex;
  gap: 1px;
}

.fleet__deck {
  width: 6px;
  height: 6px;
  border-radius: 1px;
  background: var(--danger);
}

.hint {
  margin: 0;
  text-align: center;
  font-size: 14px;
  color: var(--text-muted);
}

.hint--turn {
  color: var(--text);
  font-weight: 600;
}

.result {
  margin: 0;
  text-align: center;
  font: 500 20px/26px var(--font-display);
}

.result--win { color: var(--success); }
.result--lose { color: var(--danger); }

.actions {
  display: flex;
  gap: var(--space-2);
  justify-content: center;
}

.action {
  flex: 1;
  max-width: 220px;
  height: var(--control-h-touch);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  background: var(--surface-raised);
  color: var(--text);
  font-weight: 600;
  font-size: 15px;
}

.action.create-btn {
  border: none;
  background: var(--success);
  color: var(--on-success);
}

.action--wide {
  max-width: none;
  flex: none;
}

.action.create-btn:disabled {
  background: var(--surface-raised);
  color: var(--text-muted);
}

@media (max-width: 768px) {
  .battle {
    gap: var(--space-3);
  }

  .battle__back,
  .battle__resign,
  .tool {
    height: var(--control-h-touch);
  }

  .battle__back,
  .tool:last-child {
    width: var(--control-h-touch);
    flex-basis: var(--control-h-touch);
  }

  /* На телефоне поле соперника во всю ширину, своё — под ним поменьше. */
  .boards {
    flex-direction: column;
    align-items: stretch;
    gap: var(--space-3);
  }

  .board--enemy {
    flex: none;
    max-width: none;
  }

  .board--own {
    flex: none;
    width: 62%;
    align-self: center;
  }

  .place__grid,
  .board {
    padding: var(--space-2);
  }
}
</style>
