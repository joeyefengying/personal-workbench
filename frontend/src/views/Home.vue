<script setup>
import { ref, computed, h, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useWorkbenchStore } from '@/store/workbench'

const store = useWorkbenchStore()
const activeTab = ref('')

const tabs = computed(() => store.categories.map(c => ({ key: c.key, name: c.name })))

// 数据到达后默认选中第一个分类
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
  window.open(proj.url, '_blank')
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
                <a-tag :color="proj.active ? 'success' : 'default'" :style="proj.type === 'doc' ? 'display:none' : ''">
                  {{ proj.active ? '运行中' : '未启动' }}
                </a-tag>
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
                <a-button v-if="proj.type !== 'doc' && proj.cmd" size="small" type="primary" @click="doStart(proj)">
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