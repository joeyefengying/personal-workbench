<script setup>
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useWorkbenchStore } from '@/store/workbench'

const route = useRoute()
const store = useWorkbenchStore()
onMounted(() => store.load())

const menuItems = [
  {
    key: '/overview',
    icon: '📊',
    label: '总览',
  },
  {
    key: '/skills',
    icon: '🧩',
    label: 'Skill 能力',
  },
  {
    key: '/projects',
    icon: '🗂️',
    label: '应用与项目',
  },
  {
    key: '/automation',
    icon: '🔄',
    label: '自动化任务',
  },
  {
    key: '/wiki',
    icon: '📚',
    label: '知识库',
  },
  {
    key: '/system',
    icon: '⚙️',
    label: '系统设置',
  },
]
</script>

<template>
  <a-layout style="min-height: 100vh">
    <a-layout-sider width="200" theme="dark" breakpoint="lg" collapsible>
      <div style="height: 48px; display: flex; align-items: center; justify-content: center; gap: 6px; color: #fff; font-weight: 700; font-size: 15px; letter-spacing: 0.5px">
        🛠 个人工作台
      </div>
      <a-menu
        theme="dark"
        mode="inline"
        :selected-keys="[route.path]"
        @click="({ key }) => $router.push(key)"
      >
        <a-menu-item v-for="m in menuItems" :key="m.key">
          <span style="margin-right: 8px">{{ m.icon }}</span>
          <span>{{ m.label }}</span>
        </a-menu-item>
      </a-menu>
    </a-layout-sider>
    <a-layout>
      <a-layout-header style="background: #fff; display: flex; align-items: center; gap: 12px; padding: 0 24px; border-bottom: 1px solid #f0f0f0">
        <span style="font-size: 16px; font-weight: 600">{{ route.meta.title }}</span>
        <span style="color: #999; font-size: 13px">浩哥的 Agent 能力聚合入口 · 点开即对话</span>
        <div style="flex: 1"></div>
        <a-button size="small" :loading="store.refreshing" @click="store.refresh()">
          刷新
        </a-button>
      </a-layout-header>
      <a-layout-content style="padding: 24px; max-width: 1400px; margin: 0 auto; width: 100%">
        <router-view />
      </a-layout-content>
      <a-layout-footer style="text-align: center; color: #999; font-size: 12px">
        Personal Workbench · Agent 能力工作台 · 壳 / 桥 / 对话本体
      </a-layout-footer>
    </a-layout>
  </a-layout>
</template>
