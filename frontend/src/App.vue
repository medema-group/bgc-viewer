<template>
  <div class="app-container">
    <!-- Header spanning full width -->
    <header class="app-header">
      <h1>BGC Viewer</h1>
      <div class="header-actions">
        <button
          v-if="!isPublicMode"
          type="button"
          class="header-button"
          :title="selectedIndexPath || 'No index open'"
          @click="indexDialogOpen = true"
        >
          Index<span v-if="indexName" class="header-button-detail">{{ indexName }}</span>
        </button>
        <button type="button" class="header-button" @click="loadDialogOpen = true">
          Load data
        </button>
      </div>
      <div class="header-tools">
        <div class="version-info">
          <span v-if="appVersion">{{ appName }} v{{ appVersion }}</span>
          <span v-else>Loading version...</span>
        </div>
        <nav class="header-links">
          •<a href="https://medema-group.github.io/bgc-viewer/" target="_blank" rel="noopener noreferrer">Docs</a>
          •<a href="https://research-software-directory.org/projects/big-views" target="_blank" rel="noopener noreferrer">Project</a>
          •<a href="https://github.com/medema-group/bgc-viewer" target="_blank" rel="noopener noreferrer">GitHub</a>
        </nav>
      </div>
    </header>

    <!-- Main flow: search the index, pick a result or a loaded record, view it -->
    <main class="main-content">
      <SearchPanel
        :search="advancedSearch"
        :can-choose-index="!isPublicMode"
        @open-index="indexDialogOpen = true"
        @searched="resultsTab = 'search'"
      />

      <ResultsPanel
        v-if="showResults"
        v-model:tab="resultsTab"
        :search="advancedSearch"
        :loaded-records="loadedRecords.records.value"
        :selected-loaded-key="selectedLoadedKey"
        :loaded-loading="loadedRecords.loading.value"
        :loaded-error="loadedRecords.error.value"
        @select-hit="handleSearchSelected"
        @select-loaded="handleLoadedSelected"
        @remove-source="handleRemoveSource"
      />

      <section ref="viewerRef" class="viewer-section" aria-label="Record viewer">
        <RegionViewerContainer
          v-if="viewerProvider && currentRecordId"
          :key="viewerKey"
          :data-provider="viewerProvider"
          :record-id="currentRecordId"
          :record-data="currentRecordData"
          :initial-region-id="initialRegionId"
          @region-changed="handleRegionChanged"
          @annotation-clicked="handleAnnotationClicked"
          @error="handleViewerError"
        />
        <div v-else class="placeholder">
          <p>Select a search result or a loaded record to view it here</p>
        </div>
      </section>
    </main>

    <AppDialog
      v-if="!isPublicMode"
      :open="indexDialogOpen"
      title="Index"
      @close="indexDialogOpen = false"
    >
      <!-- Index selection stays mounted, as it reopens the last used index on startup -->
      <IndexSelection
        v-show="!folderForIndexing"
        :index-path="selectedIndexPath"
        @index-changed="handleIndexChanged"
        @create-index-for-folder="handleCreateIndexForFolder"
      />
      <IndexCreation
        v-if="folderForIndexing"
        :folder-path="folderForIndexing"
        :index-path="indexPathForCreation"
        :available-files="availableFiles"
        :is-loading-files="isLoadingFiles"
        :needs-preprocessing="needsPreprocessing"
        @preprocessing-completed="handlePreprocessingCompleted"
        @folder-changed="handleFolderForIndexingChanged"
        @cancel="handleCancelIndexCreation"
      />
    </AppDialog>

    <LoadDataDialog
      :open="loadDialogOpen"
      :initial-accessions="urlAccessions"
      @loaded="handleLoaded"
      @close="loadDialogOpen = false"
    />
  </div>
</template>

