<template>
  <div ref="root" class="value-combobox">
    <button
      type="button"
      class="combobox-trigger"
      role="combobox"
      :aria-expanded="open"
      :aria-label="`${fieldLabel} value`"
      @click="toggleOpen"
    >
      <span class="trigger-label">{{ triggerLabel }}</span>
      <span class="chevron" aria-hidden="true">▾</span>
    </button>

    <div v-if="open" class="combobox-panel">
      <input
        ref="searchInput"
        v-model="text"
        type="text"
        class="panel-search"
        placeholder="Type to search values…"
        :aria-label="`Search ${fieldLabel} values`"
        @keydown.enter.prevent="pickTyped"
        @keydown.esc.stop.prevent="open = false"
      />
      <div class="panel-list" role="listbox" :aria-multiselectable="multiple">
        <p v-if="loading" class="panel-note">Loading…</p>
        <p v-else-if="error" class="panel-note error">{{ error }}</p>
        <p v-else-if="items.length === 0" class="panel-note">No matching values</p>
        <button
          v-for="item in items"
          v-else
          :key="item.value"
          type="button"
          role="option"
          :aria-selected="modelValue.includes(item.value)"
          :class="['panel-item', { selected: modelValue.includes(item.value) }]"
          @click="pick(item.value)"
        >
          <span v-if="multiple" class="check" aria-hidden="true">{{ modelValue.includes(item.value) ? '✓' : '' }}</span>
          <span class="item-value">{{ item.value }}</span>
          <span class="item-count">{{ item.count.toLocaleString() }}</span>
        </button>
      </div>
    </div>

    <div v-if="multiple && modelValue.length" class="chips">
      <span v-for="value in modelValue" :key="value" class="chip">
        <span class="chip-label">{{ value }}</span>
        <button type="button" :aria-label="`Remove ${value}`" @click="pick(value)">&times;</button>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { FacetBucket } from '@/services/dataProviders/types'

export type LoadFieldValues = (field: string, contains: string) => Promise<FacetBucket[]>

const props = withDefaults(defineProps<{
  field: string
  fieldLabel: string
  modelValue: string[]
  multiple?: boolean
  loadValues: LoadFieldValues
}>(), {
  multiple: false
})

const emit = defineEmits<{
  (event: 'update:modelValue', values: string[]): void
}>()

const root = ref<HTMLElement | null>(null)
const searchInput = ref<HTMLInputElement | null>(null)
const open = ref(false)
const text = ref('')
const items = ref<FacetBucket[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
let timer: ReturnType<typeof setTimeout> | undefined
let request = 0

const triggerLabel = computed(() => {
  if (props.modelValue.length === 0) return 'Value'
  if (props.modelValue.length === 1 || !props.multiple) return props.modelValue[0]
  return `${props.modelValue.length} selected`
})

function fetchValues() {
  clearTimeout(timer)
  loading.value = true
  timer = setTimeout(async () => {
    const current = ++request
    try {
      const values = await props.loadValues(props.field, text.value)
      if (current === request) {
        items.value = values
        error.value = null
      }
    } catch {
      if (current === request) {
        items.value = []
        error.value = 'Could not load values'
      }
    } finally {
      if (current === request) loading.value = false
    }
  }, 200)
}

watch(text, () => { if (open.value) fetchValues() })
watch(() => props.field, () => { items.value = []; open.value = false })

async function toggleOpen() {
  open.value = !open.value
  if (open.value) {
    text.value = ''
    fetchValues()
    await nextTick()
    searchInput.value?.focus()
  }
}

function pick(value: string) {
  if (props.multiple) {
    const next = props.modelValue.includes(value)
      ? props.modelValue.filter(v => v !== value)
      : [...props.modelValue, value]
    emit('update:modelValue', next)
  } else {
    emit('update:modelValue', [value])
    open.value = false
  }
}

// Enter takes the typed text as a value, so a value the index lacks can still be asked for.
function pickTyped() {
  const typed = text.value.trim()
  if (!typed) return
  if (!props.modelValue.includes(typed) || !props.multiple) pick(typed)
  text.value = ''
}

function handleOutside(event: MouseEvent) {
  if (open.value && root.value && !root.value.contains(event.target as Node)) open.value = false
}

onMounted(() => document.addEventListener('mousedown', handleOutside))
onUnmounted(() => {
  document.removeEventListener('mousedown', handleOutside)
  clearTimeout(timer)
})
</script>

<style scoped>
.value-combobox {
  position: relative;
  display: inline-flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.combobox-trigger {
  display: flex;
  width: 220px;
  max-width: 100%;
  height: 30px;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 0 8px;
  border: 1px solid #aebbc4;
  border-radius: 4px;
  background: #fff;
  color: #263442;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  text-align: left;
}

.trigger-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chevron {
  color: #687681;
}

.combobox-panel {
  position: absolute;
  z-index: 10;
  top: 34px;
  left: 0;
  width: 300px;
  border: 1px solid #b9c5cc;
  border-radius: 6px;
  background: #fff;
  box-shadow: 0 10px 30px rgba(14, 29, 38, 0.2);
}

.panel-search {
  width: 100%;
  box-sizing: border-box;
  padding: 8px;
  border: 0;
  border-bottom: 1px solid #dce3e8;
  font: inherit;
  font-size: 12px;
}

.panel-search:focus {
  outline: none;
}

.panel-list {
  max-height: 240px;
  overflow-y: auto;
  padding: 4px;
}

.panel-note {
  margin: 0;
  padding: 8px;
  color: #687681;
  font-size: 12px;
}

.panel-note.error {
  color: #a1261d;
}

.panel-item {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 6px;
  padding: 5px 6px;
  border: 0;
  border-radius: 3px;
  background: transparent;
  color: #263442;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  text-align: left;
}

.panel-item:hover,
.panel-item.selected {
  background: #edf2f5;
}

.check {
  display: inline-flex;
  width: 12px;
  height: 12px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border: 1px solid #aebbc4;
  border-radius: 2px;
  font-size: 10px;
}

.item-value {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-count {
  color: #687681;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}

.chips {
  display: flex;
  max-width: 260px;
  flex-wrap: wrap;
  gap: 4px;
}

.chip {
  display: inline-flex;
  max-width: 100%;
  align-items: center;
  gap: 2px;
  padding: 1px 2px 1px 6px;
  border-radius: 10px;
  background: #e7eef2;
  color: #30434f;
  font-size: 11px;
}

.chip-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chip button {
  border: 0;
  background: transparent;
  color: #52616d;
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
}
</style>
