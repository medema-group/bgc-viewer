<template>
  <div class="region-viewer-container">
    <div class="controls">
      <select v-model="selectedRecord" @change="onRecordChange" class="record-select">
        <option value="">Select a record...</option>
        <option v-for="record in records" :key="record.id" :value="record.id">
          {{ record.id }} ({{ record.feature_count }} features)
        </option>
      </select>
      
      <select v-if="selectedRecord" v-model="selectedRegion" @change="onRegionChange" class="region-select">
        <option value="">Select a region...</option>
        <option v-for="region in regions" :key="region.id" :value="region.id">
          Region {{ region.region_number }} - {{ region.product.join(', ') }}
        </option>
      </select>
      
      <div v-if="selectedRecord && selectedRegion" class="feature-controls">
        <div class="multi-select-container">
          <div class="multi-select-dropdown" :class="{ open: dropdownOpen }" @click="toggleDropdown">
            <div class="selected-display">
              <span v-if="selectedTracks.length === availableTracks.length">
                All tracks ({{ selectedTracks.length }})
              </span>
              <span v-else-if="selectedTracks.length === 0">
                No tracks selected
              </span>
              <span v-else>
                {{ selectedTracks.length }} tracks selected
              </span>
              <span class="dropdown-arrow">▼</span>
            </div>
            <div v-if="dropdownOpen" class="dropdown-options" @click.stop>
              <div class="select-all-option">
                <label>
                  <input 
                    type="checkbox" 
                    :checked="selectedTracks.length === availableTracks.length"
                    :indeterminate="selectedTracks.length > 0 && selectedTracks.length < availableTracks.length"
                    @change="toggleSelectAll"
                  >
                  Select All
                </label>
              </div>
              <div class="option-separator"></div>
              <div 
                v-for="track in availableTracks" 
                :key="track.id" 
                class="dropdown-option"
              >
                <label>
                  <input 
                    type="checkbox" 
                    :value="track.id"
                    v-model="selectedTracks"
                    @change="updateViewer"
                  >
                  {{ track.label }} ({{ track.annotationCount }})
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <div ref="viewerContainer" class="viewer-container" v-show="selectedRecord && selectedRegion"></div>
    
    <div v-if="loading" class="loading">
      Loading region data...
    </div>
    
    <div v-if="error" class="error">
      {{ error }}
    </div>
  </div>
</template>

<script>
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import axios from 'axios'

