<template>
  <div class="app-container">
    <!-- Header spanning full width -->
    <header class="app-header">
      <h1>BGC Viewer</h1>
      <div class="version-info">
        <span v-if="appVersion">{{ appName }} v{{ appVersion }}</span>
        <span v-else>Loading version...</span>
      </div>
    </header>

    <!-- Main content area with sidebar and viewer -->
    <div class="main-content">
      <!-- Left sidebar for controls -->
      <aside class="sidebar" :style="{ width: sidebarWidth + '%' }">
        <!-- Top section: Data source and file controls -->
        <div class="sidebar-top" :style="{ height: sidebarTopHeight + '%' }">
          <!-- Data Source Selector -->
          <DataSourceSelector 
            v-model="dataSource"
          />

          <!-- API Mode: Index Selection Section - Only shown in API mode, local mode, and when not creating an index -->
          <IndexSelection 
            v-if="dataSource === 'api' && !isPublicMode && !folderForIndexing"
            :index-path="selectedIndexPath"
            @folder-selected="handleFolderSelected"
            @folder-changed="handleFolderChanged"
            @index-changed="handleIndexChanged"
            @create-index-for-folder="handleCreateIndexForFolder"
          />

          <!-- API Mode: Index Creation Section - Only shown in API mode, local mode, and when creating a new index -->
          <IndexCreation
            v-if="dataSource === 'api' && !isPublicMode && folderForIndexing"
            :folder-path="folderForIndexing"
            :index-path="indexPathForCreation"
            :available-files="availableFiles"
            :is-loading-files="isLoadingFiles"
            :needs-preprocessing="needsPreprocessing"
            @preprocessing-completed="handlePreprocessingCompleted"
            @cancel="handleCancelIndexCreation"
          />

          <!-- Upload Mode: File Upload Section -->
          <FileUpload
            v-if="dataSource === 'upload'"
            @files-loaded="handleFilesLoaded"
          />
        </div>

        <!-- Horizontal draggable divider -->
        <div 
          class="horizontal-divider"
          @mousedown="startVerticalDragging"
        ></div>

        <!-- Bottom section: Record list -->
        <div class="sidebar-bottom">
          <!-- Record List Selector Section - Hidden when creating an index -->
          <RecordListSelector 
            v-if="!folderForIndexing"
            ref="recordListSelectorRef"
            :data-root="selectedDataRoot"
            :index-path="selectedIndexPath"
            @record-selected="handleRecordSelected" 
          />
        </div>
      </aside>

      <!-- Draggable divider -->
      <div 
        class="divider"
        @mousedown="startDragging"
      ></div>

      <!-- Right main viewer area -->
      <main class="viewer-area">
        <RegionViewerContainer 
          v-if="!folderForIndexing && dataProvider"
          ref="regionViewerRef"
          :data-provider="dataProvider"
          :record-id="currentRecordId"
          :record-data="currentRecordData"
          :initial-region-id="initialRegionId"
          @region-changed="handleRegionChanged"
          @annotation-clicked="handleAnnotationClicked"
          @error="handleViewerError"
        />
        <div v-else class="placeholder">
          <p>Select a record from the sidebar to view details</p>
        </div>
      </main>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import axios from 'axios'
import RegionViewerContainer from './components/RegionViewerContainer.vue'
import IndexSelection from './components/IndexSelection.vue'
import IndexCreation from './components/IndexCreation.vue'
import RecordListSelector from './components/RecordListSelector.vue'
import DataSourceSelector from './components/DataSourceSelector.vue'
import FileUpload from './components/FileUpload.vue'
import { BGCViewerAPIProvider, JSONFileProvider, GenbankFileProvider } from '@/services/dataProviders'

