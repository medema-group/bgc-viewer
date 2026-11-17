<template>
  <div v-show="open" class="dialog-overlay" @mousedown.self="emit('close')">
    <section
      class="dialog"
      :style="{ width }"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="titleId"
    >
      <header class="dialog-header">
        <h2 :id="titleId">{{ title }}</h2>
        <button
          type="button"
          class="close-button"
          :aria-label="`Close ${title}`"
          :title="`Close ${title}`"
          @click="emit('close')"
        >
          &times;
        </button>
      </header>
      <div class="dialog-body">
        <slot />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
// A modal shell that stays mounted while hidden, so what it holds keeps its
// state and can act on startup, as the file and accession loaders do.
import { onMounted, onUnmounted, useId } from 'vue'

const props = withDefaults(defineProps<{
  open: boolean
  title: string
  width?: string
}>(), {
  width: 'min(760px, 100%)'
})

const emit = defineEmits<{
  (event: 'close'): void
}>()

const titleId = `dialog-title-${useId()}`

function handleKeydown(event: KeyboardEvent) {
  if (props.open && event.key === 'Escape') emit('close')
}

onMounted(() => document.addEventListener('keydown', handleKeydown))
onUnmounted(() => document.removeEventListener('keydown', handleKeydown))
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: min(8vh, 64px) 20px 20px;
  background: rgba(22, 31, 38, 0.62);
}

.dialog {
  display: flex;
  max-width: 100%;
  max-height: min(86vh, 960px);
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #b9c5cc;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 24px 70px rgba(14, 29, 38, 0.34);
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px 10px;
  border-bottom: 1px solid #dce3e8;
}

.dialog-header h2 {
  margin: 0;
  color: #263442;
  font-size: 16px;
  letter-spacing: 0;
}

.close-button {
  width: 32px;
  height: 32px;
  border: 0;
  background: transparent;
  color: #5d6c77;
  cursor: pointer;
  font-size: 25px;
  line-height: 1;
}

.close-button:hover {
  background: #edf2f5;
}

.close-button:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: 1px;
}

.dialog-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

@media (max-width: 800px) {
  .dialog-overlay {
    padding: 8px;
  }

  .dialog {
    max-height: calc(100vh - 16px);
  }
}
</style>
