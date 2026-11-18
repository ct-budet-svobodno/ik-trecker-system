<script setup>
import { computed, onMounted, ref } from 'vue'

import { fetchWelcomeBookReaders } from '../api/welcomeBook'

const data = ref(null)
const busy = ref(false)
const error = ref('')
const search = ref('')
const filter = ref('all')
const rows = computed(() => data.value?.readers ?? [])
const opened = computed(() => rows.value.filter((row) => row.max_page > 0).length)
const completed = computed(() => rows.value.filter((row) => row.max_page === data.value.pages).length)
const filtered = computed(() => {
  const query = search.value.trim().toLocaleLowerCase('ru')
  return rows.value.filter((row) => {
    if (query && !`${row.full_name} ${row.username}`.toLocaleLowerCase('ru').includes(query)) return false
    if (filter.value === 'unopened') return row.max_page === 0
    if (filter.value === 'reading') return row.max_page > 0 && row.max_page < data.value.pages
    if (filter.value === 'completed') return row.max_page === data.value.pages
    return true
  })
})
const dateFormat = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
const dateLabel = (value) => value ? dateFormat.format(new Date(value)) : '—'

async function load() {
  busy.value = true
  error.value = ''
  try { data.value = await fetchWelcomeBookReaders() }
  catch { error.value = 'Не удалось загрузить статистику. Попробуйте обновить.' }
  finally { busy.value = false }
}

onMounted(load)
</script>

<template>
  <section class="book-stats" aria-label="Статистика велкомбука">
    <div class="stats-heading">
      <div><h2>Кто читает велкомбук</h2><p>Текущее издание. Все активные участники с одобренным доступом.</p></div>
      <button :disabled="busy" @click="load">{{ busy ? 'Загружаем…' : 'Обновить' }}</button>
    </div>
    <p v-if="error" class="stats-error" role="alert">{{ error }}</p>
    <template v-if="data?.available">
      <div class="stats-summary">
        <span><b>{{ opened }}</b> открыли</span>
        <span><b>{{ rows.length - opened }}</b> ещё не открывали</span>
        <span><b>{{ completed }}</b> дошли до конца</span>
      </div>
      <div class="stats-filters">
        <input v-model="search" type="search" placeholder="Найти участника" aria-label="Поиск участника" />
        <select v-model="filter" aria-label="Фильтр по прогрессу"><option value="all">Все участники</option><option value="unopened">Не открывали</option><option value="reading">Начали смотреть</option><option value="completed">Дошли до конца</option></select>
      </div>
      <p class="stats-note">Процент — самая дальняя открытая страница, включая переход по номеру. Это не подтверждение прочтения текста. Просмотры до появления статистики не учитываются.</p>
      <div class="stats-table-wrap">
        <table>
          <thead><tr><th scope="col">Участник</th><th scope="col">Просмотрено</th><th scope="col">Первое открытие</th><th scope="col">Последняя активность</th></tr></thead>
          <tbody>
            <tr v-for="row in filtered" :key="row.user_id">
              <td><strong>{{ row.full_name }}</strong><span class="stats-username">{{ row.username }}</span></td>
              <td><template v-if="row.max_page"><div class="stats-percent"><b>{{ row.percent }}%</b><span>{{ row.max_page }} / {{ data.pages }} стр.</span></div><div class="stats-bar"><span :style="{ width: `${row.percent}%` }" /></div></template><span v-else class="stats-note">Ещё не открывал</span></td>
              <td>{{ dateLabel(row.first_opened_at) }}</td><td>{{ dateLabel(row.last_seen_at) }}</td>
            </tr>
            <tr v-if="!filtered.length"><td colspan="4" class="stats-note">{{ rows.length ? 'По этому фильтру никого нет' : 'Участников пока нет' }}</td></tr>
          </tbody>
        </table>
      </div>
    </template>
    <p v-else-if="data" class="stats-note">Сначала загрузите велкомбук.</p>
  </section>
</template>

<style scoped>
.book-stats { min-width: 0; padding: var(--space-5); background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); display: flex; flex-direction: column; gap: var(--space-4); }
.stats-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); }
.stats-heading h2 { font-size: 15px; margin: 0 0 var(--space-2); }
.stats-heading p, .stats-note { margin: 0; font-size: 12px; color: var(--text-muted); }
.book-stats button, .stats-filters input, .stats-filters select { border: 1px solid var(--border-strong); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); min-height: 40px; background: var(--surface-raised); color: var(--text); font: inherit; font-size: 13px; }
.book-stats button:disabled { opacity: 0.5; }
.stats-summary { display: flex; flex-wrap: wrap; gap: var(--space-3) var(--space-5); color: var(--text-muted); font-size: 13px; }
.stats-summary b { color: var(--text); }
.stats-filters { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.stats-filters input { min-width: 0; flex: 1; }
.stats-table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; text-align: left; font-size: 13px; }
th { color: var(--text-muted); font-size: 12px; font-weight: 500; }
th, td { padding: var(--space-3); border-bottom: 1px solid var(--border); vertical-align: middle; }
td strong { font-weight: 500; }
td:first-child { min-width: 180px; }
td:not(:first-child) { white-space: nowrap; }
.stats-username { display: block; color: var(--text-muted); font-size: 12px; }
.stats-percent { display: flex; justify-content: space-between; gap: var(--space-3); font-size: 12px; }
.stats-percent span { color: var(--text-muted); }
.stats-bar { height: 3px; background: var(--border); border-radius: var(--radius-full); margin-top: var(--space-2); overflow: hidden; }
.stats-bar span { display: block; height: 100%; background: var(--dir-prod-b); }
.stats-error { margin: 0; color: var(--danger); font-size: 13px; }
@media (max-width: 600px) {
  .book-stats { padding: var(--space-3); }
  .stats-filters input, .stats-filters select { width: 100%; flex: auto; }
}
</style>
