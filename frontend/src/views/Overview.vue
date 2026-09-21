<script setup>
import { ref, computed, onMounted } from 'vue'
import { getTodayOverview, listDailyDates, getDailyReport, runDailyDigest, getQtDocs } from '@/api'
import { message } from 'ant-design-vue'
import { marked } from 'marked'

// ── Markdown 渲染 ──
marked.setOptions({ gfm: true, breaks: true })
function md(src) {
  if (!src) return ''
  return marked.parse(src)
}

const overview = ref(null)
const loading = ref(false)
const dailyDates = ref([])
const dailyContent = ref(null)
const dailyLoading = ref(false)
const dailyRunning = ref(false)

// ── 今日群文档 ──
const todayDocs = ref([])
const todayDocsLoading = ref(false)

const WEEKDAYS = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']

const dateChinese = computed(() => {
  const d = overview.value?.date
  if (!d) return ''
  const dt = new Date(d + 'T00:00:00')
  return `${dt.getFullYear()}年${dt.getMonth() + 1}月${dt.getDate()}日 ${WEEKDAYS[dt.getDay()]}`
})

const totalEvents = computed(() => {
  const ev = overview.value?.events_by_source || {}
  return Object.values(ev).reduce((sum, n) => sum + (Number(n) || 0), 0)
})

const sourceTags = computed(() => {
  const ev = overview.value?.events_by_source || {}
  const map = [
    { key: 'git', label: 'Git 提交', icon: '🔧' },
    { key: 'browser', label: '浏览器', icon: '🌐' },
    { key: 'files', label: '文件', icon: '📁' },
    { key: 'qingtui', label: '轻推', icon: '💬' },
  ]
  return map.map(m => ({ ...m, count: Number(ev[m.key]) || 0 }))
})

const statCards = computed(() => {
  const o = overview.value || {}
  return [
    { label: '@提及', value: o.mention_count || 0, icon: '💬', color: '#5e6ad2' },
    { label: '今日事件', value: totalEvents.value, icon: '⚡', color: '#27a644' },
    { label: '活跃项目', value: (o.active_projects || []).length, icon: '🗂️', color: '#f5a623' },
    { label: '采集次数', value: o.collection_runs_today || 0, sub: o.next_collection ? `下次 ${o.next_collection}` : '', icon: '🔄', color: '#e5484d' },
  ]
})

const navItems = [
  { href: '/skills', icon: '🧩', title: 'Skill 能力', desc: '能力墙' },
  { href: '/projects', icon: '🗂️', title: '应用与项目', desc: '启动 / 停止' },
  { href: '/timeline', icon: '🕐', title: '时间线', desc: '事件流' },
  { href: '/automation', icon: '🔄', title: '自动化', desc: '定时任务' },
  { href: '/qingtui', icon: '💬', title: '轻推工作', desc: '会话总结' },
  { href: '/wiki', icon: '📚', title: '知识库', desc: 'wiki 查询' },
  { href: '/reports', icon: '📅', title: '周报', desc: '每周回顾' },
  { href: '/system', icon: '⚙️', title: '系统设置', desc: '环境自检' },
]

async function load() {
  loading.value = true
  try {
    const d = await getTodayOverview()
    if (d?.ok) {
      overview.value = d
    } else {
      message.error(d?.error || '加载总览失败')
    }
  } catch (e) {
    message.error('加载总览失败: ' + (e?.message || e))
  } finally {
    loading.value = false
  }
}

async function loadDaily() {
  dailyLoading.value = true
  try {
    const d = await listDailyDates()
    // d.dates 可能是字符串数组或对象数组 ({date, has_lifeos, ...}), 按时间倒序取最近14天
    const raw = (d.dates || []).map(x => typeof x === 'string' ? x : x.date)
    dailyDates.value = raw.slice(-14).reverse()
    // 自动加载最近一天的日报内容
    if (dailyDates.value.length) {
      const latest = dailyDates.value[0]
      const r = await getDailyReport(latest)
      if (r?.ok)
        dailyContent.value = { date: latest, ...r }
    }
  }
  catch { /* ignore */ }
  finally {
    dailyLoading.value = false
  }
}

async function viewDaily(date) {
  dailyLoading.value = true
  try {
    const r = await getDailyReport(date)
    if (r?.ok)
      dailyContent.value = { date, ...r }
    else
      message.warning(r?.error || `${date} 无日报数据`)
  }
  catch (e) {
    message.error('加载日报失败')
  }
  finally {
    dailyLoading.value = false
  }
}

async function doRunDigest() {
  dailyRunning.value = true
  try {
    const r = await runDailyDigest()
    if (r?.ok)
      message.success(r.msg || '已触发日结')
    else
      message.error(r?.error || '触发失败')
  }
  catch {
    message.error('触发日结失败')
  }
  finally {
    dailyRunning.value = false
  }
}

