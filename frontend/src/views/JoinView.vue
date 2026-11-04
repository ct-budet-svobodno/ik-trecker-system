<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import logoIk from '../assets/logo_ik.svg'
import BaseIcon from '../components/BaseIcon.vue'
import { fetchRegistrationOptions, registerWithTelegram } from '../api/telegram'
import { useAuthStore } from '../stores/auth'
import { shrinkImage } from '../utils/image'
import { isTelegram, telegramApp } from '../utils/telegram'

// Вход в мини-апп без логина и пароля: Telegram не привязан — анкета, анкета
// отправлена — ждём админа. ?link=<код> — привязать уже заведённый аккаунт
// (ссылка «Подключить Telegram» из веб-версии).
const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const inTelegram = isTelegram()
// form | pending | rejected | linking
const stage = ref(authStore.telegramStatus === 'pending' || authStore.telegramStatus === 'rejected'
  ? authStore.telegramStatus
  : 'form')
const error = ref('')
const isBusy = ref(false)

const options = ref({ directions: [], clothes_sizes: [] })

const fullName = ref('')
const birthday = ref('')
const directionId = ref('')
const studyGroup = ref('')
const phone = ref('')
const email = ref('')
const clothesSize = ref('')
const otherUnits = ref('')
// Два фото: ужатый файл и превью.
const photos = ref([null, null])

function goInside() {
  router.replace(route.query.redirect || { name: 'home' })
}

onMounted(async () => {
  if (!inTelegram) return
  if (route.query.link) {
    stage.value = 'linking'
    try {
      await authStore.claimTelegram(String(route.query.link))
      telegramApp()?.HapticFeedback?.notificationOccurred('success')
      goInside()
      return
    } catch (err) {
      error.value = err.response?.data?.detail ?? 'Не удалось привязать Telegram'
      stage.value = 'form'
    }
  }
  try {
    options.value = await fetchRegistrationOptions()
  } catch {
    /* без списка направлений поле просто останется пустым */
  }
})

onBeforeUnmount(() => photos.value.forEach((p) => p && URL.revokeObjectURL(p.preview)))

async function pickPhoto(slot, event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  error.value = ''
  let blob
  try {
    blob = await shrinkImage(file)
  } catch {
    // Телефон не смог перерисовать фото — обычный JPEG/PNG/WebP шлём как есть
    // (сервер примет до 8 МБ). HEIC и прочее так не пройдёт.
    if (/^image\/(jpeg|png|webp)$/.test(file.type) && file.size <= 8 * 1024 * 1024) {
      blob = file
    } else {
      error.value =
        'Это фото не открылось (часто так бывает с форматом HEIC). Выберите другое фото или сделайте скриншот этого.'
      return
    }
  }
  const old = photos.value[slot]
  if (old) URL.revokeObjectURL(old.preview)
  const next = [...photos.value]
  next[slot] = { blob, preview: URL.createObjectURL(blob) }
  photos.value = next
  invalid.value = invalid.value.filter((key) => key !== `photo${slot}`)
}

// Проверяем сами, а не встроенными подсказками браузера: внутри Telegram они
// часто не видны — человек жмёт «Отправить», и ничего не происходит.
const invalid = ref([])
const CHECKS = [
  ['j-name', 'ФИО', () => fullName.value.trim().split(/\s+/).length >= 2],
  ['j-birthday', 'день рождения', () => !!birthday.value],
  ['j-size', 'размер одежды', () => !!clothesSize.value],
  ['j-direction', 'направление', () => !!directionId.value],
  ['j-group', 'учебную группу', () => !!studyGroup.value.trim()],
  ['j-phone', 'телефон', () => phone.value.replace(/\D/g, '').length >= 10],
  ['j-email', 'почту', () => /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(email.value.trim())],
  ['photo0', 'первое фото', () => !!photos.value[0]],
  ['photo1', 'второе фото', () => !!photos.value[1]],
]

function isInvalid(id) {
  return invalid.value.includes(id)
}

async function validate() {
  const failed = CHECKS.filter(([, , ok]) => !ok())
  invalid.value = failed.map(([id]) => id)
  if (!failed.length) return true
  error.value = `Заполните ${failed.map(([, label]) => label).join(', ')}`
  telegramApp()?.HapticFeedback?.notificationOccurred('error')
  await nextTick()
  document.getElementById(failed[0][0])?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  return false
}

function touched(id) {
  invalid.value = invalid.value.filter((key) => key !== id)
}

