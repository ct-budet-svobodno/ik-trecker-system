<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import ZavodNodeModal from '../components/ZavodNodeModal.vue'
import { fetchAssignableUsers } from '../api/zavod'
import {
  LAYOUT_COLUMN,
  LAYOUT_ROW,
  NODE_DEFAULT_HEIGHT,
  NODE_DEFAULT_WIDTH,
  ZAVOD_STATUS_META,
} from '../constants/zavodMeta'
import { useZavodStore } from '../stores/zavod'
import { getAvatarColor, getInitials } from '../utils/avatar'

const store = useZavodStore()

const viewport = ref(null)
const pan = ref({ x: 0, y: 0 })
const zoom = ref(1)
const selectedIds = ref(new Set())
const editingNode = ref(null)
const people = ref([])
const actionError = ref('')

// Текущий жест мыши/пальца: панорама, перетаскивание карточек или протяжка связи.
let gesture = null
const linkPreview = ref(null)

const MIN_ZOOM = 0.2
const MAX_ZOOM = 3

onMounted(async () => {
  await store.init()
  try {
    people.value = await fetchAssignableUsers()
  } catch {
    people.value = []
  }
  window.addEventListener('keydown', onKeyDown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
  stopListening()
})

// --- Координаты ---
// В БД лежат «мировые» координаты; зум и панорама живут только здесь.

const worldStyle = computed(() => ({
  transform: `translate(${pan.value.x}px, ${pan.value.y}px) scale(${zoom.value})`,
  transformOrigin: '0 0',
}))

function toWorld(clientX, clientY) {
  const rect = viewport.value.getBoundingClientRect()
  return {
    x: (clientX - rect.left - pan.value.x) / zoom.value,
    y: (clientY - rect.top - pan.value.y) / zoom.value,
  }
}

function center(node) {
  return { x: node.x + node.width / 2, y: node.y + node.height / 2 }
}

/** Верхняя карточка под точкой экрана. */
function nodeAt(clientX, clientY) {
  const p = toWorld(clientX, clientY)
  for (let i = store.nodes.length - 1; i >= 0; i--) {
    const n = store.nodes[i]
    if (p.x >= n.x && p.x <= n.x + n.width && p.y >= n.y && p.y <= n.y + n.height) return n
  }
  return null
}

function onWheel(event) {
  const rect = viewport.value.getBoundingClientRect()
  const sx = event.clientX - rect.left
  const sy = event.clientY - rect.top
  zoomAt(sx, sy, event.deltaY < 0 ? 1.12 : 1 / 1.12)
}

/** Зум «к точке»: мировая точка под курсором остаётся на месте. */
function zoomAt(screenX, screenY, factor) {
  const before = {
    x: (screenX - pan.value.x) / zoom.value,
    y: (screenY - pan.value.y) / zoom.value,
  }
  const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom.value * factor))
  zoom.value = next
  pan.value = { x: screenX - before.x * next, y: screenY - before.y * next }
}

function zoomButton(factor) {
  const rect = viewport.value.getBoundingClientRect()
  zoomAt(rect.width / 2, rect.height / 2, factor)
}

/** Вписать все карточки в экран. */
function fitToContent() {
  if (!store.nodes.length || !viewport.value) return
  const rect = viewport.value.getBoundingClientRect()
  const minX = Math.min(...store.nodes.map((n) => n.x))
  const minY = Math.min(...store.nodes.map((n) => n.y))
  const maxX = Math.max(...store.nodes.map((n) => n.x + n.width))
  const maxY = Math.max(...store.nodes.map((n) => n.y + n.height))
  const padding = 60
  const scale = Math.min(
    (rect.width - padding * 2) / Math.max(maxX - minX, 1),
    (rect.height - padding * 2) / Math.max(maxY - minY, 1),
  )
  zoom.value = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, scale))
  pan.value = {
    x: rect.width / 2 - ((minX + maxX) / 2) * zoom.value,
    y: rect.height / 2 - ((minY + maxY) / 2) * zoom.value,
  }
}

// --- Связи ---

const edgePaths = computed(() => {
  const byId = store.nodeById
  const paths = []
  for (const edge of store.edges) {
    const source = byId.get(edge.source_id)
    const target = byId.get(edge.target_id)
    if (!source || !target) continue
    paths.push({ id: edge.id, d: curve(center(source), center(target)) })
  }
  return paths
})

