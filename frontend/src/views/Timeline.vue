<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import { marked } from 'marked'
import {
  getTimelineEvents, getTimelineStats, getTimelineDates,
  getTimelineDaily, triggerCollect,
  timelineCollectSync, timelineObsidianProjects, getTimelineChannels,
  triggerLifecycle, previewDailyReport, commitDailyReport,
} from '@/api'

// ── Markdown 渲染 ──
marked.setOptions({ gfm: true, breaks: true })
function md(src) {
  if (!src) return ''
  return marked.parse(src)
}

const dates = ref([])
const selectedDate = ref(new Date().toISOString().slice(0, 10))
const loading = ref(false)
const collecting = ref(false)

const events = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 200  // 加载够多才能做聚合

const stats = ref(null)
const statsLoading = ref(false)
const dailySummary = ref(null)
const dailyLoading = ref(false)
const channels = ref([])
const channelsLoading = ref(false)

// 日报预览弹窗
const reportVisible = ref(false)
const reportPreview = ref('')
const reportProjects = ref({})
const reportDate = ref('')
const reportLoading = ref(false)
const reportCommitting = ref(false)
const reportHasAi = ref(false)

// 帮助弹窗
const helpVisible = ref(false)

// 帮助文档里的管理命令
const helpCommands = [
  { label: '查看最近采集日志', cmd: 'tail -30 /tmp/workbench-collect.log' },
  { label: '手动触发一次采集', cmd: 'launchctl kickstart -k gui/$(id -u)/com.personal-workbench.collect' },
  { label: '暂停定时采集', cmd: 'launchctl unload ~/Library/LaunchAgents/com.personal-workbench.collect.plist' },
  { label: '恢复定时采集', cmd: 'launchctl load ~/Library/LaunchAgents/com.personal-workbench.collect.plist' },
]

function copyCmd(cmd) {
  navigator.clipboard.writeText(cmd).then(() => {
    message.success('已复制到剪贴板')
  }).catch(() => {
    message.error('复制失败，请手动复制')
  })
}

// 当前选中的维度 (all | git | browser | files | qingtui)
const activeSource = ref('all')

const SOURCE_META = {
  files:   { label: '文件变化', icon: '📁', color: '#1677ff' },
  browser: { label: '浏览器访问', icon: '🌐', color: '#13c2c2' },
  qingtui: { label: '轻推消息', icon: '💬', color: '#722ed1' },
  git:     { label: '代码提交', icon: '🔧', color: '#52c41a' },
}

// 按来源分组 + 聚合
const groupedBySource = computed(() => {
  const groups = { git: [], browser: [], files: [], qingtui: [] }
  for (const e of events.value) {
    if (groups[e.source])
      groups[e.source].push(e)
  }
  return groups
})

// 文件事件聚合: 按目录 + action
const fileAgg = computed(() => {
  const by = {}
  for (const e of (groupedBySource.value.files || [])) {
    const dir = (e.target || '').split('/').slice(0, -1).join('/') || '/'
    const key = dir + '|' + (e.action || '')
    if (!by[key]) by[key] = { dir, action: e.action, count: 0, sample: e.target }
    by[key].count++
  }
  return Object.values(by).sort((a, b) => b.count - a.count)
})

