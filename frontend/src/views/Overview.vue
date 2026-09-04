<script setup>
import { ref, computed, onMounted } from 'vue'
import { useWorkbenchStore } from '@/store/workbench'
import { getSkills, getActivity, runAnalyze, getAnalyzeLatest, getAnalyzeHistory } from '@/api'
import { message } from 'ant-design-vue'

const store = useWorkbenchStore()
const skills = ref([])
const activity = ref([])
const activityLoading = ref(false)
const analysis = ref(null)
const analysisLoading = ref(false)
const analysisHistory = ref([])
const running = ref(false)

const skillCount = computed(() => skills.value.length || 0)
const hermesCount = computed(() => skills.value.filter(s => s.source === 'hermes').length)
const claudeCount = computed(() => skills.value.filter(s => s.source === 'claude').length)
const projectCount = computed(() => store.projectCount)
const runningCount = computed(() => store.allProjects.filter(p => p.active).length)
const docCount = computed(() => store.allProjects.filter(p => p.type === 'doc').length)

onMounted(async () => {
  if (!store.categories.length)
    await store.load()
  try {
    const d = await getSkills()
    skills.value = d.skills || []
  }
  catch { /* ignore */ }
  await loadActivity()
  await loadAnalysis()
})

async function loadActivity() {
  activityLoading.value = true
  try {
    const d = await getActivity()
    activity.value = d.events || []
  }
  catch { /* ignore */ }
  finally {
    activityLoading.value = false
  }
}

async function loadAnalysis() {
  analysisLoading.value = true
  try {
    const [l, h] = await Promise.all([getAnalyzeLatest(), getAnalyzeHistory()])
    if (l?.ok)
      analysis.value = l.report
    if (h?.ok)
      analysisHistory.value = h.versions
  }
  catch { /* ignore */ }
  finally {
    analysisLoading.value = false
  }
}

async function doRun() {
  running.value = true
  try {
    const r = await runAnalyze()
    if (r?.ok) {
      analysis.value = r.report
      message.success(`分析完成 · 版本 ${r.version}`)
      await loadAnalysis()
    }
    else {
      message.error(r?.error || '分析失败')
    }
  }
  catch (e) {
    message.error('运行分析失败: ' + (e?.message || e))
  }
  finally {
    running.value = false
  }
}

function openAnalysis(version) {
  // 用 /api/analyze/latest 重置标记; 版本历史仅展示 (当前简化: 高亮最近版本)
  message.info(`版本 ${version} · 详情见报告文件`)
}

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
        <a href="/system" style="text-decoration:none;color:inherit">
          <div class="nav-item">
            <div style="font-size:22px">⚙️</div>
            <div style="font-weight:600;margin-top:4px">系统设置</div>
            <div style="font-size:12px;color:#999">本机环境自检</div>
          </div>
        </a>
      </div>
    </a-card>

    <!-- 近期活动分析 -->
    <a-card title="🧠 近期活动分析" size="small" style="border-radius:8px;margin-top:16px">
      <template #extra>
        <a-tag v-if="analysis" color="gold" style="margin-right:8px">
          版本 {{ analysis.generated_at.slice(0, 10) }} {{ analysis.generated_at.slice(11, 16) }}
        </a-tag>
        <a-button type="primary" size="small" :loading="running" @click="doRun">
          ▶ 运行分析
        </a-button>
      </template>
      <a-skeleton :loading="analysisLoading" active>
        <template v-if="analysis">
          <!-- 统计 -->
          <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px">
            <a-tag color="blue" style="font-size:13px">📝 {{ analysis.stats.sessions }} 次会话</a-tag>
            <a-tag color="green" style="font-size:13px">🗂️ {{ analysis.stats.projects }} 个方向</a-tag>
            <a-tag color="cyan" style="font-size:13px">📦 {{ analysis.stats.git_events }} 条提交</a-tag>
            <a-tag :color="analysis.stats.cron_failures ? 'red' : 'green'" style="font-size:13px">
              ⏰ {{ analysis.stats.cron_failures }} 个任务异常
            </a-tag>
          </div>

          <!-- 热点项目 -->
          <div style="margin-bottom:10px">
            <div style="font-size:12px;color:#999;margin-bottom:6px">🔥 近期热点</div>
            <div style="display:flex;gap:8px;flex-wrap:wrap">
              <a-tag
                v-for="(p, i) in analysis.hot_projects"
                :key="p.name"
                :color="['volcano', 'orange', 'gold'][i] || 'default'"
                style="font-size:13px;padding:2px 10px"
              >
                {{ p.name }} ×{{ p.count }}
              </a-tag>
            </div>
          </div>

          <!-- 建议 -->
          <div v-if="analysis.suggestions?.length" style="margin-bottom:10px">
            <div style="font-size:12px;color:#999;margin-bottom:6px">💡 建议</div>
            <ul style="margin:0;padding-left:18px">
              <li v-for="s in analysis.suggestions" :key="s" style="font-size:13px;color:#555;margin-bottom:4px">{{ s }}</li>
            </ul>
          </div>

          <!-- cron 异常 -->
          <div v-if="analysis.cron_issues?.length" style="margin-bottom:10px">
            <div style="font-size:12px;color:#999;margin-bottom:6px">⚠️ 定时任务异常</div>
            <div v-for="c in analysis.cron_issues" :key="c.name" style="font-size:13px;color:#cf1322;margin-bottom:2px">
              {{ c.name }} — {{ c.error }}
            </div>
          </div>

          <!-- 版本历史 -->
          <div v-if="analysisHistory.length">
            <div style="font-size:12px;color:#999;margin-bottom:6px">📜 版本记录</div>
            <div style="display:flex;gap:6px;flex-wrap:wrap">
              <a-tag
                v-for="v in analysisHistory.slice(0, 8)"
                :key="v.version"
                :color="v.version === analysis.generated_at.replace(/[-: ]/g, '').slice(0, 14) ? 'gold' : 'default'"
                style="font-size:11px;cursor:pointer"
                @click="openAnalysis(v.version)"
              >
                {{ v.time }}
              </a-tag>
            </div>
          </div>
        </template>
        <a-empty v-else-if="!analysisLoading" description="尚无分析报告, 点击运行分析生成" style="padding:20px 0" />
      </a-skeleton>
    </a-card>

    <!-- 最近活动时间线 -->
    <a-card title="🕐 最近活动" size="small" style="border-radius:8px;margin-top:16px">
      <template #extra>
        <a-button size="small" @click="loadActivity">刷新</a-button>
      </template>
      <a-skeleton :loading="activityLoading" active>
        <a-timeline v-if="activity.length" style="margin-top:8px">
          <a-timeline-item v-for="(e, i) in activity.slice(0, 12)" :key="i" :color="i < 3 ? 'green' : 'blue'">
            <div style="display:flex;gap:10px;align-items:baseline">
              <span style="font-family:monospace;font-size:12px;color:#888;white-space:nowrap">{{ e.when }}</span>
              <a-tag :color="i < 3 ? 'green' : 'default'" style="font-size:11px">{{ e.proj_name }}</a-tag>
              <span style="font-size:13px;color:#555">{{ e.subject }}</span>
            </div>
          </a-timeline-item>
        </a-timeline>
        <a-empty v-else-if="!activityLoading" description="暂无活动" style="padding:20px 0" />
      </a-skeleton>
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