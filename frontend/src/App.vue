<template>
  <div class="container">
    <header>
      <h1>BGC Viewer</h1>
    </header>

    <main>
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
import { ref, reactive } from 'vue'
import axios from 'axios'

export default {
  name: 'App',
  setup() {
    const recordId = ref('')
    const featureType = ref('')
    
    const endpoints = [
      { method: 'GET', path: '/api/info', url: '/api/info', description: 'Get dataset information and metadata', outputId: 'data-output' },
      { method: 'GET', path: '/api/records', url: '/api/records', description: 'Get all records (regions) summary', outputId: 'records-output' },
      { method: 'GET', path: '/api/feature-types', url: '/api/feature-types', description: 'Get all available feature types', outputId: 'feature-types-output' },
      { method: 'GET', path: '/api/stats', url: '/api/stats', description: 'Get dataset statistics', outputId: 'stats-output' },
      { method: 'GET', path: '/api/health', url: '/api/health', description: 'Health check endpoint', outputId: 'health-output' }
    ]
    
    const results = reactive([
      { id: 'data-output', title: 'Dataset Info', content: 'Click "Test" buttons above to see API responses', status: '' },
      { id: 'records-output', title: 'Records', content: '', status: '' },
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
        const response = await axios.get(endpoint)
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
    
    return {
      recordId,
      featureType,
      endpoints,
      results,
      fetchData,
      fetchRecordFeatures
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
</style>
