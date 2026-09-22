<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import {
  getQtStatus, getQtDailySummary, getQtTasks, getQtContext, getQtContextPage,
  getQtDocs, getQtTodos, analyzeQtTodos, operateQtTodo, addQtTodo, getQtTodoLearning,
  getCachedDocs, openDocInChrome, openOrGenerateDoc,
} from '@/api'

const status = ref({ connected: false, state: 'unknown', hint: '' })
const date = ref(new Date().toISOString().slice(0, 10))
const activeTab = ref('todos')

const summary = ref(null)
const summaryLoading = ref(false)
const tasks = ref([])

// ── 群文档 ──
const docsData = ref(null)
const docsLoading = ref(false)
const docsDays = ref(7)
const docsTypeFilter = ref('')
const docsShowArticle = ref(false)

// 文档按权重排序
const docsSorted = computed(() => docsData.value?.docs || [])
const docsFiltered = computed(() => {
  if (!docsSorted.value.length) return []
  let list = docsSorted.value
  if (!docsShowArticle.value) list = list.filter(d => d.type !== 'article')
  if (docsTypeFilter.value) list = list.filter(d => d.type === docsTypeFilter.value)
  return list
})

const docTypeColors = {
  article: 'blue', drive: 'cyan', excel: 'green', pdf: 'red',
  word: 'geekblue', markdown: 'purple', tencent_doc: 'orange',
  ones: 'volcano', oa: 'gold', minmetals: 'magenta', link: 'default', file: 'default',
}

// ── Chrome 直开 (从轻推 localStorage 缓存) ──
const cachedDocMap = ref({})  // {file_id: doc}
const openingDoc = ref(false)

async function loadCachedDocs() {
  try {
    const d = await getCachedDocs()
    if (d.ok) {
      const map = {}
      for (const doc of (d.docs || [])) map[doc.file_id] = doc
      cachedDocMap.value = map
    }
  } catch (e) { cachedDocMap.value = {} }
}

// 从群文档 URL 或 title 提取 fileId
function docFileId(url) {
  if (!url) return ''
  // 匹配 /xxx 或 fileId=xxx 格式的 10-20 位数字
  const m = url.match(/(?:\/|fileId=)(\d{10,20})(?=\D|$)/)
  return m ? m[1] : ''
}

// 判断群文档是否可直开 (有 fileId 即可: 有缓存用缓存, 无缓存用 API 生成)
function canDirectOpen(doc) {
  return !!(docFileId(doc.url) || docFileId(doc.title))
}

// 判断群文档是否有缓存 (有缓存的直开更可靠)
function cachedFileId(doc) {
  const fid = docFileId(doc.url) || docFileId(doc.title)
  return fid && cachedDocMap.value[fid] ? fid : ''
}

async function openCachedDoc(fileId) {
  openingDoc.value = true
  try {
    const d = await openDocInChrome(fileId)
    if (d.ok) {
      message.success(`已在 Chrome 打开: ${d.name}`)
    } else {
      message.error(d.error || '打开失败')
    }
  } catch (e) { message.error('打开失败') }
  finally { openingDoc.value = false }
}

// 对无缓存的文档, 用 API 生成新 URL 再打开
async function openGeneratedDoc(doc) {
  const fid = docFileId(doc.url) || docFileId(doc.title)
  if (!fid) return
  openingDoc.value = true
  try {
    // 从 URL 或标题推断文件名和类型
    let fileName = doc.title || fid
    let fileType = 'xlsx'
    if (fileName.endsWith('.docx') || fileName.endsWith('.doc')) fileType = 'docx'
    else if (fileName.endsWith('.pptx') || fileName.endsWith('.ppt')) fileType = 'pptx'
    else if (fileName.endsWith('.xls')) fileType = 'xls'

    const d = await openOrGenerateDoc(fid, fileName, fileType)
    if (d.ok) {
      message.success(`已在 Chrome 打开: ${fileName}`)
    } else {
      message.error(d.error || '生成 URL 失败')
    }
  } catch (e) { message.error('打开失败') }
  finally { openingDoc.value = false }
}

// 统一入口: 有缓存用缓存, 无缓存用 API 生成
async function openDocDirect(doc) {
  const fid = cachedFileId(doc)
  if (fid) {
    await openCachedDoc(fid)
  } else {
    await openGeneratedDoc(doc)
  }
}