function curve(a, b) {
  const direction = b.x >= a.x ? 1 : -1
  const handle = Math.max(50, Math.abs(b.x - a.x) * 0.45) * direction
  return `M ${a.x} ${a.y} C ${a.x + handle} ${a.y}, ${b.x - handle} ${b.y}, ${b.x} ${b.y}`
}

const linkPreviewPath = computed(() => {
  const p = linkPreview.value
  return p ? curve({ x: p.x1, y: p.y1 }, { x: p.x2, y: p.y2 }) : null
})

async function removeEdge(edgeId) {
  if (!window.confirm('Удалить связь?')) return
  try {
    await store.removeEdge(edgeId)
  } catch {
    actionError.value = 'Не удалось удалить связь'
  }
}

// --- Жесты ---

function startGesture(next) {
  gesture = next
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
}

function stopListening() {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
}

function onCanvasPointerDown(event) {
  // Тянем за пустое место — панорама; заодно снимаем выделение.
  if (event.button !== 0 && event.button !== 1) return
  if (!event.shiftKey) selectedIds.value = new Set()
  startGesture({
    mode: 'pan',
    startX: event.clientX,
    startY: event.clientY,
    panX: pan.value.x,
    panY: pan.value.y,
  })
}

function onNodePointerDown(event, node) {
  if (event.button !== 0) return
  if (event.shiftKey) {
    const next = new Set(selectedIds.value)
    next.has(node.id) ? next.delete(node.id) : next.add(node.id)
    selectedIds.value = next
  } else if (!selectedIds.value.has(node.id)) {
    selectedIds.value = new Set([node.id])
  }

  // Тянем всю выделенную группу разом.
  const origins = new Map()
  for (const id of selectedIds.value) {
    const target = store.nodeById.get(id)
    if (target) origins.set(id, { x: target.x, y: target.y })
  }
  if (!origins.size) origins.set(node.id, { x: node.x, y: node.y })

  startGesture({ mode: 'node', startX: event.clientX, startY: event.clientY, origins, moved: false })
}

function onPortPointerDown(event, node) {
  const from = center(node)
  linkPreview.value = { x1: from.x, y1: from.y, x2: from.x, y2: from.y }
  startGesture({ mode: 'link', sourceId: node.id })
}

function onPointerMove(event) {
  if (!gesture) return

  if (gesture.mode === 'pan') {
    pan.value = {
      x: gesture.panX + (event.clientX - gesture.startX),
      y: gesture.panY + (event.clientY - gesture.startY),
    }
    return
  }

  if (gesture.mode === 'node') {
    const dx = (event.clientX - gesture.startX) / zoom.value
    const dy = (event.clientY - gesture.startY) / zoom.value
    if (Math.abs(dx) > 1 || Math.abs(dy) > 1) gesture.moved = true
    const byId = store.nodeById
    for (const [id, origin] of gesture.origins) {
      const node = byId.get(id)
      if (!node) continue
      node.x = origin.x + dx
      node.y = origin.y + dy
    }
    return
  }

  if (gesture.mode === 'link') {
    const point = toWorld(event.clientX, event.clientY)
    linkPreview.value = { ...linkPreview.value, x2: point.x, y2: point.y }
  }
}

async function onPointerUp(event) {
  const finished = gesture
  gesture = null
  stopListening()
  if (!finished) return

  if (finished.mode === 'node' && finished.moved) {
    const byId = store.nodeById
    const moves = []
    for (const id of finished.origins.keys()) {
      const node = byId.get(id)
      if (node) moves.push({ id, x: Math.round(node.x), y: Math.round(node.y) })
    }
    try {
      await store.persistPositions(moves)
    } catch {
      actionError.value = 'Не удалось сохранить положение карточек'
    }
    return
  }

  if (finished.mode === 'link') {
    const target = nodeAt(event.clientX, event.clientY)
    linkPreview.value = null
    if (!target || target.id === finished.sourceId) return
    try {
      await store.addEdge(finished.sourceId, target.id)
      actionError.value = ''
    } catch (err) {
      actionError.value = err.response?.data?.detail ?? 'Не удалось создать связь'
    }
  }
}

// --- Карточки ---

