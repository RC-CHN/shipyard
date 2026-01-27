<script setup lang="ts">
import { useStatusBadge } from './useStatusBadge'

const props = withDefaults(defineProps<{
  status: number
  size?: 'sm' | 'md' | 'lg'
}>(), {
  size: 'md',
})

const { statusConfig, sizeClass } = useStatusBadge(props)
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 rounded-full font-medium shadow-sm border"
    :class="[statusConfig.bgClass, statusConfig.textClass, sizeClass, 'border-opacity-20']"
    :style="{ borderColor: 'currentColor' }"
  >
    <span class="relative flex h-2 w-2">
      <span class="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" :class="statusConfig.dotClass"></span>
      <span class="relative inline-flex rounded-full h-2 w-2" :class="statusConfig.dotClass"></span>
    </span>
    {{ statusConfig.text }}
  </span>
</template>
