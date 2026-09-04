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
  <div>
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
      <h2 style="margin:0;font-size:18px">🔄 自动化任务</h2>
      <a-tag color="blue">{{ jobs.length }}</a-tag>
      <div style="flex:1"></div>
      <a-button size="small" @click="load">刷新</a-button>
    </div>

    <a-alert
      v-if="scheduler"
      style="margin-bottom:16px"
      type="success"
      show-icon
      :message="`调度器运行中 · ${jobs.filter(j=>j.enabled).length} 个任务启用`"
      :description="scheduler.replace(/\\n/g, ' ')"
    />

    <a-table
      :data-source="jobs"
      :loading="loading"
      :pagination="false"
      row-key="id"
      size="middle"
      :columns="[
        { title: '名称', dataIndex: 'name', key: 'name', width: 220 },
        { title: '调度', dataIndex: 'schedule', key: 'schedule', width: 130 },
        { title: '状态', dataIndex: 'status_text', key: 'status_text', width: 100 },
        { title: '上次运行', dataIndex: 'last_run', key: 'last_run', width: 170 },
        { title: '下次运行', dataIndex: 'next_run', key: 'next_run', width: 170 },
        { title: '错误', dataIndex: 'last_error', key: 'last_error', ellipsis: true },
        { title: '操作', key: 'actions', width: 200 },
      ]"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status_text'">
          <a-tag :color="record.color">{{ record.status_text }}</a-tag>
          <a-tag v-if="record.last_status === 'error'" color="red">上次失败</a-tag>
        </template>
        <template v-else-if="column.key === 'last_run'">
          {{ record.last_run ? record.last_run.slice(0, 16) : '—' }}
        </template>
        <template v-else-if="column.key === 'next_run'">
          {{ record.next_run ? record.next_run.slice(0, 16) : '—' }}
        </template>
        <template v-else-if="column.key === 'last_error'">
          <span v-if="record.last_error" style="color:#cf1322">{{ record.last_error }}</span>
          <span v-else style="color:#aaa">—</span>
        </template>
        <template v-else-if="column.key === 'actions'">
          <a-button size="small" type="primary" :loading="running === record.id" @click="run(record)">
            运行
          </a-button>
          <a-button
            size="small"
            :danger="record.enabled"
            :loading="toggling === record.id"
            style="margin-left:6px"
            @click="toggle(record)"
          >
            {{ record.enabled ? '暂停' : '启用' }}
          </a-button>
          <a-button size="small" style="margin-left:6px" @click="showLog(record)">日志</a-button>
        </template>
      </template>
    </a-table>

    <!-- 日志弹窗 -->
    <a-modal
      :open="logModal.visible"
      :title="`日志 · ${logModal.job?.name || ''}`"
      @cancel="logModal.visible = false"
      footer=""
      width="720px"
    >
      <pre style="max-height:480px;overflow:auto;background:#141414;color:#d8e0ea;padding:12px;border-radius:8px;font-size:12px;white-space:pre-wrap;word-break:break-all">
{{ logModal.job?.recent_log || '暂无日志' }}
      </pre>
    </a-modal>
  </div>
</template>