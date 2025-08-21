<template>
  <section class="file-selector-section">
    <h2>Data File Selection</h2>
    <div class="folder-selector">
      <button @click="showFolderDialog" class="browse-button">
        Select Folder
      </button>
      <span v-if="currentFolderPath" class="current-folder">
        Current folder: <strong>{{ currentFolderPath }}</strong>
      </span>
    </div>
    <div class="file-selector">
      <label for="file-select">Choose JSON file:</label>
      <select 
        id="file-select" 
        v-model="selectedFile" 
        @change="handleFileSelection"
        class="file-select"
        :disabled="availableFiles.length === 0"
      >
        <option value="" disabled>
          {{ availableFiles.length === 0 ? 'No JSON files available - select a folder first' : 'Select a file...' }}
        </option>
        <option 
          v-for="file in availableFiles" 
          :key="file.name || file" 
          :value="file.path || file"
        >
          {{ file.relative_path || file.name || file }}{{ file.size ? ` (${formatFileSize(file.size)})` : '' }}
        </option>
      </select>
      <span v-if="currentFile" class="current-file">
        Currently loaded: <strong>{{ currentFile }}</strong>
      </span>
      <span v-else-if="availableFiles.length === 0 && !loadingFile" class="no-file-indicator">
        No data loaded - please select a folder containing JSON files
      </span>
      <span v-if="loadingFile" class="loading-indicator">Loading...</span>
    </div>

    <FolderSelectionDialog 
      :show="showDialog"
      @close="handleDialogClose"
      @folder-selected="handleFolderSelected"
    />
  </section>
</template>

<script>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import FolderSelectionDialog from './FolderSelectionDialog.vue'

export default {
  name: 'FileSelector',
  components: {
    FolderSelectionDialog
  },
  emits: ['file-loaded'],
  setup(_, { emit }) {
    const selectedFile = ref('')
    const availableFiles = ref([])
    const currentFile = ref('')
    const currentFolderPath = ref('')
    const loadingFile = ref(false)
    const showDialog = ref(false)
    
    const loadAvailableFiles = async () => {
      try {
        // Get current status first
        let currentStatus = null
        try {
          const statusResponse = await axios.get('/api/status')
          currentStatus = statusResponse.data
        } catch (statusError) {
          console.warn('Could not get current status:', statusError.message)
        }
        
        // Try to scan the default data directory
        const dataDir = './data'
        try {
          const scanResponse = await axios.post('/api/scan-folder', {
            path: dataDir
          })
          
          if (scanResponse.data.json_files && scanResponse.data.json_files.length > 0) {
            availableFiles.value = scanResponse.data.json_files
            currentFolderPath.value = scanResponse.data.folder_path
          } else {
            // No files in data directory
            availableFiles.value = []
            currentFolderPath.value = ''
          }
          
          // Set current file info from status
          if (currentStatus) {
            currentFile.value = currentStatus.current_file
            selectedFile.value = currentStatus.current_file
          }
          
        } catch (scanError) {
          console.warn('Failed to scan data directory:', scanError.message)
          availableFiles.value = []
          currentFolderPath.value = ''
          
          // Still try to set current file info from status
          if (currentStatus) {
            currentFile.value = currentStatus.current_file
            selectedFile.value = currentStatus.current_file
          }
        }
        
      } catch (error) {
        console.error('Failed to load available files:', error)
        availableFiles.value = []
        currentFile.value = ''
        selectedFile.value = ''
      }
    }
    
    const showFolderDialog = () => {
      showDialog.value = true
    }
    
    const handleDialogClose = () => {
      showDialog.value = false
    }
    
    const handleFolderSelected = (folderData) => {
      // Update the available files with the scanned JSON files
      availableFiles.value = folderData.jsonFiles
      currentFolderPath.value = folderData.folderPath
      
      // Clear current selection
      selectedFile.value = ''
      
      const count = folderData.count
      const scanType = folderData.scanType
      
      if (count === 0) {
        alert(`No JSON files found in the selected folder and its subdirectories`)
      } else {
        alert(`Found ${count} JSON file${count === 1 ? '' : 's'} in the selected folder (${scanType} scan)`)
      }
    }
    
    const handleFileSelection = async () => {
      if (!selectedFile.value) return
      
      loadingFile.value = true
      try {
        // All files now use the /api/load-file endpoint with full path
        const response = await axios.post('/api/load-file', {
          path: selectedFile.value
        })
        
        currentFile.value = response.data.current_file
        
        // Emit event to parent component
        emit('file-loaded', {
          filename: response.data.current_file,
          path: selectedFile.value
        })
        
      } catch (error) {
        console.error('Failed to load selected file:', error)
        alert(`Failed to load file: ${error.response?.data?.error || error.message}`)
      } finally {
        loadingFile.value = false
      }
    }
    
    const formatFileSize = (bytes) => {
      if (bytes === 0) return '0 B'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    }
    
    // Load available files on component mount
    onMounted(() => {
      loadAvailableFiles()
    })
    
    return {
      selectedFile,
      availableFiles,
      currentFile,
      currentFolderPath,
      loadingFile,
      showDialog,
      showFolderDialog,
      handleDialogClose,
      handleFolderSelected,
      handleFileSelection,
      formatFileSize
    }
  }
}
</script>

<style scoped>
.file-selector-section {
  background: #e3f2fd;
  border: 1px solid #bbdefb;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 30px;
}

.file-selector-section h2 {
  margin-top: 0;
  color: #1976d2;
}

.file-selector {
  display: flex;
  align-items: center;
  gap: 15px;
  flex-wrap: wrap;
}

.file-select {
  padding: 8px 12px;
  border: 1px solid #1976d2;
  border-radius: 4px;
  background: white;
  min-width: 200px;
}

.file-select:disabled {
  background: #f5f5f5;
  color: #9e9e9e;
  border-color: #e0e0e0;
  cursor: not-allowed;
}

.current-file {
  color: #2e7d32;
  font-size: 14px;
}

.loading-indicator {
  color: #ff9800;
  font-style: italic;
}

.no-file-indicator {
  color: #9e9e9e;
  font-style: italic;
  font-size: 14px;
}

.folder-selector {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #bbdefb;
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
