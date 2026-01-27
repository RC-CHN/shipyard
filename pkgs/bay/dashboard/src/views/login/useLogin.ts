import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSettingsStore } from '@/stores/settings'
import { healthApi } from '@/api'
import { toast } from '@/composables/useToast'

export function useLogin() {
  const router = useRouter()
  const settingsStore = useSettingsStore()

  const form = ref({
    token: '',
  })

  const loading = ref(false)
  const showPassword = ref(false)

  const validateForm = (): boolean => {
    if (!form.value.token.trim()) {
      toast.error('请输入 Access Token')
      return false
    }
    return true
  }

  const handleLogin = async () => {
    if (!validateForm()) return

    loading.value = true
    
    try {
      // 设置 token（API 地址固定为 /api，通过 Nginx 代理）
      settingsStore.updateToken(form.value.token)

      // 测试连接
      await healthApi.check()
      
      toast.success('登录成功')
      
      // 跳转到首页
      const redirect = router.currentRoute.value.query.redirect as string
      router.push(redirect || '/')
    } catch (error: unknown) {
      // 登录失败，清除 token
      settingsStore.updateToken('')
      // 错误已经在 api/client.ts 中处理
    } finally {
      loading.value = false
    }
  }

  return {
    form,
    loading,
    showPassword,
    handleLogin,
  }
}
