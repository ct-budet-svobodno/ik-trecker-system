<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import BaseIcon from '../components/BaseIcon.vue'
import PlayingCard from '../components/PlayingCard.vue'
import {
  cancelDurakGame,
  createDurakGame,
  fetchDurakGame,
  inviteDurakToChat,
  joinDurakGame,
  leaveDurakGame,
  readyDurakGame,
  sendDurakMove,
} from '../api/games'
import { suitName, suitSymbol } from '../utils/cards'
import { telegramApp } from '../utils/telegram'

const route = useRoute()
const router = useRouter()

const game = ref(null)
const loadError = ref('')
const moveError = ref('')
const isBusy = ref(false)
// Выбранная в руке карта, когда отбиваться ей можно сразу нескольких.
const selectedCard = ref(null)
const copied = ref(false)
// Соперник вышел из лобби до старта — у создателя место снова свободно.
const readyOutcome = ref(null)
const chatInviteError = ref('')

const code = computed(() => String(route.params.code).toUpperCase())

// ── Загрузка и опрос ──
// Пока ход у соперника (или ждём его прихода), раз в 1.5 с спрашиваем стол.
// version меняется с каждым ходом — по ней понимаем, что перерисовывать.
const POLL_MS = 1500
let pollTimer = null

function applyGame(fresh) {
  const prev = game.value
  if (
    prev?.status === 'ready_check'
    && fresh.status === 'waiting'
    && fresh.seat === 0
  ) {
    // Гость вышел из лобби: место снова свободно, создатель ждёт другого.
    readyOutcome.value = 'guest-left'
  }
  if (fresh.status === 'ready_check' && prev?.status !== 'ready_check') {
    readyOutcome.value = null
    telegramApp()?.HapticFeedback?.notificationOccurred('warning')
  }
  game.value = fresh
}

// /games/durak/new?vs=bot|human — новая партия (так открывают игру из бота).
async function startNew() {
  try {
    const fresh = await createDurakGame(route.query.vs !== 'human')
    router.replace({ name: 'durak', params: { code: fresh.code } })
  } catch {
    loadError.value = 'Не удалось начать партию'
  }
}

