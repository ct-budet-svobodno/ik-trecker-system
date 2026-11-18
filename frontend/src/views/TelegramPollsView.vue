<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import AppSidebar from '../components/AppSidebar.vue'
import AppLoader from '../components/AppLoader.vue'
import { fetchPolls, createPoll, fetchPoll, closePoll, addPollChat } from '../api/telegramPolls'

const overview = ref(null)
const active = ref(null)
const text = ref('')
const destination = ref('group')
const chatId = ref('')
const newChatId = ref('')
const addingChat = ref(false)
const options = ref(['Да', 'Нет'])
const selected = ref([])
const audienceSearch = ref('')
const resultSearch = ref('')
const filter = ref('all')
const busy = ref(false)
const error = ref('')
const targetChat = computed(() => overview.value?.chats?.find(chat => String(chat.id) === chatId.value))
let timer
let stopped = false
const people = computed(() => (overview.value?.audience ?? []).filter(u => u.full_name.toLowerCase().includes(audienceSearch.value.toLowerCase())))
const rows = computed(() => (active.value?.recipients ?? []).filter(r =>
  (r.full_name + ' ' + (r.telegram_username ?? '')).toLowerCase().includes(resultSearch.value.toLowerCase()) &&
  (filter.value === 'all' || (filter.value === 'waiting' ? r.choice === null :
    filter.value === 'failed' ? ['failed', 'no_telegram'].includes(r.delivery) : r.choice === Number(filter.value)))))
