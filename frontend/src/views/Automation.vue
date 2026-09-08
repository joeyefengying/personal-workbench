<script setup>
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { getCronJobs, toggleCronJob, runCronJob } from '@/api'

const jobs = ref([])
const loading = ref(false)
const scheduler = ref('')
const logModal = ref({ visible: false, job: null })
const toggling = ref(null)
const running = ref(null)

async function load() {
  loading.value = true
  try {
    const d = await getCronJobs()
    jobs.value = d.jobs || []
    scheduler.value = d.scheduler || ''
  }
  catch (e) {
    message.error('加载定时任务失败: ' + (e?.message || e))
  }
  finally {
    loading.value = false
  }
}

async function toggle(job) {
  toggling.value = job.id
  try {
    const d = await toggleCronJob({ id: job.id, enabled: !job.enabled })
    if (d.ok)
      message.success(d.msg || '操作成功')
    else
      message.error(d.error || '操作失败')
    await load()
  }
  finally {
    toggling.value = null
  }
}

async function run(job) {
  running.value = job.id
  try {
    const d = await runCronJob({ id: job.id })
    if (d.ok) {
      message.success(d.msg || '已触发运行')
      setTimeout(load, 3000)
    }
    else {
      message.error(d.error || '触发失败')
    }
  }
  finally {
    running.value = null
  }
}

function showLog(job) {
  logModal.value = { visible: true, job }
}

onMounted(load)
</script>

<template>
  <div class="automation-page">
    <div class="automation-header">
      <h2 class="wb-page-title">🔄 自动化任务</h2>
      <a-tag class="automation-count-tag">{{ jobs.length }}</a-tag>
      <div class="automation-header-spacer"></div>
      <a-button class="wb-btn" size="small" @click="load">刷新</a-button>
    </div>

    <div v-if="scheduler" class="automation-alert">
      <span class="automation-alert-dot"></span>
      <div class="automation-alert-content">
        <div class="automation-alert-message">
          调度器运行中 · {{ jobs.filter(j => j.enabled).length }} 个任务启用
        </div>
        <div class="automation-alert-desc">{{ scheduler.replace(/\n/g, ' ') }}</div>
      </div>
    </div>

    <div class="wb-card-elevated automation-table-wrap">
      <a-table
        :data-source="jobs"
        :loading="loading"
        :pagination="false"
        row-key="id"
        size="middle"
        :columns="[
          { title: '名称', dataIndex: 'name', key: 'name', width: 220 },
          { title: '调度', dataIndex: 'schedule', key: 'schedule', width: 130 },
          { title: '状态', dataIndex: 'status_text', key: 'status_text', width: 120 },
          { title: '上次运行', dataIndex: 'last_run', key: 'last_run', width: 170 },
          { title: '下次运行', dataIndex: 'next_run', key: 'next_run', width: 170 },
          { title: '错误', dataIndex: 'last_error', key: 'last_error', ellipsis: true },
          { title: '操作', key: 'actions', width: 210 },
        ]"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status_text'">
            <span class="wb-status-badge" :class="record.enabled ? 'is-active' : 'is-inactive'">
              <span class="wb-status-dot"></span>
              {{ record.status_text }}
            </span>
            <span v-if="record.last_status === 'error'" class="wb-status-badge is-error">
              <span class="wb-status-dot"></span>
              上次失败
            </span>
          </template>
          <template v-else-if="column.key === 'last_run'">
            <span class="wb-cell-text">{{ record.last_run ? record.last_run.slice(0, 16) : '—' }}</span>
          </template>
          <template v-else-if="column.key === 'next_run'">
            <span class="wb-cell-text">{{ record.next_run ? record.next_run.slice(0, 16) : '—' }}</span>
          </template>
          <template v-else-if="column.key === 'last_error'">
            <span v-if="record.last_error" class="wb-cell-error">{{ record.last_error }}</span>
            <span v-else class="wb-cell-muted">—</span>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-button
              class="wb-btn wb-btn-primary"
              size="small"
              type="primary"
              :loading="running === record.id"
              @click="run(record)"
            >
              运行
            </a-button>
            <a-button
              class="wb-btn"
              size="small"
              :danger="record.enabled"
              :loading="toggling === record.id"
              @click="toggle(record)"
            >
              {{ record.enabled ? '暂停' : '启用' }}
            </a-button>
            <a-button class="wb-btn wb-btn-ghost" size="small" @click="showLog(record)">日志</a-button>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 日志弹窗 -->
    <a-modal
      :open="logModal.visible"
      :title="`日志 · ${logModal.job?.name || ''}`"
      class="wb-log-modal"
      @cancel="logModal.visible = false"
      footer=""
      width="720px"
    >
      <pre class="wb-log-pre">{{ logModal.job?.recent_log || '暂无日志' }}</pre>
    </a-modal>
  </div>
