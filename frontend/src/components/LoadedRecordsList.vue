<template>
  <div class="loaded-records">
    <p v-if="loading" class="loading-note">Loading...</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="table-scroll">
      <table v-if="level === 'region'">
        <thead>
          <tr>
            <th scope="col">Record</th>
            <th scope="col" class="number">Region</th>
            <th scope="col" class="number">Length (kb)</th>
            <th scope="col">Products</th>
            <th scope="col">Source</th>
            <th scope="col">File</th>
            <th scope="col"><span class="sr-only">Remove</span></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(region, index) in regions"
            :key="region.key"
            :class="{ selected: region.key === selectedKey }"
            tabindex="0"
            @click="emit('select-region', region)"
            @keydown.enter="emit('select-region', region)"
          >
            <td>{{ region.record.recordId }}</td>
            <td class="number">{{ region.regionNumber }}</td>
            <td class="number">{{ formatKilobases(region.length) }}</td>
            <td :title="region.product.join(', ')">{{ region.product.join(', ') }}</td>
            <td>{{ region.record.sourceLabel }}</td>
            <td class="muted" :title="region.record.filename">{{ region.record.filename }}</td>
            <td class="remove">
              <button
                v-if="startsSource(regionRecords, index)"
                type="button"
                :aria-label="`Remove ${region.record.sourceLabel} records`"
                :title="`Remove ${region.record.sourceLabel} records`"
                @click.stop="emit('remove-source', region.record.source)"
              >
                &times;
              </button>
            </td>
          </tr>
          <tr v-if="regions.length === 0 && !loading">
            <td colspan="7" class="empty">The loaded records have no regions.</td>
          </tr>
        </tbody>
      </table>
      <table v-else>
        <thead>
          <tr>
            <th scope="col">Record</th>
            <th scope="col">Source</th>
            <th scope="col">File</th>
            <th scope="col">Description</th>
            <th scope="col" class="number">Regions</th>
            <th scope="col" class="number">Features</th>
            <th scope="col"><span class="sr-only">Remove</span></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(record, index) in records"
            :key="record.key"
            :class="{ selected: record.key === selectedKey }"
            tabindex="0"
            @click="emit('select', record)"
            @keydown.enter="emit('select', record)"
          >
            <td>{{ record.recordId }}</td>
            <td>{{ record.sourceLabel }}</td>
            <td class="muted" :title="record.filename">{{ record.filename }}</td>
            <td :title="record.description">{{ record.description }}</td>
            <td class="number">{{ record.regionCount.toLocaleString() }}</td>
            <td class="number">{{ record.featureCount.toLocaleString() }}</td>
            <td class="remove">
              <button
                v-if="startsSource(records, index)"
                type="button"
                :aria-label="`Remove ${record.sourceLabel} records`"
                :title="`Remove ${record.sourceLabel} records`"
                @click.stop="emit('remove-source', record.source)"
              >
                &times;
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
// Records loaded from files or external databases, beside the index search, as a
// list of records or of their regions. Uploaded files are removed in the load
// dialog, where they were added.
import { computed } from 'vue'
import type { SearchLevel } from '@/services/dataProviders/types'
import { UPLOAD_SOURCE, type LoadedRecord, type LoadedRegion } from '@/composables/useLoadedRecords'
import { formatKilobases } from '@/utils/format'

const props = withDefaults(defineProps<{
  records: LoadedRecord[]
  regions?: LoadedRegion[]
  level?: SearchLevel
  /** Key of the selected record, or of the selected region. */
  selectedKey?: string | null
  loading?: boolean
  error?: string | null
}>(), {
  regions: () => [],
  level: 'record',
  selectedKey: null,
  loading: false,
  error: null
})

const emit = defineEmits<{
  (event: 'select', record: LoadedRecord): void
  (event: 'select-region', region: LoadedRegion): void
  (event: 'remove-source', source: string): void
}>()

const regionRecords = computed(() => props.regions.map(region => region.record))

/** Whether the row at `index` is the first of a downloaded source, which carries its remove button. */
function startsSource(rows: LoadedRecord[], index: number) {
  const { source } = rows[index]
  return source !== UPLOAD_SOURCE && rows.findIndex(row => row.source === source) === index
}
</script>

<style scoped>
.loaded-records {
  border: 1px solid #dce3e8;
  border-radius: 6px;
}

.loading-note {
  margin: 0;
  padding: 7px 8px;
  color: #687681;
  font-size: 12px;
}

.error {
  margin: 0;
  padding: 9px 8px;
  background: #fff3f2;
  color: #a1261d;
  font-size: 12px;
}

.table-scroll {
  max-height: 420px;
  overflow: auto;
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

td {
  max-width: 280px;
  padding: 6px 8px;
  overflow: hidden;
  border-bottom: 1px solid #edf2f5;
  color: #263442;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* As in the search results: narrow, right-aligned number columns. */
.number {
  width: 1%;
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.muted {
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

td.remove {
  width: 30px;
  padding: 0 4px;
}

td.empty {
  padding: 24px;
  color: #687681;
  cursor: default;
  text-align: center;
}

td.remove button {
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: #687681;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
}

td.remove button:hover {
  background: #fff3f2;
  color: #a1261d;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}
</style>
