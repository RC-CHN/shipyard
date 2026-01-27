import { ref, computed } from 'vue'
import { sessionApi } from '@/api'
import type { Session } from '@/types/api'
import { useAutoRefresh } from '@/composables/useAutoRefresh'
import { toast } from '@/composables/useToast'
import { formatDateTime, getRelativeTime } from '@/utils/time'

export function useSessions() {
  const sessions = ref<Session[]>([])
  const searchQuery = ref('')
  const activeFilter = ref<boolean | null>(null)
  const deleteConfirmId = ref<string | null>(null)
  const deleteLoading = ref(false)

  const fetchSessions = async () => {
    const response = await sessionApi.getList()
    sessions.value = response.data.sessions
  }

  const { loading, error, refresh } = useAutoRefresh(fetchSessions)

  const filteredSessions = computed(() => {
    let result = sessions.value

    // 按活跃状态筛选
    if (activeFilter.value !== null) {
      result = result.filter(s => s.is_active === activeFilter.value)
    }

    // 按关键字搜索
    if (searchQuery.value.trim()) {
      const query = searchQuery.value.toLowerCase()
      result = result.filter(s =>
        s.session_id.toLowerCase().includes(query) ||
        s.ship_id.toLowerCase().includes(query)
      )
    }

    return result
  })

  const handleDelete = async () => {
    if (!deleteConfirmId.value) return

    deleteLoading.value = true
    try {
      await sessionApi.delete(deleteConfirmId.value)
      toast.success('会话已删除')
      deleteConfirmId.value = null
      await refresh()
    } catch {
      // 错误已在 client.ts 中处理
    } finally {
      deleteLoading.value = false
    }
  }

  const shortId = (id: string) => id.slice(0, 8)

  return {
    sessions,
    filteredSessions,
    searchQuery,
    activeFilter,
    deleteConfirmId,
    deleteLoading,
    loading,
    error,
    refresh,
    handleDelete,
    shortId,
    formatDateTime,
    getRelativeTime,
  }
}
