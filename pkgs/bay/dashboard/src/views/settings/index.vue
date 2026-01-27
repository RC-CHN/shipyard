<script setup lang="ts">
import { useSettings } from './useSettings'

const {
  token,
  refreshInterval,
  showToken,
  refreshIntervalPresets,
  hasChanges,
  isValid,
  handleSave,
  handleReset,
  handleClearToken,
  handleResetAll,
  toggleShowToken,
} = useSettings()
</script>

<template>
  <div class="max-w-2xl mx-auto space-y-8">
    <!-- 页面标题 -->
    <div class="flex flex-col sm:flex-row gap-6 justify-between items-start sm:items-center">
      <div>
        <h1 class="text-3xl font-bold text-[#0F4C75] tracking-tight">系统设置</h1>
        <p class="text-blue-400 mt-1 text-sm">配置系统参数和个性化选项</p>
      </div>
    </div>

    <!-- 认证配置 -->
    <div class="card overflow-hidden">
      <div class="px-8 py-6 border-b border-blue-50 bg-slate-50/50 flex items-center gap-4">
        <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center text-blue-600 shadow-sm">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" /></svg>
        </div>
        <h2 class="text-lg font-bold text-[#0F4C75]">认证配置</h2>
      </div>
      
      <div class="p-8 space-y-6">
        <!-- Token -->
        <div class="space-y-2">
          <label class="block text-sm font-medium text-slate-700">Access Token</label>
          <div class="relative">
            <input
              v-model="token"
              :type="showToken ? 'text' : 'password'"
              placeholder="输入 API Token"
              class="w-full px-4 py-2 pr-24 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-100 focus:border-[#3282B8] outline-none transition-all"
            />
            <div class="absolute inset-y-0 right-0 flex items-center pr-2 gap-1">
              <button
                type="button"
                @click="toggleShowToken"
                class="p-1.5 text-slate-400 hover:text-[#3282B8] transition-colors rounded-md hover:bg-blue-50"
                :title="showToken ? '隐藏' : '显示'"
              >
                <svg v-if="showToken" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                </svg>
                <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
              </button>
              <button
                v-if="token"
                type="button"
                @click="handleClearToken"
                class="p-1.5 text-slate-400 hover:text-red-600 transition-colors rounded-md hover:bg-red-50"
                title="清除 Token (退出登录)"
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
              </button>
            </div>
          </div>
          <p class="text-slate-400 text-xs mt-1">用于认证 API 请求的安全令牌，清除后将退出登录</p>
        </div>
      </div>
    </div>

    <!-- 界面配置 -->
    <div class="card overflow-hidden">
      <div class="px-8 py-6 border-b border-blue-50 bg-slate-50/50 flex items-center gap-4">
        <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center text-blue-600 shadow-sm">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
        </div>
        <h2 class="text-lg font-bold text-[#0F4C75]">界面配置</h2>
      </div>
      
      <div class="p-8 space-y-6">
        <!-- 刷新间隔 -->
        <div class="space-y-4">
          <label class="block text-sm font-medium text-slate-700">自动刷新间隔</label>
          <div class="flex flex-wrap gap-3">
            <button
              v-for="preset in refreshIntervalPresets"
              :key="preset.value"
              type="button"
              @click="refreshInterval = preset.value"
              :class="[
                'px-4 py-2 text-sm font-medium rounded-lg border transition-all duration-200 shadow-sm hover:shadow',
                refreshInterval === preset.value
                  ? 'bg-[#3282B8] text-white border-[#3282B8] transform scale-105'
                  : 'bg-white text-slate-600 border-slate-200 hover:border-blue-300 hover:text-[#3282B8]'
              ]"
            >
              {{ preset.label }}
            </button>
          </div>
          <p class="text-slate-400 text-xs mt-1">设置仪表盘数据自动刷新的时间间隔</p>
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="flex justify-between items-center pt-4">
      <button
        type="button"
        @click="handleResetAll"
        class="text-slate-500 hover:text-[#3282B8] transition-colors text-sm font-medium flex items-center gap-1"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
        恢复默认设置
      </button>
      <div class="flex gap-4">
        <button
          type="button"
          @click="handleReset"
          :disabled="!hasChanges"
          class="btn-secondary px-6 py-2.5"
        >
          撤销更改
        </button>
        <button
          type="button"
          @click="handleSave"
          :disabled="!hasChanges || !isValid"
          class="btn-primary px-8 py-2.5 shadow-lg shadow-blue-200"
        >
          保存设置
        </button>
      </div>
    </div>
  </div>
</template>
