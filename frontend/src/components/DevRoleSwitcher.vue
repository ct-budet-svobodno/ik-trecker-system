<script setup>
import { computed, ref } from 'vue'

import { useAuthStore } from '../stores/auth'

// Только для локальной разработки (подключается в App.vue под import.meta.env.DEV,
// в прод-сборку не попадает). Вход под тестовыми аккаунтами одним нажатием.
// Аккаунты создаёт backend/scripts/seed_test_roles.py — держать списки в согласии.
const ACCOUNTS = [
  { username: 'admin', password: 'admin123', label: 'Админ' },
  { username: 't.chairman', password: 'test12345', label: 'Председатель' },
  { username: 't.secretary', password: 'test12345', label: 'Секретарь' },
  { username: 't.head', password: 'test12345', label: 'Руководитель НВК' },
  { username: 't.activist', password: 'test12345', label: 'Активист' },
  { username: 't.editorial', password: 'test12345', label: 'Активист Редакции' },
]

const authStore = useAuthStore()
const isOpen = ref(false)
const busyName = ref(null)
const error = ref('')

const current = computed(
  () => ACCOUNTS.find((acc) => acc.username === authStore.user?.username)?.label
    ?? authStore.user?.full_name
    ?? 'Не вошли',
)

async function switchTo(account) {
  busyName.value = account.username
  error.value = ''
  try {
    authStore.logout()
    await authStore.login(account.username, account.password)
    // Перезагрузка сбрасывает сторы с данными прошлого пользователя.
    window.location.assign('/')
  } catch {
    error.value = 'Нет аккаунта — запустите scripts.seed_test_roles'
    busyName.value = null
  }
}
</script>

<template>
  <div class="dev-switch">
    <button class="dev-switch__toggle" title="Сменить роль (только dev)" @click="isOpen = !isOpen">
      <span class="dev-switch__tag">dev</span>
      {{ current }}
    </button>
    <div v-if="isOpen" class="dev-switch__menu">
      <button
        v-for="acc in ACCOUNTS"
        :key="acc.username"
        class="dev-switch__item"
        :class="{ 'dev-switch__item--active': acc.username === authStore.user?.username }"
        :disabled="busyName !== null"
        @click="switchTo(acc)"
      >
        {{ acc.label }}
        <span class="dev-switch__login">{{ busyName === acc.username ? '…' : acc.username }}</span>
      </button>
      <p v-if="error" class="dev-switch__error">{{ error }}</p>
    </div>
  </div>
</template>

<style scoped>
/* Справа внизу: сверху на телефоне живут заголовок и «Выдать ТЗ».
   Меню раскрывается вверх (column-reverse). */
.dev-switch {
  position: fixed;
  bottom: var(--space-4);
  right: var(--space-4);
  z-index: 200;
  display: flex;
  flex-direction: column-reverse;
  align-items: flex-end;
  gap: var(--space-1);
}

@media (max-width: 768px) {
  /* Над нижним таб-баром. */
  .dev-switch {
    bottom: calc(96px + env(safe-area-inset-bottom));
    right: var(--space-2);
  }
}

.dev-switch__toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 10px 0 4px;
  border: 1px dashed var(--prio-medium);
  border-radius: var(--radius-full);
  background: var(--surface-raised);
  color: var(--text);
  font-size: 12px;
  opacity: 0.85;
}

.dev-switch__toggle:hover {
  opacity: 1;
}

.dev-switch__tag {
  font: 600 11px/1 var(--font-mono);
  color: var(--bg);
  background: var(--prio-medium);
  border-radius: var(--radius-full);
  padding: 4px 6px;
}

.dev-switch__menu {
  min-width: 240px;
  padding: var(--space-1);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-lg);
  background: var(--surface-raised);
  box-shadow: var(--shadow-lift);
  display: flex;
  flex-direction: column;
}

.dev-switch__item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  min-height: 40px;
  padding: 0 var(--space-3);
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text);
  font-size: 14px;
  text-align: left;
}

.dev-switch__item:hover:not(:disabled) {
  background: var(--surface-hover);
}

.dev-switch__item--active {
  background: var(--accent-soft);
}

.dev-switch__login {
  font: 12px var(--font-mono);
  color: var(--text-faint);
}

.dev-switch__error {
  margin: var(--space-1) var(--space-3);
  font-size: 12px;
  color: var(--danger);
}
</style>
