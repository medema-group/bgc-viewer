<template>
  <div class="region-viewer-container">
    <RegionViewer
      :record-info="recordInfo"
      :regions="regions"
      :features="features"
      :region-boundaries="regionBoundaries"
      :pfam-color-map="pfamColorMap"
      :selected-region-id="selectedRegionId"
      :data-provider="dataProvider"
      :tfbs-hits="tfbsHits"
      :tta-codons="ttaCodons"
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
    const tfbsHits = ref([])
    const ttaCodons = ref([])
    const selectedRegionId = ref('')
    const loading = ref(false)
    const error = ref('')

    // Helper functions (defined before watchers to avoid hoisting issues)
    const clearViewer = () => {
      recordInfo.value = null
      regions.value = []
      features.value = []
      regionBoundaries.value = null
      tfbsHits.value = []
      ttaCodons.value = []
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

    const loadTFBSHits = async (recordId, regionId) => {
      if (!provider.value) return
      try {
        // Extract region number from regionId (e.g., "region_1" -> "1")
        const regionNumber = regionId.replace('region_', '')
        const tfbsData = await provider.value.getTFBSHits(recordId, regionNumber)
        tfbsHits.value = tfbsData.hits || []
        console.log('Loaded', tfbsHits.value.length, 'TFBS binding sites for region', regionNumber)
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

    const loadRecord = async (recordId) => {
      loading.value = true
      error.value = ''
      
      // Reset selected region when loading a new record
      selectedRegionId.value = ''
      
      try {
        if (!provider.value) {
          throw new Error('No data provider available')
        }

        // For BGCViewerAPIProvider, we need the full entryId (filename:recordId)
        // For JSONFileProvider, just the recordId is fine
        // Use recordData.entryId if available, otherwise fall back to recordId
        const entryId = props.recordData?.entryId || recordId
        
        // Get record info with description
        const entryInfo = await provider.value.loadEntry(entryId)
        recordInfo.value = {
          recordId: entryInfo.recordId,
          filename: entryInfo.filename,
          recordInfo: entryInfo.recordInfo
        }
        
        // Get regions
        const regionsData = await provider.value.getRegions(recordInfo.value.recordId)
        regions.value = regionsData.regions || []
        regionBoundaries.value = regionsData.boundaries || null
        
        // Load TTA codons (not region-specific)
        await loadTTACodons(recordInfo.value.recordId)
        
        // Load features based on whether there are regions
        if (regions.value && regions.value.length > 0) {
          // If there are regions, select the first one and load its features
          selectedRegionId.value = regions.value[0].id
          await loadRegionFeatures(recordInfo.value.recordId, selectedRegionId.value)
        } else {
          // No regions - load all features for the record
          await loadAllFeatures(recordInfo.value.recordId)
        }
        
        loading.value = false
      } catch (err) {
        console.error('Error loading record:', err)
        error.value = `Failed to load record: ${err.message}`
        emit('error', error.value)
        loading.value = false
      }
    }

    const loadRegionFeatures = async (recordId, regionId) => {
      try {
        const featuresData = await provider.value.getRegionFeatures(recordId, regionId)
        features.value = featuresData.features || []
        regionBoundaries.value = featuresData.region_boundaries || null
        
        // Load TFBS hits for this region
        await loadTFBSHits(recordId, regionId)
      } catch (err) {
        console.error('Error loading region features:', err)
        error.value = `Failed to load region features: ${err.message}`
        emit('error', error.value)
      }
    }

    const loadAllFeatures = async (recordId) => {
      try {
        const featuresData = await provider.value.getRecordFeatures(recordId)
        features.value = featuresData.features || []
        regionBoundaries.value = null // No region boundaries when showing all features
        
        // Clear TFBS hits when showing all features (not region-specific)
        tfbsHits.value = []
      } catch (err) {
        console.error('Error loading features:', err)
        error.value = `Failed to load features: ${err.message}`
        emit('error', error.value)
      }
    }

    const handleRegionChanged = async (regionId) => {
      selectedRegionId.value = regionId
      
      if (!regionId) {
        // Load all features
        await loadAllFeatures(recordInfo.value.recordId)
      } else {
        // Load region-specific features
        await loadRegionFeatures(recordInfo.value.recordId, regionId)
      }
      
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
        if (recordInfo.value) {
          loadRegionFeatures(recordInfo.value.recordId, newRegionId)
        }
      }
    })

    return {
      recordInfo,
      regions,
      features,
      regionBoundaries,
      pfamColorMap,
      tfbsHits,
      ttaCodons,
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
</style>
