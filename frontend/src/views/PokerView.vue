<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppSidebar from '../components/AppSidebar.vue'
import PlayingCard from '../components/PlayingCard.vue'
import { createPokerGame, fetchPokerGame, pokerLobbyAction, pokerNextHand, sendPokerMove } from '../api/games'

const route = useRoute()
const router = useRouter()
const game = ref(null)
const error = ref('')
const busy = ref(false)
const raiseTo = ref(40)
const code = computed(() => String(route.params.code).toUpperCase())
const me = computed(() => game.value?.players?.[game.value.seat] ?? null)
const isTurn = computed(() => game.value?.turn === game.value?.seat && game.value?.status === 'playing')
const minRaiseTo = computed(() => (game.value?.current_bet ?? 0) + (game.value?.min_raise ?? 20))
const canRaise = computed(() => me.value && me.value.stack + me.value.bet >= minRaiseTo.value)
const phaseNames = { preflop: 'Префлоп', flop: 'Флоп', turn: 'Тёрн', river: 'Ривер', showdown: 'Вскрытие' }
let timer = null

async function load() {
  try {
    if (code.value === 'NEW') {
      const fresh = await createPokerGame()
      await router.replace({ name: 'poker', params: { code: fresh.code } })
      game.value = fresh
      return
    }
    const fresh = await fetchPokerGame(code.value)
    game.value = fresh
    if (!raiseTo.value || raiseTo.value < fresh.current_bet + fresh.min_raise) {
      raiseTo.value = fresh.current_bet + fresh.min_raise
    }
    error.value = ''
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось загрузить стол'
  }
}

async function act(request) {
  busy.value = true
  error.value = ''
  try {
    game.value = await request()
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Действие не выполнено'
    await load()
  } finally {
    busy.value = false
  }
}

function lobby(action) {
  return act(() => pokerLobbyAction(code.value, action))
}

function move(action) {
  return act(() => sendPokerMove(code.value, {
    action,
    version: game.value.version,
    ...(action === 'raise' ? { amount: Number(raiseTo.value) } : {}),
  }))
}

async function copyInvite() {
  try {
    await navigator.clipboard.writeText(game.value.invite_url)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    error.value = 'Не удалось скопировать ссылку'
  }
}