async function addNode() {
  const rect = viewport.value.getBoundingClientRect()
  const middle = toWorld(rect.left + rect.width / 2, rect.top + rect.height / 2)
  try {
    const node = await store.addNode({
      title: 'Новая тема',
      x: Math.round(middle.x - NODE_DEFAULT_WIDTH / 2),
      y: Math.round(middle.y - NODE_DEFAULT_HEIGHT / 2),
    })
    selectedIds.value = new Set([node.id])
    editingNode.value = node
  } catch {
    actionError.value = 'Не удалось создать карточку'
  }
}

async function removeSelected() {
  const ids = [...selectedIds.value]
  if (!ids.length) return
  const what = ids.length === 1 ? 'карточку' : `карточки (${ids.length})`
  if (!window.confirm(`Удалить ${what} вместе со связями?`)) return
  try {
    for (const id of ids) await store.removeNode(id)
    selectedIds.value = new Set()
  } catch {
    actionError.value = 'Не удалось удалить карточки'
  }
}

function onKeyDown(event) {
  if (editingNode.value) return
  const tag = event.target?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
  if ((event.key === 'Delete' || event.key === 'Backspace') && selectedIds.value.size) {
    event.preventDefault()
    removeSelected()
  }
  if (event.key === 'Escape') selectedIds.value = new Set()
}

function statusMeta(node) {
  return ZAVOD_STATUS_META[node.status] ?? ZAVOD_STATUS_META.todo
}

function nodeStyle(node) {
  return {
    left: `${node.x}px`,
    top: `${node.y}px`,
    width: `${node.width}px`,
    minHeight: `${node.height}px`,
    ...(node.color
      ? {
          borderColor: node.color,
          background: `color-mix(in srgb, ${node.color} 16%, var(--surface))`,
        }
      : {}),
  }
}

// --- Доски ---

async function pickBoard(event) {
  await store.openBoard(Number(event.target.value))
  selectedIds.value = new Set()
  fitToContent()
}

async function addBoard() {
  const title = window.prompt('Название доски')
  if (!title?.trim()) return
  try {
    await store.addBoard(title.trim())
    pan.value = { x: 0, y: 0 }
    zoom.value = 1
  } catch {
    actionError.value = 'Не удалось создать доску'
  }
}

async function renameBoard() {
  const title = window.prompt('Новое название доски', store.boardTitle)
  if (!title?.trim()) return
  try {
    await store.renameCurrentBoard(title.trim())
  } catch {
    actionError.value = 'Не удалось переименовать доску'
  }
}

async function removeBoard() {
  if (!window.confirm(`Удалить доску «${store.boardTitle}» со всеми карточками?`)) return
  try {
    await store.removeCurrentBoard()
    selectedIds.value = new Set()
  } catch {
    actionError.value = 'Не удалось удалить доску'
  }
}

/**
 * Разложить деревом: связи задают иерархию, координаты пересчитываются с нуля.
 * Корни — карточки, в которые никто не входит; несвязанные уходят в конец.
 */
