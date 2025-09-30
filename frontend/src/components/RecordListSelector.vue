<template>
  <section class="record-list-selector-section">
    <h2>Dataset Records</h2>
    
    <div v-if="!hasDatabase" class="no-database-message">
      <p>No processed database found. Please select a folder and run preprocessing first.</p>
    </div>
    
    <div v-else-if="loading && entriesData.length === 0" class="loading">
      Loading entries...
    </div>
    
    <div v-else-if="error" class="error">
      {{ error }}
    </div>
    
    <div v-else class="entries-section">
      <!-- Search and Controls -->
      <div class="controls-bar">
        <div class="search-container">
          <input
            v-model="searchQuery"
            @input="debouncedSearch"
            type="text"
            placeholder="Search files, records, or attributes..."
            title="Search across filenames, record IDs, and all attribute values (organisms, products, descriptions, etc.)"
            class="search-input"
          />
          <button v-if="searchQuery" @click="clearSearch" class="clear-search">×</button>
        </div>
        
        <div class="pagination-controls">
          <button
            @click="goToPage(currentPage - 1)"
            :disabled="currentPage <= 1"
            class="page-btn"
          >
            ‹ Prev
          </button>
          
          <span class="page-info">
            Page {{ currentPage }} of {{ totalPages }}
          </span>
          
          <button
            @click="goToPage(currentPage + 1)"
            :disabled="currentPage >= totalPages"
            class="page-btn"
          >
            Next ›
          </button>
        </div>
      </div>
      
      <!-- Records List -->
      <div v-if="entriesData.length === 0" class="no-records">
        <p v-if="searchQuery">No records found matching "{{ searchQuery }}"</p>
        <p v-else>No records available in the database.</p>
      </div>
      
      <div v-else class="records-list">
        <div
          v-for="record in entriesData"
          :key="record.id"
          :class="['record-item', { 'selected': selectedRecordId === record.id, 'loading': loadingRecordId === record.id }]"
          @click="selectAndLoadRecord(record)"
        >
          <div class="record-main">
            <div class="record-filename">
              <span class="filename">{{ record.filename }}</span>
              <span class="record-id">{{ record.record_id }}</span>
            </div>
            <div class="record-stats">
              <span class="attribute-count">{{ record.attribute_count }} attributes</span>
            </div>
          </div>
          <div v-if="loadingRecordId === record.id" class="loading-spinner">
            ⟳
          </div>
        </div>
      </div>
      
      <!-- Bottom Pagination Info -->
      <div class="pagination-info" v-if="entriesData.length > 0">
        Showing {{ ((currentPage - 1) * perPage) + 1 }}-{{ Math.min(currentPage * perPage, total) }} 
        of {{ total }} records
      </div>
    </div>
  </section>
</template>

<script>
import { ref, computed, onMounted, watch, toRefs } from 'vue'
import axios from 'axios'

export default {
  name: 'RecordListSelector',
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
          recordId: record.id,
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
    
    const setDatabasePath = async (folderPath) => {
      if (!folderPath) return
      
      try {
        await axios.post('/api/set-database-path', {
          path: folderPath
        })
        console.log('Database path set to:', folderPath)
      } catch (err) {
        console.warn('Failed to set database path:', err.response?.data?.error || err.message)
      }
    }
    
    const refreshEntries = () => {
      loadEntries(currentPage.value, searchQuery.value)
    }
    
    // Watch for database folder changes
    watch(databaseFolder, async (newFolder) => {
      if (newFolder) {
        await setDatabasePath(newFolder)
        // Reload entries after setting the database path
        loadEntries(1, '')
      }
    }, { immediate: true })
    
    onMounted(() => {
      // If we already have a database folder, set it and load entries
      if (databaseFolder.value) {
        setDatabasePath(databaseFolder.value).then(() => {
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
      refreshEntries
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

.records-list {
  border: 1px solid #eee;
  border-radius: 4px;
  background: white;
  max-height: 600px;
  overflow-y: auto;
}

.record-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
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

.record-main {
  flex-grow: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.record-filename {
  flex-grow: 1;
}

.filename {
  font-weight: 600;
  color: #333;
  display: block;
  margin-bottom: 2px;
}

.record-id {
  font-size: 13px;
  color: #666;
  font-family: monospace;
}

.record-stats {
  text-align: right;
  margin-left: 15px;
}

.attribute-count {
  font-size: 12px;
  color: #888;
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 3px;
  white-space: nowrap;
}

.loading-spinner {
  margin-left: 10px;
  font-size: 16px;
  animation: spin 1s linear infinite;
  color: #1976d2;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
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
  
  .record-main {
    flex-direction: column;
    align-items: flex-start;
    gap: 5px;
  }
  
  .record-stats {
    margin-left: 0;
    text-align: left;
  }
}
</style>
