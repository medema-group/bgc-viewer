<template>
  <div v-if="feature" class="feature-details">
    <div class="feature-content">
      <!-- Primary Information -->
      <div class="info-section">
        <div class="info-row" v-if="feature.qualifiers?.locus_tag?.[0]">
          <span class="info-label">Locus tag</span>
          <span class="info-value">{{ feature.qualifiers.locus_tag[0] }}</span>
        </div>
        
        <div class="info-row" v-if="feature.qualifiers?.protein_id?.[0]">
          <span class="info-label">Protein ID</span>
          <span class="info-value">{{ feature.qualifiers.protein_id[0] }}</span>
        </div>
        
        <div class="info-row" v-if="feature.qualifiers?.gene?.[0]">
          <span class="info-label">Gene</span>
          <span class="info-value">{{ feature.qualifiers.gene[0] }}</span>
        </div>
        
        <div class="info-row" v-if="feature.qualifiers?.product?.[0]">
          <span class="info-label">Product</span>
          <span class="info-value">{{ feature.qualifiers.product[0] }}</span>
        </div>
        
        <div class="info-row" v-if="feature.location">
          <span class="info-label">Location</span>
          <span class="info-value">{{ formatLocation(feature.location) }}</span>
        </div>
        
        <div class="info-row" v-if="feature.qualifiers?.gene_kind?.[0]">
          <span class="info-label">Gene kind</span>
          <span class="info-value">{{ feature.qualifiers.gene_kind[0] }}</span>
        </div>
        
        <!-- Additional qualifiers below primary ones -->
        <div v-for="(value, key) in getAdditionalQualifiers()" :key="key" class="info-row">
          <span class="info-label">{{ formatQualifierKey(key) }}</span>
          <span class="info-value">
            <template v-if="Array.isArray(value) && value.length > 1">
              <details class="expandable-list">
                <summary>{{ value.length }} items</summary>
                <div class="expanded-content">{{ value.join(', ') }}</div>
              </details>
            </template>
            <template v-else>
              {{ formatQualifierValue(value) }}
            </template>
          </span>
        </div>
      </div>
      
      <!-- PFAM Domain Information (for CDS features) -->
      <div v-if="pfamDomains.length > 0" class="info-section">
        <h4>Pfam hits</h4>
        <div v-for="(domain, index) in pfamDomains" :key="index" class="pfam-domain">
          <div class="pfam-header">
            <strong>{{ domain.id }}</strong>
            <span v-if="domain.description" class="pfam-description">
              ({{ domain.description }})
            </span>
          </div>
          <div class="pfam-details">
            <span v-if="domain.location">{{ domain.location }}</span>
            <span v-if="domain.score">(score: {{ domain.score }}</span>
            <span v-if="domain.evalue">, e-value: {{ domain.evalue }})</span>
          </div>
        </div>
      </div>
      
      <!-- Gene Ontology Terms -->
      <div v-if="goTerms.length > 0" class="info-section">
        <h4>Gene Ontology terms</h4>
        <div v-for="(term, index) in goTerms" :key="index" class="go-term">
          {{ term }}
        </div>
      </div>
      
      <!-- Sequences (for CDS features) -->
      <div v-if="feature.type === 'CDS'" class="info-section sequences">
        <h4>Sequences</h4>
        
        <div v-if="feature.qualifiers?.translation?.[0]" class="sequence-block">
          <div class="sequence-header">
            <span class="sequence-label">AA sequence</span>
            <button @click="copyToClipboard(feature.qualifiers.translation[0], 'amino acid')" 
                    class="copy-button">
              Copy to clipboard
            </button>
          </div>
          <pre class="sequence-text">{{ formatSequence(feature.qualifiers.translation[0]) }}</pre>
        </div>
        
        <div v-if="feature.qualifiers?.nucleotide?.[0]" class="sequence-block">
          <div class="sequence-header">
            <span class="sequence-label">Nucleotide sequence</span>
            <button @click="copyToClipboard(feature.qualifiers.nucleotide[0], 'nucleotide')" 
                    class="copy-button">
              Copy to clipboard
            </button>
          </div>
          <pre class="sequence-text">{{ formatSequence(feature.qualifiers.nucleotide[0]) }}</pre>
        </div>
      </div>
    </div>
  </div>
  
  <div v-else class="no-selection">
    <p>Click on a feature to view details</p>
  </div>
</template>

<script>
import { ref, computed, watch } from 'vue'

