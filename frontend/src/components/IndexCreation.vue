<template>
  <div class="index-creation-section">
    <div class="header-with-cancel">
      <h2>Create new index</h2>
      <button @click="handleCancel" class="cancel-button" title="Cancel index creation">
        ✕
      </button>
    </div>
    <p class="section-description">
      Creating index for: <strong>{{ folderPath }}</strong>
    </p>
    
    <PreprocessingStatus 
      :folder-path="folderPath"
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

    <!-- Dialog for selecting index path -->
    <FolderSelectionDialog 
      :show="showIndexPathDialogFlag"
      @close="handleIndexPathDialogClose"
      @folder-selected="handleIndexPathSelected"
    />
  </div>
</template>

<script>
import { ref, computed } from 'vue'
import FolderSelectionDialog from './FolderSelectionDialog.vue'
import PreprocessingStatus from './PreprocessingStatus.vue'
import FileSelector from './FileSelector.vue'
import LoadingSpinner from './LoadingSpinner.vue'

export default {
  name: 'IndexCreation',
  components: {
    FolderSelectionDialog,
    PreprocessingStatus,
    FileSelector,
    LoadingSpinner
  },
  props: {
    folderPath: {
      type: String,
      required: true
    },
    availableFiles: {
      type: Array,
      default: () => []
    },
    isLoadingFiles: {
      type: Boolean,
      default: false
    },
    needsPreprocessing: {
      type: Boolean,
      default: false
    }
  },
  emits: ['preprocessing-completed', 'cancel'],
  setup(props, { emit }) {
    const selectedFiles = ref([])
    const preprocessingStatusRef = ref(null)
    const showIndexPathDialogFlag = ref(false)
    const indexPath = ref(`${props.folderPath}/attributes.db`)
    const isPreprocessingRunning = ref(false)
    
    const defaultIndexPath = computed(() => {
      return `${props.folderPath}/attributes.db`
    })
    
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
    
    const handlePreprocessingCompleted = () => {
      emit('preprocessing-completed', indexPath.value)
    }
    
    const handleCancel = () => {
      emit('cancel')
    }
    
    const handleFilesSelected = (files) => {
      selectedFiles.value = files
      
      // Trigger preprocessing with selected files
      if (preprocessingStatusRef.value) {
        const filePaths = files.map(f => f.path)
        preprocessingStatusRef.value.startPreprocessing(filePaths)
      }
    }
    
    return {
      selectedFiles,
      preprocessingStatusRef,
      showIndexPathDialogFlag,
      indexPath,
      defaultIndexPath,
      isPreprocessingRunning,
      showIndexPathDialog,
      handleIndexPathDialogClose,
      handleIndexPathSelected,
      handlePreprocessingCompleted,
      handleFilesSelected,
      handleCancel
    }
  }
}
</script>

<style scoped>
.index-creation-section {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
}

.index-creation-section h2 {
  margin-top: 0;
  margin-bottom: 10px;
  color: #495057;
}

.header-with-cancel {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.cancel-button {
  background: transparent;
  border: none;
  font-size: 24px;
  color: #6c757d;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s;
}

.cancel-button:hover {
  background: #e9ecef;
  color: #495057;
}

.section-description {
  color: #6c757d;
  font-size: 14px;
  margin-bottom: 15px;
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
</style>
