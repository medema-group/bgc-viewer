<template>
  <div class="condition-row">
    <select
      class="group-select"
      :value="field.group"
      aria-label="Field group"
      @change="changeGroup(($event.target as HTMLSelectElement).value)"
    >
      <option v-for="group in groups" :key="group" :value="group">{{ group }}</option>
    </select>

    <select
      class="field-select"
      :value="field.name"
      aria-label="Field"
      :title="field.description"
      @change="changeField(($event.target as HTMLSelectElement).value)"
    >
      <option v-for="option in fieldsInGroup" :key="option.name" :value="option.name">
        {{ option.label }}
      </option>
    </select>

    <select
      class="operator-select"
      :value="condition.operator"
      aria-label="Operator"
      @change="changeOperator(($event.target as HTMLSelectElement).value as FilterOperator)"
    >
      <option v-for="operator in operators" :key="operator" :value="operator">
        {{ OPERATOR_LABELS[operator] ?? operator }}
      </option>
    </select>

    <template v-if="input === 'none'" />

    <ValueCombobox
      v-else-if="input === 'values'"
      :field="field.name"
      :field-label="field.label"
      :model-value="valueList"
      :multiple="condition.operator === 'in' || condition.operator === 'not_in'"
      :load-values="loadValues"
      @update:model-value="changeValues"
    />

    <span v-else-if="input === 'range'" class="range-inputs">
      <input
        type="number"
        class="number-input"
        placeholder="Min"
        aria-label="Minimum"
        :value="rangeValue[0]"
        @input="changeRange(0, ($event.target as HTMLInputElement).value)"
      />
      <span class="range-and">and</span>
      <input
        type="number"
        class="number-input"
        placeholder="Max"
        aria-label="Maximum"
        :value="rangeValue[1]"
        @input="changeRange(1, ($event.target as HTMLInputElement).value)"
      />
    </span>

    <input
      v-else-if="input === 'number'"
      type="number"
      class="number-input"
      placeholder="Value"
      aria-label="Value"
      :value="scalarValue"
      @input="emitValue(($event.target as HTMLInputElement).value)"
    />

    <select
      v-else-if="input === 'boolean'"
      class="boolean-select"
      aria-label="Value"
      :value="scalarValue || 'true'"
      @change="emitValue(($event.target as HTMLSelectElement).value)"
    >
      <option value="true">yes</option>
      <option value="false">no</option>
    </select>

    <input
      v-else
      type="text"
      :class="['text-input', { 'query-input': field.name === RAW_QUERY_FIELD }]"
      :placeholder="field.name === RAW_QUERY_FIELD ? 'pfam:PF00550 AND substrates:Leu' : 'Text'"
      aria-label="Value"
      :value="scalarValue"
      @input="emitValue(($event.target as HTMLInputElement).value)"
    />

    <button
      type="button"
      class="remove-button"
      aria-label="Remove condition"
      title="Remove condition"
      @click="emit('remove')"
    >
      &times;
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import ValueCombobox, { type LoadFieldValues } from './ValueCombobox.vue'
import {
  OPERATOR_LABELS,
  RAW_QUERY_FIELD,
  defaultCondition,
  normalizeValue
} from '@/services/filterRows'
import type {
  FilterCondition,
  FilterOperator,
  FilterValue,
  SearchFieldInfo
} from '@/services/dataProviders/types'

const props = defineProps<{
  condition: FilterCondition
  fields: SearchFieldInfo[]
  loadValues: LoadFieldValues
}>()

const emit = defineEmits<{
  (event: 'update', condition: FilterCondition): void
  (event: 'remove'): void
}>()

const field = computed(
  () => props.fields.find(f => f.name === props.condition.field) ?? props.fields[0]
)

const groups = computed(() => [...new Set(props.fields.map(f => f.group))])
const fieldsInGroup = computed(() => props.fields.filter(f => f.group === field.value.group))

// The stored operator stays listed even when the field does not offer it, so a
// condition from a shared filter shows what it asks instead of a substitute.
const operators = computed<FilterOperator[]>(() => {
  const offered = field.value.operators
  return offered.includes(props.condition.operator)
    ? offered
    : [...offered, props.condition.operator]
})

type InputKind = 'none' | 'values' | 'range' | 'number' | 'boolean' | 'text'

const input = computed<InputKind>(() => {
  const operator = props.condition.operator
  if (operator === 'exists' || operator === 'not_exists') return 'none'
  const kind = field.value.kind
  if (kind === 'numeric') return operator === 'between' ? 'range' : 'number'
  if (kind === 'boolean') return 'boolean'
  if (kind === 'exact' && field.value.facet && ['in', 'not_in', 'equals', 'not_equals'].includes(operator)) {
    return 'values'
  }
  return 'text'
})

const valueList = computed(() => {
  const value = props.condition.value
  const values = Array.isArray(value) ? value : [value]
  return values.filter(v => v !== null && v !== undefined && `${v}` !== '').map(String)
})

const scalarValue = computed(() => {
  const value = props.condition.value
  const first = Array.isArray(value) ? value[0] : value
  return first === null || first === undefined ? '' : String(first)
})

const rangeValue = computed(() => {
  const value = props.condition.value
  return Array.isArray(value) ? [value[0] ?? '', value[1] ?? ''] : [value ?? '', '']
})

function update(partial: Partial<FilterCondition>) {
  emit('update', { ...props.condition, ...partial })
}

function emitValue(value: FilterValue) {
  update({ value })
}

function changeGroup(group: string) {
  const first = props.fields.find(f => f.group === group)
  if (first) changeField(first.name)
}

function changeField(name: string) {
  const next = props.fields.find(f => f.name === name)
  if (!next) return
  const fresh = defaultCondition(next)
  update({ field: fresh.field, operator: fresh.operator, value: fresh.value })
}

function changeOperator(operator: FilterOperator) {
  update({ operator, value: normalizeValue(props.condition.value, operator) })
}

function changeValues(values: string[]) {
  const multiple = props.condition.operator === 'in' || props.condition.operator === 'not_in'
  emitValue(multiple ? values : values[0] ?? '')
}

function changeRange(index: 0 | 1, value: string) {
  const next = [...rangeValue.value] as (string | number | null)[]
  next[index] = value
  emitValue(next)
}
</script>

<style scoped>
.condition-row {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 6px;
}

select,
input {
  height: 30px;
  box-sizing: border-box;
  border: 1px solid #aebbc4;
  border-radius: 4px;
  background: #fff;
  color: #263442;
  font: inherit;
  font-size: 12px;
}

select {
  padding: 0 4px;
}

input {
  padding: 0 8px;
}

select:focus,
input:focus,
button:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: 1px;
}

.group-select {
  width: 120px;
}

.field-select {
  width: 190px;
}

.operator-select {
  width: 130px;
}

.number-input {
  width: 110px;
}

.text-input {
  width: 220px;
}

.query-input {
  width: 320px;
  font-family: 'IBM Plex Mono', 'Liberation Mono', monospace;
}

.range-inputs {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.range-and {
  color: #687681;
  font-size: 12px;
}

.remove-button {
  width: 30px;
  height: 30px;
  margin-left: auto;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: #687681;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
}

.remove-button:hover {
  background: #fff3f2;
  color: #a1261d;
}
</style>
