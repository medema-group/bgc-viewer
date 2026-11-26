<template>
  <div class="level-switch">
    <span class="level-label">Show</span>
    <div class="level-toggle" role="group" aria-label="Result level">
      <button
        v-for="option in shown"
        :key="option.level"
        type="button"
        :class="{ active: modelValue === option.level }"
        :aria-pressed="modelValue === option.level"
        @click="emit('update:modelValue', option.level)"
      >
        {{ option.label }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
// Picks the level a result list shows: protoclusters, regions, or records.
import { computed } from 'vue'
import type { SearchLevel } from '@/services/dataProviders/types'

const props = withDefaults(defineProps<{
  modelValue: SearchLevel
  /** The levels offered, in this order. */
  levels?: SearchLevel[]
}>(), {
  levels: () => ['protocluster', 'region', 'record']
})

const emit = defineEmits<{
  (event: 'update:modelValue', level: SearchLevel): void
}>()

const LABELS: Record<SearchLevel, string> = {
  protocluster: 'Protoclusters',
  region: 'Regions',
  record: 'Records'
}

const shown = computed(() => props.levels.map(level => ({ level, label: LABELS[level] })))
</script>

<style scoped>
.level-switch {
  display: flex;
  align-items: center;
  gap: 8px;
}

.level-label {
  color: #52616d;
  font-size: 13px;
}

.level-toggle {
  display: inline-flex;
}

.level-toggle button {
  height: 28px;
  padding: 0 12px;
  border: 1px solid #aebbc4;
  border-radius: 0;
  background: #fff;
  color: #30434f;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
}

/* Neighbouring buttons share one border. */
.level-toggle button + button {
  margin-left: -1px;
}

.level-toggle button:first-child {
  border-radius: 4px 0 0 4px;
}

.level-toggle button:last-child {
  border-radius: 0 4px 4px 0;
}

.level-toggle button.active {
  border-color: #1976b5;
  background: #1976b5;
  color: #fff;
}

.level-toggle button:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: 1px;
}
</style>
