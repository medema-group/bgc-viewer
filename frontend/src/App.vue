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
import { ref, onMounted } from 'vue'
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
    const regionViewerRef = ref(null)
    
    // Version information
    const appVersion = ref('')
    const appName = ref('BGC Viewer')
    
    const handleFileLoaded = async (fileData) => {
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
    
    // Fetch application version on component mount
    onMounted(() => {
      fetchVersion()
    })
    
    return {
      regionViewerRef,
      appVersion,
      appName,
      handleFileLoaded
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
