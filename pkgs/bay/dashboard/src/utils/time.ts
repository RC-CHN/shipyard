/**
 * 时间处理工具函数
 * 处理后端 UTC 时间与本地时间的转换
 * 
 * 后端使用 datetime.now(timezone.utc) 存储时间，
 * 但 FastAPI/Pydantic 序列化时可能不带时区后缀：
 * - 2024-01-26T07:08:45.123456 (没有时区信息，但实际是 UTC)
 * - 2024-01-26T07:08:45+00:00
 * - 2024-01-26T07:08:45Z
 */

/**
 * 将后端返回的时间字符串解析为 Date 对象
 * 后端时间都是 UTC，如果没有时区信息则添加 Z 后缀
 */
export function parseServerDate(dateStr: string | null | undefined): Date | null {
  if (!dateStr) return null
  
  let normalized = dateStr.trim()
  
  // 如果没有时区信息，添加 Z 后缀表示 UTC
  // 检查是否以 Z 结尾，或包含 + 或 - 时区偏移（但排除日期中的 -）
  const hasTimezone = normalized.endsWith('Z') || 
    /[+-]\d{2}:\d{2}$/.test(normalized) || 
    /[+-]\d{4}$/.test(normalized)
  
  if (!hasTimezone) {
    normalized = normalized + 'Z'
  }
  
  const date = new Date(normalized)
  return isNaN(date.getTime()) ? null : date
}

/**
 * 格式化日期时间为本地格式
 */
export function formatDateTime(dateStr: string | null | undefined): string {
  const date = parseServerDate(dateStr)
  if (!date) return '-'
  
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

/**
 * 格式化日期为本地短格式
 */
export function formatDate(dateStr: string | null | undefined): string {
  const date = parseServerDate(dateStr)
  if (!date) return '-'
  
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

/**
 * 格式化时间为本地短格式
 */
export function formatTime(dateStr: string | null | undefined): string {
  const date = parseServerDate(dateStr)
  if (!date) return '-'
  
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

/**
 * 计算相对时间（X 分钟前、X 小时前等）
 */
export function getRelativeTime(dateStr: string | null | undefined): string {
  const date = parseServerDate(dateStr)
  if (!date) return '-'
  
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  
  // 处理未来时间（可能由于时间同步误差）
  if (diffMs < -60000) { // 允许 1 分钟的误差
    return '刚刚'
  }
  
  const diffSecs = Math.abs(Math.floor(diffMs / 1000))
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)
  const diffWeeks = Math.floor(diffDays / 7)
  const diffMonths = Math.floor(diffDays / 30)
  
  if (diffSecs < 60) return '刚刚'
  if (diffMins < 60) return `${diffMins} 分钟前`
  if (diffHours < 24) return `${diffHours} 小时前`
  if (diffDays < 7) return `${diffDays} 天前`
  if (diffWeeks < 4) return `${diffWeeks} 周前`
  if (diffMonths < 12) return `${diffMonths} 月前`
  return `${Math.floor(diffMonths / 12)} 年前`
}

/**
 * 计算距离过期的剩余秒数
 */
export function getRemainingSeconds(expiresAt: string | null | undefined): number {
  const date = parseServerDate(expiresAt)
  if (!date) return 0
  
  const now = new Date()
  const remaining = Math.floor((date.getTime() - now.getTime()) / 1000)
  return Math.max(0, remaining)
}

/**
 * 格式化剩余时间为可读格式
 */
export function formatRemainingTime(seconds: number): string {
  if (seconds <= 0) return '已过期'
  
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  
  const parts: string[] = []
  if (days > 0) parts.push(`${days}d`)
  if (hours > 0 || days > 0) parts.push(`${hours}h`)
  if (minutes > 0 || hours > 0 || days > 0) parts.push(`${minutes}m`)
  parts.push(`${secs}s`)
  
  return parts.join(' ')
}

/**
 * 判断时间是否已过期
 */
export function isExpired(expiresAt: string | null | undefined): boolean {
  return getRemainingSeconds(expiresAt) <= 0
}
