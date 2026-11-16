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

      <nav class="dialog-tabs" aria-label="Search dialog views">
        <button
          v-for="tab in tabs"
          :key="tab.view"
          type="button"
          :class="{ active: view === tab.view }"
          :aria-current="view === tab.view ? 'page' : undefined"
          @click="view = tab.view"
        >
          {{ tab.label }}
        </button>
      </nav>

      <div class="dialog-body">
        <SearchHelpPopup
          v-if="view === 'help'"
          :schema="state.schema"
          :loading="state.schemaLoading"
          :error="state.schemaError"
          @use-example="useExample"
        />

        <template v-else>
          <form class="search-form" @submit.prevent="runSearch">
            <p v-if="state.schemaLoading" class="form-note">Loading fields...</p>
            <p v-else-if="state.schemaError" class="form-note error" role="alert">
              <strong>{{ state.schemaError.code }}</strong>: {{ state.schemaError.message }}
            </p>
            <QueryBuilder
              v-else-if="state.schema"
              :rows="state.rows"
              :fields="search.builderFields.value"
              :load-values="search.loadValues"
              @update:rows="state.rows = $event"
            />
            <div v-if="summary.length" class="summary" aria-label="Search summary">
              <div v-for="(line, index) in summary" :key="index" class="summary-line">
                <span class="summary-joiner">{{ line.joiner }}</span>
                <span>
                  <template v-for="(part, partIndex) in line.parts" :key="partIndex">
                    <span v-if="part.kind === 'op'" class="summary-op"> {{ part.value }} </span>
                    <span v-else-if="part.kind === 'paren'" class="summary-paren">{{ part.value }}</span>
                    <span v-else>{{ part.value }}</span>
                  </template>
                </span>
              </div>
            </div>

            <div class="form-actions">
              <button type="submit" class="submit-button" :disabled="!search.canSearch.value">
                {{ search.hasRules.value ? 'Search' : 'Browse all' }}
              </button>
              <span class="level-label">Show</span>
              <div class="level-toggle" role="group" aria-label="Search result level">
                <button
                  v-for="option in levels"
                  :key="option.level"
                  type="button"
                  :class="{ active: state.level === option.level }"
                  :aria-pressed="state.level === option.level"
                  @click="search.setLevel(option.level)"
                >
                  {{ option.label }}
                </button>
              </div>
            </div>
          </form>

          <div v-if="state.error" class="search-error" role="alert">
            <strong>{{ state.error.code }}</strong>: {{ state.error.message }}
          </div>

          <div v-if="state.response" class="results">
            <SearchResultsTable
              :level="state.searchedLevel"
              :response="state.response"
              :page="state.page"
              :per-page="PAGE_SIZE"
              :sort="state.sort"
              :sortable-fields="search.sortableFields.value"
              :selected-hit="state.selectedHit"
              :loading="state.loading"
              @select="emit('select', $event)"
              @page="search.goToPage"
              @sort="search.setSort"
            />
            <RefinePanel
              :facets="state.response.facets ?? {}"
              :labels="search.fieldLabels.value"
              @add="search.addRefinement"
            />
          </div>
          <div v-else class="search-empty">
            <p v-if="state.loading">Searching...</p>
            <template v-else>
              <strong>Search the active index</strong>
              <p>Add conditions, then press Search.</p>
            </template>
          </div>
        </template>
      </div>

      <footer class="dialog-footer">
        <span><kbd>Enter</kbd> search</span>
        <span><kbd>Esc</kbd> close</span>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import QueryBuilder from './QueryBuilder.vue'
import RefinePanel from './RefinePanel.vue'
import SearchHelpPopup from './SearchHelpPopup.vue'
import SearchResultsTable from './SearchResultsTable.vue'
import { PAGE_SIZE, type AdvancedSearch, type SearchHit } from '@/composables/useAdvancedSearch'
import { describeCondition, summarizeRows } from '@/services/filterRows'
import type { SearchLevel } from '@/services/dataProviders/types'

