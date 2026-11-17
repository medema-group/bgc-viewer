<template>
  <div class="loaded-records">
    <p v-if="loading" class="loading-note">Loading...</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="table-scroll">
      <table>
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
            v-for="record in records"
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
                v-if="record.source !== UPLOAD_SOURCE && isFirstOfSource(record)"
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
// Records loaded from files or external databases, beside the index search.
// Uploaded files are removed in the load dialog, where they were added.
import { UPLOAD_SOURCE, type LoadedRecord } from '@/composables/useLoadedRecords'

const props = withDefaults(defineProps<{
  records: LoadedRecord[]
  selectedKey?: string | null
  loading?: boolean
  error?: string | null
}>(), {
  selectedKey: null,
  loading: false,
  error: null
})

const emit = defineEmits<{
  (event: 'select', record: LoadedRecord): void
  (event: 'remove-source', source: string): void
}>()

function isFirstOfSource(record: LoadedRecord) {
  return props.records.find(candidate => candidate.source === record.source) === record
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

.number {
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
