<script setup>
// Брендовый лоадер: белый знак ИК используется как маска,
// сквозь которую «течёт» фирменный градиент.
import logoIk from '../assets/logo_ik.svg'

defineProps({
  label: { type: String, default: 'Загрузка…' },
})
</script>

<template>
  <div class="loader" role="status">
    <span class="loader__mark" :style="{ '--logo': `url('${logoIk}')` }" />
    <span class="loader__label">{{ label }}</span>
  </div>
</template>

<style scoped>
.loader {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 0;
}

.loader__mark {
  width: 54px;
  height: 54px;
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
  animation: loader-flow 1.8s ease-in-out infinite;
}

.loader__label {
  font-size: 12px;
  letter-spacing: 0.08em;
  color: var(--text-faint);
}

@keyframes loader-flow {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

@media (prefers-reduced-motion: reduce) {
  .loader__mark {
    animation: none;
  }
}
</style>
