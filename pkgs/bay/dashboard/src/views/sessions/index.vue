<script setup lang="ts">
import { ref, computed } from 'vue'
import { useSessions } from './useSessions'
import { Modal } from '@/components'

const {
  filteredSessions,
  searchQuery,
  activeFilter,
  deleteConfirmId,
  deleteLoading,
  loading,
  error,
  refresh,
  handleDelete,
  shortId,
  formatDateTime,
  getRelativeTime,
} = useSessions()

const isActiveDropdownOpen = ref(false)

const activeOptions = computed(() => [
  { label: '全部状态', value: null },
  { label: '活跃 (Active)', value: true },
  { label: '非活跃 (Inactive)', value: false },
])

const currentActiveLabel = computed(() => {
  const option = activeOptions.value.find(o => o.value === activeFilter.value)
  return option ? option.label : '全部状态'
})

const selectActive = (value: any) => {
  activeFilter.value = value
  isActiveDropdownOpen.value = false
}

const closeDropdownWithDelay = () => {
  window.setTimeout(() => {
    isActiveDropdownOpen.value = false
  }, 200)
}
</script>

<template>
  <div class="space-y-8">
    <!-- 页面标题 -->
    <div class="flex flex-col sm:flex-row gap-6 justify-between items-start sm:items-center">
      <div>
        <h1 class="text-3xl font-bold text-[#0F4C75] tracking-tight">会话管理</h1>
        <p class="text-blue-400 mt-1 text-sm">监控和管理所有的用户会话连接</p>
      </div>

      <div class="flex gap-3 w-full sm:w-auto">
        <button
          @click="refresh"
          :disabled="loading"
          class="btn-secondary flex items-center justify-center gap-2 px-4 py-2.5 flex-1 sm:flex-none"
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
          刷新数据
        </button>
        <router-link
          to="/ships/create"
          class="btn-primary flex items-center justify-center gap-2 px-6 py-2.5 flex-1 sm:flex-none font-medium"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          新建工作区
        </router-link>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="card p-4 flex flex-col sm:flex-row gap-4 items-center bg-white/80 backdrop-blur-sm">
      <div class="relative flex-1 w-full">
        <div class="absolute left-3 top-1/2 -translate-y-1/2 flex items-center pointer-events-none">
          <svg class="h-5 w-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索会话 ID 或容器 ID..."
          class="input-field !pl-10"
        />
      </div>

      <div class="w-full sm:w-48 relative">
        <button
          @click="isActiveDropdownOpen = !isActiveDropdownOpen"
          @blur="closeDropdownWithDelay"
          class="input-field flex items-center justify-between cursor-pointer bg-white text-left !py-2"
        >
          <span class="truncate block text-sm">{{ currentActiveLabel }}</span>
          <svg 
            class="w-5 h-5 text-blue-400 transition-transform duration-300 flex-shrink-0" 
            :class="{ 'rotate-180': isActiveDropdownOpen }" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        <transition
          enter-active-class="transition duration-100 ease-out"
          enter-from-class="transform scale-95 opacity-0"
          enter-to-class="transform scale-100 opacity-100"
          leave-active-class="transition duration-75 ease-in"
          leave-from-class="transform scale-100 opacity-100"
          leave-to-class="transform scale-95 opacity-0"
        >
          <div 
            v-if="isActiveDropdownOpen"
            class="absolute z-20 w-full mt-2 bg-white rounded-lg shadow-xl border border-blue-100 py-1 overflow-hidden origin-top"
          >
            <div
              v-for="option in activeOptions"
              :key="option.label"
              @click="selectActive(option.value)"
              class="px-4 py-2.5 text-sm text-slate-600 hover:bg-blue-50 hover:text-[#0F4C75] cursor-pointer transition-colors flex items-center justify-between group"
              :class="{ 'bg-blue-50/50 text-[#0F4C75] font-medium': activeFilter === option.value }"
            >
              {{ option.label }}
              <svg 
                v-if="activeFilter === option.value" 
                class="w-4 h-4 text-[#3282B8]" 
                fill="none" 
                viewBox="0 0 24 24" 
                stroke="currentColor"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
            </div>
          </div>
        </transition>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-xl shadow-sm flex items-center gap-3">
      <span class="text-xl">⚠️</span>
      {{ error }}
    </div>

    <!-- 加载骨架 -->
    <div v-if="loading && filteredSessions.length === 0" class="card overflow-hidden">
      <div v-for="i in 5" :key="i" class="p-6 border-b border-blue-50 last:border-b-0 animate-pulse flex items-center gap-6">
        <div class="h-4 bg-blue-50 rounded w-24"></div>
        <div class="h-4 bg-slate-100 rounded w-32"></div>
        <div class="h-6 bg-slate-100 rounded-full w-20"></div>
        <div class="h-4 bg-slate-100 rounded w-16 ml-auto"></div>
      </div>
    </div>

    <!-- 会话列表 -->
    <div v-else-if="filteredSessions.length > 0" class="card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-blue-50">
          <thead class="table-header">
            <tr>
              <th class="px-6 py-4 text-left">会话 ID</th>
              <th class="px-6 py-4 text-left">容器 ID</th>
              <th class="px-6 py-4 text-left">状态</th>
              <th class="px-6 py-4 text-left">创建时间</th>
              <th class="px-6 py-4 text-left">最后活动</th>
              <th class="px-6 py-4 text-right">操作</th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-blue-50">
            <tr v-for="session in filteredSessions" :key="session.id" class="hover:bg-blue-50/50 transition-colors group">
              <td class="px-6 py-4 whitespace-nowrap">
                <router-link
                  :to="`/sessions/${session.session_id}`"
                  class="font-mono text-sm text-[#3282B8] hover:text-[#0F4C75] hover:underline decoration-2 underline-offset-2 transition-colors"
                  :title="session.session_id"
                >
                  {{ shortId(session.session_id) }}
                </router-link>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <router-link
                  :to="`/ships/${session.ship_id}`"
                  class="font-mono text-[#3282B8] hover:text-[#0F4C75] hover:underline decoration-2 underline-offset-2 transition-colors text-sm"
                  :title="session.ship_id"
                >
                  {{ shortId(session.ship_id) }}
                </router-link>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
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
              <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                {{ formatDateTime(session.created_at) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                {{ getRelativeTime(session.last_activity) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                <button
                  @click="deleteConfirmId = session.session_id"
                  class="inline-flex items-center px-3 py-1.5 rounded-lg text-red-600 bg-red-50 hover:bg-red-100 transition-colors"
                >
                  删除
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="card p-16 text-center flex flex-col items-center justify-center">
      <div class="w-24 h-24 bg-blue-50 rounded-full flex items-center justify-center mb-6 text-5xl animate-bounce-slow">
        💬
      </div>
      <h3 class="text-xl font-bold text-[#0F4C75] mb-2">暂无会话记录</h3>
      <p class="text-slate-500 mb-8 max-w-md mx-auto">
        当前没有活动的会话连接。新建工作区来开始您的工作吧。
      </p>
      <router-link
        to="/ships/create"
        class="btn-primary px-8 py-3 flex items-center gap-2 text-lg"
      >
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        新建工作区
      </router-link>
    </div>

    <!-- 删除确认弹窗 -->
    <Modal :model-value="!!deleteConfirmId" title="确认删除会话" @update:model-value="deleteConfirmId = null">
      <div class="flex items-start gap-4">
        <div class="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
          <svg class="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </div>
        <div>
          <p class="text-slate-600 text-lg">
            确定要删除会话 <code class="font-mono bg-slate-100 px-2 py-0.5 rounded text-[#0F4C75] font-bold">{{ shortId(deleteConfirmId || '') }}</code> 吗？
          </p>
          <p class="text-sm text-slate-500 mt-2">
            删除后会话记录将永久移除，无法恢复。这可能会导致正在进行的用户连接中断。
          </p>
        </div>
      </div>
      <template #footer>
        <div class="flex justify-end gap-3">
          <button
            @click="deleteConfirmId = null"
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
