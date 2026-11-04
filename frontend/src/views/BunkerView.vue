<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import BaseIcon from '../components/BaseIcon.vue'
import { bunkerLobbyAction, createBunkerGame, fetchBunkerGame, sendBunkerMove } from '../api/games'
import { getAvatarColor, getInitials } from '../utils/avatar'
import { telegramApp } from '../utils/telegram'

const route = useRoute()
const router = useRouter()

const game = ref(null)
const loadError = ref('')
const moveError = ref('')
const isBusy = ref(false)
const copied = ref(false)

const code = computed(() => String(route.params.code).toUpperCase())
const haptic = () => telegramApp()?.HapticFeedback

// Характеристики в порядке карточки; цвет — фирменные цвета направлений ИК.
const CATEGORIES = [
  { key: 'profession', label: 'Профессия', color: 'var(--dir-ct)' },
  { key: 'biology', label: 'Биология', color: 'var(--dir-design)' },
  { key: 'health', label: 'Здоровье', color: 'var(--dir-prod-a)' },
  { key: 'hobby', label: 'Хобби', color: 'var(--dir-prod-b)' },
  { key: 'phobia', label: 'Характер', color: 'var(--dir-smi)' },
  { key: 'baggage', label: 'Багаж', color: 'var(--dir-nvk)' },
  { key: 'fact', label: 'Факт', color: 'var(--dir-photo)' },
]
// Ведущий-наблюдатель видит все карты: закрытые у игроков — бледнее.
const PHASES = { reveal: 'Открываем карты', discuss: 'Обсуждение', vote: 'Голосование', result: 'Итог голосования' }
// Ориентир на обсуждение: таймер не останавливает игру, ведёт создатель.
const DISCUSS_SECONDS = 180

// ── Загрузка и опрос ──
// Игроков много, и каждый действует сам по себе — опрашиваем всю партию.
const POLL_MS = 1500
let pollTimer = null

function applyGame(fresh) {
  const prev = game.value
  if (prev && fresh.phase !== prev.phase && fresh.status === 'playing') {
    haptic()?.impactOccurred('light')
    if (fresh.phase !== 'vote') pickedTarget.value = null
  }
  if (prev?.status === 'waiting' && fresh.status === 'playing') haptic()?.notificationOccurred('success')
  game.value = fresh
  startClock()
}

// /games/bunker/new — новое лобби (так открывают игру из бота).
async function startNew() {
  try {
    const fresh = await createBunkerGame()
    router.replace({ name: 'bunker', params: { code: fresh.code } })
  } catch {
    loadError.value = 'Не удалось собрать лобби'
  }
}

async function load() {
  if (code.value === 'NEW') return startNew()
  try {
    const fresh = await fetchBunkerGame(code.value)
    const g = game.value
    if (!g || fresh.version !== g.version || fresh.status !== g.status) applyGame(fresh)
    loadError.value = ''
  } catch (err) {
    loadError.value = err.response?.status === 404
      ? 'Партия не найдена или уже началась'
      : 'Не удалось загрузить партию'
  }
}

const needsPolling = computed(() => {
  const g = game.value
  return !g || g.status === 'waiting' || g.status === 'playing'
})

function schedulePoll() {
  clearTimeout(pollTimer)
  if (!needsPolling.value) return
  pollTimer = setTimeout(async () => {
    if (!document.hidden) await load()
    schedulePoll()
  }, POLL_MS)
}

// ── Часы фазы ──
const phaseSeconds = ref(0)
let clockTimer = null

function startClock() {
  clearInterval(clockTimer)
  const g = game.value
  if (!g || g.status !== 'playing') return
  const startedAt = performance.now() - g.phase_seconds * 1000
  const tick = () => (phaseSeconds.value = (performance.now() - startedAt) / 1000)
  tick()
  clockTimer = setInterval(tick, 500)
}

