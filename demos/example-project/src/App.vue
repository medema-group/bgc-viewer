<template>
  <div>
    <header>
      <h1>BGC Viewer Components Demo</h1>
      <p class="subtitle">Interactive genomic track visualization with Vue.js</p>
    </header>

    <div class="tabs">
      <button 
        v-for="tab in tabs" 
        :key="tab.id"
        :class="['tab', { active: activeTab === tab.id }]"
        @click="activeTab = tab.id"
      >
        {{ tab.label }}
      </button>
    </div>

    <div v-if="error" class="error">
      {{ error }}
    </div>

    <div v-if="loading" class="loading">
      Loading data...
    </div>

    <template v-if="!loading && !error">
      <TrackViewerTab
        v-show="activeTab === 'trackviewer'"
        :records="records"
        :regions="currentRegions"
        :currentRecord="currentRecord"
        :currentRegion="currentRegion"
        v-model:recordIndex="selectedRecordIndex"
        v-model:regionIndex="selectedRegionIndex"
      />

      <RegionViewerTab
        v-show="activeTab === 'regionviewer'"
        :records="records"
        :regions="currentRegions"
        :currentRecord="currentRecord"
        :currentRegion="currentRegion"
        v-model:recordIndex="selectedRecordIndex"
        v-model:regionIndex="selectedRegionIndex"
      />

      <RegionViewerContainerTab
        v-show="activeTab === 'regionviewercontainer'"
        :records="records"
        :regions="currentRegions"
        :currentRecord="currentRecord"
        :currentRegion="currentRegion"
        :dataProvider="dataProvider"
        v-model:recordIndex="selectedRecordIndex"
        v-model:regionIndex="selectedRegionIndex"
      />
    </template>

    <footer>
      <p>
        Built with <a href="https://www.npmjs.com/package/@medemagroup/bgc-viewer-components" target="_blank">@medemagroup/bgc-viewer-components</a>
        | <a href="https://github.com/medema-group/bgc-viewer" target="_blank">GitHub</a>
      </p>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { JSONFileProvider } from '../../../frontend/dist/web-components/bgc-viewer-components.es.js'
// Import component styles
import './style.css'
import './style2.css'
import TrackViewerTab from './components/TrackViewerTab.vue'
import RegionViewerTab from './components/RegionViewerTab.vue'
import RegionViewerContainerTab from './components/RegionViewerContainerTab.vue'

const tabs = [
  { id: 'trackviewer', label: 'TrackViewer' },
  { id: 'regionviewer', label: 'RegionViewer' },
  { id: 'regionviewercontainer', label: 'RegionViewerContainer' }
]

const activeTab = ref('trackviewer')
const loading = ref(true)
const error = ref(null)
const jsonData = ref(null)
const records = ref([])
const selectedRecordIndex = ref(0)
const selectedRegionIndex = ref(0)
const dataProvider = ref(null)

const currentRecord = computed(() => {
  return records.value[selectedRecordIndex.value]
})

const currentRecordId = computed(() => {
  const record = currentRecord.value
  return record ? record.id : ''
})

const currentRegions = computed(() => {
  const record = currentRecord.value
  if (!record) return []
  
  // antiSMASH v7+ uses 'areas' instead of 'regions'
  if (record.areas) {
    return record.areas
  }
  
  // Older versions use 'regions'
  return record.regions || []
})

const currentRegion = computed(() => {
  return currentRegions.value[selectedRegionIndex.value]
})

const currentRegionId = computed(() => {
  const region = currentRegion.value
  if (!region) return ''
  // Try to find a region ID from the region data
  return region.id || `region_${selectedRegionIndex.value + 1}`
})

onMounted(async () => {
  await loadData()
})

async function loadData() {
  try {
    loading.value = true
    error.value = null

    const response = await fetch('/data/Y16952.json')
    if (!response.ok) {
      throw new Error(`Failed to load data: ${response.statusText}`)
    }

    jsonData.value = await response.json()
    records.value = jsonData.value.records || []

    if (records.value.length === 0) {
      throw new Error('No records found in data')
    }

    // Initialize JSONFileProvider with the loaded data
    dataProvider.value = new JSONFileProvider({ records: records.value })

    loading.value = false
  } catch (err) {
    error.value = err.message
    loading.value = false
    console.error('Error loading data:', err)
  }
}
</script>
