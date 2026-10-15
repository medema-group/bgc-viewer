<template>
  <div class="antismash-db-section">
    <h3>Load from antiSMASH DB</h3>
    <p class="help-text">
      Enter a genome accession number from
      <a href="https://antismash-db.secondarymetabolites.org/" target="_blank" rel="noopener noreferrer">antiSMASH DB</a>
    </p>

    <form class="accession-form" @submit.prevent="loadAccession">
      <input
        v-model="accession"
        type="text"
        class="accession-input"
        placeholder="e.g. GCF_000725555.1"
        :disabled="isLoading"
      />
      <button
        type="submit"
        class="load-btn"
        :disabled="isLoading || !accession.trim()"
      >
        Load
      </button>
    </form>

    <div v-if="error" class="error-message">
      {{ error }}
    </div>

    <div v-if="isLoading" class="loading-message">
      <div class="spinner"></div>
      <span>Loading {{ loadingAccession }}...</span>
    </div>

    <div v-else-if="loadedAccession && !error" class="loaded-message">
      Loaded {{ loadedAccession }}
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'

const ACCESSION_STORAGE_KEY = 'bgc-viewer-antismash-db-accession'

export default {
  name: 'AntismashDBLoader',
  emits: ['files-loaded'],
  setup(props, { emit }) {
    const accession = ref(localStorage.getItem(ACCESSION_STORAGE_KEY) || '')
    const loadingAccession = ref('')
    const loadedAccession = ref('')
    const error = ref('')
    const isLoading = ref(false)

    const loadAccession = async () => {
      const acc = accession.value.trim()
      if (!acc) return

      // Only allow characters that can appear in an accession, so the value can't alter the URL path
      if (!/^[A-Za-z0-9_.-]+$/.test(acc)) {
        error.value = `Invalid accession number: ${acc}`
        return
      }

      error.value = ''
      isLoading.value = true
      loadingAccession.value = acc

      try {
        // Fetched via the backend, as antiSMASH DB doesn't allow cross-origin requests
        const response = await fetch(`/api/antismash-db/${acc}`)
        if (!response.ok) {
          const body = await response.json().catch(() => ({}))
          throw new Error(body.error || `Failed to fetch ${acc} (HTTP ${response.status})`)
        }

        // Wrap the response as a File so it goes through the same loading path as uploads
        const blob = await response.blob()
        const file = new File([blob], `${acc}.json`, { type: 'application/json' })

        localStorage.setItem(ACCESSION_STORAGE_KEY, acc)
        loadedAccession.value = acc
        emit('files-loaded', [{ id: 0, name: file.name, type: 'json', file }])
      } catch (err) {
        console.error('Failed to load from antiSMASH DB:', err)
        // fetch() throws a TypeError on network failures
        error.value = err instanceof TypeError
          ? `Could not reach the server to load ${acc}`
          : err.message
      } finally {
        isLoading.value = false
      }
    }

    return {
      accession,
      loadingAccession,
      loadedAccession,
      error,
      isLoading,
      loadAccession
    }
  }
}
</script>

<style scoped>
.antismash-db-section {
  padding: 15px;
  border-bottom: 1px solid #e0e0e0;
}

.antismash-db-section h3 {
  margin: 0 0 8px 0;
  font-size: 16px;
  color: #2c3e50;
}

.help-text {
  margin: 0 0 15px 0;
  font-size: 13px;
  color: #666;
}

.help-text a {
  color: #1976d2;
  text-decoration: none;
}

.help-text a:hover {
  text-decoration: underline;
}

.accession-form {
  display: flex;
  gap: 8px;
}

.accession-input {
  flex: 1;
  min-width: 0;
  padding: 8px 12px;
  font-size: 14px;
  color: #2c3e50;
  border: 1px solid #ccc;
  border-radius: 4px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.accession-input:focus {
  outline: none;
  border-color: #1976d2;
  box-shadow: 0 0 0 3px rgba(25, 118, 210, 0.1);
}

.load-btn {
  padding: 8px 20px;
  background-color: #1976d2;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.load-btn:hover:not(:disabled) {
  background-color: #1565c0;
}

.load-btn:disabled {
  background-color: #90caf9;
  cursor: not-allowed;
}

.error-message {
  margin-top: 12px;
  padding: 10px;
  background-color: #ffebee;
  border-left: 4px solid #f44336;
  color: #c62828;
  font-size: 13px;
  border-radius: 4px;
}

.loading-message {
  margin-top: 12px;
  padding: 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  background-color: #e3f2fd;
  border-radius: 4px;
  font-size: 13px;
  color: #1976d2;
}

.loaded-message {
  margin-top: 12px;
  padding: 8px 10px;
  background-color: #e8f5e9;
  border-radius: 4px;
  font-size: 12px;
  color: #2e7d32;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid #1976d2;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
