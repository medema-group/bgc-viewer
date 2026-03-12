<template>
  <div class="tab-content">
    <h2>&lt;bgc-region-viewer-container&gt; (Web Component)</h2>
    <p class="description">
      Full-featured container with navigation and controls. 
      This component works with a data provider to automatically load and display BGC data.
    </p>
    
    <div class="controls">
      <div class="control-group">
        <div class="control-item">
          <label>Record:</label>
          <select :modelValue="recordIndex" @change="handleRecordChange">
            <option v-for="(record, index) in records" :key="index" :value="index">
              {{ record.id }} ({{ record.seq_length }} bp)
            </option>
          </select>
        </div>

        <div class="control-item">
          <label>Selected Region:</label>
          <span class="region-info">
            {{ currentRegion ? `Area ${regionIndex + 1}: ${currentRegion.products?.[0] || 'Unknown'}` : 'None' }}
          </span>
        </div>
      </div>
    </div>

    <div class="viewer-container">
      <bgc-region-viewer-container
        :dataProvider="dataProvider"
        :recordData="recordData"
        :initialRegionId="initialRegionId"
        @region-changed="handleRegionChanged"
      ></bgc-region-viewer-container>
    </div>

    <div class="info-panel">
      <h3>About This Component</h3>
      <p>
        The RegionViewerContainer is the highest-level component. It handles:
      </p>
      <ul>
        <li><strong>Data Loading:</strong> Works with a DataProvider to fetch record data</li>
        <li><strong>Region Selection:</strong> Built-in region selector with dropdown</li>
        <li><strong>Track Management:</strong> Multi-select dropdown for toggling tracks</li>
        <li><strong>Feature Details:</strong> Click on features to see detailed information</li>
      </ul>
      <p class="note">
        <strong>Note:</strong> This is a custom element registered as &lt;bgc-region-viewer-container&gt;. 
        It works in any framework or plain HTML once registered globally.
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

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
  },
  dataProvider: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['update:recordIndex', 'update:regionIndex'])

const selectedRegionIndex = ref(props.regionIndex)

const recordData = computed(() => {
  if (!props.currentRecord) return null
  
  return {
    recordId: props.currentRecord.id,
    filename: props.currentRecord.id,
    entryId: props.currentRecord.id
  }
})

const initialRegionId = computed(() => {
  const region = props.currentRegion
  if (!region) return ''
  return region.id || `region_${props.regionIndex + 1}`
})

watch(() => props.regionIndex, (newIndex) => {
  selectedRegionIndex.value = newIndex
})

function handleRecordChange(event) {
  const newIndex = Number(event.target.value)
  emit('update:recordIndex', newIndex)
  emit('update:regionIndex', 0) // Reset region when record changes
}

function handleRegionChanged(event) {
  // When region changes in the component, find the index
  const regionId = event.detail?.regionId
  if (regionId) {
    const index = props.regions.findIndex(r => 
      (r.id || `region_${props.regions.indexOf(r) + 1}`) === regionId
    )
    if (index !== -1 && index !== props.regionIndex) {
      emit('update:regionIndex', index)
    }
  }
}
</script>

<style scoped>
.region-info {
  color: #2c3e50;
  font-weight: 500;
}
</style>
