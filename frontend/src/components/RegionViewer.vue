<template>
  <div class="region-viewer-wrapper">
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
      <span>Current Record: {{ recordInfo.recordId }} - {{ recordInfo?.recordInfo?.description }} </span>
      <div class="file-metadata">File: {{ recordInfo.filename }}, 
        version {{ recordInfo.fileMetadata?.version || 'unknown' }}, 
        input {{ recordInfo.fileMetadata?.input_file || 'unknown' }}
      </div>
    </div>
    
    <div ref="viewerContainer" class="viewer-container" v-show="recordInfo"></div>
    
    <div v-if="loading" class="loading">
      Loading region data...
    </div>
    
    <div v-if="error" class="error">
      {{ error }}
    </div>
    
    <!-- Feature Details Panel -->
    <div v-if="recordInfo" class="feature-details-container">
      <!-- Show FeatureDetails for actual record features -->
      <FeatureDetails 
        v-if="selectedElement && selectedElement.type && selectedElement.qualifiers"
        :feature="selectedElement"
        :all-features="features"
        :data-provider="dataProvider"
        :record-info="recordInfo"
        :region-number="currentRegionNumber"
        @close="clearSelectedElement"
      />
      
      <!-- Show SimpleDetails for non-feature elements (TTA codons, resistance, TFBS) -->
      <SimpleDetails 
        v-else-if="selectedElement"
        :data="selectedElement"
        :element-type="selectedElement._elementType"
      />
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { TrackViewer } from '../TrackViewer'
import { zoomIdentity } from 'd3-zoom'
import * as d3 from 'd3-selection'
import FeatureDetails from './FeatureDetails.vue'
import SimpleDetails from './SimpleDetails.vue'
import './cand-cluster-styling.css'
import './cluster-styling.css'
import './gene-type-styling.css'

