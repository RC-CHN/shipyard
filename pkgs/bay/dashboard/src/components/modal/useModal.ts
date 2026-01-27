import { ref, watch } from 'vue'

export interface ModalProps {
  modelValue: boolean
  title?: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
  closeOnOverlay?: boolean
}

export function useModal(props: ModalProps, emit: (event: 'update:modelValue', value: boolean) => void) {
  const isVisible = ref(props.modelValue)

  watch(() => props.modelValue, (val) => {
    isVisible.value = val
  })

  const close = () => {
    emit('update:modelValue', false)
  }

  const handleOverlayClick = () => {
    if (props.closeOnOverlay !== false) {
      close()
    }
  }

  const handleEscape = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      close()
    }
  }

  const sizeClass = (): string => {
    switch (props.size) {
      case 'sm':
        return 'max-w-sm'
      case 'lg':
        return 'max-w-2xl'
      case 'xl':
        return 'max-w-4xl'
      default:
        return 'max-w-md'
    }
  }

  return {
    isVisible,
    close,
    handleOverlayClick,
    handleEscape,
    sizeClass,
  }
}
