<template>
  <div class="region-viewer-container">
    <div class="controls">
      <select v-model="selectedRecord" @change="onRecordChange" class="record-select">
        <option value="">Select a record...</option>
        <option v-for="record in records" :key="record.id" :value="record.id">
          {{ record.id }} ({{ record.feature_count }} features)
        </option>
      </select>
      
      <select v-if="selectedRecord && regions.length > 0" v-model="selectedRegion" @change="onRegionChange" class="region-select">
        <option value="">Select a region...</option>
        <option v-for="region in regions" :key="region.id" :value="region.id">
          Region {{ region.region_number }} - {{ region.product.join(', ') }}
        </option>
      </select>
      
      <!-- Show message when no regions are available -->
      <div v-if="selectedRecord && regions.length === 0 && !loading" class="no-regions-message">
        No regions found - showing all features for this record
      </div>
      
      <div v-if="selectedRecord && (selectedRegion || (regions.length === 0 && availableTracks.length > 0))" class="feature-controls">
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
    
    <div ref="viewerContainer" class="viewer-container" v-show="selectedRecord"></div>
    
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

    const pfam_colormap = {}

    onMounted(async () => {
      try {
        const response = await axios.get('/api/records')
        records.value = response.data
      } catch (err) {
        error.value = `Failed to load records: ${err.message}`
      }
      
      // Load PFAM color mapping
      try {
        const colorResponse = await axios.get('/domain-colors.csv')
        const csvText = colorResponse.data
        const lines = csvText.split('\n')
        
        // Skip header line and process each color mapping
        for (let i = 1; i < lines.length; i++) {
          const line = lines[i].trim()
          if (line) {
            const [id, color] = line.split(',')
            if (id && color) {
              pfam_colormap[id] = color
            }
          }
        }
        console.log('Loaded PFAM colors for', Object.keys(pfam_colormap).length, 'domains')
      } catch (err) {
        console.warn('Failed to load PFAM color mapping:', err.message)
      }
      
      // Add event listeners
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
        
        console.log('Loaded regions:', regions.value.length)
        
        // If no regions are available, load all features directly
        if (!regions.value || regions.value.length === 0) {
          console.log('No regions found, loading all features...')
          await loadAllFeaturesForRecord()
        } else {
          console.log('Found', regions.value.length, 'regions')
        }
        
      } catch (err) {
        error.value = `Failed to load regions: ${err.message}`
      } finally {
        loading.value = false
      }
    }
    
    const loadAllFeaturesForRecord = async () => {
      try {
        console.log('Loading all features for record:', selectedRecord.value)
        // Load all features for the selected record (no region filtering)
        const response = await axios.get(`/api/records/${selectedRecord.value}/features`)
        console.log('Features API response:', response.data)
        currentFeatures = response.data.features
        
        if (!currentFeatures || currentFeatures.length === 0) {
          console.warn('No features found for record:', selectedRecord.value)
          error.value = 'No features found for this record'
          return
        }
        
        console.log('Found', currentFeatures.length, 'features')
        
        // Build all tracks from features
        buildAllTracks()
        console.log('Built tracks:', Object.keys(allTrackData))
        
        // Extract available tracks and select all by default
        const tracks = Object.values(allTrackData).map(track => ({
          id: track.id,
          label: track.label,
          annotationCount: track.annotations.length
        }))
        tracks.sort((a, b) => a.id.localeCompare(b.id))
        availableTracks.value = tracks
        // For all features mode, select all tracks by default (not just CDS/protocluster)
        selectedTracks.value = tracks.map(t => t.id)

        console.log('Available tracks:', availableTracks.value)
        console.log('Selected tracks:', selectedTracks.value)

        await nextTick() // Wait for DOM update
        // Initialize viewer without region boundaries (use feature boundaries)
        console.log('Initializing viewer...')
        initializeViewer(null)
        updateViewer()
        console.log('Viewer initialized and updated')
        
      } catch (err) {
        console.error('Error in loadAllFeaturesForRecord:', err)
        error.value = `Failed to load all features: ${err.message}`
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
        
        // Extract available tracks
        const tracks = Object.values(allTrackData).map(track => ({
          id: track.id,
          label: track.label,
          annotationCount: track.annotations.length
        }))
        tracks.sort((a, b) => a.id.localeCompare(b.id))
        availableTracks.value = tracks
        selectedTracks.value = tracks.filter(t => ['CDS'].includes(t.id) ||
                                                  t.id.includes('protocluster') ||
                                                  t.id.includes('PFAM_domain')).map(t => t.id)

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
        console.log('Using region boundaries:', minPos, '-', maxPos)
      } else {
        // Fallback to calculating from features
        console.log('Calculating boundaries from', currentFeatures.length, 'features')
        const positions = currentFeatures
          .filter(f => f.location)
          .map(f => {
            // Parse location string like "[164:2414](+)" or "[257:2393](+)"
            const match = f.location.match(/\[<?(\d+):>?(\d+)\]/)  
            return match ? [parseInt(match[1]), parseInt(match[2])] : null
          })
          .filter(Boolean)
          .flat()
        
        console.log('Extracted positions:', positions.slice(0, 10), positions.length > 10 ? `... (${positions.length} total)` : '')
        
        if (positions.length === 0) {
          console.warn('No valid positions found, using default domain')
          minPos = 0
          maxPos = 1000
        } else {
          minPos = Math.min(...positions)
          maxPos = Math.max(...positions)
        }
        padding = (maxPos - minPos) * 0.1
        console.log('Calculated domain:', minPos - padding, 'to', maxPos + padding)
      }
      
      console.log('Creating TrackViewer...')
      regionViewer = new window.BGCViewer.TrackViewer({
        container: viewerContainer.value,
        // width is not specified, so it will be responsive
        height: 400,
        domain: [minPos - padding, maxPos + padding],
        onAnnotationClick: (annotation, track) => {
          console.log('Clicked annotation:', annotation, 'on track:', track)
        },
        onAnnotationHover: (annotation, track, event) => {
          // Hover is handled by the TrackViewer's built-in tooltip
        }
      })
      console.log('TrackViewer created successfully')
    }
    
    const buildAllTracks = () => {
      // Reset track data
      allTrackData = {}
      
      // Process all features to build all possible tracks
      currentFeatures.forEach(feature => {
        if (!feature.location) return
        
        // Parse location string like "[164:2414](+)"
        const locationMatch = feature.location?.match(/\[<?(\d+):>?(\d+)\]\(([+-])\)/)
        if (!locationMatch) return
        
        const start = parseInt(locationMatch[1])
        const end = parseInt(locationMatch[2])
        const strand = locationMatch[3]
        
        const classes = []
        classes.push(getFeatureClass(feature.type))
        
        let trackId, trackLabel, trackHeight
        
        switch (feature.type) {
          case "PFAM_domain":
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
            
            // Get PFAM ID from qualifiers to look up color
            const pfamId = feature.qualifiers?.db_xref?.[0]?.replace('PFAM:', '') || 
                           feature.qualifiers?.inference?.[0]?.match(/PFAM:([^,\s]+)/)?.[1] ||
                           feature.qualifiers?.note?.[0]?.match(/PF\d+/)?.[0]
            const [pfamAccession, pfamVersion] = pfamId ? pfamId.split('.') : [null, null];
            const domainColor = pfamAccession && pfam_colormap[pfamAccession] ? pfam_colormap[pfamAccession] : null
            
            const annotation = {
              id: `${feature.type}-${start}-${end}`,
              trackId: trackId,
              type: 'box',
              classes: classes,
              label: getFeatureLabel(feature),
              start: start,
              end: end,
              fill: domainColor,
              stroke: domainColor
            }
            
            allTrackData[trackId].annotations.push(annotation)
            break
            
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
              type: 'box',
              direction: 'none',
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

.no-regions-message {
  display: inline-block;
  padding: 8px 12px;
  background-color: #e8f4fd;
  border: 1px solid #bee5eb;
  border-radius: 4px;
  color: #0c5460;
  font-size: 14px;
  margin-right: 10px;
  font-style: italic;
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
  width: 100%;
  min-height: 400px;
  border: 1px solid #eee;
  border-radius: 4px;
  overflow-x: auto; /* Allow horizontal scrolling if needed */
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
}
:global(.gene-type-biosynthetic-additional) {
  fill: #f16d75;
}
:global(.gene-type-regulatory) {
  fill: seagreen;
}
:global(.gene-type-transport) {
  fill: cornflowerblue;
}
:global(.gene-type-other) {
  fill: gray;
}

:global(.feature-resistance) {
  fill: #bbb;
}
:global(.feature-tta-codon) {
  fill: #444;
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
