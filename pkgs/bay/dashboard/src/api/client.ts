import axios, { type AxiosInstance, type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type { ApiError } from '@/types/api'
import { useSettingsStore } from '@/stores/settings'
import { useSessionStore } from '@/stores/session'
import { toast } from '@/composables/useToast'
import router from '@/router'

// 创建 axios 实例
const createApiClient = (): AxiosInstance => {
  const instance = axios.create({
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
  })

  // 请求拦截器 - 添加认证 token 和动态 baseURL
  instance.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      const settingsStore = useSettingsStore()
      const sessionStore = useSessionStore()
      
      // 动态设置 baseURL
      config.baseURL = settingsStore.apiBaseUrl
      
      // 添加 Authorization header
      if (settingsStore.token) {
        config.headers.Authorization = `Bearer ${settingsStore.token}`
      }
      
      // 添加 X-SESSION-ID header
      if (!config.headers['X-SESSION-ID']) {
        config.headers['X-SESSION-ID'] = sessionStore.sessionId
      }
      
      return config
    },
    (error) => {
      return Promise.reject(error)
    }
  )

  // 响应拦截器 - 统一错误处理
  instance.interceptors.response.use(
    (response) => response,
    (error: AxiosError<ApiError>) => {
      const status = error.response?.status
      const message = error.response?.data?.detail || error.response?.data?.message || error.message

      switch (status) {
        case 401:
          // 未认证，清除 token 并跳转到登录页
          const settingsStore = useSettingsStore()
          settingsStore.resetSettings()
          toast.error('登录已过期，请重新登录')
          router.push('/login')
          break
        case 403:
          toast.error('无权执行此操作')
          break
        case 404:
          toast.error('请求的资源不存在')
          break
        case 408:
          toast.error('请求超时，请稍后重试')
          break
        case 413:
          toast.error('文件过大，请选择更小的文件')
          break
        case 500:
        case 502:
        case 503:
          toast.error('服务器错误，请稍后重试')
          break
        default:
          if (error.code === 'ERR_NETWORK') {
            toast.error('网络连接失败，请检查 API 地址')
          } else if (message) {
            toast.error(message)
          }
          break
      }

      return Promise.reject(error)
    }
  )

  return instance
}

export const apiClient = createApiClient()

export default apiClient
