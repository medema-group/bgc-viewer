<template>
  <div class="region-viewer-container">
    <RegionViewer
      :record-info="recordInfo"
      :regions="regions"
      :features="features"
      :region-boundaries="regionBoundaries"
      :pfam-color-map="pfamColorMap"
      :selected-region-id="selectedRegionId"
      @region-changed="handleRegionChanged"
      @annotation-clicked="handleAnnotationClicked"
      @error="handleError"
    />
  </div>
</template>

<script>
import { ref, watch, onMounted } from 'vue'
import RegionViewer from './RegionViewer.vue'

export default {
  name: 'RegionViewerContainer',
  components: {
    RegionViewer
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
    // Full record data from RecordListSelector (includes entryId, recordId, filename for API provider)
    recordData: {
      type: Object,
      default: null
    },
    // Initial region ID to select (optional)
    initialRegionId: {
      type: String,
      default: ''
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
    const regionBoundaries = ref(null)
    const pfamColorMap = ref({})
    const selectedRegionId = ref('')
    const loading = ref(false)
    const error = ref('')

    onMounted(async () => {
      // Use provided data provider (required)
      if (!props.dataProvider) {
        error.value = 'No data provider specified. Please set the dataProvider property.'
        emit('error', error.value)
        return
      }
      provider.value = props.dataProvider
      
      // Load PFAM color map
      try {
        pfamColorMap.value = await provider.value.getPfamColorMap()
        console.log('Loaded PFAM colors for', Object.keys(pfamColorMap.value).length, 'domains')
      } catch (err) {
        console.warn('Failed to load PFAM color mapping:', err.message)
      }
    })

    // Watch for recordId changes
    watch(() => props.recordId, async (newRecordId) => {
      if (newRecordId && provider.value) {
        await loadRecord(newRecordId)
      } else if (!newRecordId) {
        // Clear viewer when recordId is empty
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
        if (recordInfo.value) {
          loadRegionFeatures(recordInfo.value.recordId, newRegionId)
        }
      }
    })

    const loadColorMap = async () => {
      if (!provider.value) return
      try {
        pfamColorMap.value = await provider.value.getPfamColorMap()
      } catch (err) {
        console.warn('Failed to load PFAM color mapping:', err.message)
      }
    }

    const clearViewer = () => {
      recordInfo.value = null
      regions.value = []
      features.value = []
      regionBoundaries.value = null
      selectedRegionId.value = ''
    }

    const loadRecord = async (recordId) => {
      loading.value = true
      error.value = ''
      selectedRegionId.value = ''
      
      try {
        // First, load the entry through the provider to set up session and get metadata
        // If recordData is provided, use the entryId; otherwise use recordId as entryId
        const entryId = props.recordData?.entryId || recordId
        const recordMetadata = await provider.value.loadEntry(entryId)
        
        // Use the metadata from the provider
        recordInfo.value = {
          recordId: recordMetadata.recordId,
          filename: recordMetadata.filename,
          recordInfo: recordMetadata.recordInfo
        }

        // Load regions for the record
        const regionsResponse = await provider.value.getRegions(recordInfo.value.recordId)
        regions.value = regionsResponse.regions

        console.log('Loaded regions:', regions.value.length)

        // If regions are found and no initial region is set, select the first one
        if (regions.value.length > 0 && !selectedRegionId.value) {
          selectedRegionId.value = regions.value[0].id
          await loadRegionFeatures(recordInfo.value.recordId, selectedRegionId.value)
        } else if (selectedRegionId.value) {
          await loadRegionFeatures(recordInfo.value.recordId, selectedRegionId.value)
        } else {
          // No regions found, load all features
          await loadAllFeatures(recordInfo.value.recordId)
        }
      } catch (err) {
        error.value = `Failed to load record: ${err.message}`
        emit('error', err)
        console.error('Error loading record:', err)
      } finally {
        loading.value = false
      }
    }

    const loadAllFeatures = async (recordId) => {
      try {
        const response = await provider.value.getRecordFeatures(recordId)
        features.value = response.features
        regionBoundaries.value = null
        console.log('Loaded', features.value.length, 'features')
      } catch (err) {
        error.value = `Failed to load features: ${err.message}`
        emit('error', err)
        throw err
      }
    }

    const loadRegionFeatures = async (recordId, regionId) => {
      try {
        const response = await provider.value.getRegionFeatures(recordId, regionId)
        features.value = response.features
        regionBoundaries.value = response.region_boundaries
        console.log('Loaded', features.value.length, 'features for region', regionId)
      } catch (err) {
        error.value = `Failed to load region features: ${err.message}`
        emit('error', err)
        throw err
      }
    }

    const handleRegionChanged = async (regionId) => {
      selectedRegionId.value = regionId
      
      if (!regionId) {
        // Load all features
        await loadAllFeatures(props.recordId)
      } else {
        // Load region-specific features
        await loadRegionFeatures(props.recordId, regionId)
      }
      
      emit('region-changed', regionId)
    }

    const handleAnnotationClicked = (data) => {
      emit('annotation-clicked', data)
    }

    const handleError = (err) => {
      emit('error', err)
    }

    return {
      recordInfo,
      regions,
      features,
      regionBoundaries,
      pfamColorMap,
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
}
</style>
