<script setup>
import { onMounted } from 'vue'
import { useWorkbenchStore } from '@/store/workbench'

const store = useWorkbenchStore()
onMounted(() => store.load())
</script>

<template>
  <a-layout style="min-height: 100vh">
    <a-layout-header style="background: #001529; display: flex; align-items: center; gap: 16px">
      <span style="color: #fff; font-size: 18px; font-weight: 600">🛠 个人项目工作台</span>
      <span style="color: rgba(255,255,255,.65); font-size: 13px">浩哥的 Hermes 自研项目聚合入口</span>
      <div style="flex: 1"></div>
      <a-button size="small" ghost :loading="store.refreshing" @click="store.refresh()">
        刷新
      </a-button>
    </a-layout-header>
    <a-layout-content style="padding: 24px; max-width: 1400px; margin: 0 auto; width: 100%">
      <router-view />
    </a-layout-content>
    <a-layout-footer style="text-align: center; color: #999; font-size: 12px">
      Personal Workbench · 个人项目聚合 · 一键启动 / Git 状态
    </a-layout-footer>
  </a-layout>
</template>