async function load() {
  if (code.value === 'NEW') return startNew()
  try {
    const fresh = await fetchDurakGame(code.value)
    const g = game.value
    const changed = !g || fresh.version !== g.version || fresh.status !== g.status
    if (changed || fresh.status === 'ready_check') {
      const becameMyTurn = fresh.status === 'playing' && fresh.my_turn && !g?.my_turn
      applyGame(fresh)
      if (changed) selectedCard.value = null
      if (becameMyTurn) telegramApp()?.HapticFeedback?.impactOccurred('light')
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
  pollTimer = setTimeout(async () => {
    if (!document.hidden) await load()
    schedulePoll()
  }, POLL_MS)
}

// ── Подтверждение участия ──
// Таймера нет: оба игрока жмут «Готов» столько, сколько нужно.
async function confirmReady() {
  if (isBusy.value) return
  isBusy.value = true
  try {
    applyGame(await readyDurakGame(code.value))
    telegramApp()?.HapticFeedback?.impactOccurred('medium')
  } catch (err) {
    moveError.value = err.response?.data?.detail ?? 'Не удалось подтвердить'
  } finally {
    isBusy.value = false
  }
}

watch(needsPolling, schedulePoll)
watch(code, async () => {
  game.value = null
  selectedCard.value = null
  readyOutcome.value = null
  moveError.value = ''
  loadError.value = ''
  chatInviteError.value = ''
  copied.value = false
  await load()
  schedulePoll()
})

onMounted(async () => {
  await load()
  schedulePoll()
})

onBeforeUnmount(() => {
  clearTimeout(pollTimer)
})

// ── Ходы ──

async function move(payload) {
  if (isBusy.value || !game.value) return
  isBusy.value = true
  moveError.value = ''
  try {
    game.value = await sendDurakMove(code.value, { ...payload, version: game.value.version })
    selectedCard.value = null
    if (game.value.result) {
      telegramApp()?.HapticFeedback?.notificationOccurred(game.value.result === 'lose' ? 'error' : 'success')
    }
  } catch (err) {
    if (err.response?.status === 409) {
      await load() // соперник успел сходить — просто перерисовываем
    } else {
      moveError.value = err.response?.data?.detail ?? 'Ход не прошёл'
      telegramApp()?.HapticFeedback?.notificationOccurred('error')
    }
  } finally {
    isBusy.value = false
  }
}

const legal = computed(() => game.value?.legal ?? { attack: [], defend: {}, take: false, finish: false })

// Какие непокрытые карты стола можно побить картой card.
function targetsFor(card) {
  return Object.entries(legal.value.defend)
    .filter(([, beaters]) => beaters.includes(card))
    .map(([target]) => Number(target))
}

function isPlayable(card) {
  return legal.value.attack.includes(card) || targetsFor(card).length > 0
}

function onHandCard(card) {
  if (isBusy.value) return
  const targets = targetsFor(card)
  if (targets.length === 1) {
    playCard({ action: 'defend', target: targets[0], card })
  } else if (targets.length > 1) {
    selectedCard.value = selectedCard.value === card ? null : card
  } else if (legal.value.attack.includes(card)) {
    playCard({ action: 'attack', card })
  }
}

function onTableCard(target) {
  if (selectedCard.value !== null && targetsFor(selectedCard.value).includes(target)) {
    playCard({ action: 'defend', target, card: selectedCard.value })
  }
}

// ── Ход картой ──
// Стол обновляем сразу, не дожидаясь сети, — нажатие отзывается мгновенно.
// Ответ сервера (в игре с ботом — с его реакцией) приходит следом.
function applyOptimistic(payload) {
  const g = game.value
  const table = g.table.map((row) => [...row])
  if (payload.action === 'attack') table.push([payload.card, null])
  else table.find((row) => row[0] === payload.target)[1] = payload.card
  game.value = {
    ...g,
    hand: g.hand.filter((c) => c !== payload.card),
    table,
    my_turn: false,
    legal: { attack: [], defend: {}, take: false, finish: false },
  }
}

async function playCard(payload) {
  if (isBusy.value || !game.value) return
  isBusy.value = true
  moveError.value = ''
  selectedCard.value = null
  const before = game.value
  applyOptimistic(payload)
  try {
    applyGame(await sendDurakMove(code.value, { ...payload, version: before.version }))
    if (game.value.result) {
      telegramApp()?.HapticFeedback?.notificationOccurred(game.value.result === 'lose' ? 'error' : 'success')
    }
  } catch (err) {
    if (err.response?.status === 409) {
      await load() // соперник успел сходить — просто перерисовываем
    } else {
      applyGame(before) // карта возвращается в руку
      moveError.value = err.response?.data?.detail ?? 'Ход не прошёл'
      telegramApp()?.HapticFeedback?.notificationOccurred('error')
    }
  } finally {
    isBusy.value = false
  }
}

// Игрок выбирает ход — неходовые карты притеняем; иначе рука просто лежит.
const isChoosing = computed(() => (game.value?.hand ?? []).some(isPlayable))

// Чем больше карт, тем сильнее нахлёст: рука должна помещаться в экран телефона.
const handOverlap = computed(() => {
  const n = game.value?.hand.length ?? 0
  if (n <= 5) return '-20px'
  if (n <= 7) return '-32px'
  if (n <= 10) return '-44px'
  return '-52px'
})

const selectableTargets = computed(() =>
  selectedCard.value === null ? [] : targetsFor(selectedCard.value),
)

function resign() {
  if (window.confirm('Сдаться? Партия будет проиграна.')) move({ action: 'resign' })
}

async function join() {
  isBusy.value = true
  readyOutcome.value = null
  try {
    applyGame(await joinDurakGame(code.value))
  } catch (err) {
    loadError.value = err.response?.data?.detail ?? 'Не удалось присоединиться'
  } finally {
    isBusy.value = false
  }
}

async function rematch() {
  const next = await createDurakGame(game.value.vs_bot)
  router.push({ name: 'durak', params: { code: next.code } })
}

// ── Подсказки ──

const iAttack = computed(() => game.value && game.value.seat === game.value.attacker)

const hint = computed(() => {
  const g = game.value
  if (!g || g.status !== 'playing') return ''
  const hasUncovered = g.table.some(([, dfn]) => dfn === null)
  if (iAttack.value) {
    if (!g.table.length) return 'Ваш ход — выберите карту'
    if (g.taking) return 'Соперник берёт — подкиньте или «Забирай»'
    if (hasUncovered) return 'Соперник отбивается…'
    return 'Всё побито — подкиньте или «Бито»'
  }
  if (g.taking) return 'Вы берёте — ждём, что ещё подкинут…'
  if (hasUncovered) {
    return selectedCard.value !== null ? 'Нажмите карту на столе, которую бьёте' : 'Отбивайтесь или берите'
  }
  return g.table.length ? 'Соперник думает, подкинуть ли ещё…' : 'Соперник ходит…'
})

const finishLabel = computed(() => (game.value?.taking ? 'Забирай' : 'Бито'))

const resultText = computed(() => ({
  win: 'Победа! Дурак — соперник',
  lose: 'Вы остались в дураках',
  draw: 'Ничья',
}[game.value?.result] ?? ''))

// ── Приглашение ──
// Ссылку даёт сервер: t.me/<бот>?startapp=durak_<код> открывает партию прямо
// в мини-аппе (если у бота настроен основной мини-апп), иначе — через личку с ботом.
const inviteUrl = computed(
  () => game.value?.invite_url ?? `${window.location.origin}/games/durak/${code.value}`,
)

const inviteText = 'Сыграем в дурака? Жми, чтобы сесть за стол'

// В чат актива приглашение публикует сам бот — с превью и кнопкой «Присоединиться»,
// которую он уберёт, как только место займут.
async function inviteToChat() {
  isBusy.value = true
  chatInviteError.value = ''
  try {
    applyGame(await inviteDurakToChat(code.value))
    telegramApp()?.HapticFeedback?.notificationOccurred('success')
  } catch (err) {
    chatInviteError.value = err.response?.data?.detail ?? 'Не удалось отправить приглашение'
  } finally {
    isBusy.value = false
  }
}

// Лично — через стандартное окно «Переслать» Telegram (или системное «Поделиться»).
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
  moveError.value = ''
  try {
    await cancelDurakGame(code.value)
    router.push({ name: 'games' })
  } catch (err) {
    moveError.value = err.response?.data?.detail ?? 'Не удалось закрыть лобби'
  } finally {
    isBusy.value = false
  }
}

// Гость передумал до старта: место освобождается, создатель ждёт другого.
async function leaveGame() {
  if (!window.confirm('Выйти из лобби? Место снова станет свободным.')) return
  isBusy.value = true
  moveError.value = ''
  try {
    await leaveDurakGame(code.value)
    router.push({ name: 'games' })
  } catch (err) {
    moveError.value = err.response?.data?.detail ?? 'Не удалось выйти из лобби'
  } finally {
    isBusy.value = false
  }
}
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="durak">
        <div class="durak__head">
          <button class="durak__back" aria-label="К играм" @click="router.push({ name: 'games' })">
            <BaseIcon name="chevron-left" :size="18" />
          </button>
          <div class="durak__titles">
            <p class="breadcrumb">ИК · Игры / Дурак</p>
            <h1>Дурак</h1>
          </div>
          <button
            v-if="game?.status === 'playing' && game.seat !== null"
            class="durak__resign"
            :disabled="isBusy"
            @click="resign"
          >
            Сдаться
          </button>
        </div>

        <AppLoader v-if="!game && !loadError" />
        <p v-else-if="loadError && !game" class="durak__error">{{ loadError }}</p>

        <!-- Ждём соперника: приглашение -->
        <section v-else-if="game.status === 'waiting' && game.seat === 0" class="panel">
          <p v-if="readyOutcome === 'guest-left'" class="panel__notice">
            Соперник вышел из лобби — место снова свободно.
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
          <p class="panel__text">
            Если никто не присоединится за 5 минут, лобби закроется автоматически.
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
          <p v-if="chatInviteError" class="durak__error">{{ chatInviteError }}</p>
          <p v-if="moveError" class="durak__error">{{ moveError }}</p>
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
          <p class="panel__title">{{ game.opponent?.full_name }} зовёт сыграть</p>
          <p class="panel__text">
            Подкидной дурак один на один, колода 36. После входа оба подтвердят участие.
          </p>
          <button class="create-btn panel__btn" :disabled="isBusy" @click="join">Присоединиться</button>
        </section>

        <!-- Партия отменена -->
        <section v-else-if="game.status === 'cancelled'" class="panel">
          <p class="panel__title">Партия отменена</p>
          <p class="panel__text">
            {{ game.seat === 0
              ? 'Лобби закрыто: возможно, за 5 минут никто не присоединился, или вы закрыли его сами.'
              : 'Создатель закрыл лобби.' }}
          </p>
          <button class="create-btn panel__btn" @click="router.push({ name: 'games' })">К играм</button>
        </section>

        <!-- Соперник найден: оба подтверждают участие без таймера -->
        <section v-else-if="game.status === 'ready_check'" class="panel ready">
          <p class="panel__title">Соперник найден</p>
          <p class="panel__text">
            Вы против <b>{{ game.opponent?.full_name }}</b>. Нажмите «Готов», когда будете готовы начать.
          </p>
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
            :disabled="isBusy"
            @click="confirmReady"
          >
            Готов играть
          </button>
          <p v-else class="panel__text ready__wait">Ждём, пока подтвердит соперник…</p>
          <button
            v-if="game.seat === 0"
            class="panel__ghost"
            :disabled="isBusy"
            @click="cancelGame"
          >
            Закрыть лобби
          </button>
          <button
            v-else
            class="panel__ghost"
            :disabled="isBusy"
            @click="leaveGame"
          >
            Выйти
          </button>
          <p v-if="moveError" class="durak__error">{{ moveError }}</p>
        </section>

        <!-- Стол -->
        <template v-else>
          <div class="seat seat--opponent">
            <span class="seat__name">
              {{ game.opponent?.full_name ?? 'Соперник' }}
              <span v-if="game.status === 'playing'" class="seat__role">
                {{ game.attacker === game.seat ? 'отбивается' : 'ходит' }}
              </span>
            </span>
            <div class="backs">
              <PlayingCard
                v-for="n in Math.min(game.opponent?.cards ?? 0, 12)"
                :key="n"
                :card="null"
                size="mini"
                class="backs__card"
              />
              <span class="backs__count">{{ game.opponent?.cards ?? 0 }}</span>
            </div>
          </div>

          <div class="board">
            <div class="deck">
              <div class="deck__stack">
                <PlayingCard
                  v-if="game.trump_card !== null"
                  :card="game.trump_card"
                  size="table"
                  trump
                  class="deck__trump"
                />
                <PlayingCard v-if="game.talon > 1" :card="null" size="table" class="deck__back" />
              </div>
              <span class="deck__info">
                <template v-if="game.talon">{{ game.talon }} в колоде</template>
                <template v-else>колода пуста</template>
              </span>
              <span class="deck__trump-label">
                козырь {{ suitSymbol(game.trump) }} {{ suitName(game.trump) }}
              </span>
            </div>

            <div class="table" :class="{ 'table--taking': game.taking }">
              <p v-if="!game.table.length" class="table__empty">
                {{ game.status === 'finished' ? '' : 'Стол пуст' }}
              </p>
              <button
                v-for="[att, dfn] in game.table"
                :key="att"
                class="pair"
                :class="{ 'pair--target': selectableTargets.includes(att) }"
                :disabled="!selectableTargets.includes(att)"
                @click="onTableCard(att)"
              >
                <PlayingCard :card="att" size="table" />
                <PlayingCard v-if="dfn !== null" :card="dfn" size="table" class="pair__def" />
              </button>
            </div>
          </div>

          <p v-if="game.status === 'finished'" class="result" :class="`result--${game.result}`">
            {{ resultText }}
          </p>
          <p v-else class="hint" :class="{ 'hint--turn': game.my_turn }">{{ hint }}</p>
          <p v-if="moveError" class="durak__error">{{ moveError }}</p>

          <div v-if="game.status === 'playing'" class="actions">
            <button v-if="legal.take" class="action action--take" :disabled="isBusy" @click="move({ action: 'take' })">
              Беру
            </button>
            <button v-if="legal.finish" class="action" :disabled="isBusy" @click="move({ action: 'finish' })">
              {{ finishLabel }}
            </button>
          </div>
          <div v-else class="actions">
            <button class="create-btn action" @click="rematch">Ещё партию</button>
            <button class="action" @click="router.push({ name: 'games' })">К играм</button>
          </div>

          <div
            v-if="game.hand.length"
            class="hand"
            :class="{ 'hand--choosing': isChoosing }"
            :style="{ '--overlap': handOverlap }"
          >
          <div class="hand__row">
            <button
              v-for="card in game.hand"
              :key="card"
              class="hand__card"
              :class="{
                'hand__card--playable': isPlayable(card),
                'hand__card--selected': selectedCard === card,
              }"
              :disabled="!isPlayable(card) || isBusy"
              @click="onHandCard(card)"
            >
              <PlayingCard :card="card" :trump="Math.floor(card / 13) === game.trump" />
            </button>
          </div>
          </div>

        </template>
      </div>
    </main>
  </div>
