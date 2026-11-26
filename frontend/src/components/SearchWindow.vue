<template>
  <MiniWindow
    :label="label"
    :compact="compact"
    :viewing="viewing"
    :active="active"
    editable-label
    closable
    @expand="emit('expand')"
    @minimize="emit('minimize')"
    @close="emit('close')"
    @update:label="emit('update:label', $event)"
  >
    <template #summary>{{ compactSummary }}</template>
    <template #count>{{ compactCount }}</template>

    <template #actions>
      <button type="button" class="text-button" title="Open a copy of this search in a new window" @click="emit('duplicate')">
        Duplicate
      </button>
    </template>

    <SearchPanel
      :search="search"
      :can-choose-index="canChooseIndex"
      @open-index="emit('open-index')"
    />

    <section v-if="state.schema || state.response" class="results-section" aria-label="Search results">
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
          @select="emit('select-hit', $event)"
          @page="search.goToPage"
          @sort="search.setSort"
        />
        <!-- The table sets the height; the refine values scroll beside it. -->
        <div class="refine-column">
          <div class="refine-scroll">
            <RefinePanel
              :facets="state.response.facets ?? {}"
              :labels="search.fieldLabels.value"
              @add="search.addRefinement"
            />
          </div>
        </div>
      </div>
      <p v-else class="empty-note">{{ state.loading ? 'Searching...' : 'Run the search to list its results here.' }}</p>
    </section>
  </MiniWindow>
</template>

<script setup lang="ts">
// A search window: the query builder with the results of its search below it.
// Compact, it shows what was searched and how much matched.
import { computed } from 'vue'
import MiniWindow from './MiniWindow.vue'
import RefinePanel from './RefinePanel.vue'
import SearchPanel from './SearchPanel.vue'
import SearchResultsTable from './SearchResultsTable.vue'
import { PAGE_SIZE, type AdvancedSearch, type SearchHit } from '@/composables/useAdvancedSearch'
import { describeCondition, summarizeRows, summaryText, type FilterRow } from '@/services/filterRows'

const props = withDefaults(defineProps<{
  search: AdvancedSearch
  label: string
  compact?: boolean
  /** Whether the viewer shows one of this window's results. */
  viewing?: boolean
  /** Whether this is the card of the window that is open at normal size. */
  active?: boolean
  /** Whether the index can be chosen here, which public mode does not allow. */
  canChooseIndex?: boolean
}>(), {
  compact: false,
  viewing: false,
  active: false,
  canChooseIndex: false
})

const emit = defineEmits<{
  (event: 'expand'): void
  (event: 'minimize'): void
  (event: 'close'): void
  (event: 'duplicate'): void
  (event: 'update:label', label: string): void
  (event: 'select-hit', hit: SearchHit): void
  (event: 'open-index'): void
}>()

const state = props.search.state

const describe = (rows: FilterRow[]) => {
  const fields = new Map(props.search.builderFields.value.map(field => [field.name, field]))
  return summaryText(summarizeRows(rows, condition => describeCondition(condition, fields)))
}

// What the shown results were searched for; before a search, what the builder asks
const compactSummary = computed(() => {
  if (state.searchedRows) return describe(state.searchedRows) || 'Everything'
  if (!state.schema && !state.schemaLoading) return state.schemaError ? state.schemaError.message : 'No index is open'
  return describe(state.rows) || 'No conditions yet'
})

const compactCount = computed(() => {
  if (state.loading) return 'Searching...'
  if (state.error) return 'Search failed'
  if (!state.response) return 'Not searched yet'
  const { total } = state.response
  // The total counts protoclusters at that level and regions otherwise, records included
  const unit = state.searchedLevel === 'protocluster' ? 'protocluster' : 'region'
  return `${total.toLocaleString()} matching ${unit}${total === 1 ? '' : 's'}`
})
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

.results-section {
  border-top: 1px solid #dce3e8;
}

.results {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 230px;
  gap: 14px;
  padding: 12px 14px 14px;
}

/* Absolutely placed content adds no height, so the row is as tall as the table
   and the refine values scroll within it. */
.refine-column {
  position: relative;
  min-height: 200px;
}

.refine-scroll {
  position: absolute;
  inset: 0;
  overflow-y: auto;
  padding-right: 4px;
}

.empty-note {
  margin: 0;
  padding: 18px 14px;
  color: #52616d;
  font-size: 13px;
  text-align: center;
}

@media (max-width: 800px) {
  .results {
    grid-template-columns: minmax(0, 1fr);
  }

  .refine-column {
    min-height: 0;
  }

  .refine-scroll {
    position: static;
    max-height: 280px;
  }
}
</style>
