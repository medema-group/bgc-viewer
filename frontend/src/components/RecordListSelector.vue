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
import { BGCViewerAPIProvider } from '../services/dataProviders/BGCViewerAPIProvider'
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
    
    // Direct records mode (for uploaded JSON files)
    const isDirectMode = ref(false)
    const allDirectRecords = ref([])
    const dataProvider = ref(null) // Store reference to data provider for searching
    
    // Pagination
    const currentPage = ref(1)
    const perPage = ref(20)
    const total = ref(0)
    const totalPages = ref(0)
    
    // Search
    const searchQuery = ref('')
    const searchTimeout = ref(null)
    
    const loadEntries = async (page = 1, search = '') => {
      // Always use the provider (which is set by default or when switching sources)
      await searchRecords(search, page)
    }
    
    const goToPage = (page) => {
      if (page >= 1 && page <= totalPages.value) {
        currentPage.value = page
        searchRecords(searchQuery.value, page)
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
    
    const searchRecords = async (query, page = null) => {
      if (!dataProvider.value) {
        return
      }
      
      loading.value = true
      error.value = ''
      
      try {
        const currentPageNum = page !== null ? page : currentPage.value
        
        // Use the provider's search method with pagination
        const result = await dataProvider.value.searchRecords(query, currentPageNum, perPage.value)
        
        // For file providers, we need to handle client-side pagination
        if (isDirectMode.value) {
          // Store all results for client-side pagination
          allDirectRecords.value = result.records.map(record => ({
            entry_id: record.recordId,
            record_id: record.recordId,
            filename: record.filename || 'uploaded.json',
            description: record.recordInfo?.description || '',
            cluster_types: []
          }))
          
          // Apply client-side pagination
          const start = (currentPageNum - 1) * perPage.value
          const end = start + perPage.value
          entriesData.value = allDirectRecords.value.slice(start, end)
          total.value = allDirectRecords.value.length
          totalPages.value = Math.ceil(allDirectRecords.value.length / perPage.value)
        } else {
          // For API provider, pagination is handled server-side
          entriesData.value = result.records.map(record => ({
            entry_id: record.entryId || record.recordId,  // Use full entryId from API
            record_id: record.recordId,
            filename: record.filename || 'unknown',
            description: record.recordInfo?.description || '',
            organism: record.organism,
            products: record.products,
            cluster_types: record.clusterTypes,
            feature_count: record.featureCount
          }))
          total.value = result.total
          totalPages.value = result.totalPages
          currentPage.value = result.currentPage
        }
        
        hasDatabase.value = true
      } catch (err) {
        console.error('Search error:', err)
        error.value = 'Failed to search records'
        entriesData.value = []
        total.value = 0
        totalPages.value = 0
      } finally {
        loading.value = false
      }
    }
    
    const debouncedSearch = () => {
      if (searchTimeout.value) {
        clearTimeout(searchTimeout.value)
      }
      
      searchTimeout.value = setTimeout(() => {
        currentPage.value = 1
        searchRecords(searchQuery.value, 1)
      }, 300)
    }
    
    const clearSearch = () => {
      searchQuery.value = ''
      currentPage.value = 1
      searchRecords('', 1)
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
      await searchRecords(searchQuery.value, currentPage.value)
    }
    
    const clearRecords = () => {
      entriesData.value = []
      allDirectRecords.value = []
      isDirectMode.value = false
      dataProvider.value = null
      total.value = 0
      totalPages.value = 0
      currentPage.value = 1
      selectedEntryId.value = ''
      loadingRecordId.value = ''
      searchQuery.value = ''
      hasDatabase.value = false
    }
    
    const setRecordsFromProvider = async (provider, isDirect = true) => {
      // Set data provider (can be JSONFileProvider or BGCViewerAPIProvider)
      isDirectMode.value = isDirect
      dataProvider.value = provider
      
      // Reset search and pagination
      currentPage.value = 1
      searchQuery.value = ''
      
      // Load initial records
      await searchRecords('', 1)
      
      hasDatabase.value = true
      loading.value = false
    }
    
    // Watch for index path changes - tell backend which database to use
    watch(indexPath, async (newPath, oldPath) => {
      // Ensure provider exists
      if (!dataProvider.value) {
        dataProvider.value = new BGCViewerAPIProvider()
        isDirectMode.value = false
      }
      
      if (newPath) {
        await setDatabasePath(newPath)
        // Reload entries after setting the database path
        await loadEntries(1, '')
      } else {
        // Clear records if path is cleared
        clearRecords()
      }
    }, { immediate: true })
    
    onMounted(() => {
      // Provider is created by the watch if needed
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
      loadEntries,
      goToPage,
      selectRecord,
      debouncedSearch,
      clearSearch,
      refreshEntries,
      clearRecords,
      setRecordsFromProvider
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
  right: 8px;
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
