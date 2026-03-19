<template>
  <div class="tab-content">
    <h2>&lt;bgc-region-viewer&gt; (Web Component)</h2>
    <p class="description">
      Core region viewer component for displaying biosynthetic gene clusters. 
      This component requires structured data passed as props (recordInfo, regions, features, etc.).
    </p>
    
    <div class="controls">
      <div class="control-group">
        <div class="control-item">
          <label>Record:</label>
          <select :modelValue="recordIndex" @change="$emit('update:recordIndex', Number($event.target.value))">
            <option v-for="(record, index) in records" :key="index" :value="index">
              {{ record.id }} ({{ record.seq_length }} bp)
            </option>
          </select>
        </div>

        <div class="control-item">
          <label>Region:</label>
          <select :modelValue="regionIndex" @change="$emit('update:regionIndex', Number($event.target.value))">
            <option v-for="(region, index) in regions" :key="index" :value="index">
              Area {{ index + 1 }}: {{ region.start }}-{{ region.end }} ({{ region.products?.[0] || 'Unknown' }})
            </option>
          </select>
        </div>
      </div>
    </div>

    <div class="viewer-container">
      <RegionViewer
        :recordInfo="recordInfo"
        :regions="regionsForComponent"
        :features="featuresForComponent"
        :regionBoundaries="regionBoundaries"
        :selectedRegionId="selectedRegionId"
      />
    </div>

    <div class="info-panel">
      <h3>Component Props</h3>
      <p>The RegionViewer component receives structured data:</p>
      <ul>
        <li><strong>recordInfo:</strong> Basic record metadata</li>
        <li><strong>regions:</strong> {{ regionsForComponent.length }} region(s)</li>
        <li><strong>features:</strong> {{ featuresForComponent.length }} feature(s)</li>
        <li><strong>regionBoundaries:</strong> {{ regionBoundaries ? `${regionBoundaries.start}-${regionBoundaries.end}` : 'none' }}</li>
      </ul>
      <p class="note">
        <strong>Note:</strong> This is a Vue component imported from the package. 
        No shadow DOM is used, so styles are applied globally.
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { RegionViewer } from '../../../../frontend/dist/web-components/bgc-viewer-components.es.js'

const props = defineProps({
  records: {
    type: Array,
    required: true
  },
  regions: {
    type: Array,
    required: true
  },
  currentRecord: {
    type: Object,
    required: true
  },
  currentRegion: {
    type: Object,
    required: true
  },
  recordIndex: {
    type: Number,
    required: true
  },
  regionIndex: {
    type: Number,
    required: true
  }
})

const emit = defineEmits(['update:recordIndex', 'update:regionIndex'])

// Prepare data in the format expected by RegionViewer
const recordInfo = computed(() => {
  if (!props.currentRecord) return null
  
  return {
    recordId: props.currentRecord.id,
    filename: props.currentRecord.id,
    recordInfo: {
      description: props.currentRecord.description || 'No description'
    }
  }
})

const regionsForComponent = computed(() => {
  return props.regions.map((region, index) => ({
    id: region.id || `region_${index + 1}`,
    region_number: index + 1,
    product: region.products || ['Unknown'],
    start: region.start,
    end: region.end
  }))
})

const featuresForComponent = computed(() => {
  if (!props.currentRecord || !props.currentRecord.features) return []
  
  // Filter features to only those in the current region
  const region = props.currentRegion
  if (!region) return []
  
  return props.currentRecord.features.filter(feature => {
    const location = feature.location
    if (!location || typeof location !== 'string') return false
    
    const match = location.match(/\[(\d+):(\d+)\]/)
    if (!match) return false
    
    const featureStart = parseInt(match[1])
    const featureEnd = parseInt(match[2])
    
    return featureStart >= region.start && featureEnd <= region.end
  })
})

const regionBoundaries = computed(() => {
  const region = props.currentRegion
  if (!region) return null
  
  return {
    start: region.start,
    end: region.end
  }
})

const selectedRegionId = computed(() => {
  const region = props.currentRegion
  if (!region) return ''
  return region.id || `region_${props.regionIndex + 1}`
})
</script>
