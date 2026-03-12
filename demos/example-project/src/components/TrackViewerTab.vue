<template>
  <div class="tab-content">
    <h2>TrackViewer (Direct JS API)</h2>
    <p class="description">
      Low-level canvas-based rendering for custom track visualizations. 
      Use this for maximum control over rendering and performance.
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
          <div class="info-value">{{ regionIndex + 1 }}</div>
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
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { TrackViewer } from '../../../../frontend/src/TrackViewer'
import * as d3 from 'd3'

// Make D3 globally available
if (typeof window !== 'undefined') {
  window.d3 = d3
}

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

const trackViewer = ref(null)

onMounted(async () => {
  await nextTick()
  initializeViewer()
})

onBeforeUnmount(() => {
  if (trackViewer.value) {
    trackViewer.value.destroy()
    trackViewer.value = null
  }
})

watch(() => props.currentRegion, () => {
  initializeViewer()
})

function initializeViewer() {
  const region = props.currentRegion
  if (!region) {
    console.error('No region available')
    return
  }

  const { tracks, annotations } = createTracksFromRegion(region)

  if (trackViewer.value) {
    trackViewer.value.destroy()
  }

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
    
    trackViewer.value.setData({ tracks, annotations })
  } catch (err) {
    console.error('Error creating TrackViewer:', err)
  }
}

function createTracksFromRegion(region) {
  const tracks = []
  
  let genes = region.orfs || []
  
  if (genes.length === 0 && props.currentRecord) {
    const record = props.currentRecord
    genes = record.features.filter(feature => {
      if (feature.type !== 'CDS') return false
      
      const location = feature.location
      if (!location || typeof location !== 'string') return false
      
      const match = location.match(/\[(\d+):(\d+)\]/)
      if (!match) return false
      
      const featureStart = parseInt(match[1])
      const featureEnd = parseInt(match[2])
      
      return featureStart >= region.start && featureEnd <= region.end
    })
  }

  const geneAnnotations = genes.map((gene, index) => {
    const location = gene.location
    if (!location || typeof location !== 'string') {
      return null
    }
    
    const match = location.match(/\[(\d+):(\d+)\]\(([+-])\)/)
    if (!match) {
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

  tracks.push({
    id: 'genes',
    label: 'Genes'
  })

  return { tracks, annotations: geneAnnotations }
}

function getGeneColor(orf) {
  const functions = orf.gene_functions || []
  
  if (functions.some(f => f.function === 'biosynthetic')) {
    return '#e74c3c'
  } else if (functions.some(f => f.function === 'transport')) {
    return '#3498db'
  } else if (functions.some(f => f.function === 'regulatory')) {
    return '#9b59b6'
  } else if (functions.some(f => f.function === 'resistance')) {
    return '#e67e22'
  }
  
  return '#95a5a6'
}

function resetZoom() {
  if (trackViewer.value) {
    trackViewer.value.resetZoom()
  }
}

function fitToScreen() {
  if (trackViewer.value && props.currentRegion) {
    trackViewer.value.zoomTo(props.currentRegion.start, props.currentRegion.end)
  }
}
</script>