export default {
  name: 'FeatureDetails',
  props: {
    // The selected feature object
    feature: {
      type: Object,
      default: null
    },
    // All features (to find related PFAM domains)
    allFeatures: {
      type: Array,
      default: () => []
    }
  },
  emits: ['close'],
  setup(props) {
    // Extract PFAM domains for CDS features
    const pfamDomains = computed(() => {
      if (!props.feature || props.feature.type !== 'CDS') return []
      if (!props.allFeatures || props.allFeatures.length === 0) return []
      
      const locusTag = props.feature.qualifiers?.locus_tag?.[0]
      if (!locusTag) return []
      
      // Find all PFAM_domain features with matching locus_tag
      return props.allFeatures
        .filter(f => f.type === 'PFAM_domain' && f.qualifiers?.locus_tag?.[0] === locusTag)
        .map(f => ({
          id: f.qualifiers?.db_xref?.[0]?.replace('PFAM:', '') || 
              f.qualifiers?.inference?.[0]?.match(/PFAM:([^,\s]+)/)?.[1] || 
              'Unknown',
          description: f.qualifiers?.description?.[0] || '',
          location: formatDomainLocation(f.qualifiers),
          score: f.qualifiers?.score?.[0] || '',
          evalue: f.qualifiers?.evalue?.[0] || ''
        }))
    })
    
    // Extract Gene Ontology terms
    const goTerms = computed(() => {
      if (!props.feature) return []
      
      const terms = []
      const qualifiers = props.feature.qualifiers || {}
      
      // Check for GO terms in various qualifier fields
      if (qualifiers.go_function) {
        terms.push(...qualifiers.go_function)
      }
      if (qualifiers.go_process) {
        terms.push(...qualifiers.go_process)
      }
      if (qualifiers.go_component) {
        terms.push(...qualifiers.go_component)
      }
      
      return terms
    })
    
    const formatDomainLocation = (qualifiers) => {
      if (!qualifiers) return ''
      
      const start = qualifiers.protein_start?.[0]
      const end = qualifiers.protein_end?.[0]
      
      if (start && end) {
        return `[${start}:${end}]`
      }
      
      return ''
    }
    
    const formatLocation = (location) => {
      if (!location) return ''
      
      // Parse location string like "[164:2414](+)" or "[164:2414](-)"
      const match = location.match(/\[<?(\d+):>?(\d+)\](?:\(([+-])\))?/)
      if (!match) return location
      
      const start = parseInt(match[1])
      const end = parseInt(match[2])
      const strand = match[3] || ''
      const length = end - start
      
      return `${start.toLocaleString()} - ${end.toLocaleString()}${strand ? ', ' + strand : ''} (total: ${length.toLocaleString()} nt)`
    }
    
    const getFeatureTitle = () => {
      if (!props.feature) return ''
      
      const qualifiers = props.feature.qualifiers || {}
      
      // Try to get a meaningful title
      const locusTag = qualifiers.locus_tag?.[0] || ''
      const product = qualifiers.product?.[0] || ''
      const gene = qualifiers.gene?.[0] || ''
      const description = qualifiers.description?.[0] || ''
      
      // For CDS features
      if (props.feature.type === 'CDS') {
        if (locusTag && product) {
          return `${locusTag} - ${product}`
        }
        if (locusTag) return locusTag
        if (gene) return gene
        if (product) return product
      }
      
      // For PFAM domains
      if (props.feature.type === 'PFAM_domain') {
        const pfamId = qualifiers.db_xref?.[0]?.replace('PFAM:', '') || 'PFAM domain'
        if (description) {
          return `${pfamId} - ${description}`
        }
        return pfamId
      }
      
      // For other features
      if (description) return description
      if (product) return product
      
      return props.feature.type || 'Feature Details'
    }
    
    const formatQualifierKey = (key) => {
      // Convert snake_case to Title Case
      return key
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ')
    }
    
    const formatQualifierValue = (value) => {
      if (Array.isArray(value)) {
        return value.join(', ')
      }
      return value
    }
    
    const hasAdditionalQualifiers = () => {
      if (!props.feature || !props.feature.qualifiers) return false
      
      const displayedKeys = [
        'locus_tag', 'protein_id', 'gene', 'product', 
        'gene_kind', 'translation', 'nucleotide',
        'go_function', 'go_process', 'go_component'
      ]
      
      const additionalKeys = Object.keys(props.feature.qualifiers)
        .filter(key => !displayedKeys.includes(key))
      
      return additionalKeys.length > 0
    }
    
    const getAdditionalQualifiers = () => {
      if (!props.feature || !props.feature.qualifiers) return {}
      
      const displayedKeys = [
        'locus_tag', 'protein_id', 'gene', 'product', 
        'gene_kind', 'translation', 'nucleotide',
        'go_function', 'go_process', 'go_component'
      ]
      
      const additional = {}
      Object.keys(props.feature.qualifiers).forEach(key => {
        if (!displayedKeys.includes(key)) {
          additional[key] = props.feature.qualifiers[key]
        }
      })
      
      return additional
    }
    
    const formatSequence = (sequence) => {
      if (!sequence) return ''
      
      // Format sequence with 60 characters per line
      const formatted = []
      for (let i = 0; i < sequence.length; i += 60) {
        formatted.push(sequence.slice(i, i + 60))
      }
      return formatted.join('\n')
    }
    
    const copyToClipboard = async (text, type) => {
      try {
        await navigator.clipboard.writeText(text)
        alert(`${type} sequence copied to clipboard!`)
      } catch (err) {
        console.error('Failed to copy to clipboard:', err)
        alert('Failed to copy to clipboard')
      }
    }
    
    return {
      pfamDomains,
      goTerms,
      formatLocation,
      getFeatureTitle,
      formatQualifierKey,
      formatQualifierValue,
      hasAdditionalQualifiers,
      getAdditionalQualifiers,
      formatSequence,
      copyToClipboard
    }
  }
}
</script>

