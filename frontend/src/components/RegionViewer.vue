<template>
  <!-- Region Selector (shown when record is loaded) -->
  <div v-if="recordInfo" class="controls">
    <select v-if="regions.length > 0" v-model="selectedRegion" @change="onRegionChange" class="region-select">
      <option value="">Show all features</option>
      <option v-for="region in regions" :key="region.id" :value="region.id">
        Region {{ region.region_number }} - {{ region.product.join(', ') }}
      </option>
    </select>

    <!-- Show message when no regions are available -->
    <div v-if="regions.length === 0 && !loading" class="no-regions-message">
      No regions found - showing all features for this record
    </div>
    
    <div v-if="availableTracks.length > 0" class="feature-controls">
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

  <!-- Current Record Info -->
  <div v-if="recordInfo" class="current-record-info">
    <span>Current Record: {{ recordInfo.recordId }} ({{ recordInfo.filename }})</span>
    <div class="record-details">
      <span v-if="recordInfo.recordInfo?.description" class="description">
        {{ recordInfo.recordInfo.description }}
      </span>
    </div>
  </div>
  
  <div ref="viewerContainer" class="viewer-container" v-show="recordInfo"></div>
  
  <div v-if="loading" class="loading">
    Loading region data...
  </div>
  
  <div v-if="error" class="error">
    {{ error }}
  </div>
</template>

<script>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { TrackViewer } from '../TrackViewer'
import './cand-cluster-styling.css'
import './cluster-styling.css'
import './gene-type-styling.css'