async function loadTodayDocs() {
  todayDocsLoading.value = true
  try {
    const today = new Date().toISOString().slice(0, 10)
    const d = await getQtDocs(1, today)
    todayDocs.value = d.ok ? (d.docs || []) : []
  } catch (e) { todayDocs.value = [] }
  finally { todayDocsLoading.value = false }
}

function openDoc(url) {
  window.open(url, '_blank', 'noopener,noreferrer')
}

onMounted(() => {
  load()
  loadDaily()
  loadTodayDocs()
})
</script>

<template>
  <div class="ov">
    <!-- Header -->
    <div class="ov-header">
      <h2 class="ov-header-title">📊 总览</h2>
      <a-button size="small" :loading="loading" @click="load">刷新</a-button>
    </div>

    <!-- Hero -->
    <div class="ov-hero">
      <div class="ov-hero-date">{{ dateChinese || '今天' }}</div>
      <div class="ov-hero-sub">
        {{ overview?.ai_one_liner || '今天暂无数据，稍后自动采集' }}
      </div>
    </div>

    <!-- Stat Cards -->
    <div class="ov-stat-grid">
      <div v-for="s in statCards" :key="s.label" class="ov-card ov-stat-card">
        <div class="ov-stat-icon" :style="{ color: s.color }">{{ s.icon }}</div>
        <div>
          <div class="ov-stat-value" :style="{ color: s.color }">{{ s.value }}</div>
          <div class="ov-stat-label">
            {{ s.label }}<template v-if="s.sub"> · {{ s.sub }}</template>
          </div>
        </div>
      </div>
    </div>

    <!-- 待关注 -->
    <div v-if="overview && overview.mention_count > 0" class="ov-card">
      <div class="ov-card-title">👀 待关注</div>
      <div v-for="(m, i) in overview.mention_samples" :key="i" class="ov-mention">
        <span class="ov-mention-time">{{ m.time }}</span>
        <span class="ov-mention-session">{{ m.session }}</span>
        <span class="ov-mention-text">{{ m.text }}</span>
      </div>
    </div>

    <!-- 今日事件分布 -->
    <div class="ov-card">
      <div class="ov-card-title">📈 今日事件分布</div>
      <div class="ov-tags">
        <a-tag v-for="s in sourceTags" :key="s.key" color="blue" style="font-size: 12px; padding: 2px 10px">
          {{ s.icon }} {{ s.label }} {{ s.count }}
        </a-tag>
      </div>
    </div>

    <!-- 活跃项目 -->
    <div class="ov-card">
      <div class="ov-card-title">🚀 活跃项目</div>
      <div class="ov-tags">
        <a-tag
          v-for="p in (overview?.active_projects || [])"
          :key="p"
          color="green"
          style="font-size: 12px; padding: 2px 10px"
        >
          {{ p }}
        </a-tag>
      </div>
    </div>

    <!-- 每日日结 (second-brain-daily) -->
    <div class="ov-card">
      <div class="ov-card-title-row">
        <span class="ov-card-title">📅 每日日结</span>
        <a-tag v-if="dailyContent" color="gold" style="font-size: 11px">{{ dailyContent.date }}</a-tag>
        <div style="flex: 1"></div>
        <a-button type="primary" size="small" :loading="dailyRunning" @click="doRunDigest">
          ▶ 立即生成
        </a-button>
      </div>
      <!-- 日期选择条 -->
      <div v-if="dailyDates.length" class="ov-daily-dates">
        <a-tag
          v-for="d in dailyDates.slice(0, 10)"
          :key="d"
          :color="d === dailyContent?.date ? 'gold' : 'default'"
          style="font-size: 11px; cursor: pointer"
          @click="viewDaily(d)"
        >
          {{ d.slice(5) }}
        </a-tag>
      </div>
      <!-- AI 回顾内容 (Markdown 渲染) -->
      <div v-if="dailyLoading" class="ov-daily-loading">
        <a-spin size="small" />
      </div>
      <div v-else-if="dailyContent?.ai_review" class="ov-daily-content md-body" v-html="md(dailyContent.ai_review)"></div>
      <div v-else-if="dailyContent && !dailyContent.ai_review" class="ov-daily-empty">
        {{ dailyContent.date }} 的日报暂无 AI 回顾段
      </div>
      <a-empty v-else description="尚无日结报告" style="padding: 20px 0" />
    </div>

    <!-- 今日群文档 -->
    <div class="ov-card">
      <div class="ov-card-title-row">
        <span class="ov-card-title">📄 今日群文档</span>
        <a-tag v-if="todayDocs.length" color="blue" style="font-size: 11px">{{ todayDocs.length }} 个</a-tag>
        <div style="flex: 1"></div>
        <a href="/qingtui" class="ov-doc-more">查看全部 →</a>
      </div>
      <a-spin :spinning="todayDocsLoading" size="small">
        <div v-if="todayDocs.length" class="ov-doc-list">
          <div
            v-for="(doc, i) in todayDocs.slice(0, 8)"
            :key="i"
            class="ov-doc-item"
            @click="openDoc(doc.url)"
          >
            <a-tag :color="doc.type === 'drive' ? 'cyan' : doc.type === 'article' ? 'blue' : doc.type === 'minmetals' ? 'magenta' : 'default'" size="small">{{ doc.type_label }}</a-tag>
            <span class="ov-doc-title">{{ doc.title || doc.url.slice(0, 40) }}</span>
            <span class="ov-doc-chat">{{ (doc.chat_names || []).join('、') }}</span>
          </div>
          <div v-if="todayDocs.length > 8" class="ov-doc-extra">
            还有 {{ todayDocs.length - 8 }} 个文档…
          </div>
        </div>
        <a-empty v-else-if="!todayDocsLoading" description="今日暂无群文档" style="padding: 16px 0" />
      </a-spin>
    </div>

    <!-- Navigation Grid -->
    <div class="ov-card">
      <div class="ov-card-title">🧭 功能导航</div>
      <div class="ov-nav-grid">
        <a v-for="n in navItems" :key="n.href" :href="n.href" class="ov-nav-card">
          <div class="ov-nav-icon">{{ n.icon }}</div>
          <div class="ov-nav-title">{{ n.title }}</div>
          <div class="ov-nav-desc">{{ n.desc }}</div>
        </a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ov {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ov-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.ov-header-title {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.5px;
  margin: 0;
}

.ov-hero {
  padding: 24px 28px;
  background: linear-gradient(135deg, #0f1011, #1a1c2e);
  border-radius: 10px;
  color: #f7f8f8;
}
.ov-hero-date {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.5px;
  margin-bottom: 8px;
}
.ov-hero-sub {
  font-size: 13px;
  color: #b8bcc4;
  line-height: 1.7;
}

.ov-card {
  background: #fff;
  border: 1px solid #eef0f3;
  border-radius: 10px;
  padding: 16px 20px;
}

.ov-card-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
}

.ov-stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}
.ov-stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
}
.ov-stat-icon {
  font-size: 22px;
}
.ov-stat-value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.5px;
}
.ov-stat-label {
  font-size: 12px;
  color: #8a8f98;
  margin-top: 2px;
}

