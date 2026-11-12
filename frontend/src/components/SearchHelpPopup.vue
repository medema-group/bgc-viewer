<template>
  <section class="help-panel" aria-labelledby="search-help-title">
      <div class="help-body">
        <h2 id="search-help-title" class="sr-only">Search reference</h2>
        <p v-if="loading" class="status-message">Loading search reference...</p>
        <div v-else-if="error" class="error-message" role="alert">
          <strong>{{ error.code }}</strong>: {{ error.message }}
        </div>

        <template v-else-if="schema">
          <section class="help-section guide-section">
            <h3>Query builder</h3>
            <p>
              Each row compares one field to a value. Rows after the first start
              with <strong>AND</strong> or <strong>OR</strong>, and AND binds before
              OR: <em>a AND b OR c</em> means <em>(a AND b) OR c</em>. Add a group
              for other brackets. Without conditions, Browse all lists every region.
            </p>
            <ul>
              <li>
                <strong>is</strong> and <strong>is any of</strong> match whole values
                exactly, including case; pick them from the suggestions, which show
                how many regions hold each value. <strong>contains</strong>,
                <strong>starts with</strong>, and <strong>ends with</strong> ignore case.
              </li>
              <li>
                <strong>Any text contains</strong> finds each word inside any text
                value of a region.
              </li>
              <li>
                <strong>Query string</strong> (under General) puts a query in the
                syntax below among the rows.
              </li>
              <li>
                Click a value under <strong>Refine</strong> to add it as a condition.
              </li>
            </ul>
          </section>

          <section class="help-section">
            <h3>Example queries</h3>
            <div v-if="schema.examples.length" class="example-list">
              <div v-for="example in schema.examples" :key="example" class="example-row">
                <code>{{ example }}</code>
                <button
                  type="button"
                  class="example-button"
                  :aria-label="`Use example: ${example}`"
                  @click="$emit('use-example', example)"
                >
                  Use
                </button>
              </div>
            </div>
            <p v-else class="empty-message">No examples are available for this dataset.</p>
          </section>

          <section class="help-section">
            <h3>Available fields</h3>
            <div v-for="[group, fields] in fieldGroups" :key="group" class="field-group">
              <h4>{{ group }}</h4>
              <div class="field-list">
                <div v-for="field in fields" :key="field.name" class="field-row">
                  <div class="field-heading">
                    <span class="field-label">{{ field.label }}</span>
                    <code>{{ field.name }}</code>
                    <span class="kind-badge">{{ field.kind }}</span>
                    <span v-if="field.default_search" class="default-search-marker">
                      Searched by a bare term
                    </span>
                  </div>
                  <p>{{ field.description }}</p>
                </div>
              </div>
            </div>
          </section>

          <section class="help-section syntax-section">
            <h3>Query string syntax</h3>
            <p>
              Name a field as <code>field:value</code>, using the names above.
            </p>
            <p>
              Whitespace implies <code>OR</code>. Combine clauses with
              <code>AND</code>, <code>OR</code>, <code>NOT</code>, and parentheses.
              Use quotes for phrases, <code>"a b"~N</code> for phrase slop, and
              <code>"a b"*</code> for phrase prefix. A trailing <code>*</code> on
              an unquoted term is inert.
            </p>
            <a :href="schema.query_syntax_url" target="_blank" rel="noopener noreferrer">
              Open the Tantivy query grammar
            </a>
          </section>
        </template>
      </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SearchFieldInfo, SearchSchema } from '@/services/dataProviders/types'

interface SearchError {
  code: string
  message: string
}

const props = defineProps<{
  schema: SearchSchema | null
  loading: boolean
  error: SearchError | null
}>()

// Fields by group, in registry order, as the builder's field picker groups them.
const fieldGroups = computed(() => {
  const groups = new Map<string, SearchFieldInfo[]>()
  for (const field of props.schema?.fields ?? []) {
    groups.set(field.group, [...(groups.get(field.group) ?? []), field])
  }
  return [...groups]
})

defineEmits<{
  (event: 'use-example', example: string): void
}>()
</script>

<style scoped>
.help-body {
  padding: 4px 22px 22px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}

.help-section {
  padding-top: 18px;
}

.help-section + .help-section {
  margin-top: 18px;
  border-top: 1px solid #e5eaee;
}

.help-section h3 {
  margin: 0 0 10px;
  color: #263442;
  font-size: 15px;
  letter-spacing: 0;
}

.field-list,
.example-list {
  display: grid;
  gap: 7px;
}

.field-row {
  padding: 9px 0;
  border-bottom: 1px solid #edf0f2;
}

.field-row:last-child {
  border-bottom: 0;
}

.field-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
}

.field-group + .field-group {
  margin-top: 14px;
}

.field-group h4 {
  margin: 0 0 4px;
  color: #40525e;
  font-size: 13px;
}

.field-label {
  color: #263442;
  font-size: 13px;
  font-weight: 700;
}

.guide-section ul {
  margin: 8px 0 0;
  padding-left: 18px;
}

.guide-section li + li {
  margin-top: 4px;
}

.field-row p,
.syntax-section p,
.guide-section p,
.guide-section li {
  margin: 5px 0 0;
  color: #52616d;
  font-size: 13px;
  line-height: 1.5;
}

code {
  font-family: 'IBM Plex Mono', 'Liberation Mono', monospace;
}

.field-heading code {
  color: #173f5f;
  font-size: 12px;
}

.kind-badge {
  padding: 2px 6px;
  border: 1px solid #c8d5dc;
  border-radius: 3px;
  background: #eef4f6;
  color: #344955;
  font-size: 10px;
  font-weight: 700;
}

.default-search-marker {
  color: #24704b;
  font-size: 11px;
  font-weight: 600;
}

.example-row {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border-left: 3px solid #1976d2;
  background: #f4f7f9;
}

.example-row code {
  overflow-wrap: anywhere;
  color: #263442;
  font-size: 12px;
}

.example-button {
  flex: 0 0 auto;
  min-width: 68px;
  border: 0;
  background: transparent;
  color: #1565c0;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
}

.syntax-section a {
  display: inline-block;
  margin-top: 10px;
  color: #1565c0;
  font-size: 13px;
  font-weight: 600;
}

.status-message,
.error-message,
.empty-message {
  margin: 18px 0 0;
  font-size: 13px;
}

.error-message {
  color: #b42318;
}

.empty-message {
  color: #687681;
}

@media (max-width: 600px) {
  .help-body {
    padding-right: 16px;
    padding-left: 16px;
  }
}
</style>