<template>
  <div class="data-source-section">
    <h3>Data Source</h3>
    <select 
      class="source-dropdown"
      :value="selectedSource"
      @change="handleSourceChange"
    >
      <option value="api">BGC Viewer API</option>
      <option value="upload">Load local file</option>
    </select>
  </div>
</template>

<script>
import { computed } from 'vue'

export default {
  name: 'DataSourceSelector',
  props: {
    modelValue: {
      type: String,
      default: 'api'
    }
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    const selectedSource = computed({
      get: () => props.modelValue,
      set: (value) => emit('update:modelValue', value)
    })

    const handleSourceChange = (event) => {
      emit('update:modelValue', event.target.value)
    }

    return {
      selectedSource,
      handleSourceChange
    }
  }
}
</script>

<style scoped>
.data-source-section {
  padding: 15px;
  border-bottom: 1px solid #e0e0e0;
  background-color: #f8f9fa;
}

.data-source-section h3 {
  margin: 0 0 12px 0;
  font-size: 16px;
  color: #2c3e50;
}

.source-dropdown {
  width: 100%;
  padding: 10px 12px;
  font-size: 14px;
  color: #2c3e50;
  background-color: white;
  border: 1px solid #ccc;
  border-radius: 4px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.source-dropdown:hover {
  border-color: #1976d2;
}

.source-dropdown:focus {
  outline: none;
  border-color: #1976d2;
  box-shadow: 0 0 0 3px rgba(25, 118, 210, 0.1);
}
</style>
