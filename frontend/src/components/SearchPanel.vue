<template>
  <div class="search-panel">
    <div class="query">
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
          <button type="button" class="help-button" @click="helpOpen = true">Search help</button>
        </div>
      </form>

      <div v-if="state.error" class="search-error" role="alert">
        <strong>{{ state.error.code }}</strong>: {{ state.error.message }}
      </div>
    </div>

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
// The query part of a search window: the builder, a summary of what it asks, and
// the search button. The results are shown by SearchWindow below it. The search
// help opens in a dialog.
import { computed, ref } from 'vue'
import AppDialog from './AppDialog.vue'
import QueryBuilder from './QueryBuilder.vue'
import SearchHelpPopup from './SearchHelpPopup.vue'
import type { AdvancedSearch } from '@/composables/useAdvancedSearch'
import { describeCondition, summarizeRows } from '@/services/filterRows'

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

const summary = computed(() => {
  const fields = new Map(props.search.builderFields.value.map(field => [field.name, field]))
  return summarizeRows(state.rows, condition => describeCondition(condition, fields))
})

function runSearch() {
  emit('searched')
  props.search.search()
}

// An example is a query string, so it becomes the builder's one condition.
function useExample(example: string) {
  props.search.useQueryString(example)
  helpOpen.value = false
}
</script>

<style scoped>
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
  padding: 12px 14px;
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

.form-actions .help-button {
  margin-left: auto;
}

.submit-button:hover {
  background: #145f92;
}

.submit-button:disabled {
  border-color: #a3afb7;
  background: #a3afb7;
  cursor: default;
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
