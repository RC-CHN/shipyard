<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useModal, type ModalProps } from './useModal'

const props = withDefaults(defineProps<ModalProps>(), {
  title: '',
  size: 'md',
  closeOnOverlay: true,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const { close, handleOverlayClick, handleEscape, sizeClass } = useModal(props, emit)

onMounted(() => {
  document.addEventListener('keydown', handleEscape)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleEscape)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="modelValue"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <!-- Overlay -->
        <div
          class="absolute inset-0 bg-black/50 backdrop-blur-sm"
          @click="handleOverlayClick"
        ></div>

        <!-- Modal Content -->
        <div
          class="relative bg-white rounded-2xl shadow-2xl shadow-blue-200/50 w-full overflow-hidden transform transition-all border border-blue-50"
          :class="sizeClass()"
        >
          <!-- Header -->
          <div v-if="title || $slots.header" class="flex items-center justify-between px-6 py-5 border-b border-blue-50 bg-gradient-to-r from-slate-50 to-blue-50/30">
            <slot name="header">
              <h3 class="text-lg font-bold text-[#0F4C75]">{{ title }}</h3>
            </slot>
            <button
              @click="close"
              class="p-2 text-slate-400 hover:text-[#3282B8] rounded-full hover:bg-blue-50 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-100"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Body -->
          <div class="px-6 py-6">
            <slot></slot>
          </div>

          <!-- Footer -->
          <div v-if="$slots.footer" class="px-6 py-4 border-t border-blue-50 bg-slate-50/50 flex justify-end gap-3">
            <slot name="footer"></slot>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .relative,
.modal-leave-active .relative {
  transition: transform 0.2s ease;
}

.modal-enter-from .relative,
.modal-leave-to .relative {
  transform: scale(0.95);
}
</style>
