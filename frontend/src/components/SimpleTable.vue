<template>
  <table class="simple-table">
    <tbody>
      <tr v-for="(row, rowIndex) in rows" :key="rowIndex">
        <td v-for="(cell, cellIndex) in row" :key="cellIndex">
          {{ cell }}
        </td>
      </tr>
    </tbody>
  </table>
</template>

<script>
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
  }
}
</script>

<style scoped>
.simple-table {
  border-collapse: collapse;
  font-size: 12px;
  width: 100%;
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
