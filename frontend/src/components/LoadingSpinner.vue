<template>
  <div 
    class="loading-spinner"
    :style="customStyle"
  >
  </div>
</template>

<script>
import { computed } from 'vue'

export default {
  name: 'LoadingSpinner',
  props: {
    color: {
      type: String,
      default: '#1976d2'
    }
  },
  setup(props) {
    const customStyle = computed(() => ({
      borderColor: props.color,
      borderTopColor: 'transparent'
    }))

    return {
      customStyle
    }
  }
}
</script>

<style scoped>

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 3px solid;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  display: inline-block;
  vertical-align: middle;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
