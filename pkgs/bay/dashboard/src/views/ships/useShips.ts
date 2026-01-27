import { ref, computed } from 'vue'
import { shipApi } from '@/api'
import type { Ship } from '@/types/api'
import { useAutoRefresh } from '@/composables/useAutoRefresh'
import { toast } from '@/composables/useToast'
import { ShipStatus } from '@/types/api'

export function useShips() {
  const ships = ref<Ship[]>([])
  const searchQuery = ref('')
  const statusFilter = ref<number | null>(null)
  const deleteConfirmId = ref<string | null>(null)
  const deleteLoading = ref(false)

  const fetchShips = async () => {
    const response = await shipApi.getList()
    ships.value = response.data
  }

  const { loading, error, refresh } = useAutoRefresh(fetchShips)

  const filteredShips = computed(() => {
    let result = ships.value

    // 按状态筛选
    if (statusFilter.value !== null) {
      result = result.filter(s => s.status === statusFilter.value)
    }

    // 按关键字搜索
    if (searchQuery.value.trim()) {
      const query = searchQuery.value.toLowerCase()
      result = result.filter(s =>
        s.id.toLowerCase().includes(query) ||
        s.ip_address?.toLowerCase().includes(query)
      )
    }

    return result
  })

  const handleDelete = async () => {
    if (!deleteConfirmId.value) return

    deleteLoading.value = true
    try {
      await shipApi.delete(deleteConfirmId.value)
      toast.success('容器已停止')
      deleteConfirmId.value = null
      await refresh()
    } catch {
      // 错误已在 client.ts 中处理
    } finally {
      deleteLoading.value = false
    }
  }

  const shortId = (id: string) => id.slice(0, 8)

  const getStatusText = (status: number) => {
    switch (status) {
      case ShipStatus.RUNNING: return 'Running'
      case ShipStatus.STOPPED: return 'Stopped'
      case ShipStatus.CREATING: return 'Creating'
      default: return 'Unknown'
    }
  }

  return {
    ships,
    filteredShips,
    searchQuery,
    statusFilter,
    deleteConfirmId,
    deleteLoading,
    loading,
    error,
    refresh,
    handleDelete,
    shortId,
    getStatusText,
    ShipStatus,
  }
}