<script>
import { computed, markRaw, nextTick, onMounted, ref } from 'vue'
import axios from 'axios'
import AppDialog from './components/AppDialog.vue'
import IndexCreation from './components/IndexCreation.vue'
import IndexSelection from './components/IndexSelection.vue'
import LoadDataDialog from './components/LoadDataDialog.vue'
import RegionViewerContainer from './components/RegionViewerContainer.vue'
import ResultsPanel from './components/ResultsPanel.vue'
import SearchPanel from './components/SearchPanel.vue'
import { EXTERNAL_SOURCES } from './services/externalSources'
import { BGCViewerAPIProvider } from '@/services/dataProviders'
import {
  recordSelectionFromHit,
  regionIdFromHit
} from '@/services/searchNavigation'
import { useAdvancedSearch } from '@/composables/useAdvancedSearch'
import { UPLOAD_SOURCE, useLoadedRecords } from '@/composables/useLoadedRecords'

// The viewer is remounted per provider, so a record never loads through the previous one.
const providerKeys = new WeakMap()
let providerCounter = 0
const providerKey = (provider) => {
  if (!providerKeys.has(provider)) providerKeys.set(provider, `provider-${++providerCounter}`)
  return providerKeys.get(provider)
}

export default {
  name: 'App',
  components: {
    AppDialog,
    IndexCreation,
    IndexSelection,
    LoadDataDialog,
    RegionViewerContainer,
    ResultsPanel,
    SearchPanel
  },
  setup() {
    const viewerRef = ref(null)

    // Version information
    const appVersion = ref('')
    const appName = ref('BGC Viewer')

    // Mode information
    const isPublicMode = ref(true) // Default to true for safety

    // Accessions in the URL (e.g. ?antismash_db=GCF_000725555.1 or ?mibig=BGC0002204.3)
    // are loaded on startup
    const urlParams = new URLSearchParams(window.location.search)
    const urlAccessions = Object.fromEntries(
      Object.entries(EXTERNAL_SOURCES)
        .map(([id, source]) => [id, urlParams.get(source.urlParam) || ''])
        .filter(([, accession]) => accession)
    )

    // Index selection and creation, in the index dialog
    const indexDialogOpen = ref(false)
    const selectedIndexPath = ref('')
    const folderForIndexing = ref('')
    const indexPathForCreation = ref('')
    const availableFiles = ref([])
    const isLoadingFiles = ref(false)
    const needsPreprocessing = ref(false)
    const indexName = computed(() => selectedIndexPath.value.split(/[\\/]/).pop() || '')

    // The backend index is searched; loaded files and accessions sit beside it
    const apiProvider = markRaw(new BGCViewerAPIProvider())
    const advancedSearch = useAdvancedSearch(() => apiProvider)
    const loadedRecords = useLoadedRecords()
    const loadDialogOpen = ref(false)
    const selectedLoadedKey = ref(null)

    // Search results and loaded records share one panel as tabs
    const resultsTab = ref('search')
    const showResults = computed(() => Boolean(
      advancedSearch.state.response || advancedSearch.state.loading
      || loadedRecords.records.value.length || loadedRecords.loading.value || loadedRecords.error.value
    ))

    // The viewed record and the provider it comes from
    const viewerProvider = ref(null)
    const viewerKey = ref('')
    const currentRecordId = ref('')
    const currentRecordData = ref(null)
    const initialRegionId = ref('')

    const clearViewer = () => {
      viewerProvider.value = null
      viewerKey.value = ''
      currentRecordId.value = ''
      currentRecordData.value = null
      initialRegionId.value = ''
      selectedLoadedKey.value = null
    }

    const showRecord = async (provider, recordData, regionId = '') => {
      viewerProvider.value = provider
      viewerKey.value = providerKey(provider)
      currentRecordData.value = {
        entryId: recordData.entryId,
        recordId: recordData.recordId,
        filename: recordData.filename
      }
      // Use entryId (which includes the filename) for uniqueness, not recordId
      currentRecordId.value = recordData.entryId
      initialRegionId.value = regionId

      // Bring the viewer up when it starts below the middle of the screen
      await nextTick()
      const viewer = viewerRef.value
      if (viewer && viewer.getBoundingClientRect().top > window.innerHeight / 2) {
        viewer.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
      }
    }

    const handleSearchSelected = async (hit) => {
      const level = advancedSearch.state.searchedLevel
      advancedSearch.state.selectedHit = hit
      selectedLoadedKey.value = null
      await showRecord(apiProvider, recordSelectionFromHit(level, hit), regionIdFromHit(level, hit))
    }

    const handleLoadedSelected = async (record) => {
      advancedSearch.state.selectedHit = null
      selectedLoadedKey.value = record.key
      await showRecord(record.provider, record)
    }

    // Clear the viewer when the record it shows is no longer loaded
    const dropViewerIfUnloaded = () => {
      const provider = viewerProvider.value
      if (provider && provider !== apiProvider
          && !loadedRecords.records.value.some(record => record.provider === provider)) {
        clearViewer()
      }
    }

    const handleLoaded = async (source, files) => {
      // Uploads restored from browser storage on startup arrive with the dialog closed;
      // they should not take the place of the search results
      const asked = loadDialogOpen.value || source !== UPLOAD_SOURCE
      const records = await loadedRecords.setFiles(source, files)
      dropViewerIfUnloaded()
      if (asked && records.length > 0) resultsTab.value = 'loaded'
      // An entry fetched from a database is shown right away; uploads may still grow
      if (source !== UPLOAD_SOURCE && records.length > 0) {
        loadDialogOpen.value = false
        await handleLoadedSelected(records[0])
      }
    }

    const handleRemoveSource = (source) => {
      loadedRecords.removeSource(source)
      dropViewerIfUnloaded()
      // Its accession should not load again with the page
      const url = new URL(window.location.href)
      const param = EXTERNAL_SOURCES[source]?.urlParam
      if (param && url.searchParams.has(param)) {
        url.searchParams.delete(param)
        window.history.replaceState(null, '', url)
      }
    }

    const openIndex = async (indexPath) => {
      if (indexPath) {
        try {
          await axios.post('/api/select-database', { path: indexPath })
        } catch (err) {
          console.warn('Failed to set database path:', err.response?.data?.error || err.message)
        }
      }
      if (viewerProvider.value === apiProvider) clearViewer()
      await advancedSearch.openIndex()
    }

    const handleIndexChanged = async (indexPath) => {
      selectedIndexPath.value = indexPath
      indexDialogOpen.value = false
      await openIndex(indexPath)
    }

    const resetIndexCreation = () => {
      folderForIndexing.value = ''
      indexPathForCreation.value = ''
      availableFiles.value = []
      isLoadingFiles.value = false
      needsPreprocessing.value = false
    }

    const handleCreateIndexForFolder = ({ folderPath, indexPath, files }) => {
      folderForIndexing.value = folderPath
      indexPathForCreation.value = indexPath || ''
      availableFiles.value = files.availableFiles || []
      isLoadingFiles.value = files.isLoadingFiles || false
      needsPreprocessing.value = files.needsPreprocessing || false
    }

    const handleFolderForIndexingChanged = (newFolderPath) => {
      folderForIndexing.value = newFolderPath
    }

    const handlePreprocessingCompleted = async (indexPath) => {
      resetIndexCreation()
      await handleIndexChanged(indexPath)
    }

    const handleCancelIndexCreation = () => {
      resetIndexCreation()
    }

    const handleRegionChanged = (regionId) => {
      console.log('Region changed to:', regionId)
    }

    const handleAnnotationClicked = (data) => {
      console.log('Annotation clicked:', data)
    }

    const handleViewerError = (error) => {
      console.error('Viewer error:', error)
    }

    const fetchVersion = async () => {
      try {
        const response = await axios.get('/api/version')
        appVersion.value = response.data.version
        appName.value = response.data.name
      } catch (error) {
        console.warn('Failed to fetch version:', error)
      }
    }

    const fetchStatus = async () => {
      try {
        const response = await axios.get('/api/status')
        isPublicMode.value = response.data.public_mode
        console.log('Running in', isPublicMode.value ? 'PUBLIC' : 'LOCAL', 'mode')
      } catch (error) {
        console.warn('Failed to fetch status:', error)
        // Default to public mode for safety if fetch fails
        isPublicMode.value = true
      }
    }

    onMounted(async () => {
      fetchVersion()
      await fetchStatus()
      // Public mode serves one fixed index; in local mode the index dialog opens
      // the last used index and reports it through handleIndexChanged
      if (isPublicMode.value) await openIndex('')
    })

    return {
      viewerRef,
      appVersion,
      appName,
      isPublicMode,
      urlAccessions,
      indexDialogOpen,
      selectedIndexPath,
      indexName,
      folderForIndexing,
      indexPathForCreation,
      availableFiles,
      isLoadingFiles,
      needsPreprocessing,
      advancedSearch,
      loadedRecords,
      loadDialogOpen,
      selectedLoadedKey,
      resultsTab,
      showResults,
      viewerProvider,
      viewerKey,
      currentRecordId,
      currentRecordData,
      initialRegionId,
      handleSearchSelected,
      handleLoadedSelected,
      handleLoaded,
      handleRemoveSource,
      handleIndexChanged,
      handleCreateIndexForFolder,
      handleFolderForIndexingChanged,
      handlePreprocessingCompleted,
      handleCancelIndexCreation,
      handleRegionChanged,
      handleAnnotationClicked,
      handleViewerError
    }
  }
}
</script>