</template>

<style scoped>
/* ── Page Title ── */
.wb-page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.3px;
  color: var(--wb-text-primary);
  line-height: 1.3;
}

/* ── Page Layout ── */
.automation-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.automation-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.automation-count-tag {
  margin: 0 !important;
  background: var(--wb-accent-bg) !important;
  color: var(--wb-accent) !important;
  border-color: transparent !important;
  font-weight: 600 !important;
  font-size: 12px !important;
  border-radius: var(--wb-radius-sm) !important;
  padding: 0 8px !important;
  line-height: 20px !important;
}

.automation-header-spacer {
  flex: 1;
}

/* ── Alert ── */
.automation-alert {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  background: var(--wb-bg-elevated);
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius-md);
  transition: border-color var(--wb-transition), box-shadow var(--wb-transition);
}

.automation-alert-dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 50%;
  background: var(--wb-success);
  box-shadow: 0 0 0 3px rgba(39, 166, 68, 0.16);
}

.automation-alert-content {
  flex: 1;
  min-width: 0;
}

.automation-alert-message {
  font-size: 13px;
  font-weight: 600;
  color: var(--wb-text-primary);
  line-height: 1.5;
}

.automation-alert-desc {
  margin-top: 2px;
  font-size: 12px;
  color: var(--wb-text-tertiary);
  line-height: 1.5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Table Wrapper ── */
.automation-table-wrap {
  padding: 4px 4px 8px;
  overflow: hidden;
}

/* ── Table Overrides ── */
.automation-table-wrap :deep(.ant-table) {
  border-radius: var(--wb-radius-md);
  background: transparent;
}

.automation-table-wrap :deep(.ant-table-container) {
  border-radius: var(--wb-radius-md);
}

.automation-table-wrap :deep(.ant-table-thead > tr > th) {
  background: var(--wb-bg-elevated) !important;
  font-weight: 600;
  font-size: 12px;
  color: var(--wb-text-tertiary) !important;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  border-bottom: 1px solid var(--wb-border) !important;
  padding: 12px 16px !important;
}

.automation-table-wrap :deep(.ant-table-tbody > tr > td) {
  font-size: 13px;
  color: var(--wb-text-primary);
  border-bottom: 1px solid var(--wb-border) !important;
  padding: 14px 16px !important;
  transition: background var(--wb-transition);
}

.automation-table-wrap :deep(.ant-table-tbody > tr:last-child > td) {
  border-bottom: none !important;
}

.automation-table-wrap :deep(.ant-table-tbody > tr:hover > td) {
  background: rgba(94, 106, 210, 0.04) !important;
}

.automation-table-wrap :deep(.ant-table-tbody > tr > td:first-child) {
  font-weight: 500;
}

/* ── Cell Text ── */
.wb-cell-text {
  color: var(--wb-text-secondary);
  font-variant-numeric: tabular-nums;
}

.wb-cell-error {
  color: var(--wb-danger);
}

.wb-cell-muted {
  color: var(--wb-text-tertiary);
}

/* ── Status Badges ── */
.wb-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 999px;
  line-height: 18px;
  border: 1px solid var(--wb-border);
  background: var(--wb-bg-elevated);
  color: var(--wb-text-secondary);
  transition: all var(--wb-transition);
}

.wb-status-badge + .wb-status-badge {
  margin-left: 6px;
}

.wb-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.wb-status-badge.is-active {
  color: var(--wb-success);
  background: rgba(39, 166, 68, 0.08);
  border-color: rgba(39, 166, 68, 0.2);
}

