<template>
  <div class="preprocessing-status" v-if="showStatus">
    <div class="status-header">
      <h3>Data preprocessing</h3>
      <button @click="closeStatus" class="close-button" v-if="!isRunning">×</button>
    </div>
    
    <!-- Index Status Display -->
    <div v-if="indexStatus && !isRunning" class="index-status">
      <div v-if="indexStatus.has_index" class="index-exists">
        <div class="status-icon success">✓</div>
        <div class="status-text">
          <strong>Index found</strong>
          <div class="status-details">
            {{ indexStatus.index_stats?.indexed_files || 0 }} files indexed, 
            {{ indexStatus.index_stats?.total_records || 0 }} records
          </div>
          <div v-if="showVersionMismatch" class="version-warning">
            ⚠️ Index created with version {{ indexStatus.version || 'unknown' }} (current: {{ currentVersion }})
          </div>
        </div>
        <button @click="confirmRegenerateIndex" class="regenerate-button" title="Regenerate index">
          regenerate index
        </button>
      </div>
      
      <div v-else class="index-missing">
        <div class="status-icon warning">!</div>
        <div class="status-text">
          <strong>No index found</strong>
          <div class="status-details">
            {{ indexStatus.json_files_count }} JSON files available for preprocessing
          </div>
        </div>
      </div>
    </div>

    <!-- Preprocessing Progress -->
    <div v-if="isRunning" class="preprocessing-progress">
      <div class="progress-header">
        <LoadingSpinner color="#004085" style="width: 24px; height: 24px; border-width: 3px;" />
        <div class="status-text">
          <strong>Processing files...</strong>
          <div class="status-details">
            {{ progress.files_processed }} of {{ progress.total_files }} files processed
          </div>
        </div>
      </div>
      
      <div class="progress-bar">
        <div 
          class="progress-fill" 
          :style="{ width: progressPercentage + '%' }"
        ></div>
      </div>
      
      <div v-if="progress.current_file" class="current-file">
        Currently processing: <strong>{{ progress.current_file }}</strong>
      </div>
    </div>

    <!-- Error State -->
    <div v-if="hasError" class="preprocessing-error">
      <div class="status-icon error">✗</div>
      <div class="status-text">
        <strong>Preprocessing failed</strong>
        <div class="error-message">{{ progress.error_message }}</div>
      </div>
      <button @click="retryPreprocessing" class="retry-button">
        Retry
      </button>
    </div>

    <!-- Success State -->
    <div v-if="isCompleted" class="preprocessing-success">
      <div class="status-icon success">✓</div>
      <div class="status-text">
        <strong>Preprocessing completed!</strong>
        <div class="status-details">
          {{ progress.files_processed }} files processed successfully
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import axios from 'axios'
import LoadingSpinner from './LoadingSpinner.vue'

