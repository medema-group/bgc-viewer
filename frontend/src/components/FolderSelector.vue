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
      @preprocessing-completed="handlePreprocessingCompleted"
    />
  </section>
</template>

<script>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import FolderSelectionDialog from './FolderSelectionDialog.vue'
import PreprocessingStatus from './PreprocessingStatus.vue'

export default {
  name: 'FolderSelector',
  components: {
    FolderSelectionDialog,
    PreprocessingStatus
  },
  emits: ['folder-selected', 'folder-changed', 'preprocessing-completed'],
  setup(_, { emit }) {
    const currentFolderPath = ref('')
    const showDialog = ref(false)
    const folderRestoredFromMemory = ref(false)
    
    const STORAGE_KEY = 'bgc-viewer-last-folder'
    
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
      console.log('Preprocessing completed')
      // Emit event that preprocessing is completed
      emit('preprocessing-completed', currentFolderPath.value)
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
      handlePreprocessingCompleted
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
</style>
