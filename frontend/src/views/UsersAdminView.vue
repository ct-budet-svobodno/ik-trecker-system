<script setup>
import { onMounted, ref } from 'vue'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import { fetchDirections, setDirectionHeads } from '../api/directions'
import { createUser, fetchUsers, updateUser } from '../api/users'
import { LEADERSHIP_POSITION_LABELS, ROLE_LABELS } from '../constants/roleLabels'
import { getAvatarColor, getInitials } from '../utils/avatar'

const ROLES = Object.entries(ROLE_LABELS) // [[key,label],...]
const POSITIONS = Object.entries(LEADERSHIP_POSITION_LABELS)

const users = ref([])
const directions = ref([])
const isLoading = ref(false)
const errorMessage = ref('')

// short_code направлений, где пользователь — руководитель.
function headedDirections(user) {
  return directions.value.filter((d) => d.heads.some((h) => h.id === user.id))
}

// --- Создание ---
const draft = ref({ username: '', full_name: '', password: '', role: 'employee' })
const creating = ref(false)
const createError = ref('')

// --- Редактирование ---
const editing = ref(null) // { id, full_name, role, leadership_position, is_active, password }
const saving = ref(false)
const editError = ref('')

// Простой читаемый пароль (без похожих символов) — чтобы выдать человеку.
function generatePassword() {
  const chars = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  let out = ''
  for (let i = 0; i < 10; i++) out += chars[Math.floor(Math.random() * chars.length)]
  return out
}

async function load() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const [usersData, directionsData] = await Promise.all([fetchUsers(), fetchDirections()])
    users.value = usersData
    directions.value = directionsData
  } catch {
    errorMessage.value = 'Не удалось загрузить пользователей'
  } finally {
    isLoading.value = false
  }
}

onMounted(load)

async function submitCreate() {
  if (creating.value) return
  createError.value = ''
  creating.value = true
  try {
    const user = await createUser({
      username: draft.value.username.trim(),
      full_name: draft.value.full_name.trim(),
      password: draft.value.password,
      role: draft.value.role,
    })
    users.value.push(user)
    draft.value = { username: '', full_name: '', password: '', role: 'employee' }
  } catch (err) {
    createError.value = err.response?.data?.detail ?? 'Не удалось создать пользователя'
  } finally {
    creating.value = false
  }
}

function openEdit(user) {
  editError.value = ''
  editing.value = {
    id: user.id,
    username: user.username,
    full_name: user.full_name,
    role: user.role,
    leadership_position: user.leadership_position ?? '',
    is_active: user.is_active,
    is_editorial: user.is_editorial,
    password: '',
    // id направлений, где он руководитель (для чекбоксов).
    directionIds: headedDirections(user).map((d) => d.id),
  }
}

function closeEdit() {
  editing.value = null
}