const deliveryLabels = { pending: 'Ожидает отправки', sending: 'Отправляется', sent: 'Отправлено', failed: 'Не доставлено', no_telegram: 'Нет Telegram' }
function selectAll(activists = false) {
  selected.value = overview.value.audience.filter(u => !activists || u.is_activist).map(u => u.id)
}
async function load() {
  try {
    const [data, detail] = await Promise.all([fetchPolls(), active.value ? fetchPoll(active.value.id) : null])
    const firstLoad = !overview.value
    overview.value = data
    if (firstLoad && data.chats?.length === 1) chatId.value = String(data.chats[0].id)
    if (detail) active.value = detail
  } catch { error.value = 'Не удалось загрузить опросы' }
  clearTimeout(timer)
  if (!stopped) timer = setTimeout(load, 5000)
}
async function open(id) {
  try { active.value = await fetchPoll(id); filter.value = 'all'; resultSearch.value = ''; error.value = '' }
  catch { error.value = 'Не удалось открыть результаты' }
}
async function addChat() {
  const value = newChatId.value.trim()
  if (!/^-\d+$/.test(value) || !Number.isSafeInteger(Number(value))) {
    error.value = 'Введите числовой Chat ID группы, например -1001234567890'; return
  }
  addingChat.value = true; error.value = ''
  try {
    const chat = await addPollChat(Number(value))
    await load(); chatId.value = String(chat.id); destination.value = 'group'; newChatId.value = ''
  } catch (e) { error.value = typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Не удалось добавить чат' }
  finally { addingChat.value = false }
}
async function send() {
  if (destination.value === 'group' && !targetChat.value) {
    error.value = 'Выберите чат, в котором нужно опубликовать опрос'; return
  }
  if (!text.value.trim() || options.value.some(o => !o.trim()) || new Set(options.value.map(o => o.trim())).size !== options.value.length) {
    error.value = 'Напишите сообщение и разные непустые варианты ответа'; return
  }
  if (!selected.value.length) { error.value = 'Выберите получателей'; return }
  if (!window.confirm(`Отправить опрос ${destination.value === 'group' ? `в чат «${targetChat.value.title}»` : 'в личные сообщения'}? Ожидаем ответы от ${selected.value.length} участников.`)) return
  busy.value = true; error.value = ''
  try {
    active.value = await createPoll({ text: text.value, options: options.value, user_ids: selected.value, chat_id: destination.value === 'group' ? Number(chatId.value) : null })
    text.value = ''; options.value = ['Да', 'Нет']; filter.value = 'all'; resultSearch.value = ''
    await load()
  } catch (e) { error.value = typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Не удалось отправить опрос' }
  finally { busy.value = false }
}
async function close() {
  if (!window.confirm('Закрыть опрос? Новые ответы и изменения больше не принимаются.')) return
  busy.value = true
  try { active.value = await closePoll(active.value.id); await load() }
  catch { error.value = 'Не удалось закрыть опрос' }
  finally { busy.value = false }
}
function exportRows() {
  // Префикс предотвращает выполнение формул при открытии CSV в таблицах.
  const cell = v => '"' + String(v ?? '').replace(/^[=+\-@\t\r]/, "'$&").replace(/"/g, '""') + '"'
  const lines = [['ФИО', 'Telegram', 'Ответ', 'Доставка'], ...rows.value.map(r => [
    r.full_name, r.telegram_username ? '@' + r.telegram_username : '',
    r.choice === null ? 'Не проголосовал' : active.value.options[r.choice], deliveryLabels[r.delivery],
  ])]
  const url = URL.createObjectURL(new Blob(['\ufeff' + lines.map(line => line.map(cell).join(';')).join('\r\n')], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a'); a.href = url; a.download = `opros-${active.value.id}-${filter.value}.csv`; a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
onMounted(load)
onBeforeUnmount(() => { stopped = true; clearTimeout(timer) })
</script>

<template>
  <div class="app-layout">
    <AppSidebar />
    <main class="app-main polls">
      <p class="breadcrumb">ИК · Администрирование</p>
      <h1>Опросы в Telegram</h1>
      <p class="subtitle">Создайте опрос для общего чата. Бот опубликует сообщение с кнопками, участники выберут ответ прямо в Telegram, а вы увидите результаты и список не проголосовавших здесь.</p>
      <p v-if="error" role="alert" class="error">{{ error }}</p>
      <AppLoader v-if="!overview && !error" />
      <template v-if="overview">
        <p v-if="!overview.enabled" class="error">Бот не подключён — отправка недоступна.</p>
        <div class="columns">
          <form class="card" @submit.prevent="send">
            <h2>Новый опрос</h2>
            <label>Способ публикации
              <select v-model="destination" aria-label="Способ публикации"><option value="group">Один опрос в общем чате</option><option value="personal">Отправить каждому в личные сообщения</option></select>
            </label>
            <label v-if="destination === 'group'">Чат для опроса
              <select v-model="chatId" aria-label="Куда отправить опрос" required><option value="" disabled>Выберите чат</option><option v-for="chat in overview.chats ?? []" :key="chat.id" :value="String(chat.id)">{{ chat.title }} · {{ chat.id }}</option></select>
            </label>
            <details v-if="destination === 'group'" :open="!overview.chats?.length"><summary>Добавить чат</summary>
              <p><small>Добавьте бота в группу, напишите в ней /chatid и вставьте полученный номер. Название проверим автоматически.</small></p>
              <div class="option"><input v-model="newChatId" aria-label="Chat ID группы" placeholder="-1001234567890" inputmode="text" /><button type="button" :disabled="addingChat || !overview.enabled" @click="addChat">{{ addingChat ? 'Проверяем…' : 'Добавить чат' }}</button></div>
            </details>
            <p v-if="destination === 'group'"><small><template v-if="targetChat">Опрос появится в чате «{{ targetChat.title }}».</template> Голосовать смогут выбранные ниже участники с подключённым Telegram. Выберите тех, от кого ждёте ответ: по этому списку определим не проголосовавших. Состав группы автоматически не загружается.</small></p>
            <label>Сообщение<textarea v-model="text" rows="5" maxlength="3000" required /></label>
            <small>Разметка: **жирный**, __курсив__. Один ответ на участника, выбор можно изменить до закрытия.</small>
            <label v-for="(_, i) in options" :key="i">Вариант {{ i + 1 }}
              <span class="option"><input v-model="options[i]" maxlength="64" required :aria-label="`Вариант ${i + 1}`" />
                <button v-if="options.length > 2" type="button" @click="options.splice(i, 1)" :aria-label="`Удалить вариант ${i + 1}`">Удалить</button></span>
            </label>
            <button type="button" :disabled="options.length >= 8" @click="options.push('')">Добавить вариант</button>
            <h3>{{ destination === 'group' ? 'От кого ждём ответ' : 'Получатели' }} · {{ selected.length }}</h3>
            <div class="tools"><button type="button" @click="selectAll()">Все участники</button><button type="button" @click="selectAll(true)">Весь актив</button><button type="button" @click="selected = []">Снять выбор</button></div>
            <input v-model="audienceSearch" placeholder="Найти участника" aria-label="Поиск получателей" />
            <div class="audience">
              <label v-for="u in people" :key="u.id" class="person"><input v-model="selected" type="checkbox" :value="u.id" /><span>{{ u.full_name }}<small v-if="!u.telegram_linked">Нет Telegram — голосование недоступно</small></span></label>
            </div>
            <button class="create-btn" :disabled="busy || !overview.enabled || !selected.length || (destination === 'group' && !targetChat)">{{ busy ? 'Отправляем…' : destination === 'group' ? 'Опубликовать опрос в чате' : 'Отправить в личные сообщения' }}</button>
          </form>
          <section class="card history">
            <h2>Отправленные опросы</h2>
            <p v-if="!overview.items.length">Пока нет опросов.</p>
            <button v-for="p in overview.items" :key="p.id" class="history-item" :class="{ chosen: active?.id === p.id }" @click="open(p.id)">
              <strong>{{ p.text }}</strong><small>{{ p.chat_title || 'Личные сообщения' }} · {{ p.closed ? 'Закрыт' : 'Приём ответов' }} · {{ p.voted }}/{{ p.total }} ответили</small>
            </button>
          </section>
        </div>
        <section v-if="active" class="card results">
          <div class="tools"><h2>Результаты · #{{ active.id }}</h2><button @click="open(active.id)">Обновить</button><button v-if="!active.closed" :disabled="busy" @click="close">Закрыть опрос</button><span v-else>Опрос закрыт</span></div>
          <p class="question">{{ active.text }}</p>
          <p><small>Отправлено: {{ active.chat_title || 'в личные сообщения' }}<template v-if="active.chat_id"> · {{ active.chat_id }}</template></small></p>
          <p>{{ active.voted }} из {{ active.total }} проголосовали · {{ active.total - active.voted }} без ответа</p>
          <small><template v-if="active.chat_id">Публикация в чате: {{ deliveryLabels[active.chat_delivery] }}. Статус «Отправлено» не означает, что участник прочитал сообщение. </template>Отправлено: {{ active.sent }} · Не доставлено / нет Telegram: {{ active.failed }} · Ожидает отправки: {{ active.pending }}.</small>
          <div class="totals"><button v-for="(o, i) in active.options" :key="i" @click="filter = String(i)"><span>{{ o }}</span><b>{{ active.counts[i] }}</b></button></div>
          <div class="tools"><input v-model="resultSearch" placeholder="ФИО или Telegram" aria-label="Поиск ответов" /><select v-model="filter" aria-label="Фильтр ответов"><option value="all">Все получатели</option><option value="waiting">Не проголосовали</option><option value="failed">Не доставлено / нет Telegram</option><option v-for="(o, i) in active.options" :key="i" :value="String(i)">{{ o }}</option></select><button @click="exportRows">Скачать список CSV · {{ rows.length }}</button></div>
          <div class="table-wrap"><table><thead><tr><th>Участник</th><th>Telegram</th><th>Ответ</th><th>Доставка</th></tr></thead><tbody><tr v-for="r in rows" :key="r.user_id"><td>{{ r.full_name }}</td><td>{{ r.telegram_username ? '@' + r.telegram_username : '—' }}</td><td>{{ r.choice === null ? 'Не проголосовал' : active.options[r.choice] }}</td><td>{{ deliveryLabels[r.delivery] }}</td></tr></tbody></table></div>
          <p v-if="!rows.length">По этому фильтру никого нет.</p>
        </section>
      </template>
    </main>
  </div>
</template>

<style scoped>
.polls { min-width: 0; }
.columns { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: var(--space-5); }
.card { min-width: 0; padding: var(--space-5); border: 1px solid var(--border); border-radius: 12px; background: var(--surface); display: flex; flex-direction: column; gap: var(--space-3); }
h2 { font-size: 18px; margin: 0; } h3 { font-size: 14px; margin: var(--space-3) 0 0; }
label { display: flex; flex-direction: column; gap: var(--space-2); font-size: 13px; }
input:not([type=checkbox]), textarea, select { width: 100%; min-width: 0; padding: var(--space-3); border: 1px solid var(--border); border-radius: 8px; background: var(--bg); color: var(--text); font: inherit; }
textarea { resize: vertical; }
button { padding: var(--space-2) var(--space-3); border: 1px solid var(--border); border-radius: 8px; background: var(--surface); color: var(--text); cursor: pointer; font: inherit; font-size: 13px; }
button:disabled { opacity: .5; cursor: default; } button.create-btn { background: var(--accent); color: var(--text); }
small { display: block; font-size: 12px; color: var(--text-muted); }
.option, .tools { display: flex; align-items: center; gap: var(--space-2); }.tools { flex-wrap: wrap; }.tools > input, .tools > select { flex: 1 1 180px; }
.audience { max-height: 240px; overflow-y: auto; }.person { flex-direction: row; align-items: center; padding: var(--space-2); }.person input { flex-shrink: 0; }
.history { align-self: start; max-height: 720px; overflow: auto; }.history-item { text-align: left; display: grid; gap: var(--space-2); }.history-item strong { white-space: pre-wrap; overflow-wrap: anywhere; font-weight: 500; }.chosen { border-color: var(--accent); }
.results { margin-top: var(--space-5); }.question { white-space: pre-wrap; overflow-wrap: anywhere; }.totals { display: grid; gap: var(--space-2); }.totals button { display: flex; justify-content: space-between; gap: var(--space-3); text-align: left; overflow-wrap: anywhere; }
.error { color: var(--danger); }.table-wrap { overflow-x: auto; }table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }td, th { padding: var(--space-3); border-bottom: 1px solid var(--border); }
@media (max-width: 768px) { .columns { grid-template-columns: minmax(0, 1fr); }.card { padding: var(--space-3); }button { min-height: 44px; }.option { flex-wrap: wrap; }.history { max-height: 360px; } }
</style>
