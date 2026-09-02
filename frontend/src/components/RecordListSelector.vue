<template>
  <section class="record-list-selector-section">
    <h2>Record selection</h2>
    
    <div v-if="!hasDatabase" class="no-database-message">
      <p>No processed database found. Please select a folder and run preprocessing first.</p>
    </div>
    
    <div v-else class="entries-section">
      <!-- Search and Controls - Always visible -->
      <div class="controls-bar">
        <div class="search-container">
          <input
            v-model="searchQuery"
            @input="debouncedSearch"
            type="text"
            placeholder="Search (e.g., 'PF00457 organism')"
            title="Search across filenames, record IDs, organisms, products, and all attribute values. Multiple space-separated terms will be combined with AND logic (all terms must match)."
            class="search-input"
          />
          <button v-if="searchQuery" @click="clearSearch" class="clear-search">×</button>
          <button
            type="button"
            class="search-help-button"
            popovertarget="record-search-help"
            aria-label="Show advanced search examples"
            title="Advanced search examples"
          >?</button>
          <div
            id="record-search-help"
            ref="searchHelpPopover"
            popover="auto"
            class="search-help-popover"
          >
            <div class="search-help-header">
              <strong>Search examples</strong>
              <button
                type="button"
                class="search-help-close"
                popovertarget="record-search-help"
                popovertargetaction="hide"
                aria-label="Close search examples"
                title="Close"
              >×</button>
            </div>
            <div class="search-examples">
              <button
                v-for="example in searchExamples"
                :key="example.query"
                type="button"
                class="search-example"
                @click="applySearchExample(example.query)"
              >
                <span>{{ example.label }}</span>
                <code>{{ example.query }}</code>
              </button>
            </div>
            <details class="search-fields-disclosure">
              <summary>Available fields ({{ searchFields.length }})</summary>
              <div class="search-fields-list">
                <code v-for="field in searchFields" :key="field">{{ field }}</code>
              </div>
            </details>
          </div>
        </div>
        
        <div class="pagination-controls" v-if="!loading || entriesData.length > 0">
          <button
            @click="goToPage(currentPage - 1)"
            :disabled="currentPage <= 1 || loading"
            class="page-btn"
          >
            ‹ Prev
          </button>
          
          <span class="page-info">
            Page {{ currentPage }} of {{ totalPages }}
          </span>
          
          <button
            @click="goToPage(currentPage + 1)"
            :disabled="currentPage >= totalPages || loading"
            class="page-btn"
          >
            Next ›
          </button>
        </div>
      </div>
      
      <!-- Error State -->
      <div v-if="error" class="error">
        {{ error }}
      </div>
      
      <!-- Records List -->
      <div v-else-if="entriesData.length === 0 && !loading" class="no-records">
        <p v-if="searchQuery">No records found matching "{{ searchQuery }}"</p>
        <p v-else>No records available in the database.</p>
      </div>
      
      <div v-else-if="entriesData.length > 0" class="records-container">
        <div class="records-list" :class="{ 'refreshing': loading, 'loading-state': loading }">
          <div
            v-for="record in entriesData"
            :key="record.entry_id"
            :class="['record-item', { 'selected': selectedEntryId === record.entry_id, 'loading': loadingRecordId === record.entry_id }]"
            @click="selectRecord(record)"
          >
            <div class="record-content">
              <!-- First Line: Record ID -->
              <div class="record-id-line">
                {{ record.record_id }}
              </div>
              
              <!-- Second Line: All other attributes in dark gray -->
              <div class="record-details-line">
                <span class="detail-item">{{ record.filename }}</span>
                <span class="detail-separator">•</span>
                <span class="detail-item" v-if="record.organism">{{ record.organism }}</span>
                <span class="detail-separator" v-if="record.organism">•</span>
                <span class="detail-item" v-if="record.description">{{ record.description }}</span>
                <span class="detail-separator" v-if="record.description">•</span>
                <span class="detail-item">{{ record.feature_count }} features</span>
                <span class="detail-separator" v-if="record.products && record.products.length > 0">•</span>
                <span class="detail-item" v-if="record.products && record.products.length > 0">
                  {{ record.products.slice(0, 2).join(', ') }}
                </span>
                <span class="detail-separator" v-if="record.cluster_types && record.cluster_types.length > 0">•</span>
                <span class="detail-item" v-if="record.cluster_types && record.cluster_types.length > 0">
                  {{ record.cluster_types.slice(0, 2).join(', ') }}
                </span>
              </div>
            </div>
            <div v-if="loadingRecordId === record.entry_id" class="spinner-container">
              <LoadingSpinner />
            </div>
          </div>
        </div>
        
        <!-- Bottom Pagination Info -->
        <div class="pagination-info">
          Showing {{ ((currentPage - 1) * perPage) + 1 }}-{{ Math.min(currentPage * perPage, total) }} 
          of {{ total }} records
        </div>
      </div>
    </div>
  </section>
