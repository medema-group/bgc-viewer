<template>
  <div class="preprocessing-status" v-if="showStatus">
    <div class="status-header">
      <h3>Data preprocessing</h3>
      <button @click="closeStatus" class="close-button" v-if="!isRunning">×</button>
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
import { ref, computed, onUnmounted } from 'vue'
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
  emits: ['preprocessing-completed', 'preprocessing-started', 'preprocessing-stopped'],
  setup(props, { emit }) {
    const showStatus = ref(false)
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
    
    const progressPercentage = computed(() => {
      if (progress.value.total_files === 0) return 0
      return Math.round((progress.value.files_processed / progress.value.total_files) * 100)
    })

    const startPreprocessing = async (filePaths = null) => {
      if (!props.folderPath) return
      
      // Show the status section when preprocessing starts
      showStatus.value = true
      
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
        
        // Emit that preprocessing has started
        emit('preprocessing-started')
        
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
            
            // Emit that preprocessing has stopped
            emit('preprocessing-stopped')
            
            if (response.data.status === 'completed') {
              // Emit completion event
              emit('preprocessing-completed')
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
    
    const closeStatus = () => {
      showStatus.value = false
    }

    onUnmounted(() => {
      if (statusInterval) {
        clearInterval(statusInterval)
      }
    })

    return {
      showStatus,
      progress,
      isRunning,
      hasError,
      isCompleted,
      progressPercentage,
      startPreprocessing,
      retryPreprocessing,
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

.preprocessing-progress, .preprocessing-error, .preprocessing-success {
  display: flex;
  align-items: center;
  gap: 15px;
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

.retry-button {
  background: #007bff;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.retry-button:hover {
  background: #0056b3;
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