async function submitEdit() {
  if (saving.value || !editing.value) return
  saving.value = true
  editError.value = ''
  try {
    const e = editing.value
    const payload = {
      full_name: e.full_name.trim(),
      role: e.role,
      is_active: e.is_active,
      is_editorial: e.is_editorial,
      leadership_position: e.leadership_position || null,
    }
    if (e.password) payload.password = e.password
    await updateUser(e.id, payload)

    // Руководство направлениями: применяем изменения чекбоксов.
    const desired = new Set(e.directionIds)
    for (const d of directions.value) {
      const wasHead = d.heads.some((h) => h.id === e.id)
      const willHead = desired.has(d.id)
      if (wasHead === willHead) continue
      const headIds = d.heads.map((h) => h.id).filter((id) => id !== e.id)
      if (willHead) headIds.push(e.id)
      await setDirectionHeads(d.id, headIds)
    }

    await load()
    editing.value = null
  } catch (err) {
    editError.value = err.response?.data?.detail ?? 'Не удалось сохранить'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="app-main__header">
        <div>
          <p class="breadcrumb">ИК · ТРЕКЕР / ПОЛЬЗОВАТЕЛИ</p>
          <h1>ПОЛЬЗОВАТЕЛИ</h1>
          <p class="subtitle">Создавайте аккаунты, выдавайте роли и должности, меняйте пароли.</p>
        </div>
      </div>

      <p v-if="errorMessage" class="alert alert--error">{{ errorMessage }}</p>

      <!-- Создание -->
      <section class="card create">
        <h2 class="card__title">Новый пользователь</h2>
        <form class="create__form" @submit.prevent="submitCreate">
          <input v-model="draft.full_name" placeholder="ФИО" required maxlength="128" />
          <input v-model="draft.username" placeholder="Логин" required minlength="3" maxlength="64" />
          <input
            v-model="draft.password"
            type="text"
            placeholder="Пароль (мин. 8)"
            required
            minlength="8"
            maxlength="128"
          />
          <button type="button" class="btn-ghost" @click="draft.password = generatePassword()">
            Сген.
          </button>
          <select v-model="draft.role">
            <option v-for="[key, label] in ROLES" :key="key" :value="key">{{ label }}</option>
          </select>
          <button type="submit" class="btn-primary" :disabled="creating">
            {{ creating ? 'Создаю…' : 'Создать' }}
          </button>
        </form>
        <p v-if="createError" class="error">{{ createError }}</p>
      </section>

      <!-- Список -->
      <AppLoader v-if="isLoading" />
      <div v-else class="card table-card">
        <table class="utable">
          <thead>
            <tr>
              <th>Пользователь</th>
              <th>Логин</th>
              <th>Роль</th>
              <th>Должность</th>
              <th>Направления</th>
              <th>Редакция</th>
              <th>Статус</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id" :class="{ 'row--inactive': !user.is_active }">
              <td>
                <span class="u">
                  <span class="u__avatar" :style="{ background: getAvatarColor(user.id) }">
                    {{ getInitials(user.full_name) }}
                  </span>
                  {{ user.full_name }}
                </span>
              </td>
              <td class="mono">{{ user.username }}</td>
              <td>{{ ROLE_LABELS[user.role] ?? user.role }}</td>
              <td>
                <span v-if="user.leadership_position" class="pos-chip">
                  {{ LEADERSHIP_POSITION_LABELS[user.leadership_position] }}
                </span>
                <span v-else class="muted muted--small">—</span>
              </td>
              <td>
                <span v-if="headedDirections(user).length" class="dir-codes">
                  <span v-for="d in headedDirections(user)" :key="d.id" class="dir-code">
                    {{ d.short_code }}
                  </span>
                </span>
                <span v-else class="muted muted--small">—</span>
              </td>
              <td>
                <span v-if="user.is_editorial" class="edit-chip">Редакция</span>
                <span v-else class="muted muted--small">—</span>
              </td>
              <td>
                <span :class="user.is_active ? 'status-on' : 'status-off'">
                  {{ user.is_active ? 'Активен' : 'Отключён' }}
                </span>
              </td>
              <td><button class="btn-ghost" @click="openEdit(user)">Изменить</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </main>

    <!-- Модалка редактирования -->
    <div v-if="editing" class="modal-backdrop" @click.self="closeEdit">
      <form class="modal" @submit.prevent="submitEdit">
        <h2>{{ editing.username }}</h2>

        <label>ФИО</label>
        <input v-model="editing.full_name" required maxlength="128" />

        <div class="modal__row">
          <div class="modal__field">
            <label>Роль</label>
            <select v-model="editing.role">
              <option v-for="[key, label] in ROLES" :key="key" :value="key">{{ label }}</option>
            </select>
          </div>
          <div class="modal__field">
            <label>Должность руководства</label>
            <select v-model="editing.leadership_position">
              <option value="">— нет —</option>
              <option v-for="[key, label] in POSITIONS" :key="key" :value="key">{{ label }}</option>
            </select>
          </div>
        </div>

        <label>Руководитель направлений</label>
        <div class="dir-picker">
          <label v-for="d in directions" :key="d.id" class="dir-opt">
            <input v-model="editing.directionIds" type="checkbox" :value="d.id" />
            {{ d.short_code }}
          </label>
        </div>

        <label class="modal__check">
          <input v-model="editing.is_editorial" type="checkbox" />
          Участник Редакции (SMM-календарь)
        </label>

        <label class="modal__check">
          <input v-model="editing.is_active" type="checkbox" />
          Активен
        </label>

        <label>Новый пароль (необязательно)</label>
        <div class="pw-row">
          <input v-model="editing.password" type="text" placeholder="Оставьте пустым — без изменений" minlength="8" maxlength="128" />
          <button type="button" class="btn-ghost" @click="editing.password = generatePassword()">
            Сген.
          </button>
        </div>

        <p v-if="editError" class="error">{{ editError }}</p>

        <div class="modal__actions">
          <button type="button" class="modal__cancel" @click="closeEdit">Отмена</button>
          <button type="submit" class="btn-primary" :disabled="saving">
            {{ saving ? 'Сохраняю…' : 'Сохранить' }}
          </button>
        </div>
      </form>
    </div>
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
}

.app-main__header {
  margin-bottom: 22px;
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

.subtitle {
  color: var(--text-muted);
  margin: 6px 0 0;
  font-size: 13px;
}

.muted {
  color: var(--text-muted);
}
.muted--small {
  font-size: 12px;
}

.alert {
  padding: 10px 14px;
  border-radius: 8px;
  margin: 0 0 16px;
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
  margin-bottom: 20px;
}

.card__title {
  margin: 0 0 14px;
  font-size: 16px;
}

.create__form {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.create__form input,
.create__form select {
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-raised);
  color: var(--text);
  font-size: 13px;
  flex: 1 1 160px;
}

.btn-primary {
  border: none;
  border-radius: 8px;
  background: var(--accent);
  color: #fff;
  padding: 9px 16px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  flex: 0 0 auto;
}
.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
}
.btn-primary:disabled {
  opacity: 0.6;
}

.btn-ghost {
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text);
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
}
.btn-ghost:hover {
  background: var(--surface-hover);
}