// ── 智能待办 ──
const todos = ref([])
const todosLoading = ref(false)
const todosAnalyzing = ref(false)
const todoFilter = ref('pending')
const todoDays = ref(3)
const showAddTodo = ref(false)
const newTodoTitle = ref('')
const newTodoChat = ref('')
const learningData = ref(null)

// 展开的待办 (Set of todo ids)
const expandedTodos = ref(new Set())
const toggleTodoExpand = (id) => {
  const s = new Set(expandedTodos.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  expandedTodos.value = s
}
const TODO_COLLAPSE_LEN = 80
const todoDisplayText = (t) => {
  if (expandedTodos.value.has(t.id)) return t.title
  return t.title.length > TODO_COLLAPSE_LEN
    ? t.title.slice(0, TODO_COLLAPSE_LEN) + '…'
    : t.title
}

// 按日期分组待办 (时间轴)
const groupedTodos = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10)
  const beforeYesterday = new Date(Date.now() - 2 * 86400000).toISOString().slice(0, 10)
  const groups = {}
  for (const t of todos.value) {
    const day = (t.time_str || '').slice(0, 10) || 'unknown'
    if (!groups[day]) groups[day] = []
    groups[day].push(t)
  }
  const dayLabel = (d) => {
    if (d === today) return '📅 今天'
    if (d === yesterday) return '📆 昨天'
    if (d === beforeYesterday) return '📆 前天'
    return `📋 ${d}`
  }
  return Object.keys(groups).sort((a, b) => b.localeCompare(a)).map(d => ({
    key: d, label: dayLabel(d), items: groups[d],
  }))
})

const scoreColor = (score) => {
  if (score >= 70) return '#ff4d4f'
  if (score >= 50) return '#fa8c16'
  if (score >= 35) return '#1677ff'
  return '#999'
}

const scoreLabel = (score) => {
  if (score >= 70) return '紧急'
  if (score >= 50) return '重要'
  if (score >= 35) return '关注'
  return '低'
}

// 左侧群列表选中项
const activeCid = ref(null)

const activeMessages = computed(() => {
  if (!summary.value || !activeCid.value) return []
  const g = summary.value.groups.find(x => x.cid === activeCid.value)
  if (!g) return []
  const all = []
  g.mention.forEach(h => all.push({ ...h, kind: 'mention' }))
  g.at_all.forEach(h => all.push({ ...h, kind: 'at_all' }))
  g.mine.forEach(h => all.push({ ...h, kind: 'mine' }))
  return all.sort((a, b) => a.ts - b.ts)
})

const ctx = ref({
  visible: false, loading: false, messages: [], targetText: '',
  chatId: '', targetTs: 0,
  hasMoreBefore: false, hasMoreAfter: false,
  beforeCursor: null, afterCursor: null, loadingMore: false,
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
  } catch (e) { message.error('加载上下文失败') }
  finally {
    ctx.value.loading = false
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
  if (el.scrollTop < 40 && ctx.value.hasMoreBefore) loadMoreContext('before')
  if (el.scrollHeight - el.scrollTop - el.clientHeight < 40 && ctx.value.hasMoreAfter) loadMoreContext('after')
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
      if (!activeCid.value && d.groups?.length)
        activeCid.value = d.groups[0].cid
    } else { summary.value = null }
  } catch (e) { summary.value = null }
  finally { summaryLoading.value = false }
}

async function loadTasks() {
  try {
    const d = await getQtTasks(date.value)
    tasks.value = d.ok ? (d.tasks || []) : []
  } catch (e) { tasks.value = [] }
}

async function loadDocs() {
  docsLoading.value = true
  try {
    const excludeTypes = docsShowArticle.value ? '' : 'article'
    const d = await getQtDocs(docsDays.value, '', docsTypeFilter.value, '', excludeTypes)
    docsData.value = d.ok ? d : null
  } catch (e) { docsData.value = null }
  finally { docsLoading.value = false }
}

// ── 待办操作 ──
async function loadTodos() {
  todosLoading.value = true
  try {
    const d = await getQtTodos(todoFilter.value)
    todos.value = d.ok ? (d.todos || []) : []
  } catch (e) { todos.value = [] }
  finally { todosLoading.value = false }
}

async function doAnalyze() {
  todosAnalyzing.value = true
  try {
    const d = await analyzeQtTodos(todoDays.value)
    if (d.ok) {
      message.success(`分析完成: 扫描 ${d.scanned_messages} 条消息, 生成 ${d.total} 个待办`)
      await loadTodos()
      await loadLearning()
    } else {
      message.error(d.error || '分析失败')
    }
  } catch (e) { message.error('分析失败') }
  finally { todosAnalyzing.value = false }
}

