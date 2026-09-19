<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import { getQtStatus, getQtDailySummary, getQtTasks, getQtContext, getQtDocs } from '@/api'

const status = ref({ connected: false, state: 'unknown', hint: '' })
const date = ref(new Date().toISOString().slice(0, 10))
const activeTab = ref('messages')

const summary = ref(null)
const summaryLoading = ref(false)
const tasks = ref([])

// ── 群文档 ──
const docsData = ref(null)
const docsLoading = ref(false)
const docsDays = ref(7)
const docsTypeFilter = ref('')
const docsDate = ref(new Date().toISOString().slice(0, 10))

// 文档按日期分组 (computed)
const docsGrouped = computed(() => {
  if (!docsData.value?.docs) return []
  const grouped = {}
  for (const d of docsData.value.docs) {
    if (!grouped[d.date]) grouped[d.date] = []
    grouped[d.date].push(d)
  }
  return Object.entries(grouped)
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([date, docs]) => ({ date, docs }))
})

const docTypeColors = {
  article: 'blue',
  drive: 'cyan',
  excel: 'green',
  pdf: 'red',
  word: 'geekblue',
  markdown: 'purple',
  tencent_doc: 'orange',
  ones: 'volcano',
  oa: 'gold',
  minmetals: 'magenta',
  link: 'default',
  file: 'default',
}

// 左侧群列表选中项
const activeCid = ref(null)

// 当前群的消息流 (合并 @我/@所有人/我发言, 按时间正序)
const activeMessages = computed(() => {
  if (!summary.value || !activeCid.value)
    return []
  const g = summary.value.groups.find(x => x.cid === activeCid.value)
  if (!g)
    return []
  const all = []
  g.mention.forEach(h => all.push({ ...h, kind: 'mention' }))
  g.at_all.forEach(h => all.push({ ...h, kind: 'at_all' }))
  g.mine.forEach(h => all.push({ ...h, kind: 'mine' }))
  return all.sort((a, b) => a.ts - b.ts)
})

// 上下文抽屉 (支持滚动翻页)
const ctx = ref({
  visible: false, loading: false, messages: [], targetText: '',
  chatId: '', targetTs: 0,
  hasMoreBefore: false, hasMoreAfter: false,
  beforeCursor: null, afterCursor: null,
  loadingMore: false,
})
const ctxBodyRef = ref(null)

async function openContext(h) {
  ctx.value = {
    visible: true, loading: true, messages: [], targetText: h.text,
    chatId: h.chat_id, targetTs: h.ts,
    hasMoreBefore: false, hasMoreAfter: false,
    beforeCursor: null, afterCursor: null, loadingMore: false,
  }
  try {
    const d = await getQtContext(h.chat_id, h.ts)
    if (d.ok) {
      ctx.value.messages = d.messages || []
      ctx.value.hasMoreBefore = d.has_more_before
      ctx.value.hasMoreAfter = d.has_more_after
      ctx.value.beforeCursor = d.before_cursor
      ctx.value.afterCursor = d.after_cursor
    }
  }
  catch (e) { message.error('加载上下文失败') }
  finally {
    ctx.value.loading = false
    // 滚动到目标消息
    await nextTick()
    scrollToTarget()
  }
}

function scrollToTarget() {
  const el = ctxBodyRef.value
  if (!el) return
  const target = el.querySelector('.ctx-msg.target')
  if (target) target.scrollIntoView({ block: 'center', behavior: 'auto' })
}

async function loadMoreContext(direction) {
  if (ctx.value.loadingMore) return
  const cursor = direction === 'before' ? ctx.value.beforeCursor : ctx.value.afterCursor
  if (!cursor) return
  ctx.value.loadingMore = true
  try {
    const d = await getQtContextPage(ctx.value.chatId, cursor, direction)
    if (d.ok && d.messages?.length) {
      if (direction === 'before') {
        ctx.value.messages = [...d.messages, ...ctx.value.messages]
        ctx.value.hasMoreBefore = d.has_more_before
        ctx.value.beforeCursor = d.before_cursor
      } else {
        ctx.value.messages = [...ctx.value.messages, ...d.messages]
        ctx.value.hasMoreAfter = d.has_more_after
        ctx.value.afterCursor = d.after_cursor
      }
    }
  } catch (e) { message.error('加载更多失败') }
  finally { ctx.value.loadingMore = false }
}

