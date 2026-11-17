<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { PageFlip } from 'page-flip'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist/legacy/build/pdf.mjs'
import workerUrl from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url'

import BaseIcon from './BaseIcon.vue'

const props = defineProps({ data: { type: ArrayBuffer, required: true }, storageKey: { type: String, required: true } })
const emit = defineEmits(['close'])
GlobalWorkerOptions.workerSrc = workerUrl

const root = ref(null)
const stage = ref(null)
const current = ref(0)
const total = ref(0)
const ready = ref(false)
const error = ref('')
const fullscreenError = ref('')
const pageInput = ref(1)
const landscape = ref(false)
const turning = ref(false)
let pdf, loadingTask, flip, observer, resizeTimer, destroyed = false
let generation = 0
let renderQueue = Promise.resolve()
let host
let previousOverflow, previousFocus
const images = new Map()
const pending = new Map()
const tasks = new Set()
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
const visibleLabel = computed(() => {
  const first = current.value + 1
  return landscape.value && first > 1 && first < total.value ? `${first}–${first + 1}` : `${first}`
})
const readingProgress = computed(() => {
  if (!total.value) return 0
  const lastVisible = current.value + (landscape.value && current.value > 0 ? 2 : 1)
  return Math.round(Math.min(lastVisible, total.value) / total.value * 100)
})

function remember() {
  pageInput.value = current.value + 1
  try { localStorage.setItem(props.storageKey, String(current.value)) } catch { /* Хранилище может быть отключено. */ }
}

function hydrate(index, url) {
  stage.value?.querySelectorAll(`img[data-page="${index}"]`).forEach((img) => { img.src = url })
}

async function renderPage(index) {
  if (destroyed || index < 0 || index >= total.value) return ''
  if (images.has(index)) {
    hydrate(index, images.get(index))
    return images.get(index)
  }
  if (pending.has(index)) return pending.get(index)
  const work = renderQueue.then(async () => {
    if (destroyed) return ''
    const page = await pdf.getPage(index + 1)
    if (destroyed) return ''
    const base = page.getViewport({ scale: 1 })
    // Растр создаётся только для ближайших страниц, а не для всех 42 сразу.
    const viewport = page.getViewport({ scale: Math.min(2.5, 1500 / base.width) })
    const canvas = document.createElement('canvas')
    canvas.width = Math.ceil(viewport.width)
    canvas.height = Math.ceil(viewport.height)
    const task = page.render({ canvasContext: canvas.getContext('2d'), viewport })
    tasks.add(task)
    try { await task.promise } finally { tasks.delete(task) }
    if (destroyed) return ''
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9))
    canvas.width = canvas.height = 0
    page.cleanup()
    if (!blob || destroyed) return ''
    const url = URL.createObjectURL(blob)
    images.set(index, url)
    hydrate(index, url)
    return url
  })
  pending.set(index, work)
  renderQueue = work.catch(() => {})
  try { return await work } finally { pending.delete(index) }
}

function warmPages() {
  for (const offset of [0, 1, -1, 2, 3, -2]) {
    renderPage(current.value + offset).catch(() => {
      if (!destroyed) error.value = 'Не удалось показать страницу. Закройте книгу и попробуйте снова.'
    })
  }
  // Ограничиваем память изображениями нескольких соседних разворотов.
  for (const [index, url] of images) {
    if (Math.abs(index - current.value) > 4) {
      stage.value?.querySelectorAll(`img[data-page="${index}"]`).forEach((img) => img.removeAttribute('src'))
      URL.revokeObjectURL(url)
      images.delete(index)
    }
  }
}

