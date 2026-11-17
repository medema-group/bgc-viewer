<template>
  <AppDialog :open="open" title="Load data" @close="emit('close')">
    <nav class="source-tabs" aria-label="Data sources">
      <button
        v-for="tab in tabs"
        :key="tab.source"
        type="button"
        :class="{ active: active === tab.source }"
        :aria-current="active === tab.source ? 'page' : undefined"
        @click="active = tab.source"
      >
        {{ tab.label }}
      </button>
    </nav>

    <!-- Every loader stays mounted: uploads restore from browser storage and
         accessions in the URL load on startup, before the dialog is opened. -->
    <div v-show="active === UPLOAD_SOURCE" class="source-pane">
      <FileUpload @files-loaded="emit('loaded', UPLOAD_SOURCE, $event)" />
    </div>
    <div v-for="(_, source) in EXTERNAL_SOURCES" v-show="active === source" :key="source" class="source-pane">
      <AccessionLoader
        :source="source"
        :initial-accession="initialAccessions[source] ?? ''"
        @files-loaded="emit('loaded', source, $event)"
      />
    </div>
  </AppDialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AccessionLoader from './AccessionLoader.vue'
import AppDialog from './AppDialog.vue'
import FileUpload from './FileUpload.vue'
import { UPLOAD_SOURCE, sourceLabel, type LoadedFile } from '@/composables/useLoadedRecords'
import { EXTERNAL_SOURCES } from '@/services/externalSources'

withDefaults(defineProps<{
  open: boolean
  /** Accession per external source to load on startup, as from the page URL. */
  initialAccessions?: Record<string, string>
}>(), {
  initialAccessions: () => ({})
})

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'loaded', source: string, files: LoadedFile[]): void
}>()

const tabs = [
  { source: UPLOAD_SOURCE, label: 'Upload files' },
  ...Object.keys(EXTERNAL_SOURCES).map(source => ({ source, label: sourceLabel(source) }))
]

const active = ref(UPLOAD_SOURCE)
</script>

<style scoped>
.source-tabs {
  display: flex;
  gap: 20px;
  padding: 0 18px;
  border-bottom: 1px solid #dce3e8;
}

.source-tabs button {
  padding: 10px 1px 9px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: #5b6973;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
}

.source-tabs button.active {
  border-bottom-color: #1976b5;
  color: #145f92;
}

.source-tabs button:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: 1px;
}

.source-pane {
  padding: 4px 6px 10px;
}
</style>
