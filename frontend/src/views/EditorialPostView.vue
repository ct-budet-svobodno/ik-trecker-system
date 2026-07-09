<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import CommentThread from '../components/CommentThread.vue'
import EditorialPostModal from '../components/EditorialPostModal.vue'
import { fetchDirections } from '../api/directions'
import { fetchUsers } from '../api/users'
import {
  EDITORIAL_ROLE_LABELS,
  EDITORIAL_STATUS_COLORS,
  EDITORIAL_STATUS_LABELS,
} from '../constants/editorialMeta'
import { useAuthStore } from '../stores/auth'
import { useEditorialStore } from '../stores/editorial'
import { getAvatarColor, getInitials } from '../utils/avatar'
import { parseDateOnly } from '../utils/dateKey'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const store = useEditorialStore()

const post = computed(() => store.currentPost)
const me = computed(() => authStore.user)

const directions = ref([])
const members = ref([])
const error = ref('')
const showMetaModal = ref(false)

const textDraft = ref('')
const figmaDraft = ref('')
const designDoneDraft = ref(false)

const dateLabel = computed(() => {
  if (!post.value) return ''
  return new Intl.DateTimeFormat('ru-RU', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  }).format(parseDateOnly(post.value.date))
})

// --- Права (зеркалят бэкенд; бэкенд остаётся источником истины) ---
function headsShort(code) {
  return directions.value.some(
    (d) => d.short_code === code && d.heads.some((h) => h.id === me.value?.id),
  )
}
const isAdmin = computed(() => authStore.isAdmin)
const isTextReviewer = computed(() => isAdmin.value || headsShort('СМИ'))
const isDesignReviewer = computed(() => isAdmin.value || headsShort('Дизайн'))
const isEditor = computed(() => isTextReviewer.value || isDesignReviewer.value)

const isWriter = computed(() => post.value && post.value.writer_id === me.value?.id)
const isDesigner = computed(() => post.value && post.value.designer_id === me.value?.id)

const canEditText = computed(() => isWriter.value || isEditor.value)
const canEditDesign = computed(() => isDesigner.value || isEditor.value)

const textComments = computed(() => (post.value?.comments ?? []).filter((c) => c.target === 'text'))
const designComments = computed(() => (post.value?.comments ?? []).filter((c) => c.target === 'design'))

const canCommentText = computed(() => isWriter.value || isTextReviewer.value || isEditor.value)
const canCommentDesign = computed(() => isDesigner.value || isDesignReviewer.value || isEditor.value)

async function loadEverything() {
  error.value = ''
  try {
    directions.value = await fetchDirections()
    await store.loadPost(route.params.id)
    textDraft.value = post.value?.text_content ?? ''
    figmaDraft.value = post.value?.figma_url ?? ''
    designDoneDraft.value = post.value?.design_done ?? false
    if (isEditor.value) {
      const users = await fetchUsers()
      members.value = users.filter((u) => u.is_editorial && u.is_active)
    }
  } catch (err) {
    if (err.response?.status === 403 || err.response?.status === 404) {
      router.replace({ name: 'editorial' })
      return
    }
    error.value = 'Не удалось загрузить пост'
  }
}

onMounted(loadEverything)
watch(() => route.params.id, loadEverything)

async function run(fn) {
  error.value = ''
  try {
    await fn()
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось выполнить действие'
  }
}

const id = computed(() => post.value?.id)

// Текст
const saveText = () => run(() => store.update(id.value, { text_content: textDraft.value }))
const submitText = () =>
  run(() => store.update(id.value, { text_content: textDraft.value, text_status: 'review' }))
const setTextStatus = (status) => run(() => store.update(id.value, { text_status: status }))

// Дизайн
const saveDesign = () =>
  run(() =>
    store.update(id.value, {
      figma_url: figmaDraft.value.trim() || null,
      design_done: designDoneDraft.value,
    }),
  )
const submitDesign = () =>
  run(() =>
    store.update(id.value, {
      figma_url: figmaDraft.value.trim() || null,
      design_done: designDoneDraft.value,
      design_status: 'review',
    }),
  )
const setDesignStatus = (status) => run(() => store.update(id.value, { design_status: status }))

// Роли
const assignSelf = (role) => run(() => store.assign(id.value, role))
const assignUser = (role, userId) => run(() => store.assign(id.value, role, userId))
const unassignRole = (role) => run(() => store.unassign(id.value, role))

