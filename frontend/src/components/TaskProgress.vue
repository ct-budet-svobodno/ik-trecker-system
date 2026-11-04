<script setup>
import { computed } from 'vue'

import { STATUS_META } from '../constants/taskMeta'
import { STATUS_STEPS } from '../utils/taskProgress'

// Прогресс по задачам текущей области: процент готовых, полоса по статусам
// и счётчики, которые заодно работают фильтром списка.
const props = defineProps({
  stats: { type: Object, required: true },
  // null | статус | 'overdue'
  filter: { type: String, default: null },
})

const emit = defineEmits(['update:filter'])

const segments = computed(() =>
  STATUS_STEPS.filter((status) => props.stats[status] > 0).map((status) => ({
    status,
    color: STATUS_META[status].color,
    width: (props.stats[status] / props.stats.total) * 100,
  })),
)

const chips = computed(() => [
  { value: null, label: 'Все', count: props.stats.total },
  ...STATUS_STEPS.map((status) => ({
    value: status,
    label: STATUS_META[status].label,
    count: props.stats[status],
    color: STATUS_META[status].color,
  })),
])

function toggle(value) {
  emit('update:filter', props.filter === value ? null : value)
}
</script>

<template>
  <section class="progress" aria-label="Прогресс по задачам">
    <div class="progress__head">
      <div class="progress__main">
        <span class="progress__percent">{{ stats.percent }}<span class="progress__unit">%</span></span>
        <span class="progress__caption">
          <template v-if="stats.total">готово {{ stats.done }} из {{ stats.total }}</template>
          <template v-else>задач пока нет</template>
        </span>
      </div>
      <button
        v-if="stats.overdue"
        class="overdue"
        :class="{ 'overdue--active': filter === 'overdue' }"
        @click="toggle('overdue')"
      >
        Просрочено <span class="overdue__num">{{ stats.overdue }}</span>
      </button>
    </div>

    <div
      class="bar"
      role="progressbar"
      :aria-valuenow="stats.percent"
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <span
        v-for="seg in segments"
        :key="seg.status"
        class="bar__seg"
        :class="`bar__seg--${seg.color}`"
        :style="{ width: `${seg.width}%` }"
      />
    </div>

    <div class="chips">
      <button
        v-for="chip in chips"
        :key="chip.label"
        class="chip"
        :class="{ 'chip--active': filter === chip.value }"
        @click="chip.value === null ? emit('update:filter', null) : toggle(chip.value)"
      >
        <span v-if="chip.color" class="chip__dot" :class="`chip__dot--${chip.color}`" />
        {{ chip.label }}
        <span class="chip__num">{{ chip.count }}</span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.progress {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-bottom: var(--space-5);
}

.progress__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-3);
}

.progress__main {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  min-width: 0;
}

.progress__percent {
  font: 500 24px/1 var(--font-display);
  font-variant-numeric: tabular-nums;
  color: var(--text);
}

.progress__unit {
  font-size: 15px;
  color: var(--text-muted);
  margin-left: 2px;
}

.progress__caption {
  font-size: 13px;
  color: var(--text-muted);
  white-space: nowrap;
}

.overdue {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  height: 28px;
  padding: 0 10px;
  border: 1px solid color-mix(in srgb, var(--danger) 40%, transparent);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--danger) 10%, transparent);
  color: var(--danger);
  font-size: 12px;
  font-weight: 500;
}

.overdue--active {
  background: color-mix(in srgb, var(--danger) 22%, transparent);
  border-color: var(--danger);
}

.overdue__num {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

/* Полоса: сегменты по статусам в порядке шагов, ширина — доля задач. */
.bar {
  display: flex;
  gap: 2px;
  height: 8px;
  border-radius: var(--radius-sm);
  background: var(--surface-raised);
  overflow: hidden;
}

.bar__seg {
  height: 100%;
  transition: width 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.bar__seg--grey { background: var(--status-todo); }
.bar__seg--orange { background: var(--status-progress); }
.bar__seg--purple { background: var(--status-review); }
.bar__seg--green { background: var(--status-done); }

.chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-muted);
  font-size: 13px;
  white-space: nowrap;
}

.chip:hover {
  color: var(--text);
}

.chip--active {
  background: var(--accent-soft);
  border-color: var(--accent);
  color: var(--text);
}

.chip__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.chip__dot--grey { background: var(--status-todo); }
.chip__dot--orange { background: var(--status-progress); }
.chip__dot--purple { background: var(--status-review); }
.chip__dot--green { background: var(--status-done); }

.chip__num {
  font-family: var(--font-mono);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  color: var(--text-faint);
}

.chip--active .chip__num {
  color: var(--text-muted);
}

@media (max-width: 768px) {
  .progress {
    margin-bottom: var(--space-4);
  }

  /* Счётчики — в одну строку со свайпом, на всю ширину экрана. */
  .chips {
    flex-wrap: nowrap;
    overflow-x: auto;
    margin: 0 calc(-1 * var(--space-4));
    padding: 0 var(--space-4);
    scrollbar-width: none;
  }

  .chips::-webkit-scrollbar {
    display: none;
  }

  .chip {
    height: 36px;
    flex-shrink: 0;
  }
}
</style>
