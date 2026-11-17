<template>
  <div class="search-panel">
    <section class="panel" aria-labelledby="search-panel-title">
      <header class="panel-header">
        <h2 id="search-panel-title">Search</h2>
        <button type="button" class="help-button" @click="helpOpen = true">Search help</button>
      </header>

      <div v-if="!state.schema" class="index-note">
        <p v-if="state.schemaLoading">Loading fields...</p>
        <template v-else>
          <p v-if="state.schemaError" class="error" role="alert">
            <strong>{{ state.schemaError.code }}</strong>: {{ state.schemaError.message }}
          </p>
          <p v-else>No index is open.</p>
          <button v-if="canChooseIndex" type="button" class="secondary-button" @click="emit('open-index')">
            Choose an index
          </button>
        </template>
      </div>

      <form v-else class="search-form" @submit.prevent="runSearch">
        <QueryBuilder
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
              @click="changeLevel(option.level)"
            >
              {{ option.label }}
            </button>
          </div>
        </div>
      </form>

      <div v-if="state.error" class="search-error" role="alert">
        <strong>{{ state.error.code }}</strong>: {{ state.error.message }}
      </div>
    </section>

    <AppDialog :open="helpOpen" title="Search help" width="min(860px, 100%)" @close="helpOpen = false">
      <SearchHelpPopup
        :schema="state.schema"
        :loading="state.schemaLoading"
        :error="state.schemaError"
        @use-example="useExample"
      />
    </AppDialog>
  </div>
</template>

<script setup lang="ts">
// The main view's query builder; the results are shown by ResultsPanel. The
// search help opens in a dialog.
import { computed, ref } from 'vue'
import AppDialog from './AppDialog.vue'
import QueryBuilder from './QueryBuilder.vue'
import SearchHelpPopup from './SearchHelpPopup.vue'
import type { AdvancedSearch } from '@/composables/useAdvancedSearch'
import { describeCondition, summarizeRows } from '@/services/filterRows'
import type { SearchLevel } from '@/services/dataProviders/types'

const props = withDefaults(defineProps<{
  search: AdvancedSearch
  /** Whether the index can be chosen here, which public mode does not allow. */
  canChooseIndex?: boolean
}>(), {
  canChooseIndex: false
})

const emit = defineEmits<{
  (event: 'open-index'): void
  /** A search the user asked for, so its results can be brought forward. */
  (event: 'searched'): void
}>()

const state = props.search.state
const helpOpen = ref(false)

const levels: { level: SearchLevel; label: string }[] = [
  { level: 'region', label: 'Regions' },
  { level: 'record', label: 'Records' }
]

const summary = computed(() => {
  const fields = new Map(props.search.builderFields.value.map(field => [field.name, field]))
  return summarizeRows(state.rows, condition => describeCondition(condition, fields))
})

function runSearch() {
  emit('searched')
  props.search.search()
}

function changeLevel(level: SearchLevel) {
  emit('searched')
  props.search.setLevel(level)
}

// An example is a query string, so it becomes the builder's one condition.
function useExample(example: string) {
  props.search.useQueryString(example)
  helpOpen.value = false
}
</script>

<style scoped>
.search-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel {
  border: 1px solid #dce3e8;
  border-radius: 8px;
  background: #fff;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid #dce3e8;
}

.panel-header h2 {
  margin: 0;
  color: #263442;
  font-size: 15px;
  letter-spacing: 0;
}

.help-button,
.secondary-button {
  height: 30px;
  padding: 0 12px;
  border: 1px solid #aebbc4;
  border-radius: 4px;
  background: #fff;
  color: #30434f;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
}

.help-button:hover,
.secondary-button:hover {
  background: #edf2f5;
}

.index-note {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  color: #52616d;
  font-size: 13px;
}

.index-note p {
  margin: 0;
}

.index-note .error {
  color: #a1261d;
}

.search-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 16px;
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

.search-panel button:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: 1px;
}

.search-error {
  padding: 9px 16px;
  border-top: 1px solid #efc8c4;
  border-bottom: 1px solid #efc8c4;
  background: #fff3f2;
  color: #a1261d;
  font-size: 12px;
}
</style>