async function submit() {
  error.value = ''
  if (!(await validate())) return
  isBusy.value = true
  const form = new FormData()
  form.append('init_data', telegramApp()?.initData ?? '')
  form.append('full_name', fullName.value)
  form.append('birthday', birthday.value)
  if (directionId.value) form.append('direction_id', directionId.value)
  form.append('study_group', studyGroup.value)
  form.append('phone', phone.value)
  form.append('email', email.value)
  form.append('clothes_size', clothesSize.value)
  form.append('other_units', otherUnits.value)
  photos.value.forEach((p, i) => form.append(`photo${i + 1}`, p.blob, `photo${i + 1}.jpg`))
  try {
    await registerWithTelegram(form)
    stage.value = 'pending'
    telegramApp()?.HapticFeedback?.notificationOccurred('success')
  } catch (err) {
    const detail = err.response?.data?.detail
    error.value = typeof detail === 'string' ? detail : 'Не удалось отправить анкету, попробуйте ещё раз'
    telegramApp()?.HapticFeedback?.notificationOccurred('error')
  } finally {
    isBusy.value = false
  }
}

// Админ мог уже одобрить — пробуем войти.
async function checkAgain() {
  isBusy.value = true
  error.value = ''
  try {
    if (await authStore.loginWithTelegram()) {
      goInside()
      return
    }
    if (authStore.telegramStatus === 'rejected') stage.value = 'rejected'
    else if (authStore.telegramStatus === 'pending') error.value = 'Пока не одобрили — загляните чуть позже'
  } finally {
    isBusy.value = false
  }
}
</script>

<template>
  <div class="join-page">
    <div class="join-card">
      <span class="join-logo" :style="{ '--logo': `url('${logoIk}')` }" />

      <!-- Открыли /join не из Telegram -->
      <template v-if="!inTelegram">
        <h1>Анкета — в Telegram</h1>
        <p class="join-text">
          Заявка в трекер подаётся из Telegram: откройте бота и нажмите «Трекер».
          Если аккаунт уже есть — войдите по логину.
        </p>
        <RouterLink class="join-btn join-btn--ghost" :to="{ name: 'login' }">Войти по логину</RouterLink>
      </template>

      <template v-else-if="stage === 'linking'">
        <h1>Подключаем Telegram…</h1>
        <p class="join-text">Секунду — привязываем этот Telegram к вашему аккаунту.</p>
      </template>

      <template v-else-if="stage === 'pending'">
        <span class="join-badge"><BaseIcon name="check" :size="16" /> Анкета отправлена</span>
        <h1>Ждём одобрения</h1>
        <p class="join-text">
          Админ посмотрит анкету и откроет доступ — бот напишет, когда это случится.
          Потом трекер будет открываться сразу.
        </p>
        <button class="join-btn" :disabled="isBusy" @click="checkAgain">Проверить ещё раз</button>
        <p v-if="error" class="join-hint">{{ error }}</p>
      </template>

      <template v-else-if="stage === 'rejected'">
        <h1>Заявку не одобрили</h1>
        <p class="join-text">
          Если это ошибка — напишите руководству. Можно поправить анкету и отправить её ещё раз.
        </p>
        <button class="join-btn" @click="stage = 'form'">Заполнить заново</button>
      </template>

      <form v-else class="join-form" novalidate @submit.prevent="submit">
        <h1>Анкета актива</h1>
        <p class="join-text">
          Трекер открывается после анкеты и одобрения админа. Логин и пароль не нужны — вход по
          вашему Telegram.
        </p>

        <label for="j-name">ФИО</label>
        <input id="j-name" v-model="fullName" :class="{ 'join-invalid': isInvalid('j-name') }" @input="touched('j-name')" required maxlength="120" autocomplete="name" />

        <div class="join-row">
          <div class="join-field">
            <label for="j-birthday">День рождения</label>
            <input id="j-birthday" v-model="birthday" :class="{ 'join-invalid': isInvalid('j-birthday') }" @input="touched('j-birthday')" type="date" required />
          </div>
          <div class="join-field">
            <label for="j-size">Размер одежды</label>
            <select id="j-size" v-model="clothesSize" :class="{ 'join-invalid': isInvalid('j-size') }" @change="touched('j-size')" required>
              <option value="" disabled>Выберите</option>
              <option v-for="size in options.clothes_sizes" :key="size" :value="size">{{ size }}</option>
            </select>
          </div>
        </div>

        <label for="j-direction">Направление</label>
        <select id="j-direction" v-model="directionId" :class="{ 'join-invalid': isInvalid('j-direction') }" @change="touched('j-direction')" required>
          <option value="" disabled>Выберите направление</option>
          <option v-for="d in options.directions" :key="d.id" :value="d.id">{{ d.name }}</option>
        </select>

        <label for="j-group">Учебная группа</label>
        <input id="j-group" v-model="studyGroup" :class="{ 'join-invalid': isInvalid('j-group') }" @input="touched('j-group')" required maxlength="64" />

        <label for="j-phone">Телефон</label>
        <input id="j-phone" v-model="phone" :class="{ 'join-invalid': isInvalid('j-phone') }" @input="touched('j-phone')" type="tel" required maxlength="32" autocomplete="tel" />

        <label for="j-email">Почта <span class="join-optional">— только Gmail (@gmail.com)</span></label>
        <input id="j-email" v-model="email" :class="{ 'join-invalid': isInvalid('j-email') }" @input="touched('j-email')" type="email" required maxlength="120" autocomplete="email" />

        <label for="j-other">Другие подразделения <span class="join-optional">— если есть</span></label>
        <input id="j-other" v-model="otherUnits" maxlength="200" />

        <span class="join-label">Два своих фото</span>
        <div class="photos">
          <label
            v-for="(photo, slot) in photos"
            :key="slot"
            :id="`photo${slot}`"
            class="photo"
            :class="{ 'photo--filled': photo, 'join-invalid': isInvalid(`photo${slot}`) }"
          >
            <img v-if="photo" :src="photo.preview" alt="" class="photo__img" />
            <span v-else class="photo__empty">
              <BaseIcon name="plus" :size="22" />
              {{ slot === 0 ? 'Портрет' : 'Ещё одно' }}
            </span>
            <input type="file" accept="image/*" class="photo__input" @change="pickPhoto(slot, $event)" />
          </label>
        </div>

        <p v-if="error" class="join-error">{{ error }}</p>
        <button type="submit" class="join-btn" :disabled="isBusy">
          {{ isBusy ? 'Отправляем…' : 'Отправить анкету' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.join-page {
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-5) var(--space-4);
}

.join-card {
  position: relative;
  width: 100%;
  max-width: 440px;
  background: color-mix(in srgb, var(--surface) 82%, transparent);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-6) var(--space-5) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow: hidden;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
}

