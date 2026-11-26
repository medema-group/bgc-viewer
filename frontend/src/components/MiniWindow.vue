<template>
  <div v-if="compact" class="miniwindow compact" :class="{ viewing, active }">
    <button
      type="button"
      class="compact-card"
      :title="active ? `Make ${label} compact` : `Enlarge ${label}`"
      :aria-current="active ? 'true' : undefined"
      @click="emit(active ? 'minimize' : 'expand')"
    >
      <span class="compact-head">
        <span class="compact-label">{{ label }}</span>
        <span v-if="viewing" class="viewing-mark" title="The viewer shows a result of this window">viewing</span>
      </span>
      <span class="compact-summary"><slot name="summary" /></span>
      <span class="compact-count"><slot name="count" /></span>
    </button>
    <button
      v-if="closable && !active"
      type="button"
      class="icon-button delete"
      :title="`Delete ${label}`"
      :aria-label="`Delete ${label}`"
      @click="emit('close')"
    >
      <svg viewBox="0 0 16 16" aria-hidden="true">
        <path d="M2.5 4.5h11M6 4.5V3h4v1.5M4 4.5l.7 9h6.6l.7-9M6.8 7v4M9.2 7v4" />
      </svg>
    </button>
  </div>

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
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6 3v3H3M10 3v3h3M6 13v-3H3M10 13v-3h3" /></svg>
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
// under a header with its label and a button to make it compact; compact, it is a
// card with the label, a summary and a count, which the window fills in through
// the `summary` and `count` slots. Clicking the card enlarges the window. The
// card of the window that is open at normal size stays in place, marked active;
// clicking it makes the window compact again. A closable window is deleted from
// its card while compact, so it is not lost by accident while being worked on.
const props = withDefaults(defineProps<{
  label: string
  compact?: boolean
  /** Whether the user can rename the window in its header. */
  editableLabel?: boolean
  /** Whether the compact card offers to delete the window. */
  closable?: boolean
  /** Whether the viewer shows something picked in this window. */
  viewing?: boolean
  /** Whether this is the card of the window that is open at normal size. */
  active?: boolean
}>(), {
  compact: false,
  editableLabel: false,
  closable: false,
  viewing: false,
  active: false
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

/* Compact card: the card itself enlarges the window; the delete button sits beside it */
.compact {
  display: flex;
  align-items: flex-start;
  min-width: 0;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.compact:hover {
  border-color: #8fb6d3;
  box-shadow: 0 1px 4px rgba(25, 118, 181, 0.15);
}

.compact.viewing {
  border-left: 3px solid #1976b5;
}

.compact.active {
  border-color: #1976b5;
  background: #eef5fb;
  box-shadow: inset 0 0 0 1px #1976b5;
}

.compact-card {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  padding: 7px 10px 8px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: #30434f;
  cursor: pointer;
  font: inherit;
  text-align: left;
}

.compact.viewing .compact-card {
  padding-left: 8px;
}

.compact-card:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: -2px;
}

.compact .delete {
  flex-shrink: 0;
  margin: 4px 4px 0 -4px;
  color: #8a97a0;
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

.icon-button.delete:hover {
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
