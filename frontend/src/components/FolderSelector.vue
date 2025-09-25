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
  emits: ['folder-selected'],
  setup(_, { emit }) {
    const currentFolderPath = ref('')
    const showDialog = ref(false)
    
    const tryDefaultFolder = async () => {
      try {
        // Try to scan the default data directory
        const dataDir = '../data'
        const scanResponse = await axios.post('/api/scan-folder', {
          path: dataDir
        })
        
        if (scanResponse.data.folder_path) {
          currentFolderPath.value = scanResponse.data.folder_path
          // Emit folder selection for default data directory
          emit('folder-selected', scanResponse.data.folder_path)
        }
        
      } catch (scanError) {
        console.warn('Failed to scan default data directory:', scanError.message)
        // Don't show error to user - just means no default folder available
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
    }
    
    // Try to load default folder on component mount
    onMounted(() => {
      tryDefaultFolder()
    })
    
    return {
      currentFolderPath,
      showDialog,
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
