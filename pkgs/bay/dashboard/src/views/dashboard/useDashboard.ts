import { ref } from 'vue'
import { statApi } from '@/api'
import type { OverviewResponse } from '@/types/api'
import { useAutoRefresh } from '@/composables/useAutoRefresh'

export function useDashboard() {
  const overview = ref<OverviewResponse | null>(null)

  const fetchOverview = async () => {
    const response = await statApi.getOverview()
    overview.value = response.data
  }

  const { loading, error, refresh } = useAutoRefresh(fetchOverview)

  return {
    overview,
    loading,
    error,
    refresh,
  }
}
