<script setup lang="ts">
import { ref, computed, shallowRef } from 'vue'
import { useSessionDetail } from './useSessionDetail'
import { Modal, TTLCountdown, XtermTerminal } from '@/components'
import { formatDateTime } from '@/utils/time'
import { useSettingsStore } from '@/stores/settings'
import { VueMonacoEditor } from '@guolao/vue-monaco-editor'

const settingsStore = useSettingsStore()

const {
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
  pythonCode,
  pythonOutput,
  pythonLoading,
  runPython,
  clearPythonOutput,
} = useSessionDetail()

const MONACO_EDITOR_OPTIONS = {
  automaticLayout: true,
  formatOnType: true,
  formatOnPaste: true,
  minimap: { enabled: false },
  fontSize: 14,
  scrollBeyondLastLine: false,
  theme: 'vs-dark',
}

const editorRef = shallowRef()
const handleMount = (editor: any) => {
  editorRef.value = editor
}

// Terminal props computed from session
const terminalToken = computed(() => settingsStore.token)
const terminalShipId = computed(() => session.value?.ship_id || '')
const terminalSessionId = computed(() => session.value?.session_id || '')

// Terminal connection status
const terminalConnected = ref(false)

const onTerminalConnected = () => {
  terminalConnected.value = true
}

const onTerminalDisconnected = () => {
  terminalConnected.value = false
}

const onTerminalError = (error: string) => {
  console.error('Terminal error:', error)
}
</script>

