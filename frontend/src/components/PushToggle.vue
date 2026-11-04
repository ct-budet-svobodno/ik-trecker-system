<script setup>
import { onMounted, ref } from 'vue'

import { disablePush, enablePush, getPushState } from '../utils/pushClient'

// 'unsupported' | 'denied' | 'subscribed' | 'off' | 'busy'
const state = ref('off')
const error = ref('')

onMounted(async () => {
  state.value = await getPushState()
})

async function toggle() {
  if (state.value === 'busy') return
  error.value = ''
  const prev = state.value
  state.value = 'busy'
  try {
    if (prev === 'subscribed') {
      await disablePush()
      state.value = 'off'
    } else {
      await enablePush()
      state.value = 'subscribed'
    }
  } catch (err) {
    error.value = err?.message ?? 'Не получилось включить уведомления'
    state.value = await getPushState()
  }
}
</script>

<template>
  <div v-if="state !== 'unsupported'" class="push-toggle">
    <button
      class="push-toggle__btn"
      :class="{ 'push-toggle__btn--on': state === 'subscribed' }"
      :disabled="state === 'denied' || state === 'busy'"
      @click="toggle"
    >
      <span class="push-toggle__icon">🔔</span>
      <span v-if="state === 'subscribed'">Уведомления включены</span>
      <span v-else-if="state === 'denied'">Уведомления запрещены в браузере</span>
      <span v-else-if="state === 'busy'">Подключаю…</span>
      <span v-else>Включить уведомления</span>
    </button>
    <p v-if="error" class="push-toggle__error">{{ error }}</p>
  </div>
</template>

<style scoped>
.push-toggle__btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  text-align: left;
  transition: color 0.15s ease, border-color 0.15s ease;
}

.push-toggle__btn:hover:not(:disabled) {
  color: var(--text);
  border-color: var(--border-strong);
}

.push-toggle__btn:disabled {
  opacity: 0.6;
}

.push-toggle__btn--on {
  color: var(--status-done);
  border-color: color-mix(in srgb, var(--status-done) 40%, transparent);
}

.push-toggle__icon {
  font-size: 13px;
}

.push-toggle__error {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--danger);
}
</style>