</template>

<script>
import { ref, computed, onMounted, watch, toRefs } from 'vue'
import axios from 'axios'
import LoadingSpinner from './LoadingSpinner.vue'

export default {
  name: 'RecordListSelector',
  components: {
    LoadingSpinner
  },
  props: {
    dataRoot: {
      type: String,
      default: ''
    },
    indexPath: {
      type: String,
      default: ''
    }
  },
  emits: ['record-selected'],
  setup(props, { emit }) {
    const { dataRoot, indexPath } = toRefs(props)
    
    const entriesData = ref([])
    const loading = ref(false)
    const error = ref('')
    const selectedEntryId = ref('')
    const loadingRecordId = ref('')
    const hasDatabase = ref(false)
    
    // Pagination
    const currentPage = ref(1)
    const perPage = ref(20)
    const total = ref(0)
    const totalPages = ref(0)
    
    // Search
    const searchQuery = ref('')
    const searchTimeout = ref(null)
    const searchHelpPopover = ref(null)
    const searchFields = ref([])
    const searchExamples = [
      { label: 'Specific attribute', query: 'db_xref:PF00067.25' },
      { label: 'Exact phrase', query: 'organism:"Streptomyces coelicolor"' },
      { label: 'Both conditions', query: 'db_xref:PF00067.25 AND organism:Streptomyces' },
      { label: 'Either value', query: 'db_xref:(PF00067.25 OR PF00501.29)' },
      { label: 'Exclude value', query: 'db_xref:PF00067.25 NOT gene_kind:pseudogene' },
      { label: 'Prefix', query: 'db_xref:PF00067*' },
      { label: 'Record ID', query: 'record_id:NC_003888.3' },
      { label: 'Filename', query: 'filename:NC_003888.3.json' }
    ]
    
    const loadEntries = async (page = 1, search = '') => {
      loading.value = true
      error.value = ''
      
      try {
        const params = {
          page,
          per_page: perPage.value
        }
        
        if (search.trim()) {
          params.search = search.trim()
        }
        
        const response = await axios.get('/api/database-entries', { params })
        
        // Map backend response to use entry_id consistently
        // Backend returns 'id' but we use 'entry_id' in frontend for clarity
        entriesData.value = response.data.entries.map(entry => ({
          ...entry,
          entry_id: entry.id  // Map id to entry_id for consistency
        }))
        total.value = response.data.total
        totalPages.value = response.data.total_pages
        currentPage.value = response.data.page
        searchFields.value = response.data.search_fields || []
        hasDatabase.value = true
        
      } catch (err) {
        if (err.response?.status === 404) {
          hasDatabase.value = false
          entriesData.value = []
          total.value = 0
          totalPages.value = 0
        } else {
          error.value = err.response?.data?.error || 'Failed to load entries'
          entriesData.value = []
          total.value = 0
          totalPages.value = 0
        }
      } finally {
        loading.value = false
      }
    }
    
    const goToPage = (page) => {
      if (page >= 1 && page <= totalPages.value) {
        loadEntries(page, searchQuery.value)
      }
    }
    
    const selectRecord = async (record) => {
      if (loadingRecordId.value) return
      
      // Check if this is actually the same entry (using unique entry_id)
      if (selectedEntryId.value === record.entry_id) return
      
      selectedEntryId.value = record.entry_id
      
      // Simply emit the selected record - let the parent handle loading
      emit('record-selected', {
        entryId: record.entry_id,
        recordId: record.record_id,
        filename: record.filename
      })
    }
    
    const debouncedSearch = () => {
      if (searchTimeout.value) {
        clearTimeout(searchTimeout.value)
      }
      
      searchTimeout.value = setTimeout(() => {
        currentPage.value = 1
        loadEntries(1, searchQuery.value)
      }, 300)
    }
    
    const clearSearch = () => {
      searchQuery.value = ''
      currentPage.value = 1
      loadEntries(1, '')
    }

    const applySearchExample = (query) => {
      searchQuery.value = query
      currentPage.value = 1
      searchHelpPopover.value?.hidePopover?.()
      loadEntries(1, query)
    }
    
    const setDatabasePath = async (databasePath) => {
      if (!databasePath) return
      
      try {
        await axios.post('/api/select-database', {
          path: databasePath
        })
        console.log('Database path set to:', databasePath)
      } catch (err) {
        console.warn('Failed to set database path:', err.response?.data?.error || err.message)
      }
    }
    
    const refreshEntries = async () => {
      await loadEntries(currentPage.value, searchQuery.value)
    }
    
    const clearRecords = () => {
      entriesData.value = []
      total.value = 0
      totalPages.value = 0
      currentPage.value = 1
      selectedEntryId.value = ''
      loadingRecordId.value = ''
      searchQuery.value = ''
      searchFields.value = []
      hasDatabase.value = false
    }
    
    // Watch for index path changes - this is the primary path to the database file
    watch(indexPath, async (newPath, oldPath) => {
      if (newPath) {
        await setDatabasePath(newPath)
        // Reload entries after setting the database path
        await loadEntries(1, '')
      } else {
        // Clear records if path is cleared
        clearRecords()
      }
    }, { immediate: true })
    
    onMounted(async () => {
      // Only use indexPath - it should always point to a database file
      if (indexPath.value) {
        await setDatabasePath(indexPath.value)
        await loadEntries()
      } else {
        await loadEntries()
      }
    })
    
    return {
      entriesData,
      loading,
      error,
      selectedEntryId,
      loadingRecordId,
      hasDatabase,
      currentPage,
      perPage,
      total,
      totalPages,
      searchQuery,
      searchHelpPopover,
      searchExamples,
      searchFields,
      loadEntries,
      goToPage,
      selectRecord,
      debouncedSearch,
      clearSearch,
      applySearchExample,
      refreshEntries,
      clearRecords
    }
  }
}
</script>

