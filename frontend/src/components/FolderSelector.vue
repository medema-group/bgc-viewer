<template>
  <section class="folder-selector-section">
    <!-- Section 1: Current Index and Data Root -->
    <div class="current-index-section">
      <h2>Current Index</h2>
      
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

    <!-- Section 2: Preprocessing (only shown when a folder is selected for indexing) -->
    <div v-if="selectedFolderForIndexing" class="preprocessing-section">
      <h2>Create new index</h2>
      <p class="section-description">
        Creating index for: <strong>{{ selectedFolderForIndexing }}</strong>
      </p>
      
      <PreprocessingStatus 
        :folder-path="selectedFolderForIndexing"
        :selected-files="selectedFiles"
        :index-path="indexPath"
        @preprocessing-completed="handlePreprocessingCompleted"
        @preprocessing-started="isPreprocessingRunning = true"
        @preprocessing-stopped="isPreprocessingRunning = false"
        ref="preprocessingStatusRef"
      />
      
      <div v-if="needsPreprocessing && !isPreprocessingRunning" class="index-location-section">
        <h3>Index file location</h3>
        <div class="index-location-row">
          <label class="index-label">Index file path:</label>
          <input 
            v-model="indexPath" 
            type="text" 
            class="index-path-input"
            :placeholder="`${selectedFolderForIndexing}/attributes.db`"
          />
          <button @click="showIndexPathDialog" class="change-button">
            Browse
          </button>
        </div>
      </div>
      
      <div v-if="isLoadingFiles" class="loading-files">
        <LoadingSpinner color="#1976d2" style="width: 32px; height: 32px; border-width: 3px;" />
        <span class="loading-text">Loading file list...</span>
      </div>
      
      <FileSelector 
        v-if="needsPreprocessing && !isPreprocessingRunning"
        :json-files="availableFiles"
        @files-selected="handleFilesSelected"
      />
    </div>

    <!-- Dialog for selecting existing index file -->
    <FolderSelectionDialog 
      :show="showIndexDialog"
      :initial-path="getIndexDirectory()"
      :allow-folder-selection="false"
      :allow-database-selection="true"
      @close="handleIndexDialogClose"
      @folder-selected="handleIndexFileSelected"
    />
    
    <!-- Dialog for selecting folder to index -->
    <FolderSelectionDialog 
      :show="showFolderDialog"
      :initial-path="selectedFolderForIndexing || ''"
      :allow-folder-selection="true"
      :allow-database-selection="false"
      @close="handleFolderDialogClose"
      @folder-selected="handleFolderToIndexSelected"
    />

    <FolderSelectionDialog 
      :show="showIndexPathDialogFlag"
      @close="handleIndexPathDialogClose"
      @folder-selected="handleIndexPathSelected"
    />
  </section>
</template>

