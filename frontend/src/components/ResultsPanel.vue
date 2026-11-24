<template>
  <section class="panel" aria-label="Results">
    <div class="results-bar">
      <nav class="result-tabs" role="tablist" aria-label="Result lists">
        <button
          type="button"
          role="tab"
          :aria-selected="active === 'search'"
          :class="{ active: active === 'search' }"
          @click="emit('update:tab', 'search')"
        >
          Search results
        </button>
        <button
          v-if="hasLoaded"
          type="button"
          role="tab"
          :aria-selected="active === 'loaded'"
          :class="{ active: active === 'loaded' }"
          @click="emit('update:tab', 'loaded')"
        >
          Loaded data <span class="tab-count">{{ loadedCount.toLocaleString() }}</span>
        </button>
      </nav>

      <!-- One level for both lists -->
      <div class="level-switch">
        <span class="level-label">Show</span>
        <div class="level-toggle" role="group" aria-label="Result level">
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
    </div>

    <div v-if="active === 'search'" class="panel-body" role="tabpanel">
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
      <p v-else class="empty-note">{{ state.loading ? 'Searching...' : 'Search the index to list results here.' }}</p>
    </div>

    <div v-else class="panel-body" role="tabpanel">
      <LoadedRecordsList
        :records="loadedRecords"
        :regions="loadedRegions"
        :level="loadedLevel"
        :selected-key="selectedLoadedKey"
        :loading="loadedLoading"
        :error="loadedError"
        @select="emit('select-loaded', $event)"
        @select-region="emit('select-loaded-region', $event)"
        @remove-source="emit('remove-source', $event)"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
// The result lists of the main view: the index search results and the records
// loaded beside the index, as tabs over one panel. Both list regions or records,
// as the level toggle says; at the protocluster level, loaded data is listed by
// region, as only the index holds protoclusters.
import { computed } from 'vue'
import LoadedRecordsList from './LoadedRecordsList.vue'
import RefinePanel from './RefinePanel.vue'
import SearchResultsTable from './SearchResultsTable.vue'
import { PAGE_SIZE, type AdvancedSearch, type SearchHit } from '@/composables/useAdvancedSearch'
import type { LoadedRecord, LoadedRegion } from '@/composables/useLoadedRecords'
import type { SearchLevel } from '@/services/dataProviders/types'

export type ResultsTab = 'search' | 'loaded'

const props = withDefaults(defineProps<{
  search: AdvancedSearch
  tab: ResultsTab
  loadedRecords: LoadedRecord[]
  loadedRegions?: LoadedRegion[]
  selectedLoadedKey?: string | null
  loadedLoading?: boolean
  loadedError?: string | null
}>(), {
  loadedRegions: () => [],
  selectedLoadedKey: null,
  loadedLoading: false,
  loadedError: null
})

const emit = defineEmits<{
  (event: 'update:tab', tab: ResultsTab): void
  (event: 'select-hit', hit: SearchHit): void
  (event: 'select-loaded', record: LoadedRecord): void
  (event: 'select-loaded-region', region: LoadedRegion): void
  (event: 'remove-source', source: string): void
}>()

const state = props.search.state

const levels: { level: SearchLevel; label: string }[] = [
  { level: 'protocluster', label: 'Protoclusters' },
  { level: 'region', label: 'Regions' },
  { level: 'record', label: 'Records' }
]

const loadedLevel = computed<SearchLevel>(() => (state.level === 'protocluster' ? 'region' : state.level))

const loadedCount = computed(() =>
  loadedLevel.value === 'region' ? props.loadedRegions.length : props.loadedRecords.length
)

const hasLoaded = computed(
  () => props.loadedRecords.length > 0 || props.loadedLoading || Boolean(props.loadedError)
)
// With an index open, its results are on their way even before the first search returns
const hasSearch = computed(() =>
  Boolean(state.response || state.schema || state.schemaError || state.error)
  || state.loading || state.schemaLoading
)

// The asked tab, unless it has nothing to show and the other one has.
const active = computed<ResultsTab>(() => {
  if (props.tab === 'loaded') return hasLoaded.value ? 'loaded' : 'search'
  return hasSearch.value || !hasLoaded.value ? 'search' : 'loaded'
})
</script>

<style scoped>
.panel {
  border: 1px solid #dce3e8;
  border-radius: 8px;
  background: #fff;
}

.results-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 20px;
  padding: 0 16px;
  border-bottom: 1px solid #dce3e8;
}

.result-tabs {
  display: flex;
  gap: 20px;
}

.result-tabs button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 1px 9px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: #5b6973;
  cursor: pointer;
  font: inherit;
  font-size: 14px;
  font-weight: 700;
}

.result-tabs button.active {
  border-bottom-color: #1976b5;
  color: #145f92;
}

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

.result-tabs button:focus-visible,
.level-toggle button:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: 1px;
}

.tab-count {
  min-width: 20px;
  padding: 0 6px;
  border-radius: 10px;
  background: #e7eef2;
  color: #40525e;
  font-size: 11px;
  text-align: center;
}

.panel-body {
  padding: 14px 16px;
}

.results {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 230px;
  gap: 14px;
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
  padding: 18px 0;
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
