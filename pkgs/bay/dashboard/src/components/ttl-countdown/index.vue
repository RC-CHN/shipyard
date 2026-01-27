<script setup lang="ts">
import { useTTLCountdown } from './useTTLCountdown'

const props = withDefaults(defineProps<{
  expiresAt: string | null
  showLabel?: boolean
}>(), {
  showLabel: true,
})

// 使用 getter 函数确保响应式
const { formattedTime, isExpired, colorClass } = useTTLCountdown({
  expiresAt: () => props.expiresAt,
  showLabel: props.showLabel,
})
</script>

<template>
  <div class="inline-flex items-center gap-2">
    <span v-if="showLabel" class="text-gray-500 text-sm">TTL:</span>
    <span class="font-mono font-semibold" :class="colorClass">
      {{ formattedTime }}
    </span>
    <span v-if="isExpired" class="text-xs text-gray-400">(expired)</span>
  </div>
</template>
