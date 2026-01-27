import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { shipApi } from '@/api'
import type { Ship, Session, ExtendTTLRequest } from '@/types/api'
import { useAutoRefresh } from '@/composables/useAutoRefresh'
import { toast } from '@/composables/useToast'
import { ShipStatus } from '@/types/api'

type TabName = 'info' | 'sessions' | 'logs'

export function useShipDetail() {
  const route = useRoute()
  const router = useRouter()

  const shipId = computed(() => route.params.id as string)
  const ship = ref<Ship | null>(null)
  const sessions = ref<Session[]>([])
  const logs = ref('')
  const activeTab = ref<TabName>('info')
  const deleteConfirmVisible = ref(false)
  const deleteLoading = ref(false)
  const extendLoading = ref(false)
  const recycleConfirmVisible = ref(false)
  const recycleLoading = ref(false)

  const fetchShipDetail = async () => {
    const response = await shipApi.getById(shipId.value)
    ship.value = response.data
  }

  const fetchSessions = async () => {
    try {
      const response = await shipApi.getSessions(shipId.value)
      sessions.value = response.data.sessions
    } catch {
      // 容器已停止时可能无法获取会话，忽略错误
      sessions.value = []
    }
  }

  const fetchLogs = async () => {
    try {
      const response = await shipApi.getLogs(shipId.value)
      logs.value = response.data.logs
    } catch {
      logs.value = ''
    }
  }

  const { loading, error, refresh } = useAutoRefresh(
    async () => {
      await fetchShipDetail()
      if (activeTab.value === 'sessions') {
        await fetchSessions()
      } else if (activeTab.value === 'logs') {
        await fetchLogs()
      }
    }
  )

  // 监听 tab 变化以加载对应数据
  watch(activeTab, async (tab) => {
    if (tab === 'sessions') {
      await fetchSessions()
    } else if (tab === 'logs') {
      await fetchLogs()
    }
  })

  const isRunning = computed(() => ship.value?.status === ShipStatus.RUNNING)

  const handleDelete = async () => {
    if (!ship.value) return

    deleteLoading.value = true
    try {
      await shipApi.delete(shipId.value)
      toast.success('容器已停止')
      deleteConfirmVisible.value = false
      await refresh()
    } catch {
      // 错误已在 client.ts 中处理
    } finally {
      deleteLoading.value = false
    }
  }

  const handleExtend = async (minutes: number) => {
    if (!ship.value) return

    extendLoading.value = true
    try {
      const data: ExtendTTLRequest = { ttl: minutes * 60 }
      await shipApi.extendTTL(shipId.value, data)
      toast.success(`已延长 ${minutes} 分钟`)
      await refresh()
    } catch {
      // 错误已在 client.ts 中处理
    } finally {
      extendLoading.value = false
    }
  }

  const openRecycleConfirm = async () => {
    // 在显示确认弹窗前先获取关联的会话
    await fetchSessions()
    recycleConfirmVisible.value = true
  }

  const handleRecycle = async () => {
    if (!ship.value) return

    recycleLoading.value = true
    try {
      await shipApi.deletePermanent(shipId.value)
      toast.success('容器记录已删除')
      recycleConfirmVisible.value = false
      router.push('/ships')
    } catch {
      // 错误已在 client.ts 中处理
    } finally {
      recycleLoading.value = false
    }
  }

  const setActiveTab = (tab: TabName) => {
    activeTab.value = tab
  }

  const tabs = [
    { name: 'info' as TabName, label: '信息', icon: 'info' },
    { name: 'sessions' as TabName, label: '会话', icon: 'users' },
    { name: 'logs' as TabName, label: '日志', icon: 'terminal' },
  ]

  const shortId = (id: string) => id.slice(0, 8)

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast.success('已复制到剪贴板')
    } catch {
      toast.error('复制失败')
    }
  }

  return {
    shipId,
    ship,
    sessions,
    logs,
    activeTab,
    tabs,
    deleteConfirmVisible,
    deleteLoading,
    extendLoading,
    recycleConfirmVisible,
    recycleLoading,
    loading,
    error,
    isRunning,
    refresh,
    handleDelete,
    handleExtend,
    openRecycleConfirm,
    handleRecycle,
    setActiveTab,
    shortId,
    copyToClipboard,
    ShipStatus,
  }
}
