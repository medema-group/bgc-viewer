<template>
  <section class="folder-selector-section">
    <div class="current-index-section">
      <h2>Current index</h2>
      
      <div v-if="currentIndexPath || currentFolderPath" class="index-info">
        <div class="info-row" v-if="currentIndexPath">
          <span class="info-label">Index file:</span>
          <span class="info-value">{{ currentIndexPath }}</span>
        </div>
        <div class="info-row" v-if="currentFolderPath">
          <span class="info-label">Data root:</span>
          <span class="info-value">{{ currentFolderPath }}</span>
        </div>
        <div class="info-row" v-if="indexStats">
          <span class="info-label">Records:</span>
          <span class="info-value">
            {{ indexStats.indexed_files || 0 }} files, 
            {{ indexStats.total_records || 0 }} records
          </span>
        </div>
        <div class="info-row" v-if="currentVersion && indexVersion">
          <span class="info-label">Version:</span>
          <span class="info-value">
            {{ indexVersion }}
            <span v-if="showVersionMismatch" class="version-warning-inline">
              ⚠️ (current: {{ currentVersion }})
            </span>
          </span>
        </div>
      </div>
      
      <div v-else class="no-index-message">
        <p>No index selected. Select an existing index file or create a new one from a folder.</p>
      </div>
      
      <div class="action-buttons">
        <button @click="showSelectIndexDialog" class="browse-button">
          Select existing index file
        </button>
        <button @click="showSelectFolderDialog" class="browse-button browse-button-secondary">
          Select folder to index
        </button>
        <button 
          v-if="currentFolderPath" 
          @click="confirmRegenerateIndex" 
          class="regenerate-button"
          title="Delete current index and create a new one"
        >
          Regenerate index
        </button>
      </div>
    </div>

    <!-- Dialog for selecting existing index file -->
    <FolderSelectionDialog 
      :show="showIndexDialog"
      title="Select an index file"
      :initial-path="getIndexDirectory()"
      :allow-folder-selection="false"
      :allow-database-selection="true"
      @close="handleIndexDialogClose"
      @folder-selected="handleIndexFileSelected"
    />
    
    <!-- Dialog for selecting folder to index -->
    <FolderSelectionDialog 
      :show="showFolderDialog"
      title="Select a folder to index"
      :initial-path="''"
      :allow-folder-selection="true"
      :allow-database-selection="false"
      @close="handleFolderDialogClose"
      @folder-selected="handleFolderToIndexSelected"
    />
  </section>
</template>

<script>
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
import FolderSelectionDialog from './FolderSelectionDialog.vue'