</template>

<style scoped>
.durak {
  max-width: 560px;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.durak__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.durak__titles {
  flex: 1;
  min-width: 0;
}

.durak__back,
.durak__resign {
  height: var(--control-h);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-muted);
}

.durak__back {
  width: var(--control-h);
  display: flex;
  align-items: center;
  justify-content: center;
}

.durak__resign {
  padding: 0 12px;
  font-size: 13px;
}

.durak__resign:hover {
  color: var(--danger);
}

.durak__error {
  margin: 0;
  font-size: 13px;
  color: var(--danger);
}

/* Подтверждение участия */
.ready {
  align-items: center;
  text-align: center;
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

.panel__notice {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--prio-medium) 14%, transparent);
  color: var(--prio-medium);
  font-size: 13px;
}

/* Приглашение / присоединение */
.panel {
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

/* Соперник */
.seat {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
}

.seat__name {
  font-size: 14px;
  font-weight: 600;
  min-width: 0;
}

.seat__role {
  display: block;
  font-size: 12px;
  font-weight: 400;
  color: var(--text-muted);
}

.backs {
  display: flex;
  align-items: center;
}

.backs__card + .backs__card {
  margin-left: -24px;
}

.backs__count {
  margin-left: var(--space-2);
  font: 13px var(--font-mono);
  color: var(--text-muted);
}

/* Стол: колода слева, пары справа */
.board {
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
  display: flex;
  gap: var(--space-4);
  padding: var(--space-4);
  min-height: 236px;
  background:
    radial-gradient(120% 90% at 50% 0%, color-mix(in srgb, var(--success) 10%, transparent), transparent 70%),
    var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.deck {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
  flex-shrink: 0;
  width: 84px;
}

.deck__stack {
  position: relative;
  width: 84px;
  height: 96px;
}

.deck__trump {
  position: absolute;
  left: 26px;
  top: 4px;
  transform: rotate(90deg);
}

.deck__back {
  position: absolute;
  left: 0;
  top: 4px;
}

.deck__info,
.deck__trump-label {
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
  line-height: 14px;
}

.table {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: var(--space-3) var(--space-2);
  border-radius: var(--radius-md);
  transition: box-shadow 0.2s ease;
}

.table--taking {
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--danger) 50%, transparent);
}

