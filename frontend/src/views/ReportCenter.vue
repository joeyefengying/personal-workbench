<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import { marked } from 'marked'
import {
  listDailyDates, getDailyReport,
  listWeeklyReports, getWeeklyReport, exportWeeklyMarkdown, summarizeWeekly, writeWeeklyToLifeOS,
  listMonthlyReports, getMonthlyReport, exportMonthlyMarkdown, summarizeMonthly, writeMonthlyToLifeOS,
  listQuarterlyReports, getQuarterlyReport, summarizeQuarterly, writeQuarterlyToLifeOS,
  listYearlyReports, getYearlyReport, summarizeYearly, writeYearlyToLifeOS,
  listDocWeeks, previewWeeklyDoc, generateWeeklyDoc,
} from '@/api'

// ── Markdown 渲染 ──
marked.setOptions({ gfm: true, breaks: true })

function md(src) {
  if (!src) return ''
  return marked.parse(src)
}

// ── tab state ──
const activeTab = ref('daily')   // 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'yearly' | 'doc'
const loading = ref(false)

// ── daily state ──
const dailyDates = ref([])          // [{date, has_lifeos, event_count}]
const pickedDate = ref('')          // YYYY-MM-DD
const dailyReport = ref(null)
const dailyLoading = ref(false)
const showDetail = ref(false)       // 事件明细默认折叠

// ── 自建月历 ──
const calYear = ref(new Date().getFullYear())
const calMonth = ref(new Date().getMonth())   // 0-based

const lifeosDateSet = computed(() => new Set(dailyDates.value.filter(d => d.has_lifeos).map(d => d.date)))
const eventsDateSet = computed(() => new Set(dailyDates.value.map(d => d.date)))

// 日期 → 事件统计明细 (供 hover tooltip)
const dailyStatsMap = computed(() => {
  const m = {}
  for (const d of dailyDates.value) {
    m[d.date] = { has_lifeos: d.has_lifeos, event_count: d.event_count || 0, by_source: d.by_source || {}, ai_preview: d.ai_preview || '' }
  }
  return m
})

function calTooltipStats(ds) {
  const s = dailyStatsMap.value[ds]
  if (!s) return ''
  const b = s.by_source || {}
  const parts = []
  if (s.event_count) parts.push(`事件 ${s.event_count} 条`)
  if (b.git) parts.push(`提交 ${b.git}`)
  if (b.files) parts.push(`文件 ${b.files}`)
  if (b.browser) parts.push(`浏览 ${b.browser}`)
  if (b.qingtui) parts.push(`轻推 ${b.qingtui}`)
  return parts.join(' · ')
}

function calTooltipAi(ds) {
  const s = dailyStatsMap.value[ds]
  if (!s || !s.ai_preview) return ''
  return s.ai_preview
}

