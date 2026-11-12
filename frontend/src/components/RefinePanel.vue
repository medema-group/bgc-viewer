<template>
  <aside class="refine-panel" aria-label="Refine results">
    <h3>Refine</h3>
    <p v-if="entries.length === 0" class="refine-note">No values to refine by.</p>
    <section v-for="[field, buckets] in entries" :key="field" class="facet">
      <h4>{{ labels.get(field) ?? field }}</h4>
      <ul>
        <li v-for="bucket in buckets.slice(0, limit)" :key="bucket.value">
          <button
            type="button"
            :title="`Add filter: ${labels.get(field) ?? field} is ${bucket.value}`"
            @click="emit('add', field, bucket.value)"
          >
            <span class="facet-value">{{ bucket.value }}</span>
            <span class="facet-count">{{ bucket.count.toLocaleString() }}</span>
          </button>
        </li>
      </ul>
    </section>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FacetBucket } from '@/services/dataProviders/types'

const props = withDefaults(defineProps<{
  facets: Record<string, FacetBucket[]>
  /** Display label of each facet field. */
  labels: Map<string, string>
  /** Values shown per field. */
  limit?: number
}>(), {
  limit: 8
})

const emit = defineEmits<{
  (event: 'add', field: string, value: string): void
}>()

const entries = computed(() => Object.entries(props.facets).filter(([, buckets]) => buckets.length > 0))
</script>

<style scoped>
.refine-panel {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 10px;
}

h3 {
  margin: 0;
  color: #30434f;
  font-size: 13px;
}

h4 {
  margin: 0 0 4px;
  color: #40525e;
  font-size: 12px;
}

.refine-note {
  margin: 0;
  color: #687681;
  font-size: 12px;
}

.facet {
  padding: 8px;
  border: 1px solid #dce3e8;
  border-radius: 6px;
}

ul {
  margin: 0;
  padding: 0;
  list-style: none;
}

li button {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 2px 4px;
  border: 0;
  border-radius: 3px;
  background: transparent;
  color: #263442;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  text-align: left;
}

li button:hover,
li button:focus-visible {
  background: #edf2f5;
  outline: none;
}

.facet-value {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.facet-count {
  flex-shrink: 0;
  color: #687681;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}
</style>
