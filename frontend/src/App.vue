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
      <!-- Left sidebar for controls (30%) -->
      <aside class="sidebar" :style="{ width: sidebarWidth + 'px' }">
        <!-- Index Selection Section - Only shown in local mode and when not creating an index -->
        <IndexSelection 
          v-if="!isPublicMode && !folderForIndexing"
          @folder-selected="handleFolderSelected"
          @folder-changed="handleFolderChanged"
          @index-changed="handleIndexChanged"
          @create-index-for-folder="handleCreateIndexForFolder"
        />

        <!-- Index Creation Section - Only shown in local mode when creating a new index -->
        <IndexCreation
          v-if="!isPublicMode && folderForIndexing"
          :folder-path="folderForIndexing"
          :index-path="indexPathForCreation"
          :available-files="availableFiles"
          :is-loading-files="isLoadingFiles"
          :needs-preprocessing="needsPreprocessing"
          @preprocessing-completed="handlePreprocessingCompleted"
          @cancel="handleCancelIndexCreation"
        />

        <!-- Record List Selector Section - Hidden when creating an index -->
        <RecordListSelector 
          v-if="!folderForIndexing"
          ref="recordListSelectorRef"
          :data-root="selectedDataRoot"
          :index-path="selectedIndexPath"
          @record-selected="handleRecordSelected" 
        />
      </aside>

      <!-- Draggable divider -->
      <div 
        class="divider"
        @mousedown="startDragging"
      ></div>

      <!-- Right main viewer area (70%) -->
      <main class="viewer-area">
        <RegionViewerContainer 
          v-if="!folderForIndexing"
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
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import RegionViewerContainer from './components/RegionViewerContainer.vue'
import IndexSelection from './components/IndexSelection.vue'
import IndexCreation from './components/IndexCreation.vue'
import RecordListSelector from './components/RecordListSelector.vue'
import { BGCViewerAPIProvider } from '@/services/dataProviders'

export default {
  name: 'App',
  components: {
    RegionViewerContainer,
    IndexSelection,
    IndexCreation,
    RecordListSelector
  },
  setup() {
    const regionViewerRef = ref(null)
    const recordListSelectorRef = ref(null)
    
    // Version information
    const appVersion = ref('')
    const appName = ref('BGC Viewer')
    
    // Mode information
    const isPublicMode = ref(true) // Default to true for safety
    
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
    const sidebarWidth = ref(350) // Default width in pixels
    const isDragging = ref(false)
    const minSidebarWidth = 250
    const maxSidebarWidth = 800
    
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
      currentRecordId.value = recordData.recordId
      initialRegionId.value = '' // Reset region selection for new record
      
      console.log('Record selected:', recordData.recordId)
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
      
      // Update the selected index path
      selectedIndexPath.value = indexPath
      
      // Refresh the record list
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
      
      const newWidth = e.clientX
      if (newWidth >= minSidebarWidth && newWidth <= maxSidebarWidth) {
        sidebarWidth.value = newWidth
      }
    }
    
    const stopDragging = () => {
      isDragging.value = false
      document.removeEventListener('mousemove', onDrag)
      document.removeEventListener('mouseup', stopDragging)
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
    })
    
    return {
      regionViewerRef,
      recordListSelectorRef,
      appVersion,
      appName,
      isPublicMode,
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
      startDragging
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
  overflow-y: auto;
  display: flex;
  flex-direction: column;
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

/* Scrollbar styling for sidebar */
.sidebar::-webkit-scrollbar {
  width: 8px;
}

.sidebar::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.sidebar::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 4px;
}

.sidebar::-webkit-scrollbar-thumb:hover {
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
