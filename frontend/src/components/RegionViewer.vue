<template>
  <div class="region-viewer-container">
    <div class="controls">
      <select v-model="selectedRecord" @change="onRecordChange" class="record-select">
        <option value="">Select a record...</option>
        <option v-for="record in records" :key="record.id" :value="record.id">
          {{ record.id }} ({{ record.feature_count }} features)
        </option>
      </select>
      
      <div v-if="selectedRecord" class="feature-controls">
        <label>
          <input type="checkbox" v-model="showCDS" @change="updateViewer"> CDS
        </label>
        <label>
          <input type="checkbox" v-model="showPFAM" @change="updateViewer"> PFAM domains
        </label>
        <label>
          <input type="checkbox" v-model="showOther" @change="updateViewer"> Other features
        </label>
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
import { ref, reactive, onMounted, nextTick } from 'vue'
import axios from 'axios'

export default {
  name: 'RegionViewerComponent',
  setup() {
    const viewerContainer = ref(null)
    const selectedRecord = ref('')
    const records = ref([])
    const loading = ref(false)
    const error = ref('')
    
    // Feature type filters
    const showCDS = ref(true)
    const showPFAM = ref(true) 
    const showOther = ref(false)
    
    let regionViewer = null
    let currentFeatures = []
    
    // Load records on mount
    onMounted(async () => {
      try {
        const response = await axios.get('/api/records')
        records.value = response.data
      } catch (err) {
        error.value = `Failed to load records: ${err.message}`
      }
    })
    
    const onRecordChange = async () => {
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
        // Load features for the selected record
        const response = await axios.get(`/api/records/${selectedRecord.value}/features`)
        currentFeatures = response.data.features
        
        await nextTick() // Wait for DOM update
        initializeViewer()
        updateViewer()
        
      } catch (err) {
        error.value = `Failed to load features: ${err.message}`
      } finally {
        loading.value = false
      }
    }
    
    const initializeViewer = () => {
      if (regionViewer) {
        regionViewer.destroy()
      }
      
      if (!viewerContainer.value) return
      
      // Calculate domain from features
      const positions = currentFeatures
        .filter(f => f.location)
        .map(f => {
          // Parse location string like "[164:2414](+)" or "[257:2393](+)"
          const match = f.location.match(/\[(\d+):(\d+)\]/)
          return match ? [parseInt(match[1]), parseInt(match[2])] : null
        })
        .filter(Boolean)
        .flat()
      
      const minPos = Math.min(...positions) || 0
      const maxPos = Math.max(...positions) || 1000
      const padding = (maxPos - minPos) * 0.1
      
      regionViewer = new window.BgcViewer.RegionViewer({
        container: viewerContainer.value,
        width: 800,
        height: 400,
        domain: [minPos - padding, maxPos + padding],
        onAnnotationClick: (annotation, track) => {
          console.log('Clicked annotation:', annotation, 'on track:', track)
        },
        onAnnotationHover: (annotation, track, event) => {
          // Hover is handled by the RegionViewer's built-in tooltip
        }
      })
    }
    
    const updateViewer = () => {
      if (!regionViewer || !currentFeatures.length) return
      
      // Filter features based on checkboxes
      const filteredFeatures = currentFeatures.filter(feature => {
        if (feature.type === 'CDS' && showCDS.value) return true
        if (feature.type === 'PFAM_domain' && showPFAM.value) return true
        if (feature.type !== 'CDS' && feature.type !== 'PFAM_domain' && showOther.value) return true
        return false
      })
      
      // Group features by type into tracks
      const trackData = {}
      filteredFeatures.forEach(feature => {
        if (!trackData[feature.type]) {
          trackData[feature.type] = {
            id: feature.type,
            label: feature.type,
            annotations: []
          }
        }
        
        // Parse location string like "[164:2414](+)"
        const locationMatch = feature.location?.match(/\[(\d+):(\d+)\]\(([+-])\)/)
        if (locationMatch) {
          const start = parseInt(locationMatch[1])
          const end = parseInt(locationMatch[2])
          const strand = locationMatch[3]
          
          trackData[feature.type].annotations.push({
            id: `${feature.type}-${start}-${end}`,
            trackId: feature.type,
            type: feature.type === 'CDS' ? 'arrow' : 'box',
            direction: strand === '+' ? 'right' : strand === '-' ? 'left' : 'none',
            color: getFeatureColor(feature.type),
            label: getFeatureLabel(feature),
            start: start,
            end: end
          })
        }
      })
      
      // Convert to RegionViewer format
      const tracks = Object.values(trackData).map(track => ({
        id: track.id,
        label: track.label
      }))
      
      const annotations = Object.values(trackData)
        .flatMap(track => track.annotations)
      
      regionViewer.setData({ tracks, annotations })
    }
    
    const getFeatureColor = (type) => {
      const colors = {
        'CDS': '#4CAF50',
        'PFAM_domain': '#2196F3', 
        'region': '#FF9800',
        'protocluster': '#9C27B0',
        'cand_cluster': '#F44336'
      }
      return colors[type] || '#757575'
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
    
    const refreshData = async () => {
      try {
        loading.value = true
        const response = await axios.get('/api/records')
        records.value = response.data
        
        // Clear the current selection since the data changed
        selectedRecord.value = ''
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
      records,
      loading,
      error,
      showCDS,
      showPFAM,
      showOther,
      onRecordChange,
      updateViewer,
      refreshData
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

.feature-controls {
  display: inline-flex;
  gap: 15px;
  margin-left: 10px;
}

.feature-controls label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 14px;
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
</style>
