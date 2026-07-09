<script setup>
import { computed, ref } from 'vue'

import { getAvatarColor, getInitials } from '../utils/avatar'

const props = defineProps({
  comments: { type: Array, default: () => [] },
  canComment: { type: Boolean, default: false },
  canResolve: { type: Boolean, default: false },
  currentUserId: { type: Number, default: null },
})

const emit = defineEmits(['add', 'resolve', 'remove'])

const dtFmt = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
})

// Треды: корневые комментарии + их ответы.
const threads = computed(() => {
  const roots = props.comments.filter((c) => c.parent_id == null)
  return roots.map((root) => ({
    ...root,
    replies: props.comments.filter((c) => c.parent_id === root.id),
  }))
})

const newComment = ref('')
const replyTo = ref(null)
const replyText = ref('')

function submitRoot() {
  const body = newComment.value.trim()
  if (!body) return
  emit('add', { body, parentId: null })
  newComment.value = ''
}

function openReply(id) {
  replyTo.value = id
  replyText.value = ''
}

function submitReply(id) {
  const body = replyText.value.trim()
  if (!body) return
  emit('add', { body, parentId: id })
  replyTo.value = null
  replyText.value = ''
}

function canDelete(comment) {
  return props.canResolve || comment.author_id === props.currentUserId
}

function fmt(iso) {
  return dtFmt.format(new Date(iso))
}
</script>

<template>
  <div class="thread">
    <p v-if="!threads.length" class="thread__empty">Пока нет комментариев.</p>

    <div v-for="root in threads" :key="root.id" class="comment" :class="{ 'comment--resolved': root.resolved }">
      <div class="comment__main">
        <span class="comment__avatar" :style="{ background: getAvatarColor(root.author_id) }">
          {{ getInitials(root.author.full_name) }}
        </span>
        <div class="comment__body">
          <div class="comment__head">
            <span class="comment__name">{{ root.author.full_name }}</span>
            <span class="comment__time">{{ fmt(root.created_at) }}</span>
            <span v-if="root.resolved" class="comment__badge">решено</span>
          </div>
          <p class="comment__text">{{ root.body }}</p>
          <div class="comment__actions">
            <button v-if="canComment" type="button" class="link" @click="openReply(root.id)">Ответить</button>
            <button v-if="canResolve" type="button" class="link" @click="emit('resolve', { id: root.id, resolved: !root.resolved })">
              {{ root.resolved ? 'Вернуть' : 'Решено' }}
            </button>
            <button v-if="canDelete(root)" type="button" class="link link--danger" @click="emit('remove', { id: root.id })">Удалить</button>
          </div>
        </div>
      </div>

      <!-- Ответы -->
      <div v-for="reply in root.replies" :key="reply.id" class="comment comment--reply">
        <div class="comment__main">
          <span class="comment__avatar" :style="{ background: getAvatarColor(reply.author_id) }">
            {{ getInitials(reply.author.full_name) }}
          </span>
          <div class="comment__body">
            <div class="comment__head">
              <span class="comment__name">{{ reply.author.full_name }}</span>
              <span class="comment__time">{{ fmt(reply.created_at) }}</span>
            </div>
            <p class="comment__text">{{ reply.body }}</p>
            <div class="comment__actions">
              <button v-if="canDelete(reply)" type="button" class="link link--danger" @click="emit('remove', { id: reply.id })">Удалить</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Форма ответа -->
      <form v-if="replyTo === root.id" class="reply-form" @submit.prevent="submitReply(root.id)">
        <textarea v-model="replyText" rows="2" placeholder="Ответ…" autofocus />
        <div class="reply-form__actions">
          <button type="button" class="link" @click="replyTo = null">Отмена</button>
          <button type="submit" class="btn-mini">Ответить</button>
        </div>
      </form>
    </div>

    <form v-if="canComment" class="add-form" @submit.prevent="submitRoot">
      <textarea v-model="newComment" rows="2" placeholder="Оставить комментарий…" />
      <button type="submit" class="btn-mini" :disabled="!newComment.trim()">Отправить</button>
    </form>
  </div>
</template>

<style scoped>
.thread {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.thread__empty {
  color: var(--text-faint);
  font-size: 13px;
  margin: 0;
}

.comment--resolved {
  opacity: 0.6;
}

.comment__main {
  display: flex;
  gap: 10px;
}

.comment--reply {
  margin-left: 34px;
  margin-top: 8px;
}

.comment__avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.comment__body {
  flex: 1;
  min-width: 0;
}

.comment__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.comment__name {
  font-size: 13px;
  font-weight: 600;
}

.comment__time {
  font-size: 11px;
  color: var(--text-faint);
}

.comment__badge {
  font-size: 10px;
  background: color-mix(in srgb, var(--status-done) 20%, transparent);
  color: var(--status-done);
  border-radius: 5px;
  padding: 1px 6px;
}

.comment__text {
  margin: 3px 0 4px;
  font-size: 13.5px;
  line-height: 1.4;
  white-space: pre-wrap;
  word-break: break-word;
}

.comment__actions {
  display: flex;
  gap: 12px;
}

.link {
  border: none;
  background: none;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}

.link:hover {
  color: var(--text);
}

.link--danger:hover {
  color: var(--danger);
}

.reply-form,
.add-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}

.reply-form {
  margin-left: 34px;
}

.reply-form__actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

textarea {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font-family: inherit;
  font-size: 13.5px;
  resize: vertical;
}

.btn-mini {
  align-self: flex-start;
  border: none;
  border-radius: 7px;
  background: var(--accent);
  color: #fff;
  padding: 6px 12px;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
}

.btn-mini:disabled {
  opacity: 0.5;
}
</style>