// 浏览器事件聚合: 按域名
const browserAgg = computed(() => {
  const by = {}
  for (const e of (groupedBySource.value.browser || [])) {
    const domain = (e.meta?.domain) || (e.target || '').replace(/^https?:\/\//, '').split('/')[0] || '?'
    if (!by[domain]) by[domain] = { domain, count: 0, sample: e.title }
    by[domain].count++
  }
  return Object.values(by).sort((a, b) => b.count - a.count)
})

// Git 聚合: 按 project + repo
const gitAgg = computed(() => {
  const by = {}
  for (const e of (groupedBySource.value.git || [])) {
    const project = e.target || '?'
    if (!by[project]) by[project] = { project, commits: [], count: 0 }
    by[project].commits.push(e)
    by[project].count++
  }
  return Object.values(by).sort((a, b) => b.count - a.count)
})

// 轻推聚合: 按群
const qingtuiAgg = computed(() => {
  const by = {}
  for (const e of (groupedBySource.value.qingtui || [])) {
    const session = e.target || e.meta?.session || '?'
    if (!by[session]) by[session] = { session, count: 0, samples: [] }
    by[session].count++
    if (by[session].samples.length < 4)
      by[session].samples.push(e.title)
  }
  return Object.values(by).sort((a, b) => b.count - a.count)
})

function formatTs(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
function shortTarget(t) {
  if (!t) return ''
  const parts = t.split('/')
  if (parts.length > 3) return '…/' + parts.slice(-2).join('/')
  return t.length > 50 ? '…' + t.slice(-47) : t
}

async function loadDates() {
  try {
    const d = await getTimelineDates()
    dates.value = d.dates || []
    if (dates.value.length && !dates.value.includes(selectedDate.value))
      selectedDate.value = dates.value[0]
  } catch {}
}

async function loadEvents() {
  loading.value = true
  try {
    const d = await getTimelineEvents({ date: selectedDate.value, limit: pageSize, offset: 0 })
    events.value = d.events || []
    total.value = d.total || 0
  } catch (e) {
    message.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  statsLoading.value = true
  try {
    const d = await getTimelineStats(selectedDate.value)
    stats.value = d.stats
  } catch {} finally { statsLoading.value = false }
}

async function loadDaily() {
  dailyLoading.value = true
  try {
    const d = await getTimelineDaily(selectedDate.value)
    if (d.ok) dailySummary.value = d.summary
  } catch {} finally { dailyLoading.value = false }
}

async function loadChannels() {
  channelsLoading.value = true
  try {
    const d = await getTimelineChannels()
    if (d.ok) channels.value = d.channels || []
  } catch {} finally { channelsLoading.value = false }
}

async function refreshAll() {
  await Promise.all([loadEvents(), loadStats(), loadDaily(), loadChannels()])
}

async function doCollect() {
  collecting.value = true
  try {
    const d = await timelineCollectSync()
    if (d.ok) {
      message.success(`采集完成 · 入库 ${d.result?.total_inserted || 0} 条`)
      await refreshAll(); await loadDates()
    } else { message.error(d.error || '采集失败') }
  } catch (e) { message.error('采集失败: ' + (e?.message || e)) }
  finally { collecting.value = false }
}

async function doCreateProjects() {
  try {
    const d = await timelineObsidianProjects()
    if (d.ok) message.success(d.msg || '项目已创建')
    else message.error(d.error || '创建失败')
  } catch (e) { message.error('创建失败: ' + (e?.message || e)) }
}

async function doLifecycle() {
  try {
    const d = await triggerLifecycle()
    if (d.ok) message.success(d.msg || '维护完成')
    else message.error(d.error || '维护失败')
  } catch (e) { message.error('维护失败: ' + (e?.message || e)) }
}

async function doPreviewReport() {
  reportLoading.value = true
  reportVisible.value = true
  try {
    const d = await previewDailyReport(selectedDate.value)
    if (d.ok) {
      reportPreview.value = d.preview_md || ''
      reportProjects.value = d.projects || {}
      reportDate.value = d.date
      reportHasAi.value = d.has_ai
      if (!d.preview_md && d.error) {
        message.warning(d.error)
      }
    } else {
      message.error(d.error || '预览失败')
    }
  } catch (e) { message.error('预览失败: ' + (e?.message || e)) }
  finally { reportLoading.value = false }
}

async function doCommitReport() {
  reportCommitting.value = true
  try {
    const summaries = {}
    for (const [proj, info] of Object.entries(reportProjects.value)) {
      summaries[proj] = info.summary_md
    }
    const d = await commitDailyReport(reportDate.value || selectedDate.value, summaries)
    if (d.ok) {
      reportVisible.value = false
      message.success(
        `日报已提交 · 更新 ${d.projects_updated || 0} 个项目`
        + (d.daily_path ? ` · 独立文件 ${d.daily_path.split('/').slice(-3).join('/')}` : '')
      )
      const errors = (d.results || []).filter(r => r.error)
      if (errors.length) {
        message.warning(`${errors.length} 个项目写入失败: ${errors.map(e => e.project).join(', ')}`)
      }
    } else {
      message.error(d.error || '提交失败')
    }
  } catch (e) { message.error('提交失败: ' + (e?.message || e)) }
  finally { reportCommitting.value = false }
}

onMounted(async () => { await loadDates(); refreshAll() })
watch(selectedDate, () => { page.value = 1; refreshAll() })
</script>

<template>
  <div class="tm-page">
    <!-- 顶栏 -->
    <div class="tm-top">
      <h2 class="wb-page-title">🕐 时间线</h2>
      <a-tag color="blue">{{ total }}</a-tag>
      <div class="tm-spacer" />
      <a-date-picker v-model:value="selectedDate" value-format="YYYY-MM-DD" size="small" :allow-clear="false" />
      <a-tooltip title="手动采集一次数据（系统已每小时自动采集，通常无需手动）">
        <a-button class="wb-btn" size="small" :loading="collecting" @click="doCollect">立即采集</a-button>
      </a-tooltip>
      <a-tooltip title="用 AI 汇总当天工作，预览确认后写入各项目 README">
        <a-button class="wb-btn" size="small" @click="doPreviewReport">生成日报</a-button>
      </a-tooltip>
      <a-tooltip title="为时间线里出现的新项目，在 Obsidian 中自动创建项目 README">
        <a-button class="wb-btn" size="small" @click="doCreateProjects">自动建项目</a-button>
      </a-tooltip>
      <a-popconfirm title="聚合到汇总层 + 清理30天前事件" @confirm="doLifecycle" ok-text="确认" cancel-text="取消">
        <a-tooltip title="压缩历史事件：聚合永久统计并删除30天前的原始事件，回收磁盘">
          <a-button class="wb-btn" size="small">数据维护</a-button>
        </a-tooltip>
      </a-popconfirm>
      <a-tooltip title="重新加载当前页数据">
        <a-button class="wb-btn" size="small" @click="refreshAll">刷新</a-button>
      </a-tooltip>
      <a-tooltip title="使用说明与常用命令">
        <a-button class="wb-btn" size="small" @click="helpVisible = true">❓ 帮助</a-button>
      </a-tooltip>
    </div>

    <!-- 指标条 -->
    <div class="tm-metrics" v-if="stats">
      <div class="tm-m">
        <span class="tm-m-num">{{ stats.total }}</span>
        <span class="tm-m-lbl">今日事件</span>
      </div>
      <div v-for="src in ['git','files','browser','qingtui']" :key="src" class="tm-m">
        <span class="tm-m-num" :style="{color: SOURCE_META[src]?.color}">{{ stats.by_source?.[src] || 0 }}</span>
        <span class="tm-m-lbl">{{ SOURCE_META[src]?.icon }} {{ SOURCE_META[src]?.label }}</span>
      </div>
    </div>

    <a-spin :spinning="loading">
      <!-- 左右分栏: 维度导航 + 内容卡片 -->
      <div class="tm-body" v-if="total">
        <!-- 左栏: 维度导航 -->
        <div class="tm-nav">
          <div class="tm-nav-head">维度</div>
          <div
            class="tm-nav-item" :class="{ active: activeSource === 'all' }"
            @click="activeSource = 'all'"
          >
            <span class="tm-nav-label">📊 全部</span>
            <span class="tm-nav-cnt">{{ total }}</span>
          </div>
          <div
            v-for="src in ['git','browser','files','qingtui']" :key="src"
            class="tm-nav-item" :class="{ active: activeSource === src }"
            @click="activeSource = src"
          >
            <span class="tm-nav-label">{{ SOURCE_META[src].icon }} {{ SOURCE_META[src].label }}</span>
            <span class="tm-nav-cnt">{{ groupedBySource[src].length }}</span>
          </div>

          <!-- 渠道状态 (左栏底部) -->
          <div class="tm-nav-ch" v-if="channels.length">
            <div class="tm-nav-sub">渠道状态</div>
            <div v-for="c in channels" :key="c.key" class="tm-nav-ch-i">
              <span :style="{color: c.status === 'ok' ? '#52c41a' : '#888'}">{{ c.status === 'ok' ? '●' : '○' }}</span>
              <span>{{ c.name }}</span>
            </div>
          </div>
        </div>

        <!-- 右栏: 选中的维度卡片 -->
        <div class="tm-content">
          <!-- Git 提交 -->
          <div class="tm-card" v-if="(activeSource === 'all' || activeSource === 'git') && gitAgg.length">
            <div class="tm-card-hd">🔧 代码提交 · {{ groupedBySource.git.length }} 个 commit</div>
            <div class="tm-card-bd">
              <div v-for="g in gitAgg" :key="g.project" class="tm-git-proj">
                <div class="tm-git-name">{{ g.project }}</div>
                <div v-for="(c, i) in g.commits.slice(0, 8)" :key="i" class="tm-line">
                  <span class="tm-line-t">{{ formatTs(c.ts) }}</span>
                  <a-tag size="small" color="green">commit</a-tag>
                  <span class="tm-line-txt">{{ c.title }}</span>
                </div>
                <div v-if="g.commits.length > 8" class="tm-more">& {{ g.commits.length - 8 }} 条提交</div>
              </div>
            </div>
          </div>

          <!-- 浏览器 -->
          <div class="tm-card" v-if="(activeSource === 'all' || activeSource === 'browser') && browserAgg.length">
            <div class="tm-card-hd">🌐 浏览器访问 · {{ groupedBySource.browser.length }} 次</div>
            <div class="tm-card-bd">
              <div v-for="d in browserAgg.slice(0, 20)" :key="d.domain" class="tm-line">
                <span class="tm-line-t">{{ d.count }}次</span>
                <span class="tm-line-txt">{{ d.domain }}</span>
                <span class="tm-line-sub">{{ d.sample }}</span>
              </div>
              <div v-if="browserAgg.length > 20" class="tm-more">& {{ browserAgg.length - 20 }} 个域名</div>
            </div>
          </div>

          <!-- 文件变化 -->
          <div class="tm-card" v-if="(activeSource === 'all' || activeSource === 'files') && fileAgg.length">
            <div class="tm-card-hd">📁 文件变化 · {{ groupedBySource.files.length }} 次操作 · {{ fileAgg.length }} 类</div>
            <div class="tm-card-bd">
              <div v-for="f in fileAgg" :key="f.dir + f.action" class="tm-line">
                <span class="tm-line-t">{{ f.count }}次</span>
                <a-tag size="small" :color="f.action === '修改' ? 'orange' : f.action === '新增' ? 'green' : 'red'">{{ f.action }}</a-tag>
                <span class="tm-line-txt">{{ shortTarget(f.dir) }}</span>
              </div>
            </div>
          </div>

          <!-- 轻推消息 -->
          <div class="tm-card" v-if="(activeSource === 'all' || activeSource === 'qingtui') && qingtuiAgg.length">
            <div class="tm-card-hd">💬 轻推消息 · {{ groupedBySource.qingtui.length }} 条发言 · {{ qingtuiAgg.length }} 个群</div>
            <div class="tm-card-bd">
              <div v-for="q in qingtuiAgg" :key="q.session" class="tm-q-row">
                <div class="tm-q-name">{{ q.session }} <span class="tm-q-cnt">{{ q.count }}条</span></div>
                <div v-for="(s, i) in q.samples" :key="i" class="tm-line tm-line--sm">
                  <span class="tm-line-txt">{{ s }}</span>
                </div>
                <div v-if="q.count > 4" class="tm-more">& {{ q.count - 4 }} 条</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <a-empty v-if="!total && !loading" description="暂无事件, 点击「立即采集」获取数据" style="padding:60px 0" />
    </a-spin>

    <!-- 日报预览弹窗 -->
    <a-modal
      v-model:open="reportVisible"
      :title="`日报预览 · ${reportDate || selectedDate}`"
      width="720px"
      destroy-on-close
    >
      <a-spin :spinning="reportLoading">
        <div v-if="!reportHasAi" class="wb-hp-report-banner">
          ⚠️ 未配置 DIANXIN_API_KEY，当前为规则聚合结果（非 AI 总结）
        </div>
        <div v-if="reportPreview" class="wb-hp-report-md md-body" v-html="md(reportPreview)"></div>
      </a-spin>
      <template #footer>
        <a-button @click="reportVisible = false">取消</a-button>
        <a-button
          type="primary"
          :loading="reportCommitting"
          :disabled="!reportPreview"
          @click="doCommitReport"
        >确认提交到项目 README</a-button>
      </template>
    </a-modal>

    <!-- 帮助弹窗 -->
    <a-modal
      v-model:open="helpVisible"
      title="🕐 时间线使用说明"
      width="640px"
      :footer="null"
    >
      <div class="wb-hp-wrap">
        <div class="wb-hp-section">
          <h4>📌 这个页面是做什么的</h4>
          <p>自动汇总你每天的工作记录（Git 提交、浏览器访问、文件改动、轻推消息），帮你一眼看清「今天干了什么」，并能一键生成 AI 日报写进 Obsidian 项目笔记。</p>
        </div>

        <div class="wb-hp-section">
          <h4>🔄 数据是怎么来的</h4>
          <ul>
            <li><b>自动采集</b>：系统每小时整点自动采集一次，无需手动操作。</li>
            <li><b>立即采集</b>：想马上看到最新数据时手动点一下（通常不需要）。</li>
            <li>采集日志：<code>/tmp/workbench-collect.log</code></li>
          </ul>
        </div>

        <div class="wb-hp-section">
          <h4>🔘 按钮说明</h4>
          <table class="wb-hp-table">
            <tbody>
              <tr><td>立即采集</td><td>手动触发一次数据采集</td></tr>
              <tr><td>生成日报</td><td>AI 汇总当天工作 → 预览 → 写入项目 README</td></tr>
              <tr><td>自动建项目</td><td>为时间线里出现的新项目创建 Obsidian 项目笔记</td></tr>
              <tr><td>数据维护</td><td>聚合历史统计 + 清理 30 天前原始事件</td></tr>
              <tr><td>刷新</td><td>重新加载当前页面数据</td></tr>
            </tbody>
          </table>
        </div>

        <div class="wb-hp-section">
          <h4>⌨️ 常用命令（终端）</h4>
          <div v-for="cmd in helpCommands" :key="cmd.cmd" class="wb-hp-cmd">
            <div class="wb-hp-cmd-label">{{ cmd.label }}</div>
            <div class="wb-hp-cmd-row">
              <code class="wb-hp-cmd-code">{{ cmd.cmd }}</code>
              <a-button size="small" type="text" @click="copyCmd(cmd.cmd)">复制</a-button>
            </div>
          </div>
        </div>

        <div class="wb-hp-section">
          <h4>📝 日报是怎么写的</h4>
          <p>「生成日报」会调用 AI（DeepSeek）把当天事件按项目归类并总结成几段话。你确认后，系统会在每个项目的 <code>README.md</code> 里插入 <code>## YYYY-MM-DD 日报</code> 章节，不会覆盖你已有的任务清单。</p>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<style scoped>
.tm-page { max-width: 1100px; margin: 0 auto; padding: 0; }
.tm-top { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.tm-spacer { flex: 1; }

/* 指标条 */
.tm-metrics {
  display: flex; gap: 0; margin-bottom: 16px;
  background: #fff; border: 1px solid #eef0f3; border-radius: 10px; overflow: hidden;
}
.tm-m {
  flex: 1; display: flex; align-items: baseline; gap: 8px; justify-content: center;
  padding: 10px 0; border-right: 1px solid #f0f0f0;
}
.tm-m:last-child { border-right: none; }
.tm-m-num { font-size: 22px; font-weight: 600; color: #1f2937; }
.tm-m-lbl { font-size: 12px; color: #888; }

/* 左右分栏 */
.tm-body { display: flex; gap: 14px; align-items: flex-start; }

/* 左栏: 维度导航 */
.tm-nav {
  width: 200px; flex-shrink: 0;
  background: #fff; border: 1px solid #eef0f3; border-radius: 10px; overflow: hidden;
  position: sticky; top: 16px;
}
.tm-nav-head {
  padding: 10px 16px; font-size: 12px; font-weight: 600; color: #888;
  border-bottom: 1px solid #f0f0f0;
}
.tm-nav-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; cursor: pointer; font-size: 13px; color: #333;
  border-bottom: 1px solid #f7f7f7; transition: background .12s;
}
.tm-nav-item:hover { background: #f5f7fa; }
.tm-nav-item.active { background: #eef4ff; border-left: 3px solid #1677ff; font-weight: 500; }
.tm-nav-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tm-nav-cnt {
  min-width: 24px; height: 20px; border-radius: 10px; font-size: 11px;
  background: #f0f0f0; color: #666; display: inline-flex; align-items: center; justify-content: center;
  padding: 0 7px;
}
.tm-nav-item.active .tm-nav-cnt { background: #1677ff; color: #fff; }

/* 渠道状态 (左栏底部) */
.tm-nav-ch { padding: 10px 16px 14px; border-top: 1px solid #f0f0f0; }
.tm-nav-sub { font-size: 11px; font-weight: 600; color: #aaa; margin-bottom: 6px; }
.tm-nav-ch-i {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: #666; padding: 3px 0;
}

/* 右栏: 内容卡片 */
.tm-content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 14px; }
.tm-card {
  background: #fff; border: 1px solid #eef0f3; border-radius: 10px; overflow: hidden;
}
.tm-card-hd {
  padding: 10px 16px; font-size: 13px; font-weight: 600; color: #1f2937;
  background: #fafbfc; border-bottom: 1px solid #f0f0f0;
}
.tm-card-bd { padding: 10px 16px 12px; }

/* 通用行 */
.tm-line {
  display: flex; align-items: baseline; gap: 8px;
  padding: 4px 6px; border-radius: 4px; font-size: 13px;
}
.tm-line:hover { background: rgba(0,0,0,.02); }
.tm-line--sm { font-size: 12px; padding: 2px 6px; }
.tm-line-t { color: #999; font-size: 11px; white-space: nowrap; font-variant-numeric: tabular-nums; }
.tm-line-txt { flex: 1; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tm-line-sub { color: #aaa; font-size: 12px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tm-more { font-size: 11px; color: #1677ff; padding: 2px 6px; cursor: default; }

/* Git */
.tm-git-proj { margin-bottom: 10px; }
.tm-git-name { font-size: 12px; font-weight: 600; color: #1f2937; margin-bottom: 4px; padding: 2px 6px; }

/* 轻推 */
.tm-q-row { margin-bottom: 10px; }
.tm-q-name { font-size: 12px; font-weight: 600; color: #1f2937; padding: 2px 6px; }
.tm-q-cnt { font-weight: 400; color: #888; margin-left: 6px; }

/* 按钮 */
.wb-btn {
  border-radius: 6px !important; font-weight: 500 !important;
  font-size: 12px !important; height: 28px !important; padding: 0 12px !important;
}
</style>

<style>
/* === Modal 弹窗内容样式 ===
   不能放在 scoped 块，因为 Ant Design Modal 通过 Portal 渲染到 body 根节点，
   scoped 选择器（带 data-v-xxx 属性选择器）无法命中弹窗内部的 DOM 节点 */
.wb-hp-wrap { line-height: 1.7; color: #333; }
.wb-hp-section { margin-bottom: 20px; }
.wb-hp-section h4 {
  font-size: 14px; font-weight: 600; color: #1f2937; margin: 0 0 8px;
}
.wb-hp-section p, .wb-hp-section li { font-size: 13px; color: #555; line-height: 1.7; }
.wb-hp-section ul { padding-left: 18px; margin: 0; }
.wb-hp-section li { margin-bottom: 4px; }
.wb-hp-section code {
  background: #eef1f5; padding: 1px 6px; border-radius: 3px; font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.wb-hp-table { width: 100%; border-collapse: collapse; }
.wb-hp-table td {
  padding: 6px 12px; font-size: 13px; border-bottom: 1px solid #f0f0f0;
}
.wb-hp-table td:first-child {
  font-weight: 500; color: #1f2937; width: 110px; white-space: nowrap;
}
.wb-hp-cmd { margin-bottom: 10px; }
.wb-hp-cmd-label { font-size: 12px; color: #888; margin-bottom: 3px; }
.wb-hp-cmd-row { display: flex; align-items: center; gap: 8px; }
.wb-hp-cmd-code {
  flex: 1; display: block; padding: 6px 12px; font-size: 12px;
  background: #f5f5f5; border: 1px solid #e0e0e0; border-radius: 6px;
  overflow-x: auto; white-space: nowrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.wb-hp-report-md {
  white-space: pre-wrap; word-break: break-word;
  font-size: 13px; line-height: 1.7; color: #333;
  max-height: 450px; overflow-y: auto;
  background: #fafbfc; border: 1px solid #eef0f3;
  border-radius: 8px; padding: 16px 20px;
}
.wb-hp-report-banner {
  background: #fff7e6; border: 1px solid #ffd591; border-radius: 6px;
  padding: 8px 14px; font-size: 12px; color: #ad6800; margin-bottom: 14px;
}
</style>