<template>
  <div class="space-y-8">
    <!-- 面包屑导航 -->
    <nav class="flex items-center space-x-2 text-sm text-slate-500">
      <router-link to="/sessions" class="hover:text-[#3282B8] transition-colors flex items-center gap-1">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
        会话列表
      </router-link>
      <span class="text-slate-300">/</span>
      <span class="text-[#0F4C75] font-medium font-mono">{{ shortId(sessionId) }}</span>
    </nav>

    <!-- 加载状态 -->
    <div v-if="loading && !session" class="card p-8 animate-pulse">
      <div class="h-8 bg-blue-50 rounded w-1/4 mb-6"></div>
      <div class="h-4 bg-slate-100 rounded w-1/2 mb-3"></div>
      <div class="h-4 bg-slate-100 rounded w-1/3"></div>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error && !session" class="bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-xl shadow-sm flex items-center gap-3">
      <span class="text-xl">⚠️</span>
      <div>
        {{ error }}
        <button @click="refresh" class="ml-2 underline hover:text-red-800 font-medium">重试</button>
      </div>
    </div>

    <!-- 会话详情 -->
    <template v-else-if="session">
      <!-- 顶部信息卡片 -->
      <div class="card p-8 relative overflow-hidden">
        <div class="absolute top-0 right-0 p-8 opacity-5 pointer-events-none">
          <svg class="w-56 h-56 text-[#0F4C75]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="0.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </div>

        <div class="relative z-10 flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
          <!-- 左侧：基本信息 -->
          <div class="flex items-start gap-6">
            <div class="w-20 h-20 rounded-2xl bg-gradient-to-br from-[#0F4C75] to-[#3282B8] flex items-center justify-center shadow-lg shadow-blue-200 text-white">
              <svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
            </div>
            <div>
              <h1 class="text-3xl font-bold text-[#0F4C75] font-mono flex items-center gap-4 mb-2">
                {{ session.session_id }}
                <span
                  :class="[
                    'inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-full border',
                    isActive
                      ? 'bg-green-50 text-green-700 border-green-200'
                      : 'bg-slate-50 text-slate-600 border-slate-200'
                  ]"
                >
                  <span class="w-1.5 h-1.5 rounded-full" :class="isActive ? 'bg-green-500' : 'bg-slate-400'"></span>
                  {{ isActive ? 'Active' : 'Inactive' }}
                </span>
              </h1>
              <div class="flex flex-wrap items-center gap-6 text-slate-500 text-sm">
                <span class="flex items-center gap-1.5">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                  创建于 {{ formatDateTime(session.created_at) }}
                </span>
                <router-link
                  :to="`/ships/${session.ship_id}`"
                  class="flex items-center gap-1.5 font-mono text-[#3282B8] bg-blue-50 px-2 py-0.5 rounded hover:text-[#0F4C75]"
                  :title="session.ship_id"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" /></svg>
                  {{ shortId(session.ship_id) }}
                </router-link>
              </div>
            </div>
          </div>

          <!-- 右侧：操作按钮 -->
          <div class="flex flex-wrap gap-3">
            <button
              v-if="!isActive"
              @click="handleStart"
              :disabled="startLoading"
              class="btn-primary px-4 py-2 flex items-center gap-2"
            >
              <svg
                v-if="startLoading"
                class="w-4 h-4 animate-spin"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              启动容器
            </button>
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
            <button
              @click="deleteConfirmVisible = true"
              class="btn-danger px-4 py-2 flex items-center gap-2"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
              删除会话
            </button>
          </div>
        </div>

        <!-- TTL 倒计时 -->
        <div v-if="session.expires_at" class="mt-8 pt-6 border-t border-blue-50 flex items-center gap-4">
          <div class="text-sm font-medium text-slate-500 uppercase tracking-wider">剩余时间</div>
          <TTLCountdown :expires-at="session.expires_at" show-label class="text-2xl font-mono font-bold text-[#3282B8]" />
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
              <span v-else-if="tab.name === 'terminal'">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
              </span>
              <span v-else-if="tab.name === 'python'">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" /></svg>
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
                <div class="text-sm font-medium text-slate-500 mb-2 uppercase tracking-wider">会话 ID</div>
                <div class="flex items-center gap-2">
                  <div class="font-mono text-lg text-[#0F4C75] truncate flex-1" :title="session.session_id">{{ session.session_id }}</div>
                  <button
                    @click="copyToClipboard(session.session_id)"
                    class="flex-shrink-0 p-1.5 text-slate-400 hover:text-[#3282B8] hover:bg-blue-100 rounded-md transition-colors"
                    title="复制会话 ID"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  </button>
                </div>
              </div>
              <div class="bg-blue-50/50 rounded-xl p-6 border border-blue-50">
                <div class="text-sm font-medium text-slate-500 mb-2 uppercase tracking-wider">容器 ID</div>
                <div class="flex items-center gap-2">
                  <router-link
                    :to="`/ships/${session.ship_id}`"
                    class="font-mono text-lg text-[#0F4C75] truncate flex-1 hover:text-[#0F4C75]"
                    :title="session.ship_id"
                  >
                    {{ session.ship_id }}
                  </router-link>
                  <button
                    @click="copyToClipboard(session.ship_id)"
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
                <div class="text-sm font-medium text-slate-500 mb-2 uppercase tracking-wider">会话状态</div>
                <div class="text-lg text-[#0F4C75] font-medium">
                  {{ isActive ? 'Active' : 'Inactive' }}
                </div>
              </div>
              <div class="bg-blue-50/50 rounded-xl p-6 border border-blue-50">
                <div class="text-sm font-medium text-slate-500 mb-2 uppercase tracking-wider">初始 TTL</div>
                <div class="text-lg text-[#0F4C75] font-medium">{{ Math.floor(session.initial_ttl / 60) }} 分钟</div>
              </div>
              <div class="bg-slate-50 rounded-xl p-6 border border-slate-100">
                <div class="text-sm font-medium text-slate-500 mb-2 uppercase tracking-wider">创建时间</div>
                <div class="text-slate-700">{{ formatDateTime(session.created_at) }}</div>
              </div>
              <div class="bg-slate-50 rounded-xl p-6 border border-slate-100">
                <div class="text-sm font-medium text-slate-500 mb-2 uppercase tracking-wider">最后活动</div>
                <div class="text-slate-700">{{ formatDateTime(session.last_activity) }}</div>
              </div>
              <div class="bg-slate-50 rounded-xl p-6 border border-slate-100">
                <div class="text-sm font-medium text-slate-500 mb-2 uppercase tracking-wider">过期时间</div>
                <div class="text-slate-700">{{ formatDateTime(session.expires_at) }}</div>
              </div>
            </div>
          </div>

          <!-- 终端标签页 -->
          <div
            v-else-if="activeTab === 'terminal'"
            class="h-[600px] rounded-lg overflow-hidden border border-slate-800 shadow-inner"
          >
            <XtermTerminal
              v-if="terminalShipId && terminalSessionId && terminalToken"
              :ship-id="terminalShipId"
              :session-id="terminalSessionId"
              :token="terminalToken"
              @connected="onTerminalConnected"
              @disconnected="onTerminalDisconnected"
              @error="onTerminalError"
            />
            <div v-else class="h-full bg-[#1e1e1e] flex items-center justify-center text-slate-500">
              <div class="text-center">
                <svg class="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <p>等待会话信息加载...</p>
              </div>
            </div>
          </div>

          <!-- Python 标签页 -->
          <div v-else-if="activeTab === 'python'" class="h-full">
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 h-[600px]">
              <!-- 编辑器区域 -->
              <div class="bg-[#1e1e1e] rounded-xl overflow-hidden border border-slate-800 shadow-inner flex flex-col">
                <div class="flex items-center justify-between px-4 py-2 bg-[#2d2d2d] border-b border-slate-700">
                  <span class="text-xs text-slate-400 font-mono">script.py</span>
                  <button
                    @click="runPython"
                    :disabled="pythonLoading"
                    class="text-xs bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-3 py-1 rounded transition-colors flex items-center gap-1"
                  >
                    <svg v-if="pythonLoading" class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <svg v-else class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    {{ pythonLoading ? '运行中...' : '运行' }}
                  </button>
                </div>
                <div class="flex-1 bg-[#1e1e1e] overflow-hidden">
                  <VueMonacoEditor
                    v-model:value="pythonCode"
                    language="python"
                    theme="vs-dark"
                    :options="MONACO_EDITOR_OPTIONS"
                    @mount="handleMount"
                    class="h-full w-full"
                  />
                </div>
              </div>

              <!-- 输出区域 -->
              <div class="bg-[#1e1e1e] rounded-xl overflow-hidden border border-slate-800 shadow-inner flex flex-col">
                <div class="flex items-center justify-between px-4 py-2 bg-[#2d2d2d] border-b border-slate-700">
                  <span class="text-xs text-slate-400 font-mono">Output</span>
                  <button
                    @click="clearPythonOutput"
                    class="text-xs text-slate-400 hover:text-white transition-colors"
                  >
                    清除
                  </button>
                </div>
                <div class="flex-1 p-4 font-mono text-sm text-slate-300 overflow-auto custom-scrollbar space-y-2">
                  <template v-if="pythonOutput.length > 0">
                    <div v-for="(item, index) in pythonOutput" :key="index" class="break-words whitespace-pre-wrap">
                      <div v-if="item.type === 'text'" class="text-slate-300">{{ item.content }}</div>
                      <div v-else-if="item.type === 'image'" class="my-2">
                        <img :src="`data:image/png;base64,${item.content}`" alt="Output Image" class="max-w-full rounded border border-slate-700" />
                      </div>
                      <div v-else-if="item.type === 'error'" class="text-red-400 bg-red-900/20 p-2 rounded border border-red-900/50">
                        {{ item.content }}
                      </div>
                    </div>
                  </template>
                  <div v-else class="opacity-50 italic text-slate-500">等待执行...</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 删除确认弹窗 -->
    <Modal :model-value="deleteConfirmVisible" title="确认删除会话" @update:model-value="deleteConfirmVisible = false">
      <div class="flex items-start gap-4">
        <div class="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
          <svg class="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </div>
        <div>
          <p class="text-slate-600 text-lg">
            确定要删除会话 <code class="font-mono bg-slate-100 px-2 py-0.5 rounded text-[#0F4C75] font-bold">{{ shortId(sessionId) }}</code> 吗？
          </p>
          <p class="text-sm text-slate-500 mt-2">
            删除后会话记录将永久移除，无法恢复。这可能会导致正在进行的用户连接中断。
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
            {{ deleteLoading ? '处理中...' : '确认删除' }}
          </button>
        </div>
      </template>
    </Modal>
  </div>
</template>
