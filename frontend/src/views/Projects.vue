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
  // 未运行的工具类 Web 应用先启动再打开, 避免打开空白页
  if (proj.cmd && !proj.active) {
    message.warning(`${proj.name} 尚未启动，正在帮你启动，就绪后自动打开`)
    doStart(proj).then(async (r) => {
      if (!r || !r.ok)
        return // doStart 已提示错误
      // 启动成功后轮询 status 直到 active, 再打开
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
  <div>
    <a-skeleton :loading="store.loading" active>
      <a-tabs v-model:activeKey="activeTab" type="card">
        <a-tab-pane v-for="t in tabs" :key="t.key" :tab="`${t.name} (${tabMap[t.key].projects.length})`">
          <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px">
            <a-card
              v-for="proj in tabMap[t.key].projects"
              :key="proj.id"
              hoverable
              :title="proj.name"
              style="border-radius: 8px"
            >
              <template #extra>
                <span style="display:flex;align-items:center;gap:6px">
                  <a-tooltip v-if="proj.hasSession" title="已有项目对话，将续接不重复新建">
                    <a-tag color="cyan" style="margin:0">💬 已建会话</a-tag>
                  </a-tooltip>
                  <a-tag :color="proj.active ? 'success' : 'default'" :style="proj.type === 'doc' ? 'display:none' : ''">
                    {{ proj.active ? '运行中' : '未启动' }}
                  </a-tag>
                </span>
              </template>

              <p style="min-height: 36px; color: #666; font-size: 13px; margin-bottom: 8px">{{ proj.desc }}</p>

              <!-- Git 状态 -->
              <div v-if="gitTag(proj)" style="font-size: 12px; background: #fafafa; border-radius: 6px; padding: 8px; margin-bottom: 12px">
                <div><a-tag color="blue">{{ gitTag(proj).branch }}</a-tag>
                  <a-tag v-if="gitTag(proj).dirty > 0" color="orange">{{ gitTag(proj).dirty }} 改动</a-tag>
                  <a-tag v-else color="green">干净</a-tag>
                  <span style="color:#888; float:right">{{ gitTag(proj).remote }}</span>
                </div>
                <div v-if="gitTag(proj).last" style="color:#999; margin-top:6px; background:#eee; padding:4px 6px; border-radius:4px; font-family:monospace">
                  {{ gitTag(proj).last }}
                </div>
              </div>

              <a-tag v-else color="purple">非 git 项目</a-tag>

              <div style="font-size: 12px; color: #aaa; margin-bottom: 12px">
                {{ shortPath(proj.path) }}
              </div>

              <!-- 操作按钮 -->
              <div style="display: flex; gap: 8px; flex-wrap: wrap">
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
            </a-card>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-skeleton>
  </div>
</template>