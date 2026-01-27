import { ref, computed, onMounted, onUnmounted, toValue, type MaybeRefOrGetter } from 'vue'
import { parseServerDate, formatRemainingTime } from '@/utils/time'

export interface TTLCountdownProps {
  expiresAt: MaybeRefOrGetter<string | null>
  showLabel?: boolean
}

export function useTTLCountdown(props: TTLCountdownProps) {
  const now = ref(Date.now())
  let intervalId: ReturnType<typeof setInterval> | null = null

  const remainingSeconds = computed(() => {
    // 使用 toValue 来支持响应式和非响应式的 expiresAt
    const expiresAt = toValue(props.expiresAt)
    const date = parseServerDate(expiresAt)
    if (!date) return 0
    const remaining = Math.max(0, Math.floor((date.getTime() - now.value) / 1000))
    return remaining
  })

  const isExpired = computed(() => remainingSeconds.value <= 0)

  const formattedTime = computed(() => {
    return formatRemainingTime(remainingSeconds.value)
  })

  const progressPercent = computed(() => {
    // 假设最大 TTL 为 24 小时
    const maxSeconds = 86400
    return Math.min(100, (remainingSeconds.value / maxSeconds) * 100)
  })

  const colorClass = computed(() => {
    const seconds = remainingSeconds.value
    if (seconds <= 0) return 'text-gray-400'
    if (seconds <= 300) return 'text-red-600' // < 5 min
    if (seconds <= 1800) return 'text-yellow-600' // < 30 min
    return 'text-green-600'
  })

  onMounted(() => {
    intervalId = setInterval(() => {
      now.value = Date.now()
    }, 1000)
  })

  onUnmounted(() => {
    if (intervalId) {
      clearInterval(intervalId)
    }
  })

  return {
    remainingSeconds,
    isExpired,
    formattedTime,
    progressPercent,
    colorClass,
  }
}
