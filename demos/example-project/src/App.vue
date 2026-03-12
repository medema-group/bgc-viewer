<template>
  <div>
    <header>
      <h1>TrackViewer Demo</h1>
      <p class="subtitle">Interactive genomic track visualization with Vue.js</p>
    </header>

    <div v-if="error" class="error">
      {{ error }}
    </div>

    <div v-if="loading" class="loading">
      Loading data...
    </div>

    <template v-if="!loading && !error">
      <div class="controls">
        <div class="control-group">
          <div class="control-item">
            <label>Record:</label>
            <select v-model="selectedRecordIndex" @change="onRecordChange">
              <option v-for="(record, index) in records" :key="index" :value="index">
                {{ record.id }} ({{ record.seq_length }} bp)
              </option>
            </select>
          </div>

          <div class="control-item">
            <label>Region:</label>
            <select v-model="selectedRegionIndex" @change="onRegionChange">
              <option v-for="(region, index) in currentRegions" :key="index" :value="index">
                Area {{ index + 1 }}: {{ region.start }}-{{ region.end }} ({{ region.products?.[0] || 'Unknown' }})
              </option>
            </select>
          </div>

          <button @click="resetZoom">Reset Zoom</button>
          <button @click="fitToScreen">Fit to Screen</button>
        </div>
      </div>

      <div class="viewer-container">
        <div id="track-viewer-container"></div>
      </div>

      <div class="info-panel" v-if="currentRegion">
        <h3>Region Information</h3>
        <div class="info-grid">
          <div class="info-item">
            <div class="info-label">Area</div>
            <div class="info-value">{{ selectedRegionIndex + 1 }}</div>
          </div>
          <div class="info-item">
            <div class="info-label">Product</div>
            <div class="info-value">{{ currentRegion.products?.[0] || 'Unknown' }}</div>
          </div>
          <div class="info-item">
            <div class="info-label">Location</div>
            <div class="info-value">{{ currentRegion.start }}-{{ currentRegion.end }}</div>
          </div>
          <div class="info-item">
            <div class="info-label">Genes</div>
            <div class="info-value">{{ currentRegion.orfs?.length || 0 }}</div>
          </div>
        </div>
      </div>
    </template>

    <footer>
      <p>
        Built with <a href="https://www.npmjs.com/package/@medemagroup/bgc-viewer-components" target="_blank">@medemagroup/bgc-viewer-components</a>
        | <a href="https://github.com/medema-group/bgc-viewer" target="_blank">GitHub</a>
      </p>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { TrackViewer } from '@medemagroup/bgc-viewer-components'
import * as d3 from 'd3'

// Make D3 globally available for TrackViewer
if (typeof window !== 'undefined') {
  window.d3 = d3
}

const loading = ref(true)
const error = ref(null)
const jsonData = ref(null)
const records = ref([])
const selectedRecordIndex = ref(0)
const selectedRegionIndex = ref(0)
const trackViewer = ref(null)

const currentRecord = computed(() => {
  return records.value[selectedRecordIndex.value]
})

const currentRegions = computed(() => {
  const record = currentRecord.value
  if (!record) return []
  
  // antiSMASH v7+ uses 'areas' instead of 'regions'
  if (record.areas) {
    return record.areas
  }
  
  // Older versions use 'regions'
  return record.regions || []
})

const currentRegion = computed(() => {
  return currentRegions.value[selectedRegionIndex.value]
})

onMounted(async () => {
  await loadData()
})

onBeforeUnmount(() => {
  if (trackViewer.value) {
    trackViewer.value.destroy()
  }
})

async function loadData() {
  try {
    loading.value = true
    error.value = null

    console.log('Loading data...')
    // Load the antiSMASH JSON data (symlinked in public/data)
    const response = await fetch('/data/Y16952.json')
    console.log('Response status:', response.status)
    if (!response.ok) {
      throw new Error(`Failed to load data: ${response.statusText}`)
    }

    jsonData.value = await response.json()
    console.log('Data loaded:', jsonData.value)
    records.value = jsonData.value.records || []
    console.log('Records found:', records.value.length)
    
    if (records.value.length > 0) {
      console.log('First record structure:', records.value[0])
      console.log('First record keys:', Object.keys(records.value[0]))
      if (records.value[0].areas) {
        console.log('Record has areas:', records.value[0].areas)
      }
      if (records.value[0].regions) {
        console.log('Record has regions:', records.value[0].regions)
      }
    }

    if (records.value.length === 0) {
      throw new Error('No records found in data')
    }

    loading.value = false

    // Initialize the viewer after data is loaded
    console.log('Waiting for next tick...')
    await nextTick()
    console.log('Initializing viewer...')
    initializeViewer()
  } catch (err) {
    error.value = err.message
    loading.value = false
    console.error('Error loading data:', err)
  }
}

