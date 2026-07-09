<script setup>
import { computed } from 'vue'

import BaseIcon from './BaseIcon.vue'
import { PRIORITY_META, STATUS_META } from '../constants/taskMeta'
import { getAvatarColor, getInitials } from '../utils/avatar'
import { formatDueDate } from '../utils/formatDate'

const props = defineProps({
  task: { type: Object, required: true },
  // На канбан-доске статус задаётся колонкой — бейдж на карточке скрываем.
  showStatus: { type: Boolean, default: true },
})

const statusMeta = computed(() => STATUS_META[props.task.status])
const priorityMeta = computed(() => PRIORITY_META[props.task.priority])
</script>

<template>
  <article class="task-card" :class="[`task-card--${priorityMeta.tone}`, `task-card--dir-${task.direction.color}`]">
    <header class="task-card__head">
      <div class="task-card__labels">
        <span class="chip" :class="`chip--${task.direction.color}`">{{ task.direction.short_code }}</span>
        <span class="prio" :class="`prio--${priorityMeta.tone}`">
          <span class="prio__mark" />{{ priorityMeta.label }}
        </span>
      </div>
      <span v-if="showStatus" class="status">
        <span class="status__dot" :class="`status__dot--${statusMeta.color}`" />
        {{ statusMeta.label }}
      </span>
    </header>

    <h3 class="task-card__title">{{ task.title }}</h3>
    <p v-if="task.description" class="task-card__desc">{{ task.description }}</p>

    <footer class="task-card__foot">
      <div class="assignee">
        <span
          v-if="task.assignee"
          class="assignee__avatar"
          :style="{ background: getAvatarColor(task.assignee.id) }"
        >
          {{ getInitials(task.assignee.full_name) }}
        </span>
        <span v-else class="assignee__avatar assignee__avatar--empty">—</span>
        <span class="assignee__name">{{ task.assignee?.full_name ?? 'Не назначен' }}</span>
      </div>
      <span class="due">
        <BaseIcon name="calendar" :size="13" />
        <span class="due__date">{{ formatDueDate(task.due_date) }}</span>
      </span>
    </footer>
  </article>
</template>

<style scoped>
.task-card {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 15px 16px 13px;
  display: flex;
  flex-direction: column;
  gap: 9px;
  overflow: hidden;
  transition:
    border-color 0.18s ease,
    background 0.18s ease,
    box-shadow 0.18s ease,
    transform 0.18s ease;
}

/* Полоска слева = направление (идентичность). Приоритет показан чипом в шапке. */
.task-card::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--border-strong);
}
.task-card--dir-violet::before { background: var(--dir-ct); }
.task-card--dir-blue::before { background: var(--dir-prod); }
.task-card--dir-pink::before { background: var(--dir-design); }
.task-card--dir-green::before { background: var(--dir-photo); }
.task-card--dir-orange::before { background: var(--dir-smi); }
.task-card--dir-cyan::before { background: var(--dir-nvk); }

.task-card:hover {
  border-color: var(--border-strong);
  background: var(--surface-hover);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
}

@media (prefers-reduced-motion: no-preference) {
  .task-card:hover {
    transform: translateY(-3px);
  }
}

.task-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.task-card__labels {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

/* Направление = идентичность (заполненный приглушённый чип). */
.chip {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  padding: 3px 8px;
  border-radius: 6px;
  white-space: nowrap;
}

.chip--violet { background: color-mix(in srgb, var(--dir-ct) 16%, transparent); color: color-mix(in srgb, var(--dir-ct) 62%, #fff); }
.chip--blue { background: linear-gradient(135deg, color-mix(in srgb, var(--dir-prod-a) 18%, transparent), color-mix(in srgb, var(--dir-prod-b) 18%, transparent)); color: color-mix(in srgb, var(--dir-prod-a) 60%, #fff); }
.chip--pink { background: color-mix(in srgb, var(--dir-design) 16%, transparent); color: color-mix(in srgb, var(--dir-design) 64%, #fff); }
.chip--green { background: color-mix(in srgb, var(--dir-photo) 20%, transparent); color: color-mix(in srgb, var(--dir-photo) 55%, #fff); }
.chip--orange { background: color-mix(in srgb, var(--dir-smi) 16%, transparent); color: color-mix(in srgb, var(--dir-smi) 64%, #fff); }
.chip--cyan { background: color-mix(in srgb, var(--dir-nvk) 22%, transparent); color: color-mix(in srgb, var(--dir-nvk) 60%, #fff); }

/* Приоритет = интенсивность (ghost-стиль, легче чипа направления). */
.prio {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
  color: var(--text-faint);
}

.prio__mark {
  width: 6px;
  height: 6px;
  border-radius: 2px;
  background: var(--prio-low);
}

.prio--medium { color: var(--prio-medium); }
.prio--medium .prio__mark { background: var(--prio-medium); }
.prio--high { color: var(--prio-high); }
.prio--high .prio__mark { background: var(--prio-high); }

/* Статус = семантика. */
.status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}

.status__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.status__dot--grey { background: var(--status-todo); }
.status__dot--orange { background: var(--status-progress); }
.status__dot--purple { background: var(--status-review); }
.status__dot--green { background: var(--status-done); }

.task-card__title {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.35;
  margin: 2px 0 0;
  color: var(--text);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.task-card__desc {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-muted);
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.task-card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 3px;
}

.assignee {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.assignee__avatar {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  flex-shrink: 0;
}

.assignee__avatar--empty {
  background: var(--surface-raised);
  color: var(--text-faint);
}

.assignee__name {
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.due {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
  color: var(--text-faint);
}

.due__date {
  font-family: var(--font-mono);
  font-size: 11.5px;
  letter-spacing: -0.01em;
  color: var(--text-muted);
}
</style>
