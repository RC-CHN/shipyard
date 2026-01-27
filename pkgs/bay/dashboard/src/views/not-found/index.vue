<script setup lang="ts">
import { useNotFound } from './useNotFound'

const { goHome, goBack } = useNotFound()
</script>

<template>
  <div class="min-h-[60vh] flex items-center justify-center">
    <div class="text-center">
      <div class="text-8xl mb-6">🚢</div>
      <h1 class="text-6xl font-bold text-gray-900 mb-4">404</h1>
      <p class="text-xl text-gray-600 mb-8">页面未找到</p>
      <p class="text-gray-500 mb-8">
        您访问的页面不存在或已被移除
      </p>
      <div class="flex justify-center gap-4">
        <button
          @click="goBack"
          class="px-6 py-2 text-gray-600 hover:text-gray-800 border border-gray-300 rounded-lg hover:border-gray-400 transition-colors"
        >
          返回上页
        </button>
        <button
          @click="goHome"
          class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          返回首页
        </button>
      </div>
    </div>
  </div>
</template>
