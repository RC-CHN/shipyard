<script setup lang="ts">
import { ref, computed } from 'vue'
import { useShips } from './useShips'
import { StatusBadge, TTLCountdown, Modal } from '@/components'

const {
  filteredShips,
  searchQuery,
  statusFilter,
  deleteConfirmId,
  deleteLoading,
  loading,
  error,
  refresh,
  handleDelete,
  shortId,
  ShipStatus,
} = useShips()

const isStatusDropdownOpen = ref(false)

const statusOptions = computed(() => [
  { label: '全部状态', value: null },
  { label: '运行中 (Running)', value: ShipStatus.RUNNING },
  { label: '已停止 (Stopped)', value: ShipStatus.STOPPED },
  { label: '创建中 (Creating)', value: ShipStatus.CREATING },
])

const currentStatusLabel = computed(() => {
  const option = statusOptions.value.find(o => o.value === statusFilter.value)
  return option ? option.label : '全部状态'
})

const selectStatus = (value: any) => {
  statusFilter.value = value
  isStatusDropdownOpen.value = false
}

const closeDropdownWithDelay = () => {
  window.setTimeout(() => {
    isStatusDropdownOpen.value = false
  }, 200)
}
</script>

<template>
  <div class="space-y-8">
    <!-- 顶部操作栏 -->
    <div class="flex flex-col sm:flex-row gap-6 justify-between items-start sm:items-center">
      <div>
        <h2 class="text-3xl font-bold text-[#0F4C75] tracking-tight">容器管理</h2>
        <p class="text-blue-400 mt-1 text-sm">管理和监控您的所有容器实例</p>
      </div>

      <!-- 操作按钮 -->
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
          刷新
        </button>
        <router-link
          to="/ships/create"
          class="btn-primary flex items-center justify-center gap-2 px-6 py-2.5 flex-1 sm:flex-none font-medium"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          新建容器
        </router-link>
      </div>
    </div>

    <!-- 搜索和筛选 -->
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
          placeholder="搜索容器 ID 或 IP 地址..."
          class="input-field !pl-10"
        />
      </div>
      <div class="w-full sm:w-48 relative">
        <button
          @click="isStatusDropdownOpen = !isStatusDropdownOpen"
          @blur="closeDropdownWithDelay"
          class="input-field flex items-center justify-between cursor-pointer bg-white text-left !py-2"
        >
          <span class="truncate block text-sm">{{ currentStatusLabel }}</span>
          <svg
            class="w-5 h-5 text-blue-400 transition-transform duration-300 flex-shrink-0"
            :class="{ 'rotate-180': isStatusDropdownOpen }"
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
            v-if="isStatusDropdownOpen"
            class="absolute z-20 w-full mt-2 bg-white rounded-lg shadow-xl border border-blue-100 py-1 overflow-hidden origin-top"
          >
            <div
              v-for="option in statusOptions"
              :key="option.label"
              @click="selectStatus(option.value)"
              class="px-4 py-2.5 text-sm text-slate-600 hover:bg-blue-50 hover:text-[#0F4C75] cursor-pointer transition-colors flex items-center justify-between group"
              :class="{ 'bg-blue-50/50 text-[#0F4C75] font-medium': statusFilter === option.value }"
            >
              {{ option.label }}
              <svg
                v-if="statusFilter === option.value"
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
    <div v-if="loading && filteredShips.length === 0" class="card overflow-hidden">
      <div v-for="i in 5" :key="i" class="p-6 border-b border-blue-50 last:border-b-0 animate-pulse flex items-center gap-6">
        <div class="h-4 bg-blue-50 rounded w-24"></div>
        <div class="h-4 bg-slate-100 rounded w-32"></div>
        <div class="h-6 bg-slate-100 rounded-full w-20"></div>
        <div class="h-4 bg-slate-100 rounded w-16 ml-auto"></div>
      </div>
    </div>

    <!-- 容器列表 -->
    <div v-else-if="filteredShips.length > 0" class="card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-blue-50">
          <thead class="table-header">
            <tr>
              <th class="px-6 py-4 text-left">ID</th>
              <th class="px-6 py-4 text-left">IP 地址</th>
              <th class="px-6 py-4 text-left">状态</th>
              <th class="px-6 py-4 text-left">会话数</th>
              <th class="px-6 py-4 text-left">剩余时间 (TTL)</th>
              <th class="px-6 py-4 text-right">操作</th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-blue-50">
            <tr v-for="ship in filteredShips" :key="ship.id" class="hover:bg-blue-50/50 transition-colors group">
              <td class="px-6 py-4 whitespace-nowrap">
                <router-link
                  :to="`/ships/${ship.id}`"
                  class="font-mono text-[#3282B8] font-medium hover:text-[#0F4C75] hover:underline decoration-2 underline-offset-2 transition-colors"
                  :title="ship.id"
                >
                  {{ shortId(ship.id) }}
                </router-link>
              </td>
              <td class="px-6 py-4 whitespace-nowrap font-mono text-sm text-slate-600">
                {{ ship.ip_address || '-' }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <StatusBadge :status="ship.status" size="sm" />
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-600">
                <div class="flex items-center gap-2">
                  <span class="font-medium" :class="ship.current_session_num > 0 ? 'text-[#3282B8]' : 'text-slate-400'">
                    {{ ship.current_session_num }}
                  </span>
                  <span class="text-slate-300">/</span>
                  <span class="text-slate-400">{{ ship.max_session_num }}</span>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <TTLCountdown
                  v-if="ship.status === ShipStatus.RUNNING"
                  :expires-at="ship.expires_at"
                  :show-label="false"
                  class="text-sm font-mono"
                />
                <span v-else class="text-slate-300">-</span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                <router-link
                  :to="`/ships/${ship.id}`"
                  class="inline-flex items-center px-3 py-1.5 rounded-lg text-[#3282B8] bg-blue-50 hover:bg-blue-100 transition-colors"
                >
                  详情
                </router-link>
                <button
                  v-if="ship.status === ShipStatus.RUNNING"
                  @click="deleteConfirmId = ship.id"
                  class="inline-flex items-center px-3 py-1.5 rounded-lg text-red-600 bg-red-50 hover:bg-red-100 transition-colors"
                >
                  停止
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
        🚢
      </div>
      <h3 class="text-xl font-bold text-[#0F4C75] mb-2">暂无容器实例</h3>
      <p class="text-slate-500 mb-8 max-w-md mx-auto">
        您还没有创建任何容器。开始创建一个新的容器来运行您的应用吧。
      </p>
      <router-link
        to="/ships/create"
        class="btn-primary px-8 py-3 flex items-center gap-2 text-lg"
      >
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        创建第一个容器
      </router-link>
    </div>

    <!-- 删除确认弹窗 -->
    <Modal :model-value="!!deleteConfirmId" title="确认停止容器" @update:model-value="deleteConfirmId = null">
      <div class="flex items-start gap-4">
        <div class="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
          <svg class="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <div>
          <p class="text-slate-600 text-lg">
            确定要停止容器 <code class="font-mono bg-slate-100 px-2 py-0.5 rounded text-[#0F4C75] font-bold">{{ shortId(deleteConfirmId || '') }}</code> 吗？
          </p>
          <p class="text-sm text-slate-500 mt-2">
            容器停止后将无法继续访问，但数据会保留。您可以随时重新启动或删除它。
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
            {{ deleteLoading ? '处理中...' : '确认停止' }}
          </button>
        </div>
      </template>
    </Modal>
  </div>
</template>
