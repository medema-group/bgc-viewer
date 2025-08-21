<template>
  <div class="container">
    <header>
      <h1>BGC Viewer</h1>
    </header>

    <main>
      <!-- File Selector Section -->
      <section class="file-selector-section">
        <h2>Data File Selection</h2>
        <div class="folder-selector">
          <button @click="showFolderDialog = true" class="browse-button">
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
            @change="loadSelectedFile"
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
      </section>

      <!-- Folder Selection Modal -->
      <div v-if="showFolderDialog" class="modal-overlay" @click="closeFolderDialog">
        <div class="modal-dialog" @click.stop>
          <div class="modal-header">
            <h3>Select Folder</h3>
            <button class="close-button" @click="closeFolderDialog">&times;</button>
          </div>
          
          <div class="modal-body">
            <div class="quick-nav">
              <strong>Quick Navigation:</strong>
              <button @click="browsePath('/')" class="quick-nav-button">Root (/)</button>
              <button @click="browsePath('/Users')" class="quick-nav-button">Users</button>
              <button @click="browsePath('.')" class="quick-nav-button">Application dir</button>
            </div>
            
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
                    {{ item.type === 'directory' ? '📁' : '📄' }}
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
            <button @click="selectCurrentFolder" class="confirm-button" :disabled="!currentBrowserPath">
              Select This Folder
            </button>
            <button @click="closeFolderDialog" class="cancel-button">
              Cancel
            </button>
          </div>
        </div>
      </div>

      <!-- Region Viewer Section -->
      <section class="region-section">
        <h2>Region Visualization</h2>
        <RegionViewerComponent ref="regionViewerRef" />
      </section>
      
      <!-- API Testing Section -->
      <section class="api-section">
        <h2>API Endpoints</h2>
        <div class="endpoint-list">
          <div class="endpoint" v-for="endpoint in endpoints" :key="endpoint.path">
            <code>{{ endpoint.method }} {{ endpoint.path }}</code>
            <p>{{ endpoint.description }}</p>
            <button @click="fetchData(endpoint.url, endpoint.outputId)">Test</button>
          </div>
          
          <div class="endpoint">
            <code>GET /api/records/{record_id}/features?type={type}</code>
            <p>Get features by type for a specific record</p>
            <input 
              v-model="recordId" 
              type="text" 
              placeholder="Record ID" 
              class="input-field"
            >
            <input 
              v-model="featureType" 
              type="text" 
              placeholder="Feature Type (optional)" 
              class="input-field"
            >
            <button @click="fetchRecordFeatures">Test</button>
          </div>
        </div>
      </section>

      <section class="results-section">
        <h2>API Results</h2>
        <div 
          v-for="result in results" 
          :key="result.id" 
          :id="result.id" 
          class="output-box"
        >
          <h3>{{ result.title }}</h3>
          <pre :class="result.status">{{ result.content }}</pre>
        </div>
      </section>
    </main>
    
    <footer class="app-footer">
      <div class="version-info">
        <span v-if="appVersion">{{ appName }} v{{ appVersion }}</span>
        <span v-else>Loading version...</span>
      </div>
    </footer>
  </div>
</template>

<script>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'
import RegionViewerComponent from './components/RegionViewer.vue'

