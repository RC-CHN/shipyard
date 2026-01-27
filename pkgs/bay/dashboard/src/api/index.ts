import apiClient from './client'
import type {
  OverviewResponse,
  Ship,
  CreateShipRequest,
  ExtendTTLRequest,
  StartShipRequest,
  ExtendSessionTTLRequest,
  ShipLogsResponse,
  Session,
  SessionListResponse,
  ShipSessionsResponse,
  ExecRequest,
  ExecResponse,
  UploadFileResponse,
} from '@/types/api'

// 统计接口
export const statApi = {
  // 获取基本信息（不需要认证）
  getInfo: () => apiClient.get<{ service: string; version: string; status: string }>('/stat'),
  // 获取详细概览（需要认证）
  getOverview: () => apiClient.get<OverviewResponse>('/stat/overview'),
}

// Ship 接口
export const shipApi = {
  // 获取所有 Ships
  getList: () => apiClient.get<Ship[]>('/ships'),
  
  // 获取单个 Ship 详情
  getById: (id: string) => apiClient.get<Ship>(`/ship/${id}`),
  
  // 创建 Ship
  create: (data: CreateShipRequest) => apiClient.post<Ship>('/ship', data),
  
  // 删除 Ship（软删除 - 停止容器但保留数据）
  delete: (id: string) => apiClient.delete(`/ship/${id}`),
  
  // 永久删除 Ship（硬删除 - 删除容器、数据和数据库记录）
  deletePermanent: (id: string) => apiClient.delete(`/ship/${id}/permanent`),
  
  // 延长 TTL
  extendTTL: (id: string, data: ExtendTTLRequest) =>
    apiClient.post<Ship>(`/ship/${id}/extend-ttl`, data),
  
  // 启动已停止的容器
  start: (id: string, data?: StartShipRequest) =>
    apiClient.post<Ship>(`/ship/${id}/start`, data || {}),
  
  // 获取日志
  getLogs: (id: string) => apiClient.get<ShipLogsResponse>(`/ship/logs/${id}`),
  
  // 获取关联的 Sessions
  getSessions: (id: string) => apiClient.get<ShipSessionsResponse>(`/ship/${id}/sessions`),
  
  // 执行命令
  exec: (id: string, data: ExecRequest) => 
    apiClient.post<ExecResponse>(`/ship/${id}/exec`, data),
  
  // 上传文件
  uploadFile: (id: string, file: File, filePath: string) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('file_path', filePath)
    return apiClient.post<UploadFileResponse>(`/ship/${id}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  
  // 下载文件
  downloadFile: (id: string, filePath: string) => 
    apiClient.get(`/ship/${id}/download`, {
      params: { file_path: filePath },
      responseType: 'blob'
    }),
}

// Session 接口
export const sessionApi = {
  // 获取所有 Sessions
  getList: () => apiClient.get<SessionListResponse>('/sessions'),
  
  // 获取单个 Session
  getById: (id: string) => apiClient.get<Session>(`/sessions/${id}`),
  
  // 延长 Session TTL
  extendTTL: (id: string, data: ExtendSessionTTLRequest) =>
    apiClient.post<Session>(`/sessions/${id}/extend-ttl`, data),
  
  // 删除 Session
  delete: (id: string) => apiClient.delete(`/sessions/${id}`),
}

// 健康检查接口
export const healthApi = {
  check: () => apiClient.get<{ status: string; message: string }>('/health'),
}
