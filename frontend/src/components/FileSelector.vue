<template>
  <div class="file-selector" v-if="jsonFiles.length > 0">
    <div class="selector-header">
      <h3>Select Files for Preprocessing</h3>
      <p class="file-count">{{ jsonFiles.length }} JSON file{{ jsonFiles.length === 1 ? '' : 's' }} found</p>
    </div>
    
    <div class="selection-controls">
      <button @click="selectAll" class="control-button">Select All</button>
      <button @click="deselectAll" class="control-button">Deselect All</button>
      <span class="selection-count">{{ selectedCount }} of {{ jsonFiles.length }} selected</span>
    </div>
    
    <div class="file-list-container">
      <div class="file-list">
        <div 
          v-for="file in jsonFiles" 
          :key="file.path"
          class="file-item"
          :class="{ 'selected': selectedFiles[file.path] }"
        >
          <label class="file-label">
            <input 
              type="checkbox" 
              v-model="selectedFiles[file.path]"
              @change="updateSelection"
            />
            <span class="file-info">
              <span class="file-path">{{ file.relative_path }}</span>
              <span class="file-size">{{ formatFileSize(file.size) }}</span>
            </span>
          </label>
        </div>
      </div>
    </div>
    
    <div class="action-buttons">
      <button 
        @click="confirmSelection" 
        class="confirm-button"
        :disabled="selectedCount === 0"
      >
        Preprocess Selected Files ({{ selectedCount }})
      </button>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch } from 'vue'

export default {
  name: 'FileSelector',
  props: {
    jsonFiles: {
      type: Array,
      default: () => []
    }
  },
  emits: ['files-selected'],
  setup(props, { emit }) {
    const selectedFiles = ref({})
    
    // Initialize all files as selected by default
    const initializeSelection = () => {
      const selection = {}
      props.jsonFiles.forEach(file => {
        selection[file.path] = true
      })
      selectedFiles.value = selection
    }
    
    // Watch for changes in jsonFiles and reinitialize
    watch(() => props.jsonFiles, () => {
      initializeSelection()
    }, { immediate: true })
    
    const selectedCount = computed(() => {
      return Object.values(selectedFiles.value).filter(Boolean).length
    })
    
    const selectAll = () => {
      props.jsonFiles.forEach(file => {
        selectedFiles.value[file.path] = true
      })
    }
    
    const deselectAll = () => {
      props.jsonFiles.forEach(file => {
        selectedFiles.value[file.path] = false
      })
    }
    
    const updateSelection = () => {
      // This is triggered by checkbox changes
      // The reactive binding handles the update automatically
    }
    
    const confirmSelection = () => {
      const selected = props.jsonFiles.filter(file => selectedFiles.value[file.path])
      
      if (selected.length === 0) {
        return
      }
      
      emit('files-selected', selected)
    }
    
    const formatFileSize = (bytes) => {
      if (bytes === 0) return '0 B'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
    }
    
    return {
      selectedFiles,
      selectedCount,
      selectAll,
      deselectAll,
      updateSelection,
      confirmSelection,
      formatFileSize
    }
  }
}
</script>

<style scoped>
.file-selector {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
  margin: 20px 0;
}

.selector-header h3 {
  margin: 0 0 5px 0;
  color: #495057;
}

.file-count {
  margin: 0 0 15px 0;
  color: #6c757d;
  font-size: 14px;
}

.selection-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid #dee2e6;
}

.control-button {
  background: #fff;
  border: 1px solid #ced4da;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.control-button:hover {
  background: #e9ecef;
  border-color: #adb5bd;
}

.selection-count {
  margin-left: auto;
  color: #495057;
  font-size: 14px;
  font-weight: 500;
}

.file-list-container {
  max-height: 400px;
  overflow-y: auto;
  margin-bottom: 15px;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  background: white;
}

.file-list {
  display: flex;
  flex-direction: column;
}

.file-item {
  border-bottom: 1px solid #f1f3f5;
  transition: background-color 0.2s;
}

.file-item:last-child {
  border-bottom: none;
}

.file-item:hover {
  background-color: #f8f9fa;
}

.file-item.selected {
  background-color: #e7f5ff;
}

.file-label {
  display: flex;
  align-items: center;
  padding: 10px 15px;
  cursor: pointer;
  width: 100%;
}

.file-label input[type="checkbox"] {
  margin-right: 12px;
  cursor: pointer;
  flex-shrink: 0;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-grow: 1;
  min-width: 0;
}

.file-path {
  color: #495057;
  font-size: 13px;
  font-family: monospace;
  word-break: break-all;
  flex-grow: 1;
}

.file-size {
  color: #6c757d;
  font-size: 12px;
  white-space: nowrap;
  flex-shrink: 0;
}

.action-buttons {
  display: flex;
  gap: 10px;
  justify-content: flex-start;
  padding-top: 15px;
  border-top: 1px solid #dee2e6;
}

.confirm-button {
  background: #28a745;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
}

.confirm-button:hover:not(:disabled) {
  background: #218838;
}

.confirm-button:disabled {
  background: #6c757d;
  cursor: not-allowed;
  opacity: 0.6;
}

.cancel-button {
  background: #6c757d;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.cancel-button:hover {
  background: #5a6268;
}
</style>
