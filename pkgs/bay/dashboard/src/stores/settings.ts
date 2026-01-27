import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AppSettings } from '@/types/api'

const STORAGE_KEY = 'bay-dashboard-settings'

const defaultSettings: AppSettings = {
  apiBaseUrl: '/api',  // 使用代理模式
  token: '',
  refreshInterval: 30000, // 30 秒
}

export const useSettingsStore = defineStore('settings', () => {
  // 从 localStorage 加载设置
  const loadSettings = (): AppSettings => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        // 强制使用固定的 apiBaseUrl，忽略存储的值
        return {
          ...defaultSettings,
          ...parsed,
          apiBaseUrl: '/api'  // 始终使用代理模式
        }
      } catch {
        return defaultSettings
      }
    }
    return defaultSettings
  }

  const settings = ref<AppSettings>(loadSettings())

  // Computed
  const apiBaseUrl = computed(() => settings.value.apiBaseUrl)
  const token = computed(() => settings.value.token)
  const refreshInterval = computed(() => settings.value.refreshInterval)
  const isAuthenticated = computed(() => !!settings.value.token)

  // Actions
  const saveSettings = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings.value))
  }

  const updateApiBaseUrl = (url: string) => {
    settings.value.apiBaseUrl = url
    saveSettings()
  }

  const updateToken = (newToken: string) => {
    settings.value.token = newToken
    saveSettings()
  }

  const updateRefreshInterval = (interval: number) => {
    settings.value.refreshInterval = interval
    saveSettings()
  }

  const resetSettings = () => {
    settings.value = { ...defaultSettings }
    saveSettings()
  }

  return {
    settings,
    apiBaseUrl,
    token,
    refreshInterval,
    isAuthenticated,
    updateApiBaseUrl,
    updateToken,
    updateRefreshInterval,
    resetSettings,
  }
})
