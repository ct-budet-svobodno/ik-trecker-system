<script setup>
import { computed } from 'vue'

import BaseIcon from './BaseIcon.vue'
import { PRIORITY_META, STATUS_META } from '../constants/taskMeta'
import { getAvatarColor, getInitials } from '../utils/avatar'
import { formatDueDate } from '../utils/formatDate'
import { assigneesDone, isOverdue } from '../utils/taskProgress'

const props = defineProps({
  task: { type: Object, required: true },
  // На канбан-доске статус задаётся колонкой — бейдж на карточке скрываем.
  showStatus: { type: Boolean, default: true },
})

const statusMeta = computed(() => STATUS_META[props.task.status])
const priorityMeta = computed(() => PRIORITY_META[props.task.priority])
const overdue = computed(() => isOverdue(props.task))

// Поручение нескольким: аватарки внахлёст и сколько уже сделали.
const team = computed(() => props.task.assignees ?? [])
const isTeam = computed(() => team.value.length > 1)
const teamDone = computed(() => assigneesDone(props.task))
const AVATARS_SHOWN = 4
</script>

<template>
  <article
    class="task-card"
    :class="[
      `task-card--${priorityMeta.tone}`,
      task.direction ? `task-card--dir-${task.direction.color}` : 'task-card--private',
      { 'task-card--done': task.status === 'done' },
    ]"
  >
    <header class="task-card__head">
      <div class="task-card__labels">
        <span v-if="task.direction" class="chip" :class="`chip--${task.direction.color}`">
          {{ task.direction.short_code }}
        </span>
        <span v-else class="chip chip--private" title="Видят автор, исполнитель, админы и секретарь">
          <BaseIcon name="lock" :size="12" />
          {{ task.is_checklist ? 'Чек-лист' : 'Поручение' }}
        </span>
        <span class="prio" :class="`prio--${priorityMeta.tone}`">
          <span class="prio__mark" />{{ priorityMeta.label }}
        </span>
      </div>
      <span v-if="showStatus" class="status">
        <span class="status__dot" :class="`status__dot--${statusMeta.color}`" />
        {{ task.is_checklist && task.status === 'todo' ? 'Не начато' : task.is_checklist && task.status === 'done' ? 'Сделано' : statusMeta.label }}
      </span>
    </header>

    <h3 class="task-card__title">{{ task.title }}</h3>
    <p v-if="(task.is_private || task.is_checklist) && task.created_by" class="task-card__from">
      от {{ task.created_by.full_name }}
    </p>
    <p v-if="task.description" class="task-card__desc">{{ task.description }}</p>

    <footer class="task-card__foot">
      <div v-if="isTeam" class="team" :title="team.map((a) => a.user.full_name).join(', ')">
        <span class="team__avatars">
          <span
            v-for="a in team.slice(0, AVATARS_SHOWN)"
            :key="a.user.id"
            class="assignee__avatar team__avatar"
            :class="{ 'team__avatar--done': a.status === 'done' }"
            :style="{ background: getAvatarColor(a.user.id) }"
          >
            {{ getInitials(a.user.full_name) }}
          </span>
          <span v-if="team.length > AVATARS_SHOWN" class="assignee__avatar team__avatar team__more">
            +{{ team.length - AVATARS_SHOWN }}
          </span>
        </span>
        <span class="team__progress">
          <span class="team__bar">
            <span class="team__fill" :style="{ width: `${(teamDone / team.length) * 100}%` }" />
          </span>
          <span class="team__count">{{ teamDone }}/{{ team.length }}</span>
        </span>
      </div>
      <div v-else class="assignee">
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
      <span v-if="task.comments_count" class="comments" :title="`Комментариев: ${task.comments_count}`">
        <BaseIcon name="chat" :size="13" />
        {{ task.comments_count }}
      </span>
      <span class="due" :class="{ 'due--overdue': overdue }">
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
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
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
.task-card--private::before { background: var(--accent); }

.task-card:hover {
  border-color: var(--border-strong);
  background: var(--surface-hover);
  box-shadow: var(--shadow-lift);
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
.chip--private {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--accent-soft);
  color: var(--text);
}
.chip--cyan { background: color-mix(in srgb, var(--dir-nvk) 22%, transparent); color: color-mix(in srgb, var(--dir-nvk) 60%, #fff); }

/* Приоритет = интенсивность (ghost-стиль, легче чипа направления). */
.prio {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
  color: var(--text-muted);
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
  line-height: 20px;
  margin: 0;
  color: var(--text);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.task-card__from {
  margin: -4px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}

.task-card__desc {
  font-size: 13px;
  line-height: 19px;
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

.comments {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  font: 12px var(--font-mono);
  color: var(--text-muted);
}

.team {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.team__avatars {
  display: flex;
  flex-shrink: 0;
}

/* Внахлёст, с обводкой цветом карточки — чтобы кружки читались по отдельности. */
.team__avatar {
  box-shadow: 0 0 0 2px var(--surface);
}

.team__avatar + .team__avatar {
  margin-left: -3px;
}

.team__avatar--done {
  box-shadow: 0 0 0 2px var(--status-done);
}

.team__more {
  background: var(--surface-raised);
  color: var(--text-muted);
}

.team__progress {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.team__bar {
  width: 44px;
  height: 4px;
  border-radius: var(--radius-full);
  background: var(--border);
  overflow: hidden;
}

.team__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--status-done);
  transition: width 0.25s ease;
}

.team__count {
  font: 12px var(--font-mono);
  color: var(--text-muted);
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
  font-size: 11px;
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

.due--overdue,
.due--overdue .due__date {
  color: var(--danger);
}

/* Готовые не спорят за внимание с открытыми. */
.task-card--done .task-card__title {
  color: var(--text-muted);
  text-decoration: line-through;
  text-decoration-color: var(--text-faint);
}

.task-card--done .task-card__desc {
  display: none;
}

.due__date {
  font-family: var(--font-mono);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  color: var(--text-muted);
}
</style>