export default {
  name: 'IndexSelection',
  components: {
    FolderSelectionDialog
  },
  emits: ['folder-selected', 'folder-changed', 'index-changed', 'create-index-for-folder'],
  setup(_, { emit }) {
    const currentFolderPath = ref('')
    const currentIndexPath = ref('')
    const indexStats = ref(null)
    const indexVersion = ref('')
    const currentVersion = ref('')
    const showIndexDialog = ref(false)
    const showFolderDialog = ref(false)
    
    const STORAGE_KEY = 'bgc-viewer-last-index-path'
    
    const showVersionMismatch = computed(() => {
      if (!indexVersion.value || !currentVersion.value) {
        return false
      }
      return indexVersion.value !== currentVersion.value
    })
    
    const getIndexDirectory = () => {
      // Extract directory from index file path for browsing
      if (!currentIndexPath.value) return ''
      const lastSlash = currentIndexPath.value.lastIndexOf('/')
      return lastSlash > 0 ? currentIndexPath.value.substring(0, lastSlash) : ''
    }
    
    const fetchVersion = async () => {
      try {
        const response = await axios.get('/api/version')
        currentVersion.value = response.data.version
      } catch (error) {
        console.error('Failed to fetch version:', error)
      }
    }
    
    const showSelectIndexDialog = () => {
      showIndexDialog.value = true
    }
    
    const handleIndexDialogClose = () => {
      showIndexDialog.value = false
    }
    
    const showSelectFolderDialog = () => {
      showFolderDialog.value = true
    }
    
    const handleFolderDialogClose = () => {
      showFolderDialog.value = false
    }
    
    const saveLastIndexPath = (indexPath) => {
      try {
        localStorage.setItem(STORAGE_KEY, indexPath)
        console.log('Saved index path to localStorage:', indexPath)
      } catch (error) {
        console.warn('Failed to save last index path to localStorage:', error)
      }
    }
    
    const loadLastIndexPath = () => {
      try {
        const savedIndexPath = localStorage.getItem(STORAGE_KEY)
        console.log('Loaded index path from localStorage:', savedIndexPath)
        return savedIndexPath
      } catch (error) {
        console.warn('Failed to load last index path from localStorage:', error)
        return null
      }
    }
    
    const tryDefaultIndexPath = async () => {
      // First try to use the last remembered index path
      const lastIndexPath = loadLastIndexPath()
      if (lastIndexPath) {
        try {
          const response = await axios.post('/api/select-database', {
            path: lastIndexPath
          })
          
          if (response.data.database_path) {
            currentIndexPath.value = response.data.database_path
            currentFolderPath.value = response.data.data_root
            indexStats.value = response.data.index_stats
            indexVersion.value = response.data.version || ''
            
            // Emit events
            emit('folder-changed', currentFolderPath.value)
            emit('folder-selected', currentFolderPath.value)
            emit('index-changed', currentIndexPath.value)
            
            console.log('Restored last used index path:', lastIndexPath)
            return // Successfully restored, no need to try default
          }
        } catch (lastIndexError) {
          console.warn('Failed to restore last used index path:', lastIndexError.message)
        }
      }
      
      // If no saved index or saved index failed, try the default location
      try {
        const defaultIndexPath = '../data/attributes.db'
        const response = await axios.post('/api/select-database', {
          path: defaultIndexPath
        })
        
        if (response.data.database_path) {
          currentIndexPath.value = response.data.database_path
          currentFolderPath.value = response.data.data_root
          indexStats.value = response.data.index_stats
          indexVersion.value = response.data.version || ''
          
          // Save the default index path for next time
          saveLastIndexPath(response.data.database_path)
          
          // Emit events
          emit('folder-changed', currentFolderPath.value)
          emit('folder-selected', currentFolderPath.value)
          emit('index-changed', currentIndexPath.value)
          
          console.log('Using default index path:', defaultIndexPath)
        }
      } catch (defaultError) {
        console.warn('Failed to load default index:', defaultError.message)
        console.log('No index selected - user will need to select one manually')
      }
    }
    
    const handleIndexFileSelected = (folderData) => {
      // This handles selecting an existing index file
      if (folderData.isDatabaseSelection) {
        const stats = folderData.indexStats
        currentIndexPath.value = folderData.folderPath
        indexStats.value = stats
        indexVersion.value = folderData.version || ''
        // Extract data root from the database
        currentFolderPath.value = folderData.dataRoot || folderData.folderPath
        
        // Save the selected index path for next time
        saveLastIndexPath(currentIndexPath.value)
        
        // Emit events
        emit('folder-changed', currentFolderPath.value)
        emit('folder-selected', currentFolderPath.value)
        emit('index-changed', folderData.folderPath)
        
        showIndexDialog.value = false
      }
    }
    
    const handleFolderToIndexSelected = async (folderData) => {
      // This handles selecting a folder to create a new index
      if (!folderData.isDatabaseSelection) {
        const folderPath = folderData.folderPath
        const count = folderData.count
        
        if (count === 0) {
          alert(`No JSON files found in the selected folder and its subdirectories`)
          return
        }
        
        // Fetch the list of JSON files from the API
        try {
          const response = await axios.post('/api/scan-folder', {
            path: folderPath
          })
          
          if (response.data.json_files && response.data.json_files.length > 0) {
            // Emit event to parent to show IndexCreation component
            emit('create-index-for-folder', {
              folderPath: folderPath,
              files: {
                availableFiles: response.data.json_files,
                isLoadingFiles: false,
                needsPreprocessing: true
              }
            })
          } else {
            alert('No JSON files found in the selected folder')
          }
        } catch (error) {
          console.error('Failed to fetch JSON files:', error)
          alert(`Failed to fetch file list: ${error.response?.data?.error || error.message}`)
        }
        
        showFolderDialog.value = false
      }
    }
    
    const confirmRegenerateIndex = async () => {
      const confirmed = window.confirm(
        'Are you sure you want to regenerate the index?\n\n' +
        'This will overwrite the existing database and allow you to select which files to reprocess.\n\n' +
        'Click OK to continue or Cancel to abort.'
      )
      
      if (confirmed) {
        try {
          const folderPath = currentFolderPath.value
          const indexFilePath = currentIndexPath.value
          
          // Fetch the list of JSON files from the API
          try {
            const response = await axios.post('/api/scan-folder', {
              path: folderPath
            })
            
            if (response.data.json_files && response.data.json_files.length > 0) {
              // Emit event to parent to show IndexCreation component
              emit('create-index-for-folder', {
                folderPath: folderPath,
                indexPath: indexFilePath,
                files: {
                  availableFiles: response.data.json_files,
                  isLoadingFiles: false,
                  needsPreprocessing: true
                }
              })
            } else {
              alert('No JSON files found in the selected folder')
            }
          } catch (error) {
            console.error('Failed to fetch JSON files:', error)
            alert(`Failed to fetch file list: ${error.response?.data?.error || error.message}`)
          }
          
        } catch (error) {
          console.error('Failed to regenerate index:', error)
          alert(`Failed to regenerate index: ${error.message}`)
        }
      }
    }
    
    // Try to load default index path on component mount
    onMounted(() => {
      fetchVersion()
      tryDefaultIndexPath()
    })
    
    return {
      currentFolderPath,
      currentIndexPath,
      indexStats,
      indexVersion,
      currentVersion,
      showVersionMismatch,
      showIndexDialog,
      showFolderDialog,
      getIndexDirectory,
      showSelectIndexDialog,
      handleIndexDialogClose,
      showSelectFolderDialog,
      handleFolderDialogClose,
      handleIndexFileSelected,
      handleFolderToIndexSelected,
      confirmRegenerateIndex
    }
  }
}
</script>