export default {
  name: 'RegionViewerComponent',
  setup() {
    const viewerContainer = ref(null)
    const selectedRecord = ref('')
    const selectedRegion = ref('')
    const records = ref([])
    const regions = ref([])
    const loading = ref(false)
    const error = ref('')
    
    // Track management
    const availableTracks = ref([])
    const selectedTracks = ref([])
    const dropdownOpen = ref(false)
    
    let regionViewer = null
    let currentFeatures = []
    let allTrackData = {} // Store all generated tracks
    
    onMounted(async () => {
      try {
        const response = await axios.get('/api/records')
        records.value = response.data
      } catch (err) {
        error.value = `Failed to load records: ${err.message}`
      }
      
      // Add click outside listener
      document.addEventListener('click', handleClickOutside)
    })
    
    onUnmounted(() => {
      document.removeEventListener('click', handleClickOutside)
    })
    
    const onRecordChange = async () => {
      selectedRegion.value = ''
      regions.value = []
      
      if (!selectedRecord.value) {
        if (regionViewer) {
          regionViewer.destroy()
          regionViewer = null
        }
        return
      }
      
      loading.value = true
      error.value = ''
      
      try {
        // Load regions for the selected record
        const response = await axios.get(`/api/records/${selectedRecord.value}/regions`)
        regions.value = response.data.regions
        
      } catch (err) {
        error.value = `Failed to load regions: ${err.message}`
      } finally {
        loading.value = false
      }
    }
    
    const onRegionChange = async () => {
      if (!selectedRecord.value || !selectedRegion.value) {
        if (regionViewer) {
          regionViewer.destroy()
          regionViewer = null
        }
        return
      }
      
      loading.value = true
      error.value = ''
      
      try {
        // Load features for the selected region
        const response = await axios.get(`/api/records/${selectedRecord.value}/regions/${selectedRegion.value}/features`)
        currentFeatures = response.data.features
        
        // Build all tracks from features
        buildAllTracks()
        
        // Extract available tracks and select all by default
        const tracks = Object.values(allTrackData).map(track => ({
          id: track.id,
          label: track.label,
          annotationCount: track.annotations.length
        }))
        availableTracks.value = tracks
        selectedTracks.value = tracks.map(t => t.id)
        
        await nextTick() // Wait for DOM update
        initializeViewer(response.data.region_boundaries)
        updateViewer()
        
      } catch (err) {
        error.value = `Failed to load region features: ${err.message}`
      } finally {
        loading.value = false
      }
    }
    
    const initializeViewer = (regionBoundaries = null) => {
      if (regionViewer) {
        regionViewer.destroy()
      }
      
      if (!viewerContainer.value) return
      
      let minPos, maxPos, padding
      
      if (regionBoundaries) {
        // Use region boundaries if provided
        minPos = regionBoundaries.start
        maxPos = regionBoundaries.end
        padding = (maxPos - minPos) * 0.1
      } else {
        // Fallback to calculating from features
        const positions = currentFeatures
          .filter(f => f.location)
          .map(f => {
            // Parse location string like "[164:2414](+)" or "[257:2393](+)"
            const match = f.location.match(/\[(\d+):(\d+)\]/)
            return match ? [parseInt(match[1]), parseInt(match[2])] : null
          })
          .filter(Boolean)
          .flat()
        
        minPos = Math.min(...positions) || 0
        maxPos = Math.max(...positions) || 1000
        padding = (maxPos - minPos) * 0.1
      }
      
      regionViewer = new window.BGCViewer.TrackViewer({
        container: viewerContainer.value,
        width: 800,
        height: 400,
        domain: [minPos - padding, maxPos + padding],
        onAnnotationClick: (annotation, track) => {
          console.log('Clicked annotation:', annotation, 'on track:', track)
        },
        onAnnotationHover: (annotation, track, event) => {
          // Hover is handled by the TrackViewer's built-in tooltip
        }
      })
    }
    
    const buildAllTracks = () => {
      // Reset track data
      allTrackData = {}
      
      // Process all features to build all possible tracks
      currentFeatures.forEach(feature => {
        if (!feature.location) return
        
        // Parse location string like "[164:2414](+)"
        const locationMatch = feature.location?.match(/\[(\d+):(\d+)\]\(([+-])\)/)
        if (!locationMatch) return
        
        const start = parseInt(locationMatch[1])
        const end = parseInt(locationMatch[2])
        const strand = locationMatch[3]
        
        const classes = []
        classes.push(getFeatureClass(feature.type))
        
        let trackId, trackLabel, trackHeight
        
        switch (feature.type) {
          case "CDS":
            trackId = feature.type
            trackLabel = feature.type
            trackHeight = undefined
            
            if (feature.type === 'CDS') {
              classes.push(`gene-type-${feature.qualifiers?.gene_kind?.[0] || 'other'}`)
            }
            
            if (!allTrackData[trackId]) {
              allTrackData[trackId] = {
                id: trackId,
                label: trackLabel,
                height: trackHeight,
                annotations: []
              }
            }
            
            allTrackData[trackId].annotations.push({
              id: `${feature.type}-${start}-${end}`,
              trackId: trackId,
              type: 'arrow',
              direction: strand === '+' ? 'right' : strand === '-' ? 'left' : 'none',
              classes: classes,
              label: getFeatureLabel(feature),
              start: start,
              end: end
            })
            break
            
          case "protocluster":
          case "proto_core":
            const protocluster_number = feature.qualifiers?.protocluster_number?.[0] || 'unknown'
            trackId = `protocluster-${protocluster_number}`
            trackLabel = `Protocluster ${protocluster_number}`
            trackHeight = 16
            
            if (!allTrackData[trackId]) {
              allTrackData[trackId] = {
                id: trackId,
                label: trackLabel,
                height: trackHeight,
                annotations: []
              }
            }
            
            allTrackData[trackId].annotations.push({
              id: `${feature.type}-${protocluster_number}`,
              trackId: trackId,
              type: 'box',
              heightFraction: 0.5,
              direction: 'none',
              classes: classes,
              label: getFeatureLabel(feature),
              start: start,
              end: end
            })
            break
            
          default:
            trackId = feature.type
            trackLabel = feature.type
            trackHeight = undefined
            
            if (!allTrackData[trackId]) {
              allTrackData[trackId] = {
                id: trackId,
                label: trackLabel,
                height: trackHeight,
                annotations: []
              }
            }
            
            allTrackData[trackId].annotations.push({
              id: `${feature.type}-${start}-${end}`,
              trackId: trackId,
              type: 'arrow',
              direction: strand === '+' ? 'right' : strand === '-' ? 'left' : 'none',
              classes: classes,
              label: getFeatureLabel(feature),
              start: start,
              end: end
            })
            break
        }
      })
    }

    const updateViewer = () => {
      if (!regionViewer || !Object.keys(allTrackData).length) return
      
      // Filter tracks based on selected tracks, but maintain original order
      const selectedTrackData = []
      availableTracks.value.forEach(track => {
        if (selectedTracks.value.includes(track.id) && allTrackData[track.id]) {
          selectedTrackData.push(allTrackData[track.id])
        }
      })
      
      // Convert to RegionViewer format
      const tracks = selectedTrackData.map(track => ({
        id: track.id,
        label: track.label,
        height: track.height || undefined
      }))
      
      const annotations = selectedTrackData
        .flatMap(track => track.annotations)
      
      regionViewer.setData({ tracks, annotations })
    }
    
    const getFeatureClass = (type) => {
      return `feature-${type.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
    }
    
    const getFeatureLabel = (feature) => {
      // Try to get a meaningful label from qualifiers
      const qualifiers = feature.qualifiers || {}
      
      if (qualifiers.locus_tag?.[0]) return qualifiers.locus_tag[0]
      if (qualifiers.gene?.[0]) return qualifiers.gene[0]
      if (qualifiers.product?.[0]) return qualifiers.product[0]
      if (qualifiers.description?.[0]) return qualifiers.description[0]
      if (qualifiers.db_xref?.[0]) return qualifiers.db_xref[0]
      
      return feature.type || 'Feature'
    }
    
    const toggleDropdown = () => {
      dropdownOpen.value = !dropdownOpen.value
    }
    
    const toggleSelectAll = (event) => {
      if (event.target.checked) {
        selectedTracks.value = [...availableTracks.value.map(t => t.id)]
      } else {
        selectedTracks.value = []
      }
      updateViewer()
    }
    
    // Close dropdown when clicking outside
    const handleClickOutside = (event) => {
      if (!event.target.closest('.multi-select-dropdown')) {
        dropdownOpen.value = false
      }
    }
    
    const refreshData = async () => {
      try {
        loading.value = true
        const response = await axios.get('/api/records')
        records.value = response.data
        
        // Clear the current selections since the data changed
        selectedRecord.value = ''
        selectedRegion.value = ''
        regions.value = []
        availableTracks.value = []
        selectedTracks.value = []
        dropdownOpen.value = false
        allTrackData = {}
        if (regionViewer) {
          regionViewer.destroy()
          regionViewer = null
        }
        
        error.value = ''
      } catch (err) {
        error.value = `Failed to load records: ${err.message}`
      } finally {
        loading.value = false
      }
    }
    
    return {
      viewerContainer,
      selectedRecord,
      selectedRegion,
      records,
      regions,
      loading,
      error,
      availableTracks,
      selectedTracks,
      dropdownOpen,
      onRecordChange,
      onRegionChange,
      updateViewer,
      refreshData,
      toggleDropdown,
      toggleSelectAll
    }
  }
}
</script>

<style scoped>
.region-viewer-container {
  margin: 20px 0;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 20px;
}

.controls {
  margin-bottom: 20px;
}

.record-select {
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 14px;
  margin-right: 10px;
}

.region-select {
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 14px;
  margin-right: 10px;
  min-width: 250px;
}

.feature-controls {
  display: inline-flex;
  gap: 15px;
  margin-left: 10px;
}

.multi-select-container {
  position: relative;
  display: inline-block;
}

.multi-select-container label {
  display: block;
  margin-bottom: 5px;
  font-size: 14px;
  font-weight: 500;
}

.multi-select-dropdown {
  position: relative;
  min-width: 250px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: white;
  cursor: pointer;
}

.multi-select-dropdown.open {
  border-color: #1976d2;
}

.selected-display {
  padding: 8px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
}

.dropdown-arrow {
  transition: transform 0.2s ease;
  color: #666;
}

.multi-select-dropdown.open .dropdown-arrow {
  transform: rotate(180deg);
}

.dropdown-options {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: white;
  border: 1px solid #ccc;
  border-top: none;
  border-radius: 0 0 4px 4px;
  max-height: 200px;
  overflow-y: auto;
  z-index: 1000;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.select-all-option {
  padding: 8px 12px;
  border-bottom: 1px solid #eee;
  background-color: #f8f9fa;
}

.select-all-option label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  margin: 0;
}

.option-separator {
  height: 1px;
  background-color: #e0e0e0;
}

.dropdown-option {
  padding: 6px 12px;
}

.dropdown-option:hover {
  background-color: #f5f5f5;
}

.dropdown-option label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
  margin: 0;
}

.dropdown-option input[type="checkbox"] {
  margin: 0;
}

.viewer-container {
  min-height: 400px;
  border: 1px solid #eee;
  border-radius: 4px;
}

.loading {
  text-align: center;
  padding: 40px;
  font-style: italic;
  color: #666;
}

.error {
  color: #d32f2f;
  background: #ffebee;
  padding: 10px;
  border-radius: 4px;
  margin: 10px 0;
}

/* Gene type styling classes for the RegionViewer */
:global(.gene-type-biosynthetic) {
  fill: #810e15;
  stroke: #610b10;
}
:global(.gene-type-biosynthetic-additional) {
  fill: #f16d75;
  stroke: #c62828;
}
:global(.gene-type-regulatory) {
  fill: seagreen;
  stroke: #2e7d32;
}
:global(.gene-type-transport) {
  fill: cornflowerblue;
  stroke: #1e88e5;
}
:global(.gene-type-other) {
  fill: gray;
  stroke: #555;
}

:global(.feature-resistance) {
  fill: #bbb;
  stroke: #888;
}
:global(.feature-tta-codon) {
  fill: #444;
  stroke: #222;
}


/* Feature styling classes for the RegionViewer */
/* :global(.feature-cds) {
  fill: #4CAF50;
  stroke: #388E3C;
} */

:global(.feature-pfam) {
  fill: #2196F3;
  stroke: #1976D2;
}

:global(.feature-region) {
  fill: #FF9800;
  stroke: #F57C00;
}

:global(.feature-protocluster) {
  fill: #9C27B0;
  stroke: #7B1FA2;
}

:global(.feature-cand-cluster) {
  fill: #F44336;
  stroke: #D32F2F;
}

:global(.feature-default) {
  fill: #757575;
  stroke: #424242;
}
</style>
