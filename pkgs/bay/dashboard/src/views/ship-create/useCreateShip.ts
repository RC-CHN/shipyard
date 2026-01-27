import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { shipApi } from '@/api'
import type { CreateShipRequest, ShipSpec } from '@/types/api'
import { toast } from '@/composables/useToast'

export function useCreateShip() {
  const router = useRouter()

  // 表单数据
  const ttlMinutes = ref(60) // 默认60分钟
  const maxSessionNum = ref(1) // 默认1个会话
  const cpus = ref<number | undefined>(undefined)
  const memory = ref<string>('')
  const disk = ref<string>('')
  const showAdvanced = ref(false)
  const submitting = ref(false)

  // 预设的 TTL 选项
  const ttlPresets = [
    { label: '30 分钟', value: 30 },
    { label: '1 小时', value: 60 },
    { label: '2 小时', value: 120 },
    { label: '4 小时', value: 240 },
    { label: '8 小时', value: 480 },
    { label: '24 小时', value: 1440 },
  ]

  // 表单验证
  const errors = computed(() => {
    const errs: Record<string, string> = {}
    if (ttlMinutes.value < 1) {
      errs.ttl = 'TTL 必须大于 0'
    }
    if (ttlMinutes.value > 1440 * 7) {
      errs.ttl = 'TTL 最大为 7 天'
    }
    if (maxSessionNum.value < 1) {
      errs.maxSessionNum = '最大会话数必须大于 0'
    }
    if (memory.value && !/^\d+(m|g|M|G|Mi|Gi)?$/.test(memory.value)) {
      errs.memory = '内存格式无效，例如：512m, 1g'
    }
    if (disk.value && !/^\d+(g|G|Gi)?$/.test(disk.value)) {
      errs.disk = '磁盘格式无效，例如：1Gi, 10G'
    }
    return errs
  })

  const isValid = computed(() => Object.keys(errors.value).length === 0)

  const handleSubmit = async () => {
    if (!isValid.value || submitting.value) return

    submitting.value = true
    try {
      const spec: ShipSpec = {}
      if (cpus.value !== undefined && cpus.value > 0) {
        spec.cpus = cpus.value
      }
      if (memory.value.trim()) {
        spec.memory = memory.value.trim()
      }
      if (disk.value.trim()) {
        spec.disk = disk.value.trim()
      }

      const request: CreateShipRequest = {
        ttl: ttlMinutes.value * 60, // 转换为秒
        max_session_num: maxSessionNum.value,
      }

      // 只有在设置了 spec 时才添加
      if (Object.keys(spec).length > 0) {
        request.spec = spec
      }

      const response = await shipApi.create(request)
      toast.success('容器创建成功')
      router.push(`/ships/${response.data.id}`)
    } catch {
      // 错误已在 client.ts 中处理
    } finally {
      submitting.value = false
    }
  }

  const handleCancel = () => {
    router.push('/ships')
  }

  return {
    ttlMinutes,
    maxSessionNum,
    cpus,
    memory,
    disk,
    showAdvanced,
    submitting,
    ttlPresets,
    errors,
    isValid,
    handleSubmit,
    handleCancel,
  }
}