async function layoutAsTree() {
  if (!store.nodes.length) return
  const children = new Map()
  const hasParent = new Set()
  for (const edge of store.edges) {
    if (!children.has(edge.source_id)) children.set(edge.source_id, [])
    children.get(edge.source_id).push(edge.target_id)
    hasParent.add(edge.target_id)
  }

  const placed = new Map()
  const visited = new Set()
  let row = 0

  function place(id, depth) {
    visited.add(id)
    const kids = (children.get(id) ?? []).filter((kid) => !visited.has(kid))
    if (!kids.length) {
      const y = row * LAYOUT_ROW
      row += 1
      placed.set(id, { x: depth * LAYOUT_COLUMN, y })
      return y
    }
    const kidCenters = kids.map((kid) => place(kid, depth + 1))
    const y = (kidCenters[0] + kidCenters[kidCenters.length - 1]) / 2
    placed.set(id, { x: depth * LAYOUT_COLUMN, y })
    return y
  }

  for (const node of store.nodes) {
    if (!hasParent.has(node.id) && !visited.has(node.id)) place(node.id, 0)
  }
  // Циклы и «острова» без явного корня — раскладываем следом.
  for (const node of store.nodes) {
    if (!visited.has(node.id)) place(node.id, 0)
  }

  const moves = []
  for (const node of store.nodes) {
    const position = placed.get(node.id)
    if (!position) continue
    node.x = position.x
    node.y = position.y
    moves.push({ id: node.id, x: position.x, y: position.y })
  }

  try {
    await store.persistPositions(moves)
    fitToContent()
  } catch {
    actionError.value = 'Не удалось сохранить раскладку'
  }
}
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="app-main__header">
        <div>
          <p class="breadcrumb">ИК · ТРЕКЕР / ZAVOD</p>
          <h1>ZAVOD</h1>
        </div>
      </div>

      <p v-if="store.loadError" class="alert alert--error">{{ store.loadError }}</p>
      <p v-if="actionError" class="alert alert--error">{{ actionError }}</p>

      <AppLoader v-if="store.isLoading" />

      <!-- Ни одной доски -->
      <div v-else-if="!store.boards.length" class="card empty">
        <p class="empty__title">Досок пока нет</p>
        <p class="empty__text">Создайте первую — на ней появятся карточки тем и связи между ними.</p>
        <button class="btn-primary" @click="addBoard">Создать доску</button>
      </div>

      <template v-else>
        <div class="toolbar">
          <select class="toolbar__select" :value="store.boardId" @change="pickBoard">
            <option v-for="board in store.boards" :key="board.id" :value="board.id">
              {{ board.title }}
            </option>
          </select>

          <button class="btn-ghost" title="Новая доска" @click="addBoard">+ доска</button>
          <button class="btn-ghost" @click="renameBoard">Переименовать</button>
          <button class="btn-ghost btn-ghost--danger" @click="removeBoard">Удалить доску</button>

          <span class="toolbar__gap" />

          <button class="btn-primary" @click="addNode">+ карточка</button>
          <button class="btn-ghost" title="Разложить связи деревом" @click="layoutAsTree">
            Разложить деревом
          </button>

          <span class="toolbar__zoom">
            <button class="btn-ghost" title="Отдалить" @click="zoomButton(1 / 1.2)">−</button>
            <button class="btn-ghost" title="Вписать в экран" @click="fitToContent">
              {{ Math.round(zoom * 100) }}%
            </button>
            <button class="btn-ghost" title="Приблизить" @click="zoomButton(1.2)">+</button>
          </span>
        </div>

        <div
          ref="viewport"
          class="viewport"
          :class="{ 'viewport--grabbing': !!linkPreview }"
          @wheel.prevent="onWheel"
          @pointerdown="onCanvasPointerDown"
        >
          <div class="world" :style="worldStyle">
            <svg class="edges" width="1" height="1">
              <!-- Пара путей на связь: широкий прозрачный ловит клик, узкий рисует. -->
              <g v-for="edge in edgePaths" :key="edge.id">
                <path class="edge edge--hit" :d="edge.d" @click.stop="removeEdge(edge.id)" />
                <path class="edge" :d="edge.d" />
              </g>
              <path v-if="linkPreviewPath" class="edge edge--draft" :d="linkPreviewPath" />
            </svg>

            <div
              v-for="node in store.nodes"
              :key="node.id"
              class="node"
              :class="{ 'node--selected': selectedIds.has(node.id) }"
              :style="nodeStyle(node)"
              @pointerdown.stop="onNodePointerDown($event, node)"
              @dblclick.stop="editingNode = node"
            >
              <p class="node__title">{{ node.title }}</p>
              <p v-if="node.content" class="node__content">{{ node.content }}</p>

              <div class="node__footer">
                <span class="node__status" :class="`node__status--${statusMeta(node).tone}`">
                  {{ statusMeta(node).label }}
                </span>
                <span v-if="node.assignees.length" class="node__people">
                  <span
                    v-for="person in node.assignees"
                    :key="person.id"
                    class="node__avatar"
                    :style="{ background: getAvatarColor(person.id) }"
                    :title="person.full_name"
                  >
                    {{ getInitials(person.full_name) }}
                  </span>
                </span>
              </div>

              <button
                class="node__port"
                title="Потяните, чтобы связать с другой карточкой"
                @pointerdown.stop="onPortPointerDown($event, node)"
                @click.stop
              />
            </div>
          </div>

          <p v-if="!store.nodes.length" class="viewport__hint">
            Пусто. Нажмите «+ карточка» — она появится по центру экрана.
          </p>
        </div>

        <p class="legend">
          Тяните пустое место — двигается холст. Колесо — зум. Карточку двигают перетаскиванием,
          двойной клик открывает её. Кружок справа тянется к другой карточке — получится связь.
          Клик по связи удаляет её, Delete убирает выделенные карточки.
        </p>
      </template>
    </main>

    <ZavodNodeModal
      v-if="editingNode"
      :node="editingNode"
      :people="people"
      @close="editingNode = null"
    />
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}

