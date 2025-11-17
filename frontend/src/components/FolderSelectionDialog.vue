<template>
  <div v-if="show" class="modal-overlay" @click="handleOverlayClick">
    <div class="modal-dialog" @click.stop>
      <div class="modal-header">
        <h3>{{ title }}</h3>
        <button class="close-button" @click="closeDialog">&times;</button>
      </div>
      
      <div class="modal-body">
        <div class="current-path">
          <strong>Current path:</strong> {{ currentBrowserPath || '.' }}
        </div>
        
        <div class="folder-contents">
          <div v-if="browserLoading" class="loading">Loading...</div>
          <div v-else-if="browserError" class="error">{{ browserError }}</div>
          <div v-else>
            <div 
              v-for="item in browserItems" 
              :key="item.path"
              :class="['browser-item', item.type]"
              @click="handleBrowserItemClick(item)"
            >
              <span class="item-icon">
                {{ item.type === 'directory' ? '📁' : item.type === 'database' ? '💾' : '📄' }}
              </span>
              <span class="item-name">{{ item.name }}</span>
              <span v-if="item.size" class="item-size">
                ({{ formatFileSize(item.size) }})
              </span>
            </div>
          </div>
        </div>
      </div>
      
      <div class="modal-footer">
        <button 
          v-if="allowFolderSelection"
          @click="selectCurrentFolder" 
          class="confirm-button" 
          :disabled="!currentBrowserPath"
        >
          Select this folder
        </button>
        <button @click="closeDialog" class="cancel-button">
          Cancel
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, watch } from 'vue'
import axios from 'axios'

export default {
  name: 'FolderSelectionDialog',
  props: {
    show: {
      type: Boolean,
      default: false
    },
    title: {
      type: String,
      default: 'Select folder or index file'
    },
    initialPath: {
      type: String,
      default: ''
    },
    allowFolderSelection: {
      type: Boolean,
      default: true
    },
    allowDatabaseSelection: {
      type: Boolean,
      default: true
    }
  },
  emits: ['close', 'folder-selected'],
  setup(props, { emit }) {
    const currentBrowserPath = ref('')
    const browserItems = ref([])
    const browserLoading = ref(false)
    const browserError = ref('')
    
    const browsePath = async (path) => {
      browserLoading.value = true
      browserError.value = ''
      
      try {
        const response = await axios.get('/api/browse', {
          params: { path: path }
        })
        
        currentBrowserPath.value = response.data.current_path
        browserItems.value = response.data.items
        
      } catch (error) {
        browserError.value = `Failed to browse path: ${error.response?.data?.error || error.message}`
      } finally {
        browserLoading.value = false
      }
    }
    
    const handleBrowserItemClick = async (item) => {
      if (item.type === 'directory') {
        await browsePath(item.path)
      } else if (item.type === 'database' && props.allowDatabaseSelection) {
        // Handle database file selection
        await selectDatabaseFile(item.path)
      }
    }
    
    const closeDialog = () => {
      emit('close')
    }
    
    const handleOverlayClick = () => {
      closeDialog()
    }
    
    const selectCurrentFolder = async () => {
      if (!currentBrowserPath.value) return
      
      try {
        const response = await axios.post('/api/scan-folder', {
          path: currentBrowserPath.value
        })
        
        emit('folder-selected', {
          folderPath: response.data.folder_path,
          jsonFiles: response.data.json_files,
          count: response.data.count,
          scanType: response.data.scan_type || 'recursive'
        })
        
        closeDialog()
        
      } catch (error) {
        alert(`Failed to scan folder: ${error.response?.data?.error || error.message}`)
      }
    }
    
    const selectDatabaseFile = async (dbPath) => {
      try {
        const response = await axios.post('/api/select-database', {
          path: dbPath
        })
        
        // Emit database selection with data_root as the folder path
        emit('folder-selected', {
          folderPath: dbPath,  // The database file path itself
          dataRoot: response.data.data_root,  // The data root directory
          databasePath: response.data.database_path,
          indexStats: response.data.index_stats,
          version: response.data.version,  // Include version from backend
          isDatabaseSelection: true
        })
        
        closeDialog()
        
      } catch (error) {
        alert(`Failed to select database: ${error.response?.data?.error || error.message}`)
      }
    }
    
    const formatFileSize = (bytes) => {
      if (bytes === 0) return '0 B'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    }
    
    // Initialize folder browser when dialog is shown
    watch(() => props.show, (newValue) => {
      if (newValue) {
        // Use initial path if provided, otherwise use current directory
        const pathToOpen = props.initialPath || '.'
        browsePath(pathToOpen)
      }
    })
    
    return {
      currentBrowserPath,
      browserItems,
      browserLoading,
      browserError,
      allowFolderSelection: props.allowFolderSelection,
      browsePath,
      handleBrowserItemClick,
      closeDialog,
      handleOverlayClick,
      selectCurrentFolder,
      selectDatabaseFile,
      formatFileSize
    }
  }
}
</script>

<style scoped>
/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-dialog {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 600px;
  max-height: 80%;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #eee;
}

.modal-header h3 {
  margin: 0;
}

.close-button {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  padding: 0;
  width: 30px;
  height: 30px;
}

.modal-body {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 0 20px;
}

.modal-footer {
  padding: 20px;
  border-top: 1px solid #eee;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.confirm-button {
  background: #1976d2;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
}

.confirm-button:hover:not(:disabled) {
  background: #1565c0;
}

.confirm-button:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.cancel-button {
  background: #6c757d;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
}

.cancel-button:hover {
  background: #5a6268;
}

.current-path {
  background: #f5f5f5;
  padding: 10px;
  border-radius: 4px;
  font-family: monospace;
  margin-bottom: 15px;
  font-size: 14px;
}

.quick-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 15px;
}

.quick-nav-button {
  background: #e3f2fd;
  border: 1px solid #90caf9;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  color: #1976d2;
}

.quick-nav-button:hover {
  background: #bbdefb;
}

.folder-contents {
  max-height: 300px;
  overflow-y: auto;
}

.browser-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  cursor: pointer;
  border-bottom: 1px solid #eee;
}

.browser-item:hover {
  background: #f8f9fa;
}

.browser-item.directory {
  font-weight: 500;
}

.browser-item.database {
  font-weight: 500;
  color: #1976d2;
}

.browser-item.file {
  color: #666;
}

.item-icon {
  margin-right: 8px;
  font-size: 16px;
}

.item-name {
  flex: 1;
}

.item-size {
  font-size: 12px;
  color: #888;
}

.loading {
  color: #666;
  font-style: italic;
  padding: 20px;
  text-align: center;
}

.error {
  color: #d32f2f;
  background: #ffebee;
  padding: 15px;
  border-radius: 4px;
  margin: 10px 0;
}
</style>
