<script setup>
import { ref, computed, onMounted } from 'vue'
import { useWorkbenchStore } from '@/store/workbench'
import { getSkills } from '@/api'

const store = useWorkbenchStore()
const skills = ref([])

const skillCount = computed(() => skills.value.length || 0)
const hermesCount = computed(() => skills.value.filter(s => s.source === 'hermes').length)
const claudeCount = computed(() => skills.value.filter(s => s.source === 'claude').length)
const projectCount = computed(() => store.projectCount)
const runningCount = computed(() => store.allProjects.filter(p => p.active).length)
const docCount = computed(() => store.allProjects.filter(p => p.type === 'doc').length)

onMounted(async () => {
  if (!store.categories.length)
    store.load()
  try {
    const d = await getSkills()
    skills.value = d.skills || []
  }
  catch { /* ignore */ }
})

const statCards = computed(() => [
  { label: 'Agent 能力', value: skillCount, sub: `${hermesCount.value} H + ${claudeCount.value} C`, icon: '🧩', color: '#1677ff' },
  { label: '应用与项目', value: projectCount, sub: `${runningCount.value} 运行中`, icon: '🗂️', color: '#52c41a' },
  { label: '文档类入口', value: docCount, sub: '知识/参考', icon: '📄', color: '#faad14' },
])
</script>

<template>
  <div>
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px">
      <h2 style="margin:0;font-size:20px">📊 总览</h2>
      <span style="font-size:13px;color:#999">个人 Agent 能力工作台 · 壳 (编排) / 桥 (统一入口) / 对话本体 (Hermes 原生)</span>
    </div>

    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;margin-bottom:24px">
      <a-card v-for="s in statCards" :key="s.label" size="small" style="border-radius:8px">
        <div style="display:flex;align-items:center;gap:14px">
          <div :style="`width:48px;height:48px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:24px;background:${s.color}18`">
            {{ s.icon }}
          </div>
          <div>
            <div style="font-size:24px;font-weight:700">{{ s.value }}</div>
            <div style="font-size:12px;color:#999">{{ s.label }} · {{ s.sub }}</div>
          </div>
        </div>
      </a-card>
    </div>

    <a-card title="🎯 平台定位" size="small" style="border-radius:8px;margin-bottom:16px">
      <p style="margin:0;color:#555;line-height:1.7">
        每个 Skill 能力在工作台里是一张「点开就能对话」的卡片。点击后通过原生 Terminal 拉起
        <code style="background:#eaeef2;padding:1px 5px;border-radius:4px">hermes chat --skills &lt;skill&gt;</code>，
        多轮对话、记忆、流式输出、工具调用全部由 Hermes 原生完成——工作台只做壳，不重复造聊天轮子。
      </p>
    </a-card>

    <a-card title="🧭 功能导航" size="small" style="border-radius:8px">
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px">
        <a href="/skills" style="text-decoration:none;color:inherit">
          <div class="nav-item">
            <div style="font-size:22px">🧩</div>
            <div style="font-weight:600;margin-top:4px">Skill 能力</div>
            <div style="font-size:12px;color:#999">能力墙 → 点卡片对话</div>
          </div>
        </a>
        <a href="/projects" style="text-decoration:none;color:inherit">
          <div class="nav-item">
            <div style="font-size:22px">🗂️</div>
            <div style="font-weight:600;margin-top:4px">应用与项目</div>
            <div style="font-size:12px;color:#999">启动 / 停止 / Git 状态</div>
          </div>
        </a>
        <a href="/automation" style="text-decoration:none;color:inherit">
          <div class="nav-item">
            <div style="font-size:22px">🔄</div>
            <div style="font-weight:600;margin-top:4px">自动化任务</div>
            <div style="font-size:12px;color:#999">Cron / 定时流水线</div>
          </div>
        </a>
        <a href="/wiki" style="text-decoration:none;color:inherit">
          <div class="nav-item">
            <div style="font-size:22px">📚</div>
            <div style="font-weight:600;margin-top:4px">知识库</div>
            <div style="font-size:12px;color:#999">llm-wiki 查询与消化</div>
          </div>
        </a>
      </div>
    </a-card>
  </div>
</template>

<style scoped>
.nav-item {
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
  transition: all 0.2s;
}
.nav-item:hover {
  border-color: #1677ff;
  color: #1677ff;
  box-shadow: 0 2px 8px rgba(22, 119, 255, 0.12);
}
</style>