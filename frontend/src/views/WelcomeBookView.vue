<script setup>
import { defineAsyncComponent, onMounted, ref } from 'vue'

import AppSidebar from '../components/AppSidebar.vue'
import BaseIcon from '../components/BaseIcon.vue'
import WelcomeBookStats from '../components/WelcomeBookStats.vue'
import coverUrl from '../assets/welcome-book-cover.png'
import { fetchWelcomeBook, fetchWelcomeBookPdf, saveWelcomeBookProgress, uploadWelcomeBook } from '../api/welcomeBook'
import { useAuthStore } from '../stores/auth'

const WelcomeBookReader = defineAsyncComponent(() => import('../components/WelcomeBookReader.vue'))
const authStore = useAuthStore()
const info = ref(null)
const loading = ref(true)
const opening = ref(false)
const uploading = ref(false)
const progress = ref(0)
const error = ref('')
const success = ref('')
const fileInput = ref(null)
const data = ref(null)
const reading = ref(false)
const readingVersion = ref('')
const statsRevision = ref(0)
const syncError = ref('')
let progressQueue = Promise.resolve()

function recordProgress(page) {
  const version = readingVersion.value
  progressQueue = progressQueue.then(async () => {
    try {
      await saveWelcomeBookProgress(version, page)
      syncError.value = ''
    } catch (e) {
      syncError.value = e.response?.status === 409
        ? 'Издание изменилось. Закройте книгу и обновите раздел.'
        : 'Прогресс не сохранился. Проверьте соединение; попробуем при следующем перелистывании.'
    }
  })
}

async function closeBook() {
  reading.value = false
  data.value = null
  await progressQueue
  statsRevision.value++
}

async function load() {
  loading.value = true
  error.value = ''
  try { info.value = await fetchWelcomeBook() }
  catch { error.value = 'Не удалось загрузить велкомбук. Попробуйте ещё раз.' }
  finally { loading.value = false }
}

async function openBook() {
  opening.value = true
  error.value = ''
  try {
    readingVersion.value = info.value.version
    syncError.value = ''
    data.value = await fetchWelcomeBookPdf()
    reading.value = true
  } catch { error.value = 'Не удалось открыть книгу. Проверьте соединение и попробуйте снова.' }
  finally { opening.value = false }
}

async function upload(event) {
  const file = event.target.files?.[0]
  if (!file) return
  event.target.value = ''
  error.value = success.value = ''
  if (file.size > 18 * 1024 * 1024) {
    error.value = 'Выберите PDF размером не больше 18 МБ.'
    return
  }
  uploading.value = true
  progress.value = 0
  try {
    info.value = await uploadWelcomeBook(file, ({ loaded, total }) => {
      progress.value = total ? Math.round(loaded / total * 100) : 0
    })
    data.value = null
    statsRevision.value++
    success.value = 'Велкомбук обновлён и доступен всем участникам.'
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить PDF. Попробуйте ещё раз.'
  } finally { uploading.value = false }
}

onMounted(load)
</script>

<template>
  <div class="app-layout" :inert="reading || undefined">
    <AppSidebar />
    <main class="app-main">
      <div class="welcome">
        <header>
          <p class="breadcrumb">ИК · Трекер / Welcome Book</p>
          <h1>Welcome Book</h1>
          <p class="subtitle">Знакомство с Информационным комитетом — страница за страницей.</p>
        </header>
        <p v-if="error" class="book-error" role="alert">{{ error }}</p>
        <p v-if="success" class="book-success" role="status">{{ success }}</p>
        <p v-if="loading" class="subtitle" role="status">Загружаем велкомбук…</p>
        <section v-else-if="info?.available" class="welcome-hero">
          <div class="book-art" aria-hidden="true">
            <img v-if="info.bundled" class="book-art__cover book-art__image" :src="coverUrl" alt="" />
            <div v-else class="book-art__cover"><span>Информационный<br />комитет</span><strong>Welcome<br />Book</strong><span>Здесь начинается<br />твоя история в ИК</span></div>
          </div>
          <div class="welcome-copy">
            <span class="book-eyebrow">Твой путеводитель по ИК</span>
            <h2>Добро пожаловать<br />в команду</h2>
            <p>Открой наш велкомбук как журнал: листай страницы, знакомься с командой и возвращайся к тому, что интересно.</p>
            <span class="book-details">{{ info.pages }} стр. · На весь экран · Сохраняет место чтения</span>
            <button class="book-open" :disabled="opening || uploading" @click="openBook">{{ opening ? 'Открываем…' : 'Читать велкомбук' }} <BaseIcon name="arrow-right" /></button>
            <p class="book-help">На компьютере — развороты, на телефоне — по одной странице.</p>
            <p class="book-help">Администратору видны открытие книги и самая дальняя просмотренная страница.</p>
          </div>
        </section>
        <section v-else-if="info" class="book-empty"><h2>Скоро здесь будет наша история</h2><p>Администратор ещё не добавил велкомбук.</p></section>
        <button v-else class="book-retry" @click="load">Попробовать снова</button>
        <WelcomeBookStats v-if="authStore.isAdmin && info?.available" :key="statsRevision" />
        <section v-if="authStore.isAdmin && !loading" class="book-admin">
          <div><h2>Издание велкомбука</h2><p>Загрузи PDF, чтобы {{ info?.available ? 'заменить текущее издание' : 'открыть его для всей команды' }}. До 18 МБ, без пароля.</p></div>
          <input ref="fileInput" type="file" accept=".pdf,application/pdf" class="file-input" @change="upload" />
          <button class="book-retry" :disabled="uploading || opening" @click="fileInput.click()">{{ uploading ? `Загружаем… ${progress}%` : info?.available ? 'Заменить PDF' : 'Загрузить PDF' }}</button>
        </section>
      </div>
    </main>
    <Teleport to="body"><WelcomeBookReader v-if="reading && data" :data="data" :sync-error="syncError" :storage-key="`ik-welcome-book:${authStore.user.id}:${readingVersion}`" @progress="recordProgress" @close="closeBook" /></Teleport>
  </div>
