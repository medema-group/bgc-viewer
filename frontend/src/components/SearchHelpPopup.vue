<template>
  <div class="modal-overlay" @click="$emit('close')">
    <section
      class="modal-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="search-help-title"
      @click.stop
    >
      <header class="modal-header">
        <div>
          <p class="eyebrow">Advanced search</p>
          <h2 id="search-help-title">Search reference</h2>
        </div>
        <button
          type="button"
          class="close-button"
          aria-label="Close search help"
          title="Close search help"
          @click="$emit('close')"
        >
          &times;
        </button>
      </header>

      <div class="modal-body">
        <p v-if="loading" class="status-message">Loading search reference...</p>
        <div v-else-if="error" class="error-message" role="alert">
          <strong>{{ error.code }}</strong>: {{ error.message }}
        </div>

        <template v-else-if="schema">
          <section class="help-section">
            <h3>Example queries</h3>
            <div v-if="schema.examples.length" class="example-list">
              <div v-for="example in schema.examples" :key="example" class="example-row">
                <code>{{ example }}</code>
                <button
                  type="button"
                  class="copy-button"
                  :aria-label="`Copy example: ${example}`"
                  @click="copyExample(example)"
                >
                  {{ copyLabel(example) }}
                </button>
              </div>
            </div>
            <p v-else class="empty-message">No examples are available for this dataset.</p>
          </section>

          <section class="help-section">
            <h3>Available fields</h3>
            <div class="field-list">
              <div v-for="field in schema.fields" :key="field.name" class="field-row">
                <div class="field-heading">
                  <code>{{ field.name }}</code>
                  <span class="kind-badge">{{ field.kind }}</span>
                  <span v-if="field.unqualified" class="unqualified-marker">
                    Included in unqualified search
                  </span>
                </div>
                <p>{{ field.description }}</p>
              </div>
            </div>
          </section>

          <section class="help-section syntax-section">
            <h3>Operators</h3>
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
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { SearchSchema } from '@/services/dataProviders/types'
import { copyText } from '@/utils/clipboard'

interface SearchError {
  code: string
  message: string
}

defineProps<{
  schema: SearchSchema | null
  loading: boolean
  error: SearchError | null
}>()

defineEmits<{
  (event: 'close'): void
}>()

const copyStatus = ref<{ example: string; copied: boolean } | null>(null)

async function copyExample(example: string) {
  copyStatus.value = { example, copied: await copyText(example) }
}

function copyLabel(example: string) {
  if (copyStatus.value?.example !== example) return 'Copy'
  return copyStatus.value.copied ? 'Copied' : 'Copy failed'
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(22, 31, 38, 0.58);
}

.modal-dialog {
  display: flex;
  width: min(720px, 100%);
  max-height: min(84vh, 760px);
  flex-direction: column;
  overflow: hidden;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 20px 55px rgba(22, 31, 38, 0.3);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 22px 16px;
  border-bottom: 1px solid #dce3e8;
}

.eyebrow {
  margin: 0 0 2px;
  color: #52616d;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.modal-header h2 {
  margin: 0;
  color: #263442;
  font-size: 20px;
  letter-spacing: 0;
}

.close-button {
  width: 34px;
  height: 34px;
  border: 0;
  background: transparent;
  color: #52616d;
  cursor: pointer;
  font-size: 26px;
  line-height: 1;
}

.close-button:hover {
  background: #edf2f5;
}

.modal-body {
  overflow-y: auto;
  padding: 4px 22px 22px;
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

.field-row p,
.syntax-section p {
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
  font-size: 13px;
  font-weight: 700;
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

.unqualified-marker {
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

.copy-button {
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
  .modal-overlay {
    padding: 12px;
  }

  .modal-dialog {
    max-height: 90vh;
  }

  .modal-header,
  .modal-body {
    padding-right: 16px;
    padding-left: 16px;
  }
}
</style>