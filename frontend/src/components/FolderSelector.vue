<template>
  <section class="folder-selector-section">
    <h2>Folder Selection</h2>
    <div class="folder-selector">
      <button @click="showFolderDialog" class="browse-button">
        Select Folder
      </button>
      <span v-if="currentFolderPath" class="current-folder">
        Current folder: <strong>{{ currentFolderPath }}</strong>
      </span>
    </div>

    <FolderSelectionDialog 
      :show="showDialog"
      @close="handleDialogClose"
      @folder-selected="handleFolderSelected"
    />

    <PreprocessingStatus 
      :folder-path="currentFolderPath"
      :selected-files="selectedFiles"
      @preprocessing-completed="handlePreprocessingCompleted"
      @need-file-selection="handleNeedFileSelection"
      ref="preprocessingStatusRef"
    />
    
    <div v-if="isLoadingFiles" class="loading-files">
      <LoadingSpinner color="#1976d2" style="width: 32px; height: 32px; border-width: 3px;" />
      <span class="loading-text">Loading file list...</span>
    </div>
    
    <FileSelector 
      v-if="showFileSelector"
      :json-files="availableFiles"
      @files-selected="handleFilesSelected"
    />
  </section>
</template>

<script>
import { ref, onMounted, watch } from 'vue'
import axios from 'axios'
import FolderSelectionDialog from './FolderSelectionDialog.vue'
import PreprocessingStatus from './PreprocessingStatus.vue'
import FileSelector from './FileSelector.vue'
import LoadingSpinner from './LoadingSpinner.vue'