export default {
  name: 'PreprocessingStatus',
  components: {
    LoadingSpinner
  },
  props: {
    folderPath: {
      type: String,
      default: null
    },
    selectedFiles: {
      type: Array,
      default: null
    },
    indexPath: {
      type: String,
      default: null
    }
  },
  emits: ['preprocessing-completed', 'need-file-selection', 'index-status-changed'],
  setup(props, { emit }) {
    const showStatus = ref(false)
    const indexStatus = ref(null)
    const currentVersion = ref('')
    const progress = ref({
      is_running: false,
      current_file: null,
      files_processed: 0,
      total_files: 0,
      status: 'idle',
      error_message: null,
      folder_path: null
    })
    
    let statusInterval = null

    const isRunning = computed(() => progress.value.is_running)
    const hasError = computed(() => progress.value.status === 'error')
    const isCompleted = computed(() => progress.value.status === 'completed')
    
    const showVersionMismatch = computed(() => {
      if (!indexStatus.value || !indexStatus.value.version || !currentVersion.value) {
        return false
      }
      return indexStatus.value.version !== currentVersion.value
    })
    
    const progressPercentage = computed(() => {
      if (progress.value.total_files === 0) return 0
      return Math.round((progress.value.files_processed / progress.value.total_files) * 100)
    })
    
    const fetchVersion = async () => {
      try {
        const response = await axios.get('/api/version')
        currentVersion.value = response.data.version
      } catch (error) {
        console.error('Failed to fetch version:', error)
      }
    }

    const checkIndexStatus = async () => {
      if (!props.folderPath) return
      
      try {
        const response = await axios.post('/api/check-index', {
          path: props.folderPath
        })
        indexStatus.value = response.data
        showStatus.value = true
        
        // Emit index status to parent
        emit('index-status-changed', response.data)
        
        // Automatically show file selection if no index exists
        if (!response.data.has_index && response.data.can_preprocess) {
          showFileSelection()
        }
      } catch (error) {
        console.error('Failed to check index status:', error)
      }
    }

    const showFileSelection = () => {
      // Emit event to parent to show file selection dialog
      emit('need-file-selection', indexStatus.value)
    }

    const startPreprocessing = async (filePaths = null) => {
      if (!props.folderPath) return
      
      try {
        const requestData = {
          path: props.folderPath
        }
        
        // Include selected file paths if provided
        if (filePaths && filePaths.length > 0) {
          requestData.files = filePaths
        }
        
        // Include custom index path if specified
        if (props.indexPath) {
          requestData.index_path = props.indexPath
        }
        
        await axios.post('/api/preprocess-folder', requestData)
        
        // Start polling for status updates
        startStatusPolling()
        
      } catch (error) {
        console.error('Failed to start preprocessing:', error)
        alert(`Failed to start preprocessing: ${error.response?.data?.error || error.message}`)
      }
    }

    const startStatusPolling = () => {
      if (statusInterval) clearInterval(statusInterval)
      
      statusInterval = setInterval(async () => {
        try {
          const response = await axios.get('/api/preprocessing-status')
          progress.value = response.data
          
          // Stop polling when preprocessing is complete or errored
          if (!response.data.is_running) {
            clearInterval(statusInterval)
            statusInterval = null
            
            if (response.data.status === 'completed') {
              // Refresh index status
              setTimeout(() => {
                checkIndexStatus()
                emit('preprocessing-completed')
              }, 1000)
            }
          }
        } catch (error) {
          console.error('Failed to get preprocessing status:', error)
          clearInterval(statusInterval)
          statusInterval = null
        }
      }, 1000)
    }

    const retryPreprocessing = () => {
      progress.value.status = 'idle'
      progress.value.error_message = null
      if (props.selectedFiles && props.selectedFiles.length > 0) {
        const filePaths = props.selectedFiles.map(f => f.path)
        startPreprocessing(filePaths)
      } else {
        startPreprocessing()
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
            path: props.folderPath
          })
          
          // Refresh the index status which will show "no index found" state
          // and automatically trigger file selection
          await checkIndexStatus()
          
        } catch (error) {
          console.error('Failed to drop database:', error)
          alert(`Failed to drop database: ${error.response?.data?.error || error.message}`)
        }
      }
    }

    const closeStatus = () => {
      showStatus.value = false
    }

    // Watch for folder path changes
    const checkFolder = () => {
      if (props.folderPath) {
        checkIndexStatus()
      } else {
        showStatus.value = false
        indexStatus.value = null
      }
    }

    onMounted(() => {
      fetchVersion()
      checkFolder()
    })

    onUnmounted(() => {
      if (statusInterval) {
        clearInterval(statusInterval)
      }
    })

    // Watch for folder path changes
    watch(() => props.folderPath, () => {
      checkFolder()
    })

    return {
      showStatus,
      indexStatus,
      progress,
      isRunning,
      hasError,
      isCompleted,
      progressPercentage,
      showVersionMismatch,
      currentVersion,
      showFileSelection,
      startPreprocessing,
      retryPreprocessing,
      confirmRegenerateIndex,
      closeStatus
    }
  }
}
</script>

<style scoped>
.preprocessing-status {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
  margin: 20px 0;
}

.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.status-header h3 {
  margin: 0;
  color: #495057;
}

.close-button {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: #6c757d;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-button:hover {
  color: #495057;
}

.index-status, .preprocessing-progress, .preprocessing-error, .preprocessing-success {
  display: flex;
  align-items: center;
  gap: 15px;
}

.index-exists, .index-missing {
  display: flex;
  align-items: center;
  gap: 15px;
  width: 100%;
}

.status-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  flex-shrink: 0;
}

.status-icon.success {
  background: #d4edda;
  color: #155724;
}

.status-icon.warning {
  background: #fff3cd;
  color: #856404;
}

.status-icon.error {
  background: #f8d7da;
  color: #721c24;
}



.status-text {
  flex: 1;
}

.status-details {
  font-size: 14px;
  color: #6c757d;
  margin-top: 4px;
}

.version-warning {
  font-size: 13px;
  color: #856404;
  margin-top: 6px;
  padding: 4px 8px;
  background: #fff3cd;
  border-radius: 4px;
  display: inline-block;
}

.regenerate-button {
  background: #6c757d;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  flex-shrink: 0;
  transition: background 0.2s;
}

.regenerate-button:hover {
  background: #5a6268;
}

.preprocess-button, .retry-button {
  background: #007bff;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.preprocess-button:hover, .retry-button:hover {
  background: #0056b3;
}

.preprocess-button:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: #e9ecef;
  border-radius: 4px;
  overflow: hidden;
  margin: 10px 0;
}

.progress-fill {
  height: 100%;
  background: #007bff;
  transition: width 0.3s ease;
}

.current-file {
  font-size: 14px;
  color: #495057;
  margin-top: 8px;
}

.error-message {
  font-size: 14px;
  color: #721c24;
  margin-top: 4px;
  font-family: monospace;
}

.progress-header {
  display: flex;
  align-items: center;
  gap: 15px;
  width: 100%;
}

.preprocessing-progress {
  flex-direction: column;
  align-items: stretch;
}
</style>