async function buildBook(ratio) {
  const build = ++generation
  ready.value = false
  const { width, height } = stage.value.getBoundingClientRect()
  if (!width || !height) return
  const saved = current.value
  // На коротком экране (например, телефон повёрнут) сохраняем одну страницу.
  landscape.value = width >= 760 && height >= 420
  const pageWidth = Math.max(1, Math.floor(Math.min(width / (landscape.value ? 2 : 1), height / ratio)))
  const pageHeight = Math.floor(pageWidth * ratio)
  if (flip) {
    Object.assign(flip.getSettings(), { width: pageWidth, height: pageHeight })
    host.style.width = `${pageWidth * (landscape.value ? 2 : 1)}px`
    host.style.height = `${pageHeight}px`
    host.style.minWidth = `${pageWidth}px`
    host.style.minHeight = `${pageHeight}px`
    flip.update()
    flip.turnToPage(saved)
    turning.value = false
    ready.value = true
    return
  }
  host = document.createElement('div')
  host.style.width = `${pageWidth * (landscape.value ? 2 : 1)}px`
  host.style.height = `${pageHeight}px`
  stage.value.replaceChildren(host)
  const pages = Array.from({ length: total.value }, (_, index) => {
    const page = document.createElement('div')
    page.className = 'book-leaf'
    page.setAttribute('aria-label', `Страница ${index + 1}`)
    const label = document.createElement('span')
    label.className = 'book-leaf__placeholder'
    label.textContent = `Страница ${index + 1} · Загрузка…`
    const img = document.createElement('img')
    img.dataset.page = String(index)
    img.alt = `Велкомбук — страница ${index + 1}`
    img.draggable = false
    if (images.has(index)) img.src = images.get(index)
    page.append(label, img)
    host.append(page)
    return page
  })
  flip = new PageFlip(host, {
    width: pageWidth, height: pageHeight, size: 'fixed',
    showCover: true, usePortrait: true, autoSize: false, startPage: saved,
    flippingTime: reducedMotion ? 1 : 700, maxShadowOpacity: 0.3,
    mobileScrollSupport: false, swipeDistance: 35, showPageCorners: !reducedMotion,
  })
  flip.on('flip', ({ data }) => {
    current.value = data
    remember()
    warmPages()
  })
  flip.on('changeState', ({ data }) => { turning.value = data !== 'read' })
  flip.loadFromHTML(pages)
  current.value = flip.getCurrentPageIndex()
  remember()
  warmPages()
  await Promise.all([renderPage(current.value), renderPage(current.value + 1)])
  if (!destroyed && generation === build) ready.value = true
}

function turn(direction) {
  if (!ready.value || turning.value) return
  if (direction < 0) flip.flipPrev()
  else flip.flipNext()
}

function goToPage() {
  const page = Number(pageInput.value)
  if (!Number.isInteger(page) || page < 1 || page > total.value || !ready.value || turning.value) {
    pageInput.value = current.value + 1
    return
  }
  flip.turnToPage(page - 1)
}

async function toggleFullscreen() {
  fullscreenError.value = ''
  try {
    if (document.fullscreenElement === root.value) await document.exitFullscreen()
    else if (root.value.requestFullscreen) await root.value.requestFullscreen()
    else fullscreenError.value = 'Книга уже занимает всё доступное окно приложения.'
  } catch {
    fullscreenError.value = 'Браузер не разрешил скрыть свои панели. Книга открыта на всё окно.'
  }
}

function keydown(event) {
  if (event.key === 'Tab') {
    const container = root.value
    const controls = [...container.querySelectorAll('button:not(:disabled), input:not(:disabled), select')]
      .filter((element) => element.getClientRects().length)
    const first = controls[0]
    const last = controls.at(-1)
    if (event.shiftKey && (document.activeElement === first || document.activeElement === root.value)) {
      event.preventDefault(); last?.focus()
    } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === root.value)) {
      event.preventDefault(); first?.focus()
    }
    return
  }
  if (event.key === 'Escape') {
    emit('close')
    return
  }
  if (['INPUT', 'SELECT'].includes(document.activeElement?.tagName)) return
  if (event.key === 'ArrowLeft') { event.preventDefault(); turn(-1) }
  if (event.key === 'ArrowRight') { event.preventDefault(); turn(1) }
}

