import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useSettingsStore } from '@/stores/settings'

/**
 * 自动刷新数据的 composable
 * @param fetchFn 获取数据的函数
 * @param immediate 是否立即执行一次
 */
export function useAutoRefresh(fetchFn: () => Promise<void>, immediate = true) {
  const settingsStore = useSettingsStore()
  const loading = ref(false)
  const error = ref<string | null>(null)
  let intervalId: ReturnType<typeof setInterval> | null = null

  const execute = async () => {
    loading.value = true
    error.value = null
    try {
      await fetchFn()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '请求失败'
    } finally {
      loading.value = false
    }
  }

  const startInterval = () => {
    stopInterval()
    if (settingsStore.refreshInterval > 0) {
      intervalId = setInterval(execute, settingsStore.refreshInterval)
    }
  }

  const stopInterval = () => {
    if (intervalId) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  // 监听刷新间隔变化
  watch(() => settingsStore.refreshInterval, () => {
    startInterval()
  })

  onMounted(() => {
    if (immediate) {
      execute()
    }
    startInterval()
  })

  onUnmounted(() => {
    stopInterval()
  })

  return {
    loading,
    error,
    refresh: execute,
    pause: stopInterval,
    resume: startInterval,
  }
}
