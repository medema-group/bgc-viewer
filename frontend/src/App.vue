<template>
  <div class="container">
    <header>
      <h1>BGC Viewer</h1>
    </header>

    <main>
      <!-- File Selector Section -->
      <FileSelector @file-loaded="handleFileLoaded" />

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
import FileSelector from './components/FileSelector.vue'

export default {
  name: 'App',
  components: {
    RegionViewerComponent,
    FileSelector
  },
  setup() {
    const recordId = ref('')
    const featureType = ref('')
    const regionViewerRef = ref(null)
    
    // Version information
    const appVersion = ref('')
    const appName = ref('BGC Viewer')
    
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
    
    const handleFileLoaded = async (fileData) => {
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
    
    // Fetch application version on component mount
    onMounted(() => {
      fetchVersion()
    })
    
    return {
      recordId,
      featureType,
      regionViewerRef,
      appVersion,
      appName,
      endpoints,
      results,
      fetchData,
      fetchRecordFeatures,
      handleFileLoaded,
      formatFileSize
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