<style scoped>
.feature-details {
  border: 1px solid #ddd;
  border-radius: 6px;
  background: white;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

.feature-content {
  padding: 12px;
  max-height: 500px;
  overflow-y: auto;
}

.info-section {
  margin-bottom: 12px;
}

.info-section:last-child {
  margin-bottom: 0;
}

.info-section h4 {
  margin: 0 0 6px 0;
  color: #495057;
  font-size: 14px;
  font-weight: 600;
  border-bottom: 1px solid #e9ecef;
  padding-bottom: 3px;
}

.info-row {
  display: flex;
  /* padding: 3px 0; */
  gap: 8px;
}

.info-label {
  font-weight: 600;
  color: #495057;
  min-width: 100px;
  flex-shrink: 0;
}

.info-value {
  color: #212529;
  flex: 1;
  word-break: break-word;
}

.pfam-domain {
  margin: 4px 0;
  padding: 6px 10px;
  background: #f8f9fa;
  border-radius: 4px;
  border-left: 3px solid #2196F3;
}

.pfam-header {
  margin-bottom: 2px;
}

.pfam-header strong {
  color: #1976D2;
  font-family: 'Courier New', monospace;
}

.pfam-description {
  color: #666;
  font-style: italic;
  margin-left: 8px;
}

.pfam-details {
  font-size: 12px;
  color: #666;
  font-family: 'Courier New', monospace;
}

.go-term {
  padding: 2px 0;
  color: #495057;
  font-size: 14px;
}

.sequences {
  border-top: 1px solid #e9ecef;
  padding-top: 12px;
  margin-top: 12px;
}

.sequence-block {
  margin: 10px 0;
}

.sequence-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.sequence-label {
  font-weight: 600;
  color: #495057;
}

.copy-button {
  padding: 4px 12px;
  font-size: 12px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.copy-button:hover {
  background: #0056b3;
}

.sequence-text {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  padding: 8px;
  font-family: 'Courier New', monospace;
  font-size: 11px;
  line-height: 1.4;
  color: #212529;
  overflow-x: auto;
  max-height: 150px;
  overflow-y: auto;
  white-space: pre;
}

.no-selection {
  padding: 40px 20px;
  text-align: center;
  color: #666;
  font-style: italic;
}

/* Scrollbar styling */
.feature-content::-webkit-scrollbar,
.sequence-text::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.feature-content::-webkit-scrollbar-track,
.sequence-text::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.feature-content::-webkit-scrollbar-thumb,
.sequence-text::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 4px;
}

.feature-content::-webkit-scrollbar-thumb:hover,
.sequence-text::-webkit-scrollbar-thumb:hover {
  background: #555;
}

.expandable-list {
  display: inline;
}

.expandable-list summary {
  cursor: pointer;
  color: #007bff;
}

.expandable-list summary:hover {
  color: #0056b3;
  text-decoration: underline;
}

.expandable-list[open] summary {
  color: #212529;
}

.expandable-list[open] summary:hover {
  text-decoration: none;
}

.expanded-content {
  display: inline;
  margin-left: 4px;
}
</style>
