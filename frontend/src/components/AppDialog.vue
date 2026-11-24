<template>
  <div v-show="open" class="dialog-overlay" @mousedown.self="emit('close')">
    <section
      ref="dialog"
      class="dialog"
      :style="{ width }"
      tabindex="-1"
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
// While open it holds keyboard focus, and gives it back to the opener on close.
import { onMounted, onUnmounted, ref, useId, watch } from 'vue'

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
const dialog = ref<HTMLElement | null>(null)
let opener: HTMLElement | null = null

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[contenteditable="true"]',
  '[tabindex]:not([tabindex="-1"])'
].join(',')

/** The controls Tab moves between, in order; hidden ones (such as other tabs' panels) are left out. */
function focusable(): HTMLElement[] {
  const elements = Array.from(dialog.value?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])
  return elements.filter(element => element.checkVisibility?.() ?? !element.closest('[hidden]'))
}

/** Focus what the content marks with autofocus, or else the dialog itself, so Tab starts at its first control. */
function focusDialog() {
  const preferred = dialog.value?.querySelector<HTMLElement>('[autofocus]')
  ;(preferred ?? dialog.value)?.focus()
}

/** Keep Tab and Shift+Tab cycling through the dialog's controls. */
function trapTab(event: KeyboardEvent) {
  const elements = focusable()
  const active = document.activeElement as HTMLElement | null
  if (elements.length === 0) {
    event.preventDefault()
    dialog.value?.focus()
    return
  }
  const first = elements[0]
  const last = elements[elements.length - 1]
  const inside = active !== null && dialog.value?.contains(active)
  if (!inside || active === dialog.value) {
    event.preventDefault()
    ;(event.shiftKey ? last : first).focus()
  } else if (event.shiftKey && active === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && active === last) {
    event.preventDefault()
    first.focus()
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (!props.open) return
  if (event.key === 'Escape') emit('close')
  else if (event.key === 'Tab') trapTab(event)
}

function restoreFocus() {
  const target = opener
  opener = null
  if (target?.isConnected) target.focus()
}

// Run after the render, once v-show has revealed the dialog and focus can land in it
watch(() => props.open, open => {
  if (open) {
    const active = document.activeElement
    opener = active instanceof HTMLElement && active !== document.body ? active : null
    focusDialog()
  } else {
    restoreFocus()
  }
}, { flush: 'post' })

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
  // Opened from the start, there is no opener to return to
  if (props.open) focusDialog()
})
onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
  if (props.open) restoreFocus()
})
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
  outline: none;
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