<script>
import { ref, onMounted, watch, computed } from 'vue'
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
  emits: ['folder-selected', 'folder-changed', 'index-changed'],
  setup(_, { emit }) {
    const currentFolderPath = ref('')
    const currentIndexPath = ref('')
    const indexStats = ref(null)
    const indexVersion = ref('')
    const currentVersion = ref('')
    const showIndexDialog = ref(false)
    const showFolderDialog = ref(false)
    const selectedFolderForIndexing = ref('')
    const folderRestoredFromMemory = ref(false)
    const isLoadingFiles = ref(false)
    const availableFiles = ref([])
    const selectedFiles = ref([])
    const preprocessingStatusRef = ref(null)
    const showIndexPathDialogFlag = ref(false)
    const indexPath = ref('')
    const needsPreprocessing = ref(false)
    const isPreprocessingRunning = ref(false)
    
    const STORAGE_KEY = 'bgc-viewer-last-index-path'
    
    const showVersionMismatch = computed(() => {
      if (!indexVersion.value || !currentVersion.value) {
        return false
      }
      return indexVersion.value !== currentVersion.value
    })
    
    // Watch for selected folder changes to reset file selector
    watch(selectedFolderForIndexing, (newValue, oldValue) => {
      // Only reset if we're clearing the folder or switching from one folder to another
      // Don't reset when initially setting a folder (oldValue is empty)
      if (newValue !== oldValue && oldValue !== '') {
        // Hide file selector when folder changes
        needsPreprocessing.value = false
        isLoadingFiles.value = false
        availableFiles.value = []
        selectedFiles.value = []
        // Reset index path to use data root by default
        indexPath.value = ''
      }
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
    
    const showIndexPathDialog = () => {
      showIndexPathDialogFlag.value = true
    }
    
    const handleIndexPathDialogClose = () => {
      showIndexPathDialogFlag.value = false
    }
    
    const handleIndexPathSelected = (folderData) => {
      // Only accept folder selections for index path, not database files
      if (!folderData.isDatabaseSelection) {
        // Set the index path to the selected folder + /attributes.db
        indexPath.value = `${folderData.folderPath}/attributes.db`
        showIndexPathDialogFlag.value = false
        console.log('Index path set to:', indexPath.value)
      } else {
        alert('Please select a folder for the index location, not a database file.')
      }
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
            folderRestoredFromMemory.value = true
            
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
          folderRestoredFromMemory.value = false
          
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
        
        // Clear preprocessing section
        selectedFolderForIndexing.value = ''
        needsPreprocessing.value = false
        
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
        selectedFolderForIndexing.value = folderData.folderPath
        folderRestoredFromMemory.value = false
        
        // Don't save to localStorage yet - wait until index is created
        
        const count = folderData.count
        
        if (count === 0) {
          alert(`No JSON files found in the selected folder and its subdirectories`)
          selectedFolderForIndexing.value = ''
          return
        }
        
        // Fetch the list of JSON files from the API
        isLoadingFiles.value = true
        needsPreprocessing.value = true
        
        try {
          const response = await axios.post('/api/scan-folder', {
            path: folderData.folderPath
          })
          
          if (response.data.json_files && response.data.json_files.length > 0) {
            availableFiles.value = response.data.json_files
          } else {
            alert('No JSON files found in the selected folder')
            selectedFolderForIndexing.value = ''
            needsPreprocessing.value = false
          }
        } catch (error) {
          console.error('Failed to fetch JSON files:', error)
          alert(`Failed to fetch file list: ${error.response?.data?.error || error.message}`)
          selectedFolderForIndexing.value = ''
          needsPreprocessing.value = false
        } finally {
          isLoadingFiles.value = false
        }
        
        showFolderDialog.value = false
      }
    }
    

    
    const handlePreprocessingCompleted = async () => {
      // Clear file selection
      needsPreprocessing.value = false
      selectedFiles.value = []
      availableFiles.value = []
      
      // Set current index path based on indexPath or default
      const newIndexPath = indexPath.value || `${selectedFolderForIndexing.value}/attributes.db`
      
      // Update current folder path
      const newDataRoot = selectedFolderForIndexing.value
      
      try {
        // Select the newly created database via the API
        const response = await axios.post('/api/select-database', {
          path: newIndexPath
        })
        
        if (response.data.database_path) {
          currentIndexPath.value = response.data.database_path
          currentFolderPath.value = response.data.data_root
          indexStats.value = response.data.index_stats
          indexVersion.value = response.data.version || ''
          
          // Save the new index path for next time
          saveLastIndexPath(currentIndexPath.value)
          
          // Clear preprocessing section
          selectedFolderForIndexing.value = ''
          
          // Emit events that index has changed after preprocessing
          emit('folder-changed', currentFolderPath.value)
          emit('folder-selected', currentFolderPath.value)
          emit('index-changed', currentIndexPath.value)
        } else {
          throw new Error('No database path returned from server')
        }
      } catch (error) {
        console.error('Failed to select database after preprocessing:', error)
        alert(`Failed to activate new database: ${error.response?.data?.error || error.message}`)
        
        // Clear preprocessing section on error
        selectedFolderForIndexing.value = ''
      }
    }
    
    const handleFilesSelected = (files) => {
      selectedFiles.value = files
      
      // Trigger preprocessing with selected files
      if (preprocessingStatusRef.value) {
        const filePaths = files.map(f => f.path)
        preprocessingStatusRef.value.startPreprocessing(filePaths)
      }
    }
    
    const confirmRegenerateIndex = async () => {
      const confirmed = window.confirm(
        'Are you sure you want to regenerate the index?\n\n' +
        'This will delete the existing database and allow you to select which files to reprocess.\n\n' +
        'Click OK to continue or Cancel to abort.'
      )
      
      if (confirmed) {
        try {
          // Drop the database
          await axios.post('/api/drop-database', {
            path: currentFolderPath.value
          })
          
          // Move current folder to preprocessing section
          selectedFolderForIndexing.value = currentFolderPath.value
          
          // Clear current index section
          currentIndexPath.value = ''
          indexStats.value = null
          indexVersion.value = ''
          
          // Fetch the list of JSON files from the API
          isLoadingFiles.value = true
          needsPreprocessing.value = true
          
          try {
            const response = await axios.post('/api/scan-folder', {
              path: currentFolderPath.value
            })
            
            if (response.data.json_files && response.data.json_files.length > 0) {
              availableFiles.value = response.data.json_files
            } else {
              alert('No JSON files found in the selected folder')
              selectedFolderForIndexing.value = ''
              needsPreprocessing.value = false
            }
          } catch (error) {
            console.error('Failed to fetch JSON files:', error)
            alert(`Failed to fetch file list: ${error.response?.data?.error || error.message}`)
            selectedFolderForIndexing.value = ''
            needsPreprocessing.value = false
          } finally {
            isLoadingFiles.value = false
          }
          
        } catch (error) {
          console.error('Failed to drop database:', error)
          alert(`Failed to drop database: ${error.response?.data?.error || error.message}`)
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
      selectedFolderForIndexing,
      folderRestoredFromMemory,
      getIndexDirectory,
      showSelectIndexDialog,
      handleIndexDialogClose,
      showSelectFolderDialog,
      handleFolderDialogClose,
      handleIndexFileSelected,
      handleFolderToIndexSelected,
      handlePreprocessingCompleted,
      handleFilesSelected,
      confirmRegenerateIndex,
      isLoadingFiles,
      availableFiles,
      selectedFiles,
      preprocessingStatusRef,
      showIndexPathDialogFlag,
      indexPath,
      showIndexPathDialog,
      handleIndexPathDialogClose,
      handleIndexPathSelected,
      needsPreprocessing,
      isPreprocessingRunning
    }
  }
}
</script>

<style scoped>
.folder-selector-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-bottom: 30px;
}

/* Current Index Section */
.current-index-section {
  background: #e3f2fd;
  border: 1px solid #bbdefb;
  border-radius: 8px;
  padding: 20px;
}

.current-index-section h2 {
  margin-top: 0;
  margin-bottom: 15px;
  color: #1976d2;
}

.index-info {
  background: white;
  border: 1px solid #bbdefb;
  border-radius: 6px;
  padding: 15px;
  margin-bottom: 15px;
}

.info-row {
  display: flex;
  margin-bottom: 8px;
}

.info-row:last-child {
  margin-bottom: 0;
}

.info-label {
  font-weight: 500;
  color: #495057;
  min-width: 100px;
  font-size: 14px;
}

.info-value {
  color: #212529;
  font-size: 14px;
  word-break: break-all;
}

.no-index-message {
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 6px;
  padding: 15px;
  margin-bottom: 15px;
}

.no-index-message p {
  margin: 0;
  color: #856404;
  font-size: 14px;
}

.action-buttons {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.regenerate-button {
  background: #dc3545;
  color: white;
  border: none;
  padding: 10px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.regenerate-button:hover {
  background: #c82333;
}

.version-warning-inline {
  color: #856404;
  font-size: 13px;
  margin-left: 8px;
}

/* Preprocessing Section */
.preprocessing-section {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
}

.preprocessing-section h2 {
  margin-top: 0;
  margin-bottom: 10px;
  color: #495057;
}

.section-description {
  color: #6c757d;
  font-size: 14px;
  margin-bottom: 15px;
}

/* Buttons */
.browse-button {
  background: #1976d2;
  color: white;
  border: none;
  padding: 10px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
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

/* Loading Files */
.loading-files {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px;
  background: white;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  margin-top: 20px;
}

.loading-text {
  color: #495057;
  font-size: 14px;
}

/* Index Location Section */
.index-location-section {
  margin-top: 20px;
  padding: 15px;
  background: white;
  border: 1px solid #dee2e6;
  border-radius: 8px;
}

.index-location-section h3 {
  margin-top: 0;
  margin-bottom: 15px;
  color: #495057;
  font-size: 16px;
}

.index-location-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.index-label {
  font-weight: 500;
  color: #495057;
  min-width: 120px;
  font-size: 14px;
}

.index-path-input {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  font-size: 13px;
  font-family: monospace;
}

.index-path-input:focus {
  outline: none;
  border-color: #1976d2;
  box-shadow: 0 0 0 2px rgba(25, 118, 210, 0.1);
}

.change-button {
  background: #6c757d;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  white-space: nowrap;
  transition: background 0.2s;
}

.change-button:hover {
  background: #5a6268;
}
</style>
