<script setup>
import { computed, onMounted, ref } from 'vue'

import AppLoader from '../components/AppLoader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import RegistrationsPanel from '../components/RegistrationsPanel.vue'
import { fetchDirections, setDirectionHeads } from '../api/directions'
import { createUser, fetchUsers, importFromBot, updateUser } from '../api/users'
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

// Направления, где человек состоит (их может быть несколько).
function memberDirections(user) {
  return directions.value.filter((d) => user.direction_ids.includes(d.id))
}

// --- Фильтры списка ---
const aktivFilter = ref('all') // all | yes | no
const directionFilter = ref('') // '' — все, 'none' — без направления, иначе id
const aktivCount = computed(() => users.value.filter((u) => u.is_activist).length)

const filteredUsers = computed(() =>
  users.value.filter((u) => {
    if (aktivFilter.value === 'yes' && !u.is_activist) return false
    if (aktivFilter.value === 'no' && u.is_activist) return false
    if (directionFilter.value === 'none') return !u.direction_ids.length
    if (directionFilter.value) return u.direction_ids.includes(Number(directionFilter.value))
    return true
  }),
)

// Галочка «в активе» прямо в таблице: клик — сразу сохранили.
const togglingIds = ref(new Set())

async function toggleAktiv(user) {
  if (togglingIds.value.has(user.id)) return
  togglingIds.value.add(user.id)
  const next = !user.is_activist
  user.is_activist = next
  try {
    await updateUser(user.id, { is_activist: next })
  } catch (err) {
    user.is_activist = !next
    errorMessage.value = err.response?.data?.detail ?? 'Не удалось сохранить отметку актива'
  } finally {
    togglingIds.value.delete(user.id)
  }
}

// --- Анкеты из бота ---
// Фоновая синхронизация и так подтягивает их раз в 10 минут; кнопка — «сейчас».
const importing = ref(false)
const importResult = ref('')

