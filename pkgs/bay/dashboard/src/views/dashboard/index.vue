<script setup lang="ts">
import { useDashboard } from './useDashboard'

const { overview, loading, error, refresh } = useDashboard()
</script>

<template>
  <div class="space-y-8">
    <!-- 顶部操作栏 -->
    <div class="flex justify-between items-center">
      <div>
        <h2 class="text-3xl font-bold text-[#0F4C75] tracking-tight">系统概览</h2>
        <p class="text-blue-400 mt-1 text-sm">欢迎回到 Bay 控制面板</p>
      </div>
      <button
        @click="refresh"
        :disabled="loading"
        class="group flex items-center gap-2 px-4 py-2 text-[#3282B8] bg-white border border-blue-100 hover:border-[#3282B8] hover:bg-blue-50 rounded-xl transition-all duration-300 shadow-sm hover:shadow-md"
      >
        <svg 
          class="w-4 h-4 transition-transform duration-500 group-hover:rotate-180" 
          :class="{ 'animate-spin': loading }"
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        刷新数据
      </button>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-xl shadow-sm flex items-center gap-3">
      <span class="text-xl">⚠️</span>
      {{ error }}
    </div>

    <!-- 加载骨架 -->
    <div v-if="loading && !overview" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <div v-for="i in 4" :key="i" class="card p-6 animate-pulse">
        <div class="h-4 bg-blue-50 rounded w-1/2 mb-4"></div>
        <div class="h-10 bg-slate-100 rounded w-3/4"></div>
      </div>
    </div>

    <!-- 数据展示 -->
    <template v-else-if="overview">
      <!-- 状态卡片 -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <!-- 服务状态 -->
        <div class="card p-6 relative overflow-hidden group">
          <div class="absolute -right-6 -top-6 opacity-5 group-hover:opacity-10 transition-opacity">
            <svg class="w-32 h-32" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5zm0 9l2.5-1.25L12 8.5l-2.5 1.25L12 11zm0 2.5l-5-2.5-5 2.5L12 22l10-8.5-5-2.5-5 2.5z"/></svg>
          </div>
          <div class="text-sm font-semibold text-blue-400 uppercase tracking-wider mb-2">服务状态</div>
          <div class="flex items-center gap-3">
            <span
              class="w-3 h-3 rounded-full ring-4 ring-opacity-20"
              :class="overview.status === 'running' ? 'bg-green-500 ring-green-500' : 'bg-red-500 ring-red-500'"
            ></span>
            <span class="text-3xl font-bold text-[#0F4C75] capitalize">{{ overview.status }}</span>
          </div>
          <div class="text-sm text-slate-400 mt-3 flex items-center gap-1">
            <span class="inline-block w-2 h-2 rounded-full bg-blue-200"></span>
            Version {{ overview.version }}
          </div>
        </div>

        <!-- 容器总数 -->
        <router-link 
          to="/ships" 
          class="card p-6 hover:-translate-y-1 hover:shadow-blue-200 transition-all duration-300 group relative overflow-hidden"
        >
          <div class="absolute right-4 top-4 opacity-10 group-hover:opacity-20 group-hover:scale-110 transition-all duration-300 text-[#0F4C75]">
            <svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" /></svg>
          </div>
          <div class="text-sm font-semibold text-blue-400 uppercase tracking-wider mb-2">容器实例</div>
          <div class="text-3xl font-bold text-[#0F4C75]">
            {{ overview.ships.running }}
            <span class="text-lg text-slate-400 font-normal">/ {{ overview.ships.total }}</span>
          </div>
          <div class="text-sm text-slate-400 mt-3 flex items-center gap-2">
            <span class="flex items-center gap-1 text-amber-500">
              <span class="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
              {{ overview.ships.creating }} 创建中
            </span>
          </div>
        </router-link>

        <!-- 会话总数 -->
        <router-link 
          to="/sessions" 
          class="card p-6 hover:-translate-y-1 hover:shadow-blue-200 transition-all duration-300 group relative overflow-hidden"
        >
          <div class="absolute right-4 top-4 opacity-10 group-hover:opacity-20 group-hover:scale-110 transition-all duration-300 text-[#0F4C75]">
            <svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
          </div>
          <div class="text-sm font-semibold text-blue-400 uppercase tracking-wider mb-2">活跃会话</div>
          <div class="text-3xl font-bold text-[#0F4C75]">
            {{ overview.sessions.active }}
            <span class="text-lg text-slate-400 font-normal">/ {{ overview.sessions.total }}</span>
          </div>
          <div class="text-sm text-slate-400 mt-3">
            实时交互连接
          </div>
        </router-link>

        <!-- 快捷操作 -->
        <div class="card p-6 flex flex-col justify-center">
          <div class="text-sm font-semibold text-blue-400 uppercase tracking-wider mb-4">快捷操作</div>
          <router-link
            to="/ships/create"
            class="btn-primary flex items-center justify-center gap-2 w-full py-3 font-medium"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
            </svg>
            新建工作区
          </router-link>
        </div>
      </div>

      <!-- 详细统计 -->
      <div class="card p-8">
        <h3 class="text-xl font-bold text-[#0F4C75] mb-6 flex items-center gap-2">
          <svg class="w-6 h-6 text-[#3282B8]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
          容器状态分布
        </h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div class="text-center p-6 rounded-2xl bg-[#F0F9FF] border border-blue-100 hover:shadow-md transition-shadow group">
            <div class="text-4xl font-bold text-[#3282B8] mb-2 group-hover:scale-110 transition-transform">{{ overview.ships.running }}</div>
            <div class="text-sm font-medium text-slate-500 uppercase tracking-wide">运行中</div>
          </div>
          <div class="text-center p-6 rounded-2xl bg-slate-50 border border-slate-100 hover:shadow-md transition-shadow group">
            <div class="text-4xl font-bold text-slate-400 mb-2 group-hover:scale-110 transition-transform">{{ overview.ships.stopped }}</div>
            <div class="text-sm font-medium text-slate-500 uppercase tracking-wide">已停止</div>
          </div>
          <div class="text-center p-6 rounded-2xl bg-amber-50 border border-amber-100 hover:shadow-md transition-shadow group">
            <div class="text-4xl font-bold text-amber-500 mb-2 group-hover:scale-110 transition-transform">{{ overview.ships.creating }}</div>
            <div class="text-sm font-medium text-slate-500 uppercase tracking-wide">创建中</div>
          </div>
          <div class="text-center p-6 rounded-2xl bg-indigo-50 border border-indigo-100 hover:shadow-md transition-shadow group">
            <div class="text-4xl font-bold text-indigo-500 mb-2 group-hover:scale-110 transition-transform">{{ overview.sessions.active }}</div>
            <div class="text-sm font-medium text-slate-500 uppercase tracking-wide">活跃会话</div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
