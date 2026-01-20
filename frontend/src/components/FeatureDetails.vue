<template>
  <div v-if="feature" class="feature-details">
    <div class="feature-content">
      <!-- Header -->
      <div class="feature-header">
        <h3>{{ feature.type }}</h3>
      </div>
      
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
                <div class="expanded-content">
                  <component :is="renderQualifierValue(key, value)" />
                </div>
              </details>
            </template>
            <template v-else>
              {{ formatQualifierValue(value) }}
            </template>
          </span>
        </div>
        
        <!-- PFAM Domain Information (for CDS features) -->
        <div v-if="pfamDomains.length > 0" class="info-row">
          <span class="info-label">Pfam hits</span>
          <span class="info-value">
            <details class="expandable-list">
              <summary>{{ pfamDomains.length }} items</summary>
              <div class="expanded-content">
                <SortableTable 
                  :headers="pfamTableHeaders" 
                  :rows="pfamTableRows"
                />
              </div>
            </details>
          </span>
        </div>
        
        <!-- MiBIG Entries (for CDS features with locus_tag) -->
        <div v-if="feature.type === 'CDS' && mibigEntries.length > 0" class="info-row">
          <span class="info-label">MiBIG hits</span>
          <span class="info-value">
            <details class="expandable-list">
              <summary>{{ mibigEntries.length }} items</summary>
              <div class="expanded-content">
                <SortableTable 
                  :headers="mibigTableHeaders" 
                  :rows="mibigTableRows"
                />
              </div>
            </details>
          </span>
        </div>
        
        <!-- Gene Ontology Terms -->
        <div v-if="goTerms.length > 0" class="info-row">
          <span class="info-label">GO terms</span>
          <span class="info-value">
            <details class="expandable-list">
              <summary>{{ goTerms.length }} items</summary>
              <div class="expanded-content">
                <ul class="go-term-list">
                  <li v-for="(term, index) in goTerms" :key="index" class="go-term">
                    {{ term }}
                  </li>
                </ul>
              </div>
            </details>
          </span>
        </div>
      </div>
      
      <!-- Sequences (for CDS features) -->
      <div v-if="feature.type === 'CDS'" class="info-section sequences">
        <div v-if="feature.qualifiers?.translation?.[0]" class="info-row">
          <span class="info-label">AA sequence</span>
          <span class="info-value">
            <details class="expandable-list">
              <summary>
                Show sequence
                <button @click.stop="copyToClipboard(feature.qualifiers.translation[0], 'amino acid')" 
                        class="copy-button copy-button-inline">
                  Copy to clipboard
                </button>
              </summary>
              <div class="expanded-content">
                <pre class="sequence-text">{{ formatSequence(feature.qualifiers.translation[0]) }}</pre>
              </div>
            </details>
          </span>
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
import { ref, computed, watch, h } from 'vue'
import SimpleTable from './SimpleTable.vue'
import SortableTable from './SortableTable.vue'