async function doOperate(todoId, action) {
  try {
    const d = await operateQtTodo(todoId, action)
    if (d.ok) {
      // 本地更新状态
      const todo = todos.value.find(t => t.id === todoId)
      if (todo) todo.status = d.new_status
      if (action === 'confirm' || action === 'ignore') {
        await loadLearning()
      }
    }
  } catch (e) { message.error('操作失败') }
}

async function doAddTodo() {
  if (!newTodoTitle.value.trim()) return
  try {
    const d = await addQtTodo(newTodoTitle.value, newTodoChat.value)
    if (d.ok) {
      message.success('已添加')
      newTodoTitle.value = ''
      newTodoChat.value = ''
      showAddTodo.value = false
      await loadTodos()
    }
  } catch (e) { message.error('添加失败') }
}

async function loadLearning() {
  try {
    const d = await getQtTodoLearning()
    learningData.value = d.ok ? d : null
  } catch (e) { learningData.value = null }
}

async function refreshAll() {
  await Promise.all([loadSummary(), loadTasks()])
}

function openDocUrl(url) {
  window.open(url, '_blank', 'noopener,noreferrer')
}

function shortUrl(url) {
  if (!url) return ''
  return url.length <= 60 ? url : url.slice(0, 30) + '...' + url.slice(-20)
}

onMounted(async () => {
  await loadStatus()
  refreshAll()
  loadDocs()
  loadTodos()
  loadLearning()
  loadCachedDocs()
})

