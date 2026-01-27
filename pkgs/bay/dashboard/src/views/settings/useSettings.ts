import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSettingsStore } from '@/stores/settings'
import { toast } from '@/composables/useToast'

export function useSettings() {
  const settingsStore = useSettingsStore()
  const router = useRouter()

  // 本地表单状态 (避免直接修改 store)
  const token = ref('')
  const refreshInterval = ref(5000)
  const showToken = ref(false)

  // 预设的刷新间隔
  const refreshIntervalPresets = [
    { label: '5 秒', value: 5000 },
    { label: '10 秒', value: 10000 },
    { label: '30 秒', value: 30000 },
    { label: '1 分钟', value: 60000 },
    { label: '禁用', value: 0 },
  ]

  // 初始化表单
  onMounted(() => {
    token.value = settingsStore.token
    refreshInterval.value = settingsStore.refreshInterval
  })

  // 检查是否有更改
  const hasChanges = computed(() => {
    return (
      token.value !== settingsStore.token ||
      refreshInterval.value !== settingsStore.refreshInterval
    )
  })

  // 表单验证（现在只验证 token）
  const isValid = computed(() => true)

  const handleSave = () => {
    if (!isValid.value) return

    settingsStore.updateToken(token.value.trim())
    settingsStore.updateRefreshInterval(refreshInterval.value)
    toast.success('设置已保存')
  }

  const handleReset = () => {
    token.value = settingsStore.token
    refreshInterval.value = settingsStore.refreshInterval
    toast.info('已恢复到当前设置')
  }

  const handleClearToken = () => {
    token.value = ''
    settingsStore.updateToken('')
    toast.success('已退出登录')
    // 跳转到登录页
    router.push('/login')
  }

  const handleResetAll = () => {
    settingsStore.resetSettings()
    token.value = settingsStore.token
    refreshInterval.value = settingsStore.refreshInterval
    toast.success('已恢复默认设置')
    // 清除 token 后需要重新登录
    router.push('/login')
  }

  const toggleShowToken = () => {
    showToken.value = !showToken.value
  }

  return {
    token,
    refreshInterval,
    showToken,
    refreshIntervalPresets,
    hasChanges,
    isValid,
    handleSave,
    handleReset,
    handleClearToken,
    handleResetAll,
    toggleShowToken,
  }
}
