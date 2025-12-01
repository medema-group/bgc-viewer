<template>
  <table class="sortable-table">
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
          {{ header.label }}
          <span class="sort-indicator" v-if="sortColumn === index">
            {{ sortDirection === 'asc' ? '▲' : '▼' }}
          </span>
        </th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="(row, rowIndex) in sortedRows" :key="rowIndex">
        <td 
          v-for="(cell, cellIndex) in row" 
          :key="cellIndex"
          :class="headers[cellIndex]?.cellClass"
        >
          <component v-if="typeof cell === 'object' && cell !== null" :is="cell" />
          <template v-else>{{ cell }}</template>
        </td>
      </tr>
    </tbody>
  </table>
</template>

<script>
import { ref, computed } from 'vue'

export default {
  name: 'SortableTable',
  props: {
    // Array of header objects: [{ label: 'Column Name', key: 'propertyKey', cellClass: 'custom-class' }]
    headers: {
      type: Array,
      required: true
    },
    // Array of row data (arrays matching header order)
    rows: {
      type: Array,
      required: true
    },
    // Initial sort column index
    initialSortColumn: {
      type: Number,
      default: null
    },
    // Initial sort direction
    initialSortDirection: {
      type: String,
      default: 'asc',
      validator: (value) => ['asc', 'desc'].includes(value)
    }
  },
  setup(props) {
    const sortColumn = ref(props.initialSortColumn)
    const sortDirection = ref(props.initialSortDirection)
    
    const toggleSort = (columnIndex) => {
      if (sortColumn.value === columnIndex) {
        // Toggle direction if clicking same column
        sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
      } else {
        // Set new column and default to ascending
        sortColumn.value = columnIndex
        sortDirection.value = 'asc'
      }
    }
    
    const sortedRows = computed(() => {
      if (sortColumn.value === null) {
        return props.rows
      }
      
      return [...props.rows].sort((a, b) => {
        const aVal = a[sortColumn.value]
        const bVal = b[sortColumn.value]
        
        // Extract text content if it's a VNode/component
        const aText = typeof aVal === 'object' && aVal !== null 
          ? (aVal.children || aVal.props?.children || '') 
          : aVal
        const bText = typeof bVal === 'object' && bVal !== null 
          ? (bVal.children || bVal.props?.children || '') 
          : bVal
        
        // Handle empty values
        if (aText === '' || aText === null || aText === undefined) return 1
        if (bText === '' || bText === null || bText === undefined) return -1
        
        // Try to parse as numbers for numeric comparison
        const aNum = parseFloat(String(aText).replace(/[%,]/g, ''))
        const bNum = parseFloat(String(bText).replace(/[%,]/g, ''))
        
        let comparison = 0
        if (!isNaN(aNum) && !isNaN(bNum)) {
          // Numeric comparison
          comparison = aNum - bNum
        } else {
          // String comparison
          comparison = String(aText).localeCompare(String(bText))
        }
        
        return sortDirection.value === 'asc' ? comparison : -comparison
      })
    })
    
    return {
      sortColumn,
      sortDirection,
      sortedRows,
      toggleSort
    }
  }
}
</script>

<style scoped>
.sortable-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  margin-top: 6px;
}

.sortable-table th {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  padding: 6px 8px;
  text-align: left;
  font-weight: 600;
  color: #495057;
  white-space: nowrap;
  cursor: pointer;
  user-select: none;
  position: relative;
}

.sortable-table th:hover {
  background: #e9ecef;
}

.sortable-table th.sorted {
  background: #e2e6ea;
}

.sort-indicator {
  margin-left: 4px;
  font-size: 10px;
  color: #495057;
}

.sortable-table td {
  border: 1px solid #dee2e6;
  padding: 6px 8px;
  vertical-align: top;
}

.sortable-table tbody tr:nth-child(even) {
  background-color: #f8f9fa;
}
</style>