/* Фирменный градиентный волосок сверху карточки — как на входе. */
.join-card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto 0;
  height: 3px;
  background: linear-gradient(90deg, var(--dir-prod-a), #e8863c, var(--dir-prod-b));
}

.join-logo {
  width: 48px;
  height: 48px;
  margin: 0 auto var(--space-3);
  background: linear-gradient(120deg, var(--dir-prod-a), #e8863c, var(--dir-prod-b));
  -webkit-mask: var(--logo) center / contain no-repeat;
  mask: var(--logo) center / contain no-repeat;
}

h1 {
  margin: 0 0 4px;
  font: 600 20px/26px var(--font-display);
  text-align: center;
}

.join-text {
  margin: 0 0 var(--space-2);
  font-size: 14px;
  line-height: 21px;
  color: var(--text-muted);
  text-align: center;
}

.join-badge {
  align-self: center;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: var(--space-2);
  padding: 4px 10px;
  border-radius: var(--radius-full);
  background: color-mix(in srgb, var(--success) 16%, transparent);
  color: var(--success);
  font-size: 13px;
  font-weight: 600;
}

.join-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.join-form label,
.join-label {
  margin-top: var(--space-2);
  font-size: 13px;
  color: var(--text-muted);
}

.join-optional {
  color: var(--text-faint);
}

.join-form input,
.join-form select {
  height: var(--control-h-touch);
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--text);
  font-size: 15px;
}

.join-form input:focus,
.join-form select:focus {
  outline: none;
  border-color: var(--dir-prod-b);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--dir-prod-b) 22%, transparent);
}

.join-row {
  display: flex;
  gap: var(--space-3);
}

.join-field {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.photos {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}

.photo {
  position: relative;
  aspect-ratio: 3 / 4;
  margin: 0 !important;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-md);
  overflow: hidden;
  cursor: pointer;
  background: var(--surface);
}

.photo--filled {
  border-style: solid;
}

.photo__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.photo__empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-muted);
}

.photo__input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.join-form .join-invalid,
.photo.join-invalid {
  border-color: var(--danger);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--danger) 18%, transparent);
}

.join-error {
  margin: var(--space-2) 0 0;
  font-size: 13px;
  color: var(--danger);
}

.join-hint {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
  text-align: center;
}

.join-btn {
  height: var(--control-h-touch);
  margin-top: var(--space-3);
  border: none;
  border-radius: var(--radius-md);
  background: var(--success);
  color: var(--on-success);
  font-size: 15px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
}

.join-btn:disabled {
  opacity: 0.6;
}

.join-btn--ghost {
  background: transparent;
  border: 1px solid var(--border-strong);
  color: var(--text);
}
</style>
