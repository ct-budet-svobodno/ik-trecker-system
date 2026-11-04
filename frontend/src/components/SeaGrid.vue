<script setup>
// Поле морского боя 10×10 с подписями А–К / 1–10. Одно и то же поле —
// для расстановки, своего флота и стрельбы по сопернику: что можно нажать,
// решает родитель через clickable, сюда приходит только нажатая клетка.
import { computed } from 'vue'

import { LETTERS, N } from '../utils/seabattle'

const props = defineProps({
  ships: { type: Array, default: () => [] },
  // {клетка: 'miss' | 'hit'} — ключи строкой, как отдаёт API.
  shots: { type: Object, default: () => ({}) },
  recent: { type: Array, default: () => [] },
  // Клетки, которые можно нажать (Set или массив); пусто — поле только смотреть.
  clickable: { type: [Set, Array], default: () => [] },
  // Клетка, по которой выстрел ушёл, а ответа ещё нет.
  pending: { type: Number, default: null },
  // Подсвеченные клетки: только что поставленный корабль и т. п.
  marked: { type: Array, default: () => [] },
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['cell'])

const cells = Array.from({ length: N * N }, (_, i) => i)

const shipOf = computed(() => {
  const map = new Map()
  props.ships.forEach((ship) => ship.forEach((c) => map.set(c, ship)))
  return map
})

const clickableSet = computed(() =>
  props.clickable instanceof Set ? props.clickable : new Set(props.clickable),
)
const recentSet = computed(() => new Set(props.recent))
const markedSet = computed(() => new Set(props.marked))

function isSunk(ship) {
  return ship.every((c) => props.shots[c] === 'hit')
}

function stateOf(cell) {
  const ship = shipOf.value.get(cell)
  const shot = props.shots[cell]
  if (ship && isSunk(ship)) return 'sunk'
  if (shot === 'hit') return 'hit'
  if (shot === 'miss') return 'miss'
  return ship ? 'ship' : 'empty'
}

// Края корабля скругляем, внутренние стыки — нет: корабль читается одной плашкой.
function shipEdges(cell) {
  const ship = shipOf.value.get(cell)
  if (!ship || ship.length === 1) return {}
  const vertical = ship[1] - ship[0] === N
  const first = cell === ship[0]
  const last = cell === ship[ship.length - 1]
  return vertical
    ? { 'cell--joint-bottom': !last, 'cell--joint-top': !first }
    : { 'cell--joint-right': !last, 'cell--joint-left': !first }
}
</script>

<template>
  <div class="sea" :class="{ 'sea--compact': compact }">
    <span class="sea__axis" />
    <span v-for="letter in LETTERS" :key="letter" class="sea__axis">{{ letter }}</span>
    <template v-for="row in N" :key="row">
      <span class="sea__axis">{{ row }}</span>
      <button
        v-for="cell in cells.slice((row - 1) * N, row * N)"
        :key="cell"
        type="button"
        class="cell"
        :class="[
          `cell--${stateOf(cell)}`,
          shipEdges(cell),
          {
            'cell--clickable': clickableSet.has(cell),
            'cell--recent': recentSet.has(cell),
            'cell--pending': pending === cell,
            'cell--marked': markedSet.has(cell),
          },
        ]"
        :disabled="!clickableSet.has(cell)"
        @click="emit('cell', cell)"
      />
    </template>
  </div>
</template>

<style scoped>
.sea {
  --gap: 3px;
  display: grid;
  grid-template-columns: 16px repeat(10, minmax(0, 1fr));
  gap: var(--gap);
  width: 100%;
  user-select: none;
  -webkit-user-select: none;
}

.sea--compact {
  --gap: 2px;
  grid-template-columns: 12px repeat(10, minmax(0, 1fr));
}

.sea__axis {
  display: flex;
  align-items: center;
  justify-content: center;
  font: 11px/1 var(--font-mono);
  color: var(--text-faint);
}

.sea--compact .sea__axis {
  font-size: 11px;
  transform: scale(0.85);
}

.cell {
  position: relative;
  aspect-ratio: 1;
  padding: 0;
  border: none;
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--accent) 7%, var(--surface-raised));
  transition: background-color 0.15s ease, box-shadow 0.15s ease;
}

.sea--compact .cell {
  border-radius: 3px;
}

.cell:disabled {
  cursor: default;
}

.cell--clickable {
  cursor: pointer;
}

.cell--clickable:hover {
  background: color-mix(in srgb, var(--accent) 28%, var(--surface-raised));
}

.cell--ship {
  background: color-mix(in srgb, var(--accent) 70%, var(--surface-raised));
}

.cell--clickable.cell--ship:hover {
  background: color-mix(in srgb, var(--danger) 45%, var(--surface-raised));
}

/* Стыки палуб: корабль — одна плашка, а не набор квадратиков. */
.cell--joint-right { border-top-right-radius: 0; border-bottom-right-radius: 0; }
.cell--joint-left { border-top-left-radius: 0; border-bottom-left-radius: 0; }
.cell--joint-bottom { border-bottom-left-radius: 0; border-bottom-right-radius: 0; }
.cell--joint-top { border-top-left-radius: 0; border-top-right-radius: 0; }

.cell--ship.cell--joint-right::before,
.cell--hit.cell--joint-right::before,
.cell--sunk.cell--joint-right::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  right: calc(-1 * var(--gap));
  width: var(--gap);
  background: inherit;
}

.cell--ship.cell--joint-bottom::before,
.cell--hit.cell--joint-bottom::before,
.cell--sunk.cell--joint-bottom::before {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(-1 * var(--gap));
  height: var(--gap);
  background: inherit;
}

.cell--miss {
  background: color-mix(in srgb, var(--accent) 3%, var(--surface));
}

.cell--miss::after {
  content: '';
  position: absolute;
  inset: 0;
  margin: auto;
  width: 22%;
  height: 22%;
  border-radius: 50%;
  background: var(--text-faint);
}

.cell--hit {
  background: color-mix(in srgb, var(--danger) 35%, var(--surface-raised));
}

.cell--sunk {
  background: color-mix(in srgb, var(--danger) 70%, var(--surface));
}

/* Крестик попадания — две диагонали. */
.cell--hit::after,
.cell--sunk::after {
  content: '';
  position: absolute;
  inset: 22%;
  background:
    linear-gradient(45deg, transparent 43%, var(--text) 43%, var(--text) 57%, transparent 57%),
    linear-gradient(-45deg, transparent 43%, var(--text) 43%, var(--text) 57%, transparent 57%);
}

/* Свежие выстрелы соперника — обводка, чтобы было видно, куда прилетело. */
.cell--recent {
  box-shadow: inset 0 0 0 2px var(--prio-medium);
}

.cell--marked {
  box-shadow: inset 0 0 0 2px var(--success);
}

.cell--pending::after {
  content: '';
  position: absolute;
  inset: 0;
  margin: auto;
  width: 40%;
  height: 40%;
  border-radius: 50%;
  background: var(--accent);
  animation: sea-ping 0.8s ease-in-out infinite alternate;
}

@keyframes sea-ping {
  from { opacity: 0.35; transform: scale(0.7); }
  to { opacity: 1; transform: scale(1); }
}
</style>
