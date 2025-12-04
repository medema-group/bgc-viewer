<template>
  <table class="simple-table">
    <thead>
      <tr>
        <th 
          v-for="(header, index) in headers" 
          :key="index"
          @click="toggleSort(index)"
          :class="{ 
            sortable: true, 
            sorted: sortColumn === index,
            'sort-asc': sortColumn === index && sortDirection === 'asc',
            'sort-desc': sortColumn === index && sortDirection === 'desc'
          }"
        >
          {{ header }}
          <span class="sort-indicator" v-if="sortColumn === index">
            {{ sortDirection === 'asc' ? '▲' : '▼' }}
          </span>
        </th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="(row, rowIndex) in sortedDataRows" :key="rowIndex">
        <td v-for="(cell, cellIndex) in row" :key="cellIndex">
          {{ cell }}
        </td>
      </tr>
    </tbody>
  </table>
</template>

<script>
import { ref, computed } from 'vue'

export default {
  name: 'SimpleTable',
  props: {
    rows: {
      type: Array,
      required: true,
      validator: (value) => {
        return value.every(row => Array.isArray(row))
      }
    }
  },
  setup(props) {
    const sortColumn = ref(null)
    const sortDirection = ref('asc')
    
    // First row is headers
    const headers = computed(() => props.rows[0] || [])
    
    // Remaining rows are data
    const dataRows = computed(() => props.rows.slice(1))
    
    const toggleSort = (columnIndex) => {
      if (sortColumn.value === columnIndex) {
        // Cycle through: asc -> desc -> no sort
        if (sortDirection.value === 'asc') {
          sortDirection.value = 'desc'
        } else {
          // Reset to no sorting
          sortColumn.value = null
          sortDirection.value = 'asc'
        }
      } else {
        // Set new column and default to ascending
        sortColumn.value = columnIndex
        sortDirection.value = 'asc'
      }
    }
    
    const sortedDataRows = computed(() => {
      if (sortColumn.value === null) {
        return dataRows.value
      }
      
      return [...dataRows.value].sort((a, b) => {
        const aVal = a[sortColumn.value]
        const bVal = b[sortColumn.value]
        
        // Handle empty values
        if (aVal === '' || aVal === null || aVal === undefined) return 1
        if (bVal === '' || bVal === null || bVal === undefined) return -1
        
        // Try to parse as numbers for numeric comparison
        const aNum = parseFloat(String(aVal).replace(/[%,]/g, ''))
        const bNum = parseFloat(String(bVal).replace(/[%,]/g, ''))
        
        let comparison = 0
        if (!isNaN(aNum) && !isNaN(bNum)) {
          // Numeric comparison
          comparison = aNum - bNum
        } else {
          // String comparison
          comparison = String(aVal).localeCompare(String(bVal))
        }
        
        return sortDirection.value === 'asc' ? comparison : -comparison
      })
    })
    
    return {
      headers,
      sortColumn,
      sortDirection,
      sortedDataRows,
      toggleSort
    }
  }
}
</script>

<style scoped>
.simple-table {
  border-collapse: collapse;
  font-size: 12px;
  width: 100%;
}

.simple-table th {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  padding: 6px 8px;
  text-align: left;
  font-weight: 600;
  color: #495057;
  white-space: nowrap;
  cursor: pointer;
  user-select: none;
}

.simple-table th:hover {
  background: #e9ecef;
}

.simple-table th.sorted {
  background: #e2e6ea;
}

.sort-indicator {
  margin-left: 4px;
  font-size: 10px;
  color: #495057;
}

.simple-table td {
  padding: 3px 8px;
  border: 1px solid #dee2e6;
  vertical-align: top;
}

.simple-table tr:nth-child(even) {
  background-color: #f8f9fa;
}
</style>
