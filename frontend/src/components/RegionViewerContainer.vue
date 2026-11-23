<template>
  <div class="region-viewer-container">
    <div v-if="loading" class="loading-container">
      <LoadingSpinner color="#1976d2" style="width: 48px; height: 48px; border-width: 4px;" />
      <p class="loading-text">Loading record data...</p>
    </div>
    <RegionViewer
      v-else-if="recordInfo"
      :record-info="recordInfo"
      :regions="regions"
      :features="features"
      :pfam-color-map="pfamColorMap"
      :selected-region-id="selectedRegionId"
      :selected-protocluster-number="initialProtoclusterNumber"
      :data-provider="dataProvider"
      :tfbs-hits="tfbsHits"
      :tta-codons="ttaCodons"
      :resistance-features="resistanceFeatures"
      @region-changed="handleRegionChanged"
      @annotation-clicked="handleAnnotationClicked"
      @error="handleError"
    />
  </div>
</template>

<script>
import { ref, watch, onMounted } from 'vue'
import RegionViewer from './RegionViewer.vue'
import LoadingSpinner from './LoadingSpinner.vue'

export default {
  name: 'RegionViewerContainer',
  components: {
    RegionViewer,
    LoadingSpinner
  },
  props: {
    // Data provider instance (optional, defaults to BGCViewerAPIProvider)
    dataProvider: {
      type: Object,
      default: null
    },
    // Record ID to load (can be changed dynamically)
    recordId: {
      type: String,
      default: ''
    },
    // Full record data of the selected record (includes entryId, recordId, filename for API provider)
    recordData: {
      type: Object,
      default: null
    },
    // Initial region ID to select (optional)
    initialRegionId: {
      type: String,
      default: ''
    },
    // Number of a protocluster to zoom to instead of the region (optional)
    initialProtoclusterNumber: {
      type: Number,
      default: null
    }
  },
  emits: [
    'region-changed',
    'annotation-clicked',
    'error'
  ],
  setup(props, { emit }) {
    const provider = ref(null)
    const recordInfo = ref(null)
    const regions = ref([])
    const features = ref([])
    const pfamColorMap = ref({})
    const tfbsHits = ref([])
    const ttaCodons = ref([])
    const resistanceFeatures = ref([])
    const selectedRegionId = ref('')
    const loading = ref(false)
    const error = ref('')
    const currentLoadingRequestId = ref(0)

    // Helper functions (defined before watchers to avoid hoisting issues)
    const clearViewer = () => {
      recordInfo.value = null
      regions.value = []
      features.value = []
      tfbsHits.value = []
      ttaCodons.value = []
      resistanceFeatures.value = []
      selectedRegionId.value = ''
    }

    const loadColorMap = async () => {
      if (!provider.value) return
      try {
        pfamColorMap.value = await provider.value.getPfamColorMap()
        console.log('Loaded PFAM colors for', Object.keys(pfamColorMap.value).length, 'domains')
      } catch (err) {
        console.warn('Failed to load PFAM color mapping:', err.message)
      }
    }

    // TFBS hits are stored per region, so load them for every region of the record
    const loadTFBSHits = async (recordId, recordRegions) => {
      if (!provider.value) return
      try {
        const tfbsData = await Promise.all(recordRegions.map(region =>
          provider.value.getTFBSHits(recordId, String(region.region_number))
        ))
        tfbsHits.value = tfbsData.flatMap(data => data.hits || [])
        console.log('Loaded', tfbsHits.value.length, 'TFBS binding sites for record', recordId)
      } catch (err) {
        console.warn('Failed to load TFBS hits:', err.message)
        tfbsHits.value = [] // Clear on error
      }
    }

    const loadTTACodons = async (recordId) => {
      if (!provider.value) return
      try {
        const ttaData = await provider.value.getTTACodons(recordId)
        ttaCodons.value = ttaData.codons || []
        console.log('Loaded', ttaCodons.value.length, 'TTA codons for record', recordId)
      } catch (err) {
        console.warn('Failed to load TTA codons:', err.message)
        ttaCodons.value = [] // Clear on error
      }
    }

    const loadResistanceFeatures = async (recordId) => {
      if (!provider.value) return
      try {
        const resistanceData = await provider.value.getResistanceFeatures(recordId)
        resistanceFeatures.value = resistanceData.features || []
        console.log('Loaded', resistanceFeatures.value.length, 'resistance features for record', recordId)
      } catch (err) {
        console.warn('Failed to load resistance features:', err.message)
        resistanceFeatures.value = [] // Clear on error
      }
    }

    const loadRecord = async (recordId) => {
      // Increment request ID to track this specific load request
      const requestId = ++currentLoadingRequestId.value
      
      // Clear current data immediately and show loading
      clearViewer()
      loading.value = true
      error.value = ''
      
      try {
        if (!provider.value) {
          throw new Error('No data provider available')
        }

        // Use the entryId which is always in format "filename:recordId"
        const entryId = props.recordData?.entryId
        
        // Get record info with description
        const entryInfo = await provider.value.loadEntry(entryId)
        
        // Check if this request is still the latest one
        if (requestId !== currentLoadingRequestId.value) {
          console.log('Ignoring stale load request for', recordId)
          return // Ignore this response - a newer request has been made
        }
        
        recordInfo.value = {
          entryId: entryInfo.entryId,  // Full unique ID in format "filename:recordId"
          recordId: entryInfo.recordId,  // Just the record ID part
          filename: entryInfo.filename,
          fileMetadata: entryInfo.fileMetadata,
          recordInfo: entryInfo.recordInfo
        }
        
        // Get regions (use entryId for unique identification)
        const regionsData = await provider.value.getRegions(recordInfo.value.entryId)
        
        // Check again after async operation
        if (requestId !== currentLoadingRequestId.value) {
          console.log('Ignoring stale load request for', recordId)
          return
        }
        
        regions.value = regionsData.regions || []
        
        // Load TTA codons (not region-specific)
        await loadTTACodons(recordInfo.value.entryId)
        
        // Check again after async operation
        if (requestId !== currentLoadingRequestId.value) {
          console.log('Ignoring stale load request for', recordId)
          return
        }
        
        // Load resistance features (not region-specific)
        await loadResistanceFeatures(recordInfo.value.entryId)
        
        // Check again after async operation
        if (requestId !== currentLoadingRequestId.value) {
          console.log('Ignoring stale load request for', recordId)
          return
        }
        
        // Load TFBS hits for all regions
        await loadTFBSHits(recordInfo.value.entryId, regions.value)

        // Check again after async operation
        if (requestId !== currentLoadingRequestId.value) {
          console.log('Ignoring stale load request for', recordId)
          return
        }

        // Always load the whole record; selecting a region only zooms the viewer to it
        await loadFeatures(recordInfo.value.entryId)

        if (regions.value.length > 0) {
          selectedRegionId.value = props.initialRegionId && regions.value.some(r => r.id === props.initialRegionId)
            ? props.initialRegionId
            : regions.value[0].id
        }
        
        // Final check before marking as loaded
        if (requestId !== currentLoadingRequestId.value) {
          console.log('Ignoring stale load request for', recordId)
          return
        }
        
        loading.value = false
      } catch (err) {
        // Only update error if this is still the current request
        if (requestId === currentLoadingRequestId.value) {
          console.error('Error loading record:', err)
          error.value = `Failed to load record: ${err.message}`
          emit('error', error.value)
          loading.value = false
        }
      }
    }

    const loadFeatures = async (recordId) => {
      try {
        const featuresData = await provider.value.getRecordFeatures(recordId)
        features.value = featuresData.features || []
      } catch (err) {
        console.error('Error loading features:', err)
        error.value = `Failed to load features: ${err.message}`
        emit('error', error.value)
      }
    }

    const handleRegionChanged = (regionId) => {
      // The viewer zooms to the selected region itself; all features are already loaded
      selectedRegionId.value = regionId
      emit('region-changed', regionId)
    }

    const handleAnnotationClicked = (data) => {
      emit('annotation-clicked', data)
    }

    const handleError = (err) => {
      emit('error', err)
    }

    onMounted(async () => {
      // Use provided data provider (required)
      if (!props.dataProvider) {
        error.value = 'No data provider specified. Please set the dataProvider property.'
        emit('error', error.value)
        return
      }
      provider.value = props.dataProvider
      
      // Load PFAM color map
      await loadColorMap()
      
      // Load record if recordId is provided
      if (props.recordId) {
        await loadRecord(props.recordId)
      }
    })

    // Watch for recordId changes
    watch(() => props.recordId, async (newRecordId, oldRecordId) => {
      if (newRecordId && provider.value) {
        await loadRecord(newRecordId)
      } else if (!newRecordId && oldRecordId !== undefined) {
        // Clear viewer when recordId is changed to empty (but not on initial mount)
        clearViewer()
      }
    }, { immediate: true })

    // Watch for dataProvider changes
    watch(() => props.dataProvider, (newProvider) => {
      if (newProvider) {
        provider.value = newProvider
        // Reload color map with new provider
        loadColorMap()
      }
    })

    // Watch for initialRegionId changes
    watch(() => props.initialRegionId, (newRegionId) => {
      if (newRegionId && regions.value.length > 0) {
        selectedRegionId.value = newRegionId
      }
    })

    return {
      recordInfo,
      regions,
      features,
      pfamColorMap,
      tfbsHits,
      ttaCodons,
      resistanceFeatures,
      selectedRegionId,
      loading,
      error,
      handleRegionChanged,
      handleAnnotationClicked,
      handleError
    }
  }
}
</script>

<style scoped>
.region-viewer-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 20px;
  background: white;
  border-radius: 8px;
  padding: 40px;
}

.loading-text {
  color: #666;
  font-size: 16px;
  font-weight: 500;
}
</style>