async function runImport() {
  importing.value = true
  importResult.value = ''
  try {
    const report = await importFromBot()
    importResult.value = report.created
      ? `Заведено из бота: ${report.created} — ${report.names.join(', ')}`
      : 'Все из анкет бота уже в трекере'
    if (report.created || report.linked) await load()
  } catch (err) {
    importResult.value = err.response?.data?.detail ?? 'Не удалось подтянуть анкеты'
  } finally {
    importing.value = false
  }
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
    is_zavod: user.is_zavod,
    is_activist: user.is_activist,
    memberIds: [...user.direction_ids],
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
      is_zavod: e.is_zavod,
      is_activist: e.is_activist,
      direction_ids: e.memberIds,
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
          <h1>Пользователи</h1>
          <p class="subtitle">Создавайте аккаунты, выдавайте роли и должности, меняйте пароли.</p>
        </div>
        <button class="import-btn" :disabled="importing" @click="runImport">
          {{ importing ? 'Подтягиваем…' : 'Подтянуть из бота' }}
        </button>
      </div>
      <p v-if="importResult" class="alert import-result">{{ importResult }}</p>

      <p v-if="errorMessage" class="alert alert--error">{{ errorMessage }}</p>

      <!-- Заявки из мини-аппа: принятые сразу появляются в списке ниже -->
      <RegistrationsPanel @approved="load" />

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
      <div v-if="!isLoading" class="filters">
        <div class="seg">
          <button :class="{ 'seg__btn--on': aktivFilter === 'all' }" class="seg__btn" @click="aktivFilter = 'all'">
            Все · {{ users.length }}
          </button>
          <button :class="{ 'seg__btn--on': aktivFilter === 'yes' }" class="seg__btn" @click="aktivFilter = 'yes'">
            В активе · {{ aktivCount }}
          </button>
          <button :class="{ 'seg__btn--on': aktivFilter === 'no' }" class="seg__btn" @click="aktivFilter = 'no'">
            Не в активе · {{ users.length - aktivCount }}
          </button>
        </div>
        <select v-model="directionFilter" class="filters__dir">
          <option value="">Все направления</option>
          <option v-for="d in directions" :key="d.id" :value="String(d.id)">{{ d.name }}</option>
          <option value="none">Без направления</option>
        </select>
        <span class="muted muted--small">Показано: {{ filteredUsers.length }}</span>
      </div>
      <AppLoader v-if="isLoading" />
      <div v-else class="card table-card">
        <table class="utable">
          <thead>
            <tr>
              <th>Пользователь</th>
              <th>Актив</th>
              <th>Направления</th>
              <th>Логин</th>
              <th>Роль</th>
              <th>Должность</th>
              <th>Руководит</th>
              <th>Редакция</th>
              <th>ZAVOD</th>
              <th>Статус</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in filteredUsers" :key="user.id" :class="{ 'row--inactive': !user.is_active }">
              <td>
                <span class="u">
                  <span class="u__avatar" :style="{ background: getAvatarColor(user.id) }">
                    {{ getInitials(user.full_name) }}
                  </span>
                  {{ user.full_name }}
                </span>
              </td>
              <td>
                <button
                  type="button"
                  class="aktiv-toggle"
                  :class="{ 'aktiv-toggle--on': user.is_activist }"
                  :disabled="togglingIds.has(user.id)"
                  :aria-pressed="user.is_activist"
                  @click="toggleAktiv(user)"
                >
                  {{ user.is_activist ? 'В активе' : 'Нет' }}
                </button>
              </td>
              <td>
                <span v-if="user.direction_ids.length" class="dir-codes">
                  <span v-for="d in memberDirections(user)" :key="d.id" class="dir-code">
                    {{ d.short_code }}
                  </span>
                </span>
                <span v-else class="muted muted--small">—</span>
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
                <span v-if="user.is_zavod" class="zavod-chip">ZAVOD</span>
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
      <form v-swipe-close="closeEdit" class="modal" @submit.prevent="submitEdit">
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

        <label class="modal__check">
          <input v-model="editing.is_activist" type="checkbox" />
          В активе
        </label>
        <label>Состоит в направлениях</label>
        <div class="dir-picker">
          <label v-for="d in directions" :key="d.id" class="dir-opt">
            <input v-model="editing.memberIds" type="checkbox" :value="d.id" />
            {{ d.short_code }}
          </label>
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
          <input v-model="editing.is_zavod" type="checkbox" />
          Доступ к ZAVOD (доска тем)
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
.app-main__header {
  margin-bottom: 22px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.import-btn {
  height: var(--control-h);
  padding: 0 14px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text);
  font-size: 14px;
}

.import-btn:hover:not(:disabled) {
  background: var(--surface-hover);
}

.import-result {
  background: color-mix(in srgb, var(--success) 12%, transparent);
  color: var(--success);
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
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

@media (max-width: 768px) {
  .utable {
    min-width: 960px;
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
  font-size: 13px;
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
  font-size: 13px;
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
  border-radius: 6px;
  padding: 1px 6px;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.seg {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.seg__btn {
  border: none;
  background: transparent;
  color: var(--text-muted);
  padding: 7px 12px;
  font-size: 13px;
  cursor: pointer;
}

.seg__btn + .seg__btn {
  border-left: 1px solid var(--border);
}

.seg__btn--on {
  background: var(--accent-soft);
  color: var(--accent);
}

.filters__dir {
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-raised);
  color: var(--text);
  font-size: 13px;
}

.aktiv-toggle {
  font-size: 12px;
  border: 1px dashed var(--border-strong);
  background: transparent;
  color: var(--text-faint);
  border-radius: 6px;
  padding: 3px 9px;
  white-space: nowrap;
  cursor: pointer;
}
.aktiv-toggle:hover:not(:disabled) {
  color: var(--text);
  border-color: var(--text-muted);
}
.aktiv-toggle--on {
  border: 1px solid transparent;
  background: color-mix(in srgb, var(--success) 20%, transparent);
  color: var(--success);
}
.aktiv-toggle--on:hover:not(:disabled) {
  color: var(--success);
  border-color: var(--success);
}
.aktiv-toggle:disabled {
  opacity: 0.6;
}

.edit-chip {
  font-size: 12px;
  background: color-mix(in srgb, var(--dir-smi, #a06bef) 22%, transparent);
  color: var(--dir-smi, #a06bef);
  border-radius: 6px;
  padding: 2px 8px;
}

.zavod-chip {
  font-size: 12px;
  background: color-mix(in srgb, var(--success) 20%, transparent);
  color: var(--success);
  border-radius: 6px;
  padding: 2px 8px;
  letter-spacing: 0.04em;
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
  font-size: 13px;
}
.status-off {
  color: var(--text-faint);
  font-size: 13px;
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
