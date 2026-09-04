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
  <div>
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
      <h2 style="margin:0;font-size:18px">⚙️ 系统设置</h2>
      <div style="flex:1"></div>
      <a-button size="small" :loading="loading" @click="load">重新检测</a-button>
    </div>

    <a-card size="small" style="border-radius:8px;margin-bottom:16px" title="本机环境自检">
      <a-skeleton :loading="loading" active>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px">
          <div v-for="it in items" :key="it.key" style="display:flex;align-items:center;gap:12px;border:1px solid #f0f0f0;border-radius:8px;padding:12px">
            <div style="font-size:24px">{{ it.icon }}</div>
            <div>
              <div style="font-size:12px;color:#999">{{ it.label }}</div>
              <div style="font-weight:600">{{ env?.[it.key] ?? '—' }}</div>
            </div>
          </div>
        </div>
      </a-skeleton>
    </a-card>

    <a-card v-if="env?.running?.length" size="small" style="border-radius:8px" title="当前运行中的服务">
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <a-tag v-for="r in env.running" :key="r" color="green" style="font-size:13px;padding:2px 10px">
          🟢 {{ r }}
        </a-tag>
      </div>
    </a-card>
  </div>
</template>