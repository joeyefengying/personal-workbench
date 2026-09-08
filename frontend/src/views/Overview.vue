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
  message.info(`版本 ${version} · 详情见报告文件`)
}

const statCards = computed(() => [
  { label: 'Agent 能力', value: skillCount, sub: `${hermesCount.value} H + ${claudeCount.value} C`, icon: '🧩', bg: 'rgba(94, 106, 210, 0.1)', color: '#5e6ad2' },
  { label: '应用与项目', value: projectCount, sub: `${runningCount.value} 运行中`, icon: '🗂️', bg: 'rgba(39, 166, 68, 0.1)', color: '#27a644' },
  { label: '文档类入口', value: docCount, sub: '知识/参考', icon: '📄', bg: 'rgba(245, 166, 35, 0.1)', color: '#f5a623' },
])

const navItems = [
  { href: '/skills', icon: '🧩', title: 'Skill 能力', desc: '能力墙 → 点卡片对话' },
  { href: '/projects', icon: '🗂️', title: '应用与项目', desc: '启动 / 停止 / Git 状态' },
  { href: '/automation', icon: '🔄', title: '自动化任务', desc: 'Cron / 定时流水线' },
  { href: '/wiki', icon: '📚', title: '知识库', desc: 'llm-wiki 查询与消化' },
  { href: '/system', icon: '⚙️', title: '系统设置', desc: '本机环境自检' },
]
</script>

<template>
  <div class="wb-overview">
    <!-- Hero -->
    <div class="wb-hero">
      <h2 class="wb-hero-title">Agent 能力工作台</h2>
      <p class="wb-hero-desc">
        壳（编排）· 桥（统一入口）· 对话本体（Hermes 原生）<br />
        每个 Skill 是一张「点开就能对话」的卡片，多轮/记忆/流式/工具全部复用 Hermes
      </p>
    </div>

    <!-- Stat Cards -->
    <div class="wb-stat-grid">
      <div v-for="s in statCards" :key="s.label" class="wb-stat-card">
        <div class="wb-stat-icon" :style="{ background: s.bg }">
          <span :style="{ color: s.color }">{{ s.icon }}</span>
        </div>
        <div>
          <div class="wb-stat-value" :style="{ color: s.color }">{{ s.value }}</div>
          <div class="wb-stat-label">{{ s.label }} · {{ s.sub }}</div>
        </div>
      </div>
    </div>

    <!-- Navigation Grid -->
    <div class="wb-section">
      <div class="wb-section-header">
        <span class="wb-section-title">🧭 功能导航</span>
        <span class="wb-section-sub">快速跳转到各模块</span>
      </div>
      <div class="wb-nav-grid">
        <a v-for="n in navItems" :key="n.href" :href="n.href" class="wb-nav-card">
          <div class="wb-nav-card-icon">{{ n.icon }}</div>
          <div class="wb-nav-card-title">{{ n.title }}</div>
          <div class="wb-nav-card-desc">{{ n.desc }}</div>
        </a>
      </div>
    </div>

    <!-- Activity Analysis -->
    <div class="wb-section">
      <div class="wb-section-header" style="margin-bottom: 12px">
        <span class="wb-section-title">🧠 近期活动分析</span>
        <a-tag v-if="analysis" color="gold" style="margin-left: 8px; font-size: 11px">
          {{ analysis.generated_at.slice(0, 10) }} {{ analysis.generated_at.slice(11, 16) }}
        </a-tag>
        <div style="flex: 1"></div>
        <a-button type="primary" size="small" :loading="running" @click="doRun">
          ▶ 运行分析
        </a-button>
      </div>
      <a-card size="small" class="wb-analysis-card">
        <a-skeleton :loading="analysisLoading" active>
          <template v-if="analysis">
            <div class="wb-analysis-stats">
              <div class="wb-analysis-stat">
                <span class="wb-analysis-stat-val">{{ analysis.stats.sessions }}</span>
                <span class="wb-analysis-stat-label">次会话</span>
              </div>
              <div class="wb-analysis-divider"></div>
              <div class="wb-analysis-stat">
                <span class="wb-analysis-stat-val">{{ analysis.stats.projects }}</span>
                <span class="wb-analysis-stat-label">个方向</span>
              </div>
              <div class="wb-analysis-divider"></div>
              <div class="wb-analysis-stat">
                <span class="wb-analysis-stat-val">{{ analysis.stats.git_events }}</span>
                <span class="wb-analysis-stat-label">条提交</span>
              </div>
              <div class="wb-analysis-divider"></div>
              <div class="wb-analysis-stat">
                <span class="wb-analysis-stat-val" :style="{ color: analysis.stats.cron_failures ? '#e5484d' : '#27a644' }">
                  {{ analysis.stats.cron_failures }}
                </span>
                <span class="wb-analysis-stat-label">任务异常</span>
              </div>
            </div>

            <div v-if="analysis.hot_projects?.length" class="wb-analysis-block">
              <div class="wb-analysis-label">🔥 近期热点</div>
              <div class="wb-analysis-tags">
                <a-tag
                  v-for="(p, i) in analysis.hot_projects"
                  :key="p.name"
                  :color="['volcano', 'orange', 'gold'][i] || 'default'"
                  style="font-size: 12px; padding: 2px 10px"
                >
                  {{ p.name }} ×{{ p.count }}
                </a-tag>
              </div>
            </div>

            <div v-if="analysis.suggestions?.length" class="wb-analysis-block">
              <div class="wb-analysis-label">💡 建议</div>
              <ul class="wb-analysis-list">
                <li v-for="s in analysis.suggestions" :key="s">{{ s }}</li>
              </ul>
            </div>

            <div v-if="analysis.cron_issues?.length" class="wb-analysis-block">
              <div class="wb-analysis-label" style="color: #e5484d">⚠️ 定时任务异常</div>
              <div v-for="c in analysis.cron_issues" :key="c.name" class="wb-analysis-cron-issue">
                {{ c.name }} — {{ c.error }}
              </div>
            </div>

            <div v-if="analysisHistory.length" class="wb-analysis-block">
              <div class="wb-analysis-label">📜 版本记录</div>
              <div class="wb-analysis-tags">
                <a-tag
                  v-for="v in analysisHistory.slice(0, 8)"
                  :key="v.version"
                  :color="v.version === analysis.generated_at.replace(/[-: ]/g, '').slice(0, 14) ? 'gold' : 'default'"
                  style="font-size: 11px; cursor: pointer"
                  @click="openAnalysis(v.version)"
                >
                  {{ v.time }}
                </a-tag>
              </div>
            </div>
          </template>
          <a-empty v-else-if="!analysisLoading" description="尚无分析报告, 点击运行分析生成" style="padding: 20px 0" />
        </a-skeleton>
      </a-card>
    </div>

    <!-- Activity Timeline -->
    <div class="wb-section">
      <div class="wb-section-header" style="margin-bottom: 12px">
        <span class="wb-section-title">🕐 最近活动</span>
        <div style="flex: 1"></div>
        <a-button size="small" @click="loadActivity">刷新</a-button>
      </div>
      <a-card size="small">
        <a-skeleton :loading="activityLoading" active>
          <a-timeline v-if="activity.length" style="margin-top: 4px">
            <a-timeline-item v-for="(e, i) in activity.slice(0, 12)" :key="i" :color="i < 3 ? '#27a644' : '#5e6ad2'">
              <div class="wb-timeline-item">
                <span class="wb-timeline-time">{{ e.when }}</span>
                <a-tag :color="i < 3 ? 'green' : 'default'" style="font-size: 11px">{{ e.proj_name }}</a-tag>
                <span class="wb-timeline-subject">{{ e.subject }}</span>
              </div>
            </a-timeline-item>
          </a-timeline>
          <a-empty v-else-if="!activityLoading" description="暂无活动" style="padding: 20px 0" />
        </a-skeleton>
      </a-card>
    </div>
  </div>