// Комментарии
const addComment = (target, { body, parentId }) =>
  run(() => store.comment(id.value, { target, body, parent_id: parentId }))
const resolveComment = ({ id: cid, resolved }) => run(() => store.resolve(id.value, cid, resolved))
const removeComment = ({ id: cid }) => run(() => store.removeComment(id.value, cid))

function statusColor(status) {
  return EDITORIAL_STATUS_COLORS[status]
}
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <button class="back" @click="router.push({ name: 'editorial' })">‹ К календарю</button>

      <p v-if="error" class="alert">{{ error }}</p>

      <AppLoader v-if="!post && !error" />

      <template v-if="post">
        <!-- Шапка -->
        <div class="head">
          <div>
            <p class="breadcrumb">
              {{ dateLabel }}<span v-if="post.format"> · {{ post.format }}</span>
            </p>
            <h1>{{ post.title }}</h1>
          </div>
          <button v-if="isEditor" class="btn-ghost" @click="showMetaModal = true">Изменить</button>
        </div>

        <!-- Описание -->
        <section v-if="post.brief || post.reference" class="card brief">
          <p v-if="post.brief" class="brief__text">{{ post.brief }}</p>
          <a v-if="post.reference" :href="post.reference" target="_blank" rel="noopener" class="brief__ref">
            Референс ↗
          </a>
        </section>

        <!-- Роли -->
        <section class="card roles">
          <div v-for="role in ['writer', 'designer']" :key="role" class="role">
            <span class="role__label">{{ EDITORIAL_ROLE_LABELS[role] }}</span>
            <template v-if="post[`${role}_id`]">
              <span class="role__person">
                <span class="role__avatar" :style="{ background: getAvatarColor(post[`${role}_id`]) }">
                  {{ getInitials(post[role].full_name) }}
                </span>
                {{ post[role].full_name }}
              </span>
              <button
                v-if="isEditor || post[`${role}_id`] === me?.id"
                class="link"
                @click="unassignRole(role)"
              >
                снять
              </button>
            </template>
            <template v-else>
              <span class="role__empty">не назначен</span>
              <button v-if="authStore.isEditorial" class="btn-mini" @click="assignSelf(role)">
                Стать {{ role === 'writer' ? 'райтером' : 'дизайнером' }}
              </button>
              <select
                v-if="isEditor && members.length"
                class="role__select"
                @change="assignUser(role, Number($event.target.value)); $event.target.value = ''"
              >
                <option value="">назначить…</option>
                <option v-for="m in members" :key="m.id" :value="m.id">{{ m.full_name }}</option>
              </select>
            </template>
          </div>
        </section>

        <div class="panels">
          <!-- Панель текста -->
          <section class="card panel">
            <div class="panel__head">
              <h2>Текст</h2>
              <span class="badge" :style="{ color: statusColor(post.text_status) }">
                {{ EDITORIAL_STATUS_LABELS[post.text_status] }}
              </span>
            </div>

            <textarea
              v-if="canEditText"
              v-model="textDraft"
              rows="12"
              class="editor"
              placeholder="Пишите текст поста здесь…"
            />
            <p v-else class="readonly">{{ post.text_content || 'Текст ещё не написан.' }}</p>

            <div v-if="canEditText" class="panel__actions">
              <button class="btn-ghost" @click="saveText">Сохранить</button>
              <button class="btn-primary" @click="submitText">Отправить на проверку</button>
            </div>
            <div v-if="isTextReviewer" class="panel__actions">
              <button class="btn-ghost" @click="setTextStatus('fixes')">Вернуть на правки</button>
              <button class="btn-primary" @click="setTextStatus('ready')">Принять</button>
            </div>

            <h3 class="panel__sub">Правки</h3>
            <CommentThread
              :comments="textComments"
              :can-comment="canCommentText"
              :can-resolve="isTextReviewer || isEditor"
              :current-user-id="me?.id"
              @add="addComment('text', $event)"
              @resolve="resolveComment"
              @remove="removeComment"
            />
          </section>

          <!-- Панель дизайна -->
          <section class="card panel">
            <div class="panel__head">
              <h2>Дизайн</h2>
              <span class="badge" :style="{ color: statusColor(post.design_status) }">
                {{ EDITORIAL_STATUS_LABELS[post.design_status] }}
              </span>
            </div>

            <template v-if="canEditDesign">
              <label class="field-label">Ссылка на Figma</label>
              <input v-model="figmaDraft" class="editor editor--input" placeholder="https://figma.com/…" />
              <label class="check">
                <input v-model="designDoneDraft" type="checkbox" />
                Дизайн готов
              </label>
              <div class="panel__actions">
                <button class="btn-ghost" @click="saveDesign">Сохранить</button>
                <button class="btn-primary" @click="submitDesign">Отправить на проверку</button>
              </div>
            </template>
            <template v-else>
              <a v-if="post.figma_url" :href="post.figma_url" target="_blank" rel="noopener" class="brief__ref">
                Открыть в Figma ↗
              </a>
              <p v-else class="readonly">Дизайн ещё не прикреплён.</p>
              <p class="readonly readonly--small">
                {{ post.design_done ? 'Отмечен как готовый' : 'Ещё в работе' }}
              </p>
            </template>

            <div v-if="isDesignReviewer" class="panel__actions">
              <button class="btn-ghost" @click="setDesignStatus('fixes')">Вернуть на правки</button>
              <button class="btn-primary" @click="setDesignStatus('ready')">Принять</button>
            </div>

            <h3 class="panel__sub">Правки</h3>
            <CommentThread
              :comments="designComments"
              :can-comment="canCommentDesign"
              :can-resolve="isDesignReviewer || isEditor"
              :current-user-id="me?.id"
              @add="addComment('design', $event)"
              @resolve="resolveComment"
              @remove="removeComment"
            />
          </section>
        </div>
      </template>

      <EditorialPostModal
        v-if="showMetaModal && post"
        :post="post"
        @close="showMetaModal = false"
      />
    </main>
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
  max-width: 1100px;
}

