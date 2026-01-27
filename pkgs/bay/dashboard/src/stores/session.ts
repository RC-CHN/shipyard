import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const SESSION_STORAGE_KEY = 'bay-session-id'

/**
 * 生成 UUID v4
 * 兼容非安全上下文（HTTP 环境）
 */
const generateUUID = (): string => {
  // 优先使用 crypto.randomUUID()（需要安全上下文）
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    try {
      return crypto.randomUUID()
    } catch {
      // 在非安全上下文中可能会失败
    }
  }
  
  // 回退方案：使用 crypto.getRandomValues()
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    const bytes = new Uint8Array(16)
    crypto.getRandomValues(bytes)
    // 设置版本为 4 和变体
    const byte6 = bytes[6]
    const byte8 = bytes[8]
    if (byte6 !== undefined && byte8 !== undefined) {
      bytes[6] = (byte6 & 0x0f) | 0x40
      bytes[8] = (byte8 & 0x3f) | 0x80
    }
    
    const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('')
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
  }
  
  // 最后的回退方案：使用 Math.random()
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

/**
 * Session Store
 * 管理当前浏览器会话的上下文，用于 X-SESSION-ID 请求头
 */
export const useSessionStore = defineStore('session', () => {
  // 从 sessionStorage 加载或生成新的 session ID
  const loadOrCreateSessionId = (): string => {
    try {
      const stored = sessionStorage.getItem(SESSION_STORAGE_KEY)
      if (stored) {
        return stored
      }
    } catch {
      // sessionStorage 可能不可用
    }
    
    const newId = generateUUID()
    
    try {
      sessionStorage.setItem(SESSION_STORAGE_KEY, newId)
    } catch {
      // sessionStorage 可能不可用
    }
    
    return newId
  }

  const sessionId = ref<string>(loadOrCreateSessionId())
  const currentShipId = ref<string | null>(null)

  // Computed
  const shortSessionId = computed(() => sessionId.value.slice(0, 8))

  // Actions
  const regenerateSessionId = () => {
    const newId = generateUUID()
    try {
      sessionStorage.setItem(SESSION_STORAGE_KEY, newId)
    } catch {
      // sessionStorage 可能不可用
    }
    sessionId.value = newId
  }

  const setCurrentShipId = (shipId: string | null) => {
    currentShipId.value = shipId
  }

  const clearSession = () => {
    sessionStorage.removeItem(SESSION_STORAGE_KEY)
    currentShipId.value = null
  }

  return {
    sessionId,
    currentShipId,
    shortSessionId,
    regenerateSessionId,
    setCurrentShipId,
    clearSession,
  }
})
