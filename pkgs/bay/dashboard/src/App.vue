<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'
import { ToastContainer } from '@/components'

const route = useRoute()

const useLayout = computed(() => !route.meta.hideLayout)
</script>

<template>
  <MainLayout v-if="useLayout">
    <RouterView />
  </MainLayout>
  <RouterView v-else />
  
  <!-- 全局 Toast 容器 -->
  <ToastContainer />
</template>
