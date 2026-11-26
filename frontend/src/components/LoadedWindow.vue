<template>
  <MiniWindow
    label="Loaded data"
    :compact="compact"
    :viewing="viewing"
    @expand="emit('expand')"
    @minimize="emit('minimize')"
  >
    <template #summary>{{ sources || (loading ? 'Loading...' : 'Nothing loaded') }}</template>
    <template #count>{{ error ? 'Loading failed' : count }}</template>

    <template #actions>
      <button type="button" class="text-button" @click="emit('load')">Load data...</button>
    </template>

    <div class="loaded-body">
      <div class="results-bar">
        <h3>{{ count }}</h3>
        <LevelToggle :model-value="level" :levels="['region', 'record']" @update:model-value="emit('update:level', $event)" />
      </div>
      <LoadedRecordsList
        :records="records"
        :regions="regions"
        :level="level"
        :selected-key="selectedKey"
        :loading="loading"
        :error="error"
        @select="emit('select', $event)"
        @select-region="emit('select-region', $event)"
        @remove-source="emit('remove-source', $event)"
      />
    </div>
  </MiniWindow>
</template>

<script setup lang="ts">
// The window of the records loaded beside the index, from files or external
// databases, listed by region or by record. Only the index holds protoclusters.
// Compact, it shows where the records came from and how many there are.
import { computed } from 'vue'
import LevelToggle from './LevelToggle.vue'
import LoadedRecordsList from './LoadedRecordsList.vue'
import MiniWindow from './MiniWindow.vue'
import type { LoadedRecord, LoadedRegion } from '@/composables/useLoadedRecords'

export type LoadedLevel = 'region' | 'record'

const props = withDefaults(defineProps<{
  records: LoadedRecord[]
  regions?: LoadedRegion[]
  level?: LoadedLevel
  /** Key of the selected record, or of the selected region. */
  selectedKey?: string | null
  loading?: boolean
  error?: string | null
  compact?: boolean
  /** Whether the viewer shows one of these records. */
  viewing?: boolean
}>(), {
  regions: () => [],
  level: 'region',
  selectedKey: null,
  loading: false,
  error: null,
  compact: false,
  viewing: false
})

const emit = defineEmits<{
  (event: 'expand'): void
  (event: 'minimize'): void
  (event: 'load'): void
  (event: 'update:level', level: LoadedLevel): void
  (event: 'select', record: LoadedRecord): void
  (event: 'select-region', region: LoadedRegion): void
  (event: 'remove-source', source: string): void
}>()

const plural = (n: number, word: string) => `${n.toLocaleString()} ${word}${n === 1 ? '' : 's'}`

const count = computed(() => `${plural(props.records.length, 'record')} · ${plural(props.regions.length, 'region')}`)

const sources = computed(() => [...new Set(props.records.map(record => record.sourceLabel))].join(', '))
</script>

<style scoped>
.text-button {
  height: 28px;
  padding: 0 10px;
  border: 1px solid #aebbc4;
  border-radius: 4px;
  background: #fff;
  color: #30434f;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
}

.text-button:hover {
  background: #edf2f5;
}

.text-button:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: 1px;
}

.loaded-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px 14px 14px;
}

/* The window body scrolls, so the list needs no scroll box of its own */
.loaded-body :deep(.table-scroll) {
  max-height: none;
}

.results-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 20px;
}

.results-bar h3 {
  margin: 0;
  color: #263442;
  font-size: 14px;
}
</style>
