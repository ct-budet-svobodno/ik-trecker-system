<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

import BaseIcon from './BaseIcon.vue'
import {
  approveRegistration,
  fetchProfilePhoto,
  fetchRegistrations,
  rejectRegistration,
} from '../api/users'
import { getAvatarColor, getInitials } from '../utils/avatar'

// Заявки из мини-аппа: анкета с фото, админ принимает или отклоняет.
// Принятый появляется в списке пользователей как активист.
const emit = defineEmits(['approved'])

const items = ref([])
const photos = ref({}) // `${id}-${slot}` → objectURL
const busyId = ref(null)
const error = ref('')

const birthdayFmt = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })

async function load() {
  try {
    items.value = await fetchRegistrations()
  } catch {
    items.value = []
    return
  }
  for (const item of items.value) {
    for (const slot of [1, 2]) {
      const key = `${item.id}-${slot}`
      if (photos.value[key]) continue
      fetchProfilePhoto(item.id, slot)
        .then((blob) => (photos.value = { ...photos.value, [key]: URL.createObjectURL(blob) }))
        .catch(() => {})
    }
  }
}

onMounted(load)
onBeforeUnmount(() => Object.values(photos.value).forEach((url) => URL.revokeObjectURL(url)))

async function decide(item, approve) {
  if (!approve && !window.confirm(`Отклонить заявку ${item.full_name}?`)) return
  busyId.value = item.id
  error.value = ''
  try {
    await (approve ? approveRegistration(item.id) : rejectRegistration(item.id))
    items.value = items.value.filter((i) => i.id !== item.id)
    if (approve) emit('approved')
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Не удалось сохранить решение'
  } finally {
    busyId.value = null
  }
}

function phone(value) {
  const d = value.replace(/\D/g, '')
  return d.length === 11 ? `+${d[0]} ${d.slice(1, 4)} ${d.slice(4, 7)}-${d.slice(7, 9)}-${d.slice(9)}` : value
}
</script>

<template>
  <section v-if="items.length" class="regs">
    <header class="regs__head">
      <h2 class="regs__title">Заявки из Telegram</h2>
      <span class="regs__count">{{ items.length }}</span>
    </header>
    <p v-if="error" class="regs__error">{{ error }}</p>

    <article v-for="item in items" :key="item.id" class="reg">
      <div class="reg__photos">
        <div v-for="slot in [1, 2]" :key="slot" class="reg__photo">
          <img v-if="photos[`${item.id}-${slot}`]" :src="photos[`${item.id}-${slot}`]" alt="" />
          <span v-else class="reg__avatar" :style="{ background: getAvatarColor(item.id) }">
            {{ getInitials(item.full_name) }}
          </span>
        </div>
      </div>

      <div class="reg__body">
        <p class="reg__name">{{ item.full_name }}</p>
        <p v-if="item.telegram_username" class="reg__tag">@{{ item.telegram_username }}</p>
        <dl v-if="item.profile" class="reg__meta">
          <div><dt>Направление</dt><dd>{{ item.profile.direction_name ?? '—' }}</dd></div>
          <div><dt>День рождения</dt><dd>{{ birthdayFmt.format(new Date(item.profile.birthday)) }}</dd></div>
          <div><dt>Группа</dt><dd>{{ item.profile.study_group }}</dd></div>
          <div><dt>Телефон</dt><dd>{{ phone(item.profile.phone) }}</dd></div>
          <div><dt>Почта</dt><dd>{{ item.profile.email }}</dd></div>
          <div><dt>Размер</dt><dd>{{ item.profile.clothes_size }}</dd></div>
          <div v-if="item.profile.other_units"><dt>Ещё состоит</dt><dd>{{ item.profile.other_units }}</dd></div>
        </dl>
        <div class="reg__actions">
          <button class="reg__approve" :disabled="busyId === item.id" @click="decide(item, true)">
            <BaseIcon name="check" :size="16" />
            Принять
          </button>
          <button class="reg__reject" :disabled="busyId === item.id" @click="decide(item, false)">
            Отклонить
          </button>
        </div>
      </div>
    </article>
  </section>
</template>

<style scoped>
.regs {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-bottom: var(--space-5);
}

.regs__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.regs__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.regs__count {
  min-width: 22px;
  height: 22px;
  padding: 0 7px;
  border-radius: var(--radius-full);
  background: var(--accent);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  line-height: 22px;
  text-align: center;
}

.regs__error {
  margin: 0;
  font-size: 13px;
  color: var(--danger);
}

.reg {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-4);
  background: var(--surface);
  border: 1px solid color-mix(in srgb, var(--accent) 40%, var(--border));
  border-radius: var(--radius-lg);
}

.reg__photos {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}

.reg__photo {
  width: 96px;
  aspect-ratio: 3 / 4;
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--surface-raised);
  display: flex;
  align-items: center;
  justify-content: center;
}

.reg__photo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.reg__avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
}

.reg__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.reg__name {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.reg__tag {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.reg__meta {
  margin: var(--space-2) 0 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 6px var(--space-4);
}

.reg__meta dt {
  font-size: 11px;
  color: var(--text-faint);
}

.reg__meta dd {
  margin: 0;
  font-size: 13px;
  overflow-wrap: anywhere;
}

.reg__actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.reg__approve,
.reg__reject {
  height: var(--control-h);
  padding: 0 14px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.reg__approve {
  border: none;
  background: var(--success);
  color: var(--on-success);
}

.reg__reject {
  border: 1px solid var(--border-strong);
  background: transparent;
  color: var(--text);
}

.reg__reject:hover:not(:disabled) {
  color: var(--danger);
}

@media (max-width: 768px) {
  .reg {
    flex-direction: column;
  }

  .reg__photo {
    width: calc(50% - var(--space-1));
  }

  .reg__photos {
    width: 100%;
  }

  .reg__approve,
  .reg__reject {
    flex: 1;
    justify-content: center;
    height: var(--control-h-touch);
  }
}
</style>