.table__empty {
  margin: auto;
  font-size: 13px;
  color: var(--text-faint);
}

.pair {
  position: relative;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  width: 86px;
  height: 124px;
  padding: 0;
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
}

.pair:disabled {
  cursor: default;
}

.pair__def {
  position: absolute;
  left: 22px;
  top: 34px;
  transform: rotate(6deg);
}

.pair--target {
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--success) 60%, transparent);
}

/* Подсказка и итог */
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
  min-height: var(--control-h-touch);
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

.action--take {
  border-color: color-mix(in srgb, var(--danger) 50%, transparent);
  color: var(--danger);
}

/* Рука: карты внахлёст, ходовые приподняты */
.hand {
  display: flex;
  padding: var(--space-4) var(--space-2) var(--space-2);
  overflow-x: auto;
  scrollbar-width: none;
}

/* Строка карт по центру через margin: auto, а не justify-content: при
   переполнении левые карты не уезжают за край и до них можно долистать.
   Центрируем строку целиком, а не крайние карты: уходящая (скрытая) карта
   ещё в DOM и сбивала бы :first-child — рука прыгала после хода. */
.hand__row {
  display: flex;
  width: max-content;
  margin: 0 auto;
  padding-left: calc(-1 * var(--overlap));
}

.hand::-webkit-scrollbar {
  display: none;
}

