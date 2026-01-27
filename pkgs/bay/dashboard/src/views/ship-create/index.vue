<script setup lang="ts">
import { useCreateShip } from './useCreateShip'

const {
  createMode,
  ttlMinutes,
  maxSessionNum,
  cpus,
  memory,
  disk,
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
      <router-link to="/sessions" class="hover:text-[#3282B8] transition-colors flex items-center gap-1">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
        会话管理
      </router-link>
      <span class="text-slate-300">/</span>
      <span class="text-[#0F4C75] font-medium font-mono">新建工作区</span>
    </nav>

    <!-- 表单卡片 -->
    <div class="card overflow-hidden">
      <div class="px-8 py-6 border-b border-blue-50 bg-slate-50/50 flex items-center gap-4">
        <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center text-blue-600 shadow-sm">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" /></svg>
        </div>
        <div>
          <h1 class="text-2xl font-bold text-[#0F4C75]">新建工作区</h1>
          <p class="text-sm text-slate-500 mt-1">配置并获取一个工作环境</p>
        </div>
      </div>

      <form @submit.prevent="handleSubmit" class="p-8 space-y-8">
        <!-- 模式选择器 -->
        <div class="space-y-4">
          <label class="block text-sm font-semibold text-[#0F4C75] uppercase tracking-wider">
            创建模式
          </label>
          <div class="grid grid-cols-2 gap-4">
            <!-- 快速模式 -->
            <button
              type="button"
              @click="createMode = 'quick'"
              :class="[
                'relative p-4 rounded-xl border-2 transition-all duration-200 text-left',
                createMode === 'quick'
                  ? 'border-[#3282B8] bg-blue-50/50 shadow-md'
                  : 'border-slate-200 hover:border-blue-200 hover:bg-slate-50'
              ]"
            >
              <div class="flex items-start gap-3">
                <div :class="[
                  'w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0',
                  createMode === 'quick' ? 'bg-[#3282B8] text-white' : 'bg-slate-100 text-slate-500'
                ]">
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <div>
                  <h3 :class="['font-semibold', createMode === 'quick' ? 'text-[#0F4C75]' : 'text-slate-700']">
                    快速模式
                  </h3>
                  <p class="text-sm text-slate-500 mt-1">系统自动分配可用容器或创建新容器</p>
                </div>
              </div>
              <div v-if="createMode === 'quick'" class="absolute top-2 right-2">
                <svg class="w-5 h-5 text-[#3282B8]" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                </svg>
              </div>
            </button>

            <!-- 自定义模式 -->
            <button
              type="button"
              @click="createMode = 'custom'"
              :class="[
                'relative p-4 rounded-xl border-2 transition-all duration-200 text-left',
                createMode === 'custom'
                  ? 'border-[#3282B8] bg-blue-50/50 shadow-md'
                  : 'border-slate-200 hover:border-blue-200 hover:bg-slate-50'
              ]"
            >
              <div class="flex items-start gap-3">
                <div :class="[
                  'w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0',
                  createMode === 'custom' ? 'bg-[#3282B8] text-white' : 'bg-slate-100 text-slate-500'
                ]">
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
                <div>
                  <h3 :class="['font-semibold', createMode === 'custom' ? 'text-[#0F4C75]' : 'text-slate-700']">
                    自定义模式
                  </h3>
                  <p class="text-sm text-slate-500 mt-1">自定义配置并强制创建新容器</p>
                </div>
              </div>
              <div v-if="createMode === 'custom'" class="absolute top-2 right-2">
                <svg class="w-5 h-5 text-[#3282B8]" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                </svg>
              </div>
            </button>
          </div>
        </div>

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

        <!-- 自定义模式下的高级配置 -->
        <div v-if="createMode === 'custom'" class="space-y-6">
          <!-- 说明文字 -->
          <div class="bg-green-50 border border-green-100 rounded-lg p-4 flex items-start gap-3">
            <svg class="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div class="text-sm text-green-700">
              <p class="font-medium">自定义模式：您的配置将被完整应用</p>
              <p class="mt-1 text-green-600">系统将跳过容器复用逻辑，直接创建一个符合您配置要求的新容器。</p>
            </div>
          </div>

          <!-- 最大会话数 -->
          <div class="bg-slate-50 rounded-xl p-6 border border-slate-100">
            <label class="block text-sm font-semibold text-[#0F4C75] uppercase tracking-wider mb-4">
              最大会话数
            </label>
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

          <!-- 资源配置 -->
          <div class="bg-slate-50 rounded-xl p-6 border border-slate-100">
            <label class="block text-sm font-semibold text-[#0F4C75] uppercase tracking-wider mb-4">
              资源限制
            </label>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
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
          </div>
        </div>

        <!-- 快速模式提示 -->
        <div v-else class="bg-blue-50 border border-blue-100 rounded-lg p-4 flex items-start gap-3">
          <svg class="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div class="text-sm text-blue-700">
            <p class="font-medium">快速模式：系统自动优化资源分配</p>
            <p class="mt-1 text-blue-600">系统会尝试分配已有的可用容器给您使用，如果没有可用容器则会自动创建新容器。</p>
          </div>
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
            {{ submitting ? '创建中...' : '立即开始' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
