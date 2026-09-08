<script setup>
import { ref, onMounted } from 'vue'
import { getSystemEnv } from '@/api'

const env = ref(null)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    env.value = await getSystemEnv()
  }
  finally {
    loading.value = false
  }
}

const items = [
  { key: 'os', label: '操作系统', icon: '💻' },
  { key: 'python', label: 'Python', icon: '🐍' },
  { key: 'hermes', label: 'Hermes Agent', icon: '🤖' },
  { key: 'skills', label: 'Agent 能力', icon: '🧩' },
  { key: 'projects', label: '项目数量', icon: '🗂️' },
  { key: 'sessions', label: '项目会话', icon: '💬' },
  { key: 'favorites', label: '收藏能力', icon: '⭐' },
]

onMounted(load)
</script>

<template>
  <div class="system-page">
    <!-- Page header -->
    <header class="system-header">
      <h2 class="wb-page-title">⚙️ 系统设置</h2>
      <div class="system-header-spacer"></div>
      <a-button size="small" :loading="loading" @click="load">重新检测</a-button>
    </header>

    <!-- Environment cards -->
    <section class="env-section">
      <div class="env-section-title">本机环境自检</div>
      <a-skeleton :loading="loading" active>
        <div class="env-grid">
          <div
            v-for="it in items"
            :key="it.key"
            class="env-card wb-card-elevated"
          >
            <div class="env-icon">{{ it.icon }}</div>
            <div class="env-card-body">
              <div class="env-label">{{ it.label }}</div>
              <div class="env-value">{{ env?.[it.key] ?? '—' }}</div>
            </div>
          </div>
        </div>
      </a-skeleton>
    </section>

    <!-- Running services -->
    <section v-if="env?.running?.length" class="running-section">
      <div class="env-section-title">当前运行中的服务</div>
      <div class="running-list">
        <span v-for="r in env.running" :key="r" class="running-badge">
          <span class="running-dot"></span>
          {{ r }}
        </span>
      </div>
    </section>
  </div>
</template>

<style scoped>
.system-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── Page header ── */
.system-header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.wb-page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.3px;
  color: var(--wb-text-primary);
}
.system-header-spacer {
  flex: 1;
}

/* ── Section titles ── */
.env-section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--wb-text-primary);
  margin-bottom: 12px;
  letter-spacing: -0.2px;
}

/* ── Environment cards grid ── */
.env-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.env-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border-radius: var(--wb-radius-md);
  transition: all var(--wb-transition);
}
.env-card:hover {
  box-shadow: var(--wb-shadow-md);
  transform: translateY(-1px);
}
.env-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  line-height: 1;
  border-radius: var(--wb-radius-sm);
  background: var(--wb-accent-bg);
  color: var(--wb-accent);
}
.env-card-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.env-label {
  font-size: 12px;
  color: var(--wb-text-tertiary);
  line-height: 1.4;
}
.env-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--wb-text-primary);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Running services badges ── */
.running-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.running-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  font-size: 13px;
  font-weight: 500;
  color: var(--wb-text-secondary);
  background: var(--wb-bg-elevated);
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius-lg);
  transition: all var(--wb-transition);
}
.running-badge:hover {
  border-color: var(--wb-success);
  box-shadow: var(--wb-shadow-sm);
}
.running-dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--wb-success);
  box-shadow: 0 0 0 3px rgba(39, 166, 68, 0.15);
}
</style>
