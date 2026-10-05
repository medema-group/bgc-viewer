<template>
  <div class="search-overlay" @mousedown.self="emit('close')">
    <section
      class="search-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="search-dialog-title"
    >
      <header class="dialog-header">
        <h2 id="search-dialog-title">Search BGC data</h2>
        <button
          type="button"
          class="close-button"
          aria-label="Close search"
          title="Close search"
          @click="emit('close')"
        >
          &times;
        </button>
      </header>

      <form class="search-form" @submit.prevent="submit">
        <div class="query-control">
          <span class="search-icon" aria-hidden="true"></span>
          <input
            ref="queryInput"
            :value="query"
            type="search"
            aria-label="Advanced search query"
            placeholder="Search records, regions, and protoclusters"
            @input="updateQuery"
          />
          <button
            v-if="query"
            type="button"
            class="clear-button"
            aria-label="Clear search"
            title="Clear search"
            @click="emit('clear')"
          >
            &times;
          </button>
        </div>

        <select :value="level" aria-label="Search result level" @change="changeLevel">
          <option value="protocluster">Protocluster</option>
          <option value="region">Region</option>
          <option value="record">Record</option>
        </select>

        <button type="submit" class="submit-button">Search</button>
      </form>

      <nav class="dialog-tabs" aria-label="Search dialog views">
        <button
          type="button"
          :class="{ active: view === 'results' }"
          :aria-current="view === 'results' ? 'page' : undefined"
          @click="view = 'results'"
        >
          Results
          <span v-if="response" class="result-count">{{ response.hits.length }}</span>
        </button>
        <button
          type="button"
          :class="{ active: view === 'help' }"
          :aria-current="view === 'help' ? 'page' : undefined"
          @click="showHelp"
        >
          Search help
        </button>
      </nav>

      <div v-if="error && view === 'results'" class="search-error" role="alert">
        <strong>{{ error.code }}</strong>: {{ error.message }}
      </div>

      <div class="dialog-body">
        <SearchHelpPopup
          v-if="view === 'help'"
          :schema="schema"
          :loading="schemaLoading"
          :error="schemaError"
          @use-example="useExample"
        />
        <SearchResultsPopover
          v-else-if="response"
          :query="resultsQuery"
          :level="resultsLevel"
          :response="response"
          :selected-hit="selectedHit"
          :loading="loading"
          :loading-more="loadingMore"
          @load-more="emit('load-more')"
          @search-selected="emit('search-selected', $event)"
        />
        <div v-else class="search-empty">
          <p v-if="loading">Searching...</p>
          <template v-else>
            <strong>Search the active index</strong>
            <p>Use a word or field query, then press Enter.</p>
          </template>
        </div>
      </div>

      <footer class="dialog-footer">
        <span><kbd>Enter</kbd> search</span>
        <span><kbd>Esc</kbd> close</span>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import SearchHelpPopup from './SearchHelpPopup.vue'
import SearchResultsPopover from './SearchResultsPopover.vue'
import type {
  ProtoclusterSearchHit,
  RecordSearchHit,
  RegionSearchHit,
  SearchLevel,
  SearchResponse,
  SearchSchema
} from '@/services/dataProviders/types'

type SearchHit = ProtoclusterSearchHit | RegionSearchHit | RecordSearchHit

interface SearchError {
  code: string
  message: string
}

const props = defineProps<{
  query: string
  level: SearchLevel
  response: SearchResponse<SearchHit> | null
  resultsQuery: string
  resultsLevel: SearchLevel
  selectedHit: SearchHit | null
  loading: boolean
  loadingMore: boolean
  error: SearchError | null
  schema: SearchSchema | null
  schemaLoading: boolean
  schemaError: SearchError | null
}>()

const emit = defineEmits<{
  (event: 'update:query', query: string): void
  (event: 'update:level', level: SearchLevel): void
  (event: 'search', payload: { query: string; level: SearchLevel; page: number }): void
  (event: 'clear'): void
  (event: 'close'): void
  (event: 'request-help'): void
  (event: 'load-more'): void
  (event: 'search-selected', hit: SearchHit): void
}>()

const queryInput = ref<HTMLInputElement | null>(null)
const view = ref<'results' | 'help'>('results')

function updateQuery(event: Event) {
  emit('update:query', (event.target as HTMLInputElement).value)
}

function submit() {
  view.value = 'results'
  emit('search', { query: queryInput.value?.value ?? props.query, level: props.level, page: 1 })
}

function changeLevel(event: Event) {
  const level = (event.target as HTMLSelectElement).value as SearchLevel
  emit('update:level', level)
  if (props.query.trim()) {
    view.value = 'results'
    emit('search', { query: props.query, level, page: 1 })
  }
}