export default {
  name: 'App',
  components: {
    RegionViewerComponent
  },
  setup() {
    const recordId = ref('')
    const featureType = ref('')
    const selectedFile = ref('')
    const availableFiles = ref([])
    const currentFile = ref('')
    const loadingFile = ref(false)
    const regionViewerRef = ref(null)
    
    // Version information
    const appVersion = ref('')
    const appName = ref('BGC Viewer')
    
    // Folder browser state
    const showFolderDialog = ref(false)
    const currentBrowserPath = ref('')
    const currentFolderPath = ref('')
    const browserItems = ref([])
    const browserLoading = ref(false)
    const browserError = ref('')
    
    const endpoints = [
      { method: 'GET', path: '/api/status', url: '/api/status', description: 'Get current file and loading status', outputId: 'status-output' },
      { method: 'GET', path: '/api/info', url: '/api/info', description: 'Get dataset information and metadata', outputId: 'data-output' },
      { method: 'GET', path: '/api/records', url: '/api/records', description: 'Get all records (regions) summary', outputId: 'records-output' },
      { method: 'GET', path: '/api/records/{id}/regions', url: '', description: 'Get regions for a specific record', outputId: 'regions-output', dynamic: true },
      { method: 'GET', path: '/api/feature-types', url: '/api/feature-types', description: 'Get all available feature types', outputId: 'feature-types-output' },
      { method: 'GET', path: '/api/stats', url: '/api/stats', description: 'Get dataset statistics', outputId: 'stats-output' },
      { method: 'GET', path: '/api/health', url: '/api/health', description: 'Health check endpoint', outputId: 'health-output' }
    ]
    
    const results = reactive([
      { id: 'status-output', title: 'Current Status', content: 'Click "Test" buttons above to see API responses', status: '' },
      { id: 'data-output', title: 'Dataset Info', content: '', status: '' },
      { id: 'records-output', title: 'Records', content: '', status: '' },
      { id: 'regions-output', title: 'Regions', content: '', status: '' },
      { id: 'feature-types-output', title: 'Feature Types', content: '', status: '' },
      { id: 'stats-output', title: 'Dataset Statistics', content: '', status: '' },
      { id: 'health-output', title: 'Health Status', content: '', status: '' },
      { id: 'record-features-output', title: 'Record Features', content: '', status: '' }
    ])
    
    const fetchData = async (endpoint, outputId) => {
      const result = results.find(r => r.id === outputId)
      result.content = 'Loading...'
      result.status = 'loading'
      
      try {
        let url = endpoint
        
        // Handle dynamic endpoints that need a record ID
        if (!url && outputId === 'regions-output') {
          // First fetch records to get the first available record ID
          const recordsResponse = await axios.get('/api/records')
          const records = recordsResponse.data
          
          if (records.length === 0) {
            result.content = 'No records available'
            result.status = 'error'
            return
          }
          
          // Use the first record's ID to construct the regions URL
          const firstRecordId = records[0].id
          url = `/api/records/${encodeURIComponent(firstRecordId)}/regions`
        }
        
        const response = await axios.get(url)
        result.content = JSON.stringify(response.data, null, 2)
        result.status = response.status === 200 ? 'success' : 'error'
      } catch (error) {
        result.content = `Error: ${error.message}`
        result.status = 'error'
      }
    }
    
    const fetchRecordFeatures = async () => {
      if (!recordId.value) {
        alert('Please enter a record ID')
        return
      }
      
      let endpoint = `/api/records/${encodeURIComponent(recordId.value)}/features`
      if (featureType.value) {
        endpoint += `?type=${encodeURIComponent(featureType.value)}`
      }
      
      await fetchData(endpoint, 'record-features-output')
    }
    
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
    
    // Load available files on component mount
    onMounted(() => {
      loadAvailableFiles()
      browsePath('.') // Initialize folder browser
      fetchVersion() // Fetch application version
    })
    
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
      }
      // Remove file clicking functionality - now only for directory navigation
    }
    
    const closeFolderDialog = () => {
      showFolderDialog.value = false
    }
    
    const selectCurrentFolder = async () => {
      if (!currentBrowserPath.value) return
      
      try {
        loadingFile.value = true
        const response = await axios.post('/api/scan-folder', {
          path: currentBrowserPath.value
        })
        
        // Update the available files with the scanned JSON files
        availableFiles.value = response.data.json_files
        currentFolderPath.value = response.data.folder_path
        
        // Clear current selection
        selectedFile.value = ''
        
        // Close the dialog
        closeFolderDialog()
        
        const count = response.data.count
        const scanType = response.data.scan_type || 'recursive'
        
        if (count === 0) {
          alert(`No JSON files found in the selected folder and its subdirectories`)
        } else {
          alert(`Found ${count} JSON file${count === 1 ? '' : 's'} in the selected folder (${scanType} scan)`)
        }
        
      } catch (error) {
        alert(`Failed to scan folder: ${error.response?.data?.error || error.message}`)
      } finally {
        loadingFile.value = false
      }
    }
    
    const loadSelectedFile = async () => {
      if (!selectedFile.value) return
      
      loadingFile.value = true
      try {
        // All files now use the /api/load-file endpoint with full path
        const response = await axios.post('/api/load-file', {
          path: selectedFile.value
        })
        
        currentFile.value = response.data.current_file
        
        // Refresh all data outputs to reflect the new file
        await Promise.all([
          fetchData('/api/info', 'data-output'),
          fetchData('/api/records', 'records-output'),
          fetchData('/api/stats', 'stats-output')
        ])
        
        // Refresh the RegionViewer component
        if (regionViewerRef.value) {
          await regionViewerRef.value.refreshData()
        }
        
      } catch (error) {
        console.error('Failed to load selected file:', error)
        alert(`Failed to load file: ${error.response?.data?.error || error.message}`)
      } finally {
        loadingFile.value = false
      }
    }
    
    const fetchVersion = async () => {
      try {
        const response = await axios.get('/api/version')
        appVersion.value = response.data.version
        appName.value = response.data.name
      } catch (error) {
        console.warn('Failed to fetch version:', error)
        // Keep default values if fetch fails
      }
    }
    
    const formatFileSize = (bytes) => {
      if (bytes === 0) return '0 B'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    }
    
    return {
      recordId,
      featureType,
      selectedFile,
      availableFiles,
      currentFile,
      loadingFile,
      regionViewerRef,
      appVersion,
      appName,
      showFolderDialog,
      currentBrowserPath,
      currentFolderPath,
      browserItems,
      browserLoading,
      browserError,
      endpoints,
      results,
      fetchData,
      fetchRecordFeatures,
      loadSelectedFile,
      handleBrowserItemClick,
      formatFileSize,
      browsePath,
      closeFolderDialog,
      selectCurrentFolder
    }
  }
}
</script>

