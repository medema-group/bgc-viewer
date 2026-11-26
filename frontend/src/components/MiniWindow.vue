<template>
  <button
    v-if="compact"
    type="button"
    class="miniwindow compact"
    :class="{ viewing }"
    :title="`Show ${label}`"
    @click="emit('expand')"
  >
    <span class="compact-head">
      <span class="compact-label">{{ label }}</span>
      <span v-if="viewing" class="viewing-mark" title="The viewer shows a result of this window">viewing</span>
    </span>
    <span class="compact-summary"><slot name="summary" /></span>
    <span class="compact-count"><slot name="count" /></span>
  </button>

  <section v-else class="miniwindow normal" :aria-label="label">
    <header class="window-header">
      <input
        v-if="editableLabel"
        class="window-label editable"
        :value="label"
        aria-label="Window label"
        maxlength="60"
        @change="renameTo($event.target as HTMLInputElement)"
        @keydown.enter="($event.target as HTMLInputElement).blur()"
      >
      <h2 v-else class="window-label">{{ label }}</h2>
      <div class="window-actions">
        <slot name="actions" />
        <button type="button" class="icon-button" title="Make compact" aria-label="Make compact" @click="emit('minimize')">
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 12h10" /></svg>
        </button>
        <button
          v-if="closable"
          type="button"
          class="icon-button close"
          :title="`Close ${label}`"
          :aria-label="`Close ${label}`"
          @click="emit('close')"
        >
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8" /></svg>
        </button>
      </div>
    </header>
    <div class="window-body">
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
// The shell of a window in the main view. At normal size it shows its content
// under a header with its label; compact, it is a card with the label, a summary
// and a count, which the window fills in through the `summary` and `count` slots.
const props = withDefaults(defineProps<{
  label: string
  compact?: boolean
  /** Whether the user can rename the window in its header. */
  editableLabel?: boolean
  closable?: boolean
  /** Whether the viewer shows something picked in this window. */
  viewing?: boolean
}>(), {
  compact: false,
  editableLabel: false,
  closable: false,
  viewing: false
})

const emit = defineEmits<{
  (event: 'expand'): void
  (event: 'minimize'): void
  (event: 'close'): void
  (event: 'update:label', label: string): void
}>()

// An emptied label keeps the old one
function renameTo(input: HTMLInputElement) {
  const label = input.value.trim()
  if (label) emit('update:label', label)
  else input.value = props.label
}
</script>

<style scoped>
.miniwindow {
  border: 1px solid #dce3e8;
  border-radius: 8px;
  background: #fff;
}

/* Compact card */
.compact {
  display: flex;
  width: 100%;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
  padding: 7px 10px 8px;
  color: #30434f;
  cursor: pointer;
  font: inherit;
  text-align: left;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.compact:hover {
  border-color: #8fb6d3;
  box-shadow: 0 1px 4px rgba(25, 118, 181, 0.15);
}

.compact:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: 1px;
}

.compact.viewing {
  border-left: 3px solid #1976b5;
  padding-left: 8px;
}

.compact-head {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
}

.compact-label {
  overflow: hidden;
  color: #263442;
  font-size: 13px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.viewing-mark {
  flex-shrink: 0;
  margin-left: auto;
  color: #1976b5;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.compact-summary {
  display: -webkit-box;
  overflow: hidden;
  color: #52616d;
  font-size: 12px;
  line-height: 1.4;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  word-break: break-word;
}

.compact-count {
  color: #145f92;
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

/* Normal window */
.normal {
  display: flex;
  height: 100%;
  min-height: 0;
  min-width: 0;
  flex-direction: column;
  overflow: hidden;
}

.window-header {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 10px;
  padding: 6px 8px 6px 12px;
  border-bottom: 1px solid #dce3e8;
}

.window-label {
  min-width: 0;
  flex: 1;
  margin: 0;
  color: #263442;
  font: inherit;
  font-size: 15px;
  font-weight: 700;
}

.window-label.editable {
  max-width: 360px;
  padding: 2px 6px;
  margin-left: -7px;
  border: 1px solid transparent;
  border-radius: 4px;
  background: transparent;
}

.window-label.editable:hover {
  border-color: #dce3e8;
}

.window-label.editable:focus {
  border-color: #1976b5;
  background: #fff;
  outline: none;
}

.window-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}

.icon-button {
  display: inline-flex;
  width: 28px;
  height: 28px;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  border-radius: 4px;
  background: transparent;
  color: #52616d;
  cursor: pointer;
}

.icon-button svg {
  width: 14px;
  height: 14px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-width: 1.8;
}

.icon-button:hover {
  border-color: #dce3e8;
  background: #edf2f5;
}

.icon-button.close:hover {
  border-color: #efc8c4;
  background: #fff3f2;
  color: #a1261d;
}

.icon-button:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: 1px;
}

.window-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
</style>
