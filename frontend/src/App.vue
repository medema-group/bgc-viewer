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

    <!-- Main flow: search windows and loaded data beside the one viewer. The focused
         window, or the viewer, is shown at normal size. Every window has a compact card,
         the focused one's too, so the cards keep their places. -->
    <main class="main-content">
      <div
        class="workspace"
        :class="{ 'has-focus': !viewerFocused }"
        :style="workspaceStyle"
        aria-label="Windows"
      >
        <template v-for="item in windows" :key="item.id">
          <template v-for="view in viewsOf(item)" :key="`${item.id}-${view}`">
            <SearchWindow
              v-if="item.search"
              :class="view === 'normal' ? 'focused' : 'docked'"
              :search="item.search.search"
              :label="item.search.label"
              :compact="view === 'card'"
              :active="view === 'card' && item.id === focusedWindowId"
              :viewing="viewingWindow === item.id"
              :can-choose-index="!isPublicMode"
              @expand="focusWindow(item.id)"
              @minimize="focusViewer"
              @close="closeSearch(item.id)"
              @duplicate="workspace.duplicateSearch(item.id)"
              @update:label="item.search.label = $event"
              @select-hit="handleSearchSelected(item.search, $event)"
              @open-index="indexDialogOpen = true"
            />
            <LoadedWindow
              v-else
              v-model:level="loadedLevel"
              :class="view === 'normal' ? 'focused' : 'docked'"
              :records="loadedRecords.records.value"
              :regions="loadedRecords.regions.value"
              :selected-key="selectedLoadedKey"
              :loading="loadedRecords.loading.value"
              :error="loadedRecords.error.value"
              :compact="view === 'card'"
              :active="view === 'card' && item.id === focusedWindowId"
              :viewing="viewingWindow === item.id"
              @expand="focusWindow(item.id)"
              @minimize="focusViewer"
              @load="loadDialogOpen = true"
              @select="handleLoadedSelected"
              @select-region="handleLoadedRegionSelected"
              @remove-source="handleRemoveSource"
            />
          </template>
        </template>
        <button type="button" class="new-search docked" title="Open a new search window" @click="workspace.addSearch()">
          <span aria-hidden="true">+</span> New search
        </button>
      </div>

      <section
        class="viewer-window"
        :class="{ compact: !viewerFocused, empty: !hasRecord }"
        aria-label="Record viewer"
      >
        <header class="viewer-header" @click="!viewerFocused && hasRecord && focusViewer()">
          <h2>Viewer</h2>
          <span v-if="hasRecord" class="viewer-subject">
            <strong>{{ currentRecordData.recordId }}</strong>
            <span v-if="viewedRegionLabel"> · {{ viewedRegionLabel }}</span>
            <span class="viewer-file"> · {{ currentRecordData.filename }}</span>
          </span>
          <span v-else class="viewer-subject muted">Select a search result or a loaded record to view it here</span>
          <button
            v-if="hasRecord && !viewerFocused"
            type="button"
            class="viewer-toggle"
            title="Enlarge the viewer"
            aria-label="Enlarge the viewer"
            @click.stop="focusViewer"
          >
            <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 6V3h3M13 6V3h-3M3 10v3h3M13 10v3h-3" /></svg>
          </button>
          <button
            v-else-if="viewerFocused && windows.length"
            type="button"
            class="viewer-toggle"
            title="Make the viewer compact"
            aria-label="Make the viewer compact"
            @click.stop="focusWindow(lastWindowId)"
          >
            <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6 3v3H3M10 3v3h3M6 13v-3H3M10 13v-3h3" /></svg>
          </button>
        </header>
        <div v-if="viewerProvider && currentRecordId" class="viewer-body">
          <RegionViewerContainer
            :key="viewerKey"
            :data-provider="viewerProvider"
            :record-id="currentRecordId"
            :record-data="currentRecordData"
            :initial-region-id="initialRegionId"
            :initial-protocluster-number="initialProtoclusterNumber"
            :show-record-info="viewerFocused"
            @region-changed="handleRegionChanged"
            @annotation-clicked="handleAnnotationClicked"
            @error="handleViewerError"
          />
        </div>
        <p v-else-if="viewerFocused" class="placeholder">
          Pick a result in one of the windows above to view it here.
        </p>
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
import { computed, markRaw, onMounted, ref, watch } from 'vue'
import axios from 'axios'
import AppDialog from './components/AppDialog.vue'
import IndexCreation from './components/IndexCreation.vue'
import IndexSelection from './components/IndexSelection.vue'
import LoadDataDialog from './components/LoadDataDialog.vue'
import LoadedWindow from './components/LoadedWindow.vue'
import RegionViewerContainer from './components/RegionViewerContainer.vue'
import SearchWindow from './components/SearchWindow.vue'
import { EXTERNAL_SOURCES } from './services/externalSources'
import { BGCViewerAPIProvider } from '@/services/dataProviders'
import {
  protoclusterNumberFromHit,
  recordSelectionFromHit,
  regionIdFromHit
} from '@/services/searchNavigation'
import { UPLOAD_SOURCE, useLoadedRecords } from '@/composables/useLoadedRecords'
import { LOADED_WINDOW, VIEWER, useWorkspace } from '@/composables/useWorkspace'

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
    LoadedWindow,
    RegionViewerContainer,
    SearchWindow
  },
  setup() {
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

    // The backend index is searched in any number of search windows; loaded files
    // and accessions are listed beside them in a window of their own
    const apiProvider = markRaw(new BGCViewerAPIProvider())
    const workspace = useWorkspace(() => apiProvider)
    const loadedRecords = useLoadedRecords()
    const loadDialogOpen = ref(false)
    const selectedLoadedKey = ref(null)
    const loadedLevel = ref('region')

    // The windows in screen order: the searches, then the loaded data when there is any
    const showLoaded = computed(() => Boolean(
      loadedRecords.records.value.length || loadedRecords.loading.value || loadedRecords.error.value
    ))
    const windows = computed(() => [
      ...workspace.searches.value.map(search => ({ id: search.id, search })),
      ...(showLoaded.value ? [{ id: LOADED_WINDOW, search: null }] : [])
    ])

    // One window, or the viewer, is shown at normal size
    const focusedWindowId = computed(() =>
      windows.value.some(window => window.id === workspace.focus.value) ? workspace.focus.value : null
    )
    const viewerFocused = computed(() => focusedWindowId.value === null)
    // The window that was last at normal size, which the viewer gives way to again
    const lastWindowId = ref(null)
    watch(focusedWindowId, id => { if (id) lastWindowId.value = id }, { immediate: true })

    const focusWindow = (id) => {
      workspace.focus.value = windows.value.some(window => window.id === id) ? id : windows.value[0]?.id ?? VIEWER
    }
    const focusViewer = () => { workspace.focus.value = VIEWER }
    // How a window is shown: as a card, and the focused one also at normal size
    const viewsOf = (item) => (item.id === focusedWindowId.value ? ['normal', 'card'] : ['card'])

    // The focused window fills the first column; the cards stack beside it, each
    // row as tall as its card, and the last row takes what is left
    const workspaceStyle = computed(() => {
      if (viewerFocused.value) return {}
      // A card for every window, and the new search button
      return { gridTemplateRows: `repeat(${windows.value.length + 1}, auto) minmax(0, 1fr)` }
    })

    // The window whose result the viewer shows, marked in its compact card
    const viewingWindow = ref(null)

    // The viewed record and the provider it comes from
    const viewerProvider = ref(null)
    const viewerKey = ref('')
    const currentRecordId = ref('')
    const currentRecordData = ref(null)
    const initialRegionId = ref('')
    // Set for a protocluster search hit, whose protocluster the viewer zooms to instead of the region
    const initialProtoclusterNumber = ref(null)
    // The region the viewer is zoomed to, for its header
    const viewedRegionId = ref('')
    const hasRecord = computed(() => Boolean(viewerProvider.value && currentRecordId.value))
    const viewedRegionLabel = computed(() => {
      const region = viewedRegionId.value.replace(/^region_/, 'region ')
      if (region && initialProtoclusterNumber.value != null && viewedRegionId.value === initialRegionId.value) {
        return `${region}, protocluster ${initialProtoclusterNumber.value}`
      }
      return region
    })

    // Only one result is selected at a time, across all windows
    const clearSelections = () => {
      workspace.searches.value.forEach(({ search }) => { search.state.selectedHit = null })
      selectedLoadedKey.value = null
    }

    const clearViewer = () => {
      viewerProvider.value = null
      viewerKey.value = ''
      currentRecordId.value = ''
      currentRecordData.value = null
      initialRegionId.value = ''
      initialProtoclusterNumber.value = null
      viewedRegionId.value = ''
      viewingWindow.value = null
      clearSelections()
    }

    const showRecord = (provider, recordData, regionId = '', protoclusterNumber = null) => {
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
      initialProtoclusterNumber.value = protoclusterNumber
      viewedRegionId.value = regionId
    }

    const handleSearchSelected = (searchWindow, hit) => {
      const { state } = searchWindow.search
      const level = state.searchedLevel
      clearSelections()
      state.selectedHit = hit
      viewingWindow.value = searchWindow.id
      showRecord(
        apiProvider,
        recordSelectionFromHit(level, hit),
        regionIdFromHit(level, hit),
        protoclusterNumberFromHit(level, hit)
      )
    }

    const handleLoadedSelected = (record) => {
      clearSelections()
      selectedLoadedKey.value = record.key
      viewingWindow.value = LOADED_WINDOW
      showRecord(record.provider, record)
    }

    const handleLoadedRegionSelected = (region) => {
      clearSelections()
      selectedLoadedKey.value = region.key
      viewingWindow.value = LOADED_WINDOW
      showRecord(region.record.provider, region.record, region.regionId)
    }

    const closeSearch = (id) => {
      if (viewingWindow.value === id) viewingWindow.value = null
      workspace.removeSearch(id)
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
      if (records.length === 0) return
      // An entry fetched from a database is shown right away in the viewer;
      // uploads may still grow, so their list is brought forward
      if (source !== UPLOAD_SOURCE) {
        loadDialogOpen.value = false
        handleLoadedSelected(records[0])
        focusViewer()
      } else if (asked) {
        workspace.focus.value = LOADED_WINDOW
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
      await workspace.openIndex()
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
      viewedRegionId.value = regionId || ''
    }

    // The details of a clicked annotation need the room of the normal viewer
    const handleAnnotationClicked = () => {
      focusViewer()
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

    // Before an index opens, its search window says how to open one
    workspace.addSearch()

    onMounted(async () => {
      fetchVersion()
      await fetchStatus()
      // Public mode serves one fixed index; in local mode the index dialog opens
      // the last used index and reports it through handleIndexChanged
      if (isPublicMode.value) await openIndex('')
    })

    return {
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
      workspace,
      windows,
      focusedWindowId,
      viewerFocused,
      lastWindowId,
      workspaceStyle,
      viewingWindow,
      focusWindow,
      focusViewer,
      viewsOf,
      closeSearch,
      loadedRecords,
      loadDialogOpen,
      selectedLoadedKey,
      loadedLevel,
      hasRecord,
      viewedRegionLabel,
      viewerProvider,
      viewerKey,
      currentRecordId,
      currentRecordData,
      initialRegionId,
      initialProtoclusterNumber,
      handleSearchSelected,
      handleLoadedSelected,
      handleLoadedRegionSelected,
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

/* Main content: the windows over the viewer, sized to fit the screen without scrolling */
.main-content {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  padding: 12px 20px 16px;
  overflow-y: auto;
  background-color: #f4f4f4;
}

/* Viewer focused: every window is a compact card in one row */
.workspace {
  display: flex;
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 10px;
}

.workspace > .docked {
  width: 230px;
}

/* A window focused: it fills the first column, the compact cards stack beside it */
.workspace.has-focus {
  display: grid;
  flex: 1 1 0;
  grid-template-columns: minmax(0, 1fr) 230px;
  align-content: stretch;
  min-height: 360px;
}

.workspace.has-focus > .focused {
  grid-column: 1;
  grid-row: 1 / -1;
}

.workspace.has-focus > .docked {
  grid-column: 2;
  width: auto;
}

.new-search {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 44px;
  align-self: stretch;
  padding: 6px 10px;
  border: 1px dashed #aebbc4;
  border-radius: 8px;
  background: transparent;
  color: #40525e;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
}

.workspace.has-focus > .new-search {
  align-self: start;
}

.new-search:hover {
  border-color: #1976b5;
  background: #fff;
  color: #145f92;
}

.new-search:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: 1px;
}

/* The viewer: as large as the screen allows when focused; otherwise a strip below the windows */
.viewer-window {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-height: 420px;
  border: 1px solid #dce3e8;
  border-radius: 8px;
  background: #f8f9fa;
  overflow: hidden;
}

.viewer-window.compact {
  flex: 0 0 clamp(240px, 38vh, 460px);
  min-height: 0;
}

.viewer-window.compact.empty {
  flex-basis: auto;
}

.viewer-header {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 10px;
  min-height: 41px;
  padding: 6px 8px 6px 12px;
  border-bottom: 1px solid #dce3e8;
  background: #fff;
}

.viewer-window.empty .viewer-header {
  border-bottom: 0;
}

.viewer-window.compact:not(.empty) .viewer-header {
  cursor: pointer;
}

.viewer-window.compact:not(.empty) .viewer-header:hover {
  background: #f3f7fa;
}

.viewer-header h2 {
  margin: 0;
  color: #263442;
  font-size: 15px;
}

.viewer-subject {
  min-width: 0;
  overflow: hidden;
  color: #30434f;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.viewer-subject.muted,
.viewer-file {
  color: #687681;
}

.viewer-subject.muted {
  font-style: italic;
}

.viewer-toggle {
  display: inline-flex;
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  align-items: center;
  justify-content: center;
  margin-left: auto;
  border: 1px solid transparent;
  border-radius: 4px;
  background: transparent;
  color: #52616d;
  cursor: pointer;
}

.viewer-toggle svg {
  width: 14px;
  height: 14px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.8;
}

.viewer-toggle:hover {
  border-color: #dce3e8;
  background: #edf2f5;
}

.viewer-toggle:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: 1px;
}

.viewer-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px 15px;
}

.placeholder {
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: center;
  color: #666;
  font-style: italic;
}

@media (max-width: 800px) {
  .workspace.has-focus {
    grid-template-columns: minmax(0, 1fr);
  }

  .workspace.has-focus > .focused,
  .workspace.has-focus > .docked {
    grid-column: 1;
    grid-row: auto;
  }
}

.main-content::-webkit-scrollbar,
.viewer-body::-webkit-scrollbar {
  width: 10px;
}

.main-content::-webkit-scrollbar-track,
.viewer-body::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.main-content::-webkit-scrollbar-thumb,
.viewer-body::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 5px;
}

.main-content::-webkit-scrollbar-thumb:hover,
.viewer-body::-webkit-scrollbar-thumb:hover {
  background: #555;
}
</style>