function clock(seconds) {
  const s = Math.max(0, Math.floor(seconds))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

const discussLeft = computed(() => DISCUSS_SECONDS - phaseSeconds.value)

watch(needsPolling, schedulePoll)
watch(code, async () => {
  game.value = null
  moveError.value = ''
  loadError.value = ''
  copied.value = false
  pickedTarget.value = null
  await load()
  schedulePoll()
})

onMounted(async () => {
  await load()
  schedulePoll()
})

onBeforeUnmount(() => {
  clearTimeout(pollTimer)
  clearInterval(clockTimer)
})

// ── Игроки ──
const me = computed(() => {
  const g = game.value
  return g && g.seat !== null ? g.players[g.seat] : null
})
const alive = computed(() => game.value?.players.filter((p) => !p.out) ?? [])
const nameOf = (seat) => game.value?.players[seat]?.full_name ?? 'Игрок'
const amActive = computed(() => !!me.value && !me.value.out)

// ── Действия ──
async function act(request, fallback) {
  if (isBusy.value) return false
  isBusy.value = true
  moveError.value = ''
  try {
    applyGame(await request())
    return true
  } catch (err) {
    if (err.response?.status === 409) await load()
    else {
      moveError.value = err.response?.data?.detail ?? fallback
      haptic()?.notificationOccurred('error')
    }
    return false
  } finally {
    isBusy.value = false
  }
}

const move = (payload, fallback) =>
  act(() => sendBunkerMove(code.value, { ...payload, version: game.value.version }), fallback)
const lobby = (action, fallback) => act(() => bunkerLobbyAction(code.value, action), fallback)

const canReveal = computed(
  () => game.value?.phase === 'reveal' && amActive.value && !me.value.revealed_now,
)

function reveal(category) {
  if (!canReveal.value || !me.value.hidden.includes(category)) return
  haptic()?.impactOccurred('medium')
  move({ action: 'reveal', category }, 'Не удалось открыть карту')
}

// Голос: сначала выбрать игрока, потом подтвердить — случайный тап не считается.
const pickedTarget = ref(null)
const canVote = computed(
  () => game.value?.phase === 'vote' && amActive.value && game.value.my_vote === null,
)

function isVotable(player) {
  const g = game.value
  if (!canVote.value || player.out || player.seat === g.seat) return false
  return !g.candidates || g.candidates.includes(player.seat)
}

function pick(player) {
  if (!isVotable(player)) return
  pickedTarget.value = pickedTarget.value === player.seat ? null : player.seat
  haptic()?.selectionChanged()
}

function castVote() {
  if (pickedTarget.value === null) return
  move({ action: 'vote', target: pickedTarget.value }, 'Голос не принят')
}

function stop() {
  const waiting = game.value.status === 'waiting'
  if (!window.confirm(waiting ? 'Распустить лобби?' : 'Остановить партию для всех?')) return
  move({ action: 'stop' }, 'Не удалось остановить')
}

// Сначала выходим из лобби, и только потом уходим со страницы: иначе при
// ошибке игрок остаётся в партии, а экран уже показывает список.
async function leave() {
  if (await lobby('leave', 'Не удалось выйти')) router.push({ name: 'games' })
}

async function newGame() {
  const next = await createBunkerGame()
  router.push({ name: 'bunker', params: { code: next.code } })
}

// ── Подсказка и кнопка ведущего ──
const waitingFor = computed(() => {
  const g = game.value
  if (!g || g.status !== 'playing') return []
  if (g.phase === 'reveal') return alive.value.filter((p) => !p.revealed_now)
  if (g.phase === 'vote') return alive.value.filter((p) => !p.voted)
  return []
})

const hint = computed(() => {
  const g = game.value
  if (!g || g.status !== 'playing') return ''
  if (g.observer) {
    if (g.phase === 'reveal') return 'Игроки открывают по карте. Вам видны все, закрытые — бледнее'
    if (g.phase === 'vote') return 'Игроки голосуют. Подведите итог, когда все проголосуют'
    if (g.phase === 'discuss') return g.to_exclude ? 'Обсуждение, потом голосование' : 'Обсуждение. В этом раунде без изгнания'
    return 'Объявите итог и ведите дальше'
  }
  if (!amActive.value) return 'Вы вне бункера — смотрите и болейте'
  if (g.phase === 'reveal') {
    return me.value.revealed_now
      ? 'Ждём, пока откроют остальные'
      : 'Откройте одну свою карту — нажмите на неё'
  }
  if (g.phase === 'discuss') {
    return g.to_exclude
      ? 'Доказывайте, почему вы нужны бункеру. Потом голосование'
      : 'Обсуждаем открытые карты. В этом раунде без изгнания'
  }
  if (g.phase === 'vote') {
    if (g.my_vote !== null) return `Ваш голос против: ${nameOf(g.my_vote)}`
    return g.candidates ? 'Переголосование: выберите одного из лидеров' : 'Выберите, кого не пускать в бункер'
  }
  return ''
})

const advanceLabel = computed(() => {
  const g = game.value
  if (!g) return ''
  if (g.phase === 'reveal') return 'Дальше без остальных'
  if (g.phase === 'vote') return 'Подвести итог'
  if (g.candidates) return 'Переголосовать'
  if (g.to_exclude > 0) return g.phase === 'result' ? 'Ещё голосование' : 'К голосованию'
  return g.round >= g.rounds ? 'Открыть итог' : 'Следующий раунд'
})

// В фазах, где ждём игроков, кнопка ведущего — запасная (вторичная).
const advanceIsPrimary = computed(() => ['discuss', 'result'].includes(game.value?.phase))

// ── Итог голосования ──
const tally = computed(() => {
  const result = game.value?.last_vote
  if (!result) return []
  const rows = {}
  for (const [voter, target] of Object.entries(result.votes)) {
    rows[target] ??= { seat: target, voters: [] }
    rows[target].voters.push(nameOf(Number(voter)))
  }
  return Object.values(rows).sort((a, b) => b.voters.length - a.voters.length)
})
const maxVotes = computed(() => Math.max(1, ...tally.value.map((r) => r.voters.length)))

const survivors = computed(() => alive.value.map((p) => p.full_name))

// ── Приглашение ──
const inviteUrl = computed(
  () => game.value?.invite_url ?? `${window.location.origin}/games/bunker/${code.value}`,
)
const inviteText = 'Собираем бункер — жми, чтобы попасть в лобби'

function shareInvite() {
  const tg = telegramApp()
  const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(inviteUrl.value)}&text=${encodeURIComponent(inviteText)}`
  if (tg) tg.openTelegramLink(shareUrl)
  else if (navigator.share) navigator.share({ text: inviteText, url: inviteUrl.value }).catch(() => {})
  else window.open(shareUrl, '_blank', 'noopener')
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
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="bunker">
        <div class="bunker__head">
          <button class="bunker__back" aria-label="К играм" @click="router.push({ name: 'games' })">
            <BaseIcon name="chevron-left" :size="18" />
          </button>
          <div class="bunker__titles">
            <p class="breadcrumb">ИК · Игры / Бункер</p>
            <h1>{{ game?.title ? `Бункер · ${game.title}` : 'Бункер' }}</h1>
          </div>
          <button
            v-if="game?.is_host && (game.status === 'waiting' || game.status === 'playing')"
            class="bunker__stop"
            :disabled="isBusy"
            @click="stop"
          >
            {{ game.status === 'waiting' ? 'Распустить' : 'Остановить' }}
          </button>
        </div>

        <AppLoader v-if="!game && !loadError" />
        <p v-else-if="loadError && !game" class="bunker__error">{{ loadError }}</p>

        <!-- Пришли по приглашению -->
        <section v-else-if="game.can_join" class="panel">
          <p class="panel__title">
            {{ game.title ? `Бункер · ${game.title}` : `${game.players[0]?.full_name} собирает бункер` }}
          </p>
          <p class="panel__text">
            Катастрофа, мест в убежище вдвое меньше, чем игроков. Обсуждаем вживую, карты и голосование —
            здесь. В лобби {{ game.players.length }} из {{ game.max_players }}.
          </p>
          <button class="create-btn panel__btn" :disabled="isBusy" @click="lobby('join', 'Не удалось войти')">
            {{ game.title ? 'Сесть за стол' : 'Присоединиться' }}
          </button>
        </section>

        <!-- Отменена -->
        <section v-else-if="game.status === 'cancelled'" class="panel">
          <p class="panel__title">Партия остановлена</p>
          <p class="panel__text">Создатель распустил лобби или остановил игру.</p>
          <button class="create-btn panel__btn" @click="router.push({ name: 'games' })">К играм</button>
        </section>

        <!-- Лобби -->
        <section v-else-if="game.status === 'waiting'" class="panel">
          <div class="lobby__top">
            <p class="panel__title">{{ game.title ? 'Состав стола' : 'Собираем выживших' }}</p>
            <span class="lobby__count">{{ game.players.length }}/{{ game.max_players }}</span>
          </div>
          <p class="panel__text">
            <template v-if="game.title && game.is_host">
              Вы ведёте этот стол{{ game.observer ? ' и сами не играете — вам будут видны все карты' : '' }}.
              Когда все сядут, раздайте карты.
            </template>
            <template v-else-if="game.title">
              Вы за этим столом. Карты раздаст ведущий, когда все соберутся, — экран обновится сам.
            </template>
            <template v-else-if="game.is_host">
              Позовите актив: нужно минимум {{ game.min_players }} человек. Начнёте, когда все соберутся.
            </template>
            <template v-else>Вы в лобби. Игра начнётся, когда создатель нажмёт «Начать».</template>
          </p>

          <ul class="lobby__list">
            <li v-for="p in game.players" :key="p.id" class="lobby__player">
              <span class="avatar" :style="{ background: getAvatarColor(p.id) }">{{ getInitials(p.full_name) }}</span>
              <span class="lobby__name">{{ p.full_name }}</span>
              <span v-if="p.is_host" class="lobby__tag">{{ game.title ? 'ведущий' : 'создатель' }}</span>
            </li>
            <li v-for="n in Math.max(0, game.min_players - game.players.length)" :key="`empty-${n}`" class="lobby__player lobby__player--empty">
              <span class="avatar avatar--empty" />
              <span class="lobby__name">Свободное место</span>
            </li>
          </ul>

          <template v-if="game.is_host">
            <button
              class="create-btn panel__btn"
              :disabled="isBusy || game.players.length < game.min_players"
              @click="lobby('start', 'Не удалось начать')"
            >
              <template v-if="game.players.length < game.min_players">
                Ещё {{ game.min_players - game.players.length }} — и можно начинать
              </template>
              <template v-else>{{ game.title ? 'Раздать карты' : 'Начать игру' }}</template>
            </button>
            <button
              v-if="game.chat_invite.available && !game.chat_invite.sent"
              class="panel__ghost"
              :disabled="isBusy"
              @click="lobby('invite-chat', 'Не удалось отправить приглашение')"
            >
              <BaseIcon name="send" :size="16" />
              Позвать в чат актива
            </button>
            <p v-else-if="game.chat_invite.sent" class="panel__text lobby__sent">
              <BaseIcon name="check" :size="14" /> Приглашение висит в чате актива
            </p>
            <div class="lobby__share">
              <button class="panel__ghost" @click="shareInvite">Отправить лично</button>
              <button class="panel__ghost" @click="copyInvite">{{ copied ? 'Скопировано' : 'Скопировать ссылку' }}</button>
            </div>
          </template>
          <template v-else>
            <div class="lobby__share">
              <button class="panel__ghost" @click="shareInvite">Позвать ещё</button>
              <button class="panel__ghost" :disabled="isBusy" @click="leave">Выйти из лобби</button>
            </div>
          </template>
          <p v-if="moveError" class="bunker__error">{{ moveError }}</p>
        </section>

        <!-- Игра и итог -->
        <template v-else>
          <div class="world">
            <section class="scene scene--disaster">
              <p class="scene__label">Катастрофа</p>
              <h2 class="scene__title">{{ game.catastrophe.title }}</h2>
              <p class="scene__text">{{ game.catastrophe.text }}</p>
              <p class="scene__meta">Сидеть в бункере: <b>{{ game.catastrophe.duration }}</b></p>
            </section>
            <section class="scene">
              <p class="scene__label">Бункер</p>
              <div class="seats">
                <span class="seats__num">{{ game.seats }}</span>
                <span class="seats__text">{{ game.seats === 1 ? 'место' : game.seats < 5 ? 'места' : 'мест' }} на {{ game.players.length }}</span>
              </div>
              <p class="scene__meta">{{ game.bunker.area }} м², запас {{ game.bunker.supplies }}</p>
              <ul class="rooms">
                <li v-for="room in game.bunker.rooms" :key="room">{{ room }}</li>
              </ul>
            </section>
          </div>

          <!-- Итог партии -->
          <section v-if="game.status === 'finished'" class="finale">
            <p class="scene__label">В бункер попали</p>
            <p class="finale__names">{{ survivors.join(', ') }}</p>
            <p class="panel__text">
              Все карты открыты. Решите вместе: выживет ли такая команда {{ game.catastrophe.duration }} под землёй?
            </p>
            <div class="finale__actions">
              <button class="create-btn" @click="newGame">Новая партия</button>
              <button class="panel__ghost" @click="router.push({ name: 'games' })">К играм</button>
            </div>
          </section>

          <!-- Ход раунда -->
          <section v-else class="stage">
            <div class="stage__top">
              <span class="stage__round">Раунд {{ game.round }} из {{ game.rounds }}</span>
              <span class="stage__phase">{{ PHASES[game.phase] }}</span>
              <span v-if="game.phase === 'discuss'" class="stage__clock" :class="{ 'stage__clock--over': discussLeft < 0 }">
                {{ discussLeft >= 0 ? clock(discussLeft) : `+${clock(-discussLeft)}` }}
              </span>
              <span v-else class="stage__clock stage__clock--quiet">{{ clock(phaseSeconds) }}</span>
            </div>
            <div class="steps" aria-hidden="true">
              <span v-for="n in game.rounds" :key="n" class="steps__dot" :class="{ 'steps__dot--done': n < game.round, 'steps__dot--now': n === game.round }" />
            </div>
            <p v-if="game.phase !== 'result' || game.to_exclude || game.candidates" class="stage__exclude">
              <template v-if="game.to_exclude">В этом раунде выбывает: {{ game.to_exclude }}</template>
              <template v-else-if="game.candidates">Ничья — переголосование</template>
              <template v-else>В этом раунде никто не выбывает</template>
            </p>

            <!-- Итог голосования -->
            <div v-if="game.phase === 'result' && game.last_vote" class="verdict">
              <p v-if="game.last_vote.out !== null" class="verdict__title">
                {{ game.last_vote.out === game.seat ? 'Вы не попадаете в бункер' : `${nameOf(game.last_vote.out)} не попадает в бункер` }}
              </p>
              <p v-else class="verdict__title">Ничья: {{ game.last_vote.leaders.map(nameOf).join(', ') }}</p>
              <p v-if="game.last_vote.lot" class="panel__text">Снова ничья — решил жребий.</p>
              <ul class="tally">
                <li v-for="row in tally" :key="row.seat" class="tally__row">
                  <span class="tally__name">{{ nameOf(row.seat) }}</span>
                  <span class="tally__bar"><span :style="{ width: `${(row.voters.length / maxVotes) * 100}%` }" /></span>
                  <span class="tally__num">{{ row.voters.length }}</span>
                  <span class="tally__voters">{{ row.voters.join(', ') }}</span>
                </li>
              </ul>
            </div>

            <p class="stage__hint" :class="{ 'stage__hint--turn': canReveal || (canVote && pickedTarget === null) }">{{ hint }}</p>
            <p v-if="waitingFor.length" class="stage__waiting">
              Ждём: {{ waitingFor.map((p) => p.full_name).join(', ') }}
            </p>

            <button v-if="canVote && pickedTarget !== null" class="create-btn stage__btn" :disabled="isBusy" @click="castVote">
              Голосую против: {{ nameOf(pickedTarget) }}
            </button>
            <button
              v-if="game.is_host"
              :class="advanceIsPrimary ? 'create-btn stage__btn' : 'panel__ghost stage__btn'"
              :disabled="isBusy || (game.phase === 'vote' && !game.players.some((p) => p.voted))"
              @click="move({ action: 'advance' }, 'Не удалось перейти дальше')"
            >
              {{ advanceLabel }}
            </button>
            <p v-if="moveError" class="bunker__error">{{ moveError }}</p>
          </section>

          <!-- Мой персонаж -->
          <section v-if="me && game.status === 'playing'" class="hero">
            <header class="section-head">
              <h2 class="section-head__title">Ваш персонаж</h2>
              <span class="section-head__meta">{{ me.out ? `Выбыли в раунде ${me.out_round}` : `Закрыто карт: ${me.hidden.length}` }}</span>
            </header>
            <div class="cards">
              <button
                v-for="cat in CATEGORIES"
                :key="cat.key"
                class="trait"
                :class="{
                  'trait--hidden': me.hidden.includes(cat.key),
                  'trait--pickable': canReveal && me.hidden.includes(cat.key),
                }"
                :style="{ '--cat': cat.color }"
                :disabled="!(canReveal && me.hidden.includes(cat.key)) || isBusy"
                @click="reveal(cat.key)"
              >
                <span class="trait__label">
                  <span class="trait__dot" />
                  {{ cat.label }}
                  <BaseIcon v-if="me.hidden.includes(cat.key)" name="lock" :size="12" class="trait__lock" />
                </span>
                <span class="trait__value">{{ me.cards[cat.key] }}</span>
                <span v-if="canReveal && me.hidden.includes(cat.key)" class="trait__action">Открыть</span>
              </button>
            </div>
          </section>

          <!-- Игроки -->
          <section class="table">
            <header class="section-head">
              <h2 class="section-head__title">{{ game.status === 'finished' ? 'Все карты' : 'Игроки' }}</h2>
              <span class="section-head__meta">В игре {{ alive.length }} из {{ game.players.length }}</span>
            </header>
            <div class="players">
              <article
                v-for="p in game.players"
                :key="p.id"
                class="player"
                :class="{
                  'player--out': p.out,
                  'player--me': p.seat === game.seat,
                  'player--votable': isVotable(p),
                  'player--picked': pickedTarget === p.seat && canVote,
                  'player--saved': game.status === 'finished' && !p.out,
                }"
                :role="isVotable(p) ? 'button' : undefined"
                :tabindex="isVotable(p) ? 0 : undefined"
                @click="pick(p)"
                @keydown.enter="pick(p)"
              >
                <header class="player__head">
                  <span class="avatar" :style="{ background: getAvatarColor(p.id) }">{{ getInitials(p.full_name) }}</span>
                  <span class="player__name">{{ p.full_name }}{{ p.seat === game.seat ? ' · вы' : '' }}</span>
                  <span v-if="p.out" class="player__badge player__badge--out">выбыл · р{{ p.out_round }}</span>
                  <span v-else-if="game.status === 'finished'" class="player__badge player__badge--saved">в бункере</span>
                  <span v-else-if="game.phase === 'reveal' && p.revealed_now" class="player__badge"><BaseIcon name="check" :size="12" /> открыл</span>
                  <span v-else-if="game.phase === 'vote' && p.voted" class="player__badge"><BaseIcon name="check" :size="12" /> голос</span>
                </header>
                <ul class="player__traits">
                  <template v-for="cat in CATEGORIES" :key="cat.key">
                    <li
                      v-if="p.seat !== game.seat ? p.cards[cat.key] : !p.hidden.includes(cat.key)"
                      class="mini"
                      :class="{ 'mini--hidden': game.observer && p.hidden.includes(cat.key) }"
                      :style="{ '--cat': cat.color }"
                    >
                      <span class="mini__label">{{ cat.label }}</span>
                      <span class="mini__value">{{ p.cards[cat.key] }}</span>
                    </li>
                  </template>
                </ul>
              </article>
            </div>
          </section>
        </template>
      </div>
    </main>
  </div>
</template>

<style scoped>
.bunker {
  max-width: 980px;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.bunker__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.bunker__titles {
  flex: 1;
  min-width: 0;
}

.bunker__back,
.bunker__stop {
  height: var(--control-h);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-muted);
}

.bunker__back {
  width: var(--control-h);
  display: flex;
  align-items: center;
  justify-content: center;
}

.bunker__stop {
  padding: 0 12px;
  font-size: 13px;
}

.bunker__stop:hover {
  color: var(--danger);
}

.bunker__error {
  margin: 0;
  font-size: 13px;
  color: var(--danger);
}

/* Лобби и служебные панели — как в дураке и морском бое */
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
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: 0 14px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text);
  font-size: 14px;
}

.panel__ghost:hover:not(:disabled) {
  background: var(--surface-hover);
}

.lobby__top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.lobby__count {
  font: 500 14px var(--font-mono);
  color: var(--text-muted);
}

.lobby__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--space-2);
}

.lobby__player {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-raised);
}

.lobby__player--empty {
  border-style: dashed;
  background: transparent;
  color: var(--text-faint);
}

.lobby__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}

.lobby__tag {
  font-size: 11px;
  color: var(--text-muted);
}

.lobby__share {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}

.lobby__sent {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--success);
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

.avatar--empty {
  border: 1px dashed var(--border-strong);
}

/* Сцена: катастрофа и бункер */
.world {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
  gap: var(--space-3);
}

.scene {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-5);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

/* Фирменный градиент Прода — только полосой сверху, карточка остаётся ровной. */
.scene--disaster {
  position: relative;
  overflow: hidden;
}

.scene--disaster::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  background: var(--dir-prod);
}

.scene__label {
  margin: 0;
  font: 500 11px var(--font-mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.scene__title {
  margin: 0;
  font: 500 24px/30px var(--font-display);
}

.scene__text {
  margin: 0;
  font-size: 14px;
  line-height: 21px;
  color: var(--text-muted);
}

.scene__meta {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.scene__meta b {
  color: var(--text);
  font-weight: 600;
}

.seats {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}

.seats__num {
  font: 500 24px/30px var(--font-display);
  color: var(--success);
}

.seats__text {
  font-size: 14px;
  color: var(--text-muted);
}

.rooms {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.rooms li {
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  background: var(--surface-raised);
  border: 1px solid var(--border);
  font-size: 12px;
}

/* Ход раунда */
.stage,
.finale {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-5);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.stage__top {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.stage__round {
  font: 500 12px var(--font-mono);
  color: var(--text-muted);
}

.stage__phase {
  flex: 1;
  font: 500 18px/24px var(--font-display);
}

.stage__clock {
  font: 500 20px var(--font-mono);
  color: var(--success);
}

.stage__clock--over {
  color: var(--prio-high);
}

.stage__clock--quiet {
  font-size: 14px;
  color: var(--text-faint);
}

.steps {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--space-1);
}

.steps__dot {
  height: 4px;
  border-radius: var(--radius-full);
  background: var(--border);
}

.steps__dot--done {
  background: var(--text-faint);
}

.steps__dot--now {
  background: var(--success);
}

.stage__exclude {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.stage__hint {
  margin: 0;
  font-size: 15px;
  color: var(--text-muted);
}

.stage__hint--turn {
  color: var(--text);
  font-weight: 600;
}

.stage__waiting {
  margin: 0;
  font-size: 12px;
  color: var(--text-faint);
}

.stage__btn {
  align-self: flex-start;
}

.verdict {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4);
  border-radius: var(--radius-md);
  background: var(--surface-raised);
}

.verdict__title {
  margin: 0;
  font: 500 18px/24px var(--font-display);
  color: var(--danger);
}

.tally {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.tally__row {
  display: grid;
  grid-template-columns: minmax(90px, 160px) minmax(0, 1fr) 24px;
  align-items: center;
  gap: var(--space-2);
  font-size: 13px;
}

.tally__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tally__bar {
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--border);
  overflow: hidden;
}

.tally__bar span {
  display: block;
  height: 100%;
  background: var(--danger);
}

.tally__num {
  font-family: var(--font-mono);
  text-align: right;
}

.tally__voters {
  grid-column: 1 / -1;
  margin-top: -4px;
  font-size: 12px;
  color: var(--text-faint);
}

.finale__names {
  margin: 0;
  font: 500 20px/26px var(--font-display);
  color: var(--success);
}

.finale__actions {
  display: flex;
  gap: var(--space-2);
}

/* Секции */
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.section-head__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.section-head__meta {
  font-size: 12px;
  color: var(--text-muted);
}

/* Мои карты */
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--space-2);
}

.trait {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1);
  min-height: 84px;
  padding: var(--space-3);
  border: 1px solid color-mix(in srgb, var(--cat) 45%, var(--border));
  border-radius: var(--radius-lg);
  background: color-mix(in srgb, var(--cat) 12%, var(--surface));
  color: var(--text);
  text-align: left;
  transition: transform 0.15s, border-color 0.15s;
}

.trait:disabled {
  cursor: default;
  opacity: 1;
}

.trait--hidden {
  border-style: dashed;
  background: var(--surface);
  border-color: var(--border-strong);
}

.trait--hidden .trait__value {
  color: var(--text-muted);
}

.trait--pickable {
  border-color: var(--cat);
  cursor: pointer;
}

.trait--pickable:hover {
  transform: translateY(-2px);
  background: color-mix(in srgb, var(--cat) 10%, var(--surface));
}

.trait__label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
}

.trait__dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--cat);
}

.trait__lock {
  color: var(--text-faint);
}

.trait__value {
  font-size: 14px;
  line-height: 20px;
  font-weight: 500;
}

.trait__action {
  margin-top: auto;
  font-size: 12px;
  font-weight: 600;
  color: var(--success);
}

/* Игроки за столом */
.players {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: var(--space-2);
}

.player {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  transition: border-color 0.15s, transform 0.15s;
}

.player--me {
  border-color: var(--border-strong);
}

.player--out {
  opacity: 0.55;
}

.player--saved {
  border-color: color-mix(in srgb, var(--success) 60%, var(--border));
}

.player--votable {
  cursor: pointer;
}

.player--votable:hover {
  border-color: var(--danger);
  transform: translateY(-2px);
}

.player--picked {
  border-color: var(--danger);
  background: color-mix(in srgb, var(--danger) 10%, var(--surface));
}

.player__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.player__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  font-weight: 600;
}

.player__badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  font-size: 11px;
  color: var(--success);
}

.player__badge--out {
  color: var(--danger);
}

.player__traits {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.mini {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: var(--space-2);
  font-size: 13px;
  line-height: 18px;
}

.mini--hidden .mini__value {
  color: var(--text-faint);
}

.mini__label {
  position: relative;
  padding-left: 12px;
  font-size: 12px;
  color: var(--text-muted);
}

.mini__label::before {
  content: '';
  position: absolute;
  left: 0;
  top: 6px;
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--cat);
}

@media (max-width: 768px) {
  .bunker {
    gap: var(--space-3);
  }

  .bunker__back,
  .bunker__stop,
  .panel__ghost {
    height: var(--control-h-touch);
  }

  .panel,
  .scene,
  .stage,
  .finale {
    padding: var(--space-4);
  }

  .world {
    grid-template-columns: minmax(0, 1fr);
  }

  .scene__title {
    font-size: 20px;
    line-height: 26px;
  }

  .cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .trait {
    min-height: 76px;
  }

  .stage__btn,
  .panel__btn {
    align-self: stretch;
    height: var(--control-h-touch);
  }

  .lobby__share {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (prefers-reduced-motion: reduce) {
  .trait,
  .player {
    transition: none;
  }

  .trait--pickable:hover,
  .player--votable:hover {
    transform: none;
  }
}
</style>
