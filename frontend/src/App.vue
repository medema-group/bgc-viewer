<template>
  <div class="container">
    <header>
      <h1>BGC Viewer</h1>
    </header>

    <main>
      <!-- File Selector Section -->
      <section class="file-selector-section">
        <h2>Data File Selection</h2>
        <div class="file-selector">
          <label for="file-select">Choose JSON file:</label>
          <select 
            id="file-select" 
            v-model="selectedFile" 
            @change="loadSelectedFile"
            class="file-select"
          >
            <option value="" disabled>Select a file...</option>
            <option 
              v-for="file in availableFiles" 
              :key="file" 
              :value="file"
            >
              {{ file }}
            </option>
          </select>
          <span v-if="currentFile" class="current-file">
            Currently loaded: <strong>{{ currentFile }}</strong>
          </span>
          <span v-if="loadingFile" class="loading-indicator">Loading...</span>
        </div>
      </section>

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
    
    const endpoints = [
      { method: 'GET', path: '/api/files', url: '/api/files', description: 'Get available files and current file', outputId: 'files-output' },
      { method: 'GET', path: '/api/info', url: '/api/info', description: 'Get dataset information and metadata', outputId: 'data-output' },
      { method: 'GET', path: '/api/records', url: '/api/records', description: 'Get all records (regions) summary', outputId: 'records-output' },
      { method: 'GET', path: '/api/records/{id}/regions', url: '', description: 'Get regions for a specific record', outputId: 'regions-output', dynamic: true },
      { method: 'GET', path: '/api/feature-types', url: '/api/feature-types', description: 'Get all available feature types', outputId: 'feature-types-output' },
      { method: 'GET', path: '/api/stats', url: '/api/stats', description: 'Get dataset statistics', outputId: 'stats-output' },
      { method: 'GET', path: '/api/health', url: '/api/health', description: 'Health check endpoint', outputId: 'health-output' }
    ]
    
    const results = reactive([
      { id: 'files-output', title: 'Available Files', content: 'Click "Test" buttons above to see API responses', status: '' },
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
        const response = await axios.get('/api/files')
        availableFiles.value = response.data.available_files
        currentFile.value = response.data.current_file
        selectedFile.value = response.data.current_file
      } catch (error) {
        console.error('Failed to load available files:', error)
      }
    }
    
    const loadSelectedFile = async () => {
      if (!selectedFile.value) return
      
      loadingFile.value = true
      try {
        const response = await axios.post(`/api/files/${encodeURIComponent(selectedFile.value)}`)
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
        
        alert(`Successfully loaded ${selectedFile.value}`)
      } catch (error) {
        console.error('Failed to load selected file:', error)
        alert(`Failed to load ${selectedFile.value}: ${error.message}`)
      } finally {
        loadingFile.value = false
      }
    }
    
    // Load available files on component mount
    onMounted(() => {
      loadAvailableFiles()
    })
    
    return {
      recordId,
      featureType,
      selectedFile,
      availableFiles,
      currentFile,
      loadingFile,
      regionViewerRef,
      endpoints,
      results,
      fetchData,
      fetchRecordFeatures,
      loadSelectedFile
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

.current-file {
  color: #2e7d32;
  font-size: 14px;
}

.loading-indicator {
  color: #ff9800;
  font-style: italic;
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
</style>
