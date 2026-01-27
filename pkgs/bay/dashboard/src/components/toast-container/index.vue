<script setup lang="ts">
import { useToast } from '@/composables/useToast'

const { toasts, remove } = useToast()

const getTypeStyles = (type: string) => {
  switch (type) {
    case 'success':
      return 'bg-emerald-50 border-emerald-200 text-emerald-800 shadow-emerald-100'
    case 'error':
      return 'bg-red-50 border-red-200 text-red-800 shadow-red-100'
    case 'warning':
      return 'bg-amber-50 border-amber-200 text-amber-800 shadow-amber-100'
    default:
      return 'bg-blue-50 border-blue-200 text-blue-800 shadow-blue-100'
  }
}

const getIcon = (type: string) => {
  switch (type) {
    case 'success':
      return '✓'
    case 'error':
      return '✕'
    case 'warning':
      return '⚠'
    default:
      return 'ℹ'
  }
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed top-4 right-4 z-[100] flex flex-col gap-2 max-w-sm">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="flex items-start gap-3 px-4 py-3 rounded-lg border shadow-lg"
          :class="getTypeStyles(toast.type)"
        >
          <span class="text-lg">{{ getIcon(toast.type) }}</span>
          <p class="flex-1 text-sm">{{ toast.message }}</p>
          <button
            @click="remove(toast.id)"
            class="text-current opacity-60 hover:opacity-100 transition-opacity"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}

.toast-move {
  transition: transform 0.3s ease;
}
</style>