<style scoped>
.record-list-selector-section {
  padding: 15px;
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.record-list-selector-section h2 {
  margin: 0 0 12px 0;
  color: #333;
  font-size: 16px;
}

.no-database-message {
  text-align: center;
  padding: 30px 15px;
  color: #666;
  font-style: italic;
  background: #f8f9fa;
  border-radius: 4px;
  font-size: 13px;
}

.loading {
  text-align: center;
  padding: 30px 15px;
  color: #666;
  font-style: italic;
  font-size: 13px;
}

.error {
  color: #d32f2f;
  background: #ffebee;
  padding: 10px;
  border-radius: 4px;
  margin: 10px 0;
  font-size: 13px;
}

.entries-section {
  width: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex: 1;
}

.controls-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 10px;
  flex-shrink: 0;
}

.search-container {
  position: relative;
  display: flex;
  align-items: center;
  gap: 2px;
  flex: 1;
  max-width: 100%;
}

.search-input {
  padding: 6px 30px 6px 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 13px;
  width: 100%;
}

.search-input:focus {
  border-color: #1976d2;
  outline: none;
  box-shadow: 0 0 0 2px rgba(25, 118, 210, 0.2);
}

.clear-search {
  position: absolute;
  right: 26px;
  background: none;
  border: none;
  font-size: 16px;
  cursor: pointer;
  color: #666;
  padding: 0;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.clear-search:hover {
  color: #333;
}

.search-help-button,
.search-help-close {
  border: 1px solid #bbb;
  background: white;
  color: #444;
  cursor: pointer;
  flex: 0 0 auto;
}

.search-help-button {
  width: 22px;
  height: 28px;
  padding: 0;
  border: none;
  border-radius: 50%;
  font-size: 14px;
  font-weight: 700;
}

.search-help-button:hover,
.search-help-button:focus-visible {
  color: #1976d2;
}

.search-help-popover {
  position: fixed;
  inset: 50% auto auto 50%;
  transform: translate(-50%, -50%);
  width: min(520px, calc(100vw - 24px));
  max-height: min(520px, calc(100vh - 48px));
  margin: 0;
  padding: 0;
  border: 1px solid #bbb;
  border-radius: 6px;
  background: white;
  color: #222;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.22);
  overflow: auto;
}

.search-help-popover::backdrop {
  background: rgba(0, 0, 0, 0.12);
}

.search-help-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #ddd;
  font-size: 14px;
}

