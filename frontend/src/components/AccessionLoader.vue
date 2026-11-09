<template>
  <div class="accession-section">
    <h3>Load from {{ sourceConfig.name }}</h3>
    <p class="help-text">
      Enter a {{ sourceConfig.idDescription }} from
      <a :href="sourceConfig.homepage" target="_blank" rel="noopener noreferrer">{{ sourceConfig.name }}</a>
    </p>

    <form class="accession-form" @submit.prevent="loadAccession">
      <input
        v-model="accession"
        type="text"
        class="accession-input"
        :placeholder="`e.g. ${sourceConfig.example}`"
        :aria-label="`${sourceConfig.name} ${sourceConfig.idDescription}`"
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
      Loaded {{ loadedAccession }} &middot;
      <a :href="sourceConfig.entryUrl(loadedAccession)" target="_blank" rel="noopener noreferrer">View on {{ sourceConfig.name }}</a>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { EXTERNAL_SOURCES } from '../services/externalSources'

export default {
  name: 'AccessionLoader',
  props: {
    // Key of the external source to load from
    source: {
      type: String,
      required: true
    },
    // Accession to load immediately on mount (e.g. from the ?antismash_db= URL parameter)
    initialAccession: {
      type: String,
      default: ''
    }
  },
  emits: ['files-loaded'],
  setup(props, { emit }) {
    const sourceConfig = EXTERNAL_SOURCES[props.source]
    const storageKey = `bgc-viewer-${props.source}-accession`
    const accession = ref(props.initialAccession || localStorage.getItem(storageKey) || '')
    const loadingAccession = ref('')
    const loadedAccession = ref('')
    const error = ref('')
    const isLoading = ref(false)
    // Aborted on unmount, so a pending download can't update the URL or emit after the user switched sources
    let abortController = null

    const loadAccession = async () => {
      const acc = accession.value.trim()
      if (!acc) return

      if (!sourceConfig.pattern.test(acc)) {
        error.value = `Invalid ${sourceConfig.idDescription}: ${acc} (expected e.g. ${sourceConfig.example})`
        return
      }

      error.value = ''
      isLoading.value = true
      loadingAccession.value = acc
      abortController = new AbortController()
      const { signal } = abortController

      try {
        // Fetched via the backend, as the external sources don't allow cross-origin requests
        const response = await fetch(`/api/${props.source}/${acc}`, { signal })
        if (!response.ok) {
          const body = await response.json().catch(() => ({}))
          throw new Error(body.error || `Failed to fetch ${acc} (HTTP ${response.status})`)
        }

        // Wrap the response as a File so it goes through the same loading path as uploads
        const blob = await response.blob()
        if (signal.aborted) return
        const file = new File([blob], `${acc}.json`, { type: 'application/json' })

        localStorage.setItem(storageKey, acc)
        loadedAccession.value = acc

        // Reflect the loaded accession in the URL so the view can be shared
        const url = new URL(window.location.href)
        url.searchParams.set(sourceConfig.urlParam, acc)
        window.history.replaceState(null, '', url)

        emit('files-loaded', [{ id: 0, name: file.name, type: 'json', file }])
      } catch (err) {
        if (signal.aborted) return
        console.error(`Failed to load from ${sourceConfig.name}:`, err)
        // fetch() throws a TypeError on network failures
        error.value = err instanceof TypeError
          ? `Could not reach the server to load ${acc}`
          : err.message
      } finally {
        isLoading.value = false
      }
    }

    onMounted(() => {
      if (props.initialAccession) {
        loadAccession()
      }
    })

    onBeforeUnmount(() => {
      abortController?.abort()
    })

    return {
      sourceConfig,
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
.accession-section {
  padding: 15px;
  border-bottom: 1px solid #e0e0e0;
  flex: 1; /* Take available space */
  min-height: 0; /* Allow shrinking */
  overflow-y: auto; /* Keep messages reachable when the sidebar section is short */
}

.accession-section h3 {
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

.loaded-message a {
  color: inherit;
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