export default {
  name: 'FeatureDetails',
  components: {
    SimpleTable,
    SortableTable
  },
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
    },
    // Data provider for fetching MiBIG entries
    dataProvider: {
      type: Object,
      default: null
    },
    // Record information containing recordId
    recordInfo: {
      type: Object,
      default: null
    },
    // Region number for MiBIG entry retrieval
    regionNumber: {
      type: String,
      default: '1'
    }
  },
  emits: ['close'],
  setup(props) {
    // MiBIG entries state
    const mibigEntries = ref([])
    const mibigLoading = ref(false)
    const mibigError = ref(null)
    
    // Fetch MiBIG entries when CDS feature is selected
    const fetchMiBIGEntries = async () => {
      mibigEntries.value = []
      mibigLoading.value = false
      mibigError.value = null
      
      if (!props.feature || props.feature.type !== 'CDS') return
      if (!props.dataProvider || !props.recordInfo) return
      
      const locusTag = props.feature.qualifiers?.locus_tag?.[0]
      if (!locusTag) return
      
      mibigLoading.value = true
      
      try {
        const response = await props.dataProvider.getMiBIGEntries(props.recordInfo.recordId, locusTag, props.regionNumber)
        mibigEntries.value = response.entries || []
      } catch (error) {
        // Don't show error if it's just "not found" - many features won't have MiBIG entries
        if (error.response?.status === 404) {
          mibigEntries.value = []
        } else {
          console.error('Error fetching MiBIG entries:', error)
          mibigError.value = 'Failed to load MiBIG entries'
        }
      } finally {
        mibigLoading.value = false
      }
    }
    
    // Watch for feature changes
    watch(() => props.feature, () => {
      fetchMiBIGEntries()
    }, { immediate: true })
    
    // Extract PFAM domains for CDS features
    const pfamDomains = computed(() => {
      if (!props.feature || props.feature.type !== 'CDS') return []
      if (!props.allFeatures || props.allFeatures.length === 0) return []
      
      const locusTag = props.feature.qualifiers?.locus_tag?.[0] || props.feature.qualifiers?.gene?.[0]
      if (!locusTag) return []
      
      // Find all PFAM_domain features with matching locus_tag or gene
      return props.allFeatures
        .filter(f => f.type === 'PFAM_domain' && (f.qualifiers?.locus_tag?.[0] === locusTag || f.qualifiers?.gene?.[0] === locusTag))
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
      // Convert snake_case to Sentence case (only first word capitalized)
      const words = key.split('_')
      return words.map((word, index) => 
        index === 0 ? word.charAt(0).toUpperCase() + word.slice(1) : word
      ).join(' ')
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
    
    // Render function for qualifier values based on key type
    const renderQualifierValue = (key, values) => {
      // Hard-coded renderers for known formats
      const renderers = {
        'NRPS_PKS': renderNRPSPKS,
        'sec_met_domain': renderSecMetDomain,
      }
      
      // Use specific renderer if available, otherwise fall back to default
      const renderer = renderers[key] || renderDefaultList
      return renderer(values)
    }
    
    // Renderer for NRPS_PKS format
    // "Domain: PKS_KS(Hybrid-KS) (10-463). E-value: 9.5e-118. Score: 385.7. Matches aSDomain: ..."
    const renderNRPSPKS = (values) => {
      const parsedItems = values.map((item) => {
        // Split by ". " to separate domain header from properties
        const parts = item.split(/\.\s+/)
        if (parts.length === 0) {
          return { domain: item }
        }
        
        // First part is the domain (everything before first ". ")
        const domain = parts[0].replace(/^Domain:\s*/, '').trim()
        const data = { domain }
        
        // Parse remaining parts as key-value pairs
        parts.slice(1).forEach(prop => {
          const colonIndex = prop.indexOf(':')
          if (colonIndex > -1) {
            const key = prop.substring(0, colonIndex).trim()
            const val = prop.substring(colonIndex + 1).trim()
            data[key] = val
          }
        })
        
        return data
      })
      
      // Get keys from first item (excluding 'domain')
      const firstItem = parsedItems[0] || {}
      const keys = Object.keys(firstItem).filter(k => k !== 'domain')
      const headers = ['', ...keys] // Empty string for domain column
      
      const rows = [
        headers,
        ...parsedItems.map(item => {
          const row = [item.domain || '']
          keys.forEach(key => {
            row.push(item[key] || '')
          })
          return row
        })
      ]
      
      return h(SimpleTable, { rows })
    }
    
    // Renderer for sec_met_domain format
    // "hglE (E-value: 1.4e-217, bitscore: 720.9, seeds: 4, tool: rule-based-clusters)"
    const renderSecMetDomain = (values) => {
      const parsedItems = values.map((item) => {
        const match = item.match(/^([^(]+)\s*\(([^)]+)\)/)
        if (!match) {
          return { name: item }
        }
        
        const name = match[1].trim()
        const details = match[2]
        const data = { name }
        
        // Parse key-value pairs
        const pairs = details.split(/,\s*/)
        pairs.forEach(pair => {
          const colonIndex = pair.indexOf(':')
          if (colonIndex > -1) {
            const key = pair.substring(0, colonIndex).trim()
            const val = pair.substring(colonIndex + 1).trim()
            data[key] = val
          }
        })
        
        return data
      })
      
      // Get keys from first item (excluding 'name')
      const firstItem = parsedItems[0] || {}
      const keys = Object.keys(firstItem).filter(k => k !== 'name')
      const headers = ['', ...keys] // Empty string for name column
      
      const rows = [
        headers,
        ...parsedItems.map(item => {
          const row = [item.name || '']
          keys.forEach(key => {
            row.push(item[key] || '')
          })
          return row
        })
      ]
      
      return h(SimpleTable, { rows })
    }
    
    // Default renderer for unstructured lists
    const renderDefaultList = (values) => {
      const items = values.map((item, idx) => 
        h('li', { key: idx }, item)
      )
      return h('ul', { class: 'qualifier-list' }, items)
    }
    
    // Format E-value for display
    const formatEvalue = (evalue) => {
      if (typeof evalue === 'number') {
        return evalue.toExponential(2)
      }
      return evalue
    }
    
    // Prepare PFAM table data for SortableTable
    const pfamTableHeaders = [
      { label: 'Domain', cellClass: 'pfam-id' },
      { label: 'Description', cellClass: 'pfam-description' },
      { label: 'Location', cellClass: 'pfam-location' },
      { label: 'Score', cellClass: 'pfam-score' },
      { label: 'E-value', cellClass: 'pfam-evalue' }
    ]
    
    const pfamTableRows = computed(() => {
      return pfamDomains.value.map(domain => [
        domain.id,
        domain.description,
        domain.location,
        domain.score,
        domain.evalue
      ])
    })
    
    // Prepare MiBIG table data for SortableTable
    const mibigTableHeaders = [
      { label: 'MIBiG Protein', cellClass: 'mibig-protein' },
      { label: 'Description', cellClass: 'mibig-description' },
      { label: 'MIBiG Cluster', cellClass: 'mibig-cluster' },
      { label: 'Product', cellClass: 'mibig-product' },
      { label: '% ID', cellClass: 'mibig-percent' },
      { label: 'BLAST Score', cellClass: 'mibig-score' },
      { label: '% Coverage', cellClass: 'mibig-percent' },
      { label: 'E-value', cellClass: 'mibig-evalue' }
    ]
    
    const mibigTableRows = computed(() => {
      return mibigEntries.value.map(entry => [
        entry.mibig_protein,
        entry.description,
        h('a', {
          href: `https://mibig.secondarymetabolites.org/go/${entry.mibig_cluster}`,
          target: '_blank',
          rel: 'noopener noreferrer'
        }, entry.mibig_cluster),
        entry.mibig_product,
        `${parseFloat(entry.percent_identity).toFixed(1)}%`,
        parseFloat(entry.blast_score).toFixed(1),
        `${parseFloat(entry.percent_coverage).toFixed(1)}%`,
        formatEvalue(entry.evalue)
      ])
    })
    
    return {
      pfamDomains,
      goTerms,
      mibigEntries,
      mibigLoading,
      mibigError,
      formatLocation,
      getFeatureTitle,
      formatQualifierKey,
      formatQualifierValue,
      hasAdditionalQualifiers,
      getAdditionalQualifiers,
      formatSequence,
      copyToClipboard,
      renderQualifierValue,
      formatEvalue,
      pfamTableHeaders,
      pfamTableRows,
      mibigTableHeaders,
      mibigTableRows
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
  display: flex;
  flex-direction: column;
}

.feature-content {
  padding: 12px;
}

.feature-header {
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #dee2e6;
}

.feature-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #212529;
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
  padding: 1px 0;
  gap: 8px;
}

.info-label {
  font-weight: 600;
  color: #495057;
  min-width: 180px;
  flex-shrink: 0;
}

.info-value {
  color: #212529;
  flex: 1;
  word-break: break-word;
}

.go-term {
  padding: 2px 0;
  color: #495057;
  font-size: 14px;
}

.go-term-list {
  margin: 4px 0 0 0;
  padding-left: 20px;
  list-style: disc;
}

.go-term-list li {
  margin: 2px 0;
  font-size: 13px;
  line-height: 1.4;
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

.copy-button-inline {
  margin-left: 8px;
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
  color: #212529;
}

.expandable-list summary:hover {
  color: #495057;
}

.expandable-list[open] summary {
  color: #212529;
}

.expandable-list[open] summary:hover {
  color: #495057;
}

.expanded-content {
  display: block;
  margin-left: 0;
}

.qualifier-list {
  margin: 4px 0 0 0;
  padding-left: 20px;
  list-style: disc;
}

.qualifier-list li {
  margin: 2px 0;
  font-size: 13px;
  line-height: 1.4;
}

.qualifier-table {
  margin: 4px 0 0 0;
  border-collapse: collapse;
  font-size: 12px;
  width: 100%;
}

.qualifier-table td {
  padding: 3px 8px;
  border: 1px solid #dee2e6;
  vertical-align: top;
}

.qualifier-table tr:nth-child(even) {
  background-color: #f8f9fa;
}

.qualifier-table td.col-domain,
.qualifier-table td.col-name,
.qualifier-table td.col-key {
  font-weight: 600;
  color: #495057;
}

.qualifier-table td.col-e_value,
.qualifier-table td.col-evalue,
.qualifier-table td.col-score,
.qualifier-table td.col-bitscore {
  font-family: 'Courier New', monospace;
  text-align: right;
}

.loading-text {
  color: #666;
  font-style: italic;
  margin: 4px 0;
}

.error-text {
  color: #dc3545;
  margin: 4px 0;
}

/* PFAM and MiBIG table cell styling */
:deep(.sortable-table td.pfam-id),
:deep(.sortable-table td.mibig-protein) {
  font-weight: 600;
  color: #495057;
}

:deep(.sortable-table td.mibig-protein) {
  font-family: 'Courier New', monospace;
}

:deep(.sortable-table td.pfam-description),
:deep(.sortable-table td.mibig-description) {
  color: #666;
}

:deep(.sortable-table td.mibig-description) {
  max-width: 200px;
}

:deep(.sortable-table td.pfam-location) {
  font-family: 'Courier New', monospace;
  color: #495057;
}

:deep(.sortable-table td.mibig-cluster a) {
  color: #007bff;
  text-decoration: none;
  font-family: 'Courier New', monospace;
}

:deep(.sortable-table td.mibig-cluster a:hover) {
  text-decoration: underline;
}

:deep(.sortable-table td.mibig-product) {
  color: #495057;
  font-size: 11px;
}

:deep(.sortable-table td.pfam-score),
:deep(.sortable-table td.pfam-evalue),
:deep(.sortable-table td.mibig-percent),
:deep(.sortable-table td.mibig-score),
:deep(.sortable-table td.mibig-evalue) {
  font-family: 'Courier New', monospace;
  text-align: right;
  white-space: nowrap;
}
</style>