export default {
  name: 'App',
  components: {
    RegionViewerContainer,
    IndexSelection,
    IndexCreation,
    RecordListSelector,
    DataSourceSelector,
    FileUpload
  },
  setup() {
    const regionViewerRef = ref(null)
    const recordListSelectorRef = ref(null)
    
    // Version information
    const appVersion = ref('')
    const appName = ref('BGC Viewer')
    
    // Mode information
    const isPublicMode = ref(true) // Default to true for safety
    
    // Restore data source from localStorage, default to 'api'
    const savedDataSource = localStorage.getItem('bgc-viewer-data-source')
    const dataSource = ref(savedDataSource || 'api') // 'api' or 'upload'
    
    // Data root and index tracking
    const selectedDataRoot = ref('')
    const selectedIndexPath = ref('')
    
    // Index creation state
    const folderForIndexing = ref('')
    const indexPathForCreation = ref('')
    const availableFiles = ref([])
    const isLoadingFiles = ref(false)
    const needsPreprocessing = ref(false)
    
    // Region viewer state - much simpler now!
    const dataProvider = ref(null)
    const currentRecordId = ref('')
    const currentRecordData = ref(null)
    const initialRegionId = ref('')
    
    // Draggable divider state
    const sidebarWidth = ref(32) // Default width as percentage
    const isDragging = ref(false)
    const minSidebarWidth = 15 // Minimum 15%
    const maxSidebarWidth = 50 // Maximum 50%
    
    // Vertical (horizontal divider) state for sidebar sections
    const sidebarTopHeight = ref(30) // Default top section height as percentage
    const isVerticalDragging = ref(false)
    const minSidebarTopHeight = 15 // Minimum 15%
    const maxSidebarTopHeight = 70 // Maximum 70%
    
    const handleFolderSelected = async (folderPath) => {
      // Update the selected data root
      selectedDataRoot.value = folderPath
    }

    const handleFolderChanged = async (folderPath) => {
      // Clear the record list immediately when folder changes
      if (recordListSelectorRef.value) {
        recordListSelectorRef.value.clearRecords()
      }
      // Update the selected data root
      selectedDataRoot.value = folderPath
    }

    const handleIndexChanged = async (indexPath) => {
      // Clear the viewer when the index changes
      currentRecordId.value = ''
      initialRegionId.value = ''
      
      // Store the index file path (not data root)
      selectedIndexPath.value = indexPath
      // Refresh the record list when index has changed
      if (recordListSelectorRef.value) {
        await recordListSelectorRef.value.refreshEntries()
      }
    }

    const handleRecordSelected = async (recordData) => {
      // Store the selected entry ID - container will load it through the provider
      currentRecordData.value = {
        entryId: recordData.entryId,
        recordId: recordData.recordId,
        filename: recordData.filename
      }
      
      // Set the record ID to trigger the container to load
      // Use entryId (which includes filename) for uniqueness, not recordId
      currentRecordId.value = recordData.entryId
      initialRegionId.value = '' // Reset region selection for new record
      
      console.log('Record selected:', recordData.recordId, 'from', recordData.filename, '(entryId:', recordData.entryId, ')')
    }
    
    const handleRegionChanged = (regionId) => {
      console.log('Region changed to:', regionId)
      // You can add custom handling here if needed
    }
    
    const handleAnnotationClicked = (data) => {
      console.log('Annotation clicked:', data)
      // You can add custom handling here
    }
    
    const handleViewerError = (error) => {
      console.error('Viewer error:', error)
      // You can add error handling/display here
    }
    
    const handleCreateIndexForFolder = async ({ folderPath, indexPath, files }) => {
      // Set up state for index creation
      folderForIndexing.value = folderPath
      indexPathForCreation.value = indexPath || ''
      availableFiles.value = files.availableFiles || []
      isLoadingFiles.value = files.isLoadingFiles || false
      needsPreprocessing.value = files.needsPreprocessing || false
    }
    
    const handlePreprocessingCompleted = async (indexPath) => {
      // Clear index creation state
      folderForIndexing.value = ''
      indexPathForCreation.value = ''
      availableFiles.value = []
      isLoadingFiles.value = false
      needsPreprocessing.value = false
      
      // Update the selected index path - this will trigger the watcher in RecordListSelector
      // which will call setDatabasePath and loadEntries automatically
      selectedIndexPath.value = indexPath
      
      // Give the watcher time to process the change
      await new Promise(resolve => setTimeout(resolve, 100))
      
      // Refresh the record list to ensure it's fully loaded
      if (recordListSelectorRef.value) {
        await recordListSelectorRef.value.refreshEntries()
      }
    }
    
    const handleCancelIndexCreation = () => {
      // Clear index creation state
      folderForIndexing.value = ''
      indexPathForCreation.value = ''
      availableFiles.value = []
      isLoadingFiles.value = false
      needsPreprocessing.value = false
    }
    
    const handleFilesLoaded = async (files) => {
      if (files.length === 0) {
        // All files removed
        dataProvider.value = null
        currentRecordId.value = ''
        currentRecordData.value = null
        initialRegionId.value = ''
        
        if (recordListSelectorRef.value) {
          await recordListSelectorRef.value.clearRecords()
        }
        return
      }
      
      console.log('Files loaded:', files.length)
      
      // Detect file types and create appropriate providers
      const jsonFiles = files.filter(f => f.type === 'json')
      const genbankFiles = files.filter(f => f.type === 'genbank')
      
      let provider = null
      
      if (jsonFiles.length > 0 && genbankFiles.length > 0) {
        // Mixed file types - not supported yet
        console.error('Mixed file types not supported. Please upload only JSON or only GenBank files.')
        return
      } else if (jsonFiles.length > 0) {
        // Create JSONFileProvider
        const jsonProvider = new JSONFileProvider()
        
        // Load all JSON files into the provider
        for (const fileInfo of jsonFiles) {
          await jsonProvider.loadFromFile(fileInfo.file)
        }
        
        provider = jsonProvider
      } else if (genbankFiles.length > 0) {
        // Create GenbankFileProvider
        const genbankProvider = new GenbankFileProvider()
        
        // Load all GenBank files into the provider
        for (const fileInfo of genbankFiles) {
          await genbankProvider.loadFromFile(fileInfo.file)
        }
        
        provider = genbankProvider
      }
      
      if (!provider) {
        console.error('No valid files to load')
        return
      }
      
      // Replace the current data provider
      dataProvider.value = provider
      
      // Get record count
      const records = await provider.getRecords()
      console.log('Total records loaded:', records.length)
      
      // Clear current selection
      currentRecordId.value = ''
      currentRecordData.value = null
      initialRegionId.value = ''
      
      // Pass the provider to RecordListSelector for searching
      if (recordListSelectorRef.value) {
        await recordListSelectorRef.value.setRecordsFromProvider(provider)
      }
    }
    
    // Watch for data source changes
    watch(dataSource, async (newSource) => {
      // Save to localStorage
      localStorage.setItem('bgc-viewer-data-source', newSource)
      
      // Clear current data when switching sources
      currentRecordId.value = ''
      currentRecordData.value = null
      initialRegionId.value = ''
      
      // Reset data provider based on source
      if (newSource === 'api') {
        const apiProvider = new BGCViewerAPIProvider()
        dataProvider.value = apiProvider
        
        // Set API provider in RecordListSelector
        if (recordListSelectorRef.value) {
          await recordListSelectorRef.value.setRecordsFromProvider(apiProvider, false)
        }
      } else if (newSource === 'upload') {
        // Clear records and wait for file upload
        if (recordListSelectorRef.value) {
          recordListSelectorRef.value.clearRecords()
        }
        dataProvider.value = null
      }
    })
    
    // Draggable divider functions
    const startDragging = (e) => {
      isDragging.value = true
      e.preventDefault()
      document.addEventListener('mousemove', onDrag)
      document.addEventListener('mouseup', stopDragging)
      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'
    }
    
    const onDrag = (e) => {
      if (!isDragging.value) return
      
      // Calculate percentage based on window width
      const percentage = (e.clientX / window.innerWidth) * 100
      if (percentage >= minSidebarWidth && percentage <= maxSidebarWidth) {
        sidebarWidth.value = percentage
      }
    }
    
    const stopDragging = () => {
      isDragging.value = false
      document.removeEventListener('mousemove', onDrag)
      document.removeEventListener('mouseup', stopDragging)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    
    // Vertical draggable divider functions (for sidebar sections)
    const startVerticalDragging = (e) => {
      isVerticalDragging.value = true
      e.preventDefault()
      document.addEventListener('mousemove', onVerticalDrag)
      document.addEventListener('mouseup', stopVerticalDragging)
      document.body.style.cursor = 'row-resize'
      document.body.style.userSelect = 'none'
    }
    
    const onVerticalDrag = (e) => {
      if (!isVerticalDragging.value) return
      
      // Get sidebar element to calculate relative position
      const sidebar = e.target.closest('.sidebar')
      if (!sidebar) return
      
      const sidebarRect = sidebar.getBoundingClientRect()
      const relativeY = e.clientY - sidebarRect.top
      const percentage = (relativeY / sidebarRect.height) * 100
      
      if (percentage >= minSidebarTopHeight && percentage <= maxSidebarTopHeight) {
        sidebarTopHeight.value = percentage
      }
    }
    
    const stopVerticalDragging = () => {
      isVerticalDragging.value = false
      document.removeEventListener('mousemove', onVerticalDrag)
      document.removeEventListener('mouseup', stopVerticalDragging)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    
    const fetchVersion = async () => {
      try {
        const response = await axios.get('/api/version')
        appVersion.value = response.data.version
        appName.value = response.data.name
      } catch (error) {
        console.warn('Failed to fetch version:', error)
        // Keep default values if fetch fails
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
    
    // Fetch application version and status on component mount
    onMounted(async () => {
      fetchVersion()
      fetchStatus()
      
      // Initialize data provider - this will be shared with the container
      dataProvider.value = new BGCViewerAPIProvider()
    })
    
    // Cleanup on unmount
    onUnmounted(() => {
      document.removeEventListener('mousemove', onDrag)
      document.removeEventListener('mouseup', stopDragging)
      document.removeEventListener('mousemove', onVerticalDrag)
      document.removeEventListener('mouseup', stopVerticalDragging)
    })
    
    return {
      regionViewerRef,
      recordListSelectorRef,
      appVersion,
      appName,
      isPublicMode,
      dataSource,
      selectedDataRoot,
      selectedIndexPath,
      folderForIndexing,
      indexPathForCreation,
      availableFiles,
      isLoadingFiles,
      needsPreprocessing,
      dataProvider,
      currentRecordId,
      currentRecordData,
      sidebarTopHeight,
      initialRegionId,
      sidebarWidth,
      handleFolderSelected,
      handleFolderChanged,
      handleIndexChanged,
      handleRecordSelected,
      handleRegionChanged,
      handleAnnotationClicked,
      handleViewerError,
      handleCreateIndexForFolder,
      handlePreprocessingCompleted,
      handleCancelIndexCreation,
      handleFilesLoaded,
      startDragging,
      startVerticalDragging
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
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  z-index: 10;
}

.app-header h1 {
  color: #2c3e50;
  margin: 0;
  font-size: 24px;
}

.app-header .version-info {
  color: #666;
  font-size: 0.85rem;
  font-weight: 500;
}

/* Main content area with sidebar and viewer */
.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  background-color: #f4f4f4;
}

/* Left sidebar (30%) */
.sidebar {
  flex-shrink: 0;
  background: white;
  overflow: hidden; /* Parent doesn't scroll */
  display: flex;
  flex-direction: column;
  min-height: 0; /* Critical for flexbox scrolling */
  scrollbar-width: thin; /* Firefox */
  scrollbar-color: #888 #f1f1f1; /* Firefox - thumb and track */
}

/* Sidebar top section */
.sidebar-top {
  flex-shrink: 0;
  overflow-y: auto; /* Allow scrolling when content exceeds height */
  display: flex;
  flex-direction: column;
  min-height: 100px; /* Prevent it from becoming too small */
}

/* Horizontal draggable divider */
.horizontal-divider {
  height: 4px;
  background: #e0e0e0;
  cursor: row-resize;
  flex-shrink: 0;
  transition: background-color 0.2s;
}

.horizontal-divider:hover {
  background: #1976d2;
}

.horizontal-divider:active {
  background: #1565c0;
}

/* Sidebar bottom section */
.sidebar-bottom {
  flex: 1;
  overflow: hidden; /* No scrollbar */
  display: flex;
  flex-direction: column;
  min-height: 100px; /* Prevent it from becoming too small */
}

/* Draggable divider */
.divider {
  width: 4px;
  background: #e0e0e0;
  cursor: col-resize;
  flex-shrink: 0;
  transition: background-color 0.2s;
  position: relative;
}

.divider:hover {
  background: #1976d2;
}

.divider:active {
  background: #1565c0;
}

/* Right viewer area (70%) */
.viewer-area {
  flex: 1;
  overflow-y: auto;
  background: #f8f9fa;
  padding: 15px;
}

.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #666;
  font-style: italic;
}

/* Scrollbar styling for sidebar sections */
.sidebar-top::-webkit-scrollbar,
.sidebar-bottom::-webkit-scrollbar {
  width: 8px;
}

.sidebar-top::-webkit-scrollbar-track,
.sidebar-bottom::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.sidebar-top::-webkit-scrollbar-thumb,
.sidebar-bottom::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 4px;
}

.sidebar-top::-webkit-scrollbar-thumb:hover,
.sidebar-bottom::-webkit-scrollbar-thumb:hover {
  background: #555;
}

/* Scrollbar styling for viewer area */
.viewer-area::-webkit-scrollbar {
  width: 10px;
}

.viewer-area::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.viewer-area::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 5px;
}

.viewer-area::-webkit-scrollbar-thumb:hover {
  background: #555;
}
</style>