.app-main {
  flex-grow: 1;
  padding: 28px 32px;
  max-width: 100%;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
}

.app-main__header {
  margin-bottom: 16px;
}

.breadcrumb {
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--text-faint);
  margin: 0 0 6px;
}

h1 {
  font-size: 22px;
  margin: 0;
  letter-spacing: 0.02em;
}

.alert {
  padding: 10px 14px;
  border-radius: 8px;
  margin: 0 0 12px;
  font-size: 14px;
}

.alert--error {
  background: color-mix(in srgb, var(--danger) 14%, transparent);
  color: var(--danger);
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 18px;
}

.empty {
  max-width: 460px;
}

.empty__title {
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 600;
}

.empty__text {
  margin: 0 0 14px;
  color: var(--text-muted);
  font-size: 14px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.toolbar__gap {
  flex-grow: 1;
}

.toolbar__zoom {
  display: inline-flex;
  gap: 4px;
}

.toolbar__select {
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-raised);
  color: var(--text);
  font-size: 13px;
  max-width: 220px;
}

.btn-primary {
  border: none;
  border-radius: 8px;
  background: var(--accent);
  color: #fff;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

.btn-ghost {
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text);
  border-radius: 8px;
  padding: 7px 12px;
  font-size: 13px;
}

.btn-ghost:hover {
  background: var(--surface-hover);
}

.btn-ghost--danger {
  color: var(--danger);
  border-color: color-mix(in srgb, var(--danger) 40%, transparent);
}

/* --- Холст --- */

.viewport {
  position: relative;
  flex-grow: 1;
  min-height: 480px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background-color: var(--surface);
  /* Точечная сетка — чтобы панорама читалась глазом. */
  background-image: radial-gradient(var(--border-strong) 1px, transparent 1px);
  background-size: 28px 28px;
  overflow: hidden;
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.viewport:active {
  cursor: grabbing;
}

.viewport--grabbing {
  cursor: crosshair;
}

.world {
  position: absolute;
  left: 0;
  top: 0;
  width: 0;
  height: 0;
}

.edges {
  position: absolute;
  overflow: visible;
  pointer-events: none;
}

.edge {
  fill: none;
  stroke: var(--border-strong);
  stroke-width: 2;
}

.edge--hit {
  stroke: transparent;
  stroke-width: 14;
  pointer-events: stroke;
  cursor: pointer;
}

.edge--hit:hover + .edge {
  stroke: var(--danger);
}

.edge--draft {
  stroke: var(--accent);
  stroke-dasharray: 6 5;
}

.node {
  position: absolute;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  border: 1px solid var(--border-strong);
  border-radius: 10px;
  background: var(--surface-raised);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.28);
  cursor: grab;
}

.node--selected {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-soft), 0 6px 18px rgba(0, 0, 0, 0.28);
}

.node__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.3;
  overflow-wrap: anywhere;
}

.node__content {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.4;
  overflow-wrap: anywhere;
  /* Длинное описание не должно раздувать карточку — полностью видно в модалке. */
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.node__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: auto;
}

.node__status {
  font-size: 10px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 999px;
}

.node__status--todo {
  background: color-mix(in srgb, var(--status-todo) 20%, transparent);
  color: var(--status-todo);
}

.node__status--progress {
  background: color-mix(in srgb, var(--status-progress) 20%, transparent);
  color: var(--status-progress);
}

.node__status--done {
  background: color-mix(in srgb, var(--status-done) 20%, transparent);
  color: var(--status-done);
}

.node__people {
  display: inline-flex;
}

.node__avatar {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 600;
  color: #fff;
  border: 2px solid var(--surface-raised);
  margin-left: -6px;
}

.node__avatar:first-child {
  margin-left: 0;
}

.node__port {
  position: absolute;
  right: -9px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid var(--surface);
  background: var(--accent);
  padding: 0;
  opacity: 0;
  transition: opacity 0.15s ease;
  cursor: crosshair;
}

.node:hover .node__port,
.node--selected .node__port {
  opacity: 1;
}

.viewport__hint {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  color: var(--text-faint);
  font-size: 14px;
  pointer-events: none;
}

.legend {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--text-faint);
  line-height: 1.5;
}

@media (max-width: 768px) {
  .viewport {
    min-height: 60vh;
  }

  .legend {
    display: none;
  }
}
</style>