function initializeViewer() {
  const region = currentRegion.value
  console.log('Current region:', region)
  if (!region) {
    console.error('No region available')
    return
  }

  console.log('Region keys:', Object.keys(region))
  console.log('Region orfs:', region.orfs)
  
  // Create track data from region
  const { tracks, annotations } = createTracksFromRegion(region)
  console.log('Created tracks:', tracks)
  console.log('Created annotations:', annotations)

  // Initialize or update the viewer
  if (trackViewer.value) {
    console.log('Destroying previous viewer')
    trackViewer.value.destroy()
  }

  console.log('Creating new TrackViewer...')
  try {
    trackViewer.value = new TrackViewer({
      container: '#track-viewer-container',
      domain: [region.start, region.end],
      width: 1200,
      height: 400,
      trackHeight: 60,
      showTrackLabels: true,
      onAnnotationClick: (annotation, track) => {
        console.log('Clicked:', annotation.label, 'on track:', track.id)
        alert(`Gene: ${annotation.label}\nStart: ${annotation.start}\nEnd: ${annotation.end}`)
      }
    })
    
    // Set the data after creating the viewer
    trackViewer.value.setData({ tracks, annotations })

    console.log('TrackViewer created successfully')
  } catch (err) {
    console.error('Error creating TrackViewer:', err)
    error.value = `Failed to create viewer: ${err.message}`
  }
}

function createTracksFromRegion(region) {
  const tracks = []

  console.log('createTracksFromRegion called with:', region)
  
  // antiSMASH v8 may store genes differently - check multiple possible locations
  let genes = region.orfs || []
  
  // If no orfs, get features from the record that fall within this region
  if (genes.length === 0 && currentRecord.value) {
    console.log('No orfs in region, getting features from record')
    const record = currentRecord.value
    console.log('Record has', record.features.length, 'total features')
    
    // Filter features that are CDS and within the region boundaries
    genes = record.features.filter(feature => {
      if (feature.type !== 'CDS') return false
      
      // Parse location string: "[start:end](strand)"
      const location = feature.location
      if (!location || typeof location !== 'string') return false
      
      const match = location.match(/\[(\d+):(\d+)\]/)
      if (!match) return false
      
      const featureStart = parseInt(match[1])
      const featureEnd = parseInt(match[2])
      
      // Check if feature overlaps with region
      return featureStart >= region.start && featureEnd <= region.end
    })
    
    console.log('Found', genes.length, 'CDS features in region', region.start, '-', region.end)
  }
  
  console.log('Processing', genes.length, 'genes')

  // Create a track for genes
  const geneAnnotations = genes.map((gene, index) => {
    const location = gene.location
    if (!location || typeof location !== 'string') {
      console.warn('Gene has no valid location:', gene)
      return null
    }
    
    // Parse location string: "[start:end](strand)"
    const match = location.match(/\[(\d+):(\d+)\]\(([+-])\)/)
    if (!match) {
      console.warn('Could not parse location:', location)
      return null
    }
    
    const start = parseInt(match[1])
    const end = parseInt(match[2])
    const strand = match[3]

    return {
      id: gene.locus_tag || gene.id || `gene_${index}`,
      trackId: 'genes',
      type: 'arrow',
      classes: [],
      label: gene.locus_tag || gene.gene || gene.id || `Gene ${index + 1}`,
      start: start,
      end: end,
      direction: strand === '+' ? 'right' : 'left',
      fill: getGeneColor(gene),
      stroke: '#333',
      heightFraction: 0.8
    }
  }).filter(Boolean)

  console.log('Created', geneAnnotations.length, 'gene annotations')

  tracks.push({
    id: 'genes',
    label: 'Genes'
  })

  return { tracks, annotations: geneAnnotations }
}

function getGeneColor(orf) {
  // Color by gene function
  const functions = orf.gene_functions || []
  
  if (functions.some(f => f.function === 'biosynthetic')) {
    return '#e74c3c' // Red for biosynthetic
  } else if (functions.some(f => f.function === 'transport')) {
    return '#3498db' // Blue for transport
  } else if (functions.some(f => f.function === 'regulatory')) {
    return '#9b59b6' // Purple for regulatory
  } else if (functions.some(f => f.function === 'resistance')) {
    return '#e67e22' // Orange for resistance
  }
  
  return '#95a5a6' // Gray for other/unknown
}

function onRecordChange() {
  selectedRegionIndex.value = 0
  initializeViewer()
}

function onRegionChange() {
  initializeViewer()
}

function resetZoom() {
  if (trackViewer.value) {
    trackViewer.value.resetZoom()
  }
}

function fitToScreen() {
  if (trackViewer.value && currentRegion.value) {
    trackViewer.value.zoomTo(currentRegion.value.start, currentRegion.value.end)
  }
}
</script>