.wb-status-badge.is-active .wb-status-dot {
  background: var(--wb-success);
  box-shadow: 0 0 0 2px rgba(39, 166, 68, 0.18);
}

.wb-status-badge.is-inactive {
  color: var(--wb-text-tertiary);
  background: var(--wb-bg);
  border-color: var(--wb-border);
}

.wb-status-badge.is-inactive .wb-status-dot {
  background: var(--wb-text-tertiary);
}

.wb-status-badge.is-error {
  color: var(--wb-danger);
  background: rgba(229, 72, 77, 0.08);
  border-color: rgba(229, 72, 77, 0.2);
}

.wb-status-badge.is-error .wb-status-dot {
  background: var(--wb-danger);
  box-shadow: 0 0 0 2px rgba(229, 72, 77, 0.18);
}

/* ── Buttons ── */
.automation-table-wrap :deep(.ant-btn) + .ant-btn {
  margin-left: 6px;
}

.wb-btn {
  border-radius: var(--wb-radius-sm) !important;
  font-weight: 500 !important;
  font-size: 12px !important;
  height: 28px !important;
  padding: 0 12px !important;
  border: 1px solid var(--wb-border) !important;
  background: var(--wb-bg-elevated) !important;
  color: var(--wb-text-secondary) !important;
  box-shadow: var(--wb-shadow-sm);
  transition: all var(--wb-transition) !important;
}

.wb-btn:hover {
  border-color: var(--wb-accent) !important;
  color: var(--wb-accent) !important;
  background: var(--wb-bg-elevated) !important;
  box-shadow: var(--wb-shadow-sm), var(--wb-shadow-glow);
}

.wb-btn-primary {
  background: var(--wb-accent) !important;
  border-color: var(--wb-accent) !important;
  color: #fff !important;
  box-shadow: var(--wb-shadow-sm);
}

.wb-btn-primary:hover {
  background: var(--wb-accent-hover) !important;
  border-color: var(--wb-accent-hover) !important;
  color: #fff !important;
  box-shadow: var(--wb-shadow-md), var(--wb-shadow-glow);
}

.wb-btn-ghost {
  background: transparent !important;
  box-shadow: none;
}

.wb-btn-ghost:hover {
  background: var(--wb-bg-elevated) !important;
}

/* danger variant uses ant default danger flag; refine the tone */
.automation-table-wrap :deep(.ant-btn-dangerous) {
  border-color: rgba(229, 72, 77, 0.3) !important;
  color: var(--wb-danger) !important;
  background: var(--wb-bg-elevated) !important;
}

.automation-table-wrap :deep(.ant-btn-dangerous:hover) {
  background: rgba(229, 72, 77, 0.08) !important;
  border-color: var(--wb-danger) !important;
  color: var(--wb-danger) !important;
}

/* ── Log Modal ── */
.wb-log-modal :deep(.ant-modal-content) {
  border-radius: var(--wb-radius-lg);
  box-shadow: var(--wb-shadow-lg);
  padding: 0 !important;
  overflow: hidden;
}

.wb-log-modal :deep(.ant-modal-header) {
  padding: 16px 20px !important;
  margin: 0 !important;
  border-bottom: 1px solid var(--wb-border);
  background: var(--wb-bg-elevated);
}

.wb-log-modal :deep(.ant-modal-title) {
  font-size: 15px;
  font-weight: 600;
  color: var(--wb-text-primary);
}

.wb-log-modal :deep(.ant-modal-body) {
  padding: 0 !important;
  background: #141416;
}

.wb-log-pre {
  margin: 0;
  padding: 16px 18px;
  max-height: 480px;
  overflow: auto;
  background: #141416;
  color: #d8e0ea;
  font-family: var(--wb-font-mono);
  font-size: 12px;
  line-height: 1.65;
  border-radius: 0;
  white-space: pre-wrap;
  word-break: break-all;
  letter-spacing: 0.2px;
}

.wb-log-pre::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.wb-log-pre::-webkit-scrollbar-track {
  background: transparent;
}

.wb-log-pre::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.12);
  border-radius: 4px;
}

.wb-log-pre::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

.wb-log-modal :deep(.ant-modal-close) {
  top: 16px;
  inset-inline-end: 18px;
  color: var(--wb-text-tertiary);
}
</style>
