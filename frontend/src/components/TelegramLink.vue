<script setup>
import { computed, onMounted, ref } from 'vue'

import BaseIcon from './BaseIcon.vue'
import { createTelegramLinkCode, fetchTelegramConfig, unlinkTelegram } from '../api/telegram'
import { useAuthStore } from '../stores/auth'

// Подключение Telegram в вебе. Логина в мини-аппе нет, поэтому привязываем
// одноразовой ссылкой: t.me/<бот>?startapp=link_<код> открывает мини-апп,
// и он привязывает свой Telegram к этому аккаунту (registration_service).
const authStore = useAuthStore()
const botUsername = ref(null)
const isBusy = ref(false)

onMounted(async () => {
  try {
    const config = await fetchTelegramConfig()
    botUsername.value = config.enabled ? config.bot_username : null
  } catch {
    botUsername.value = null
  }
})

const linked = computed(() => !!authStore.user?.telegram_linked)
const botUrl = computed(() => (botUsername.value ? `https://t.me/${botUsername.value}?start=web` : null))

const linkError = ref('')

async function handleConnect() {
  isBusy.value = true
  linkError.value = ''
  // Окно открываем сразу, по клику: после await браузер счёл бы его всплывающим.
  const tab = window.open('about:blank', '_blank')
  try {
    const { url } = await createTelegramLinkCode()
    const target = url ?? botUrl.value
    if (tab) tab.location.href = target
    else window.location.href = target
  } catch {
    tab?.close()
    linkError.value = 'Не удалось получить ссылку, попробуйте ещё раз'
  } finally {
    isBusy.value = false
  }
}

async function handleUnlink() {
  isBusy.value = true
  try {
    authStore.user = await unlinkTelegram()
  } finally {
    isBusy.value = false
  }
}
</script>

<template>
  <div v-if="botUrl || linked" class="tg-link">
    <template v-if="linked">
      <span class="tg-link__text">
        Telegram подключён<template v-if="authStore.user.telegram_username">
          · @{{ authStore.user.telegram_username }}</template>
      </span>
      <button class="tg-link__action" :disabled="isBusy" @click="handleUnlink">Отключить</button>
    </template>
    <template v-else>
      <button class="tg-link__connect" :disabled="isBusy" @click="handleConnect">
        <BaseIcon name="send" :size="16" />
        Подключить Telegram
      </button>
      <span class="tg-link__hint">
        {{ linkError || 'Ссылка действует 15 минут. Трекер в Telegram и уведомления от бота' }}
      </span>
    </template>
  </div>
</template>

<style scoped>
.tg-link {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 8px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
}

.tg-link__text {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.tg-link__action {
  border: none;
  background: transparent;
  padding: 0;
  color: var(--text-muted);
  font-size: 12px;
}

.tg-link__action:hover {
  color: var(--danger);
}

.tg-link__connect {
  padding: 0;
  border: none;
  background: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text);
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
}

.tg-link__connect:hover {
  color: var(--accent);
}

.tg-link__hint {
  flex-basis: 100%;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
