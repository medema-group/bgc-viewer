<template>
  <div class="container">
    <header>
      <h1>BGC Viewer</h1>
    </header>

    <main>
      <!-- Folder Selector Section - Only shown in local mode -->
      <FolderSelector 
        v-if="!isPublicMode"
        @folder-selected="handleFolderSelected"
        @folder-changed="handleFolderChanged"
        @index-changed="handleIndexChanged"
      />

      <!-- Record List Selector Section -->
      <RecordListSelector 
        ref="recordListSelectorRef"
        :data-root="selectedDataRoot"
        @record-loaded="handleRecordLoaded" 
      />

      <!-- Region Viewer Section -->
      <section class="region-section">
        <h2>Record Visualization</h2>
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
import FolderSelector from './components/FolderSelector.vue'
import RecordListSelector from './components/RecordListSelector.vue'

export default {
  name: 'App',
  components: {
    RegionViewerComponent,
    FolderSelector,
    RecordListSelector
  },
  setup() {
    const regionViewerRef = ref(null)
    const recordListSelectorRef = ref(null)
    
    // Version information
    const appVersion = ref('')
    const appName = ref('BGC Viewer')
    
    // Mode information
    const isPublicMode = ref(true) // Default to true for safety
    
    // Data root tracking
    const selectedDataRoot = ref('')
    
    const handleFolderSelected = async (folderPath) => {
      // Update the selected data root
      selectedDataRoot.value = folderPath
    }

    const handleFolderChanged = async (folderPath) => {
      // Clear the record list immediately when folder changes
      if (recordListSelectorRef.value) {
        recordListSelectorRef.value.clearRecords()
      }
      // Update the selected data root
      selectedDataRoot.value = folderPath
    }

    const handleIndexChanged = async (folderPath) => {
      // Update the data root to ensure it's in sync
      selectedDataRoot.value = folderPath
      // Refresh the record list when index has changed
      if (recordListSelectorRef.value) {
        await recordListSelectorRef.value.refreshEntries()
      }
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
    
    const fetchStatus = async () => {
      try {
        const response = await axios.get('/api/status')
        isPublicMode.value = response.data.public_mode
        console.log('Running in', isPublicMode.value ? 'PUBLIC' : 'LOCAL', 'mode')
      } catch (error) {
        console.warn('Failed to fetch status:', error)
        // Default to public mode for safety if fetch fails
        isPublicMode.value = true
      }
    }
    
    // Fetch application version and status on component mount
    onMounted(() => {
      fetchVersion()
      fetchStatus()
    })
    
    return {
      regionViewerRef,
      recordListSelectorRef,
      appVersion,
      appName,
      isPublicMode,
      selectedDataRoot,
      handleFolderSelected,
      handleFolderChanged,
      handleIndexChanged,
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