<style>
/* Global font styling */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body,
html,
#app {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  line-height: 1.6;
  color: #333;
  background-color: #f4f4f4;
  height: 100%;
  overflow: hidden;
}

/* App container - fills viewport */
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

/* Header spanning full width */
.app-header {
  background: white;
  border-bottom: 2px solid #e0e0e0;
  padding: 12px 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.08);
  display: flex;
  align-items: center;
  gap: 20px;
  flex-shrink: 0;
  z-index: 10;
}

.app-header h1 {
  color: #2c3e50;
  margin: 0;
  font-size: 24px;
}

.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.header-button {
  display: inline-flex;
  max-width: 320px;
  height: 34px;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
  border: 1px solid #aebbc4;
  border-radius: 4px;
  background: #fff;
  color: #30434f;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
}

.header-button:hover {
  background: #edf2f5;
}

.header-button:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: 1px;
}

.header-button-detail {
  overflow: hidden;
  color: #687681;
  font-weight: 400;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-tools {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  min-width: 0;
  margin-left: auto;
}

.app-header .version-info {
  color: #666;
  font-size: 0.85rem;
  font-weight: 500;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .app-header {
    flex-wrap: wrap;
    gap: 10px;
  }

  .header-tools {
    width: 100%;
    justify-content: flex-start;
    margin-left: 0;
  }
}

.header-links {
  color: #777;
  display: flex;
  gap: 5px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.header-links a {
  color: #1976d2;
  text-decoration: none;
  font-size: 0.9rem;
  font-weight: 500;
  transition: color 0.2s;
}

.header-links a:hover {
  color: #1565c0;
  text-decoration: underline;
}

/* Main content: one scrolling column of search, loaded records, and viewer */
.main-content {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
  padding: 16px 20px 24px;
  overflow-y: auto;
  background-color: #f4f4f4;
}

/* The viewer keeps a screen-sized box of its own, as it had beside the sidebar */
.viewer-section {
  flex-shrink: 0;
  height: calc(100vh - 110px);
  min-height: 480px;
  overflow-y: auto;
  padding: 15px;
  border: 1px solid #dce3e8;
  border-radius: 8px;
  background: #f8f9fa;
}

.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #666;
  font-style: italic;
}

.main-content::-webkit-scrollbar,
.viewer-section::-webkit-scrollbar {
  width: 10px;
}

.main-content::-webkit-scrollbar-track,
.viewer-section::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.main-content::-webkit-scrollbar-thumb,
.viewer-section::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 5px;
}

.main-content::-webkit-scrollbar-thumb:hover,
.viewer-section::-webkit-scrollbar-thumb:hover {
  background: #555;
}
</style>
