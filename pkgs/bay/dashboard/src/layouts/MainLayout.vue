<script setup lang="ts">
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { ref, computed } from 'vue'

const route = useRoute()
const sidebarOpen = ref(true)

const navItems = [
  { 
    path: '/', 
    name: '仪表盘', 
    icon: 'M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z' 
  },
  { 
    path: '/ships', 
    name: '容器管理', 
    icon: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4' 
  },
  { 
    path: '/sessions', 
    name: '会话管理', 
    icon: 'M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z' 
  },
  { 
    path: '/settings', 
    name: '系统设置', 
    icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' 
  },
]

const currentNavItem = computed(() => 
  navItems.find(item => route.path === item.path || route.path.startsWith(item.path + '/'))
)
</script>

<template>
  <!-- Fixed viewport layout - no scrolling on body -->
  <div class="h-screen bg-slate-50 flex overflow-hidden">
    <!-- Sidebar - fixed, no scroll -->
    <aside 
      class="bg-[#0F4C75] text-white transition-all duration-300 flex flex-col shadow-xl z-20 flex-shrink-0"
      :class="sidebarOpen ? 'w-64' : 'w-20'"
    >
      <!-- Logo -->
      <div class="flex items-center justify-between h-16 px-4 border-b border-blue-800/50 bg-[#0a3d61] flex-shrink-0">
        <div v-if="sidebarOpen" class="flex items-center gap-3 overflow-hidden whitespace-nowrap">
          <div class="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center shadow-lg bg-opacity-20 backdrop-blur-sm border border-blue-400/30">
            <svg class="w-5 h-5 text-blue-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <span class="font-bold text-lg tracking-wide text-white">Bay Dashboard</span>
        </div>
        <div v-else class="w-full flex justify-center">
          <div class="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center shadow-lg bg-opacity-20 backdrop-blur-sm border border-blue-400/30">
            <svg class="w-5 h-5 text-blue-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
        </div>
      </div>
      
      <!-- Navigation - scrollable if too many items -->
      <nav class="flex-1 py-6 px-3 space-y-2 overflow-y-auto">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="flex items-center px-3 py-3 rounded-xl transition-all duration-200 group relative overflow-hidden"
          :class="[
            currentNavItem?.path === item.path 
              ? 'bg-[#3282B8] text-white shadow-lg shadow-blue-900/20' 
              : 'text-blue-100 hover:bg-white/10 hover:text-white'
          ]"
        >
          <svg 
            class="w-6 h-6 relative z-10 transition-transform duration-300 group-hover:scale-110 flex-shrink-0" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="item.icon" />
          </svg>
          <span 
            v-if="sidebarOpen" 
            class="ml-3 font-medium relative z-10 whitespace-nowrap transition-opacity duration-300"
          >
            {{ item.name }}
          </span>
          
          <!-- Active Indicator -->
          <div 
            v-if="currentNavItem?.path === item.path"
            class="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-white rounded-r-full opacity-0 transition-opacity duration-300"
            :class="{ 'opacity-100': !sidebarOpen }"
          ></div>
        </RouterLink>
      </nav>

      <!-- Footer Toggle - fixed at bottom -->
      <div class="p-4 border-t border-blue-800/50 bg-[#0a3d61] flex-shrink-0">
        <button 
          @click="sidebarOpen = !sidebarOpen"
          class="w-full flex items-center justify-center p-2 rounded-lg hover:bg-white/10 text-blue-200 hover:text-white transition-colors"
        >
          <svg 
            class="w-5 h-5 transition-transform duration-300"
            :class="{ 'rotate-180': !sidebarOpen }"
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
      </div>
    </aside>

    <!-- Main content area -->
    <div class="flex-1 flex flex-col min-w-0 overflow-hidden">
      <!-- Header - fixed, no scroll -->
      <header class="h-16 bg-white shadow-sm border-b border-slate-200 flex items-center justify-between px-8 z-10 flex-shrink-0">
        <div class="flex items-center gap-4">
          <h1 class="text-xl font-bold text-[#0F4C75]">
            {{ currentNavItem?.name || 'Bay Dashboard' }}
          </h1>
        </div>
        <div class="flex items-center gap-4">
          <div class="px-3 py-1 rounded-full bg-blue-50 text-[#3282B8] text-xs font-mono font-medium border border-blue-100">
            v0.1.0
          </div>
        </div>
      </header>

      <!-- Content - scrollable area -->
      <main class="flex-1 overflow-auto p-8 bg-slate-50 scroll-smooth">
        <div class="max-w-7xl mx-auto">
          <RouterView v-slot="{ Component }">
            <transition 
              name="fade" 
              mode="out-in"
              enter-active-class="transition duration-200 ease-out"
              enter-from-class="transform opacity-0 translate-y-2"
              enter-to-class="transform opacity-100 translate-y-0"
              leave-active-class="transition duration-150 ease-in"
              leave-from-class="transform opacity-100 translate-y-0"
              leave-to-class="transform opacity-0 -translate-y-2"
            >
              <component :is="Component" />
            </transition>
          </RouterView>
        </div>
      </main>
    </div>
  </div>
</template>