type View = 'builder' | 'help'

const props = defineProps<{
  search: AdvancedSearch
}>()

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'select', hit: SearchHit): void
}>()

const state = props.search.state
const view = ref<View>('builder')

const tabs: { view: View; label: string }[] = [
  { view: 'builder', label: 'Query builder' },
  { view: 'help', label: 'Search help' }
]

const levels: { level: SearchLevel; label: string }[] = [
  { level: 'region', label: 'Regions' },
  { level: 'record', label: 'Records' }
]

const summary = computed(() => {
  const fields = new Map(props.search.builderFields.value.map(field => [field.name, field]))
  return summarizeRows(state.rows, condition => describeCondition(condition, fields))
})

function runSearch() {
  props.search.search()
}

// An example is a query string, so it becomes the builder's one condition.
function useExample(example: string) {
  props.search.useQueryString(example)
  view.value = 'builder'
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close')
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
  props.search.loadSchema()
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
  padding: min(8vh, 64px) 20px 20px;
  background: rgba(22, 31, 38, 0.62);
}

.search-dialog {
  display: flex;
  width: min(1180px, 100%);
  max-height: min(86vh, 960px);
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
  padding: 14px 18px 6px;
}

.dialog-header h2 {
  margin: 0;
  color: #263442;
  font-size: 16px;
  letter-spacing: 0;
}

.close-button {
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

.close-button:hover {
  background: #edf2f5;
}

.dialog-tabs {
  display: flex;
  gap: 20px;
  padding: 0 18px;
  border-bottom: 1px solid #dce3e8;
}

.dialog-tabs button {
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

.dialog-body {
  flex: 1;
  min-height: 260px;
  overflow-y: auto;
}

.search-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 1px solid #dce3e8;
}

.form-note {
  margin: 0;
  color: #52616d;
  font-size: 13px;
}

.form-note.error {
  color: #a1261d;
}

.summary {
  padding: 8px 10px;
  border-radius: 6px;
  background: #f6f8f9;
  color: #30434f;
  font-size: 12px;
}

.summary-line {
  display: flex;
  gap: 8px;
}

.summary-joiner {
  width: 30px;
  flex-shrink: 0;
  color: #687681;
  font-size: 11px;
  font-weight: 700;
}

.summary-op {
  color: #687681;
  font-size: 11px;
  font-weight: 700;
}

.summary-paren {
  color: #687681;
}

.form-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.submit-button {
  height: 34px;
  padding: 0 17px;
  border: 1px solid #176da7;
  border-radius: 4px;
  background: #1976b5;
  color: #fff;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
}

.submit-button:hover {
  background: #145f92;
}

.submit-button:disabled {
  border-color: #a3afb7;
  background: #a3afb7;
  cursor: default;
}

.level-label {
  color: #52616d;
  font-size: 13px;
}

.level-toggle {
  display: inline-flex;
}

.level-toggle button {
  height: 30px;
  padding: 0 12px;
  border: 1px solid #aebbc4;
  background: #fff;
  color: #30434f;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
}

.level-toggle button:first-child {
  border-radius: 4px 0 0 4px;
}

.level-toggle button:last-child {
  margin-left: -1px;
  border-radius: 0 4px 4px 0;
}

.level-toggle button.active {
  border-color: #1976b5;
  background: #1976b5;
  color: #fff;
}

.search-dialog button:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: 1px;
}

.search-error {
  padding: 9px 18px;
  border-bottom: 1px solid #efc8c4;
  background: #fff3f2;
  color: #a1261d;
  font-size: 12px;
}

.results {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 230px;
  align-items: start;
  gap: 14px;
  padding: 14px 18px;
}

.search-empty {
  display: flex;
  min-height: 160px;
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

@media (max-width: 800px) {
  .search-overlay {
    padding: 8px;
  }

  .search-dialog {
    max-height: calc(100vh - 16px);
  }

  .results {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
