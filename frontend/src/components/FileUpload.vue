<template>
  <div class="file-upload-section">
    <h3>Upload JSON File</h3>
    <p class="help-text">Select or drag and drop an antiSMASH JSON file</p>
    
    <input
      ref="fileInputRef"
      type="file"
      accept=".json,application/json"
      multiple
      style="display: none"
      @change="handleFileSelect"
    />
    
    <div 
      class="drop-zone"
      :class="{ 'drag-over': isDragOver, 'file-loaded': loadedFiles.length > 0 }"
      @drop="handleDrop"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
    >
      <div v-if="loadedFiles.length === 0" class="drop-zone-content">
        <svg class="upload-icon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
        <p class="drop-text">Drag and drop JSON files here</p>
        <p class="or-text">or</p>
        <button class="select-file-btn" @click="triggerFileInput">
          Select Files
        </button>
      </div>
      
      <div v-else class="files-list">
        <div v-for="fileInfo in loadedFiles" :key="fileInfo.id" class="file-info">
          <svg class="file-icon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <div class="file-details">
            <p class="file-name">{{ fileInfo.name }}</p>
            <p class="file-size">{{ fileInfo.size }} • {{ fileInfo.recordCount }} records</p>
          </div>
          <button class="remove-btn" @click="removeFile(fileInfo.id)" title="Remove file">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <button class="add-more-btn" @click="triggerFileInput">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          Add More Files
        </button>
      </div>
    </div>
    
    <div v-if="error" class="error-message">
      {{ error }}
    </div>
    
    <div v-if="isLoading" class="loading-message">
      <div class="spinner"></div>
      <span>Loading file...</span>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'

export default {
  name: 'FileUpload',
  emits: ['files-loaded'],
  setup(props, { emit }) {
    const fileInputRef = ref(null)
    const isDragOver = ref(false)
    const loadedFiles = ref([])
    const error = ref('')
    const isLoading = ref(false)
    let fileIdCounter = 0
    
    const formatFileSize = (bytes) => {
      if (bytes < 1024) return bytes + ' B'
      if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
      return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
    }
    
    const triggerFileInput = () => {
      fileInputRef.value?.click()
    }
    
    const handleFileSelect = (event) => {
      const files = Array.from(event.target.files || [])
      if (files.length > 0) {
        processFiles(files)
      }
      // Reset input to allow selecting the same file again
      event.target.value = ''
    }
    
    const handleDrop = (event) => {
      event.preventDefault()
      isDragOver.value = false
      
      const files = Array.from(event.dataTransfer?.files || [])
      if (files.length > 0) {
        processFiles(files)
      }
    }
    
    const handleDragOver = (event) => {
      event.preventDefault()
      isDragOver.value = true
    }
    
    const handleDragLeave = (event) => {
      event.preventDefault()
      isDragOver.value = false
    }
    
    const processFiles = async (files) => {
      error.value = ''
      isLoading.value = true
      
      const newFiles = []
      
      for (const file of files) {
        // Validate file type
        if (!file.name.endsWith('.json')) {
          console.warn(`Skipping non-JSON file: ${file.name}`)
          continue
        }
        
        try {
          // Read and parse the file
          const text = await file.text()
          const data = JSON.parse(text)
          
          // Count records in the file
          let recordCount = 0
          if (data.records && Array.isArray(data.records)) {
            recordCount = data.records.length
          } else if (data.id) {
            recordCount = 1
          }
          
          // Add to loaded files
          const fileInfo = {
            id: ++fileIdCounter,
            name: file.name,
            size: formatFileSize(file.size),
            recordCount: recordCount,
            file: file,
            data: data
          }
          
          newFiles.push(fileInfo)
          loadedFiles.value.push(fileInfo)
        } catch (err) {
          console.error(`Failed to parse ${file.name}:`, err)
          error.value = `Failed to parse ${file.name}: ${err.message}`
        }
      }
      
      isLoading.value = false
      
      // Emit all loaded files
      if (newFiles.length > 0) {
        emit('files-loaded', loadedFiles.value)
      }
    }
    
    const removeFile = (fileId) => {
      loadedFiles.value = loadedFiles.value.filter(f => f.id !== fileId)
      error.value = ''
      
      // Emit updated file list
      emit('files-loaded', loadedFiles.value)
    }
    
    return {
      fileInputRef,
      isDragOver,
      loadedFiles,
      error,
      isLoading,
      triggerFileInput,
      handleFileSelect,
      handleDrop,
      handleDragOver,
      handleDragLeave,
      removeFile
    }
  }
}
</script>

<style scoped>
.file-upload-section {
  padding: 15px;
  border-bottom: 1px solid #e0e0e0;
}

.file-upload-section h3 {
  margin: 0 0 8px 0;
  font-size: 16px;
  color: #2c3e50;
}

.help-text {
  margin: 0 0 15px 0;
  font-size: 13px;
  color: #666;
}

.drop-zone {
  border: 2px dashed #ccc;
  border-radius: 8px;
  padding: 30px 20px;
  text-align: center;
  background-color: #fafafa;
  transition: all 0.3s ease;
  cursor: pointer;
}

.drop-zone.drag-over {
  border-color: #1976d2;
  background-color: #e3f2fd;
}

.drop-zone.file-loaded {
  border: none;
  background-color: transparent;
  cursor: default;
  padding: 0;
}

.files-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}

.drop-zone-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.upload-icon {
  width: 48px;
  height: 48px;
  color: #1976d2;
}

.drop-text {
  margin: 0;
  font-size: 14px;
  color: #555;
}

.or-text {
  margin: 0;
  font-size: 12px;
  color: #999;
}

.select-file-btn {
  padding: 8px 20px;
  background-color: #1976d2;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.select-file-btn:hover {
  background-color: #1565c0;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  background-color: white;
  border-radius: 4px;
  border: 1px solid #e0e0e0;
}

.file-icon {
  width: 32px;
  height: 32px;
  color: #4caf50;
  flex-shrink: 0;
}

.file-details {
  flex: 1;
  text-align: left;
}

.file-name {
  margin: 0 0 2px 0;
  font-size: 13px;
  font-weight: 500;
  color: #2c3e50;
  word-break: break-all;
}

.file-size {
  margin: 0;
  font-size: 11px;
  color: #666;
}

.remove-btn {
  width: 24px;
  height: 24px;
  padding: 4px;
  background-color: transparent;
  color: #999;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}

.remove-btn:hover {
  background-color: #ffebee;
  color: #f44336;
}

.remove-btn svg {
  width: 100%;
  height: 100%;
}

.add-more-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
  background-color: white;
  color: #1976d2;
  border: 2px dashed #1976d2;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.add-more-btn:hover {
  background-color: #e3f2fd;
  border-color: #1565c0;
  color: #1565c0;
}

.add-more-btn svg {
  width: 16px;
  height: 16px;
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