const copied = ref(false)
onMounted(() => {
  load()
  timer = setInterval(() => { if (!document.hidden && code.value !== 'NEW' && !busy.value) load() }, 2000)
})
watch(code, load)
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <div class="app-layout">
    <AppSidebar />
    <main class="app-main">
      <div class="poker">
        <p class="breadcrumb"><router-link to="/games">ИК · Игры</router-link> / Покер</p>
        <h1>Техасский холдем</h1>
        <p class="subtitle">Стол {{ code }} · 2–6 человек · игровые фишки</p>
        <p v-if="error" class="error">{{ error }}</p>
        <template v-if="game">
          <div v-if="game.status === 'waiting'" class="panel">
            <h2>Собираем игроков</h2>
            <p>За столом {{ game.players.length }} из {{ game.max_players }}. Начать можно вдвоём.</p>
            <div class="players">
              <div v-for="player in game.players" :key="player.id" class="player">
                <strong>{{ player.name }}</strong><span>{{ player.stack }} фишек</span>
              </div>
            </div>
            <div class="actions">
              <button v-if="game.can_join" :disabled="busy" @click="lobby('join')">Сесть за стол</button>
              <button v-if="game.is_host" :disabled="busy || game.players.length < 2" @click="lobby('start')">Начать игру</button>
              <button v-if="game.seat !== null" class="secondary" :disabled="busy" @click="lobby('leave')">
                {{ game.is_host ? 'Распустить стол' : 'Выйти' }}
              </button>
            </div>
          </div>

          <template v-else-if="game.status === 'playing'">
            <div class="table">
              <div class="table-head"><strong>{{ phaseNames[game.phase] }}</strong><span>Банк: {{ game.pot }}</span></div>
              <div class="board">
                <PlayingCard v-for="(card, index) in game.board" :key="index" :card="card" size="table" />
                <PlayingCard v-for="index in 5 - game.board.length" :key="`empty-${index}`" :card="null" size="table" />
              </div>
              <div class="players">
                <div v-for="player in game.players" :key="player.id" class="player" :class="{ active: game.turn === player.seat, folded: player.folded }">
                  <div><strong>{{ player.name }}</strong><span v-if="player.seat === game.dealer"> · дилер</span></div>
                  <span>{{ player.stack }} фишек · ставка {{ player.bet }}</span>
                  <div v-if="player.cards?.length" class="hand">
                    <PlayingCard v-for="(card, index) in player.cards" :key="index" :card="card" size="mini" />
                  </div>
                  <small v-if="player.folded">Пас</small>
                </div>
              </div>
            </div>
            <div v-if="game.phase === 'showdown'" class="panel">
              <h2>Раздача завершена</h2>
              <p v-for="(amount, seat) in game.result?.payouts" :key="seat">
                {{ game.players[Number(seat)]?.name }} получает {{ amount }} фишек
              </p>
              <button v-if="game.is_host && game.can_continue" :disabled="busy" @click="act(() => pokerNextHand(code, game.version))">Следующая раздача</button>
              <p v-else-if="!game.can_continue">Победитель: {{ game.players.find((player) => player.stack > 0)?.name }}</p>
            </div>
            <div v-else-if="isTurn" class="panel">
              <h2>Ваш ход</h2>
              <p>Уравнять: {{ Math.min(game.to_call, me.stack) }} · фишек: {{ me.stack }}</p>
              <div class="actions">
                <button class="secondary" :disabled="busy" @click="move('fold')">Пас</button>
                <button :disabled="busy" @click="move(game.to_call ? 'call' : 'check')">{{ game.to_call ? 'Уравнять' : 'Чек' }}</button>
                <button class="secondary" :disabled="busy || !me.stack" @click="move('all_in')">Олл-ин</button>
              </div>
              <div v-if="canRaise" class="actions raise">
                <label>Повысить до <input v-model.number="raiseTo" type="number" :min="minRaiseTo" :max="me.stack + me.bet" step="10" /></label>
                <button :disabled="busy || raiseTo < minRaiseTo || raiseTo > me.stack + me.bet" @click="move('raise')">Повысить</button>
              </div>
            </div>
            <p v-else-if="game.phase !== 'showdown'" class="hint">Ходит {{ game.players[game.turn]?.name ?? 'другой игрок' }}</p>
            <button v-if="game.is_host" class="secondary stop" :disabled="busy" @click="lobby('stop')">Закрыть стол</button>
          </template>
          <div v-else class="panel"><h2>Стол закрыт</h2></div>

          <div v-if="game.status === 'waiting'" class="panel invite">
            <h2>Пригласить игроков</h2>
            <p>Отправьте ссылку тем, с кем хотите сыграть.</p>
            <div class="actions"><input :value="game.invite_url" readonly /><button @click="copyInvite">{{ copied ? 'Скопировано' : 'Копировать' }}</button></div>
          </div>
        </template>
      </div>
    </main>
  </div>
</template>

<style scoped>
.poker { max-width: 760px; }
.breadcrumb a { color: inherit; }
.subtitle, .hint { color: var(--text-muted); }
.panel, .table { margin-top: var(--space-5); padding: var(--space-5); border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--surface); }
.panel h2 { margin: 0 0 var(--space-3); font-size: 20px; }
.players { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: var(--space-3); margin: var(--space-4) 0; }
.player { display: flex; flex-direction: column; gap: 6px; min-height: 72px; padding: var(--space-3); background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius-md); }
.player span, .player small { color: var(--text-muted); font-size: 13px; }
.player.active { border-color: var(--accent); }
.player.folded { opacity: .5; }
.table { background: radial-gradient(circle at center, rgba(32, 157, 139, .28), var(--surface) 70%); }
.table-head { display: flex; justify-content: space-between; }
.board, .hand, .actions { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-2); }
.board { min-height: 108px; justify-content: center; margin: var(--space-5) 0; }
.hand { margin-top: auto; }
.actions { margin-top: var(--space-4); }
button { padding: 10px 15px; border: 0; border-radius: var(--radius-md); background: var(--accent); color: white; font: inherit; cursor: pointer; }
button.secondary { background: var(--bg); border: 1px solid var(--border); color: var(--text); }
button:disabled { opacity: .45; cursor: default; }
input { min-width: 0; max-width: 100%; padding: 10px; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--bg); color: var(--text); font: inherit; }
.raise input { width: 100px; }
.invite input { flex: 1; }
.error { color: var(--danger); }
.stop { margin-top: var(--space-5); }
</style>
