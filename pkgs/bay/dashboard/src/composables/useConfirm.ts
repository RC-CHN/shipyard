import { ref } from 'vue'

export interface ConfirmOptions {
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  type?: 'danger' | 'warning' | 'info'
}

const isOpen = ref(false)
const options = ref<ConfirmOptions | null>(null)
let resolvePromise: ((value: boolean) => void) | null = null

/**
 * 确认弹窗 composable
 */
export function useConfirm() {
  const confirm = (opts: ConfirmOptions): Promise<boolean> => {
    options.value = {
      confirmText: '确认',
      cancelText: '取消',
      type: 'info',
      ...opts,
    }
    isOpen.value = true

    return new Promise<boolean>((resolve) => {
      resolvePromise = resolve
    })
  }

  const handleConfirm = () => {
    isOpen.value = false
    if (resolvePromise) {
      resolvePromise(true)
      resolvePromise = null
    }
  }

  const handleCancel = () => {
    isOpen.value = false
    if (resolvePromise) {
      resolvePromise(false)
      resolvePromise = null
    }
  }

  return {
    isOpen,
    options,
    confirm,
    handleConfirm,
    handleCancel,
  }
}

// 便捷方法
export const confirmDialog = (opts: ConfirmOptions) => {
  const { confirm } = useConfirm()
  return confirm(opts)
}

export const confirmDelete = (itemName: string) => {
  return confirmDialog({
    title: '确认删除',
    message: `确定要删除 ${itemName} 吗？此操作不可撤销。`,
    confirmText: '删除',
    type: 'danger',
  })
}
