<script setup>
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useWorkbenchStore } from '@/store/workbench'

const route = useRoute()
const store = useWorkbenchStore()
onMounted(() => store.load())

// 分组菜单 (带分组标题, 模仿 Linear/Notion 的导航结构)
const menuGroups = [
  {
    label: '工作台',
    items: [
      { key: '/overview', icon: '📊', label: '总览' },
      { key: '/timeline', icon: '🕐', label: '时间线' },
    ],
  },
  {
    label: '能力',
    items: [
      { key: '/skills', icon: '🧩', label: 'Skill 能力' },
      { key: '/projects', icon: '🗂️', label: '应用与项目' },
      { key: '/automation', icon: '🔄', label: '自动化任务' },
    ],
  },
  {
    label: '数据',
    items: [
      { key: '/qingtui', icon: '💬', label: '轻推工作' },
      { key: '/wiki', icon: '📚', label: '知识库' },
      { key: '/reports', icon: '📋', label: '报告中心' },
    ],
  },
  {
    label: '系统',
    items: [
      { key: '/system', icon: '⚙️', label: '系统设置' },
    ],
  },
]
</script>

<template>
  <a-layout style="min-height: 100vh">
    <a-layout-sider
      :width="232"
      theme="dark"
      breakpoint="lg"
      collapsible
      :trigger="null"
      class="wb-sider"
    >
      <!-- Logo -->
      <div class="wb-logo">
        <div class="wb-logo-mark">◈</div>
        <div class="wb-logo-text-wrap">
          <span class="wb-logo-text">Workbench</span>
          <span class="wb-logo-sub">Personal Agent Hub</span>
        </div>
      </div>

      <!-- Menu -->
      <div class="wb-menu-scroll">
        <div v-for="group in menuGroups" :key="group.label" class="wb-menu-group">
          <div class="wb-menu-group-label">{{ group.label }}</div>
          <a-menu
            theme="dark"
            mode="inline"
            :selected-keys="[route.path]"
            :inline-indent="8"
            @click="({ key }) => $router.push(key)"
            class="wb-menu"
          >
            <a-menu-item v-for="m in group.items" :key="m.key">
              <span class="wb-menu-icon">{{ m.icon }}</span>
              <span class="wb-menu-label">{{ m.label }}</span>
            </a-menu-item>
          </a-menu>
        </div>
      </div>

      <!-- Footer -->
      <div class="wb-sidebar-footer">
        <div class="wb-sidebar-footer-row">
          <span class="wb-sidebar-dot"></span>
          <span>Personal Agent Workbench</span>
        </div>
        <div class="wb-sidebar-footer-version">v0.4 · Launcher Mode</div>
      </div>
    </a-layout-sider>

    <a-layout class="wb-main">
      <a-layout-header class="wb-header">
        <div class="wb-header-left">
          <span class="wb-header-crumb">工作台</span>
          <span class="wb-header-crumb-sep">/</span>
          <h1 class="wb-header-title">{{ route.meta.title }}</h1>
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
/* ── Sider ── */
.wb-sider {
  background: var(--wb-slate-12) !important;
  border-right: 1px solid var(--wb-border-dark);
  position: fixed !important;
  left: 0;
  top: 0;
  bottom: 0;
  height: 100vh !important;
  z-index: 20;
  display: flex !important;
  flex-direction: column !important;
}

/* ── Logo ── */
.wb-logo {
  height: 64px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}
.wb-logo-mark {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--wb-indigo-6), var(--wb-indigo-9));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  box-shadow: 0 2px 8px rgba(94, 99, 213, 0.35);
}
.wb-logo-text-wrap {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.wb-logo-text {
  color: var(--wb-text-on-dark);
  font-weight: 600;
  font-size: 15px;
  letter-spacing: -0.02em;
  line-height: 1.2;
}
.wb-logo-sub {
  color: var(--wb-text-on-dark-sec);
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 0.02em;
}

/* ── Menu Scroll ── */
.wb-menu-scroll {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 12px 8px;
}

.wb-menu-group {
  margin-bottom: 16px;
}
.wb-menu-group-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.32);
  padding: 0 12px;
  margin-bottom: 4px;
}

.wb-menu {
  background: transparent !important;
  border-inline-end: none !important;
}
.wb-menu :deep(.ant-menu-item) {
  margin: 1px 0 !important;
  border-radius: 6px !important;
  height: 36px !important;
  line-height: 36px !important;
  color: rgba(255, 255, 255, 0.56) !important;
  transition: all 0.15s ease;
  position: relative;
}
.wb-menu :deep(.ant-menu-item:hover) {
  background: rgba(255, 255, 255, 0.05) !important;
  color: var(--wb-text-on-dark) !important;
}
.wb-menu :deep(.ant-menu-item-selected) {
  background: rgba(94, 99, 213, 0.18) !important;
  color: #fff !important;
}
/* 选中态左侧指示条 */
.wb-menu :deep(.ant-menu-item-selected::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 18px;
  border-radius: 0 2px 2px 0;
  background: var(--wb-indigo-5);
}
.wb-menu-icon {
  margin-right: 10px;
  font-size: 15px;
  opacity: 0.85;
}
.wb-menu-label {
  font-size: 13px;
  font-weight: 500;
}

/* ── Footer ── */
.wb-sidebar-footer {
  padding: 12px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}
.wb-sidebar-footer-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  font-weight: 500;
}
.wb-sidebar-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--wb-success);
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.15);
}
.wb-sidebar-footer-version {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.22);
  margin-top: 4px;
  font-family: var(--wb-font-mono);
}

/* ── Header ── */
.wb-main {
  background: var(--wb-bg) !important;
  margin-left: var(--wb-sidebar-width) !important;
  min-height: 100vh !important;
  display: flex !important;
  flex-direction: column !important;
}
.wb-header {
  background: rgba(255, 255, 255, 0.8) !important;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px !important;
  height: 56px !important;
  border-bottom: 1px solid var(--wb-border);
  position: sticky;
  top: 0;
  z-index: 10;
  flex-shrink: 0;
}
.wb-header-left {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.wb-header-crumb {
  font-size: 13px;
  color: var(--wb-text-quaternary);
  font-weight: 500;
}
.wb-header-crumb-sep {
  font-size: 13px;
  color: var(--wb-text-quaternary);
  opacity: 0.6;
}
.wb-header-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--wb-text-primary);
}
.wb-header-btn {
  border-color: var(--wb-border);
}

.wb-content {
  padding: 28px !important;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  flex: 1;
  overflow-y: auto;
}
</style>