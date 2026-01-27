import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { sessionApi, shipApi } from '@/api'
import type { Session } from '@/types/api'
import { useAutoRefresh } from '@/composables/useAutoRefresh'
import { toast } from '@/composables/useToast'
import { apiClient } from '@/api/client'

export function useSessionDetail() {
  const route = useRoute()
  const router = useRouter()

  const sessionId = computed(() => route.params.id as string)
  const session = ref<Session | null>(null)
  const deleteConfirmVisible = ref(false)
  const deleteLoading = ref(false)
  const startLoading = ref(false)

  const fetchSessionDetail = async () => {
    const response = await sessionApi.getById(sessionId.value)
    session.value = response.data
  }

  const { loading, error, refresh } = useAutoRefresh(fetchSessionDetail)

  const isActive = computed(() => session.value?.is_active ?? false)

  const handleDelete = async () => {
    if (!session.value) return

    deleteLoading.value = true
    try {
      await sessionApi.delete(sessionId.value)
      toast.success('会话已删除')
      deleteConfirmVisible.value = false
      router.push('/sessions')
    } catch {
      // 错误已在 client.ts 中处理
    } finally {
      deleteLoading.value = false
    }
  }

  const handleStart = async () => {
    if (!session.value) return
    
    startLoading.value = true
    const defaultTTL = 3600  // 默认 1 小时
    try {
      // 启动容器
      await shipApi.start(session.value.ship_id, { ttl: defaultTTL })
      
      // 同时延长会话的 TTL
      await sessionApi.extendTTL(session.value.session_id, { ttl: defaultTTL })
      
      toast.success('容器已启动，会话 TTL 已更新')
      // 刷新会话信息
      await fetchSessionDetail()
    } catch {
      // 错误已在 client.ts 中处理
    } finally {
      startLoading.value = false
    }
  }

  const shortId = (id: string) => id.slice(0, 8)

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast.success('已复制到剪贴板')
    } catch {
      toast.error('复制失败')
    }
  }

  const activeTab = ref<'info' | 'terminal' | 'python'>('info')

  const tabs = [
    { name: 'info', label: '基本信息', icon: 'info' },
    { name: 'terminal', label: '终端', icon: 'terminal' },
    { name: 'python', label: 'Python 执行', icon: 'code' },
  ] as const

  const setActiveTab = (tab: typeof activeTab.value) => {
    activeTab.value = tab
  }

  const terminalInput = ref('')
  const terminalHistory = ref<string[]>([])
  const terminalLoading = ref(false)


  const clearTerminal = () => {
    terminalHistory.value = []
  }

  const refreshShipSessions = async () => {
    if (!session.value) return
    const response = await shipApi.getSessions(session.value.ship_id)
    const target = response.data.sessions.find((item) => item.session_id === session.value?.session_id)
    if (target) {
      session.value = target
    }
  }

  // 终端命令历史回溯
  const commandHistoryIndex = ref(-1)
  const localCommandHistory = ref<string[]>([])

  const getPreviousCommand = () => {
    if (localCommandHistory.value.length === 0) return ''
    if (commandHistoryIndex.value < localCommandHistory.value.length - 1) {
      commandHistoryIndex.value++
      return localCommandHistory.value[localCommandHistory.value.length - 1 - commandHistoryIndex.value]
    }
    return localCommandHistory.value[0]
  }

  const getNextCommand = () => {
    if (commandHistoryIndex.value > 0) {
      commandHistoryIndex.value--
      return localCommandHistory.value[localCommandHistory.value.length - 1 - commandHistoryIndex.value]
    }
    commandHistoryIndex.value = -1
    return ''
  }

  // 修改 sendCommand 以支持历史记录
  const sendCommand = async () => {
    if (!session.value || !terminalInput.value.trim() || terminalLoading.value) return
    const command = terminalInput.value.trim()
    
    // 添加到本地历史用于回溯
    localCommandHistory.value.push(command)
    commandHistoryIndex.value = -1

    // 添加到显示历史
    terminalHistory.value.push(`$ ${command}`)
    terminalInput.value = ''
    terminalLoading.value = true
    
    try {
      const response = await apiClient.post(
        `/ship/${session.value.ship_id}/exec`,
        {
          type: 'shell/exec',
          payload: {
            command,
            timeout: 30,
            shell: true,
            background: false,
          },
        },
        {
          headers: {
            'X-SESSION-ID': session.value.session_id,
          },
        }
      )
      const data = response.data as any
      if (data?.data?.stdout) {
        terminalHistory.value.push(data.data.stdout.trimEnd())
      }
      if (data?.data?.stderr) {
        terminalHistory.value.push(data.data.stderr.trimEnd())
      }
      if (!data?.success && data?.error) {
        terminalHistory.value.push(`Error: ${data.error}`)
      }
      if (!data?.data?.stdout && !data?.data?.stderr && data?.success) {
        // 如果没有输出且成功，不显示任何内容（像真实终端一样）
      }
    } catch {
      // 错误已在 client.ts 中处理
    } finally {
      terminalLoading.value = false
    }
  }

  // Python 执行相关
  const pythonCode = ref('# 在这里编写 Python 代码\nprint("Hello, World!")\n')
  const pythonOutput = ref<Array<{ type: 'text' | 'image' | 'error'; content: string }>>([])
  const pythonLoading = ref(false)

  const runPython = async () => {
    if (!session.value || pythonLoading.value) return
    pythonLoading.value = true
    pythonOutput.value = []
    try {
      const response = await apiClient.post(
        `/ship/${session.value.ship_id}/exec`,
        {
          type: 'ipython/exec',
          payload: {
            code: pythonCode.value,
            timeout: 60,
          },
        },
        {
          headers: {
            'X-SESSION-ID': session.value.session_id,
          },
        }
      )
      const resp = response.data as any
      // Bay 代理返回格式: { success, data: { success, output: { text, images }, error, ... } }
      // Ship 返回的数据在 resp.data 里
      const shipData = resp?.data || {}
      if (resp?.success && shipData?.success !== false) {
        const output = shipData?.output || {}
        // 处理文本输出
        if (output.text) {
          pythonOutput.value.push({ type: 'text', content: output.text })
        }
        // 处理图片输出 (images 是数组，每个元素为 {"image/png": "base64..."})
        if (output.images && Array.isArray(output.images)) {
          for (const img of output.images) {
            if (img['image/png']) {
              pythonOutput.value.push({ type: 'image', content: img['image/png'] })
            }
          }
        }
        // 如果没有任何输出，显示执行完成
        if (pythonOutput.value.length === 0) {
          pythonOutput.value.push({ type: 'text', content: '执行完成' })
        }
      } else if (shipData?.error || resp?.error) {
        pythonOutput.value.push({ type: 'error', content: shipData?.error || resp?.error })
      }
    } catch {
      // 错误已在 client.ts 中处理
    } finally {
      pythonLoading.value = false
    }
  }

  const clearPythonOutput = () => {
    pythonOutput.value = []
  }

  return {
    sessionId,
    session,
    deleteConfirmVisible,
    deleteLoading,
    loading,
    error,
    refresh,
    isActive,
    handleDelete,
    handleStart,
    startLoading,
    shortId,
    copyToClipboard,
    activeTab,
    tabs,
    setActiveTab,
    terminalInput,
    terminalHistory,
    terminalLoading,
    sendCommand,
    clearTerminal,
    refreshShipSessions,
    pythonCode,
    pythonOutput,
    pythonLoading,
    runPython,
    clearPythonOutput,
    getPreviousCommand,
    getNextCommand,
  }
}