.search-help-close {
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  font-size: 20px;
  line-height: 1;
}

.search-examples {
  display: grid;
  padding: 6px;
}

.search-example {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr);
  gap: 10px;
  align-items: baseline;
  padding: 8px;
  border: 0;
  border-radius: 3px;
  background: transparent;
  color: #333;
  text-align: left;
  cursor: pointer;
}

.search-example:hover,
.search-example:focus-visible {
  background: #eef5fb;
  outline: none;
}

.search-example span {
  font-size: 12px;
  color: #666;
}

.search-example code {
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: 12px;
  color: #174f78;
}

.search-fields-disclosure {
  border-top: 1px solid #ddd;
  font-size: 12px;
}

.search-fields-disclosure summary {
  padding: 10px 14px;
  color: #444;
  cursor: pointer;
  font-weight: 600;
}

.search-fields-disclosure summary:hover,
.search-fields-disclosure summary:focus-visible {
  background: #f5f7f8;
}

.search-fields-list {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  max-height: 160px;
  padding: 0 12px 12px;
  overflow-y: auto;
}

.search-fields-list code {
  padding: 2px 5px;
  border: 1px solid #d8dde1;
  border-radius: 3px;
  color: #174f78;
  background: #f7f9fa;
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.page-btn {
  padding: 5px 10px;
  border: 1px solid #ccc;
  background: white;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s ease;
}

.page-btn:hover:not(:disabled) {
  background-color: #f5f5f5;
  border-color: #999;
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-info {
  font-size: 13px;
  color: #666;
  white-space: nowrap;
}

.no-entries {
  text-align: center;
  padding: 30px 15px;
  color: #666;
  font-style: italic;
  background: #f8f9fa;
  border-radius: 4px;
  font-size: 13px;
}

.records-container {
  position: relative;
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.records-list {
  border: 1px solid #eee;
  border-radius: 4px;
  background: white;
  overflow-y: auto;
  transition: opacity 0.2s ease, background-color 0.2s ease;
  flex: 1;
}

.records-list.refreshing {
  opacity: 0.7;
}

.records-list.loading-state {
  background-color: #f5f5f5;
}

.record-item {
  display: flex;
  align-items: flex-start;
  padding: 8px 12px;
  border-bottom: 1px solid #eee;
  cursor: pointer;
  transition: background-color 0.2s ease;
  position: relative;
}

.record-item:last-child {
  border-bottom: none;
}

.record-item:hover {
  background-color: #f5f5f5;
}

.record-item.selected {
  background-color: #e3f2fd;
  border-left: 3px solid #1976d2;
}

.record-item.loading {
  pointer-events: none;
  opacity: 0.7;
}

.record-content {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
  width: 100%;
}

/* First Line: Record ID */
.record-id-line {
  font-weight: 600;
  color: #333;
  font-size: 14px;
}

/* Second Line: All other attributes */
.record-details-line {
  font-size: 12px;
  color: #555;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  line-height: 1.3;
}

.detail-item {
  color: #555;
}

.detail-separator {
  color: #999;
  margin: 0 2px;
}

.spinner-container {
  margin-left: auto;
  padding-left: 8px;
  display: flex;
  align-items: center;
}

.no-records {
  text-align: center;
  padding: 30px 15px;
  color: #666;
  font-style: italic;
  background: #f8f9fa;
  border-radius: 4px;
  font-size: 13px;
}

.no-records p {
  margin: 0;
}

.pagination-info {
  text-align: center;
  font-size: 13px;
  color: #666;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #eee;
}

/* Responsive design */
@media (max-width: 768px) {
  .controls-bar {
    flex-direction: column;
    align-items: stretch;
  }
  
  .search-container {
    max-width: none;
  }

  .search-example {
    grid-template-columns: 1fr;
    gap: 3px;
  }
  
  .pagination-controls {
    justify-content: center;
  }
  
  .record-content {
    gap: 6px;
  }
  
  .record-id-line {
    font-size: 15px;
  }
  
  .record-details-line {
    font-size: 12px;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
  }
  
  .detail-separator {
    display: none;
  }
}
</style>
