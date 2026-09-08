<script setup>
import { ref, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useWorkbenchStore } from '@/store/workbench'
import { openProjectChat } from '@/api'

const store = useWorkbenchStore()
const activeTab = ref('')

const tabs = computed(() => store.categories.map(c => ({ key: c.key, name: c.name })))

watch(
  () => store.categories,
  (cats) => {
    if (cats.length && !activeTab.value)
      activeTab.value = cats[0].key
  },
  { immediate: true },
)

const tabMap = computed(() => {
  const m = {}
  store.categories.forEach(c => { m[c.key] = c })
  return m
})

async function doStart(proj) {
  const r = await store.start(proj.id)
  if (r.ok)
    message.success(r.msg || '已启动')
  else
    message.error(r.error || '启动失败')
  store.refresh()
  return r
}

async function doStop(proj) {
  const r = await store.stop(proj.id)
  message.info(r.msg || '已停止')
  store.refresh()
}

async function doOpen(proj) {
  const r = await store.open(proj.id)
  if (r.ok)
    message.success(r.msg || '已打开目录')
  else
    message.error(r.error || '打开失败')
}

function openUrl(proj) {
  if (!proj.url)
    return
  if (proj.cmd && !proj.active) {
    message.warning(`${proj.name} 尚未启动，正在帮你启动，就绪后自动打开`)
    doStart(proj).then(async (r) => {
      if (!r || !r.ok)
        return
      for (let i = 0; i < 20; i++) {
        const st = await store.status(proj.id).catch(() => ({ active: false }))
        if (st.active) {
          window.open(proj.url, '_blank')
          return
        }
        await new Promise(r => setTimeout(r, 1200))
      }
      message.error(`${proj.name} 启动超时，请查看日志确认`)
    })
    return
  }
  window.open(proj.url, '_blank')
}

async function doChat(proj) {
  const r = await openProjectChat({ proj_id: proj.id })
  if (r.ok)
    message.success(r.msg || '已打开对话')
  else
    message.error(r.error || '打开对话失败')
  store.refresh()
}

function shortPath(p) {
  return p.replace('/Users/zhanghao/', '~/')
}

function gitTag(proj) {
  const g = proj.git
  if (!g?.isGit)
    return null
  return {
    branch: g.branch || '-',
    dirty: g.dirty,
    remote: g.remote || '本地',
    last: g.lastCommit,
  }
}
</script>

<template>
  <div class="wb-projects">
    <a-skeleton :loading="store.loading" active>
      <a-tabs v-model:activeKey="activeTab" type="card" class="wb-proj-tabs">
        <a-tab-pane v-for="t in tabs" :key="t.key" :tab="`${t.name} (${tabMap[t.key].projects.length})`">
          <div class="wb-proj-grid">
            <div
              v-for="proj in tabMap[t.key].projects"
              :key="proj.id"
              class="wb-proj-card"
            >
              <!-- Card Header -->
              <div class="wb-proj-card-head">
                <div class="wb-proj-card-title">
                  <span
                    v-if="proj.type !== 'doc'"
                    class="wb-proj-status-dot"
                    :class="{ active: proj.active }"
                  ></span>
                  {{ proj.name }}
                </div>
                <div class="wb-proj-card-badges">
                  <a-tooltip v-if="proj.hasSession" title="已有项目对话，将续接不重复新建">
                    <a-tag color="cyan" style="margin: 0; font-size: 11px">💬 已建会话</a-tag>
                  </a-tooltip>
                  <a-tag
                    v-if="proj.type !== 'doc'"
                    :color="proj.active ? 'success' : 'default'"
                    style="margin: 0; font-size: 11px"
                  >
                    {{ proj.active ? '运行中' : '未启动' }}
                  </a-tag>
                </div>
              </div>

              <!-- Description -->
              <p class="wb-proj-desc">{{ proj.desc }}</p>

              <!-- Git Info -->
              <div v-if="gitTag(proj)" class="wb-proj-git">
                <div class="wb-proj-git-row">
                  <a-tag color="blue" style="font-size: 11px">{{ gitTag(proj).branch }}</a-tag>
                  <a-tag v-if="gitTag(proj).dirty > 0" color="orange" style="font-size: 11px">{{ gitTag(proj).dirty }} 改动</a-tag>
                  <a-tag v-else color="green" style="font-size: 11px">干净</a-tag>
                  <span class="wb-proj-git-remote">{{ gitTag(proj).remote }}</span>
                </div>
                <div v-if="gitTag(proj).last" class="wb-proj-git-last">
                  {{ gitTag(proj).last }}
                </div>
              </div>
              <a-tag v-else color="purple" style="font-size: 11px">非 git 项目</a-tag>

              <!-- Path -->
              <div class="wb-proj-path">{{ shortPath(proj.path) }}</div>

              <!-- Actions -->
              <div class="wb-proj-actions">
                <a-button size="small" type="primary" ghost @click="doChat(proj)">
                  💬 对话
                </a-button>
                <a-button v-if="proj.type !== 'doc' && proj.cmd" size="small" @click="doStart(proj)">
                  启动
                </a-button>
                <a-button v-if="proj.type !== 'doc' && proj.cmd" size="small" danger :disabled="!proj.active" @click="doStop(proj)">
                  停止
                </a-button>
                <a-button v-if="proj.url" size="small" @click="openUrl(proj)">
                  打开页面
                </a-button>
                <a-button size="small" @click="doOpen(proj)">
                  打开目录
                </a-button>
              </div>
            </div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-skeleton>
  </div>
</template>

<style scoped>
.wb-projects {
  display: flex;
  flex-direction: column;
}

.wb-proj-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 16px;
}

.wb-proj-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}

.wb-proj-card {
  background: var(--wb-bg-elevated);
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius-md);
  padding: 18px;
  transition: all var(--wb-transition);
}
.wb-proj-card:hover {
  box-shadow: var(--wb-shadow-md);
  border-color: var(--wb-border-light);
}

.wb-proj-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.wb-proj-card-title {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.2px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.wb-proj-card-badges {
  display: flex;
  align-items: center;
  gap: 6px;
}

.wb-proj-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #d1d5db;
  flex-shrink: 0;
}
.wb-proj-status-dot.active {
  background: #27a644;
  box-shadow: 0 0 0 3px rgba(39, 166, 68, 0.12);
}

.wb-proj-desc {
  min-height: 36px;
  color: var(--wb-text-secondary);
  font-size: 13px;
  margin-bottom: 12px;
  line-height: 1.5;
}

.wb-proj-git {
  font-size: 12px;
  background: var(--wb-bg);
  border-radius: var(--wb-radius-sm);
  padding: 10px 12px;
  margin-bottom: 12px;
}
.wb-proj-git-row {
  display: flex;
  align-items: center;
  gap: 4px;
}
.wb-proj-git-remote {
  color: var(--wb-text-tertiary);
  margin-left: auto;
  font-size: 11px;
}
.wb-proj-git-last {
  color: var(--wb-text-tertiary);
  margin-top: 6px;
  background: rgba(0, 0, 0, 0.03);
  padding: 4px 8px;
  border-radius: 4px;
  font-family: var(--wb-font-mono);
  font-size: 11px;
}

.wb-proj-path {
  font-size: 11px;
  color: var(--wb-text-tertiary);
  margin-bottom: 12px;
  font-family: var(--wb-font-mono);
}

.wb-proj-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
</style>
