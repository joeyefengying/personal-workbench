<script setup>
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useWorkbenchStore } from '@/store/workbench'

const route = useRoute()
const store = useWorkbenchStore()
onMounted(() => store.load())

const menuItems = [
  { key: '/overview', icon: '📊', label: '总览' },
  { key: '/skills', icon: '🧩', label: 'Skill 能力' },
  { key: '/projects', icon: '🗂️', label: '应用与项目' },
  { key: '/automation', icon: '🔄', label: '自动化任务' },
  { key: '/wiki', icon: '📚', label: '知识库' },
  { key: '/system', icon: '⚙️', label: '系统设置' },
]
</script>

<template>
  <a-layout style="min-height: 100vh">
    <a-layout-sider
      width="220"
      theme="dark"
      breakpoint="lg"
      collapsible
      :trigger="null"
    >
      <!-- Logo -->
      <div class="wb-logo">
        <span class="wb-logo-icon">◈</span>
        <span class="wb-logo-text">Workbench</span>
      </div>

      <!-- Menu -->
      <a-menu
        theme="dark"
        mode="inline"
        :selected-keys="[route.path]"
        @click="({ key }) => $router.push(key)"
        class="wb-menu"
      >
        <a-menu-item v-for="m in menuItems" :key="m.key">
          <span class="wb-menu-icon">{{ m.icon }}</span>
          <span>{{ m.label }}</span>
        </a-menu-item>
      </a-menu>

      <!-- Footer -->
      <div class="wb-sidebar-footer">
        <div class="wb-sidebar-footer-text">Personal Agent Workbench</div>
        <div class="wb-sidebar-footer-version">v0.3 · Launcher Mode</div>
      </div>
    </a-layout-sider>

    <a-layout>
      <a-layout-header class="wb-header">
        <div class="wb-header-left">
          <h1 class="wb-header-title">{{ route.meta.title }}</h1>
          <span class="wb-header-sub">浩哥的 Agent 能力聚合入口</span>
        </div>
        <div class="wb-header-right">
          <a-button
            size="small"
            :loading="store.refreshing"
            @click="store.refresh()"
            class="wb-header-btn"
          >
            刷新
          </a-button>
        </div>
      </a-layout-header>

      <a-layout-content class="wb-content">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<style scoped>
.wb-logo {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.wb-logo-icon {
  font-size: 20px;
  color: #7170ff;
  font-weight: 700;
}
.wb-logo-text {
  color: #f7f8f8;
  font-weight: 600;
  font-size: 15px;
  letter-spacing: -0.3px;
}

.wb-menu {
  background: transparent !important;
  padding: 8px;
}
.wb-menu :deep(.ant-menu-item) {
  margin: 2px 0 !important;
  border-radius: 8px !important;
  height: 38px !important;
  line-height: 38px !important;
  color: #8a8f98 !important;
  transition: all 0.2s ease;
}
.wb-menu :deep(.ant-menu-item:hover) {
  background: rgba(255, 255, 255, 0.04) !important;
  color: #f7f8f8 !important;
}
.wb-menu :deep(.ant-menu-item-selected) {
  background: rgba(94, 106, 210, 0.15) !important;
  color: #7170ff !important;
}
.wb-menu-icon {
  margin-right: 10px;
  font-size: 16px;
}

.wb-sidebar-footer {
  position: absolute;
  bottom: 16px;
  left: 0;
  right: 0;
  padding: 12px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}
.wb-sidebar-footer-text {
  font-size: 11px;
  color: #62666d;
  font-weight: 500;
}
.wb-sidebar-footer-version {
  font-size: 10px;
  color: #4a4d52;
  margin-top: 2px;
  font-family: 'JetBrains Mono', monospace;
}

.wb-header {
  background: var(--wb-bg-elevated) !important;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px !important;
  height: 56px !important;
  border-bottom: 1px solid var(--wb-border);
  box-shadow: var(--wb-shadow-sm);
  position: sticky;
  top: 0;
  z-index: 10;
}
.wb-header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}
.wb-header-title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.3px;
  color: var(--wb-text-primary);
}
.wb-header-sub {
  font-size: 12px;
  color: var(--wb-text-tertiary);
}
.wb-header-btn {
  border-color: var(--wb-border-light);
}

.wb-content {
  padding: 28px !important;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}
</style>
