<template>
  <div class="entry-selector">
    <div class="header">
      <h3>Select Dataset Entry</h3>
      <div class="search-container">
        <input
          v-model="searchQuery"
          @input="debouncedSearch"
          type="text"
          placeholder="Search files or records..."
          class="search-input"
        />
        <button v-if="searchQuery" @click="clearSearch" class="clear-search">×</button>
      </div>
    </div>

    <div v-if="loading" class="loading">
      Loading entries...
    </div>

    <div v-else-if="error" class="error">
      {{ error }}
    </div>

    <div v-else-if="entries.length === 0" class="no-entries">
      <p v-if="searchQuery">No entries found matching "{{ searchQuery }}"</p>
      <p v-else>No entries available. Please preprocess some data first.</p>
    </div>

    <div v-else class="entries-container">
      <div class="entries-list">
        <div
          v-for="entry in entries"
          :key="entry.id"
          :class="['entry-item', { 'selected': selectedEntryId === entry.id }]"
          @click="selectEntry(entry)"
        >
          <div class="entry-main">
            <div class="entry-filename">{{ entry.filename }}</div>
            <div class="entry-record">{{ entry.record_id }}</div>
          </div>
          <div class="entry-stats">
            <span class="attribute-count">{{ entry.attribute_count }} attributes</span>
          </div>
        </div>
      </div>

      <div class="pagination" v-if="totalPages > 1">
        <button
          @click="goToPage(currentPage - 1)"
          :disabled="currentPage <= 1"
          class="page-btn"
        >
          Previous
        </button>
        
        <div class="page-numbers">
          <button
            v-for="page in visiblePages"
            :key="page"
            @click="goToPage(page)"
            :class="['page-btn', { 'active': page === currentPage }]"
          >
            {{ page }}
          </button>
        </div>
        
        <button
          @click="goToPage(currentPage + 1)"
          :disabled="currentPage >= totalPages"
          class="page-btn"
        >
          Next
        </button>
      </div>

      <div class="pagination-info">
        Showing {{ ((currentPage - 1) * perPage) + 1 }}-{{ Math.min(currentPage * perPage, total) }} 
        of {{ total }} entries
      </div>
    </div>

    <div class="actions" v-if="selectedEntryId">
      <button @click="loadSelectedEntry" :disabled="loadingEntry" class="load-btn">
        {{ loadingEntry ? 'Loading...' : 'Load Entry' }}
      </button>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'

export default {
  name: 'EntrySelector',
  emits: ['entry-loaded'],
  setup(props, { emit }) {
    const entries = ref([])
    const loading = ref(false)
    const error = ref('')
    const selectedEntryId = ref('')
    const loadingEntry = ref(false)
    
    // Pagination
    const currentPage = ref(1)
    const perPage = ref(20)
    const total = ref(0)
    const totalPages = ref(0)
    
    // Search
    const searchQuery = ref('')
    const searchTimeout = ref(null)
    
    const visiblePages = computed(() => {
      const pages = []
      const start = Math.max(1, currentPage.value - 2)
      const end = Math.min(totalPages.value, currentPage.value + 2)
      
      for (let i = start; i <= end; i++) {
        pages.push(i)
      }
      return pages
    })
    
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
        
        entries.value = response.data.entries
        total.value = response.data.total
        totalPages.value = response.data.total_pages
        currentPage.value = response.data.page
        
      } catch (err) {
        error.value = err.response?.data?.error || 'Failed to load entries'
        entries.value = []
        total.value = 0
        totalPages.value = 0
      } finally {
        loading.value = false
      }
    }
    
    const goToPage = (page) => {
      if (page >= 1 && page <= totalPages.value) {
        loadEntries(page, searchQuery.value)
      }
    }
    
    const selectEntry = (entry) => {
      selectedEntryId.value = entry.id
    }
    
    const loadSelectedEntry = async () => {
      if (!selectedEntryId.value) return
      
      loadingEntry.value = true
      
      try {
        const response = await axios.post('/api/load-entry', {
          id: selectedEntryId.value
        })
        
        emit('entry-loaded', {
          entryId: selectedEntryId.value,
          filename: response.data.filename,
          recordId: response.data.record_id,
          recordInfo: response.data.record_info
        })
        
      } catch (err) {
        error.value = err.response?.data?.error || 'Failed to load entry'
      } finally {
        loadingEntry.value = false
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
    
    const refreshEntries = () => {
      loadEntries(currentPage.value, searchQuery.value)
    }
    
    onMounted(() => {
      loadEntries()
    })
    
    return {
      entries,
      loading,
      error,
      selectedEntryId,
      loadingEntry,
      currentPage,
      perPage,
      total,
      totalPages,
      visiblePages,
      searchQuery,
      loadEntries,
      goToPage,
      selectEntry,
      loadSelectedEntry,
      debouncedSearch,
      clearSearch,
      refreshEntries
    }
  }
}
</script>

<style scoped>
.entry-selector {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 20px;
  margin: 20px 0;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h3 {
  margin: 0;
  color: #333;
}

.search-container {
  position: relative;
  display: flex;
  align-items: center;
}

.search-input {
  padding: 8px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 14px;
  width: 250px;
}

.search-input:focus {
  border-color: #1976d2;
  outline: none;
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

.loading, .error, .no-entries {
  text-align: center;
  padding: 40px 20px;
}

.loading {
  color: #666;
  font-style: italic;
}

.error {
  color: #d32f2f;
  background: #ffebee;
  border-radius: 4px;
}

.no-entries {
  color: #666;
}

.entries-container {
  margin-bottom: 20px;
}

.entries-list {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #eee;
  border-radius: 4px;
}

.entry-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.entry-item:last-child {
  border-bottom: none;
}

.entry-item:hover {
  background-color: #f5f5f5;
}

.entry-item.selected {
  background-color: #e3f2fd;
  border-color: #1976d2;
}

.entry-main {
  flex-grow: 1;
}

.entry-filename {
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}

.entry-record {
  font-size: 14px;
  color: #666;
}

.entry-stats {
  text-align: right;
}

.attribute-count {
  font-size: 12px;
  color: #888;
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 3px;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  margin: 20px 0;
}

.page-numbers {
  display: flex;
  gap: 5px;
}

.page-btn {
  padding: 8px 12px;
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

.page-btn.active {
  background-color: #1976d2;
  color: white;
  border-color: #1976d2;
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pagination-info {
  text-align: center;
  font-size: 14px;
  color: #666;
  margin-bottom: 10px;
}

.actions {
  text-align: center;
  margin-top: 20px;
}

.load-btn {
  padding: 10px 20px;
  background-color: #1976d2;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 16px;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.load-btn:hover:not(:disabled) {
  background-color: #1565c0;
}

.load-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