function onCtxScroll() {
  const el = ctxBodyRef.value
  if (!el) return
  const nearTop = el.scrollTop < 40
  const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
  if (nearTop && ctx.value.hasMoreBefore) loadMoreContext('before')
  if (nearBottom && ctx.value.hasMoreAfter) loadMoreContext('after')
}

async function loadStatus() {
  try { status.value = await getQtStatus() } catch (e) {}
}

async function loadSummary() {
  summaryLoading.value = true
  try {
    const d = await getQtDailySummary(date.value)
    if (d.ok) {
      summary.value = d
      // 默认选中第一个群
      if (!activeCid.value && d.groups?.length)
        activeCid.value = d.groups[0].cid
    } else {
      summary.value = null
    }
  }
  catch (e) { summary.value = null }
  finally { summaryLoading.value = false }
}

async function loadTasks() {
  try {
    const d = await getQtTasks(date.value)
    tasks.value = d.ok ? (d.tasks || []) : []
  }
  catch (e) { tasks.value = [] }
}

async function loadDocs() {
  docsLoading.value = true
  try {
    const d = await getQtDocs(docsDays.value, '', docsTypeFilter.value)
    if (d.ok) {
      docsData.value = d
    } else {
      docsData.value = null
    }
  } catch (e) { docsData.value = null }
  finally { docsLoading.value = false }
}

async function refreshAll() {
  await Promise.all([loadSummary(), loadTasks()])
}

function openDocUrl(url) {
  window.open(url, '_blank', 'noopener,noreferrer')
}

function shortUrl(url) {
  if (!url) return ''
  if (url.length <= 60) return url
  return url.slice(0, 30) + '...' + url.slice(-20)
}

onMounted(async () => {
  await loadStatus()
  refreshAll()
  loadDocs()
})

watch(date, () => { refreshAll() })
watch(docsDays, () => { loadDocs() })
watch(docsTypeFilter, () => { loadDocs() })
</script>