</template>

<style scoped>
.wb-overview {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.wb-hero {
  padding: 24px 28px;
  background: linear-gradient(135deg, #0f1011 0%, #1a1c2e 100%);
  border-radius: var(--wb-radius-lg);
  color: #f7f8f8;
}
.wb-hero-title {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.5px;
  margin-bottom: 8px;
}
.wb-hero-desc {
  font-size: 13px;
  color: #8a8f98;
  line-height: 1.7;
}

.wb-stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.wb-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.wb-section-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.wb-nav-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.wb-analysis-card {
  padding: 4px;
}
.wb-analysis-stats {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 8px 0 16px;
  border-bottom: 1px solid var(--wb-border);
  margin-bottom: 16px;
}
.wb-analysis-stat {
  flex: 1;
  text-align: center;
}
.wb-analysis-stat-val {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.5px;
  display: block;
}
.wb-analysis-stat-label {
  font-size: 12px;
  color: var(--wb-text-tertiary);
  margin-top: 2px;
  display: block;
}
.wb-analysis-divider {
  width: 1px;
  height: 32px;
  background: var(--wb-border);
}
.wb-analysis-block {
  margin-bottom: 14px;
}
.wb-analysis-label {
  font-size: 12px;
  color: var(--wb-text-tertiary);
  margin-bottom: 8px;
  font-weight: 500;
}
.wb-analysis-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.wb-analysis-list {
  margin: 0;
  padding-left: 18px;
  list-style: none;
}
.wb-analysis-list li {
  font-size: 13px;
  color: var(--wb-text-secondary);
  margin-bottom: 4px;
  position: relative;
}
.wb-analysis-list li::before {
  content: '→';
  position: absolute;
  left: -16px;
  color: var(--wb-accent);
}
.wb-analysis-cron-issue {
  font-size: 13px;
  color: #e5484d;
  margin-bottom: 2px;
}

.wb-timeline-item {
  display: flex;
  gap: 10px;
  align-items: baseline;
}
.wb-timeline-time {
  font-family: var(--wb-font-mono);
  font-size: 12px;
  color: var(--wb-text-tertiary);
  white-space: nowrap;
}
.wb-timeline-subject {
  font-size: 13px;
  color: var(--wb-text-secondary);
}
</style>
