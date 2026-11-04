<script setup>
import { computed } from 'vue'

import { isRed, rankLabel, suitOf, suitSymbol } from '../utils/cards'

// Игральная карта. Без card — рубашка. size: hand (рука) | table (стол) | mini.
const props = defineProps({
  card: { type: Number, default: null },
  size: { type: String, default: 'hand' },
  trump: { type: Boolean, default: false },
})

const suit = computed(() => (props.card === null ? null : suitOf(props.card)))
</script>

<template>
  <span
    class="pcard"
    :class="[
      `pcard--${size}`,
      card === null ? 'pcard--back' : isRed(suit) ? 'pcard--red' : 'pcard--black',
      { 'pcard--trump': trump },
    ]"
  >
    <template v-if="card !== null">
      <span class="pcard__corner">
        <span class="pcard__rank">{{ rankLabel(card) }}</span>
        <span class="pcard__suit">{{ suitSymbol(suit) }}</span>
      </span>
      <span class="pcard__pip">{{ suitSymbol(suit) }}</span>
    </template>
  </span>
</template>

<style scoped>
.pcard {
  position: relative;
  flex-shrink: 0;
  display: inline-flex;
  border-radius: var(--radius-md);
  background: var(--text);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.35);
  user-select: none;
  overflow: hidden;
}

.pcard--hand { width: 76px; height: 108px; }
.pcard--table { width: 62px; height: 88px; }
.pcard--mini { width: 34px; height: 48px; border-radius: var(--radius-sm); }

.pcard--black { color: var(--bg); }
.pcard--red { color: var(--danger); }

/* Рубашка — фирменный градиент направлений. */
.pcard--back {
  background:
    repeating-linear-gradient(45deg, rgba(255, 255, 255, 0.08) 0 4px, transparent 4px 8px),
    linear-gradient(135deg, var(--accent), var(--dir-prod-b));
  border: 2px solid var(--text);
}

.pcard__corner {
  position: absolute;
  top: 6px;
  left: 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1;
  gap: 1px;
}

.pcard__rank {
  font: 600 20px/1 var(--font-sans);
}

.pcard__suit {
  font-size: 15px;
}

.pcard__pip {
  margin: auto;
  padding-top: 14px;
  font-size: 24px;
  line-height: 1;
  transform: scale(1.4);
}

.pcard--table .pcard__rank { font-size: 18px; }
.pcard--table .pcard__suit { font-size: 14px; }
.pcard--table .pcard__pip { padding-top: 12px; transform: scale(1.15); }
.pcard--mini .pcard__rank { font-size: 12px; }
.pcard--mini .pcard__suit { font-size: 11px; }
.pcard--mini .pcard__pip { display: none; }

.pcard--trump {
  box-shadow: 0 0 0 2px var(--prio-medium), 0 2px 6px rgba(0, 0, 0, 0.35);
}
</style>
