<template>
  <div v-if="data" class="simple-details">
    <div v-if="elementType" class="details-header">
      <h3>{{ elementType }}</h3>
    </div>
    <div class="details-content">
      <div class="info-section">
        <!-- Dynamic rendering of all data properties in original order -->
        <div v-for="key in displayKeys" :key="key" class="info-row">
          <span class="info-label">{{ formatLabel(key) }}</span>
          <span class="info-value">{{ formatValue(key, displayData[key]) }}</span>
        </div>
      </div>
    </div>
  </div>
  
  <div v-else class="no-selection">
    <p>Click on an element to view details</p>
  </div>
</template>

<script>
import { computed } from 'vue'

export default {
  name: 'SimpleDetails',
  props: {
    // The data object to display
    data: {
      type: Object,
      default: null
    },
    // The type of element for the header
    elementType: {
      type: String,
      default: ''
    }
  },
  setup(props) {
    
    // Compute display data, filtering out unwanted keys
    const displayData = computed(() => {
      if (!props.data) return {}
      
      const filtered = {}
      const excludeKeys = ['_elementType']
      
      Object.keys(props.data).forEach(key => {
        if (!excludeKeys.includes(key)) {
          filtered[key] = props.data[key]
        }
      })
      
      return filtered
    })
    
    // Compute display keys in original order
    const displayKeys = computed(() => {
      if (!props.data) return []
      
      const excludeKeys = ['_elementType']
      
      return Object.keys(props.data).filter(key => !excludeKeys.includes(key))
    })
    
    const formatLabel = (key) => {
      // Convert snake_case and camelCase to sentence case
      const words = key
        .replace(/_/g, ' ')
        .replace(/([A-Z])/g, ' $1')
        .split(' ')
        .filter(word => word.length > 0)
      
      if (words.length === 0) return ''
      
      // Capitalize first word, lowercase the rest
      return words[0].charAt(0).toUpperCase() + words[0].slice(1).toLowerCase() +
             (words.length > 1 ? ' ' + words.slice(1).map(w => w.toLowerCase()).join(' ') : '')
    }
    
    const formatValue = (key, value) => {
      if (value === null || value === undefined) return 'N/A'
      
      // Format specific types
      if (typeof value === 'number') {
        // Format e-values in scientific notation
        if (key.toLowerCase().includes('evalue') && value < 0.01) {
          return value.toExponential(2)
        }
        // Format scores and other numbers with appropriate precision
        if (key.toLowerCase().includes('score') || key.toLowerCase().includes('bitscore')) {
          return value.toFixed(1)
        }
        // Format percentages
        if (key.toLowerCase().includes('percent') || key.toLowerCase().includes('identity') || key.toLowerCase().includes('coverage')) {
          return `${value.toFixed(1)}%`
        }
        // Default number formatting
        return value.toLocaleString()
      }
      
      // Format arrays
      if (Array.isArray(value)) {
        if (value.length === 0) return 'None'
        if (value.length === 1) return String(value[0])
        return value.join(', ')
      }
      
      // Format booleans
      if (typeof value === 'boolean') {
        return value ? 'Yes' : 'No'
      }
      
      // Format objects (stringify)
      if (typeof value === 'object') {
        return JSON.stringify(value, null, 2)
      }
      
      // Default string conversion
      return String(value)
    }
    
    return {
      displayData,
      displayKeys,
      formatLabel,
      formatValue
    }
  }
}
</script>

<style scoped>
.simple-details {
  border: 1px solid #ddd;
  border-radius: 6px;
  background: white;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
}

.details-header {
  padding: 10px 12px;
  background: #f8f9fa;
  border-bottom: 1px solid #ddd;
}

.details-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #212529;
}

.details-content {
  padding: 12px;
}

.info-section {
  margin-bottom: 12px;
}

.info-section:last-child {
  margin-bottom: 0;
}

.info-row {
  display: flex;
  gap: 8px;
  padding: 1px 0;
}

.info-label {
  font-weight: 600;
  color: #495057;
  min-width: 140px;
  flex-shrink: 0;
}

.info-value {
  color: #212529;
  flex: 1;
  word-break: break-word;
}

.no-selection {
  padding: 40px 20px;
  text-align: center;
  color: #666;
  font-style: italic;
}

/* Scrollbar styling */
.details-content::-webkit-scrollbar {
  width: 8px;
}

.details-content::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.details-content::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 4px;
}

.details-content::-webkit-scrollbar-thumb:hover {
  background: #555;
}
</style>
