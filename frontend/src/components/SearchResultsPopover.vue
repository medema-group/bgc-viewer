<template>
  <section class="search-results" aria-label="Search results">
    <header class="results-header">
      <div class="results-heading">
        <p class="results-count">{{ response.total }} {{ resultLabel }}</p>
        <h2>{{ query }}</h2>
      </div>
    </header>

    <div class="results-body" :class="{ loading }" aria-live="polite">
      <p v-if="loading" class="loading-message">Updating results...</p>
      <p v-if="response.hits.length === 0" class="empty-message">No results found.</p>

      <button
        v-for="hit in response.hits"
        :key="hitKey(hit)"
        type="button"
        :class="['result-row', { selected: isSelected(hit) }]"
        @click="$emit('search-selected', hit)"
      >
        <template v-if="level === 'protocluster'">
          <strong class="primary-text">{{ protoclusterFields(hit).organism || protoclusterFields(hit).record }}</strong>
          <span class="product-line">
            {{ protoclusterFields(hit).product }}
            <span v-if="protoclusterFields(hit).category" class="category">
              {{ protoclusterFields(hit).category }}
            </span>
          </span>
          <span class="location-line">
            Region {{ protoclusterFields(hit).region }} · Protocluster {{ protoclusterFields(hit).protocluster }}
          </span>
          <span class="coordinate-line">{{ formatCoordinates(hit) }}</span>
          <span class="file-line">{{ fileContext(hit) }}</span>
        </template>

        <template v-else-if="level === 'region'">
          <strong class="primary-text">{{ groupedHit(hit).record }}</strong>
          <span class="location-line">Region {{ regionNumber(hit) }}</span>
          <span class="file-line">{{ fileContext(hit) }}</span>
        </template>

        <template v-else>
          <strong class="primary-text">{{ groupedHit(hit).record }}</strong>
          <span class="file-line">{{ fileContext(hit) }}</span>
        </template>

        <span class="score">Score {{ hit.score.toFixed(3) }}</span>
      </button>
    </div>

    <footer v-if="totalPages > 1" class="pagination">
      <button
        type="button"
        aria-label="Previous search results page"
        :disabled="page <= 1 || loading"
        @click="$emit('page-change', page - 1)"
      >
        &lsaquo;
      </button>
      <span>Page {{ page }} of {{ totalPages }}</span>
      <button
        type="button"
        aria-label="Next search results page"
        :disabled="page >= totalPages || loading"
        @click="$emit('page-change', page + 1)"
      >
        &rsaquo;
      </button>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type {
  ProtoclusterSearchHit,
  RecordSearchHit,
  RegionSearchHit,
  SearchLevel,
  SearchResponse
} from '@/services/dataProviders/types'

type SearchHit = ProtoclusterSearchHit | RegionSearchHit | RecordSearchHit

const props = withDefaults(defineProps<{
  query: string
  level: SearchLevel
  response: SearchResponse<SearchHit>
  page: number
  selectedHit: SearchHit | null
  loading?: boolean
  perPage?: number
}>(), {
  loading: false,
  perPage: 20
})

defineEmits<{
  (event: 'page-change', page: number): void
  (event: 'search-selected', hit: SearchHit): void
}>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.response.total / props.perPage)))
const resultLabel = computed(() => `${props.level} result${props.response.total === 1 ? '' : 's'}`)

function protoclusterFields(hit: SearchHit) {
  return (hit as ProtoclusterSearchHit).fields
}

function groupedHit(hit: SearchHit) {
  return hit as RegionSearchHit | RecordSearchHit
}

function regionNumber(hit: SearchHit) {
  return (hit as RegionSearchHit).region
}

function outputFile(hit: SearchHit) {
  return props.level === 'protocluster'
    ? protoclusterFields(hit).output_file
    : groupedHit(hit).output_file
}

function inputFile(hit: SearchHit) {
  return props.level === 'protocluster'
    ? protoclusterFields(hit).input_file
    : groupedHit(hit).input_file
}

function fileContext(hit: SearchHit) {
  const input = inputFile(hit)
  return input ? `${outputFile(hit)} · ${input}` : outputFile(hit)
}

function formatCoordinates(hit: SearchHit) {
  const { start, end } = protoclusterFields(hit)
  return start === null || end === null ? 'Coordinates unavailable' : `${start}–${end}`
}

function hitKey(hit: SearchHit) {
  if (props.level === 'protocluster') {
    const fields = protoclusterFields(hit)
    return `${fields.output_file}:${fields.record}:${fields.region}:${fields.protocluster}`
  }
  const grouped = groupedHit(hit)
  return props.level === 'region'
    ? `${grouped.output_file}:${grouped.record}:${regionNumber(hit)}`
    : `${grouped.output_file}:${grouped.record}`
}

function isSelected(hit: SearchHit) {
  return props.selectedHit !== null && hitKey(hit) === hitKey(props.selectedHit)
}
</script>

<style scoped>
.search-results {
  display: flex;
  min-height: 100%;
  flex-direction: column;
  background: #fff;
}

.results-header {
  display: flex;
  flex: 0 0 auto;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid #dce3e8;
}

.results-heading {
  min-width: 0;
}

.results-count {
  margin: 0 0 2px;
  color: #52616d;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.results-header h2 {
  overflow: hidden;
  margin: 0;
  color: #263442;
  font-family: 'IBM Plex Mono', 'Liberation Mono', monospace;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.results-body {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.results-body.loading::after {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.38);
  content: '';
  pointer-events: none;
}

.loading-message,
.empty-message {
  margin: 0;
  padding: 18px 16px;
  color: #687681;
  font-size: 13px;
}

.loading-message {
  padding-block: 7px;
  background: #eef4f6;
  color: #344955;
}

.result-row {
  position: relative;
  display: flex;
  width: 100%;
  min-height: 112px;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 13px 16px;
  border: 0;
  border-bottom: 1px solid #e5eaee;
  background: #fff;
  color: #263442;
  cursor: pointer;
  font: inherit;
  text-align: left;
}

.result-row:hover {
  background: #f4f8fa;
}

.result-row.selected {
  background: #e8f2f8;
  box-shadow: inset 3px 0 #1976d2;
}

.primary-text,
.product-line,
.location-line,
.coordinate-line,
.file-line {
  max-width: 100%;
  overflow-wrap: anywhere;
}

.primary-text {
  color: #173f5f;
  font-size: 14px;
}

.product-line,
.location-line,
.coordinate-line,
.file-line,
.score {
  font-size: 12px;
}

.category {
  margin-left: 5px;
  padding: 2px 5px;
  border-radius: 3px;
  background: #e7f0ea;
  color: #28633f;
  font-size: 10px;
  font-weight: 700;
}

.location-line,
.coordinate-line,
.file-line {
  color: #52616d;
}

.score {
  position: absolute;
  right: 16px;
  bottom: 12px;
  color: #687681;
  font-variant-numeric: tabular-nums;
}

.pagination {
  display: grid;
  grid-template-columns: 34px 1fr 34px;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-top: 1px solid #dce3e8;
  color: #52616d;
  font-size: 12px;
  text-align: center;
}

.pagination button {
  width: 34px;
  height: 30px;
  border: 1px solid #b8c2cc;
  border-radius: 4px;
  background: #fff;
  color: #263442;
  cursor: pointer;
  font-size: 20px;
  line-height: 1;
}

.pagination button:disabled {
  cursor: default;
  opacity: 0.45;
}

</style>