<template>
  <div class="qt-page">
    <!-- 顶栏 -->
    <div class="qt-header">
      <h2 class="wb-page-title">💬 轻推工作</h2>
      <a-tag :color="status.connected ? 'green' : 'red'">
        {{ status.connected ? '已就绪' : '不可用' }}
      </a-tag>
      <div class="qt-header-spacer" />
      <a-date-picker v-if="activeTab === 'messages'" v-model:value="date" value-format="YYYY-MM-DD" size="small" :allow-clear="false" />
      <a-select v-else-if="activeTab === 'docs'" v-model:value="docsDays" size="small" style="width:100px">
        <a-select-option :value="1">今天</a-select-option>
        <a-select-option :value="3">3天</a-select-option>
        <a-select-option :value="7">7天</a-select-option>
        <a-select-option :value="14">14天</a-select-option>
      </a-select>
      <a-button class="wb-btn" size="small" :loading="activeTab === 'messages' ? summaryLoading : docsLoading" @click="activeTab === 'messages' ? refreshAll() : loadDocs()">刷新</a-button>
    </div>

    <!-- Tab 切换 -->
    <a-tabs v-model:activeKey="activeTab" size="small" class="qt-tabs">
      <a-tab-pane key="messages" tab="📋 消息概览">
        <!-- 指标条 -->
        <div class="qt-metrics" v-if="summary">
          <div class="qt-metric">
            <span class="qt-metric-num">{{ summary.my_total }}</span>
            <span class="qt-metric-lbl">我发言</span>
          </div>
          <div class="qt-metric qt-metric--warn">
            <span class="qt-metric-num">@{{ summary.mention_total || 0 }}</span>
            <span class="qt-metric-lbl">@提及</span>
          </div>
          <div class="qt-metric">
            <span class="qt-metric-num">{{ summary.group_count || 0 }}</span>
            <span class="qt-metric-lbl">工作群</span>
          </div>
          <div class="qt-metric">
            <span class="qt-metric-num">{{ tasks.length }}</span>
            <span class="qt-metric-lbl">待办关注</span>
          </div>
        </div>

        <!-- 主体: 左右分栏 -->
        <a-spin :spinning="summaryLoading">
          <div class="qt-body" v-if="summary && summary.groups">
            <!-- 左栏: 群列表 -->
            <div class="qt-side">
              <div class="qt-side-head">工作群 ({{ summary.groups.length }})</div>
              <div
                v-for="g in summary.groups"
                :key="g.cid"
                class="qt-side-item"
                :class="{ active: g.cid === activeCid }"
                @click="activeCid = g.cid"
              >
                <div class="qt-side-name">{{ g.session }}</div>
                <div class="qt-side-counts">
                  <span v-if="g.mention_count" class="qt-cnt qt-cnt--red">{{ g.mention_count }}</span>
                  <span v-if="g.at_all_count" class="qt-cnt qt-cnt--orange">{{ g.at_all_count }}</span>
                  <span v-if="g.mine_count" class="qt-cnt qt-cnt--green">{{ g.mine_count }}</span>
                </div>
              </div>
            </div>

            <!-- 右栏: 消息流 -->
            <div class="qt-main">
              <div class="qt-main-head">
                {{ summary.groups.find(g => g.cid === activeCid)?.session || '请选择群' }}
                <span class="qt-main-legend">
                  <span class="qt-lg qt-lg--red">@我</span>
                  <span class="qt-lg qt-lg--orange">@所有人</span>
                  <span class="qt-lg qt-lg--green">我</span>
                </span>
              </div>
              <div class="qt-msgs">
                <div
                  v-for="(h, i) in activeMessages"
                  :key="i"
                  class="qt-msg"
                  :class="'qt-msg--' + h.kind"
                  @click="openContext(h)"
                  :title="'点击查看上下文'"
                >
                  <span class="qt-msg-time">{{ h.time }}</span>
                  <span class="qt-msg-badge">
                    <span v-if="h.kind === 'mention'" class="qt-badge qt-badge--red">@我</span>
                    <span v-else-if="h.kind === 'at_all'" class="qt-badge qt-badge--orange">@所有人</span>
                    <span v-else class="qt-badge qt-badge--green">我</span>
                  </span>
                  <span class="qt-msg-text">{{ h.text }}</span>
                </div>
                <a-empty v-if="!activeMessages.length" description="该群当日无消息" />
              </div>
            </div>
          </div>
        </a-spin>
      </a-tab-pane>

      <a-tab-pane key="docs" :tab="`📄 群文档${docsData?.total ? ' (' + docsData.total + ')' : ''}`">
        <!-- 文档统计 + 筛选 -->
        <div class="qt-docs-bar" v-if="docsData">
          <div class="qt-docs-stats">
            <span class="qt-doc-stat" v-for="(count, type) in docsData.by_type" :key="type">
              <a-tag :color="docTypeColors[type] || 'default'" size="small">{{ docsData.type_labels[type] || type }} {{ count }}</a-tag>
            </span>
          </div>
          <a-select v-model:value="docsTypeFilter" size="small" style="width:120px" placeholder="全部类型" allow-clear>
            <a-select-option value="">全部类型</a-select-option>
            <a-select-option v-for="(label, type) in docsData.type_labels" :key="type" :value="type">{{ label }}</a-select-option>
          </a-select>
        </div>

        <!-- 文档列表 (按天分组) -->
        <a-spin :spinning="docsLoading">
          <div class="qt-docs-list" v-if="docsGrouped.length">
            <div v-for="group in docsGrouped" :key="group.date" class="qt-doc-day">
              <div class="qt-doc-day-head">
                <span class="qt-doc-day-date">{{ group.date }}</span>
                <span class="qt-doc-day-count">{{ group.docs.length }} 个文档</span>
              </div>
              <div
                v-for="(doc, i) in group.docs"
                :key="i"
                class="qt-doc-item"
                @click="openDocUrl(doc.url)"
              >
                <div class="qt-doc-icon">
                  <a-tag :color="docTypeColors[doc.type] || 'default'" size="small">{{ doc.type_label }}</a-tag>
                </div>
                <div class="qt-doc-content">
                  <div class="qt-doc-title">{{ doc.title || shortUrl(doc.url) }}</div>
                  <div class="qt-doc-meta">
                    <span class="qt-doc-chat">{{ doc.chat_name }}</span>
                    <span class="qt-doc-time">{{ doc.time_str }}</span>
                    <span v-if="doc.is_me" class="qt-doc-me">我发的</span>
                  </div>
                </div>
                <div class="qt-doc-arrow">↗</div>
              </div>
            </div>
          </div>
          <a-empty v-else-if="!docsLoading" description="暂无群文档" />
        </a-spin>
      </a-tab-pane>
    </a-tabs>

    <!-- 上下文抽屉 -->
    <a-drawer v-model:open="ctx.visible" placement="right" :width="520" title="📎 消息上下文">
      <div class="ctx-target">
        <a-tag color="blue" size="small">目标消息</a-tag>
        <div class="ctx-target-text">{{ ctx.targetText }}</div>
      </div>
      <a-divider style="margin:10px 0" />
      <a-spin :spinning="ctx.loading">
        <div class="ctx-scroll" ref="ctxBodyRef" @scroll="onCtxScroll">
          <div v-if="ctx.hasMoreBefore" class="ctx-more">
            <a-spin size="small" v-if="ctx.loadingMore" />
            <span v-else>向上滚动加载更早消息…</span>
          </div>
          <div class="ctx-list">
            <div
              v-for="(m, i) in ctx.messages"
              :key="m.ts + '-' + i"
              class="ctx-msg"
              :class="{ mine: m.mine, target: m.is_target }"
            >
              <div class="ctx-meta">
                <span class="ctx-time">{{ m.time }}</span>
                <a-tag :color="m.mine ? 'green' : 'blue'" size="small">{{ m.mine ? '我' : '对方' }}</a-tag>
                <a-tag v-if="m.is_target" color="red" size="small">目标</a-tag>
              </div>
              <div class="ctx-body">{{ m.text }}</div>
            </div>
          </div>
          <div v-if="ctx.hasMoreAfter" class="ctx-more">
            <a-spin size="small" v-if="ctx.loadingMore" />
            <span v-else>向下滚动加载更多消息…</span>
          </div>
        </div>
      </a-spin>
    </a-drawer>
  </div>