onMounted(async () => {
  previousFocus = document.activeElement
  previousOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  root.value.focus()
  document.addEventListener('keydown', keydown)
  try {
    // PDF.js передаёт буфер воркеру; копия позволяет открыть книгу повторно.
    loadingTask = getDocument({ data: props.data.slice(0), isEvalSupported: false })
    pdf = await loadingTask.promise
    if (destroyed) return
    total.value = pdf.numPages
    try {
      const saved = Number(localStorage.getItem(props.storageKey))
      if (Number.isInteger(saved)) current.value = Math.max(0, Math.min(saved, total.value - 1))
    } catch { /* Чтение работает и без localStorage. */ }
    const first = await pdf.getPage(1)
    const viewport = first.getViewport({ scale: 1 })
    const ratio = viewport.height / viewport.width
    await buildBook(ratio)
    if (destroyed) return
    let lastSize = ''
    observer = new ResizeObserver(([entry]) => {
      const size = `${Math.round(entry.contentRect.width)}:${Math.round(entry.contentRect.height)}`
      if (size === lastSize) return
      const initial = !lastSize
      lastSize = size
      if (initial) return
      clearTimeout(resizeTimer)
      resizeTimer = setTimeout(() => buildBook(ratio).catch(() => {
        if (!destroyed) error.value = 'Не удалось изменить размер книги. Откройте её заново.'
      }), 180)
    })
    observer.observe(stage.value)
  } catch (cause) {
    if (import.meta.env.DEV) console.error('Welcome Book PDF:', cause.message, cause.details, cause.stack)
    if (!destroyed) error.value = 'Не удалось открыть PDF. Попробуйте загрузить файл заново.'
  }
})

onBeforeUnmount(() => {
  destroyed = true
  generation++
  observer?.disconnect()
  clearTimeout(resizeTimer)
  document.removeEventListener('keydown', keydown)
  tasks.forEach((task) => task.cancel())
  flip?.destroy()
  loadingTask?.destroy()
  images.forEach((url) => URL.revokeObjectURL(url))
  document.body.style.overflow = previousOverflow
  previousFocus?.focus()
})
</script>

<template>
  <section ref="root" class="book-reader" tabindex="-1" role="dialog" aria-modal="true" aria-label="Чтение велкомбука">
    <header class="reader-header">
      <button class="reader-button" @click="emit('close')"><BaseIcon name="chevron-left" /> Назад</button>
      <div class="reader-title"><strong>Welcome Book</strong><span>Информационный комитет</span></div>
      <button class="reader-button fullscreen-button" aria-label="На весь экран" @click="toggleFullscreen"><BaseIcon name="expand" /><span>На весь экран</span></button>
    </header>
    <div class="reading-progress" role="progressbar" aria-label="Прогресс чтения" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="readingProgress" :aria-valuetext="`${readingProgress}% · страницы ${visibleLabel} из ${total}`">
      <div class="reading-progress__track"><span :style="{ width: `${readingProgress}%` }" /></div>
      <span class="reading-progress__label">{{ readingProgress }}% прочитано</span>
    </div>
    <p v-if="fullscreenError" class="reader-notice" role="status">{{ fullscreenError }}</p>
    <p v-if="error" class="reader-error" role="alert">{{ error }}</p>
    <div ref="stage" class="book-stage" :class="{ 'book-stage--loading': !ready }" />
    <div v-if="!ready && !error" class="reader-loading" role="status">Открываем книгу…</div>
    <footer class="reader-footer">
      <div class="reader-controls">
        <button class="reader-button" :disabled="!ready || current === 0 || turning" aria-label="Предыдущая страница" @click="turn(-1)"><BaseIcon name="chevron-left" /></button>
        <form class="page-picker" @submit.prevent="goToPage">
          <label for="book-page">Страница</label>
          <input id="book-page" v-model="pageInput" type="number" min="1" :max="total" :disabled="!ready || turning" aria-label="Перейти к странице" @change="goToPage" />
          <span>/ {{ total || '…' }}</span>
        </form>
        <button class="reader-button" :disabled="!ready || current >= total - (landscape && current > 0 ? 2 : 1) || turning" aria-label="Следующая страница" @click="turn(1)"><BaseIcon name="chevron-right" /></button>
      </div>
      <span class="reader-hint">Листайте за уголок, свайпом или стрелками ← →</span>
      <span class="sr-only" aria-live="polite">Страницы {{ visibleLabel }} из {{ total }}</span>
    </footer>
  </section>
</template>