function showHelp() {
  view.value = 'help'
  emit('request-help')
}

async function useExample(example: string) {
  emit('update:query', example)
  view.value = 'results'
  await nextTick()
  queryInput.value?.focus()
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close')
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
  queryInput.value?.focus()
})
onUnmounted(() => document.removeEventListener('keydown', handleKeydown))
</script>

<style scoped>
.search-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: min(12vh, 104px) 20px 20px;
  background: rgba(22, 31, 38, 0.62);
}

.search-dialog {
  display: flex;
  width: min(760px, 100%);
  max-height: min(76vh, 720px);
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #b9c5cc;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 24px 70px rgba(14, 29, 38, 0.34);
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px 10px;
}

.dialog-header h2 {
  margin: 0;
  color: #263442;
  font-size: 16px;
  letter-spacing: 0;
}

.close-button,
.clear-button {
  border: 0;
  background: transparent;
  color: #5d6c77;
  cursor: pointer;
  line-height: 1;
}

.close-button {
  width: 32px;
  height: 32px;
  font-size: 25px;
}

.close-button:hover,
.clear-button:hover {
  background: #edf2f5;
}

.search-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 126px auto;
  gap: 8px;
  padding: 0 18px 14px;
}

.query-control {
  position: relative;
  min-width: 0;
}

.query-control input,
.search-form select,
.submit-button {
  height: 42px;
  border-radius: 4px;
  font: inherit;
  font-size: 14px;
}

.query-control input,
.search-form select {
  width: 100%;
  border: 1px solid #aebbc4;
  background: #fff;
  color: #263442;
}

.query-control input {
  padding: 8px 36px 8px 38px;
}

.query-control input::-webkit-search-cancel-button {
  appearance: none;
}

.search-form select {
  padding: 7px 9px;
}

.query-control input:focus,
.search-form select:focus,
.search-dialog button:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: 1px;
}

.search-icon {
  position: absolute;
  top: 13px;
  left: 14px;
  width: 13px;
  height: 13px;
  border: 2px solid #687681;
  border-radius: 50%;
}

.search-icon::after {
  position: absolute;
  right: -5px;
  bottom: -3px;
  width: 6px;
  height: 2px;
  background: #687681;
  content: '';
  transform: rotate(45deg);
}

.clear-button {
  position: absolute;
  top: 7px;
  right: 6px;
  width: 28px;
  height: 28px;
  font-size: 20px;
}

.submit-button {
  padding: 0 17px;
  border: 1px solid #176da7;
  background: #1976b5;
  color: #fff;
  cursor: pointer;
  font-weight: 700;
}

.submit-button:hover {
  background: #145f92;
}

.dialog-tabs {
  display: flex;
  gap: 20px;
  padding: 0 18px;
  border-bottom: 1px solid #dce3e8;
}

.dialog-tabs button {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px 1px 9px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: #5b6973;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
}

.dialog-tabs button.active {
  border-bottom-color: #1976b5;
  color: #145f92;
}

.result-count {
  min-width: 20px;
  padding: 1px 6px;
  border-radius: 10px;
  background: #e7eef2;
  color: #40525e;
  font-size: 11px;
  text-align: center;
}

.search-error {
  padding: 9px 18px;
  border-bottom: 1px solid #efc8c4;
  background: #fff3f2;
  color: #a1261d;
  font-size: 12px;
}

.dialog-body {
  flex: 1;
  min-height: 220px;
  overflow-y: auto;
}

.search-empty {
  display: flex;
  min-height: 220px;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  color: #52616d;
  text-align: center;
}

.search-empty strong {
  color: #30434f;
  font-size: 14px;
}

.search-empty p {
  margin: 4px 0 0;
  font-size: 13px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 14px;
  padding: 8px 18px;
  border-top: 1px solid #dce3e8;
  background: #f6f8f9;
  color: #687681;
  font-size: 11px;
}

kbd {
  padding: 1px 4px;
  border: 1px solid #cad3d9;
  border-radius: 3px;
  background: #fff;
  color: #43535f;
  font: 10px 'IBM Plex Mono', 'Liberation Mono', monospace;
}

@media (max-width: 600px) {
  .search-overlay {
    padding: 8px;
  }

  .search-dialog {
    max-height: calc(100vh - 16px);
  }

  .search-form {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .search-form select {
    grid-column: 1 / -1;
    grid-row: 2;
  }

  .submit-button {
    grid-column: 2;
    grid-row: 1;
  }
}
</style>