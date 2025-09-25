<template>
  <div class="container">
    <header>
      <h1>BGC Viewer</h1>
    </header>

    <main>
      <!-- File Selector Section -->
      <FileSelector 
        @file-loaded="handleFileLoaded" 
        @folder-selected="handleFolderSelected"
      />

      <!-- Record List Selector Section -->
      <RecordListSelector 
        :database-folder="selectedDatabaseFolder"
        @record-loaded="handleRecordLoaded" 
      />

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
import RecordListSelector from './components/RecordListSelector.vue'

export default {
  name: 'App',
  components: {
    RegionViewerComponent,
    FileSelector,
    RecordListSelector
  },
  setup() {
    const regionViewerRef = ref(null)
    
    // Version information
    const appVersion = ref('')
    const appName = ref('BGC Viewer')
    
    // Database folder tracking
    const selectedDatabaseFolder = ref('')
    
    const handleFileLoaded = async (fileData) => {
      // This method is for old file-based loading, now mostly unused
      console.log('File loaded:', fileData)
    }

    const handleFolderSelected = async (folderPath) => {
      // Update the selected database folder
      selectedDatabaseFolder.value = folderPath
    }

    const handleRecordLoaded = async (recordData) => {
      // Load the record into the RegionViewer component
      if (regionViewerRef.value) {
        await regionViewerRef.value.loadRecord(recordData)
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
      selectedDatabaseFolder,
      handleFileLoaded,
      handleFolderSelected,
      handleRecordLoaded
    }
  }
}
</script>

<style>
/* Global font styling to match backend */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body, 
html,
#app {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  line-height: 1.6;
  color: #333;
  background-color: #f4f4f4;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

header {
  text-align: center;
  margin-bottom: 40px;
  padding: 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}

header h1 {
  color: #2c3e50;
  margin-bottom: 10px;
}

.region-section {
  background: white;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 30px;
  margin-bottom: 30px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}

.region-section h2 {
  margin-top: 0;
  color: #2c3e50;
  border-bottom: 2px solid #3498db;
  padding-bottom: 10px;
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