.table-card {
  padding: 6px 8px;
}

@media (max-width: 768px) {
  .table-card {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .utable {
    min-width: 720px;
  }
}

.utable {
  width: 100%;
  border-collapse: collapse;
}

.utable th {
  text-align: left;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-faint);
  padding: 10px 12px;
}

.utable td {
  padding: 10px 12px;
  border-top: 1px solid var(--border);
  font-size: 13.5px;
}

.row--inactive {
  opacity: 0.55;
}

.u {
  display: inline-flex;
  align-items: center;
  gap: 9px;
}

.u__avatar {
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

.mono {
  font-family: var(--font-mono);
  font-size: 12.5px;
  color: var(--text-muted);
}

.pos-chip {
  font-size: 12px;
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: 6px;
  padding: 2px 8px;
}

.dir-codes {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 4px;
}

.dir-code {
  font-size: 11px;
  background: var(--surface-raised);
  color: var(--text-muted);
  border-radius: 5px;
  padding: 1px 6px;
}

.edit-chip {
  font-size: 12px;
  background: color-mix(in srgb, var(--dir-smi, #a06bef) 22%, transparent);
  color: var(--dir-smi, #a06bef);
  border-radius: 6px;
  padding: 2px 8px;
}

.dir-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin-top: 6px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
}

.dir-opt {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text);
  margin: 0;
}

.dir-opt input {
  width: 15px;
  height: 15px;
  margin: 0;
}

.status-on {
  color: var(--status-done);
  font-size: 12.5px;
}
.status-off {
  color: var(--text-faint);
  font-size: 12.5px;
}

.error {
  color: var(--danger);
  font-size: 13px;
  margin: 10px 0 0;
}

/* Модалка */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  z-index: 100;
}
.modal {
  width: 100%;
  max-width: 460px;
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.modal h2 {
  margin: 0 0 8px;
  font-size: 18px;
}
.modal label {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 10px;
}
.modal input,
.modal select {
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-top: 4px;
  background: var(--surface);
  color: var(--text);
  font-family: inherit;
}
.modal__row {
  display: flex;
  gap: 12px;
}
.modal__field {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.modal__check {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text);
  margin-top: 14px;
}
.modal__check input {
  width: 16px;
  height: 16px;
  margin-top: 0;
}

.pw-row {
  display: flex;
  gap: 8px;
  align-items: stretch;
}
.pw-row input {
  flex: 1;
}
.pw-row .btn-ghost {
  margin-top: 4px;
}
.modal__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}
.modal__cancel {
  padding: 9px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: transparent;
  color: var(--text);
}
</style>