<style scoped>
.book-reader { position: fixed; inset: 0; z-index: 210; width: 100%; height: 100dvh; min-width: 0; display: flex; flex-direction: column; overflow: hidden; background: var(--bg); outline: none; padding-left: env(safe-area-inset-left); padding-right: env(safe-area-inset-right); }
.reader-header { flex-shrink: 0; display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: var(--space-3); padding: calc(var(--space-3) + env(safe-area-inset-top)) var(--space-5) var(--space-3); }
.reader-header > .reader-button:first-child { justify-self: start; }
.fullscreen-button { justify-self: end; }
.reader-title { min-width: 0; display: flex; flex-direction: column; text-align: center; }
.reader-title strong { font: 500 14px var(--font-display); }
.reader-title span, .reader-hint { font-size: 12px; color: var(--text-muted); }
.reader-button { display: inline-flex; align-items: center; justify-content: center; gap: var(--space-1); min-height: 40px; padding: var(--space-2) var(--space-3); border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface); color: var(--text); font: inherit; font-size: 13px; }
.reader-button:hover:not(:disabled) { background: var(--surface-hover); border-color: var(--border-strong); }
.reader-button:disabled { opacity: 0.4; cursor: default; }
.reading-progress { flex-shrink: 0; display: flex; flex-direction: column; gap: var(--space-1); padding: 0 var(--space-5); }
.reading-progress__track { height: 3px; overflow: hidden; border-radius: var(--radius-full); background: var(--border); }
.reading-progress__track span { display: block; height: 100%; background: linear-gradient(90deg, var(--dir-prod-b), var(--accent)); transition: width 0.3s ease; }
.reading-progress__label { align-self: flex-end; color: var(--text-muted); font: 11px var(--font-mono); }
.book-stage { position: relative; flex: 1 1 0; min-width: 0; min-height: 0; margin: var(--space-3) var(--space-5); display: flex; align-items: center; justify-content: center; overflow: hidden; }
.book-stage--loading { visibility: hidden; }
.book-stage :deep(.book-leaf) { background: var(--surface-raised); overflow: hidden; }
.book-stage :deep(.book-leaf img) { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; user-select: none; }
.book-stage :deep(.book-leaf img:not([src])) { display: none; }
.book-stage :deep(.book-leaf__placeholder) { display: grid; place-items: center; height: 100%; font-size: 13px; color: var(--text-muted); }
.book-stage :deep(.stf__parent) { flex: none; filter: drop-shadow(0 8px 24px color-mix(in srgb, var(--bg) 80%, transparent)); }
.book-stage :deep(.stf__wrapper) { height: 100%; }
.reader-footer { flex-shrink: 0; display: flex; flex-direction: column; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-3) calc(var(--space-3) + env(safe-area-inset-bottom)); }
.reader-controls { display: flex; align-items: center; justify-content: center; gap: var(--space-2); }
.page-picker { display: flex; align-items: center; gap: var(--space-2); font-size: 13px; color: var(--text-muted); }
.page-picker input { width: 58px; min-height: 40px; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface); color: var(--text); padding: var(--space-2); font: 13px var(--font-mono); }
.reader-loading { position: absolute; top: 50%; align-self: center; color: var(--text-muted); }
.reader-error, .reader-notice { padding: var(--space-3); margin: 0; text-align: center; font-size: 13px; }
.reader-error { color: var(--danger); }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
@media (max-width: 600px) {
  .reader-header { padding-left: var(--space-2); padding-right: var(--space-2); }
  .reader-title span { display: none; }
  .reader-title strong { font-size: 12px; }
  .fullscreen-button span { display: none; }
  .reader-header { grid-template-columns: 1fr auto 1fr; gap: var(--space-1); }
  .reader-header .reader-button { min-height: 44px; }
  .reading-progress { padding: 0 var(--space-2); }
  .book-stage { margin: var(--space-2); }
  .page-picker label { display: none; }
  .reader-controls { gap: var(--space-1); }
  .reader-hint { font-size: 11px; }
}
@media (max-height: 480px) {
  .reader-header { padding-top: calc(var(--space-1) + env(safe-area-inset-top)); padding-bottom: var(--space-1); }
  .reader-title span, .reader-hint { display: none; }
  .book-stage { margin-top: var(--space-1); margin-bottom: var(--space-1); }
  .reader-footer { padding-top: var(--space-1); padding-bottom: calc(var(--space-1) + env(safe-area-inset-bottom)); }
}
@media (prefers-reduced-motion: reduce) {
  .reading-progress__track span { transition: none; }
}
</style>