.ov-mention {
  display: flex;
  gap: 10px;
  align-items: baseline;
  padding: 6px 0;
  border-bottom: 1px solid #f2f4f7;
}
.ov-mention:last-child {
  border-bottom: none;
}
.ov-mention-time {
  font-size: 12px;
  color: #8a8f98;
  white-space: nowrap;
}
.ov-mention-session {
  font-size: 12px;
  color: #5e6ad2;
  white-space: nowrap;
}
.ov-mention-text {
  font-size: 13px;
  color: #3b3f46;
}

.ov-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.ov-nav-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}
.ov-nav-card {
  display: block;
  text-decoration: none;
  padding: 12px;
  border: 1px solid #eef0f3;
  border-radius: 8px;
  background: #fafbfc;
  transition: border-color 0.2s;
}
.ov-nav-card:hover {
  border-color: #5e6ad2;
}
.ov-nav-icon {
  font-size: 20px;
  margin-bottom: 6px;
}
.ov-nav-title {
  font-size: 13px;
  font-weight: 600;
  color: #2b2f36;
}
.ov-nav-desc {
  font-size: 12px;
  color: #8a8f98;
  margin-top: 2px;
}

.ov-card-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.ov-daily-dates {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #eef0f3;
}
.ov-daily-loading {
  display: flex;
  justify-content: center;
  padding: 24px 0;
}
.ov-daily-content {
  font-size: 13px;
  color: #4b5563;
  line-height: 1.8;
  max-height: 400px;
  overflow-y: auto;
  padding: 4px 0;
}
.ov-daily-empty {
  font-size: 13px;
  color: #9ca3af;
  padding: 20px 0;
  text-align: center;
}

/* 今日群文档 */
.ov-doc-more { font-size: 12px; color: #5e6ad2; text-decoration: none; }
.ov-doc-more:hover { text-decoration: underline; }
.ov-doc-list { display: flex; flex-direction: column; gap: 6px; }
.ov-doc-item {
  display: flex; align-items: center; gap: 8px; padding: 8px 10px;
  border-radius: 8px; cursor: pointer; transition: background .12s;
}
.ov-doc-item:hover { background: #f5f7fa; }
.ov-doc-title {
  flex: 1; font-size: 13px; color: #333;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ov-doc-chat { font-size: 11px; color: #999; flex-shrink: 0; }
.ov-doc-extra { font-size: 12px; color: #aaa; text-align: center; padding: 6px 0; }
</style>
