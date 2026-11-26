<template>
  <div class="region-viewer-wrapper">
    <!-- Current Record Info -->
    <div v-if="recordInfo && showRecordInfo" class="current-record-info">
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
import FeatureDetails from './FeatureDetails.vue'
import SimpleDetails from './SimpleDetails.vue'
import { parseLocation } from '@/utils/location'
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
      // Expected shape: [{ id, region_number, product, start, end }]
    },
    // Features to display
    features: {
      type: Array,
      default: () => []
      // Expected shape: [{ type, location, qualifiers }]
    },
    // PFAM color mapping
    pfamColorMap: {
      type: Object,
      default: () => ({})
      // Expected shape: { 'PF00001': '#FF0000', ... }
    },
    // Whether the record ID, description and file are shown above the tracks
    showRecordInfo: {
      type: Boolean,
      default: true
    },
    // Selected region ID (controlled from parent)
    selectedRegionId: {
      type: String,
      default: ''
    },
    // Number of a protocluster to zoom to and select instead of the region, as for a protocluster search hit
    selectedProtoclusterNumber: {
      type: Number,
      default: null
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
    // Protocluster the view is focused on; picking a region from the menu drops it
    const focusedProtocluster = ref(null)
    const loading = ref(false)
    const error = ref('')
    
    // Track management
    const availableTracks = ref([])
    const selectedTracks = ref([])
    const currentDomain = ref(null)
    
    let regionViewer = null
    let allTrackData = {} // Store all generated tracks
    // Whether tracks without features in view are hidden; a viewer is made per record, so the
    // choice is kept here, and in browser storage for the next visit
    const HIDE_EMPTY_TRACKS_KEY = 'bgc-viewer-hide-empty-tracks'
    // On unless it was turned off
    let hideEmptyTracks = true
    try {
      hideEmptyTracks = localStorage.getItem(HIDE_EMPTY_TRACKS_KEY) !== 'false'
    } catch {
      // Storage may be unavailable; the empty tracks are then hidden
    }
    const setHideEmptyTracks = (hide) => {
      hideEmptyTracks = hide
      try {
        localStorage.setItem(HIDE_EMPTY_TRACKS_KEY, String(hide))
      } catch {
        // The choice then lasts until the page is reloaded
      }
    }
    const selectedAnnotation = ref(null) // Track the selected annotation for highlighting
    const ANNOTATION_THRESHOLD = 500 // Max annotations to render before showing placeholder
    const REGION_ZOOM_DURATION = 1500 // Duration (ms) of the zoom out, pan and zoom in to a selected region
    
    // Derive selected element from selected annotation
    const selectedElement = computed(() => {
      return selectedAnnotation.value?.data || null
    })

    // Region number of the selected element: the region it lies in, else the selected region
    const currentRegionNumber = computed(() => {
      const location = selectedElement.value?.location && parseLocation(selectedElement.value.location)
      const region = (location && props.regions.find(r => r.start < location.end && location.start < r.end))
        || props.regions.find(r => r.id === selectedRegion.value)
      return region ? String(region.region_number) : '1' // Default to region 1
    })

    // Watch for prop changes and rebuild the viewer
    watch(() => props.features, () => {
      if (props.features && props.features.length > 0) {
        rebuildViewer()
      }
    })

    watch(() => props.tfbsHits, () => {
      // Rebuild viewer when TFBS hits change
      if (props.features && props.features.length > 0) {
        rebuildViewer()
      }
    })

    watch(() => props.ttaCodons, () => {
      // Rebuild viewer when TTA codons change
      if (props.features && props.features.length > 0) {
        rebuildViewer()
      }
    })

    watch(() => props.resistanceFeatures, () => {
      // Rebuild viewer when resistance features change
      if (props.features && props.features.length > 0) {
        rebuildViewer()
      }
    })

    watch(() => props.selectedRegionId, (newVal) => {
      selectedRegion.value = newVal
    }, { immediate: true })

    watch(() => props.selectedProtoclusterNumber, (newVal) => {
      focusedProtocluster.value = newVal
    }, { immediate: true })

    // Covers regions picked from the menu as well as region and protocluster search results.
    // One watcher for both, so a hit that changes region and protocluster at once zooms once.
    watch([selectedRegion, focusedProtocluster], () => {
      clearSelection()
      zoomToSelection()
    })

    onMounted(() => {
      // Initial build if we already have features
      if (props.features && props.features.length > 0) {
        rebuildViewer()
      }
    })

    onUnmounted(() => {
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
        selectedAnnotation.value = null
        
        // Build all tracks from features
        buildAllTracks()
        console.log('Built tracks:', Object.keys(allTrackData))
        
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
        
        // Select default tracks based on availability
        const preferredTracks = tracks.filter(t => 
          ['CDS'].includes(t.id) ||
          t.id.includes('protocluster') ||
          t.id.includes('PFAM_domain') ||
          t.id.includes('cand_cluster')
        ).map(t => t.id)

        // If preferred tracks exist, use them; otherwise select all
        selectedTracks.value = preferredTracks.length > 0 ? preferredTracks : tracks.map(t => t.id)

        console.log('Available tracks:', availableTracks.value)
        console.log('Selected tracks:', selectedTracks.value)

        await nextTick() // Wait for DOM update
        
        // Initialize viewer
        console.log('Initializing viewer...')
        initializeViewer()
        
        // Get initial domain and filter annotations
        if (regionViewer) {
          currentDomain.value = regionViewer.getCurrentDomain()
          filterAnnotationsForViewport(currentDomain.value)
        }
        
        updateViewer()
        console.log('Viewer initialized and updated')
        
      } catch (err) {
        console.error('Error in rebuildViewer:', err)
        error.value = `Failed to build viewer: ${err.message}`
        emit('error', err)
      }
    }
    
    const selectRegion = (regionId) => {
      const unchanged = regionId === selectedRegion.value && focusedProtocluster.value === null
      // A region picked from the menu replaces a focused protocluster
      focusedProtocluster.value = null
      if (unchanged) {
        // Zoom back to the region, e.g. after panning away from it
        clearSelection()
        zoomToSelection()
      } else if (regionId !== selectedRegion.value) {
        // The selection watcher zooms to the region
        selectedRegion.value = regionId
        emit('region-changed', regionId)
      }
    }

    const toggleTrack = (trackId) => {
      selectedTracks.value = selectedTracks.value.includes(trackId)
        ? selectedTracks.value.filter(id => id !== trackId)
        : [...selectedTracks.value, trackId]
      updateViewer()
    }

    const toggleAllTracks = () => {
      selectedTracks.value = selectedTracks.value.length === availableTracks.value.length
        ? []
        : availableTracks.value.map(t => t.id)
      updateViewer()
    }

    // Region and track options for the track viewer's menu
    const getMenuItems = () => {
      const items = [{
        label: 'Zoom to',
        children: [
          { label: 'Whole record', action: () => selectRegion('') },
          ...(props.regions.length > 0 ? [{ type: 'separator' }] : []),
          ...props.regions.map(region => ({
            label: `Region ${region.region_number} - ${region.product.join(', ')}`,
            action: () => selectRegion(region.id)
          }))
        ]
      }]
      if (availableTracks.value.length > 0) {
        items.push({
          label: 'Tracks',
          children: [
            {
              label: 'All tracks',
              keepOpen: true,
              checked: () => selectedTracks.value.length === availableTracks.value.length
                || (selectedTracks.value.length > 0 && 'mixed'),
              action: toggleAllTracks
            },
            { type: 'separator' },
            ...availableTracks.value.map(track => ({
              label: `${track.label} (${track.annotationCount})`,
              keepOpen: true,
              checked: () => selectedTracks.value.includes(track.id),
              action: () => toggleTrack(track.id)
            }))
          ]
        })
      }
      return items
    }

    // The full-location annotation of protocluster `number`, also when the viewport filters it out
    const findProtoclusterAnnotation = (number) => {
      const id = `protocluster-${number}`
      for (const track of Object.values(allTrackData)) {
        if (!track.id.startsWith('protocluster-track-')) continue
        const annotation = (track._originalAnnotations || track.annotations).find(ann => ann.id === id)
        if (annotation) return annotation
      }
      return null
    }

    // Zoom to start..end with a little room on either side
    const zoomToSpan = (start, end, duration) => {
      const padding = (end - start) * 0.02
      regionViewer.zoomTo(start - padding, end + padding, duration)
    }

    // Zoom to and select the focused protocluster, else zoom to the selected region,
    // or out to the whole record if none is selected
    const zoomToSelection = (duration = REGION_ZOOM_DURATION) => {
      if (!regionViewer) return
      const protocluster = focusedProtocluster.value !== null
        ? findProtoclusterAnnotation(focusedProtocluster.value)
        : null
      if (protocluster) {
        // Selected as a click on it would, so its details show and its genes are highlighted
        selectedAnnotation.value = protocluster
        updateAnnotationHighlighting()
        updateViewer()
        zoomToSpan(protocluster.start, protocluster.end, duration)
        return
      }
      const region = props.regions.find(r => r.id === selectedRegion.value)
      if (region && region.start != null && region.end != null) {
        zoomToSpan(region.start, region.end, duration)
      } else {
        regionViewer.resetZoom(duration)
      }
    }
    
    const initializeViewer = () => {
      if (regionViewer) {
        regionViewer.destroy()
      }
      
      if (!viewerContainer.value) return
      
      let minPos, maxPos
      
      // The domain always spans the whole record; a selected region is zoomed to below
      console.log('Calculating boundaries from', props.features.length, 'features')
      const positions = props.features
        .filter(f => f.location)
        .map(f => {
          const location = parseLocation(f.location)
          return location ? [location.start, location.end] : null
        })
        .filter(Boolean)
        .flat()
      
      console.log('Extracted positions:', positions.slice(0, 10), positions.length > 10 ? `... (${positions.length} total)` : '')
      
      if (positions.length === 0) {
        console.warn('No valid positions found, using default domain')
        minPos = 0
        maxPos = 1000
      } else {
        // Reduce instead of Math.min(...positions): whole records can exceed the argument limit
        minPos = positions.reduce((a, b) => Math.min(a, b))
        maxPos = positions.reduce((a, b) => Math.max(a, b))
      }
      const padding = (maxPos - minPos) * 0.02
      console.log('Calculated domain:', minPos - padding, 'to', maxPos + padding)
      
      console.log('Creating TrackViewer...')
      regionViewer = new TrackViewer({
        container: viewerContainer.value,
        // width is not specified, so it will be responsive
        height: 400,
        domain: [minPos - padding, maxPos + padding],
        trackHeight: 40,
        // Zooming out stops at the whole record; zooming in goes down to about 100 bp
        zoomExtent: [1, Math.max(1000, (maxPos - minPos) / 100)],
        showTrackLabels: false,
        hideEmptyTracks,
        onHideEmptyTracksChange: setHideEmptyTracks,
        menuItems: getMenuItems,
        onAnnotationClick: (annotation, track) => {
          console.log('Clicked annotation:', annotation, 'on track:', track)
          handleAnnotationClick(annotation, track)
          emit('annotation-clicked', { annotation, track })
        },
        onAnnotationHover: (annotation, track, event) => {
          // Hover is handled by the TrackViewer's built-in tooltip
          emit('annotation-hovered', { annotation, track, event })
        },
        onBackgroundClick: () => {
          // Clear selection when clicking background
          clearSelection()
        },
        onDomainChange: (domain) => {
          currentDomain.value = domain
          filterAnnotationsForViewport(domain)
          updateAnnotationHighlighting()  // Apply highlighting to newly visible annotations
          updateViewer()
        }
      })
      console.log('TrackViewer created successfully')

      // Start zoomed to the focused protocluster or selected region, without animation
      zoomToSelection(0)
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
      const parsed = parseLocation(location)
      if (!parsed) return null

      const { start, end, strand } = parsed
      return {
        start: start,
        end: end,
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
              showLabel: 'auto',
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
                showLabel: 'auto',
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
          console.log('Mapping resistance feature', resistFeature.reference_id, 'to locus tag', locusTag, 'with location', location)
          
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

        // If still too many in viewport, show placeholder
        if (visibleAnnotations.length > ANNOTATION_THRESHOLD) {
          const minPos = Math.min(...visibleAnnotations.flatMap(ann => [ann.start, ann.end]))
          const maxPos = Math.max(...visibleAnnotations.flatMap(ann => [ann.start, ann.end]))
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
            // Keep the default double-click zoom in: zooming to the placeholder would zoom out
            zoomOnDoubleClick: false,
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
      const tracks = selectedTrackData.map(track => ({
        id: track.id,
        label: track.label,
        height: track.height || undefined
      }))
      
      const annotations = selectedTrackData
        .flatMap(track => track.annotations)
      const primitives = selectedTrackData
        .flatMap(track => track.primitives)
      
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
      
      // Force re-render by calling drawTracks on the viewer
      // This updates the opacity without changing the viewport
      if (regionViewer && regionViewer.drawTracks) {
        regionViewer.drawTracks()
      }
    }
    
    // Clear selected element
    const clearSelectedElement = () => {
      selectedAnnotation.value = null
    }

    // Deselect the selected feature and undo its highlighting
    const clearSelection = () => {
      selectedAnnotation.value = null
      updateAnnotationHighlighting()
      updateViewer()
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
        
        // Update annotations
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
      selectedElement,
      currentRegionNumber,
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
  overflow-y: auto;
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
