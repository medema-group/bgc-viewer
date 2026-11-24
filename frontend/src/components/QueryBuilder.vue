<template>
  <div :class="['query-builder', { nested }]">
    <div v-for="(row, index) in rows" :key="row.id" class="builder-line">
      <span v-if="index === 0" class="join-spacer">{{ nested ? '' : 'Where' }}</span>
      <select
        v-else
        class="join-select"
        :value="row.join"
        aria-label="Join with the row above"
        @change="replace(index, { ...row, join: ($event.target as HTMLSelectElement).value as Join })"
      >
        <option value="AND">AND</option>
        <option value="OR">OR</option>
      </select>

      <ConditionRow
        v-if="row.kind === 'condition'"
        :condition="row.condition"
        :fields="fields"
        :load-values="loadValues"
        @update="replace(index, { ...row, condition: $event })"
        @remove="replace(index, null)"
      />
      <div v-else class="group-box">
        <QueryBuilder
          :rows="row.rows"
          :fields="fields"
          :load-values="loadValues"
          nested
          @update:rows="replace(index, $event.length ? { ...row, rows: $event } : null)"
          @remove-group="replace(index, null)"
        />
      </div>
    </div>

    <div class="builder-actions">
      <button type="button" class="action-button" @click="addCondition">+ Add condition</button>
      <button v-if="nested" type="button" class="action-button subtle" @click="emit('remove-group')">
        Remove group
      </button>
      <button v-else type="button" class="action-button" @click="addGroup">+ Add group</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import ConditionRow from './ConditionRow.vue'
import type { LoadFieldValues } from './ValueCombobox.vue'
import {
  conditionRow,
  defaultCondition,
  groupRow,
  type FilterRow,
  type Join
} from '@/services/filterRows'
import type { SearchFieldInfo } from '@/services/dataProviders/types'

const props = withDefaults(defineProps<{
  rows: FilterRow[]
  fields: SearchFieldInfo[]
  loadValues: LoadFieldValues
  /** Inside a group: no "+ Add group", as groups nest one level. */
  nested?: boolean
}>(), {
  nested: false
})

const emit = defineEmits<{
  (event: 'update:rows', rows: FilterRow[]): void
  (event: 'remove-group'): void
}>()

function replace(index: number, next: FilterRow | null) {
  const copy = [...props.rows]
  if (next) copy[index] = next
  else copy.splice(index, 1)
  emit('update:rows', copy)
}

// A new row joins the way the last one did.
function lastJoin(): Join {
  return props.rows.length > 1 ? props.rows[props.rows.length - 1].join : 'AND'
}

function addCondition() {
  emit('update:rows', [...props.rows, conditionRow(defaultCondition(props.fields[0]), lastJoin())])
}

function addGroup() {
  emit('update:rows', [...props.rows, groupRow([conditionRow(defaultCondition(props.fields[0]))], 'AND')])
}
</script>

<style scoped>
.query-builder {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.builder-line {
  display: grid;
  grid-template-columns: 62px minmax(0, 1fr);
  align-items: start;
  gap: 8px;
}

.nested .builder-line {
  grid-template-columns: 62px minmax(0, 1fr);
}

.join-spacer {
  padding-top: 7px;
  color: #687681;
  font-size: 12px;
  font-weight: 700;
}

.join-select {
  height: 30px;
  border: 1px solid #aebbc4;
  border-radius: 4px;
  background: #fff;
  color: #52616d;
  font: inherit;
  font-size: 11px;
  font-weight: 700;
}

.group-box {
  padding: 10px;
  border: 1px solid #dce3e8;
  border-radius: 6px;
  background: #f6f8f9;
}

.builder-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-left: 70px;
}

.action-button {
  height: 28px;
  padding: 0 10px;
  border: 1px solid #aebbc4;
  border-radius: 4px;
  background: #fff;
  color: #30434f;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
}

.action-button:hover {
  background: #edf2f5;
}

.action-button.subtle {
  border-color: transparent;
  background: transparent;
  color: #687681;
}

.join-select:focus,
.action-button:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: 1px;
}
</style>
