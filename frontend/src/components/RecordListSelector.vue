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
            :key="record.id"
            :class="['record-item', { 'selected': selectedRecordId === record.id, 'loading': loadingRecordId === record.id }]"
            @click="selectAndLoadRecord(record)"
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
            <div v-if="loadingRecordId === record.id" class="spinner-container">
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
    databaseFolder: {
      type: String,
      default: ''
    }
  },
  emits: ['record-loaded'],
  setup(props, { emit }) {
    const { databaseFolder } = toRefs(props)
    
    const entriesData = ref([])
    const loading = ref(false)
    const error = ref('')
    const selectedRecordId = ref('')
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
        
        entriesData.value = response.data.entries
        total.value = response.data.total
        totalPages.value = response.data.total_pages
        currentPage.value = response.data.page
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
    
    const selectAndLoadRecord = async (record) => {
      if (loadingRecordId.value || selectedRecordId.value === record.id) return
      
      selectedRecordId.value = record.id
      loadingRecordId.value = record.id
      
      try {
        const response = await axios.post('/api/load-entry', {
          id: record.id
        })
        
        emit('record-loaded', {
          entryId: record.id,
          filename: response.data.filename,
          recordId: response.data.record_id,
          recordInfo: response.data.record_info
        })
        
      } catch (err) {
        error.value = err.response?.data?.error || 'Failed to load record'
        selectedRecordId.value = ''
      } finally {
        loadingRecordId.value = ''
      }
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
    
    const setDataRoot = async (folderPath) => {
      if (!folderPath) return
      
      try {
        await axios.post('/api/set-data-root', {
          path: folderPath
        })
        console.log('Data root set to:', folderPath)
      } catch (err) {
        console.warn('Failed to set data root:', err.response?.data?.error || err.message)
      }
    }
    
    const refreshEntries = () => {
      loadEntries(currentPage.value, searchQuery.value)
    }
    
    const clearRecords = () => {
      entriesData.value = []
      total.value = 0
      totalPages.value = 0
      currentPage.value = 1
      selectedRecordId.value = ''
      loadingRecordId.value = ''
      searchQuery.value = ''
      hasDatabase.value = false
    }
    
    // Watch for database folder changes
    watch(databaseFolder, async (newFolder) => {
      if (newFolder) {
        await setDataRoot(newFolder)
        // Reload entries after setting the data root
        loadEntries(1, '')
      }
    }, { immediate: true })
    
    onMounted(() => {
      // If we already have a database folder, set it and load entries
      if (databaseFolder.value) {
        setDataRoot(databaseFolder.value).then(() => {
          loadEntries()
        })
      } else {
        loadEntries()
      }
    })
    
    return {
      entriesData,
      loading,
      error,
      selectedRecordId,
      loadingRecordId,
      hasDatabase,
      currentPage,
      perPage,
      total,
      totalPages,
      searchQuery,
      loadEntries,
      goToPage,
      selectAndLoadRecord,
      debouncedSearch,
      clearSearch,
      refreshEntries,
      clearRecords
    }
  }
}
</script>

<style scoped>
.record-list-selector-section {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  background-color: #f9f9f9;
}

.record-list-selector-section h2 {
  margin: 0 0 16px 0;
  color: #333;
}

.no-database-message {
  text-align: center;
  padding: 40px 20px;
  color: #666;
  font-style: italic;
  background: #f8f9fa;
  border-radius: 4px;
}

.loading {
  text-align: center;
  padding: 40px 20px;
  color: #666;
  font-style: italic;
}

.error {
  color: #d32f2f;
  background: #ffebee;
  padding: 15px;
  border-radius: 4px;
  margin: 15px 0;
}

.entries-section {
  width: 100%;
}

.controls-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 15px;
}

.search-container {
  position: relative;
  display: flex;
  align-items: center;
  flex: 1;
  max-width: 300px;
}

.search-input {
  padding: 8px 30px 8px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 14px;
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
  font-size: 18px;
  cursor: pointer;
  color: #666;
  padding: 0;
  width: 20px;
  height: 20px;
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
  gap: 10px;
}

.page-btn {
  padding: 6px 12px;
  border: 1px solid #ccc;
  background: white;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
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
  font-size: 14px;
  color: #666;
  white-space: nowrap;
}

.no-entries {
  text-align: center;
  padding: 40px 20px;
  color: #666;
  font-style: italic;
  background: #f8f9fa;
  border-radius: 4px;
}

.records-container {
  position: relative;
}

.records-list {
  border: 1px solid #eee;
  border-radius: 4px;
  background: white;
  max-height: 300px;
  overflow-y: auto;
  transition: opacity 0.2s ease, background-color 0.2s ease;
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
  padding: 10px 16px;
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
  border-left: 4px solid #1976d2;
}

.record-item.loading {
  pointer-events: none;
  opacity: 0.7;
}

.record-content {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
}

/* First Line: Record ID */
.record-id-line {
  font-weight: 600;
  color: #333;
  font-size: 16px;
}

/* Second Line: All other attributes */
.record-details-line {
  font-size: 13px;
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
  padding-left: 10px;
  display: flex;
  align-items: center;
}



.pagination-info {
  text-align: center;
  font-size: 14px;
  color: #666;
  margin-top: 15px;
  padding-top: 15px;
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