export default {
  name: 'FolderSelector',
  components: {
    FolderSelectionDialog,
    PreprocessingStatus,
    FileSelector,
    LoadingSpinner
  },
  emits: ['folder-selected', 'folder-changed', 'preprocessing-completed'],
  setup(_, { emit }) {
    const currentFolderPath = ref('')
    const showDialog = ref(false)
    const folderRestoredFromMemory = ref(false)
    const showFileSelector = ref(false)
    const isLoadingFiles = ref(false)
    const availableFiles = ref([])
    const selectedFiles = ref([])
    const preprocessingStatusRef = ref(null)
    
    const STORAGE_KEY = 'bgc-viewer-last-folder'
    
    // Watch for folder path changes to reset file selector
    watch(currentFolderPath, () => {
      // Hide file selector when folder changes
      showFileSelector.value = false
      isLoadingFiles.value = false
      availableFiles.value = []
      selectedFiles.value = []
    })
    
    const saveLastFolder = (folderPath) => {
      try {
        localStorage.setItem(STORAGE_KEY, folderPath)
        console.log('Saved folder to localStorage:', folderPath)
      } catch (error) {
        console.warn('Failed to save last folder to localStorage:', error)
      }
    }
    
    const loadLastFolder = () => {
      try {
        const savedFolder = localStorage.getItem(STORAGE_KEY)
        console.log('Loaded folder from localStorage:', savedFolder)
        return savedFolder
      } catch (error) {
        console.warn('Failed to load last folder from localStorage:', error)
        return null
      }
    }
    
    const tryDefaultFolder = async () => {
      // First try to use the last remembered folder
      const lastFolder = loadLastFolder()
      if (lastFolder) {
        try {
          const lastFolderResponse = await axios.post('/api/scan-folder', {
            path: lastFolder
          })
          
          if (lastFolderResponse.data.folder_path) {
            currentFolderPath.value = lastFolderResponse.data.folder_path
            folderRestoredFromMemory.value = true
            // Emit folder change event first
            emit('folder-changed', lastFolderResponse.data.folder_path)
            emit('folder-selected', lastFolderResponse.data.folder_path)
            console.log('Restored last used folder:', lastFolder)
            return // Successfully restored, no need to try default
          }
        } catch (lastFolderError) {
          console.warn('Failed to restore last used folder:', lastFolderError.message)
        }
      }
      
      // If no saved folder or saved folder failed, try the default data directory
      try {
        const dataDir = '../data'
        const scanResponse = await axios.post('/api/scan-folder', {
          path: dataDir
        })
        
        if (scanResponse.data.folder_path) {
          currentFolderPath.value = scanResponse.data.folder_path
          folderRestoredFromMemory.value = false
          // Save the default folder for next time
          saveLastFolder(scanResponse.data.folder_path)
          // Emit folder change event first
          emit('folder-changed', scanResponse.data.folder_path)
          // Emit folder selection for default data directory
          emit('folder-selected', scanResponse.data.folder_path)
          console.log('Using default data directory:', dataDir)
        }
        
      } catch (scanError) {
        console.warn('Failed to scan default data directory:', scanError.message)
        console.log('No folder selected - user will need to select one manually')
      }
    }
    
    const showFolderDialog = () => {
      showDialog.value = true
    }
    
    const handleDialogClose = () => {
      showDialog.value = false
    }
    
    const handleFolderSelected = (folderData) => {
      currentFolderPath.value = folderData.folderPath
      folderRestoredFromMemory.value = false
      
      // Save the selected folder for next time
      saveLastFolder(folderData.folderPath)
      
      // Emit folder change event first when user manually selects folder
      emit('folder-changed', folderData.folderPath)
      
      // Emit the folder selection event to parent
      emit('folder-selected', folderData.folderPath)
      
      const count = folderData.count
      const scanType = folderData.scanType
      
      if (count === 0) {
        alert(`No JSON files found in the selected folder and its subdirectories`)
      } else {
        alert(`Found ${count} JSON file${count === 1 ? '' : 's'} in the selected folder (${scanType} scan)`)
      }
    }
    

    
    const handlePreprocessingCompleted = () => {
      // Clear file selection
      showFileSelector.value = false
      selectedFiles.value = []
      availableFiles.value = []
      // Emit event that preprocessing is completed
      emit('preprocessing-completed', currentFolderPath.value)
    }
    
    const handleNeedFileSelection = async (indexStatusData) => {
      // Fetch the list of JSON files from the API
      isLoadingFiles.value = true
      try {
        const response = await axios.post('/api/scan-folder', {
          path: currentFolderPath.value
        })
        
        if (response.data.json_files && response.data.json_files.length > 0) {
          availableFiles.value = response.data.json_files
          showFileSelector.value = true
        } else {
          alert('No JSON files found in the selected folder')
        }
      } catch (error) {
        console.error('Failed to fetch JSON files:', error)
        alert(`Failed to fetch file list: ${error.response?.data?.error || error.message}`)
      } finally {
        isLoadingFiles.value = false
      }
    }
    
    const handleFilesSelected = (files) => {
      selectedFiles.value = files
      showFileSelector.value = false
      
      // Trigger preprocessing with selected files
      if (preprocessingStatusRef.value) {
        const filePaths = files.map(f => f.path)
        preprocessingStatusRef.value.startPreprocessing(filePaths)
      }
    }
    
    // Try to load default folder on component mount
    onMounted(() => {
      tryDefaultFolder()
    })
    
    return {
      currentFolderPath,
      showDialog,
      folderRestoredFromMemory,
      showFolderDialog,
      handleDialogClose,
      handleFolderSelected,
      handlePreprocessingCompleted,
      handleNeedFileSelection,
      handleFilesSelected,
      showFileSelector,
      isLoadingFiles,
      availableFiles,
      selectedFiles,
      preprocessingStatusRef
    }
  }
}
</script>

<style scoped>
.folder-selector-section {
  background: #e3f2fd;
  border: 1px solid #bbdefb;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 30px;
}

.folder-selector-section h2 {
  margin-top: 0;
  color: #1976d2;
}

.folder-selector {
  display: flex;
  align-items: center;
  gap: 15px;
  flex-wrap: wrap;
}

.current-folder {
  color: #2e7d32;
  font-size: 14px;
  margin-left: 15px;
}

.restored-indicator {
  color: #1976d2;
  font-size: 12px;
  font-style: italic;
  margin-left: 8px;
}

.browse-button {
  background: #1976d2;
  color: white;
  border: none;
  padding: 10px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.browse-button:hover {
  background: #1565c0;
}

.loading-files {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px;
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  margin: 20px 0;
}

.loading-text {
  color: #495057;
  font-size: 14px;
}
</style>
