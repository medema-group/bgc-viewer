<template>
  <section class="panel" aria-label="Results">
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
        Loaded records <span class="tab-count">{{ loadedRecords.length }}</span>
      </button>
    </nav>

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
        :selected-key="selectedLoadedKey"
        :loading="loadedLoading"
        :error="loadedError"
        @select="emit('select-loaded', $event)"
        @remove-source="emit('remove-source', $event)"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
// The result lists of the main view: the index search results and the records
// loaded beside the index, as tabs over one panel.
import { computed } from 'vue'
import LoadedRecordsList from './LoadedRecordsList.vue'
import RefinePanel from './RefinePanel.vue'
import SearchResultsTable from './SearchResultsTable.vue'
import { PAGE_SIZE, type AdvancedSearch, type SearchHit } from '@/composables/useAdvancedSearch'
import type { LoadedRecord } from '@/composables/useLoadedRecords'

export type ResultsTab = 'search' | 'loaded'

const props = withDefaults(defineProps<{
  search: AdvancedSearch
  tab: ResultsTab
  loadedRecords: LoadedRecord[]
  selectedLoadedKey?: string | null
  loadedLoading?: boolean
  loadedError?: string | null
}>(), {
  selectedLoadedKey: null,
  loadedLoading: false,
  loadedError: null
})

const emit = defineEmits<{
  (event: 'update:tab', tab: ResultsTab): void
  (event: 'select-hit', hit: SearchHit): void
  (event: 'select-loaded', record: LoadedRecord): void
  (event: 'remove-source', source: string): void
}>()

const state = props.search.state

const hasLoaded = computed(
  () => props.loadedRecords.length > 0 || props.loadedLoading || Boolean(props.loadedError)
)
const hasSearch = computed(() => Boolean(state.response) || state.loading)

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

.result-tabs {
  display: flex;
  gap: 20px;
  padding: 0 16px;
  border-bottom: 1px solid #dce3e8;
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

.result-tabs button:focus-visible {
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