<style scoped>
.folder-selector-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 15px;
  border-bottom: 1px solid #e0e0e0;
}

/* Current Index Section */
.current-index-section {
  background: #e3f2fd;
  border: 1px solid #bbdefb;
  border-radius: 6px;
  padding: 12px;
}

.current-index-section h2 {
  margin-top: 0;
  margin-bottom: 10px;
  color: #1976d2;
  font-size: 16px;
}

.index-info {
  background: white;
  border: 1px solid #bbdefb;
  border-radius: 4px;
  padding: 10px;
  margin-bottom: 10px;
}

.info-row {
  display: flex;
  margin-bottom: 6px;
}

.info-row:last-child {
  margin-bottom: 0;
}

.info-label {
  font-weight: 500;
  color: #495057;
  min-width: 90px;
  font-size: 13px;
  flex-shrink: 0;
}

.info-value {
  color: #212529;
  font-size: 13px;
  word-break: break-all;
}

.no-index-message {
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 4px;
  padding: 10px;
  margin-bottom: 10px;
}

.no-index-message p {
  margin: 0;
  color: #856404;
  font-size: 13px;
}

.action-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.regenerate-button {
  background: #dc3545;
  color: white;
  border: none;
  padding: 8px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.2s;
}

.regenerate-button:hover {
  background: #c82333;
}

.version-warning-inline {
  color: #856404;
  font-size: 12px;
  margin-left: 8px;
}

/* Buttons */
.browse-button {
  background: #1976d2;
  color: white;
  border: none;
  padding: 8px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.2s;
}

.browse-button:hover {
  background: #1565c0;
}

.browse-button-secondary {
  background: #6c757d;
}

.browse-button-secondary:hover {
  background: #5a6268;
}
</style>