export default {
  name: 'RegionViewerComponent',
  props: {
    // Current record information
    recordInfo: {
      type: Object,
      default: null
      // Expected shape: { recordId, filename, recordInfo: { description } }
    },
    // Available regions for the current record
    regions: {
      type: Array,
      default: () => []
      // Expected shape: [{ id, region_number, product }]
    },
    // Features to display
    features: {
      type: Array,
      default: () => []
      // Expected shape: [{ type, location, qualifiers }]
    },
    // Region boundaries (optional, for region-specific view)
    regionBoundaries: {
      type: Object,
      default: null
      // Expected shape: { start, end }
    },
    // PFAM color mapping
    pfamColorMap: {
      type: Object,
      default: () => ({})
      // Expected shape: { 'PF00001': '#FF0000', ... }
    },
    // Selected region ID (controlled from parent)
    selectedRegionId: {
      type: String,
      default: ''
    }
  },
  emits: [
    'region-changed',      // Emitted when user selects a different region
    'annotation-clicked',  // Emitted when user clicks an annotation
    'annotation-hovered',  // Emitted when user hovers over an annotation
    'error'                // Emitted when an error occurs
  ],
  setup(props, { emit, expose }) {
    const viewerContainer = ref(null)
    const selectedRegion = ref('')
    const loading = ref(false)
    const error = ref('')
    
    // Track management
    const availableTracks = ref([])
    const selectedTracks = ref([])
    const dropdownOpen = ref(false)
    
    let regionViewer = null
    let allTrackData = {} // Store all generated tracks
    let selectedAnnotation = null // Track the selected annotation for highlighting

    // Watch for prop changes and rebuild the viewer
    watch(() => props.features, () => {
      if (props.features && props.features.length > 0) {
        rebuildViewer()
      }
    })

    watch(() => props.selectedRegionId, (newVal) => {
      selectedRegion.value = newVal
    }, { immediate: true })

    onMounted(() => {
      // Add event listeners
      document.addEventListener('click', handleClickOutside)
      
      // Initial build if we already have features
      if (props.features && props.features.length > 0) {
        rebuildViewer()
      }
    })

    onUnmounted(() => {
      document.removeEventListener('click', handleClickOutside)
      
      // Clean up TrackViewer instance to prevent stale references after HMR
      if (regionViewer) {
        regionViewer.destroy()
        regionViewer = null
      }
    })

    const rebuildViewer = async () => {
      try {
        error.value = ''
        
        if (!props.features || props.features.length === 0) {
          console.warn('No features provided')
          return
        }
        
        console.log('Building viewer with', props.features.length, 'features')
        
        // Clear selection when rebuilding
        selectedAnnotation = null
        
        // Build all tracks from features
        buildAllTracks()
        console.log('Built tracks:', Object.keys(allTrackData))
        
        // Extract available tracks
        const tracks = Object.values(allTrackData).map(track => ({
          id: track.id,
          label: track.label,
          annotationCount: track.annotations.length
        }))
        sortTracks(tracks)
        availableTracks.value = tracks
        
        // Select default tracks based on context
        if (props.regionBoundaries) {
          // Region-specific view: select CDS, protoclusters, PFAM, candidate clusters
          selectedTracks.value = tracks.filter(t => 
            ['CDS'].includes(t.id) ||
            t.id.includes('protocluster') ||
            t.id.includes('PFAM_domain') ||
            t.id.includes('cand_cluster')
          ).map(t => t.id)
        } else {
          // All features view: select all tracks
          selectedTracks.value = tracks.map(t => t.id)
        }

        console.log('Available tracks:', availableTracks.value)
        console.log('Selected tracks:', selectedTracks.value)

        await nextTick() // Wait for DOM update
        
        // Initialize viewer
        console.log('Initializing viewer...')
        initializeViewer()
        updateViewer()
        console.log('Viewer initialized and updated')
        
      } catch (err) {
        console.error('Error in rebuildViewer:', err)
        error.value = `Failed to build viewer: ${err.message}`
        emit('error', err)
      }
    }
    
    const onRegionChange = () => {
      // Emit event to parent to handle region change
      emit('region-changed', selectedRegion.value)
    }
    
    const initializeViewer = () => {
      if (regionViewer) {
        regionViewer.destroy()
      }
      
      if (!viewerContainer.value) return
      
      let minPos, maxPos, padding
      
      if (props.regionBoundaries) {
        // Use region boundaries if provided
        minPos = props.regionBoundaries.start
        maxPos = props.regionBoundaries.end
        padding = (maxPos - minPos) * 0.02
        console.log('Using region boundaries:', minPos, '-', maxPos)
      } else {
        // Fallback to calculating from features
        console.log('Calculating boundaries from', props.features.length, 'features')
        const positions = props.features
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
        padding = (maxPos - minPos) * 0.02  // Reduced padding from 0.1 to 0.02 for more zoomed-in view
        console.log('Calculated domain:', minPos - padding, 'to', maxPos + padding)
      }
      
      console.log('Creating TrackViewer...')
      regionViewer = new TrackViewer({
        container: viewerContainer.value,
        // width is not specified, so it will be responsive
        height: 400,
        domain: [minPos - padding, maxPos + padding],
        trackHeight: 40,
        showTrackLabels: false,
        onAnnotationClick: (annotation, track) => {
          console.log('Clicked annotation:', annotation, 'on track:', track)
          handleAnnotationClick(annotation, track)
          emit('annotation-clicked', { annotation, track })
        },
        onAnnotationHover: (annotation, track, event) => {
          // Hover is handled by the TrackViewer's built-in tooltip
          emit('annotation-hovered', { annotation, track, event })
        }
      })
      console.log('TrackViewer created successfully')
    }
    
    const makeSureTrackExists = (trackId, trackLabel, trackHeight) => {
      if (!allTrackData[trackId]) {
        allTrackData[trackId] = {
          id: trackId,
          label: trackLabel,
          height: trackHeight,
          annotations: []
        }
      }
    }

    const parseGeneLocation = (location) => {
      // Parse location string like "[164:2414](+)" or "[164:2414]"
      if (!location) return null
      const match = location.match(/\[<?(\d+):>?(\d+)\](?:\(([+-])\))?/)
      if (!match) return null

      const strand = match[3] || null
      return {
        start: parseInt(match[1]),
        end: parseInt(match[2]),
        strand: strand,
        direction: strand === '+' ? 'right' : strand === '-' ? 'left' : 'none'
      }
    }

    // Converts a string to a readable label
    const stringToLabel = (str) => {
      return str.toLowerCase().replace('_', ' ')
    }

    // Converts a string to a CSS class-friendly format
    const stringToClass = (str) => {
      return str.toLowerCase().replace(/[^a-z0-9]+/g, '-')
    }

    const buildAllTracks = () => {
      // Reset track data
      allTrackData = {}
      
      // Process all features to build all possible tracks
      props.features.forEach(feature => {
        if (!feature.location) return
        const location = parseGeneLocation(feature.location)
        if (!location) {
          console.warn('Failed to parse location for feature:', feature.type, feature.location)
          return
        }

        const classes = []
        classes.push(getFeatureClass(feature.type))
        
        let trackId, trackLabel
        switch (feature.type) {
          case "cand_cluster":
            // Only include the candidate clusters that have multiple protocluster children
            if ((feature.qualifiers?.protoclusters?.length || 1) < 2) break

            const cluster_index = feature.qualifiers?.candidate_cluster_number?.[0] || 'unknown'
            const cluster_kind = feature.qualifiers?.kind?.[0] || 'unknown'
            trackId = `cand_cluster-${cluster_index}`
            trackLabel = `Candidate Cluster ${cluster_index}`
            classes.push(`candidate-${stringToClass(cluster_kind)}`)
            makeSureTrackExists(trackId, trackLabel)

            allTrackData[trackId].annotations.push({
              id: `${feature.type}-${cluster_index}`,
              trackId: trackId,
              type: 'box',
              heightFraction: 0.4,
              classes: classes,
              label: `CC ${cluster_index}: ${stringToLabel(cluster_kind)}`,
              labelPosition: 'center',
              showLabel: 'always',
              start: location.start,
              end: location.end,
            })
            break

          case "PFAM_domain":
            trackId = feature.type
            trackLabel = feature.type
            makeSureTrackExists(trackId, trackLabel)
            
            // Get PFAM ID from qualifiers to look up color
            const pfamId = feature.qualifiers?.db_xref?.[0]?.replace('PFAM:', '') || 
                           feature.qualifiers?.inference?.[0]?.match(/PFAM:([^,\s]+)/)?.[1] ||
                           feature.qualifiers?.note?.[0]?.match(/PF\d+/)?.[0]
            const [pfamAccession, pfamVersion] = pfamId ? pfamId.split('.') : ['', ''];
            const domainColor = pfamAccession && props.pfamColorMap[pfamAccession] ? props.pfamColorMap[pfamAccession] : null
            const pfamDescription = feature.qualifiers?.description?.[0] || ''
            const pfamLabel = `${pfamAccession} ${pfamDescription}`.trim()

            const annotation = {
              id: `${feature.type}-${location.start}-${location.end}`,
              trackId: trackId,
              type: 'box',
              classes: classes,
              label: pfamLabel || 'unknown',
              start: location.start,
              end: location.end,
              fill: domainColor,
              stroke: domainColor
            }
            
            allTrackData[trackId].annotations.push(annotation)
            break
            
          case "CDS":
            trackId = feature.type
            trackLabel = feature.type
            classes.push(`gene-type-${feature.qualifiers?.gene_kind?.[0] || 'other'}`)
            makeSureTrackExists(trackId, trackLabel)

            allTrackData[trackId].annotations.push({
              id: `${feature.type}-${location.start}-${location.end}`,
              trackId: trackId,
              type: 'arrow',
              classes: classes,
              label: getFeatureLabel(feature),
              start: location.start,
              end: location.end,
              direction: location.direction,
              stroke: 'black'
            })
            break
            
          case "protocluster":
            const protocluster_number = feature.qualifiers?.protocluster_number?.[0] || 'unknown'
            const protocluster_category = feature.qualifiers?.category?.[0] || 'unknown'
            const protocluster_product = feature.qualifiers?.product?.[0] || 'unknown'
            classes.push(protocluster_category)
            classes.push(protocluster_product)
            const core_location = parseGeneLocation(feature.qualifiers?.core_location?.[0] || null)
            trackId = `protocluster-track-${protocluster_number}`
            trackLabel = `Protocluster track ${protocluster_number}`

            // See if there is any room on existing tracks. This is the case when none of the annotations
            // on the track overlap with the current annotation.
            for (let key of Object.keys(allTrackData)) {
              if (!key.startsWith('protocluster-track-')) continue
              const track = allTrackData[key]
              const overlaps = track.annotations.some(ann => !(location.end < ann.start || location.start > ann.end))
              if (!overlaps) {
                trackId = key
                break // Exit the loop once we find a suitable track
              }
            }
            makeSureTrackExists(trackId, trackLabel)

            // Protocluster
            allTrackData[trackId].annotations.push({
              id: `${feature.type}-${protocluster_number}`,
              trackId: trackId,
              type: 'box',
              heightFraction: 0.3,
              classes: classes,
              start: location.start,
              end: location.end,
              stroke: 'none',
              opacity: 0.5
            })
            // Protocluster core
            if (core_location) {
              allTrackData[trackId].annotations.push({
                id: `${feature.type}-${protocluster_number}-core`,
                trackId: trackId,
                type: 'box',
                heightFraction: 0.35,
                classes: [...classes, 'proto-core'],
                label: getFeatureLabel(feature),
                showLabel: 'always',
                start: core_location.start,
                end: core_location.end,
                stroke: 'black'
              })
            }
            break
            
          default:
            trackId = feature.type
            trackLabel = feature.type
            makeSureTrackExists(trackId, trackLabel)
            
            allTrackData[trackId].annotations.push({
              id: `${feature.type}-${location.start}-${location.end}`,
              trackId: trackId,
              type: 'box',
              classes: classes,
              label: getFeatureLabel(feature),
              start: location.start,
              end: location.end
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
    
    const sortTracks = (tracks) => {
      // Define track type priority: candidates, protoclusters, CDS, PFAM domains, others
      const getTrackTypePriority = (trackId) => {
        if (trackId.startsWith('cand_cluster')) return 1 // Candidates first
        if (trackId.startsWith('protocluster')) return 2 // Protoclusters second
        if (trackId.startsWith('CDS')) return 3 // CDS third
        if (trackId.startsWith('PFAM_domain')) return 4 // PFAM domains fourth
        return 5 // Everything else last
      }
      
      return tracks.sort((a, b) => {
        const priorityA = getTrackTypePriority(a.id)
        const priorityB = getTrackTypePriority(b.id)
        
        // First sort by priority
        if (priorityA !== priorityB) {
          return priorityA - priorityB
        }
        
        // Within same priority, maintain original order (stable sort by id)
        return a.id.localeCompare(b.id)
      })
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
    
    // Handle annotation click for highlighting
    const handleAnnotationClick = (annotation, track) => {
      // Toggle selection: if clicking the same annotation, deselect it
      if (selectedAnnotation?.id === annotation.id) {
        selectedAnnotation = null
      } else {
        selectedAnnotation = annotation
        if (annotation.id.endsWith('-core')) {
          // If core annotation clicked, find parent protocluster annotation
          const parentTrack = allTrackData[annotation.trackId]
          const parentAnnotationId = annotation.id.replace('-core', '')
          if (parentTrack) {
            const parentAnnotation = parentTrack.annotations.find(ann => 
              ann.id === parentAnnotationId
            )
            if (parentAnnotation) {
              selectedAnnotation = parentAnnotation
            }
          }
        }
      }
      
      // Update highlighting in allTrackData
      updateAnnotationHighlighting()
      
      // Update the viewer with new opacity values
      updateViewer()
    }
    
    // Determine if an annotation should be highlighted
    const shouldHighlightAnnotation = (annotation) => {
      // If no annotation is selected, highlight all
      if (!selectedAnnotation) {
        return true
      }

      if (annotation.id.endsWith('-core')) {
        // For core annotations, highlight if parent protocluster is within selected range
        const parentTrack = allTrackData[annotation.trackId]
        const parentAnnotationId = annotation.id.replace('-core', '')
        if (parentTrack) {
          const parentAnnotation = parentTrack.annotations.find(ann => 
            ann.id === parentAnnotationId
          )
          if (parentAnnotation) {
            return parentAnnotation.start >= selectedAnnotation.start && 
                   parentAnnotation.end <= selectedAnnotation.end
          }
        }
        return false
      }
      
      // Highlight annotations that fall completely within the selected annotation's range
      return annotation.start >= selectedAnnotation.start && 
             annotation.end <= selectedAnnotation.end
    }
    
    // Update opacity on all annotations in allTrackData
    const updateAnnotationHighlighting = () => {
      // Iterate through all tracks and their annotations
      Object.values(allTrackData).forEach(track => {
        track.annotations.forEach(annotation => {
          const shouldHighlight = shouldHighlightAnnotation(annotation)
          
          // Store the original opacity if not already stored
          if (annotation._originalOpacity === undefined) {
            annotation._originalOpacity = annotation.opacity !== undefined ? annotation.opacity : 1
          }
          
          // Set opacity based on highlighting state
          if (shouldHighlight) {
            annotation.opacity = annotation._originalOpacity
          } else {
            annotation.opacity = annotation._originalOpacity * 0.5
          }
        })
      })
    }
    
    // Clear the viewer and reset state
    const clearViewer = () => {
      selectedRegion.value = ''
      selectedAnnotation = null
      allTrackData = {}
      availableTracks.value = []
      selectedTracks.value = []
      error.value = ''
      
      // Clear the viewer container
      if (viewerContainer.value) {
        viewerContainer.value.innerHTML = ''
      }
      regionViewer = null
    }

    
    // Expose methods for parent component (kept for backwards compatibility)
    expose({
      clearViewer,
      rebuildViewer
    })

    return {
      viewerContainer,
      selectedRegion,
      loading,
      error,
      availableTracks,
      selectedTracks,
      dropdownOpen,
      onRegionChange,
      updateViewer,
      toggleDropdown,
      toggleSelectAll
    }
  }
}
</script>

<style scoped>

.current-record-info {
  margin: 10px 0;
  padding: 8px;
}

.record-details {
  font-size: 14px;
  color: #666;
}

.description {
  font-style: italic;
}

.controls {
  margin-bottom: 20px;
}

.region-select {
  margin: 20px 0px 0px 0px;
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

:global(.feature-resistance) {
  fill: #bbb;
}
:global(.feature-tta-codon) {
  fill: #444;
}


/* Feature styling classes for the RegionViewer */

:global(.feature-pfam) {
  fill: #2196F3;
  stroke: #1976D2;
}

:global(.feature-region) {
  fill: #FF9800;
  stroke: #F57C00;
}

:global(.feature-default) {
  fill: #757575;
  stroke: #424242;
}

/* TrackViewer font styles - using :global() to apply to dynamically created elements */
:global(.track-viewer-tooltip) {
  font-size: 14px;
  font-family: sans-serif;
}

:global(.track-label) {
  font-size: 14px;
  font-family: sans-serif;
}

:global(.annotation-label) {
  font-size: 13px;
  font-family: sans-serif;
  stroke: white;
  stroke-width: 0.5px;
  paint-order: stroke fill;
  pointer-events: none;
}

:global(.axis-label) {
  font-size: 14px;
  font-family: sans-serif;
}

:global(.x-axis) {
  font-size: 14px;
  font-family: sans-serif;
}

</style>
