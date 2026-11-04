<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import logoIk from '../assets/logo_ik.svg'
import { useAuthStore } from '../stores/auth'

const username = ref('')
const password = ref('')
const showPassword = ref(false)
const error = ref('')
const isSubmitting = ref(false)

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

async function handleSubmit() {
  error.value = ''
  isSubmitting.value = true
  try {
    await authStore.login(username.value, password.value)
    router.push(route.query.redirect || { name: 'home' })
  } catch (err) {
    error.value =
      err.response?.status === 401 ? 'Неверный логин или пароль' : 'Не удалось войти, попробуйте позже'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <form class="login-card" @submit.prevent="handleSubmit">
      <span class="login-logo" :style="{ '--logo': `url('${logoIk}')` }" />
      <h1>Информационный комитет</h1>
      <p class="subtitle">Вход в таск-трекер</p>

      <label for="username">Логин</label>
      <input id="username" v-model="username" type="text" autocomplete="username" required />

      <label for="password">Пароль</label>
      <div class="pw-field">
        <input
          id="password"
          v-model="password"
          :type="showPassword ? 'text' : 'password'"
          autocomplete="current-password"
          required
        />
        <button
          type="button"
          class="pw-toggle"
          :title="showPassword ? 'Скрыть пароль' : 'Показать пароль'"
          :aria-label="showPassword ? 'Скрыть пароль' : 'Показать пароль'"
          :aria-pressed="showPassword"
          @click="showPassword = !showPassword"
        >
          <svg v-if="!showPassword" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"
            />
            <circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="2" />
          </svg>
          <svg v-else viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M3 3l18 18M10.6 10.6a3 3 0 0 0 4.2 4.2M9.9 4.7A9.6 9.6 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.4 4.3M6.6 6.6A17 17 0 0 0 2 12s3.5 7 10 7a9.6 9.6 0 0 0 3.1-.5"
            />
          </svg>
        </button>
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <button type="submit" :disabled="isSubmitting">
        {{ isSubmitting ? 'Входим…' : 'Войти' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.login-card {
  position: relative;
  width: 100%;
  max-width: 380px;
  background: color-mix(in srgb, var(--surface) 82%, transparent);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 36px 32px 32px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow: hidden;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
}

/* Фирменный градиентный волосок сверху карточки. */
.login-card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto 0;
  height: 3px;
  background: linear-gradient(90deg, var(--dir-prod-a), #e8863c, var(--dir-prod-b));
}

@media (prefers-reduced-motion: no-preference) {
  .login-card {
    animation: card-in 0.45s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .login-logo {
    animation: logo-flow 3.2s ease-in-out infinite;
  }
}

@keyframes card-in {
  from {
    opacity: 0;
    transform: translateY(18px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

/* Логотип, залитый «дышащим» фирменным градиентом (белый знак = маска). */
.login-logo {
  width: 64px;
  height: 64px;
  margin: 0 auto 14px;
  background: linear-gradient(
    120deg,
    var(--dir-prod-a),
    #e8863c,
    var(--dir-prod-b),
    #e8863c,
    var(--dir-prod-a)
  );
  background-size: 300% 300%;
  -webkit-mask: var(--logo) center / contain no-repeat;
  mask: var(--logo) center / contain no-repeat;
}

@keyframes logo-flow {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

h1 {
  font: 600 20px/26px var(--font-display);
  letter-spacing: -0.01em;
  margin: 0 0 4px;
  text-align: center;
}

.subtitle {
  color: var(--text-muted);
  margin: 0 0 20px;
  text-align: center;
}


label {
  font-size: 14px;
  color: var(--text-muted);
  margin-top: 12px;
}

input {
  padding: 11px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-top: 4px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

input:focus {
  outline: none;
  border-color: var(--dir-prod-b);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--dir-prod-b) 22%, transparent);
}

/* Поле пароля с кнопкой-глазом. */
.pw-field {
  position: relative;
  display: flex;
}

.pw-field input {
  flex: 1;
  /* Место под кнопку, чтобы текст не заезжал под неё. */
  padding-right: 42px;
}

.pw-field .pw-toggle {
  position: absolute;
  top: 50%;
  right: 6px;
  transform: translateY(-50%);
  margin: 0;
  padding: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  box-shadow: none;
  transition: color 0.15s ease, background 0.15s ease;
}

.pw-field .pw-toggle:hover {
  color: var(--text);
  background: var(--surface-hover);
  box-shadow: none;
}

.error {
  color: var(--danger);
  font-size: 14px;
  margin-top: 12px;
}

button {
  margin-top: 20px;
  padding: 11px 16px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(90deg, var(--dir-prod-a), var(--dir-prod-b));
  background-size: 160% 100%;
  background-position: 0% 50%;
  color: #fff;
  font-weight: 600;
  letter-spacing: 0.01em;
  transition: background-position 0.35s ease, box-shadow 0.2s ease, transform 0.1s ease;
}

button:hover:not(:disabled) {
  background-position: 100% 50%;
  box-shadow: 0 6px 22px color-mix(in srgb, var(--dir-prod-a) 40%, transparent);
}

button:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>
