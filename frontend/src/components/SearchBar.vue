<template>
  <button
    type="button"
    class="search-trigger"
    aria-label="Open search"
    @click="emit('open')"
  >
    <span class="search-icon" aria-hidden="true"></span>
    <span class="search-label">Search</span>
    <kbd>Ctrl K</kbd>
  </button>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

const emit = defineEmits<{
  (event: 'open'): void
}>()

function handleShortcut(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    emit('open')
  }
}

onMounted(() => document.addEventListener('keydown', handleShortcut))
onUnmounted(() => document.removeEventListener('keydown', handleShortcut))
</script>

<style scoped>
.search-trigger {
  display: flex;
  width: 240px;
  height: 36px;
  align-items: center;
  gap: 9px;
  padding: 0 7px 0 12px;
  border: 1px solid #aebbc4;
  border-radius: 4px;
  background: #fff;
  color: #43535f;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  text-align: left;
}

.search-trigger:hover {
  border-color: #1976d2;
  box-shadow: 0 1px 4px rgba(25, 118, 210, 0.14);
}

.search-trigger:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: 1px;
}

.search-icon {
  width: 13px;
  height: 13px;
  flex: 0 0 auto;
  border: 2px solid currentColor;
  border-radius: 50%;
  position: relative;
}

.search-icon::after {
  position: absolute;
  right: -5px;
  bottom: -3px;
  width: 6px;
  height: 2px;
  background: currentColor;
  content: '';
  transform: rotate(45deg);
}

.search-label {
  flex: 1;
}

kbd {
  padding: 2px 6px;
  border: 1px solid #cbd4da;
  border-radius: 3px;
  background: #f3f5f6;
  color: #687681;
  font: 11px 'IBM Plex Mono', 'Liberation Mono', monospace;
  white-space: nowrap;
}

@media (max-width: 600px) {
  .search-trigger {
    width: 128px;
  }

  kbd {
    display: none;
  }
}
</style>