</template>

<style scoped>
.qt-page { max-width: 1080px; margin: 0 auto; padding: 0; }
.qt-header { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.qt-header-spacer { flex: 1; }
.qt-tabs :deep(.ant-tabs-nav) { margin-bottom: 14px; }

/* 指标条 */
.qt-metrics {
  display: flex; gap: 0; margin-bottom: 14px;
  background: #fff; border: 1px solid #eef0f3; border-radius: 10px; overflow: hidden;
}
.qt-metric {
  flex: 1; display: flex; align-items: baseline; gap: 8px; justify-content: center;
  padding: 12px 0; border-right: 1px solid #f0f0f0;
}
.qt-metric:last-child { border-right: none; }
.qt-metric-num { font-size: 22px; font-weight: 600; color: #1f2937; }
.qt-metric-lbl { font-size: 12px; color: #888; }
.qt-metric--warn .qt-metric-num { color: #ff4d4f; }
.qt-metric--warn { background: #fffafa; }

/* 左右分栏 */
.qt-body { display: flex; gap: 12px; align-items: flex-start; }
.qt-side {
  width: 260px; flex-shrink: 0; border: 1px solid #eef0f3; border-radius: 10px;
  background: #fff; max-height: calc(100vh - 220px); overflow-y: auto;
}
.qt-side-head {
  padding: 10px 14px; font-size: 12px; font-weight: 600; color: #888;
  border-bottom: 1px solid #f0f0f0; position: sticky; top: 0; background: #fff;
}
.qt-side-item {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 10px 14px; cursor: pointer; border-bottom: 1px solid #f7f7f7;
  transition: background .12s;
}
.qt-side-item:hover { background: #f5f7fa; }
.qt-side-item.active { background: #eef4ff; border-left: 3px solid #1677ff; }
.qt-side-name { font-size: 13px; color: #333; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.qt-side-counts { display: flex; gap: 4px; }
.qt-cnt {
  min-width: 20px; height: 20px; border-radius: 10px; font-size: 11px;
  display: inline-flex; align-items: center; justify-content: center; padding: 0 6px;
}
.qt-cnt--red { background: #fff1f0; color: #ff4d4f; }
.qt-cnt--orange { background: #fff7e6; color: #fa8c16; }
.qt-cnt--green { background: #f6ffed; color: #52c41a; }

/* 右栏消息流 */
.qt-main {
  flex: 1; min-width: 0; border: 1px solid #eef0f3; border-radius: 10px;
  background: #fff; max-height: calc(100vh - 220px); overflow-y: auto; display: flex; flex-direction: column;
}
.qt-main-head {
  padding: 10px 16px; font-size: 14px; font-weight: 600; color: #1f2937;
  border-bottom: 1px solid #f0f0f0; position: sticky; top: 0; background: #fff;
  display: flex; align-items: center; justify-content: space-between; z-index: 1;
}
.qt-main-legend { display: flex; gap: 10px; font-size: 11px; font-weight: 400; color: #888; }
.qt-lg--red { color: #ff4d4f; }
.qt-lg--orange { color: #fa8c16; }
.qt-lg--green { color: #52c41a; }

.qt-msgs { padding: 8px 16px 16px; }
.qt-msg {
  display: flex; align-items: flex-start; gap: 8px; padding: 9px 10px;
  border-radius: 8px; margin-bottom: 6px; cursor: pointer; transition: background .12s;
  border: 1px solid transparent;
}
.qt-msg:hover { box-shadow: 0 1px 4px rgba(0,0,0,.05); }
.qt-msg--mention { background: #fff7f5; border-color: #ffd8d5; }
.qt-msg--at_all { background: #fffbe6; border-color: #ffe9b3; }
.qt-msg--mine { background: #fafbfc; border-color: #f0f0f0; }
.qt-msg-time { color: #999; font-size: 11px; white-space: nowrap; font-variant-numeric: tabular-nums; padding-top: 1px; }
.qt-msg-badge { flex-shrink: 0; }
.qt-badge {
  font-size: 10px; padding: 1px 6px; border-radius: 4px; font-weight: 500; white-space: nowrap;
}
.qt-badge--red { background: #ff4d4f; color: #fff; }
.qt-badge--orange { background: #fa8c16; color: #fff; }
.qt-badge--green { background: #52c41a; color: #fff; }
.qt-msg-text { flex: 1; font-size: 13px; line-height: 1.55; color: #333; word-break: break-word; }

/* ── 群文档 ── */
.qt-docs-bar {
  display: flex; align-items: center; gap: 12px; margin-bottom: 14px;
  background: #fff; border: 1px solid #eef0f3; border-radius: 10px; padding: 10px 14px;
}
.qt-docs-stats { flex: 1; display: flex; flex-wrap: wrap; gap: 4px; }

.qt-docs-list { display: flex; flex-direction: column; gap: 16px; }
.qt-doc-day {
  background: #fff; border: 1px solid #eef0f3; border-radius: 10px; overflow: hidden;
}
.qt-doc-day-head {
  display: flex; align-items: center; gap: 10px; padding: 10px 14px;
  background: #f8f9fb; border-bottom: 1px solid #f0f0f0;
  font-size: 13px; font-weight: 600; color: #555;
}
.qt-doc-day-count { font-size: 12px; font-weight: 400; color: #999; }

.qt-doc-item {
  display: flex; align-items: center; gap: 12px; padding: 12px 14px;
  cursor: pointer; border-bottom: 1px solid #f7f7f7; transition: background .12s;
}
.qt-doc-item:last-child { border-bottom: none; }
.qt-doc-item:hover { background: #f5f7fa; }
.qt-doc-icon { flex-shrink: 0; }
.qt-doc-content { flex: 1; min-width: 0; }
.qt-doc-title {
  font-size: 14px; color: #1f2937; font-weight: 500;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.qt-doc-meta {
  display: flex; align-items: center; gap: 8px; margin-top: 3px;
  font-size: 12px; color: #999;
}
.qt-doc-chat { color: #666; }
.qt-doc-time { font-variant-numeric: tabular-nums; }
.qt-doc-me {
  background: #f6ffed; color: #52c41a; font-size: 10px; padding: 0 6px;
  border-radius: 4px; font-weight: 500;
}
.qt-doc-arrow { flex-shrink: 0; color: #ccc; font-size: 14px; }

/* 上下文抽屉 */
.ctx-target {
  background: #f0f7ff; border: 1px solid #bae0ff; border-radius: 8px; padding: 10px 12px;
}
.ctx-target-text { font-size: 13px; line-height: 1.6; color: #333; margin-top: 6px; }
.ctx-scroll { max-height: calc(100vh - 260px); overflow-y: auto; }
.ctx-more {
  text-align: center; padding: 8px 0; font-size: 12px; color: #aaa;
  user-select: none;
}
.ctx-list { display: flex; flex-direction: column; gap: 6px; }
.ctx-msg { padding: 8px 10px; border-radius: 6px; background: #f9f9f9; }
.ctx-msg.mine { background: #e6f4ff; }
.ctx-msg.target { outline: 2px solid #ff4d4f; }
.ctx-meta { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.ctx-time { color: #999; font-size: 12px; font-variant-numeric: tabular-nums; }
.ctx-body { font-size: 13px; line-height: 1.6; color: #333; word-break: break-word; }
</style>
