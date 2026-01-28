<script setup lang="ts">
import { useShipDetail } from './useShipDetail'
import { StatusBadge, TTLCountdown, Modal } from '@/components'
import { formatDateTime } from '@/utils/time'

const {
  shipId,
  ship,
  sessions,
  logs,
  activeTab,
  tabs,
  deleteConfirmVisible,
  deleteLoading,
  extendLoading,
  recycleConfirmVisible,
  recycleLoading,
  loading,
  error,
  isRunning,
  refresh,
  handleDelete,
  handleExtend,
  openRecycleConfirm,
  handleRecycle,
  setActiveTab,
  shortId,
  copyToClipboard
} = useShipDetail()
</script>

<template>
  <div class="space-y-8">
    <!-- 面包屑导航 -->
    <nav class="flex items-center space-x-2 text-sm text-slate-500">
      <router-link to="/ships" class="hover:text-[#3282B8] transition-colors flex items-center gap-1">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
        容器列表
      </router-link>
      <span class="text-slate-300">/</span>
      <span class="text-[#0F4C75] font-medium font-mono">{{ shortId(shipId) }}</span>
    </nav>

    <!-- 加载状态 -->
    <div v-if="loading && !ship" class="card p-8 animate-pulse">
      <div class="h-8 bg-blue-50 rounded w-1/4 mb-6"></div>
      <div class="h-4 bg-slate-100 rounded w-1/2 mb-3"></div>
      <div class="h-4 bg-slate-100 rounded w-1/3"></div>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error && !ship" class="bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-xl shadow-sm flex items-center gap-3">
      <span class="text-xl">⚠️</span>
      <div>
        {{ error }}
        <button @click="refresh" class="ml-2 underline hover:text-red-800 font-medium">重试</button>
      </div>
    </div>

    <!-- 容器详情 -->
    <template v-else-if="ship">
      <!-- 顶部信息卡片 -->
      <div class="card p-8 relative overflow-hidden">
        <div class="absolute top-0 right-0 p-8 opacity-5 pointer-events-none">
          <svg class="w-64 h-64 text-[#0F4C75]" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5zm0 9l2.5-1.25L12 8.5l-2.5 1.25L12 11zm0 2.5l-5-2.5-5 2.5L12 22l10-8.5-5-2.5-5 2.5z"/></svg>
        </div>

        <div class="relative z-10 flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
          <!-- 左侧：基本信息 -->
          <div class="flex items-start gap-6">
            <div class="w-20 h-20 rounded-2xl bg-gradient-to-br from-[#0F4C75] to-[#3282B8] flex items-center justify-center shadow-lg shadow-blue-200 text-white">
              <svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" /></svg>
            </div>
            <div>
              <h1 class="text-3xl font-bold text-[#0F4C75] font-mono flex items-center gap-4 mb-2">
                {{ shipId }}
                <StatusBadge :status="ship.status" size="md" />
              </h1>
              <div class="flex items-center gap-6 text-slate-500 text-sm">
                <span class="flex items-center gap-1.5">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                  创建于 {{ formatDateTime(ship.created_at) }}
                </span>
                <span v-if="ship.ip_address" class="flex items-center gap-1.5 font-mono text-[#3282B8] bg-blue-50 px-2 py-0.5 rounded">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" /></svg>
                  {{ ship.ip_address }}
                </span>
              </div>
            </div>
          </div>

          <!-- 右侧：操作按钮 -->
          <div class="flex flex-wrap gap-3">
            <button
              @click="refresh"
              :disabled="loading"
              class="btn-secondary px-4 py-2 flex items-center gap-2"
            >
              <svg 
                class="w-4 h-4 transition-transform duration-500" 
                :class="{ 'animate-spin': loading }"
                fill="none" 
                stroke="currentColor" 
                viewBox="0 0 24 24"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              刷新
            </button>
            <template v-if="isRunning">
              <div class="relative group">
                <button
                  :disabled="extendLoading"
                  class="btn-primary px-4 py-2 flex items-center gap-2 bg-green-600 hover:bg-green-700 border-green-600"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                  {{ extendLoading ? '处理中...' : '延长时间' }}
                </button>
                <div class="absolute right-0 mt-2 w-48 bg-white rounded-xl shadow-xl border border-blue-100 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-20 overflow-hidden transform origin-top-right scale-95 group-hover:scale-100">
                  <button
                    @click="handleExtend(30)"
                    class="w-full text-left px-4 py-3 hover:bg-blue-50 text-slate-600 hover:text-[#0F4C75] transition-colors border-b border-slate-50"
                  >
                    +30 分钟
                  </button>
                  <button
                    @click="handleExtend(60)"
                    class="w-full text-left px-4 py-3 hover:bg-blue-50 text-slate-600 hover:text-[#0F4C75] transition-colors border-b border-slate-50"
                  >
                    +1 小时
                  </button>
                  <button
                    @click="handleExtend(120)"
                    class="w-full text-left px-4 py-3 hover:bg-blue-50 text-slate-600 hover:text-[#0F4C75] transition-colors"
                  >
                    +2 小时
                  </button>
                </div>
              </div>
              <button
                @click="deleteConfirmVisible = true"
                class="btn-danger px-4 py-2 flex items-center gap-2"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" /></svg>
                停止容器
              </button>
            </template>
            <button
              v-else
              @click="openRecycleConfirm"
              class="btn-danger px-4 py-2 flex items-center gap-2"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
              永久删除
            </button>
          </div>
        </div>

        <!-- TTL 倒计时 (运行中才显示) -->
        <div v-if="isRunning && ship.expires_at" class="mt-8 pt-6 border-t border-blue-50 flex items-center gap-4">
          <div class="text-sm font-medium text-slate-500 uppercase tracking-wider">剩余运行时间</div>
          <TTLCountdown :expires-at="ship.expires_at" show-label class="text-2xl font-mono font-bold text-[#3282B8]" />
        </div>
      </div>

      <!-- 标签页导航 -->
      <div class="card overflow-hidden min-h-[500px] flex flex-col">
        <div class="border-b border-blue-50 bg-slate-50/50">
          <nav class="flex px-6 gap-6">
            <button
              v-for="tab in tabs"
              :key="tab.name"
              @click="setActiveTab(tab.name)"
              :class="[
                'px-2 py-4 text-sm font-medium border-b-2 transition-all duration-300 flex items-center gap-2',
                activeTab === tab.name
                  ? 'border-[#3282B8] text-[#0F4C75]'
                  : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
              ]"
            >
              <span v-if="tab.name === 'info'">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              </span>
              <span v-else-if="tab.name === 'sessions'">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
              </span>
              <span v-else-if="tab.name === 'logs'">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
              </span>
              {{ tab.label }}
            </button>
          </nav>
        </div>

        <!-- 标签页内容 -->
        <div class="p-8 flex-1">
          <!-- 信息标签页 -->
          <div v-if="activeTab === 'info'" class="space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div class="bg-blue-50/50 rounded-xl p-6 border border-blue-50">
                <div class="text-sm font-medium text-slate-500 mb-2 uppercase tracking-wider">容器 ID</div>
                <div class="flex items-center gap-2">
                  <div class="font-mono text-lg text-[#0F4C75] truncate flex-1" :title="ship.container_id || undefined">{{ ship.container_id || '-' }}</div>
                  <button
                    v-if="ship.container_id"
                    @click="copyToClipboard(ship.container_id)"
                    class="flex-shrink-0 p-1.5 text-slate-400 hover:text-[#3282B8] hover:bg-blue-100 rounded-md transition-colors"
                    title="复制容器 ID"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  </button>
                </div>
              </div>
              <div class="bg-blue-50/50 rounded-xl p-6 border border-blue-50">
                <div class="text-sm font-medium text-slate-500 mb-2 uppercase tracking-wider">IP 地址</div>
                <div class="font-mono text-lg text-[#0F4C75]">{{ ship.ip_address || '-' }}</div>
              </div>
              <div class="bg-blue-50/50 rounded-xl p-6 border border-blue-50">
                <div class="text-sm font-medium text-slate-500 mb-2 uppercase tracking-wider">TTL 配置</div>
                <div class="text-lg text-[#0F4C75] font-medium">{{ Math.floor(ship.ttl / 60) }} 分钟</div>
              </div>
              <div class="bg-slate-50 rounded-xl p-6 border border-slate-100">
                <div class="text-sm font-medium text-slate-500 mb-2 uppercase tracking-wider">创建时间</div>
                <div class="text-slate-700">{{ formatDateTime(ship.created_at) }}</div>
              </div>
              <div class="bg-slate-50 rounded-xl p-6 border border-slate-100">
                <div class="text-sm font-medium text-slate-500 mb-2 uppercase tracking-wider">更新时间</div>
                <div class="text-slate-700">{{ formatDateTime(ship.updated_at) }}</div>
              </div>
            </div>
          </div>

          <!-- 会话标签页 -->
          <div v-else-if="activeTab === 'sessions'">
            <div v-if="sessions.length === 0" class="text-center py-16 flex flex-col items-center justify-center">
              <div class="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4 text-3xl text-slate-300">
                <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
              </div>
              <div class="text-slate-500 font-medium">暂无会话记录</div>
            </div>
            <div v-else class="overflow-hidden rounded-xl border border-blue-50">
              <table class="min-w-full divide-y divide-blue-50">
                <thead class="table-header">
                  <tr>
                    <th class="px-6 py-4 text-left">会话 ID</th>
                    <th class="px-6 py-4 text-left">状态</th>
                    <th class="px-6 py-4 text-left">创建时间</th>
                    <th class="px-6 py-4 text-left">最后活动</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-blue-50 bg-white">
                  <tr v-for="session in sessions" :key="session.id" class="hover:bg-blue-50/50 transition-colors">
                    <td class="px-6 py-4 font-mono text-sm text-[#0F4C75] font-medium">
                      <router-link
                        :to="`/sessions/${session.session_id}`"
                        class="text-[#3282B8] hover:text-[#0F4C75] hover:underline decoration-2 underline-offset-2 transition-colors"
                        :title="session.session_id"
                      >
                        {{ session.session_id.slice(0, 8) }}
                      </router-link>
                    </td>
                    <td class="px-6 py-4">
                      <span
                        :class="[
                          'inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full border',
                          session.is_active 
                            ? 'bg-green-50 text-green-700 border-green-200' 
                            : 'bg-slate-50 text-slate-600 border-slate-200'
                        ]"
                      >
                        <span class="w-1.5 h-1.5 rounded-full" :class="session.is_active ? 'bg-green-500' : 'bg-slate-400'"></span>
                        {{ session.is_active ? 'Active' : 'Inactive' }}
                      </span>
                    </td>
                    <td class="px-6 py-4 text-sm text-slate-500">{{ formatDateTime(session.created_at) }}</td>
                    <td class="px-6 py-4 text-sm text-slate-500">{{ formatDateTime(session.last_activity) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- 日志标签页 -->
          <div v-else-if="activeTab === 'logs'" class="h-full">
            <div class="bg-[#1e1e1e] rounded-xl overflow-hidden border border-slate-800 shadow-inner h-[600px] flex flex-col">
              <!-- 终端头部 -->
              <div class="flex items-center justify-between px-4 py-2 bg-[#2d2d2d] border-b border-slate-700">
                <div class="flex items-center gap-2">
                  <div class="flex gap-1.5">
                    <div class="w-3 h-3 rounded-full bg-[#ff5f56]"></div>
                    <div class="w-3 h-3 rounded-full bg-[#ffbd2e]"></div>
                    <div class="w-3 h-3 rounded-full bg-[#27c93f]"></div>
                  </div>
                  <span class="ml-3 text-xs text-slate-400 font-mono">ship-logs</span>
                </div>
                <div class="flex items-center gap-3">
                  <span class="text-xs text-slate-500 flex items-center gap-1">
                    <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                    Live
                  </span>
                  <button 
                    @click="copyToClipboard(logs)"
                    class="text-xs text-slate-400 hover:text-white transition-colors flex items-center gap-1"
                  >
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                    Copy
                  </button>
                </div>
              </div>
              
              <!-- 终端内容 -->
              <div class="flex-1 p-4 overflow-auto font-mono text-sm leading-relaxed custom-scrollbar">
                <pre v-if="logs" class="text-slate-300 whitespace-pre-wrap break-all">{{ logs }}</pre>
                <div v-else class="h-full flex flex-col items-center justify-center text-slate-600">
                  <svg class="w-12 h-12 mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
                  <p>暂无日志数据</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 删除确认弹窗 -->
    <Modal :model-value="deleteConfirmVisible" title="确认停止容器" @update:model-value="deleteConfirmVisible = false">
      <div class="flex items-start gap-4">
        <div class="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
          <svg class="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <div>
          <p class="text-slate-600 text-lg">
            确定要停止容器 <code class="font-mono bg-slate-100 px-2 py-0.5 rounded text-[#0F4C75] font-bold">{{ shortId(shipId) }}</code> 吗？
          </p>
          <p class="text-sm text-slate-500 mt-2">
            容器停止后将无法继续访问，但数据会保留。您可以随时重新启动或删除它。
          </p>
        </div>
      </div>
      <template #footer>
        <div class="flex justify-end gap-3">
          <button
            @click="deleteConfirmVisible = false"
            class="btn-secondary px-4 py-2"
          >
            取消
          </button>
          <button
            @click="handleDelete"
            :disabled="deleteLoading"
            class="btn-danger px-4 py-2 flex items-center gap-2"
          >
            <svg v-if="deleteLoading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ deleteLoading ? '处理中...' : '确认停止' }}
          </button>
        </div>
      </template>
    </Modal>

    <!-- 永久删除确认弹窗 -->
    <Modal :model-value="recycleConfirmVisible" title="确认永久删除容器" @update:model-value="recycleConfirmVisible = false">
      <div class="flex items-start gap-4">
        <div class="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
          <svg class="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </div>
        <div class="flex-1">
          <p class="text-slate-600 text-lg">
            确定要永久删除容器 <code class="font-mono bg-slate-100 px-2 py-0.5 rounded text-[#0F4C75] font-bold">{{ shortId(shipId) }}</code> 吗？
          </p>
          <p class="text-sm text-slate-500 mt-2">
            此操作将删除容器的数据库记录。
          </p>
          <!-- 关联会话列表 -->
          <div v-if="sessions.length > 0" class="mt-3 bg-red-50 p-3 rounded border border-red-100">
            <p class="text-sm text-red-600 font-medium mb-2">
              ⚠️ 以下 {{ sessions.length }} 个关联会话也将被删除：
            </p>
            <div class="flex flex-wrap gap-1">
              <code
                v-for="session in sessions"
                :key="session.session_id"
                class="font-mono text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded"
              >
                {{ session.session_id.slice(0, 8) }}
              </code>
            </div>
          </div>
          <p class="text-sm text-amber-600 mt-3 bg-amber-50 p-2 rounded border border-amber-100">
            ⚠️ 出于安全考虑，容器的挂载卷数据不会被自动清除。如需清理，请手动处理宿主机上的相关目录。
          </p>
        </div>
      </div>
      <template #footer>
        <div class="flex justify-end gap-3">
          <button
            @click="recycleConfirmVisible = false"
            class="btn-secondary px-4 py-2"
          >
            取消
          </button>
          <button
            @click="handleRecycle"
            :disabled="recycleLoading"
            class="btn-danger px-4 py-2 flex items-center gap-2"
          >
            <svg v-if="recycleLoading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ recycleLoading ? '处理中...' : '确认删除' }}
          </button>
        </div>
      </template>
    </Modal>
  </div>
</template>
