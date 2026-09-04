<script setup>
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<template>
  <div style="padding: 40px 0; text-align: center">
    <div style="font-size: 48px; margin-bottom: 16px">{{ route.meta.icon }}</div>
    <h2 style="margin: 0 0 8px">{{ route.meta.title }}</h2>
    <p style="color: #999; margin: 0">该模块正在规划建设中，将作为系统级入口逐步接入。</p>
  </div>
</template>