.back {
  border: none;
  background: none;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  margin-bottom: 14px;
}

.back:hover {
  color: var(--text);
}

.alert {
  background: color-mix(in srgb, var(--danger) 14%, transparent);
  color: var(--danger);
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 14px;
}

.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.breadcrumb {
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--text-faint);
  margin: 0 0 6px;
  text-transform: capitalize;
}

h1 {
  font-size: 24px;
  margin: 0;
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 18px;
  margin-bottom: 16px;
}

.brief__text {
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.brief__ref {
  display: inline-block;
  margin-top: 8px;
  color: var(--accent);
  font-size: 13px;
  text-decoration: none;
}

.brief__ref:hover {
  text-decoration: underline;
}

.roles {
  display: flex;
  gap: 28px;
  flex-wrap: wrap;
}

.role {
  display: flex;
  align-items: center;
  gap: 10px;
}

.role__label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-faint);
}

.role__person {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.role__avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
}

.role__empty {
  font-size: 13px;
  color: var(--text-faint);
}

.role__select {
  border: 1px solid var(--border);
  border-radius: 7px;
  background: var(--surface-raised);
  color: var(--text);
  padding: 5px 8px;
  font-size: 12.5px;
}

.panels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

@media (max-width: 900px) {
  .panels {
    grid-template-columns: 1fr;
  }
}

.panel {
  margin-bottom: 0;
}

.panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.panel__head h2 {
  margin: 0;
  font-size: 16px;
}

.badge {
  font-size: 12px;
  font-weight: 600;
}

.editor {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-raised);
  color: var(--text);
  font-family: inherit;
  font-size: 14px;
  line-height: 1.5;
  resize: vertical;
}

.editor--input {
  resize: none;
}

.field-label {
  display: block;
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.readonly {
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
  color: var(--text);
  margin: 0;
}

.readonly--small {
  font-size: 12.5px;
  color: var(--text-muted);
  margin-top: 6px;
}

.check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
  margin: 10px 0;
}

.check input {
  width: 16px;
  height: 16px;
}

.panel__actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.panel__sub {
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-faint);
  margin: 20px 0 12px;
  border-top: 1px solid var(--border);
  padding-top: 16px;
}

.btn-primary {
  border: none;
  border-radius: 8px;
  background: var(--accent);
  color: #fff;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.btn-primary:hover {
  background: var(--accent-hover);
}

.btn-ghost {
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text);
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
}

.btn-ghost:hover {
  background: var(--surface-hover);
}

.btn-mini {
  border: none;
  border-radius: 7px;
  background: var(--accent);
  color: #fff;
  padding: 5px 12px;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
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
  color: var(--danger);
}

@media (max-width: 768px) {
  h1 {
    font-size: 20px;
  }

  .roles {
    flex-direction: column;
    align-items: stretch;
    gap: 14px;
  }

  .role {
    flex-wrap: wrap;
  }

  .card {
    padding: 14px;
  }
}
</style>
