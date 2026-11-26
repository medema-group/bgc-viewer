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

      <!-- The rows are searched by themselves after a pause; Enter searches them right away -->
      <form v-else class="search-form" @submit.prevent @keydown.enter="search.searchNow()">
        <!-- The summary, level and search buttons share the line of the builder's own buttons -->
        <QueryBuilder
          :rows="state.rows"
          :fields="search.builderFields.value"
          :load-values="search.loadValues"
          @update:rows="state.rows = $event"
        >
          <template #actions>
            <button
              type="button"
              class="icon-button help-button"
              title="Search help"
              aria-label="Search help"
              @click="helpOpen = true"
            >
              <svg viewBox="0 0 16 16" aria-hidden="true">
                <circle cx="8" cy="8" r="6.5" />
                <path d="M6.2 6.3a1.8 1.8 0 1 1 2.6 1.6c-.5.3-.8.6-.8 1.2v.4" />
                <circle class="dot" cx="8" cy="11.4" r="0.4" />
              </svg>
            </button>

            <!-- The summary of what the builder asks, shown on hover or keyboard focus -->
            <div v-if="summary.length" class="summary-hint">
              <button
                type="button"
                class="icon-button"
                aria-label="Search summary"
                :aria-describedby="summaryId"
              >
                <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 4.5h10M3 8h10M3 11.5h6" /></svg>
              </button>
              <div :id="summaryId" class="summary" role="tooltip">
                <div v-for="(line, index) in summary" :key="index" class="summary-line">
                  <span v-if="line.joiner" class="summary-joiner">{{ line.joiner }}</span>
                  <span>
                    <template v-for="(part, partIndex) in line.parts" :key="partIndex">
                      <span v-if="part.kind === 'op'" class="summary-op"> {{ part.value }} </span>
                      <span v-else-if="part.kind === 'paren'" class="summary-paren">{{ part.value }}</span>
                      <span v-else>{{ part.value }}</span>
                    </template>
                  </span>
                </div>
              </div>
            </div>

            <div class="form-actions">
              <span class="search-status" role="status">{{ state.loading ? 'Searching...' : '' }}</span>
              <LevelToggle :model-value="state.level" @update:model-value="search.setLevel" />
            </div>
          </template>
        </QueryBuilder>
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
// The query part of a search window: the builder, with the search help, a summary
// of what it asks (on hover), the level to list, and the search button on the line
// of its own buttons. The
// results are shown by SearchWindow below it. The search help opens in a dialog.
import { computed, ref } from 'vue'
import AppDialog from './AppDialog.vue'
import LevelToggle from './LevelToggle.vue'
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
}>()

const state = props.search.state
const helpOpen = ref(false)
// Ties the summary button to its tooltip; there can be several search windows
const summaryId = `search-summary-${Math.random().toString(36).slice(2, 10)}`

const summary = computed(() => {
  const fields = new Map(props.search.builderFields.value.map(field => [field.name, field]))
  return summarizeRows(state.rows, condition => describeCondition(condition, fields))
})

// An example is a query string, so it becomes the builder's one condition.
function useExample(example: string) {
  props.search.useQueryString(example)
  helpOpen.value = false
}
</script>

<style scoped>
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
  padding: 12px 14px;
}

/* Small square buttons beside the builder's own buttons */
.icon-button {
  display: inline-flex;
  width: 28px;
  height: 28px;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid #aebbc4;
  border-radius: 4px;
  background: #fff;
  color: #52616d;
  cursor: pointer;
}

.icon-button:hover {
  background: #edf2f5;
  color: #263442;
}

.icon-button svg {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.5;
}

.icon-button svg .dot {
  fill: currentColor;
}

.summary-hint {
  position: relative;
  display: inline-flex;
}

/* The summary opens below its button while the button is hovered or focused */
.summary {
  position: absolute;
  z-index: 20;
  top: calc(100% + 6px);
  left: 0;
  display: none;
  width: max-content;
  max-width: min(480px, 70vw);
  padding: 8px 10px;
  border: 1px solid #dce3e8;
  border-radius: 6px;
  background: #fff;
  box-shadow: 0 4px 12px rgba(38, 52, 66, 0.15);
  color: #30434f;
  font-size: 12px;
  line-height: 1.5;
}

.summary-hint:hover .summary,
.summary-hint:focus-within .summary {
  display: block;
}

.summary-line {
  display: flex;
  gap: 6px;
}

.summary-joiner {
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
  gap: 8px;
  margin-left: auto;
}

.search-status {
  color: #687681;
  font-size: 12px;
  font-style: italic;
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
