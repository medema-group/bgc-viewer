<template>
  <section class="results-table" aria-label="Search results">
    <div class="table-scroll" :class="{ loading }">
      <table>
        <thead>
          <tr>
            <th v-for="column in columns" :key="column.key" scope="col" :aria-sort="ariaSort(column)">
              <button
                v-if="column.sortField && sortable.has(column.sortField)"
                type="button"
                class="sort-button"
                :title="`Sort by ${column.label}`"
                @click="cycleSort(column.sortField)"
              >
                {{ column.label }}
                <span class="sort-mark" aria-hidden="true">{{ sortMark(column) }}</span>
              </button>
              <span v-else>{{ column.label }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="hit in response.hits"
            :key="hitKey(hit)"
            :class="{ selected: isSelected(hit) }"
            tabindex="0"
            @click="emit('select', hit)"
            @keydown.enter="emit('select', hit)"
          >
            <td v-for="column in columns" :key="column.key" :class="column.key">
              {{ column.value(hit) }}
            </td>
          </tr>
          <tr v-if="response.hits.length === 0">
            <td :colspan="columns.length" class="empty">No {{ level }}s match this search.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <footer class="pager">
      <span class="pager-status">{{ status }}</span>
      <button
        type="button"
        aria-label="Previous page"
        :disabled="page <= 1 || loading"
        @click="emit('page', page - 1)"
      >
        ‹ Previous
      </button>
      <button
        type="button"
        aria-label="Next page"
        :disabled="!response.has_more || loading"
        @click="emit('page', page + 1)"
      >
        Next ›
      </button>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type {
  RecordSearchHit,
  RegionSearchHit,
  SearchLevel,
  SearchResponse,
  SearchSort
} from '@/services/dataProviders/types'

type SearchHit = RegionSearchHit | RecordSearchHit

interface Column {
  key: string
  label: string
  sortField?: string
  value: (hit: SearchHit) => string
}

const props = withDefaults(defineProps<{
  level: SearchLevel
  response: SearchResponse<SearchHit>
  page: number
  perPage: number
  sort: SearchSort | null
  /** Fields hits can be sorted by, from the search schema. */
  sortableFields: string[]
  selectedHit: SearchHit | null
  loading?: boolean
}>(), {
  loading: false
})

const emit = defineEmits<{
  (event: 'select', hit: SearchHit): void
  (event: 'page', page: number): void
  (event: 'sort', sort: SearchSort | null): void
}>()

const sortable = computed(() => new Set(props.sortableFields))

const region = (hit: SearchHit) => (hit as RegionSearchHit).fields
const record = (hit: SearchHit) => hit as RecordSearchHit

const REGION_COLUMNS: Column[] = [
  { key: 'record', label: 'Record', sortField: 'record', value: hit => region(hit).record },
  { key: 'region', label: 'Region', sortField: 'region', value: hit => `${region(hit).region}` },
  {
    key: 'location',
    label: 'Location',
    sortField: 'start',
    value: hit => {
      const { start, end } = region(hit)
      return start === null || end === null ? '' : `${start.toLocaleString()}–${end.toLocaleString()}`
    }
  },
  { key: 'product', label: 'Products', value: hit => region(hit).product.join(', ') },
  { key: 'category', label: 'Categories', value: hit => region(hit).product_category.join(', ') },
  { key: 'organism', label: 'Organism', sortField: 'organism', value: hit => region(hit).organism ?? '' },
  { key: 'file', label: 'File', value: hit => region(hit).output_file }
]

const RECORD_COLUMNS: Column[] = [
  { key: 'record', label: 'Record', sortField: 'record', value: hit => record(hit).record },
  { key: 'file', label: 'File', value: hit => record(hit).output_file },
  { key: 'input', label: 'Input file', value: hit => record(hit).input_file ?? '' }
]

const columns = computed(() => (props.level === 'region' ? REGION_COLUMNS : RECORD_COLUMNS))

const status = computed(() => {
  const shown = props.response.hits.length
  const total = props.response.total_regions
  const regions = `${total.toLocaleString()} matching region${total === 1 ? '' : 's'}`
  if (shown === 0) return regions
  const first = (props.page - 1) * props.perPage + 1
  const last = first + shown - 1
  return props.level === 'region'
    ? `${first.toLocaleString()}–${last.toLocaleString()} of ${regions}`
    : `Records ${first.toLocaleString()}–${last.toLocaleString()} · ${regions}`
})

// Ascending, then descending, then back to relevance.
function cycleSort(field: string) {
  if (props.sort?.field !== field) emit('sort', { field, order: 'asc' })
  else if (props.sort.order === 'asc') emit('sort', { field, order: 'desc' })
  else emit('sort', null)
}

function sortMark(column: Column) {
  if (!column.sortField || props.sort?.field !== column.sortField) return '↕'
  return props.sort.order === 'asc' ? '▲' : '▼'
}

function ariaSort(column: Column) {
  if (!column.sortField || props.sort?.field !== column.sortField) return undefined
  return props.sort.order === 'asc' ? 'ascending' : 'descending'
}

function hitKey(hit: SearchHit) {
  if (props.level === 'region') {
    const fields = region(hit)
    return `${fields.output_file}:${fields.record}:${fields.region}`
  }
  return `${record(hit).output_file}:${record(hit).record}`
}

function isSelected(hit: SearchHit) {
  return props.selectedHit !== null && hitKey(hit) === hitKey(props.selectedHit)
}
</script>

<style scoped>
.results-table {
  display: flex;
  min-width: 0;
  flex-direction: column;
  border: 1px solid #dce3e8;
  border-radius: 6px;
  background: #fff;
}

.table-scroll {
  overflow-x: auto;
}

.table-scroll.loading {
  opacity: 0.55;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

th {
  position: sticky;
  top: 0;
  padding: 7px 8px;
  border-bottom: 1px solid #dce3e8;
  background: #f6f8f9;
  color: #40525e;
  font-weight: 700;
  text-align: left;
  white-space: nowrap;
}

.sort-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
}

.sort-mark {
  color: #8796a0;
  font-size: 10px;
}

td {
  max-width: 260px;
  padding: 6px 8px;
  overflow: hidden;
  border-bottom: 1px solid #edf2f5;
  color: #263442;
  text-overflow: ellipsis;
  white-space: nowrap;
}

td.region,
td.location {
  font-variant-numeric: tabular-nums;
}

td.file {
  color: #687681;
}

tbody tr {
  cursor: pointer;
}

tbody tr:hover,
tbody tr:focus-visible {
  background: #f3f7fa;
  outline: none;
}

tbody tr.selected {
  background: #e3f0fa;
}

td.empty {
  padding: 24px;
  color: #687681;
  cursor: default;
  text-align: center;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 7px 8px;
  border-top: 1px solid #dce3e8;
  font-size: 12px;
}

.pager-status {
  margin-right: auto;
  color: #52616d;
}

.pager button {
  height: 26px;
  padding: 0 10px;
  border: 1px solid #aebbc4;
  border-radius: 4px;
  background: #fff;
  color: #30434f;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
}

.pager button:disabled {
  color: #a3afb7;
  cursor: default;
}

.sort-button:focus-visible,
.pager button:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: 1px;
}
</style>
