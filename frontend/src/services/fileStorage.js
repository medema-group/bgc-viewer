/**
 * Utility for persisting uploaded files in IndexedDB
 * Allows reloading files after page refresh
 */

const DB_NAME = 'bgc-viewer-files'
const DB_VERSION = 1
const STORE_NAME = 'uploaded-files'

class FileStorageService {
  constructor() {
    this.db = null
  }

  /**
   * Initialize the IndexedDB database
   */
  async init() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION)

      request.onerror = () => reject(request.error)
      request.onsuccess = () => {
        this.db = request.result
        resolve(this.db)
      }

      request.onupgradeneeded = (event) => {
        const db = event.target.result
        
        // Create object store if it doesn't exist
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true })
          store.createIndex('timestamp', 'timestamp', { unique: false })
        }
      }
    })
  }

  /**
   * Save files to IndexedDB
   * @param {Array} files - Array of file info objects with File objects
   */
  async saveFiles(files) {
    if (!this.db) await this.init()

    // Clear existing files first
    await this.clearFiles()

    // Read all files as ArrayBuffer FIRST (before starting transaction)
    // This prevents transaction from finishing during async operations
    const fileRecords = await Promise.all(
      files.map(async (fileInfo) => {
        const arrayBuffer = await fileInfo.file.arrayBuffer()
        return {
          name: fileInfo.name,
          size: fileInfo.file.size,
          type: fileInfo.file.type,
          lastModified: fileInfo.file.lastModified,
          recordCount: fileInfo.recordCount,
          fileType: fileInfo.type,
          // Don't store parsed data - it can contain non-cloneable objects
          // We'll re-parse from arrayBuffer when loading
          arrayBuffer: arrayBuffer,
          timestamp: Date.now()
        }
      })
    )

    // Now start transaction and add all records synchronously
    const transaction = this.db.transaction([STORE_NAME], 'readwrite')
    const store = transaction.objectStore(STORE_NAME)

    for (const record of fileRecords) {
      store.add(record)
    }

    return new Promise((resolve, reject) => {
      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(transaction.error)
    })
  }

  /**
   * Load files from IndexedDB
   * @returns {Array} Array of reconstructed File objects with metadata
   */
  async loadFiles() {
    if (!this.db) await this.init()

    const transaction = this.db.transaction([STORE_NAME], 'readonly')
    const store = transaction.objectStore(STORE_NAME)
    const request = store.getAll()

    return new Promise((resolve, reject) => {
      request.onsuccess = () => {
        const records = request.result
        
        // Reconstruct File objects from stored data
        const files = records.map((record, index) => {
          // Create a new File object from the stored ArrayBuffer
          const blob = new Blob([record.arrayBuffer], { type: record.type })
          const file = new File([blob], record.name, {
            type: record.type,
            lastModified: record.lastModified
          })

          // Re-parse JSON data if it's a JSON file
          let data = null
          if (record.fileType === 'json') {
            try {
              const text = new TextDecoder().decode(record.arrayBuffer)
              data = JSON.parse(text)
            } catch (err) {
              console.error(`Failed to re-parse ${record.name}:`, err)
            }
          }

          return {
            id: index + 1,
            name: record.name,
            size: this.formatFileSize(record.size),
            recordCount: record.recordCount,
            file: file,
            data: data,
            type: record.fileType
          }
        })

        resolve(files)
      }
      request.onerror = () => reject(request.error)
    })
  }

  /**
   * Clear all stored files
   */
  async clearFiles() {
    if (!this.db) await this.init()

    const transaction = this.db.transaction([STORE_NAME], 'readwrite')
    const store = transaction.objectStore(STORE_NAME)
    const request = store.clear()

    return new Promise((resolve, reject) => {
      request.onsuccess = () => resolve()
      request.onerror = () => reject(request.error)
    })
  }

  /**
   * Check if there are stored files
   */
  async hasStoredFiles() {
    if (!this.db) await this.init()

    const transaction = this.db.transaction([STORE_NAME], 'readonly')
    const store = transaction.objectStore(STORE_NAME)
    const request = store.count()

    return new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result > 0)
      request.onerror = () => reject(request.error)
    })
  }

  formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }
}

// Export a singleton instance
export const fileStorage = new FileStorageService()