const calendarCells = computed(() => {
  const firstDay = new Date(calYear.value, calMonth.value, 1).getDay()  // 0=周日
  const daysInMonth = new Date(calYear.value, calMonth.value + 1, 0).getDate()
  const cells = []
  // 前置空白
  for (let i = 0; i < firstDay; i++) cells.push(null)
  // 当月日期
  for (let d = 1; d <= daysInMonth; d++) {
    const ds = `${calYear.value}-${String(calMonth.value + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    cells.push({
      day: d,
      date: ds,
      hasLifeos: lifeosDateSet.value.has(ds),
      hasEvents: eventsDateSet.value.has(ds),
      isToday: ds === new Date().toISOString().slice(0, 10),
      isPicked: ds === pickedDate.value,
    })
  }
  return cells
})

function prevMonth() {
  if (calMonth.value === 0) { calMonth.value = 11; calYear.value-- }
  else calMonth.value--
}
function nextMonth() {
  if (calMonth.value === 11) { calMonth.value = 0; calYear.value++ }
  else calMonth.value++
}
function pickDate(ds) {
  pickedDate.value = ds
}

// ── weekly state (same as before) ──
const weeks = ref([])
const months = ref([])
const quarters = ref([])
const years = ref([])
const activeWeek = ref('')
const activeMonth = ref('')
const activeQuarter = ref('')
const activeYear = ref('')
const report = ref(null)
const reportLoading = ref(false)
const aiSummary = ref('')
const aiLoading = ref(false)
const aiFailed = ref(false)
const aiCached = ref(false)
const aiAt = ref('')
const lifeosWriting = ref(false)
const exportVisible = ref(false)
const exportMd = ref('')
const exportLoading = ref(false)

// ── helpers ──
function fmtShort(d) {
  if (!d) return ''
  const p = d.split('-')
  return `${parseInt(p[1])}/${parseInt(p[2])}`
}

function fmtFull(d) {
  if (!d) return ''
  const [y, m, day] = d.split('-')
  return `${y}年${parseInt(m)}月${parseInt(day)}日`
}

// ── load list on mount ──
onMounted(async () => {
  await Promise.all([loadDailyDates(), loadWeeklyList()])
})

// ========== DAILY ==========

async function loadDailyDates() {
  try {
    const d = await listDailyDates()
    dailyDates.value = d.dates || []
    // default: latest date
    if (dailyDates.value.length > 0 && !pickedDate.value) {
      const latest = dailyDates.value[dailyDates.value.length - 1]
      pickedDate.value = latest.date
      loadDailyReport()
    }
    // 滚动日历到最新日期所在月份
    if (dailyDates.value.length > 0) {
      const latest = dailyDates.value[dailyDates.value.length - 1]
      const [y, m] = latest.date.split('-')
      calYear.value = +y
      calMonth.value = +m - 1
    }
  } catch { }
}

async function loadDailyReport() {
  if (!pickedDate.value) return
  dailyLoading.value = true
  dailyReport.value = null
  showDetail.value = false   // 切换日期时收起明细
  try {
    const d = await getDailyReport(pickedDate.value)
    if (d.ok) dailyReport.value = d
    else message.error(d.error || '加载失败')
  } catch { message.error('加载失败') }
  finally { dailyLoading.value = false }
}

watch(pickedDate, () => {
  if (activeTab.value === 'daily') loadDailyReport()
})

function onTabChange(key) {
  activeTab.value = key
  if (key === 'daily') loadDailyReport()
  else if (key === 'weekly' && !weeks.value.length) loadWeeklyList()
  else if (key === 'quarterly' && !quarters.value.length) loadQuarterlyList()
  else if (key === 'yearly' && !years.value.length) loadYearlyList()
  else if (key === 'doc' && !docWeeks.value.length) loadDocWeeks()
}

// ========== WEEKLY (same logic as WeeklyReport.vue) ==========

async function loadWeeklyList() {
  loading.value = true
  try {
    const [w, m] = await Promise.all([listWeeklyReports(), listMonthlyReports()])
    weeks.value = (w.weeks || []).reverse()
    months.value = (m.months || []).reverse()
    if (!activeWeek.value && weeks.value.length > 0) {
      activeWeek.value = weeks.value[0].week_label
      loadWeeklyReport()
    }
  } catch { }
  finally { loading.value = false }
}

async function loadWeeklyReport() {
  if (!activeWeek.value) return
  activeMonth.value = ''
  reportLoading.value = true
  report.value = null
  aiSummary.value = ''
  aiFailed.value = false
  aiCached.value = false
  aiAt.value = ''
  try {
    const d = await getWeeklyReport(activeWeek.value)
    if (d.ok) report.value = d.report
    else message.error(d.error || '加载失败')
  } catch { message.error('加载失败') }
  finally { reportLoading.value = false }
  if (report.value?.ai_summary) {
    aiSummary.value = report.value.ai_summary
    aiCached.value = true
    aiAt.value = report.value.ai_summary_at || ''
    return
  }
  loadWeeklyAi()
}

async function loadWeeklyAi(force = false) {
  if (!activeWeek.value || !report.value) return
  aiLoading.value = true
  aiFailed.value = false
  try {
    const d = await summarizeWeekly(activeWeek.value, force)
    if (d.ok && d.summary) {
      aiSummary.value = d.summary
      aiCached.value = !!d.cached
      aiAt.value = d.at || ''
    } else { aiFailed.value = true }
  } catch { aiFailed.value = true }
  finally { aiLoading.value = false }
}

async function doWeeklyLifeOS() {
  lifeosWriting.value = true
  try {
    const d = await writeWeeklyToLifeOS(activeWeek.value)
    if (d.ok) message.success(`已写入 LifeOS（${d.action === 'replace' ? '更新' : '新建'}）`)
    else message.error(d.error || '写入失败')
  } catch (e) { message.error('写入失败: ' + (e?.message || e)) }
  finally { lifeosWriting.value = false }
}

async function doWeeklyExport() {
  exportLoading.value = true
  exportVisible.value = true
  try {
    const d = await exportWeeklyMarkdown(activeWeek.value)
    if (d.ok) exportMd.value = d.markdown || ''
    else message.error(d.error || '导出失败')
  } catch { message.error('导出失败') }
  finally { exportLoading.value = false }
}

function copyMd() {
  navigator.clipboard.writeText(exportMd.value).then(() => {
    message.success('已复制到剪贴板')
  }).catch(() => message.error('复制失败，请手动复制'))
}

const topChannels = computed(() => {
  const byChannel = report.value?.qingtui?.by_channel
  if (!byChannel) return []
  return Object.entries(byChannel)
    .map(([name, info]) => ({ name, count: info.count || 0 }))
    .sort((a, b) => b.count - a.count)
})

const topProjects = computed(() => {
  const byProject = report.value?.git?.by_project
  if (!byProject) return []
  return Object.entries(byProject)
    .map(([name, info]) => ({ name, count: info.count || 0, commits: info.commits || [] }))
    .sort((a, b) => b.count - a.count)
})

// ========== MONTHLY ==========

async function loadMonthlyReport() {
  if (!activeMonth.value) return
  activeWeek.value = ''
  reportLoading.value = true
  report.value = null
  aiSummary.value = ''
  aiFailed.value = false
  aiCached.value = false
  aiAt.value = ''
  try {
    const d = await getMonthlyReport(activeMonth.value)
    if (d.ok) report.value = d.report
    else message.error(d.error || '加载失败')
  } catch { message.error('加载失败') }
  finally { reportLoading.value = false }
  if (report.value?.ai_summary) {
    aiSummary.value = report.value.ai_summary
    aiCached.value = true
    aiAt.value = report.value.ai_summary_at || ''
    return
  }
  loadMonthlyAi()
}

async function loadMonthlyAi(force = false) {
  if (!activeMonth.value || !report.value) return
  aiLoading.value = true
  aiFailed.value = false
  try {
    const d = await summarizeMonthly(activeMonth.value, force)
    if (d.ok && d.summary) {
      aiSummary.value = d.summary
      aiCached.value = !!d.cached
      aiAt.value = d.at || ''
    } else { aiFailed.value = true }
  } catch { aiFailed.value = true }
  finally { aiLoading.value = false }
}

async function doMonthlyLifeOS() {
  lifeosWriting.value = true
  try {
    const d = await writeMonthlyToLifeOS(activeMonth.value)
    if (d.ok) message.success(`已写入 LifeOS（${d.action === 'replace' ? '更新' : '新建'}）`)
    else message.error(d.error || '写入失败')
  } catch (e) { message.error('写入失败: ' + (e?.message || e)) }
  finally { lifeosWriting.value = false }
}

async function doMonthlyExport() {
  exportLoading.value = true
  exportVisible.value = true
  try {
    const d = await exportMonthlyMarkdown(activeMonth.value)
    if (d.ok) exportMd.value = d.markdown || ''
    else message.error(d.error || '导出失败')
  } catch { message.error('导出失败') }
  finally { exportLoading.value = false }
}

// ========== QUARTERLY / YEARLY ==========

async function loadQuarterlyList() {
  loading.value = true
  try {
    const d = await listQuarterlyReports()
    quarters.value = (d.quarters || []).reverse()
    if (!activeQuarter.value && quarters.value.length > 0) {
      activeQuarter.value = quarters.value[0].quarter
      loadQuarterlyReport()
    }
  } catch { }
  finally { loading.value = false }
}

async function loadYearlyList() {
  loading.value = true
  try {
    const d = await listYearlyReports()
    years.value = (d.years || []).reverse()
    if (!activeYear.value && years.value.length > 0) {
      activeYear.value = years.value[0].year
      loadYearlyReport()
    }
  } catch { }
  finally { loading.value = false }
}

async function loadQuarterlyReport() {
  if (!activeQuarter.value) return
  reportLoading.value = true
  report.value = null
  aiSummary.value = ''
  aiFailed.value = false
  aiCached.value = false
  aiAt.value = ''
  try {
    const d = await getQuarterlyReport(activeQuarter.value)
    if (d.ok) report.value = d.report
    else message.error(d.error || '加载失败')
  } catch { message.error('加载失败') }
  finally { reportLoading.value = false }
  if (report.value?.ai_summary) {
    aiSummary.value = report.value.ai_summary
    aiCached.value = true
    aiAt.value = report.value.ai_summary_at || ''
    return
  }
  loadQuarterlyAi()
}

async function loadQuarterlyAi(force = false) {
  if (!activeQuarter.value || !report.value) return
  aiLoading.value = true
  aiFailed.value = false
  try {
    const d = await summarizeQuarterly(activeQuarter.value, force)
    if (d.ok && d.summary) {
      aiSummary.value = d.summary
      aiCached.value = !!d.cached
      aiAt.value = d.at || ''
    } else { aiFailed.value = true }
  } catch { aiFailed.value = true }
  finally { aiLoading.value = false }
}

async function doQuarterlyLifeOS() {
  lifeosWriting.value = true
  try {
    const d = await writeQuarterlyToLifeOS(activeQuarter.value)
    if (d.ok) message.success(`已写入 LifeOS（${d.action === 'replace' ? '更新' : '新建'}）`)
    else message.error(d.error || '写入失败')
  } catch (e) { message.error('写入失败: ' + (e?.message || e)) }
  finally { lifeosWriting.value = false }
}

async function loadYearlyReport() {
  if (!activeYear.value) return
  reportLoading.value = true
  report.value = null
  aiSummary.value = ''
  aiFailed.value = false
  aiCached.value = false
  aiAt.value = ''
  try {
    const d = await getYearlyReport(activeYear.value)
    if (d.ok) report.value = d.report
    else message.error(d.error || '加载失败')
  } catch { message.error('加载失败') }
  finally { reportLoading.value = false }
  if (report.value?.ai_summary) {
    aiSummary.value = report.value.ai_summary
    aiCached.value = true
    aiAt.value = report.value.ai_summary_at || ''
    return
  }
  loadYearlyAi()
}

async function loadYearlyAi(force = false) {
  if (!activeYear.value || !report.value) return
  aiLoading.value = true
  aiFailed.value = false
  try {
    const d = await summarizeYearly(activeYear.value, force)
    if (d.ok && d.summary) {
      aiSummary.value = d.summary
      aiCached.value = !!d.cached
      aiAt.value = d.at || ''
    } else { aiFailed.value = true }
  } catch { aiFailed.value = true }
  finally { aiLoading.value = false }
}

async function doYearlyLifeOS() {
  lifeosWriting.value = true
  try {
    const d = await writeYearlyToLifeOS(activeYear.value)
    if (d.ok) message.success(`已写入 LifeOS（${d.action === 'replace' ? '更新' : '新建'}）`)
    else message.error(d.error || '写入失败')
  } catch (e) { message.error('写入失败: ' + (e?.message || e)) }
  finally { lifeosWriting.value = false }
}

// ========== 工作周报 DOC ==========

const docWeeks = ref([])
const docWeekStart = ref('')          // 选中的周一 'YYYY-MM-DD'
const docPreview = ref(null)          // 预览数据
const docPreviewLoading = ref(false)
const docGenerating = ref(false)
const docAiSummary = ref('')          // 周报 AI 总结
const docAiLoading = ref(false)

function _fmtDateCn(d) {
  if (!d) return ''
  const [y, m, day] = d.split('-')
  return `${y}年${parseInt(m)}月${parseInt(day)}日`
}

// 计算上周一
function _lastMonday() {
  const now = new Date()
  const dow = (now.getDay() + 6) % 7  // 周一=0
  const monday = new Date(now)
  monday.setDate(now.getDate() - dow - 7)
  return monday.toISOString().slice(0, 10)
}

async function loadDocWeeks() {
  try {
    const d = await listDocWeeks()
    docWeeks.value = (d.weeks || []).slice(0, 20)  // 只显示最近 20 周
    if (!docWeekStart.value && docWeeks.value.length) {
      // 默认选上周一（最近的过去周一）
      const lastMon = _lastMonday()
      docWeekStart.value = docWeeks.value.includes(lastMon) ? lastMon : docWeeks.value[0]
      doDocPreview()
    }
  } catch { }
}

async function doDocPreview() {
  if (!docWeekStart.value) return
  docPreviewLoading.value = true
  docPreview.value = null
  docAiSummary.value = ''
  docAiLoading.value = true
  try {
    const d = await previewWeeklyDoc(docWeekStart.value)
    if (d.ok) docPreview.value = d
    else message.error(d.error || '预览失败')
  } catch (e) { message.error('预览失败: ' + (e?.message || e)) }
  finally { docPreviewLoading.value = false }

  // 同时加载周报 AI 总结
  try {
    const ws = new Date(docWeekStart.value)
    const iso = _isoWeek(ws)
    const r = await summarizeWeekly(iso.weekLabel, false)
    if (r.ok && r.summary) docAiSummary.value = r.summary
  } catch (e) { console.warn('[docAi] load failed:', e?.message || e) }
  finally { docAiLoading.value = false }
}

function _isoWeek(d) {
  const date = new Date(d)
  const tmp = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()))
  const dayNum = tmp.getUTCDay() || 7
  tmp.setUTCDate(tmp.getUTCDate() + 4 - dayNum)
  const yearStart = new Date(Date.UTC(tmp.getUTCFullYear(), 0, 1))
  const week = Math.ceil(((tmp - yearStart) / 86400000 + 1) / 7)
  return { year: tmp.getUTCFullYear(), week, weekLabel: `${tmp.getUTCFullYear()}-W${String(week).padStart(2, '0')}` }
}

async function doDocGenerate() {
  if (!docWeekStart.value) return
  docGenerating.value = true
  try {
    const d = await generateWeeklyDoc(docWeekStart.value)
    if (d.ok) {
      const paths = d.paths || []
      const existed = d.existing || []
      if (existed.length) message.warning('已存在该周周报，已覆盖重新生成')
      else message.success(`周报已生成：${d.filename}`)
      if (paths.length) {
        message.info(`已保存到 ${paths.length} 个位置`)
      }
    } else {
      message.error(d.error || '生成失败')
    }
  } catch (e) { message.error('生成失败: ' + (e?.message || e)) }
  finally { docGenerating.value = false }
}
</script>

<template>
  <div class="rc-page">
    <div class="rc-top">
      <h2 class="wb-page-title">📋 报告中心</h2>
      <div style="flex:1" />
      <a-button size="small" :loading="loading" @click="loadDailyDates(); loadWeeklyList()">刷新</a-button>
    </div>

    <!-- Tabs -->
    <a-tabs v-model:activeKey="activeTab" @change="onTabChange" class="rc-tabs">
      <a-tab-pane key="daily" tab="📅 日报" />
      <a-tab-pane key="weekly" tab="📈 周报" />
      <a-tab-pane key="monthly" tab="📊 月报" />
      <a-tab-pane key="quarterly" tab="📆 季报" />
      <a-tab-pane key="yearly" tab="📅 年报" />
      <a-tab-pane key="doc" tab="📄 工作周报" />
    </a-tabs>

    <!-- ===================== DAILY ===================== -->
    <div v-if="activeTab === 'daily'" class="rc-daily-layout">
      <!-- 左侧日历 (自建月历) -->
      <div class="rc-cal-area">
        <div class="rc-cal-head">
          <a-button size="small" type="text" @click="prevMonth">&lt;</a-button>
          <span class="rc-cal-title">{{ calYear }}年{{ calMonth + 1 }}月</span>
          <a-button size="small" type="text" @click="nextMonth">&gt;</a-button>
        </div>
        <div class="rc-cal-grid">
          <div class="rc-cal-dow" v-for="d in ['日','一','二','三','四','五','六']" :key="d">{{ d }}</div>
          <div
            v-for="(c, i) in calendarCells" :key="i"
            class="rc-cal-day"
            :class="{
              'rc-cal-null': c === null,
              'rc-cal-lifeos': c && c.hasLifeos,
              'rc-cal-events': c && !c.hasLifeos && c.hasEvents,
              'rc-cal-today': c && c.isToday,
              'rc-cal-picked': c && c.isPicked,
            }"
            @click="c && pickDate(c.date)"
          >
            <template v-if="c">
              <a-tooltip
                v-if="c.hasLifeos || c.hasEvents"
                placement="top"
                overlay-class-name="rc-cal-tip"
                color="#fff"
              >
                <template #title>
                  <div class="rc-tip">
                    <div class="rc-tip-date">{{ c.date }}</div>
                    <div class="rc-tip-stats" v-if="calTooltipStats(c.date)">
                      {{ calTooltipStats(c.date) }}
                    </div>
                    <div class="rc-tip-ai" v-if="calTooltipAi(c.date)">
                      🧠 {{ calTooltipAi(c.date) }}
                    </div>
                  </div>
                </template>
                <span class="rc-cal-num">{{ c.day }}</span>
              </a-tooltip>
              <span v-else class="rc-cal-num">{{ c.day }}</span>
            </template>
          </div>
        </div>
        <div class="rc-cal-legend">
          <span class="rc-leg-item"><span class="rc-leg-dot green" /> 有日报</span>
          <span class="rc-leg-item"><span class="rc-leg-dot gray" /> 有事件</span>
        </div>
      </div>

      <!-- 右侧日报内容 -->
      <div class="rc-daily-content" v-if="pickedDate">
        <div class="rc-header">
          <span class="rc-header-title">{{ fmtFull(pickedDate) }}</span>
          <a-tag v-if="dailyReport?.source === 'lifeos'" color="green">Obsidian</a-tag>
          <a-tag v-else-if="dailyReport?.source === 'events'" color="orange">事件聚合</a-tag>
        </div>

        <a-spin :spinning="dailyLoading">
          <!-- 无数据 -->
          <a-empty v-if="dailyReport?.source === 'none'" description="该日暂无数据" style="padding:40px 0" />

          <!-- LifeOS 日报展示 -->
          <template v-else-if="dailyReport?.source === 'lifeos'">
            <!-- AI 今日回顾 -->
            <div class="rc-card" v-if="dailyReport.ai_review">
              <div class="rc-card-hd">🧠 AI 今日回顾</div>
              <div class="rc-card-bd rc-ai-review md-body" v-html="md(dailyReport.ai_review)" />
            </div>

            <!-- 事件明细：tabs 包裹 -->
            <div class="rc-card" v-if="dailyReport.event_detail?.counts">
              <div class="rc-card-hd rc-detail-hd" @click="showDetail = !showDetail">
                <span>
                  📋 今日事件
                  · 提交 {{ dailyReport.event_detail.counts.git || 0 }}
                  · 文件 {{ dailyReport.event_detail.counts.files || 0 }}
                  · 浏览 {{ dailyReport.event_detail.counts.browser || 0 }}
                  · 轻推 {{ dailyReport.event_detail.counts.qingtui || 0 }}
                </span>
                <span class="rc-detail-toggle">{{ showDetail ? '收起 ▲' : '展开 ▼' }}</span>
              </div>
              <div v-if="showDetail" class="rc-card-bd" style="padding:0">
                <a-tabs size="small" class="rc-detail-tabs">
                  <a-tab-pane v-if="dailyReport.event_detail?.git" :tab="'🔧 提交 (' + (dailyReport.event_detail.counts.git || 0) + ')'" key="git">
                    <div class="rc-section-body md-body" v-html="md(dailyReport.event_detail.git)" style="max-height:400px;overflow-y:auto" />
                  </a-tab-pane>
                  <a-tab-pane v-if="dailyReport.event_detail?.files" :tab="'📁 文件 (' + (dailyReport.event_detail.counts.files || 0) + ')'" key="files">
                    <div class="rc-section-body md-body" v-html="md(dailyReport.event_detail.files)" style="max-height:400px;overflow-y:auto" />
                  </a-tab-pane>
                  <a-tab-pane v-if="dailyReport.event_detail?.browser" :tab="'🌐 浏览 (' + (dailyReport.event_detail.counts.browser || 0) + ')'" key="browser">
                    <div class="rc-section-body md-body" v-html="md(dailyReport.event_detail.browser)" style="max-height:400px;overflow-y:auto" />
                  </a-tab-pane>
                  <a-tab-pane v-if="dailyReport.event_detail?.qingtui" :tab="'💬 轻推 (' + (dailyReport.event_detail.counts.qingtui || 0) + ')'" key="qingtui">
                    <div class="rc-section-body md-body" v-html="md(dailyReport.event_detail.qingtui)" style="max-height:400px;overflow-y:auto" />
                  </a-tab-pane>
                </a-tabs>
              </div>
            </div>
          </template>

          <!-- 事件聚合兜底 -->
          <template v-else-if="dailyReport?.source === 'events'">
            <div class="rc-card">
              <div class="rc-card-hd">📊 当日概览</div>
              <div class="rc-card-bd rc-stats">
                <div class="rc-stat" v-for="s in [
                  {lbl:'@提及', v: dailyReport.overview?.mention_count||0, u:'次'},
                  {lbl:'事件', v: Object.values(dailyReport.overview?.events_by_source||{}).reduce((a,b)=>a+b,0), u:'条'},
                  {lbl:'项目', v: dailyReport.overview?.active_projects?.length||0, u:'个'},
                  {lbl:'采集', v: dailyReport.overview?.collection_runs_today||0, u:'次'},
                ]" :key="s.lbl">
                  <span class="rc-stat-v">{{ s.v }}</span>
                  <span class="rc-stat-l">{{ s.lbl }}</span>
                </div>
              </div>
            </div>
            <div class="rc-card" v-if="dailyReport.overview?.ai_one_liner">
              <div class="rc-card-hd">🤖 AI 一句话</div>
              <div class="rc-card-bd" style="font-size:14px;line-height:1.8;color:#333">
                {{ dailyReport.overview.ai_one_liner }}
              </div>
            </div>
            <div class="rc-card" v-if="dailyReport.overview?.active_projects?.length">
              <div class="rc-card-hd">📂 活跃项目</div>
              <div class="rc-card-bd rc-tags">
                <a-tag v-for="p in dailyReport.overview.active_projects" :key="p">{{ p }}</a-tag>
              </div>
            </div>
            <!-- 事件明细（折叠） -->
            <div class="rc-card" v-if="dailyReport.event_detail?.counts">
              <div class="rc-card-hd rc-detail-hd" @click="showDetail = !showDetail">
                <span>
                  📋 今日事件
                  <template v-if="dailyReport.event_detail?.counts">
                    · 提交 {{ dailyReport.event_detail.counts.git || 0 }}
                    · 文件 {{ dailyReport.event_detail.counts.files || 0 }}
                    · 浏览 {{ dailyReport.event_detail.counts.browser || 0 }}
                    · 轻推 {{ dailyReport.event_detail.counts.qingtui || 0 }}
                  </template>
                </span>
                <span class="rc-detail-toggle">{{ showDetail ? '收起 ▲' : '展开 ▼' }}</span>
              </div>
              <div v-if="showDetail" class="rc-card-bd" style="padding:0">
                <a-tabs size="small" class="rc-detail-tabs">
                  <a-tab-pane v-if="dailyReport.event_detail?.git" :tab="'🔧 提交 (' + (dailyReport.event_detail.counts.git || 0) + ')'" key="git">
                    <div class="rc-section-body md-body" v-html="md(dailyReport.event_detail.git)" style="max-height:400px;overflow-y:auto" />
                  </a-tab-pane>
                  <a-tab-pane v-if="dailyReport.event_detail?.files" :tab="'📁 文件 (' + (dailyReport.event_detail.counts.files || 0) + ')'" key="files">
                    <div class="rc-section-body md-body" v-html="md(dailyReport.event_detail.files)" style="max-height:400px;overflow-y:auto" />
                  </a-tab-pane>
                  <a-tab-pane v-if="dailyReport.event_detail?.browser" :tab="'🌐 浏览 (' + (dailyReport.event_detail.counts.browser || 0) + ')'" key="browser">
                    <div class="rc-section-body md-body" v-html="md(dailyReport.event_detail.browser)" style="max-height:400px;overflow-y:auto" />
                  </a-tab-pane>
                  <a-tab-pane v-if="dailyReport.event_detail?.qingtui" :tab="'💬 轻推 (' + (dailyReport.event_detail.counts.qingtui || 0) + ')'" key="qingtui">
                    <div class="rc-section-body md-body" v-html="md(dailyReport.event_detail.qingtui)" style="max-height:400px;overflow-y:auto" />
                  </a-tab-pane>
                </a-tabs>
              </div>
            </div>
          </template>
        </a-spin>
      </div>

      <!-- 未选择日期 -->
      <div v-else style="flex:1;display:flex;align-items:center;justify-content:center;color:#aaa;font-size:13px">
        请从日历中选择日期查看日报
      </div>
    </div>

    <!-- ===================== WEEKLY ===================== -->
    <div v-if="activeTab === 'weekly'" class="rc-wm-layout">
      <div class="rc-nav">
        <div class="rc-nav-head">周报</div>
        <div
          v-for="w in weeks" :key="w.week_label"
          class="rc-nav-item" :class="{ active: activeWeek === w.week_label }"
          @click="activeWeek = w.week_label; loadWeeklyReport()"
        >
          <span>{{ w.week_label }}</span>
          <span class="rc-nav-sub">{{ fmtShort(w.start) }}-{{ fmtShort(w.end) }}</span>
        </div>
      </div>
      <div class="rc-content" v-if="report">
        <WeeklyContent
          :report="report" :ai-summary="aiSummary" :ai-loading="aiLoading"
          :ai-failed="aiFailed" :ai-cached="aiCached" :ai-at="aiAt"
          :top-channels="topChannels" :top-projects="topProjects"
          :lifeos-writing="lifeosWriting"
          @regenerate="loadWeeklyAi(true)"
          @write-lifeos="doWeeklyLifeOS"
          @export="doWeeklyExport"
        />
      </div>
      <a-spin v-else :spinning="reportLoading" style="flex:1;padding-top:60px" />
    </div>

    <!-- ===================== MONTHLY ===================== -->
    <div v-if="activeTab === 'monthly'" class="rc-wm-layout">
      <div class="rc-nav">
        <div class="rc-nav-head">月报</div>
        <div
          v-for="m in months" :key="m.month"
          class="rc-nav-item" :class="{ active: activeMonth === m.month }"
          @click="activeMonth = m.month; loadMonthlyReport()"
        >
          <span>{{ m.month }}</span>
          <span class="rc-nav-sub">{{ fmtShort(m.start) }}-{{ fmtShort(m.end) }}</span>
        </div>
      </div>
      <div class="rc-content" v-if="report">
        <WeeklyContent
          :report="report" :ai-summary="aiSummary" :ai-loading="aiLoading"
          :ai-failed="aiFailed" :ai-cached="aiCached" :ai-at="aiAt"
          :top-channels="report.summary?.top_channels?.map(c=>({name:c.name,count:c.count}))||[]"
          :top-projects="report.summary?.top_projects?.map(p=>({name:p.name,count:p.count,commits:[]}))||[]"
          :lifeos-writing="lifeosWriting"
          @regenerate="loadMonthlyAi(true)"
          @write-lifeos="doMonthlyLifeOS"
          @export="doMonthlyExport"
        />
      </div>
      <a-spin v-else :spinning="reportLoading" style="flex:1;padding-top:60px" />
    </div>

    <!-- ===================== QUARTERLY ===================== -->
    <div v-if="activeTab === 'quarterly'" class="rc-wm-layout">
      <div class="rc-nav">
        <div class="rc-nav-head">季报</div>
        <div
          v-for="q in quarters" :key="q.quarter"
          class="rc-nav-item" :class="{ active: activeQuarter === q.quarter }"
          @click="activeQuarter = q.quarter; loadQuarterlyReport()"
        >
          <span>{{ q.quarter }}</span>
          <span class="rc-nav-sub">{{ q.month_count }} 个月 · {{ (q.months || []).join(', ') }}</span>
        </div>
      </div>
      <div class="rc-content" v-if="report">
        <WeeklyContent
          :report="report" :ai-summary="aiSummary" :ai-loading="aiLoading"
          :ai-failed="aiFailed" :ai-cached="aiCached" :ai-at="aiAt"
          :top-channels="report.summary?.top_channels?.map(c=>({name:c.name,count:c.count}))||[]"
          :top-projects="report.summary?.top_projects?.map(p=>({name:p.name,count:p.count,commits:[]}))||[]"
          :lifeos-writing="lifeosWriting"
          @regenerate="loadQuarterlyAi(true)"
          @write-lifeos="doQuarterlyLifeOS"
        />
      </div>
      <a-spin v-else :spinning="reportLoading" style="flex:1;padding-top:60px" />
    </div>

    <!-- ===================== YEARLY ===================== -->
    <div v-if="activeTab === 'yearly'" class="rc-wm-layout">
      <div class="rc-nav">
        <div class="rc-nav-head">年报</div>
        <div
          v-for="y in years" :key="y.year"
          class="rc-nav-item" :class="{ active: activeYear === y.year }"
          @click="activeYear = y.year; loadYearlyReport()"
        >
          <span>{{ y.year }}</span>
          <span class="rc-nav-sub">{{ y.month_count }} 个月</span>
        </div>
      </div>
      <div class="rc-content" v-if="report">
        <WeeklyContent
          :report="report" :ai-summary="aiSummary" :ai-loading="aiLoading"
          :ai-failed="aiFailed" :ai-cached="aiCached" :ai-at="aiAt"
          :top-channels="report.summary?.top_channels?.map(c=>({name:c.name,count:c.count}))||[]"
          :top-projects="report.summary?.top_projects?.map(p=>({name:p.name,count:p.count,commits:[]}))||[]"
          :lifeos-writing="lifeosWriting"
          @regenerate="loadYearlyAi(true)"
          @write-lifeos="doYearlyLifeOS"
        />
      </div>
      <a-spin v-else :spinning="reportLoading" style="flex:1;padding-top:60px" />
    </div>

    <!-- ===================== DOC 工作周报 ===================== -->
    <div v-if="activeTab === 'doc'" class="rc-doc-layout">
      <!-- 左侧：周选择 -->
      <div class="rc-nav">
        <div class="rc-nav-head">选择周</div>
        <div class="rc-nav-list">
          <div
            v-for="w in docWeeks" :key="w"
            class="rc-nav-item"
            :class="{ active: docWeekStart === w }"
            @click="docWeekStart = w; doDocPreview()"
          >
            <span>{{ _fmtDateCn(w) }}</span>
            <span class="rc-nav-sub">~ {{ _fmtDateCn(new Date(new Date(w).getTime() + 6*86400000).toISOString().slice(0,10)) }}</span>
          </div>
        </div>
      </div>

      <!-- 右侧：预览 + 操作 -->
      <div class="rc-content">
        <div class="rc-header" v-if="docWeekStart">
          <span class="rc-header-title">📄 工作周报 · {{ _fmtDateCn(docWeekStart) }} ~ {{ _fmtDateCn(new Date(new Date(docWeekStart).getTime() + 6*86400000).toISOString().slice(0,10)) }}</span>
          <a-space>
            <a-button size="small" @click="doDocPreview">刷新预览</a-button>
            <a-button size="small" type="primary" :loading="docGenerating" @click="doDocGenerate">
              📥 生成 DOC 文件
            </a-button>
          </a-space>
        </div>

        <a-spin :spinning="docPreviewLoading" tip="加载数据...">
          <template v-if="docPreview">
            <!-- 概览统计 -->
            <div class="rc-card" style="margin-bottom:14px">
              <div class="rc-card-hd">📊 数据概览</div>
              <div class="rc-card-bd rc-stats">
                <div class="rc-stat">
                  <span class="rc-stat-v">{{ docPreview.total_my_msgs }}</span>
                  <span class="rc-stat-l">我发言条数</span>
                </div>
                <div class="rc-stat" v-for="(span, gname) in docPreview.group_spans" :key="gname">
                  <span class="rc-stat-v" style="font-size:14px">{{ span[0] }}</span>
                  <span class="rc-stat-l">{{ gname }}</span>
                </div>
              </div>
            </div>

            <!-- 周报 AI 总结 -->
            <div class="rc-card" v-if="docPreview">
              <div class="rc-card-hd">🧠 周报 AI 总结</div>
              <div class="rc-card-bd">
                <a-spin :spinning="docAiLoading" size="small">
                  <div class="md-body" v-if="docAiSummary" v-html="md(docAiSummary)" />
                  <span v-else style="color:#888;font-size:13px">暂无 AI 总结</span>
                </a-spin>
              </div>
            </div>

            <!-- 每日明细 -->
            <div class="rc-card">
              <div class="rc-card-hd">📅 每日发言分组</div>
              <div class="rc-card-bd">
                <div v-for="(day_data, day) in docPreview.daily_summary" :key="day" style="margin-bottom:12px">
                  <div style="font-size:13px;font-weight:600;margin-bottom:4px;color:#1f2937">
                    {{ day }} ({{ day_data.total }} 条)
                  </div>
                  <div style="display:flex;flex-wrap:wrap;gap:4px">
                    <a-tag v-for="(cnt, gname) in day_data.groups" :key="gname" size="small" color="blue">
                      {{ gname }} · {{ cnt }}
                    </a-tag>
                    <a-tag v-if="!Object.keys(day_data.groups).length" size="small" color="default">其他</a-tag>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <!-- 未选择/无数据 -->
          <a-empty v-if="!docPreview && !docPreviewLoading" description="选择一周后自动预览" style="padding:60px 0" />
        </a-spin>
      </div>
    </div>

    <!-- Export Modal -->
    <a-modal v-model:open="exportVisible" title="导出 Markdown" width="680px" :footer="null">
      <a-spin :spinning="exportLoading">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
          <span style="font-size:13px;color:#888">可直接粘贴到汇报文档中</span>
          <a-button size="small" @click="copyMd" :disabled="!exportMd">复制</a-button>
        </div>
        <pre class="rc-md">{{ exportMd }}</pre>
      </a-spin>
    </a-modal>
  </div>
</template>

<!-- ── Weekly/Monthly content shared component ── -->
<script>
import { defineComponent, h } from 'vue'
import { marked } from 'marked'
import { Button as AButton, Tag as ATag } from 'ant-design-vue'

marked.setOptions({ gfm: true, breaks: true })

const WeeklyContent = defineComponent({
  name: 'WeeklyContent',
  components: { AButton, ATag },
  props: ['report','aiSummary','aiLoading','aiFailed','aiCached','aiAt','topChannels','topProjects','lifeosWriting'],
  emits: ['regenerate','writeLifeos','export'],
  setup(props, { emit }) {
    const summary = () => props.report?.summary || {}
    return () => {
      const s = summary()
      return h('div', { style: { display:'flex', flexDirection:'column', gap:'14px' } }, [
        // header
        h('div', { class: 'rc-header' },
          h('span', { class: 'rc-header-title' }, s.week_label || ''),
          h(AButton, { size:'small', onClick: () => emit('export') }, () => '导出 Markdown')
        ),
        // AI summary
        props.aiSummary
          ? h('div', { class: 'rc-card' },
              h('div', { class: 'rc-card-hd' }, [
                  h('span', { }, [
                    '🤖 AI 总结',
                    props.aiCached ? h(ATag, { color:'blue', style:'margin-left:6px' }, () => '已缓存') : null,
                    props.aiAt ? h('span', { class:'wr-ai-at' }, props.aiAt) : null,
                  ]),
                  h('span', { }, [
                    h(AButton, { size:'small', type:'text', loading: props.aiLoading, onClick: () => emit('regenerate') }, () => '重新生成'),
                    h(AButton, { size:'small', type:'primary', loading: props.lifeosWriting, onClick: () => emit('writeLifeos') }, () => '写入 LifeOS'),
                  ])
              ]),
              h('div', { class: 'rc-card-bd md-body', innerHTML: marked.parse(props.aiSummary || '') })
            )
          : props.aiLoading
            ? h('div', { class: 'rc-card' },
                h('div', { class: 'rc-card-hd' }, h('span', '🤖 AI 总结')),
                h('div', { class: 'rc-card-bd', style: 'color:#aaa' }, '正在生成总结…')
              )
            : props.aiFailed
              ? h('div', { class: 'rc-card rc-ai-empty' },
                  h('div', { class: 'rc-card-hd' }, h('span', '🤖 AI 总结')),
                  h('div', { class: 'rc-card-bd', style: 'display:flex;align-items:center;justify-content:space-between' }, [
                    h('span', { style: 'color:#e5484d;font-size:13px' }, 'AI 总结生成失败，可点击重试'),
                    h(AButton, { size:'small', type:'primary', loading: props.aiLoading, onClick: () => emit('regenerate') }, () => '🤖 重新生成'),
                  ])
                )
              : h('div', { class: 'rc-card rc-ai-empty' },
                  h('div', { class: 'rc-card-hd' }, h('span', '🤖 AI 总结')),
                  h('div', { class: 'rc-card-bd', style: 'display:flex;align-items:center;justify-content:space-between' }, [
                    h('span', { style: 'color:#999;font-size:13px' }, '尚未生成 AI 总结，点击右侧按钮一键生成'),
                    h(AButton, { size:'small', type:'primary', loading: props.aiLoading, onClick: () => emit('regenerate') }, () => '🤖 生成 AI 总结'),
                  ])
                ),
        // stats
        h('div', { class: 'rc-card' }, [
          h('div', { class: 'rc-card-hd' }, '📊 概览'),
          h('div', { class: 'rc-card-bd rc-stats' }, [
            h('div', { class: 'rc-stat' }, [h('span',{class:'rc-stat-v'},s.qingtui_msgs||0), h('span',{class:'rc-stat-l'},'轻推消息')]),
            h('div', { class: 'rc-stat' }, [h('span',{class:'rc-stat-v'},s.git_commits||0), h('span',{class:'rc-stat-l'},'Git 提交')]),
            h('div', { class: 'rc-stat' }, [h('span',{class:'rc-stat-v'},s.active_projects||0), h('span',{class:'rc-stat-l'},'活跃项目')]),
            h('div', { class: 'rc-stat' }, [h('span',{class:'rc-stat-v'},s.active_channels||0), h('span',{class:'rc-stat-l'},'群聊')]),
          ])
        ]),
        // channels
        props.topChannels.length ? h('div', { class:'rc-card' }, [
          h('div', { class:'rc-card-hd' }, `💬 轻推消息 · ${s.qingtui_msgs || 0} 条`),
          h('div', { class:'rc-card-bd' }, props.topChannels.map(c =>
            h('div', { class:'rc-ch-row', key: c.name }, [
              h('span',{class:'rc-ch-name'},c.name),
              h('span',{class:'rc-ch-cnt'},`${c.count}条`)
            ])
          ))
        ]) : null,
        // projects / git
        props.topProjects.length ? h('div', { class:'rc-card' }, [
          h('div', { class:'rc-card-hd' }, `🔧 Git 提交 · ${s.git_commits || 0} 次`),
          h('div', { class:'rc-card-bd' }, props.topProjects.map(p =>
            h('div', { class:'rc-git-proj', key: p.name }, [
              h('div', { class:'rc-git-name' }, `${p.name} · ${p.count} commits`),
              ...((p.commits||[]).slice(0,5).map(c =>
                h('div', { class:'rc-line' }, [
                  h('span',{class:'rc-line-t'},(c.when||'').slice(5)),
                  h('span',{class:'rc-line-txt'},c.subject),
                ])
              )),
              (p.commits||[]).length > 5
                ? h('div',{class:'rc-more'},`& ${p.commits.length - 5} 条`)
                : null,
            ])
          ))
        ]) : null,
      ])
    }
  }
})

export default { components: { WeeklyContent } }
</script>

<style scoped>
/* ── page ── */
.rc-page { max-width: 1100px; margin: 0 auto; }
.rc-top { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }

.rc-tabs { margin-bottom: 16px; }
.rc-tabs :deep(.ant-tabs-nav) { margin-bottom: 0 !important; }

/* ── daily layout ── */
.rc-daily-layout { display: flex; gap: 16px; align-items: flex-start; }
.rc-cal-area { width: 280px; flex-shrink: 0; }

/* ── 自建月历 ── */
.rc-cal-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 6px; padding: 0 2px;
}
.rc-cal-title { font-size: 14px; font-weight: 600; color: #1f2937; }
.rc-cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
  background: #fff;
  border: 1px solid #eef0f3;
  border-radius: 10px;
  overflow: hidden;
  padding: 4px;
}
.rc-cal-dow {
  text-align: center; font-size: 11px; color: #aaa; font-weight: 500;
  padding: 6px 0;
}
.rc-cal-day {
  aspect-ratio: 1;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; color: #333; border-radius: 6px;
  cursor: pointer; transition: all .12s;
  position: relative;
}
.rc-cal-day:hover { background: #f0f3ff; }
.rc-cal-null { cursor: default; background: transparent; }
.rc-cal-null:hover { background: transparent; }
.rc-cal-lifeos { background: #e6fffb; color: #08964c; font-weight: 600; }
.rc-cal-events { background: #f5f5f5; color: #666; }
.rc-cal-today { box-shadow: inset 0 0 0 2px #1677ff; }
.rc-cal-picked { background: #1677ff !important; color: #fff !important; font-weight: 600; }
.rc-cal-legend { display: flex; gap: 16px; padding: 8px 0 0 4px; font-size: 12px; color: #888; }
/* ── 日历格子文字居中 ── */
.rc-cal-num { display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; }
.rc-leg-item { display: flex; align-items: center; gap: 4px; }
.rc-leg-dot { width: 8px; height: 8px; border-radius: 50%; }
.rc-leg-dot.green { background: #52c41a; }
.rc-leg-dot.gray { background: #bbb; }

.rc-daily-content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 16px; }

/* ── weekly/monthly layout ── */
.rc-wm-layout { display: flex; gap: 14px; align-items: flex-start; }

/* ── doc weekly report layout ── */
.rc-doc-layout { display: flex; gap: 14px; align-items: flex-start; }
.rc-nav {
  width: 200px; flex-shrink: 0;
  background: #fff; border: 1px solid #eef0f3; border-radius: 10px; overflow: hidden;
  position: sticky; top: 16px;
  display: flex; flex-direction: column;
  max-height: calc(100vh - 140px);
}
.rc-nav-head {
  padding: 10px 16px; font-size: 12px; font-weight: 600; color: #888; border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}
.rc-nav .rc-nav-list {
  overflow-y: auto; flex: 1;
}
.rc-nav-item {
  display: flex; flex-direction: column; gap: 2px;
  padding: 10px 16px; cursor: pointer; font-size: 13px; color: #333;
  border-bottom: 1px solid #f7f7f7; transition: background .12s;
}
.rc-nav-item:hover { background: #f5f7fa; }
.rc-nav-item.active { background: #eef4ff; border-left: 3px solid #1677ff; font-weight: 500; }
.rc-nav-sub { font-size: 11px; color: #aaa; }

.rc-content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 16px; }

/* ── daily sections ── */
.rc-detail-hd { cursor: pointer; user-select: none; }
.rc-detail-hd:hover { background: #f0f2f5; }
.rc-detail-toggle { font-size: 12px; color: #1677ff; font-weight: 400; }
.rc-detail-tabs :deep(.ant-tabs-nav) { margin-bottom: 0 !important; padding-left: 8px; }
.rc-detail-tabs :deep(.ant-tabs-content) { padding: 8px 16px 12px; }
.rc-summary-card { background: #fafbfc; border: 1px solid #eee; }
.rc-summary-text { font-size: 13px; line-height: 1.7; color: #555; padding: 8px 12px; }
.rc-section-body { font-size: 13px; line-height: 1.8; color: #333; }
.rc-ai-review { font-size: 13px; line-height: 1.8; color: #333; max-height: 600px; overflow-y: auto; }

/* ── export md ── */
.rc-md {
  white-space: pre-wrap; word-break: break-word;
  font-size: 13px; line-height: 1.7; color: #333;
  max-height: 420px; overflow-y: auto;
  background: #fafbfc; border: 1px solid #eef0f3;
  border-radius: 8px; padding: 16px 20px;
}
</style>

<!-- non-scoped: portal Modal & AI card header, Markdown rendered body -->
<style>
.wr-ai-hd {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; font-size: 13px; font-weight: 600; color: #1f2937;
  background: #fafbfc; border-bottom: 1px solid #f0f0f0;
}
.wr-ai-body { padding: 14px 18px; font-size: 14px; line-height: 1.8; color: #333; }
.wr-ai-at { font-size: 11px; color: #aaa; margin-left: 8px; font-weight: 400; }

/* ── Markdown rendered content → 已提到全局 theme.css ── */

/* ── 日历 hover tooltip（非 scoped, tooltip 由 antdv teleport 到 body）── */
.ant-tooltip-inner.rc-cal-tip {
  background: #fff; color: #1f2937; font-size: 12px;
  padding: 8px 12px; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,.12);
  max-width: 320px;
}
.rc-tip-date { font-weight: 600; color: #1f2937; margin-bottom: 4px; }
.rc-tip-stats { color: #666; font-size: 11px; margin-bottom: 4px; }
.rc-tip-ai { color: #5e6ad2; font-size: 11px; line-height: 1.5; }
</style>