</template>

<style scoped>
.welcome { max-width: 1080px; display: flex; flex-direction: column; gap: var(--space-5); }
.welcome-hero { display: grid; grid-template-columns: minmax(240px, 0.8fr) 1fr; align-items: center; gap: var(--space-10); padding: var(--space-10); background: radial-gradient(ellipse at top left, var(--accent-soft), transparent 70%), var(--surface); border: 1px solid var(--border); border-radius: var(--radius-xl); overflow: hidden; }
.book-art { perspective: 1000px; padding: var(--space-5); }
.book-art__cover { width: 100%; max-width: 280px; aspect-ratio: 595 / 842; margin: auto; display: flex; flex-direction: column; justify-content: space-between; padding: var(--space-6); background: linear-gradient(150deg, var(--dir-nvk), var(--accent)); color: var(--text); border: 1px solid var(--border-strong); border-left: 8px solid color-mix(in srgb, var(--bg) 40%, var(--accent)); border-radius: 6px 12px 12px 6px; box-shadow: 8px 8px 0 var(--text-muted), 10px 10px 0 var(--border-strong), var(--shadow-lift); transform: rotateY(-12deg) rotate(-5deg); }
.book-art__cover strong { font: 500 24px/1.4 var(--font-display); }
.book-art__image { padding: 0 !important; object-fit: cover; }
.book-art__cover span { font-size: 12px; }
.welcome-copy { display: flex; flex-direction: column; align-items: flex-start; gap: var(--space-4); }
.book-eyebrow { color: var(--text-muted); font: 12px var(--font-mono); }
.welcome-copy h2 { margin: 0; font: 500 24px/1.4 var(--font-display); }
.welcome-copy p { margin: 0; color: var(--text-muted); font-size: 14px; }
.book-details { color: var(--text-muted); font-size: 12px; }
.book-open { display: inline-flex; align-items: center; justify-content: center; gap: var(--space-4); padding: var(--space-3) var(--space-5); background: var(--accent); border: 1px solid transparent; border-radius: var(--radius-md); color: var(--text); font: inherit; }
.book-open:hover:not(:disabled) { background: var(--accent-hover); }
.book-open:disabled, .book-retry:disabled { opacity: 0.5; }
.welcome-copy .book-help { font-size: 12px; }
.book-admin { display: flex; justify-content: space-between; align-items: center; gap: var(--space-4); padding: var(--space-5); border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--surface); }
.book-admin h2, .book-empty h2 { font-size: 15px; margin: 0 0 var(--space-2); }
.book-admin p, .book-empty p { margin: 0; font-size: 13px; color: var(--text-muted); }
.book-retry { padding: var(--space-2) var(--space-4); min-height: 40px; border: 1px solid var(--border-strong); border-radius: var(--radius-md); background: var(--surface-raised); color: var(--text); font: inherit; white-space: nowrap; align-self: flex-start; }
.book-empty { padding: var(--space-8); background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); }
.file-input { display: none; }
.book-error { color: var(--danger); margin: 0; }
.book-success { color: var(--success); margin: 0; }
@media (max-width: 768px) {
  .welcome-hero { grid-template-columns: 1fr; padding: var(--space-6); gap: var(--space-6); }
  .book-art { padding: var(--space-3); }
  .book-art__cover { max-width: 190px; padding: var(--space-5); }
  .book-art__cover strong { font-size: 20px; }
  .welcome-copy h2 { font-size: 20px; }
  .book-admin { align-items: flex-start; flex-direction: column; }
}
</style>
