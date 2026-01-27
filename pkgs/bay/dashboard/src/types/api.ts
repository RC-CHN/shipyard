// API 响应的基础类型

// 系统概览
export interface OverviewResponse {
  service: string
  version: string
  status: 'running' | 'stopped'
  ships: {
    total: number
    running: number
    stopped: number
    creating: number
  }
  sessions: {
    total: number
    active: number
  }
}

// Ship 状态常量 (与后端一致)
export const ShipStatus = {
  STOPPED: 0,
  RUNNING: 1,
  CREATING: 2,
} as const

export type ShipStatusType = typeof ShipStatus[keyof typeof ShipStatus]

// Ship 相关类型 (与后端 ShipResponse 一致)
export interface Ship {
  id: string
  status: number  // 0: stopped, 1: running, 2: creating
  created_at: string
  updated_at: string
  container_id: string | null
  ip_address: string | null
  ttl: number
  max_session_num: number
  current_session_num: number
  expires_at: string | null
}

// Ship 规格
export interface ShipSpec {
  cpus?: number
  memory?: string  // e.g., '512m', '1g'
  disk?: string    // e.g., '1Gi', '10G'
}

// 创建 Ship 请求 (与后端 CreateShipRequest 一致)
export interface CreateShipRequest {
  ttl: number
  spec?: ShipSpec
  max_session_num?: number
}

export interface ExtendTTLRequest {
  ttl: number
}

export interface StartShipRequest {
  ttl?: number  // 默认 3600 秒
}

export interface ExtendSessionTTLRequest {
  ttl: number  // TTL in seconds
}

export interface ShipLogsResponse {
  logs: string
}

// Session 相关类型 (与后端 SessionResponse 一致)
export interface Session {
  id: string
  session_id: string
  ship_id: string
  created_at: string
  last_activity: string
  expires_at: string
  initial_ttl: number
  is_active: boolean
}

// Session 列表响应
export interface SessionListResponse {
  sessions: Session[]
  total: number
}

// Ship Sessions 响应
export interface ShipSessionsResponse {
  ship_id: string
  sessions: Session[]
  total: number
}

// 执行命令相关类型 (与后端 ExecRequest 一致)
export interface ExecRequest {
  type: string  // e.g., 'shell/exec', 'ipython/exec'
  payload?: Record<string, unknown>
}

export interface ExecResponse {
  success: boolean
  data?: Record<string, unknown>
  error?: string
}

// 文件操作相关类型
export interface UploadFileResponse {
  success: boolean
  message: string
  file_path?: string
  error?: string
}

// API 通用响应
export interface ApiResponse<T> {
  data: T
  message?: string
}

export interface ApiError {
  status: number
  message: string
  detail?: string
}

// 设置相关
export interface AppSettings {
  apiBaseUrl: string
  token: string
  refreshInterval: number
}

// 辅助函数
export function getShipStatusText(status: number): string {
  switch (status) {
    case ShipStatus.RUNNING: return 'running'
    case ShipStatus.STOPPED: return 'stopped'
    case ShipStatus.CREATING: return 'creating'
    default: return 'unknown'
  }
}

export function getShipStatusClass(status: number): string {
  switch (status) {
    case ShipStatus.RUNNING: return 'bg-green-100 text-green-800'
    case ShipStatus.STOPPED: return 'bg-gray-100 text-gray-800'
    case ShipStatus.CREATING: return 'bg-yellow-100 text-yellow-800'
    default: return 'bg-gray-100 text-gray-800'
  }
}