export default {
  name: 'RegionViewerComponent',
  components: {
    FeatureDetails,
    SimpleDetails
  },
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
    // Whether to zoom to regionBoundaries when they change
    shouldZoomToBoundaries: {
      type: Boolean,
      default: false
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
    },
    // Data provider for fetching additional data
    dataProvider: {
      type: Object,
      default: null
    },
    // TFBS binding site hits
    tfbsHits: {
      type: Array,
      default: () => []
      // Expected shape: [{ name, start, species, link, description, consensus, confidence, strand, score, max_score }]
    },
    // TTA codon positions
    ttaCodons: {
      type: Array,
      default: () => []
      // Expected shape: [{ start, strand }]
    },
    // Resistance features
    resistanceFeatures: {
      type: Array,
      default: () => []
      // Expected shape: [{ locus_tag, query_id, reference_id, subfunctions, description, bitscore, evalue, query_start, query_end }]
    },
    // Loading viewport - when true, shows placeholder while loading data
    loadingViewport: {
      type: Boolean,
      default: false
    },
    // Loaded range - the coordinate range for which features have been loaded
    loadedRange: {
      type: Object,
      default: null
      // Expected shape: { start, end }
    }
  },
  emits: [
    'region-changed',      // Emitted when user selects a different region
    'annotation-clicked',  // Emitted when user clicks an annotation
    'annotation-hovered',  // Emitted when user hovers over an annotation
    'viewport-changed',    // Emitted when the viewport changes (zoom/pan)
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
    const currentDomain = ref(null)  // Current viewport domain [start, end]
    const fullRecordDomain = ref(null)  // Full record domain [min, max]
    
    // Compute current region number from selected region
    const currentRegionNumber = computed(() => {
      if (!selectedRegion.value || !props.regions.length) {
        return '1' // Default to region 1 if no region selected
      }
      const region = props.regions.find(r => r.id === selectedRegion.value)
      return region ? String(region.region_number) : '1'
    })
    
    let regionViewer = null
    let allTrackData = {} // Store all generated tracks
    const selectedAnnotation = ref(null) // Track the selected annotation for highlighting
    const ANNOTATION_THRESHOLD = 500 // Max annotations to render before showing placeholder
    
    // Derive selected element from selected annotation
    const selectedElement = computed(() => {
      return selectedAnnotation.value?.data || null
    })

    // Watch for prop changes and rebuild the viewer
    // Combined watcher for all data props to avoid duplicate rebuilds
    watch(
      () => [props.features, props.tfbsHits, props.ttaCodons, props.resistanceFeatures],
      () => {
        // Always rebuild when features change, even if empty (e.g., when loading new viewport)
        rebuildViewer()
      }
    )

    watch(() => props.loadedRange, (newRange) => {
      // Update viewer when loaded range changes (to update unloaded area indicators)
      if (regionViewer && newRange) {
        updateViewer()
      }
    }, { deep: true })

    watch(() => props.selectedRegionId, (newVal) => {
      selectedRegion.value = newVal
    }, { immediate: true })

    // Watch shouldZoomToBoundaries to trigger zoom when explicitly requested
    watch(() => props.shouldZoomToBoundaries, (shouldZoom) => {
      if (shouldZoom && props.regionBoundaries && regionViewer) {
        // Use nextTick to ensure viewer is updated before zooming
        nextTick(() => {
          if (!regionViewer) return
          
          const { start, end } = props.regionBoundaries
          const chartWidth = regionViewer.getConfig().width - regionViewer.getConfig().margin.left - regionViewer.getConfig().margin.right
          const x = regionViewer.x
          
          const scale = chartWidth / (x(end) - x(start))
          const translate = -x(start) * scale
          
          const transform = zoomIdentity.translate(translate, 0).scale(scale)
          // Apply transform with animation for smoother transition
          regionViewer.svg.transition().duration(500).call(regionViewer.zoom.transform, transform)
          regionViewer.currentTransform = transform
        })
      }
    })

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
          console.warn('[RegionViewer] No features provided - props.features:', props.features)
          // Clear tracks when features are empty (e.g., when switching records)
          allTrackData = {}
          availableTracks.value = []
          selectedTracks.value = []
          selectedAnnotation.value = null
          return
        }
        
        // Preserve selection during viewport changes (pan/zoom)
        // Only clear if we're switching records (no existing tracks)
        if (Object.keys(allTrackData).length === 0) {
          selectedAnnotation.value = null
        }
        
        // Build all tracks from features
        buildAllTracks()
        
        // Store original annotations for tracks with many features
        optimizeTracksForRendering()
        
        // Filter annotations based on viewport (if domain is available)
        if (currentDomain.value) {
          filterAnnotationsForViewport(currentDomain.value)
        }
        
        // Extract available tracks
        const tracks = Object.values(allTrackData).map(track => ({
          id: track.id,
          label: track.label,
          annotationCount: track._originalAnnotations?.length || track.annotations.length
        }))
        sortTracks(tracks)
        availableTracks.value = tracks
        
        // Preserve user's track selection if possible
        const previousSelection = selectedTracks.value || []
        const availableTrackIds = new Set(tracks.map(t => t.id))
        
        // Keep tracks that are still available
        const preservedTracks = previousSelection.filter(id => availableTrackIds.has(id))
        
        // Only use default selection if no previous selection or none can be preserved
        if (preservedTracks.length > 0) {
          selectedTracks.value = preservedTracks
        } else {
          // Select default tracks based on availability
          const preferredTracks = tracks.filter(t => 
            ['CDS'].includes(t.id) ||
            t.id.includes('protocluster') ||
            t.id.includes('PFAM_domain') ||
            t.id.includes('cand_cluster')
          ).map(t => t.id)

          // If preferred tracks exist, use them; otherwise select all
          selectedTracks.value = preferredTracks.length > 0 ? preferredTracks : tracks.map(t => t.id)
        }

        await nextTick() // Wait for DOM update
        
        // Only recreate if: no viewer exists, or container is invalid
        const needsReinit = !regionViewer || !viewerContainer.value
        
        if (needsReinit) {
          initializeViewer()
          
          // Get current domain after initialization
          if (regionViewer) {
            currentDomain.value = regionViewer.getCurrentDomain()
          }
        }
        
        // Always update the viewer with current track data
        // This is needed both for new viewers and when updating existing ones
        updateViewer()
        
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
      
      if (!viewerContainer.value) {
        console.warn('[RegionViewer] viewerContainer.value is null, cannot initialize viewer')
        return
      }
      
      let minPos, maxPos, padding
      
      // Step 1: Calculate the full record domain from all available regions
      // This determines the pannable area - should be the full record length
      if (props.regions && props.regions.length > 0) {
        const regionPositions = props.regions
          .filter(r => r.start !== undefined && r.end !== undefined)
          .flatMap(r => [r.start, r.end])
        
        if (regionPositions.length > 0) {
          minPos = Math.min(...regionPositions)
          maxPos = Math.max(...regionPositions)
          const recordSize = maxPos - minPos
          
          // Add 5% padding on each side for the full record domain
          padding = recordSize * 0.05
          minPos = Math.max(0, minPos - padding)
          maxPos = maxPos + padding
          
          console.log(`Full record domain from regions: ${minPos}-${maxPos}`)
        }
      }
      
      // If no regions or couldn't calculate from regions, fall back to features
      if (minPos === undefined || maxPos === undefined) {
        console.log('Calculating domain from', props.features.length, 'features')
        const positions = props.features
          .filter(f => f.location)
          .map(f => {
            // Parse location string like "[164:2414](+)" or "[257:2393](+)"
            const match = f.location.match(/\[<?(\d+):>?(\d+)\]/)  
            return match ? [parseInt(match[1]), parseInt(match[2])] : null
          })
          .filter(Boolean)
          .flat()
        
        if (positions.length === 0) {
          console.warn('No valid positions found, using default domain')
          minPos = 0
          maxPos = 1000
        } else {
          minPos = Math.min(...positions)
          maxPos = Math.max(...positions)
          padding = (maxPos - minPos) * 0.05
          minPos = Math.max(0, minPos - padding)
          maxPos = maxPos + padding
        }
        console.log('Calculated domain from features:', minPos, '-', maxPos)
      }
      
      // Step 2: Determine initial viewport (what to zoom to initially)
      // This is separate from the domain - region only determines initial zoom level
      let targetStart, targetEnd
      
      if (props.regionBoundaries) {
        // Zoom to the specific region initially
        targetStart = props.regionBoundaries.start
        targetEnd = props.regionBoundaries.end
        console.log(`Initial zoom target: ${targetStart}-${targetEnd}`)
      } else {
        // Zoom to show all features
        targetStart = minPos
        targetEnd = maxPos
      }
      
      console.log('Creating TrackViewer with full record domain...')
      
      // Store the full record domain for use in showing unloaded areas
      fullRecordDomain.value = [minPos, maxPos]
      
      regionViewer = new TrackViewer({
        container: viewerContainer.value,
        // width is not specified, so it will be responsive
        height: 400,
        domain: [minPos, maxPos],  // Full record domain with padding already included
        trackHeight: 40,
        zoomExtent: [0.1, 1000],
        showTrackLabels: false,
        onAnnotationClick: (annotation, track) => {
          handleAnnotationClick(annotation, track)
          emit('annotation-clicked', { annotation, track })
        },
        onAnnotationHover: (annotation, track, event) => {
          // Hover is handled by the TrackViewer's built-in tooltip
          emit('annotation-hovered', { annotation, track, event })
        },
        onBackgroundClick: () => {
          // Clear selection when clicking background
          clearSelectedElement()
        },
        onDomainChange: (domain) => {
          // Update domain ref for tracking (called continuously during pan/zoom)
          currentDomain.value = domain
          // Note: We don't call updateViewer here to avoid performance issues
          // Unloaded indicators are updated via the loadedRange watcher
        },
        onZoomEnd: (domain) => {
          // Called when pan/zoom ends (TrackViewer already filters out non-changes)
          const viewport = { start: Math.floor(domain[0]), end: Math.ceil(domain[1]) }
          emit('viewport-changed', viewport)
        }
      })
      
      // If we expanded the domain for panning, zoom to the actual region
      if (props.regionBoundaries) {
        // Use zoomTo to zoom to the region without animation
        console.log(`Zooming to region: ${targetStart}-${targetEnd}`)
        const chartWidth = regionViewer.getConfig().width - regionViewer.getConfig().margin.left - regionViewer.getConfig().margin.right
        const x = regionViewer.x // Access the scale
        const scale = chartWidth / (x(targetEnd) - x(targetStart))
        const translate = -x(targetStart) * scale
        
        const transform = zoomIdentity.translate(translate, 0).scale(scale)
        // Apply transform without animation for initial load
        regionViewer.svg.call(regionViewer.zoom.transform, transform)
        regionViewer.currentTransform = transform
      }
      
      console.log('TrackViewer created successfully')
    }
    
    const makeSureTrackExists = (trackId, trackLabel, trackHeight) => {
      if (!allTrackData[trackId]) {
        allTrackData[trackId] = {
          id: trackId,
          label: trackLabel,
          height: trackHeight,
          annotations: [],
          primitives: []
        }
        // Add line to CDS track
        if (trackId === 'CDS') {
          allTrackData[trackId].primitives.push({
            id: 'cds-baseline',
            trackId: trackId,
            type: 'horizontal-line',
            class: 'cds-baseline',
            fy: 0.5,
            stroke: 'black',
            opacity: 1
          })
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
      // Clear annotations from existing tracks but keep track structure
      // This prevents tracks from disappearing when zooming to areas without those features
      Object.values(allTrackData).forEach(track => {
        track.annotations = []
        track.primitives = track.primitives?.filter(p => p.id === 'cds-baseline') || [] // Keep baseline
      })
      
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
            const paddedClusterIndex = cluster_index !== 'unknown' ? String(cluster_index).padStart(3, '0') : cluster_index
            trackId = `cand_cluster-track-${paddedClusterIndex}`
            trackLabel = `Candidate Cluster track ${cluster_index}`
            classes.push(`candidate-${stringToClass(cluster_kind)}`)

            // See if there is any room on existing tracks. This is the case when none of the annotations
            // on the track overlap with the current annotation.
            for (let key of Object.keys(allTrackData)) {
              if (!key.startsWith('cand_cluster-track-')) continue
              const track = allTrackData[key]
              const overlaps = track.annotations.some(ann => !(location.end < ann.start || location.start > ann.end))
              if (!overlaps) {
                trackId = key
                break // Exit the loop once we find a suitable track
              }
            }
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
              data: feature
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
              stroke: domainColor,
              data: feature
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
              stroke: 'black',
              data: feature
            })
            break
            
          case "protocluster":
            const protocluster_number = feature.qualifiers?.protocluster_number?.[0] || 'unknown'
            const protocluster_category = feature.qualifiers?.category?.[0] || 'unknown'
            const protocluster_product = feature.qualifiers?.product?.[0] || 'unknown'
            classes.push(protocluster_category)
            classes.push(protocluster_product)
            const core_location = parseGeneLocation(feature.qualifiers?.core_location?.[0] || null)
            const paddedProtoclusterNumber = protocluster_number !== 'unknown' ? String(protocluster_number).padStart(3, '0') : protocluster_number
            trackId = `protocluster-track-${paddedProtoclusterNumber}`
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
              opacity: 0.5,
              data: feature
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
                stroke: 'black',
                data: feature
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
              end: location.end,
              data: feature
            })
            break
        }
      })
      
      // Add TFBS hits as pins on the CDS track
      if (props.tfbsHits && props.tfbsHits.length > 0) {
        const cdsTrackId = 'CDS'
        makeSureTrackExists(cdsTrackId, cdsTrackId)
        
        props.tfbsHits.forEach((hit, idx) => {
          // Only show medium or strong confidence hits
          if (hit.confidence !== 'strong' && hit.confidence !== 'medium') {
            return
          }
          
          allTrackData[cdsTrackId].annotations.push({
            id: `tfbs-${idx}-${hit.start}`,
            trackId: cdsTrackId,
            type: 'pin',
            classes: ['tfbs-hit', `tfbs-${hit.confidence}`],
            label: hit.name,
            labelPosition: 'above',
            showLabel: 'hover',
            start: hit.start,
            end: hit.start, // Pins are at a single position
            fy: 0.5, // Middle of the track
            heightFraction: 0.5,
            opacity: 0.8,
            data: { ...hit, _elementType: 'Binding Site' }
          })
        })
      }
      
      // Add TTA codons as triangles on the CDS track
      if (props.ttaCodons && props.ttaCodons.length > 0) {
        const cdsTrackId = 'CDS'
        makeSureTrackExists(cdsTrackId, cdsTrackId)
        
        props.ttaCodons.forEach((codon, idx) => {
          allTrackData[cdsTrackId].annotations.push({
            id: `tta-${idx}-${codon.start}`,
            trackId: cdsTrackId,
            type: 'triangle',
            classes: ['tta-codon'],
            showLabel: 'none',
            start: codon.start,
            end: codon.start, // Triangles are at a single position
            fy: 0.2, // Middle of the track
            heightFraction: 0.4,
            opacity: 0.9,
            data: { ...codon, _elementType: 'TTA Codon' }
          })
        })
      }
      
      // Add resistance features as boxes on the CDS track
      if (props.resistanceFeatures && props.resistanceFeatures.length > 0) {
        const cdsTrackId = 'CDS'
        makeSureTrackExists(cdsTrackId, cdsTrackId)
        
        // Build a lookup map of locus_tag to CDS feature location
        const locusTagMap = {}
        props.features.forEach(feature => {
          if (feature.type === 'CDS' && feature.qualifiers?.locus_tag?.[0]) {
            const locusTag = feature.qualifiers.locus_tag[0]
            const location = parseGeneLocation(feature.location)
            if (location) {
              locusTagMap[locusTag] = location
            }
          }
        })
        
        props.resistanceFeatures.forEach((resistFeature, idx) => {
          const locusTag = resistFeature.locus_tag
          const location = locusTagMap[locusTag]
          
          if (location) {
            allTrackData[cdsTrackId].annotations.push({
              id: `resistance-${idx}-${locusTag}`,
              trackId: cdsTrackId,
              type: 'box',
              classes: ['resistance'],
              showLabel: 'never',
              start: location.start,
              end: location.end,
              fy: 0.1,
              heightFraction: 0.2,
              fill: '#BBB',
              data: { ...resistFeature, _elementType: 'Resistance' }
            })
          }
        })
      }
    }

    const optimizeTracksForRendering = () => {
      Object.keys(allTrackData).forEach(trackId => {
        const track = allTrackData[trackId]
        
        if (track.annotations.length > ANNOTATION_THRESHOLD) {
          // Store original annotations for viewport-based filtering
          track._originalAnnotations = track.annotations
        }
      })
    }

    const filterAnnotationsForViewport = (domain) => {
      const [viewStart, viewEnd] = domain
      const padding = (viewEnd - viewStart) * 0.1 // Add 10% padding to load slightly outside viewport
      
      Object.keys(allTrackData).forEach(trackId => {
        const track = allTrackData[trackId]
        
        // Skip if no original annotations stored
        if (!track._originalAnnotations) {
          return
        }
        
        // Filter annotations to only those visible in viewport (with padding)
        const visibleAnnotations = track._originalAnnotations.filter(ann => {
          // Check if annotation overlaps with visible range (including padding)
          return ann.end >= (viewStart - padding) && ann.start <= (viewEnd + padding)
        })
        
        console.log(`Track ${trackId}: Showing ${visibleAnnotations.length} of ${track._originalAnnotations.length} annotations in viewport [${Math.round(viewStart)}, ${Math.round(viewEnd)}]`)
        
        // If still too many in viewport, show placeholder
        if (visibleAnnotations.length > ANNOTATION_THRESHOLD) {
          const minPos = Math.min(...visibleAnnotations.flatMap(ann => [ann.start, ann.end]))
          const maxPos = Math.max(...visibleAnnotations.flatMap(ann => [ann.start, ann.end]))
          ANNOTATION_THRESHOLD
          track.annotations = [{
            id: `${trackId}-placeholder`,
            trackId: trackId,
            type: 'box',
            classes: ['track-placeholder'],
            label: `${track.label}: zoom in further to see ${visibleAnnotations.length.toLocaleString()} features`,
            labelPosition: 'center',
            showLabel: 'always',
            start: minPos,
            end: maxPos,
            fill: '#cccccc',
            stroke: '#999999',
            opacity: 0.6,
            heightFraction: 0.8,
            data: { 
              _elementType: 'Placeholder', 
              count: visibleAnnotations.length,
              message: 'This viewport has too many features to display. Zoom in further to see details.'
            }
          }]
        } else {
          // Show visible annotations
          track.annotations = visibleAnnotations
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
      let tracks = selectedTrackData.map(track => ({
        id: track.id,
        label: track.label,
        height: track.height || undefined
      }))
      
      let annotations = selectedTrackData
        .flatMap(track => track.annotations)
      let primitives = selectedTrackData
        .flatMap(track => track.primitives)
      
      // Add placeholder annotations for unloaded areas to ALL tracks
      // Always add them (even when not visible) so they appear immediately when panning
      if (fullRecordDomain.value && props.loadedRange && tracks.length > 0) {
        const [recordMin, recordMax] = fullRecordDomain.value
        const { start: loadedStart, end: loadedEnd } = props.loadedRange
        
        // For each track, add placeholder boxes for unloaded areas
        tracks.forEach(track => {
          // Add left unloaded area (from record start to loaded start)
          if (loadedStart > recordMin) {
            annotations.push({
              id: `${track.id}-unloaded-left`,
              trackId: track.id,
              type: 'box',
              start: recordMin,
              end: loadedStart,
              fill: '#d0d0d0',
              stroke: 'none',
              opacity: 0.6,
              heightFraction: 1.0,
              classes: ['unloaded-indicator']
            })
          }
          
          // Add right unloaded area (from loaded end to record end)
          if (loadedEnd < recordMax) {
            annotations.push({
              id: `${track.id}-unloaded-right`,
              trackId: track.id,
              type: 'box',
              start: loadedEnd,
              end: recordMax,
              fill: '#d0d0d0',
              stroke: 'none',
              opacity: 0.6,
              heightFraction: 1.0,
              classes: ['unloaded-indicator']
            })
          }
        })
      }
      
      regionViewer.setData({ tracks, annotations, primitives })
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
    
    // Update annotation opacities directly in the SVG
    const updateAnnotationOpacitiesInSVG = () => {
      if (!regionViewer) return
      
      const svg = regionViewer.svg
      
      // Update annotation opacities directly in the SVG
      svg.selectAll('.element.annotation').each(function(d) {
        const element = d3.select(this)
        const annotationId = element.attr('id')
        
        // Find the annotation data to get its opacity
        Object.values(allTrackData).forEach(track => {
          const annotation = track.annotations.find(ann => ann.id === annotationId)
          if (annotation && annotation.opacity !== undefined) {
            element.style('opacity', annotation.opacity)
          }
        })
      })
      
      // Update primitive opacities directly in the SVG
      svg.selectAll('.element.primitive').each(function(d) {
        const element = d3.select(this)
        const primitiveId = element.attr('id')
        
        // Find the primitive data to get its opacity
        Object.values(allTrackData).forEach(track => {
          const primitive = track.primitives?.find(prim => prim.id === primitiveId)
          if (primitive && primitive.opacity !== undefined) {
            element.style('opacity', primitive.opacity)
          }
        })
      })
    }
    
    // Handle annotation click for highlighting
    const handleAnnotationClick = (annotation, track) => {
      // Set selected annotation (don't toggle)
      selectedAnnotation.value = annotation
      if (annotation.id.endsWith('-core')) {
        // If core annotation clicked, find parent protocluster annotation
        const parentTrack = allTrackData[annotation.trackId]
        const parentAnnotationId = annotation.id.replace('-core', '')
        if (parentTrack) {
          const parentAnnotation = parentTrack.annotations.find(ann => 
            ann.id === parentAnnotationId
          )
          if (parentAnnotation) {
            selectedAnnotation.value = parentAnnotation
          }
        }
      }
      
      // Update highlighting in allTrackData
      updateAnnotationHighlighting()
      
      // Update opacity directly on rendered elements instead of re-rendering everything
      // This avoids visual jumps from re-rendering
      updateAnnotationOpacitiesInSVG()
    }
    
    // Clear selected element
    const clearSelectedElement = () => {
      selectedAnnotation.value = null
      updateAnnotationHighlighting()
      // Update SVG elements directly to reset opacity
      updateAnnotationOpacitiesInSVG()
    }
    
    // Determine if an annotation should be highlighted
    const shouldHighlightAnnotation = (annotation) => {
      // If no annotation is selected, highlight all
      if (!selectedAnnotation.value) {
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
            return parentAnnotation.start >= selectedAnnotation.value.start && 
                   parentAnnotation.end <= selectedAnnotation.value.end
          }
        }
        return false
      }
      
      // Highlight annotations that fall completely within the selected annotation's range
      return annotation.start >= selectedAnnotation.value.start && 
             annotation.end <= selectedAnnotation.value.end
    }
    
    // Update opacity on all annotations in allTrackData
    const updateAnnotationHighlighting = () => {
      // Iterate through all tracks and their annotations
      Object.values(allTrackData).forEach(track => {
        if (track.id !== 'CDS' && track.id !== 'PFAM_domain') return
        
        // Update both current annotations and original annotations (for filtered tracks)
        const annotationsToUpdate = track._originalAnnotations || track.annotations
        
        annotationsToUpdate.forEach(annotation => {
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
        
        // If we updated _originalAnnotations, also update the current annotations
        if (track._originalAnnotations && track.annotations !== track._originalAnnotations) {
          track.annotations.forEach(annotation => {
            const shouldHighlight = shouldHighlightAnnotation(annotation)
            
            if (annotation._originalOpacity === undefined) {
              annotation._originalOpacity = annotation.opacity !== undefined ? annotation.opacity : 1
            }
            
            if (shouldHighlight) {
              annotation.opacity = annotation._originalOpacity
            } else {
              annotation.opacity = annotation._originalOpacity * 0.5
            }
          })
        }
        
        // Also update the baseline primitive for CDS track
        if (track.id === 'CDS' && track.primitives) {
          track.primitives.forEach(primitive => {
            if (primitive.id === 'cds-baseline') {
              // Store the original opacity if not already stored
              if (primitive._originalOpacity === undefined) {
                primitive._originalOpacity = primitive.opacity !== undefined ? primitive.opacity : 1
              }
              
              // Dim the baseline when any annotation is selected
              if (selectedAnnotation.value) {
                primitive.opacity = primitive._originalOpacity * 0.1
              } else {
                primitive.opacity = primitive._originalOpacity
              }
            }
          })
        }
      })
    }
    
    // Clear the viewer and reset state
    const clearViewer = () => {
      selectedRegion.value = ''
      selectedAnnotation.value = null
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
      selectedElement,
      currentRegionNumber,
      onRegionChange,
      updateViewer,
      toggleDropdown,
      toggleSelectAll,
      clearSelectedElement
    }
  }
}
</script>

<style scoped>
.region-viewer-wrapper {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  overflow-y: scroll;
}

.current-record-info {
  margin: 0 0 10px 0;
  padding: 10px;
  background: white;
  border-radius: 6px;
  border: 1px solid #e0e0e0;
}

.file-metadata {
  margin-top: 4px;
  font-size: 12px;
  color: #666;
}

.controls {
  margin-bottom: 12px;
  background: white;
  padding: 10px;
  border-radius: 6px;
  border: 1px solid #e0e0e0;
}

.region-select {
  margin: 0;
  padding: 6px 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 13px;
  margin-right: 8px;
  min-width: 200px;
}

.no-regions-message {
  display: inline-block;
  padding: 6px 10px;
  background-color: #e8f4fd;
  border: 1px solid #bee5eb;
  border-radius: 4px;
  color: #0c5460;
  font-size: 13px;
  margin-right: 8px;
  font-style: italic;
}

.feature-controls {
  display: inline-flex;
  gap: 10px;
  margin-left: 8px;
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
  min-width: 200px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: white;
  cursor: pointer;
}

.multi-select-dropdown.open {
  border-color: #1976d2;
}

.selected-display {
  padding: 6px 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
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
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  background: white;
  margin-bottom: 8px;
  padding-bottom: 8px;
  flex-shrink: 0;
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
  padding: 8px;
  border-radius: 4px;
  margin: 8px 0;
  font-size: 13px;
}

.feature-details-container {
  margin-top: 15px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}

:global(.feature-resistance) {
  fill: #bbb;
}
:global(.feature-tta-codon) {
  fill: #444;
}

:global(.track-placeholder) {
  fill: #cccccc;
  stroke: #999999;
  opacity: 0.6;
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

/* Unloaded data indicator styling - light gray overlay on tracks */
:global(.unloaded-indicator) {
  fill: #f5f5f5;
  stroke: none;
  opacity: 0.4;
  pointer-events: none;
}

</style>
