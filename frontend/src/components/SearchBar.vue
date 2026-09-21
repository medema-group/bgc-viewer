<template>
  <div class="search-bar">
    <div class="query-control">
      <input
        ref="queryInput"
        :value="query"
        type="search"
        aria-label="Advanced search query"
        placeholder="Search protoclusters"
        @input="updateQuery"
        @keydown.enter.prevent="submit"
      />
      <button
        v-if="query"
        type="button"
        class="icon-button clear-button"
        aria-label="Clear search"
        title="Clear search"
        @click="$emit('clear')"
      >
        ×
      </button>
    </div>

    <select :value="level" aria-label="Search result level" @change="changeLevel">
      <option value="protocluster">Protocluster</option>
      <option value="region">Region</option>
      <option value="record">Record</option>
    </select>

    <button type="button" class="search-button" @click="submit">Search</button>
    <button
      type="button"
      class="icon-button help-button"
      aria-label="Search help"
      title="Search help"
      @click="$emit('help')"
    >
      ?
    </button>

    <div v-if="error" class="search-error" role="alert">
      <strong>{{ error.code }}</strong>: {{ error.message }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { SearchLevel } from '@/services/dataProviders/types'

interface SearchError {
  code: string
  message: string
}

const props = defineProps<{
  query: string
  level: SearchLevel
  error: SearchError | null
}>()

const emit = defineEmits<{
  (event: 'update:query', query: string): void
  (event: 'update:level', level: SearchLevel): void
  (event: 'search', payload: { query: string; level: SearchLevel; page: number }): void
  (event: 'clear'): void
  (event: 'help'): void
}>()

const queryInput = ref<HTMLInputElement | null>(null)

function updateQuery(event: Event) {
  emit('update:query', (event.target as HTMLInputElement).value)
}

function submit() {
  emit('search', { query: queryInput.value?.value ?? props.query, level: props.level, page: 1 })
}

function changeLevel(event: Event) {
  const level = (event.target as HTMLSelectElement).value as SearchLevel
  emit('update:level', level)
  if (props.query.trim()) {
    emit('search', { query: props.query, level, page: 1 })
  }
}
</script>

<style scoped>
.search-bar {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto auto 32px;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.query-control {
  position: relative;
  min-width: 0;
}

.query-control input,
.search-bar select {
  height: 34px;
  border: 1px solid #b8c2cc;
  border-radius: 4px;
  background: #fff;
  color: #263442;
  font: inherit;
  font-size: 13px;
}

.query-control input {
  width: 100%;
  padding: 6px 32px 6px 10px;
}

.query-control input::-webkit-search-cancel-button {
  appearance: none;
}

.search-bar select {
  width: 114px;
  padding: 5px 28px 5px 9px;
}

.query-control input:focus,
.search-bar select:focus,
.search-bar button:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: 1px;
}

.search-button,
.icon-button {
  height: 34px;
  border: 1px solid #1976d2;
  border-radius: 4px;
  cursor: pointer;
  font: inherit;
}

.search-button {
  padding: 0 13px;
  background: #1976d2;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
}

.search-button:hover {
  background: #1565c0;
}

.icon-button {
  width: 32px;
  padding: 0;
  background: #fff;
  color: #1976d2;
  font-size: 17px;
  font-weight: 700;
}

.clear-button {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 26px;
  height: 26px;
  border-color: transparent;
  color: #687681;
}

.help-button:hover,
.clear-button:hover {
  background: #edf5fb;
}

.search-error {
  grid-column: 1 / -1;
  color: #b42318;
  font-size: 12px;
  line-height: 1.3;
  text-align: left;
}

@media (max-width: 760px) {
  .search-bar {
    grid-template-columns: minmax(150px, 1fr) auto 32px;
  }

  .search-button {
    display: none;
  }
}
</style>