.hand__card {
  padding: 0;
  border: none;
  background: transparent;
  flex-shrink: 0;
  transition: transform 0.15s ease, filter 0.15s ease;
}

/* Нахлёст — у каждой карты, а у строки компенсация: без «+»-селектора соседей,
   иначе скрытая уходящая карта сбивала бы отступ следующей. */
.hand__card {
  margin-left: var(--overlap);
}

/* Притеняем, а не делаем прозрачными: внахлёст прозрачные карты просвечивают. */
.hand--choosing .hand__card:not(.hand__card--playable) {
  filter: brightness(0.5);
}

.hand__card:disabled {
  cursor: default;
}

.hand__card--playable {
  transform: translateY(-8px);
}

.hand__card--selected {
  transform: translateY(-18px);
}

.hand__card--selected :deep(.pcard) {
  box-shadow: 0 0 0 2px var(--success), 0 6px 14px rgba(0, 0, 0, 0.4);
}

@media (max-width: 768px) {
  .durak {
    gap: var(--space-3);
  }

  .durak__back,
  .durak__resign {
    height: var(--control-h-touch);
  }

  .durak__back {
    width: var(--control-h-touch);
  }

  .board {
    padding: var(--space-3);
    gap: var(--space-3);
  }

  /* Рука прижимается к таб-бару, чтобы до карт доставал большой палец. */
  .hand {
    margin: 0 calc(-1 * var(--space-4));
    padding-left: var(--space-4);
    padding-right: var(--space-4);
  }
}
</style>