<style>
.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

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

/* Folder Browser Styles (within modal) */
.folder-browser {
  padding: 0 20px;
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
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

.folder-list {
  flex: 1;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: #fafafa;
  overflow-y: auto;
  min-height: 200px;
}

.folder-item {
  padding: 10px 15px;
  border-bottom: 1px solid #eee;
  cursor: pointer;
  display: flex;
  align-items: center;
}

.folder-item:hover {
  background: #e3f2fd;
}

.folder-item.selected {
  background: #bbdefb;
  color: #1976d2;
  font-weight: bold;
}

.folder-item:last-child {
  border-bottom: none;
}

.folder-item span {
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

.folder-browser {
  margin-top: 15px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: white;
}

.quick-nav {
  padding: 10px;
  background: #f8f9fa;
  border-bottom: 1px solid #ccc;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.quick-nav-button {
  background: #6c757d;
  color: white;
  border: none;
  padding: 4px 8px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 12px;
}

.quick-nav-button:hover {
  background: #5a6268;
}

.current-path {
  padding: 10px;
  background: #f5f5f5;
  border-bottom: 1px solid #ccc;
  font-size: 14px;
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

.endpoint-list {
  display: grid;
  gap: 20px;
  margin-bottom: 30px;
}

.endpoint {
  border: 1px solid #ddd;
  padding: 15px;
  border-radius: 8px;
}

.input-field {
  margin: 5px;
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.output-box {
  margin-bottom: 20px;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 15px;
}

.output-box pre {
  background: #f5f5f5;
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
}

.loading {
  color: #666;
  font-style: italic;
}

.error {
  color: #d32f2f;
  background: #ffebee !important;
}

.success {
  color: #2e7d32;
}

.region-section {
  background: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 30px;
}

.region-section h2 {
  margin-top: 0;
  color: #495057;
}

.app-footer {
  margin-top: 40px;
  padding: 20px 0;
  border-top: 1px solid #e0e0e0;
  text-align: center;
}

.version-info {
  color: #666;
  font-size: 0.9rem;
}

.version-info span {
  font-weight: 500;
}
</style>
