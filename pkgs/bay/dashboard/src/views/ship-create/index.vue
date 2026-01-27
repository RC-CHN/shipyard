<script setup lang="ts">
import { useCreateShip } from './useCreateShip'

const {
  ttlMinutes,
  maxSessionNum,
  cpus,
  memory,
  disk,
  showAdvanced,
  submitting,
  ttlPresets,
  errors,
  isValid,
  handleSubmit,
  handleCancel,
} = useCreateShip()
</script>

<template>
  <div class="max-w-2xl mx-auto space-y-8">
    <!-- 面包屑导航 -->
    <nav class="flex items-center space-x-2 text-sm text-slate-500">
      <router-link to="/ships" class="hover:text-[#3282B8] transition-colors flex items-center gap-1">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
        容器列表
      </router-link>
      <span class="text-slate-300">/</span>
      <span class="text-[#0F4C75] font-medium font-mono">创建容器</span>
    </nav>

    <!-- 表单卡片 -->
    <div class="card overflow-hidden">
      <div class="px-8 py-6 border-b border-blue-50 bg-slate-50/50 flex items-center gap-4">
        <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center text-blue-600 shadow-sm">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" /></svg>
        </div>
        <div>
          <h1 class="text-2xl font-bold text-[#0F4C75]">创建新容器</h1>
          <p class="text-sm text-slate-500 mt-1">配置并启动一个新的容器实例以运行您的应用</p>
        </div>
      </div>

      <form @submit.prevent="handleSubmit" class="p-8 space-y-8">
        <!-- TTL 配置 -->
        <div class="space-y-4">
          <label class="block text-sm font-semibold text-[#0F4C75] uppercase tracking-wider">
            生存时间 (TTL)
          </label>
          <div class="bg-blue-50/50 rounded-xl p-6 border border-blue-50">
            <div class="flex flex-wrap gap-3 mb-6">
              <button
                v-for="preset in ttlPresets"
                :key="preset.value"
                type="button"
                @click="ttlMinutes = preset.value"
                :class="[
                  'px-4 py-2 text-sm font-medium rounded-lg border transition-all duration-200 shadow-sm hover:shadow',
                  ttlMinutes === preset.value
                    ? 'bg-[#3282B8] text-white border-[#3282B8] transform scale-105'
                    : 'bg-white text-slate-600 border-slate-200 hover:border-blue-300 hover:text-[#3282B8]'
                ]"
              >
                {{ preset.label }}
              </button>
            </div>
            <div class="flex items-center gap-4">
              <div class="relative w-32">
                <input
                  v-model.number="ttlMinutes"
                  type="number"
                  min="1"
                  max="10080"
                  class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-100 focus:border-[#3282B8] outline-none transition-all text-center font-mono text-lg"
                />
              </div>
              <span class="text-slate-500 font-medium">分钟</span>
            </div>
            <p v-if="errors.ttl" class="text-red-500 text-sm mt-2 flex items-center gap-1">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              {{ errors.ttl }}
            </p>
          </div>
        </div>

        <!-- 最大会话数 -->
        <div class="space-y-4">
          <label class="block text-sm font-semibold text-[#0F4C75] uppercase tracking-wider">
            最大会话数
          </label>
          <div class="bg-slate-50 rounded-xl p-6 border border-slate-100">
            <div class="flex items-center gap-6">
              <div class="relative w-32">
                <input
                  v-model.number="maxSessionNum"
                  type="number"
                  min="1"
                  max="10"
                  class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-100 focus:border-[#3282B8] outline-none transition-all text-center font-mono text-lg"
                />
              </div>
              <p class="text-slate-500 text-sm flex-1">单个容器可以同时承载的最大并发会话连接数</p>
            </div>
            <p v-if="errors.maxSessionNum" class="text-red-500 text-sm mt-2 flex items-center gap-1">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              {{ errors.maxSessionNum }}
            </p>
          </div>
        </div>

        <!-- 高级配置折叠 -->
        <div class="border-t border-slate-100 pt-6">
          <button
            type="button"
            @click="showAdvanced = !showAdvanced"
            class="flex items-center gap-2 text-slate-500 hover:text-[#3282B8] transition-colors font-medium"
          >
            <svg 
              class="w-5 h-5 transition-transform duration-300" 
              :class="{ 'rotate-90': showAdvanced }"
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
            高级资源配置
          </button>

          <transition
            enter-active-class="transition duration-200 ease-out"
            enter-from-class="transform scale-y-95 opacity-0"
            enter-to-class="transform scale-y-100 opacity-100"
            leave-active-class="transition duration-150 ease-in"
            leave-from-class="transform scale-y-100 opacity-100"
            leave-to-class="transform scale-y-95 opacity-0"
          >
            <div v-if="showAdvanced" class="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6 bg-slate-50 rounded-xl p-6 border border-slate-100">
              <!-- CPU -->
              <div class="space-y-2">
                <label class="block text-sm font-medium text-slate-700">CPU 核心数</label>
                <div class="relative">
                  <input
                    v-model.number="cpus"
                    type="number"
                    min="0.1"
                    max="8"
                    step="0.1"
                    placeholder="默认"
                    class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-100 focus:border-[#3282B8] outline-none transition-all"
                  />
                  <div class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">Core</div>
                </div>
              </div>

              <!-- 内存 -->
              <div class="space-y-2">
                <label class="block text-sm font-medium text-slate-700">内存限制</label>
                <input
                  v-model="memory"
                  type="text"
                  placeholder="例如：512m, 1g"
                  class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-100 focus:border-[#3282B8] outline-none transition-all"
                />
                <p v-if="errors.memory" class="text-red-500 text-xs mt-1">{{ errors.memory }}</p>
              </div>

              <!-- 磁盘 -->
              <div class="space-y-2">
                <label class="block text-sm font-medium text-slate-700">磁盘空间</label>
                <input
                  v-model="disk"
                  type="text"
                  placeholder="例如：1Gi, 10G"
                  class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-100 focus:border-[#3282B8] outline-none transition-all"
                />
                <p v-if="errors.disk" class="text-red-500 text-xs mt-1">{{ errors.disk }}</p>
              </div>
            </div>
          </transition>
        </div>

        <!-- 操作按钮 -->
        <div class="flex justify-end gap-4 pt-6 border-t border-slate-100">
          <button
            type="button"
            @click="handleCancel"
            class="btn-secondary px-6 py-2.5"
          >
            取消
          </button>
          <button
            type="submit"
            :disabled="!isValid || submitting"
            class="btn-primary px-8 py-2.5 flex items-center gap-2 font-medium shadow-lg shadow-blue-200"
          >
            <svg v-if="submitting" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" /></svg>
            {{ submitting ? '创建中...' : '立即创建' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