watch(date, () => { refreshAll() })
watch(docsDays, () => { loadDocs() })
watch(docsTypeFilter, () => { loadDocs() })
watch(docsShowArticle, () => { loadDocs() })
watch(todoFilter, () => { loadTodos() })
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
      <a-button v-if="activeTab === 'todos'" type="primary" size="small" :loading="todosAnalyzing" @click="doAnalyze">🔍 重新分析</a-button>
      <a-button class="wb-btn" size="small" :loading="activeTab === 'messages' ? summaryLoading : activeTab === 'docs' ? docsLoading : todosLoading" @click="activeTab === 'messages' ? refreshAll() : activeTab === 'docs' ? loadDocs() : loadTodos()">刷新</a-button>
    </div>

    <!-- Tab 切换 -->
    <a-tabs v-model:activeKey="activeTab" size="small" class="qt-tabs">
      <!-- ── 智能待办 ── -->
      <a-tab-pane key="todos" :tab="`🎯 智能待办${todos.length ? ' (' + todos.length + ')' : ''}`">
        <!-- 工具栏 -->
        <div class="qt-todo-bar">
          <a-radio-group v-model:value="todoFilter" size="small">
            <a-radio-button value="pending">待处理</a-radio-button>
            <a-radio-button value="confirmed">已确认</a-radio-button>
            <a-radio-button value="ignored">已忽略</a-radio-button>
            <a-radio-button value="all">全部</a-radio-button>
          </a-radio-group>
          <div style="flex:1"></div>
          <a-select v-model:value="todoDays" size="small" style="width:90px">
            <a-select-option :value="1">1天</a-select-option>
            <a-select-option :value="3">3天</a-select-option>
            <a-select-option :value="7">7天</a-select-option>
          </a-select>
          <a-button size="small" @click="showAddTodo = !showAddTodo">+ 手动添加</a-button>
        </div>

        <!-- 手动添加表单 -->
        <div v-if="showAddTodo" class="qt-todo-add">
          <a-input v-model:value="newTodoTitle" placeholder="待办标题..." size="small" @pressEnter="doAddTodo" />
          <a-input v-model:value="newTodoChat" placeholder="来源群 (可选)" size="small" style="width:160px" />
          <a-button type="primary" size="small" @click="doAddTodo">添加</a-button>
        </div>

        <!-- 学习模式展示 -->
        <div v-if="learningData && (learningData.keywords?.length || learningData.chats?.length)" class="qt-learn">
          <span class="qt-learn-title">🧠 已学习模式:</span>
          <a-tag v-for="kw in learningData.keywords.slice(0, 8)" :key="kw.keyword" size="small"
            :color="kw.weight > 0 ? 'green' : 'red'">
            {{ kw.keyword }} {{ kw.weight > 0 ? '+' : '' }}{{ kw.weight.toFixed(1) }}
          </a-tag>
          <a-tag v-for="ch in learningData.chats.slice(0, 3)" :key="ch.chat_name" size="small"
            :color="ch.weight > 0 ? 'green' : 'red'">
            {{ ch.chat_name }} {{ ch.weight > 0 ? '+' : '' }}{{ ch.weight.toFixed(1) }}
          </a-tag>
        </div>

        <!-- 待办列表 -->
        <a-spin :spinning="todosLoading || todosAnalyzing">
          <div class="qt-todo-timeline" v-if="todos.length">
            <div v-for="g in groupedTodos" :key="g.key" class="qt-todo-group">
              <div class="qt-todo-group-header">
                <span class="qt-todo-group-dot"></span>
                <span class="qt-todo-group-label">{{ g.label }}</span>
                <span class="qt-todo-group-count">{{ g.items.length }}条</span>
              </div>
              <div class="qt-todo-group-body">
                <div v-for="t in g.items" :key="t.id" class="qt-todo-item" :class="'qt-todo--' + t.status">
                  <!-- 评分徽章 -->
                  <div class="qt-todo-score" :style="{ color: scoreColor(t.score), borderColor: scoreColor(t.score) }">
                    <span class="qt-todo-score-num">{{ t.score }}</span>
                    <span class="qt-todo-score-lbl">{{ scoreLabel(t.score) }}</span>
                  </div>
                  <!-- 内容 -->
                  <div class="qt-todo-body">
                    <div class="qt-todo-title" :class="{ expanded: expandedTodos.has(t.id) }" @click="toggleTodoExpand(t.id)">
                      {{ todoDisplayText(t) }}
                    </div>
                    <div class="qt-todo-expand-hint" v-if="t.title.length > TODO_COLLAPSE_LEN" @click="toggleTodoExpand(t.id)">
                      {{ expandedTodos.has(t.id) ? '收起 ▲' : `展开全文 (${t.title.length}字) ▼` }}
                    </div>
                    <!-- body 仅在 ≠title 时展示 -->
                    <div class="qt-todo-fullbody" v-if="expandedTodos.has(t.id) && t.body && t.body !== t.title">
                      <div class="qt-todo-fullbody-label">完整内容:</div>
                      <pre class="qt-todo-fullbody-text">{{ t.body }}</pre>
                    </div>
                    <div class="qt-todo-meta">
                      <a-tag size="small" color="blue">{{ t.topic }}</a-tag>
                      <span class="qt-todo-chat">{{ t.chat_name }}</span>
                      <span class="qt-todo-time">{{ t.time_str }}</span>
                      <span v-if="t.related_count > 1" class="qt-todo-rel">📌 {{ t.related_count }}条相关</span>
                      <span v-if="t.source === 'manual'" class="qt-todo-manual">✋ 手动</span>
                    </div>
                    <!-- 评分明细 -->
                    <div class="qt-todo-detail" v-if="t.score_detail?.matched_kw?.length">
                      <span v-for="kw in t.score_detail.matched_kw" :key="kw" class="qt-todo-kw">{{ kw }}</span>
                    </div>
                  </div>
                  <!-- 操作按钮 -->
                  <div class="qt-todo-actions" v-if="t.status === 'pending'">
                    <a-button size="small" type="primary" @click="doOperate(t.id, 'confirm')">✓ 确认</a-button>
                    <a-button size="small" @click="doOperate(t.id, 'ignore')">✕ 忽略</a-button>
                  </div>
                  <div class="qt-todo-actions" v-else>
                    <a-tag :color="t.status === 'confirmed' ? 'green' : 'default'" size="small">
                      {{ t.status === 'confirmed' ? '✓ 已确认' : '已忽略' }}
                    </a-tag>
                    <a-button size="small" type="link" @click="doOperate(t.id, 'reopen')">恢复</a-button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <a-empty v-else-if="!todosLoading && !todosAnalyzing" description="暂无待办, 点击「重新分析」扫描消息">
            <a-button type="primary" size="small" :loading="todosAnalyzing" @click="doAnalyze">🔍 开始分析</a-button>
          </a-empty>
        </a-spin>
      </a-tab-pane>

      <!-- ── 消息概览 ── -->
      <a-tab-pane key="messages" tab="📋 消息概览">
        <div class="qt-metrics" v-if="summary">
          <div class="qt-metric"><span class="qt-metric-num">{{ summary.my_total }}</span><span class="qt-metric-lbl">我发言</span></div>
          <div class="qt-metric qt-metric--warn"><span class="qt-metric-num">@{{ summary.mention_total || 0 }}</span><span class="qt-metric-lbl">@提及</span></div>
          <div class="qt-metric"><span class="qt-metric-num">{{ summary.group_count || 0 }}</span><span class="qt-metric-lbl">工作群</span></div>
          <div class="qt-metric"><span class="qt-metric-num">{{ tasks.length }}</span><span class="qt-metric-lbl">待办关注</span></div>
        </div>
        <a-spin :spinning="summaryLoading">
          <div class="qt-body" v-if="summary && summary.groups">
            <div class="qt-side">
              <div class="qt-side-head">工作群 ({{ summary.groups.length }})</div>
              <div v-for="g in summary.groups" :key="g.cid" class="qt-side-item" :class="{ active: g.cid === activeCid }" @click="activeCid = g.cid">
                <div class="qt-side-name">{{ g.session }}</div>
                <div class="qt-side-counts">
                  <span v-if="g.mention_count" class="qt-cnt qt-cnt--red">{{ g.mention_count }}</span>
                  <span v-if="g.at_all_count" class="qt-cnt qt-cnt--orange">{{ g.at_all_count }}</span>
                  <span v-if="g.mine_count" class="qt-cnt qt-cnt--green">{{ g.mine_count }}</span>
                </div>
              </div>
            </div>
            <div class="qt-main">
              <div class="qt-main-head">
                {{ summary.groups.find(g => g.cid === activeCid)?.session || '请选择群' }}
                <span class="qt-main-legend">
                  <span class="qt-lg qt-lg--red">@我</span><span class="qt-lg qt-lg--orange">@所有人</span><span class="qt-lg qt-lg--green">我</span>
                </span>
              </div>
              <div class="qt-msgs">
                <div v-for="(h, i) in activeMessages" :key="i" class="qt-msg" :class="'qt-msg--' + h.kind" @click="openContext(h)" :title="'点击查看上下文'">
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

      <!-- ── 群文档 ── -->
      <a-tab-pane key="docs" :tab="`📄 群文档${docsData?.total ? ' (' + docsData.total + ')' : ''}`">
        <a-alert v-if="docsData?.total" type="info" show-icon banner style="margin-bottom:8px;font-size:12px" message="🚀 直开需要安装 Tampermonkey 脚本 (WPS编辑器iframe需要Authorization头注入)">
          <template #action>
            <a-space size="small">
              <a href="https://chrome.google.com/webstore/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo" target="_blank" style="font-size:12px">装 Tampermonkey</a>
              <a :href="`/api/qingtui/wps-auth-script/download`" download="qingtui-wps-auth.user.js" style="font-size:12px">下载脚本</a>
            </a-space>
          </template>
        </a-alert>
        <div class="qt-docs-bar" v-if="docsData">
          <div class="qt-docs-stats">
            <span class="qt-doc-stat" :class="{ 'qt-stat-active': docsTypeFilter === '' }" @click="docsTypeFilter = ''">
              <a-tag :color="docsTypeFilter === '' ? 'blue' : 'default'" size="small">全部 {{ docsData.total }}</a-tag>
            </span>
            <span class="qt-doc-stat" :class="{ 'qt-stat-active': docsTypeFilter === type }" v-for="(count, type) in docsData.by_type" :key="type" @click="docsTypeFilter = docsTypeFilter === type ? '' : type">
              <a-tag :color="docsTypeFilter === type ? docTypeColors[type] || 'blue' : 'default'" size="small">{{ docsData.type_labels[type] || type }} {{ count }}</a-tag>
            </span>
          </div>
          <a-checkbox v-model:checked="docsShowArticle" size="small">显示企业号文章</a-checkbox>
        </div>
        <a-spin :spinning="docsLoading">
          <div class="qt-docs-list" v-if="docsFiltered.length">
            <div v-for="(doc, i) in docsFiltered" :key="i" class="qt-doc-item" @click="openDocUrl(doc.url)">
              <div class="qt-doc-rank" :class="{ 'rank-top': i < 3 }">{{ i + 1 }}</div>
              <div class="qt-doc-icon"><a-tag :color="docTypeColors[doc.type] || 'default'" size="small">{{ doc.type_label }}</a-tag></div>
              <div class="qt-doc-content">
                <div class="qt-doc-title">{{ doc.title || shortUrl(doc.url) }}</div>
                <div class="qt-doc-meta">
                  <span class="qt-doc-weight" :title="`权重 ${doc.weight}`">⭐ {{ doc.weight }}</span>
                  <span v-if="doc.mention_count > 1" class="qt-doc-mentions">🔥 {{ doc.mention_count }}次提及</span>
                  <span v-if="doc.chat_count > 1" class="qt-doc-spread">📢 {{ doc.chat_count }}个群</span>
                  <span class="qt-doc-chat" :title="doc.chat_names.join(', ')">{{ doc.chat_names.length > 2 ? doc.chat_names.slice(0, 2).join('、') + '等' : doc.chat_names.join('、') }}</span>
                  <span class="qt-doc-time">{{ doc.time_str }}</span>
                  <span v-if="doc.has_me" class="qt-doc-me">我发过</span>
                  <span v-if="canDirectOpen(doc)" class="qt-doc-chrome" :class="{ 'qt-doc-cached': cachedFileId(doc) }" @click.stop="openDocDirect(doc)" :title="cachedFileId(doc) ? `Chrome 直开 (缓存${cachedDocMap[cachedFileId(doc)]?.permission === 'write' ? '·可编辑' : '·只读'})` : 'Chrome 直开 (API 生成·可能报24002)'">🚀 直开</span>
                </div>
              </div>
              <div class="qt-doc-arrow">↗</div>
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
          <div v-if="ctx.hasMoreBefore" class="ctx-more"><a-spin size="small" v-if="ctx.loadingMore" /><span v-else>向上滚动加载更早消息…</span></div>
          <div class="ctx-list">
            <div v-for="(m, i) in ctx.messages" :key="m.ts + '-' + i" class="ctx-msg" :class="{ mine: m.mine, target: m.is_target }">
              <div class="ctx-meta"><span class="ctx-time">{{ m.time }}</span><a-tag :color="m.mine ? 'green' : 'blue'" size="small">{{ m.mine ? '我' : '对方' }}</a-tag><a-tag v-if="m.is_target" color="red" size="small">目标</a-tag></div>
              <div class="ctx-body">{{ m.text }}</div>
            </div>
          </div>
          <div v-if="ctx.hasMoreAfter" class="ctx-more"><a-spin size="small" v-if="ctx.loadingMore" /><span v-else>向下滚动加载更多消息…</span></div>
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
.qt-metrics { display: flex; gap: 0; margin-bottom: 14px; background: #fff; border: 1px solid #eef0f3; border-radius: 10px; overflow: hidden; }
.qt-metric { flex: 1; display: flex; align-items: baseline; gap: 8px; justify-content: center; padding: 12px 0; border-right: 1px solid #f0f0f0; }
.qt-metric:last-child { border-right: none; }
.qt-metric-num { font-size: 22px; font-weight: 600; color: #1f2937; }
.qt-metric-lbl { font-size: 12px; color: #888; }
.qt-metric--warn .qt-metric-num { color: #ff4d4f; }
.qt-metric--warn { background: #fffafa; }

/* 左右分栏 */
.qt-body { display: flex; gap: 12px; align-items: flex-start; }
.qt-side { width: 260px; flex-shrink: 0; border: 1px solid #eef0f3; border-radius: 10px; background: #fff; max-height: calc(100vh - 220px); overflow-y: auto; }
.qt-side-head { padding: 10px 14px; font-size: 12px; font-weight: 600; color: #888; border-bottom: 1px solid #f0f0f0; position: sticky; top: 0; background: #fff; }
.qt-side-item { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 10px 14px; cursor: pointer; border-bottom: 1px solid #f7f7f7; transition: background .12s; }
.qt-side-item:hover { background: #f5f7fa; }
.qt-side-item.active { background: #eef4ff; border-left: 3px solid #1677ff; }
.qt-side-name { font-size: 13px; color: #333; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.qt-side-counts { display: flex; gap: 4px; }
.qt-cnt { min-width: 20px; height: 20px; border-radius: 10px; font-size: 11px; display: inline-flex; align-items: center; justify-content: center; padding: 0 6px; }
.qt-cnt--red { background: #fff1f0; color: #ff4d4f; } .qt-cnt--orange { background: #fff7e6; color: #fa8c16; } .qt-cnt--green { background: #f6ffed; color: #52c41a; }

.qt-main { flex: 1; min-width: 0; border: 1px solid #eef0f3; border-radius: 10px; background: #fff; max-height: calc(100vh - 220px); overflow-y: auto; display: flex; flex-direction: column; }
.qt-main-head { padding: 10px 16px; font-size: 14px; font-weight: 600; color: #1f2937; border-bottom: 1px solid #f0f0f0; position: sticky; top: 0; background: #fff; display: flex; align-items: center; justify-content: space-between; z-index: 1; }
.qt-main-legend { display: flex; gap: 10px; font-size: 11px; font-weight: 400; color: #888; }
.qt-lg--red { color: #ff4d4f; } .qt-lg--orange { color: #fa8c16; } .qt-lg--green { color: #52c41a; }
.qt-msgs { padding: 8px 16px 16px; }
.qt-msg { display: flex; align-items: flex-start; gap: 8px; padding: 9px 10px; border-radius: 8px; margin-bottom: 6px; cursor: pointer; transition: background .12s; border: 1px solid transparent; }
.qt-msg:hover { box-shadow: 0 1px 4px rgba(0,0,0,.05); }
.qt-msg--mention { background: #fff7f5; border-color: #ffd8d5; } .qt-msg--at_all { background: #fffbe6; border-color: #ffe9b3; } .qt-msg--mine { background: #fafbfc; border-color: #f0f0f0; }
.qt-msg-time { color: #999; font-size: 11px; white-space: nowrap; font-variant-numeric: tabular-nums; padding-top: 1px; }
.qt-msg-badge { flex-shrink: 0; }
.qt-badge { font-size: 10px; padding: 1px 6px; border-radius: 4px; font-weight: 500; white-space: nowrap; }
.qt-badge--red { background: #ff4d4f; color: #fff; } .qt-badge--orange { background: #fa8c16; color: #fff; } .qt-badge--green { background: #52c41a; color: #fff; }
.qt-msg-text { flex: 1; font-size: 13px; line-height: 1.55; color: #333; word-break: break-word; }

/* ── 智能待办 ── */
.qt-todo-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.qt-todo-add { display: flex; gap: 8px; margin-bottom: 12px; }
.qt-learn { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; margin-bottom: 12px; padding: 8px 10px; background: #f8f9fb; border-radius: 8px; }
.qt-learn-title { font-size: 12px; color: #888; margin-right: 4px; }
.qt-todo-list { display: flex; flex-direction: column; gap: 8px; }
/* 时间轴分组 */
.qt-todo-timeline { display: flex; flex-direction: column; gap: 4px; }
.qt-todo-group { position: relative; }
.qt-todo-group-header {
  display: flex; align-items: center; gap: 8px; padding: 10px 0 6px;
  position: sticky; top: 0; z-index: 2; background: #fafafa;
}
.qt-todo-group-dot {
  width: 8px; height: 8px; border-radius: 50%; background: #5e6ad2; flex-shrink: 0;
}
.qt-todo-group-label { font-size: 14px; font-weight: 600; color: #1f2937; }
.qt-todo-group-count { font-size: 12px; color: #999; }
.qt-todo-group-body { display: flex; flex-direction: column; gap: 8px; padding-left: 16px; border-left: 2px solid #eef0f3; margin-left: 3px; }
.qt-todo-item {
  display: flex; align-items: flex-start; gap: 12px; padding: 12px 14px;
  background: #fff; border: 1px solid #eef0f3; border-radius: 10px; transition: box-shadow .12s;
}
.qt-todo-item:hover { box-shadow: 0 2px 8px rgba(0,0,0,.04); }
.qt-todo--confirmed { opacity: 0.6; }
.qt-todo--ignored { opacity: 0.4; }
.qt-todo-score {
  flex-shrink: 0; width: 48px; height: 48px; border-radius: 10px; border: 2px solid;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.qt-todo-score-num { font-size: 18px; font-weight: 700; }
.qt-todo-score-lbl { font-size: 10px; }
.qt-todo-body { flex: 1; min-width: 0; }
.qt-todo-title { font-size: 14px; color: #1f2937; line-height: 1.5; margin-bottom: 4px; word-break: break-word; cursor: pointer; }
.qt-todo-title.expanded { background: #f0f5ff; padding: 6px 8px; border-radius: 4px; }
.qt-todo-expand-hint { font-size: 12px; color: #5e6ad2; cursor: pointer; margin-bottom: 4px; user-select: none; }
.qt-todo-expand-hint:hover { text-decoration: underline; }
.qt-todo-fullbody { margin: 6px 0; padding: 8px 10px; background: #f8f9fb; border-radius: 6px; border-left: 3px solid #5e6ad2; }
.qt-todo-fullbody-label { font-size: 11px; color: #999; margin-bottom: 4px; }
.qt-todo-fullbody-text { font-size: 13px; color: #4b5563; line-height: 1.6; white-space: pre-wrap; word-break: break-word; margin: 0; font-family: inherit; }
.qt-todo-meta { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #999; flex-wrap: wrap; }
.qt-todo-chat { color: #666; }
.qt-todo-time { font-variant-numeric: tabular-nums; }
.qt-todo-rel { color: #fa8c16; }
.qt-todo-manual { color: #5e6ad2; }
.qt-todo-detail { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 4px; }
.qt-todo-kw { font-size: 11px; color: #888; background: #f5f7fa; padding: 1px 6px; border-radius: 4px; }
.qt-todo-actions { flex-shrink: 0; display: flex; flex-direction: column; gap: 4px; align-items: flex-end; }

/* ── 群文档 ── */
.qt-docs-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; background: #fff; border: 1px solid #eef0f3; border-radius: 10px; padding: 10px 14px; }
.qt-docs-stats { flex: 1; display: flex; flex-wrap: wrap; gap: 6px; }
.qt-doc-stat { cursor: pointer; user-select: none; }
.qt-doc-stat .ant-tag { cursor: pointer; transition: all .12s; margin: 0; }
.qt-doc-stat .ant-tag:hover { transform: scale(1.05); }
.qt-stat-active .ant-tag { font-weight: 600; box-shadow: 0 0 0 2px rgba(94,106,210,.15); }
.qt-docs-list { display: flex; flex-direction: column; gap: 4px; }
.qt-doc-item { display: flex; align-items: center; gap: 10px; padding: 12px 14px; cursor: pointer; border: 1px solid #eef0f3; border-radius: 8px; background: #fff; transition: background .12s; }
.qt-doc-item:hover { background: #f5f7fa; }
.qt-doc-rank { flex-shrink: 0; width: 24px; height: 24px; border-radius: 50%; background: #f0f0f0; color: #999; font-size: 12px; font-weight: 600; display: flex; align-items: center; justify-content: center; }
.qt-doc-rank.rank-top { background: #1677ff; color: #fff; }
.qt-doc-icon { flex-shrink: 0; }
.qt-doc-content { flex: 1; min-width: 0; }
.qt-doc-title { font-size: 14px; color: #1f2937; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.qt-doc-meta { display: flex; align-items: center; gap: 8px; margin-top: 3px; font-size: 12px; color: #999; flex-wrap: wrap; }
.qt-doc-weight { color: #fa8c16; font-weight: 600; }
.qt-doc-mentions { color: #ff4d4f; font-weight: 500; }
.qt-doc-spread { color: #722ed1; font-weight: 500; }
.qt-doc-chat { color: #666; }
.qt-doc-time { font-variant-numeric: tabular-nums; }
.qt-doc-me { background: #f6ffed; color: #52c41a; font-size: 10px; padding: 0 6px; border-radius: 4px; font-weight: 500; }
.qt-doc-arrow { flex-shrink: 0; color: #ccc; font-size: 14px; }
.qt-doc-chrome { cursor: pointer; background: #f0f0f0; color: #888; font-size: 11px; padding: 1px 8px; border-radius: 4px; font-weight: 500; transition: all .12s; user-select: none; }
.qt-doc-chrome:hover { background: #999; color: #fff; }
.qt-doc-chrome.qt-doc-cached { background: #f0f5ff; color: #5e6ad2; }
.qt-doc-chrome.qt-doc-cached:hover { background: #5e6ad2; color: #fff; }

/* 上下文抽屉 */
.ctx-target { background: #f0f7ff; border: 1px solid #bae0ff; border-radius: 8px; padding: 10px 12px; }
.ctx-target-text { font-size: 13px; line-height: 1.6; color: #333; margin-top: 6px; }
.ctx-scroll { max-height: calc(100vh - 260px); overflow-y: auto; }
.ctx-more { text-align: center; padding: 8px 0; font-size: 12px; color: #aaa; user-select: none; }
.ctx-list { display: flex; flex-direction: column; gap: 6px; }
.ctx-msg { padding: 8px 10px; border-radius: 6px; background: #f9f9f9; }
.ctx-msg.mine { background: #e6f4ff; }
.ctx-msg.target { outline: 2px solid #ff4d4f; }
.ctx-meta { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.ctx-time { color: #999; font-size: 12px; font-variant-numeric: tabular-nums; }
.ctx-body { font-size: 13px; line-height: 1.6; color: #333; word-break: break-word; }
</style>
