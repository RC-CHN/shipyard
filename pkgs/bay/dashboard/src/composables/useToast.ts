import { ref, readonly } from 'vue'

export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface Toast {
  id: number
  type: ToastType
  message: string
  duration: number
}

// 全局共享的 toasts 状态（单例模式）
const toasts = ref<Toast[]>([])
let toastId = 0

const add = (type: ToastType, message: string, duration = 3000) => {
  const id = ++toastId
  toasts.value.push({ id, type, message, duration })
  
  if (duration > 0) {
    setTimeout(() => {
      remove(id)
    }, duration)
  }
  
  return id
}

const remove = (id: number) => {
  const index = toasts.value.findIndex(t => t.id === id)
  if (index > -1) {
    toasts.value.splice(index, 1)
  }
}

const clear = () => {
  toasts.value = []
}

/**
 * Toast 通知 composable
 */
export function useToast() {
  const success = (message: string, duration?: number) => add('success', message, duration)
  const error = (message: string, duration?: number) => add('error', message, duration)
  const warning = (message: string, duration?: number) => add('warning', message, duration)
  const info = (message: string, duration?: number) => add('info', message, duration)

  return {
    toasts: readonly(toasts),
    add,
    remove,
    success,
    error,
    warning,
    info,
    clear,
  }
}

// 全局 toast 实例（便捷方法）
export const toast = {
  success: (message: string, duration?: number) => add('success', message, duration),
  error: (message: string, duration?: number) => add('error', message, duration),
  warning: (message: string, duration?: number) => add('warning', message, duration),
  info: (message: string, duration?: number) => add('info', message, duration),
}
